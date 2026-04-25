"""PRE-VERIFY 페이즈 — 복구 액션을 적용 전에 시뮬레이션해 최선의 액션을 선택.

DIAGNOSE → [PRE-VERIFY] → RECOVER 순서로 동작.

각 후보 액션에 대해:
  - 과거 (action_type, cause_type) 성공률로 success_prob 추정
  - 액션이 만들 yield/OEE 델타와 곱해 expected_delta 산출
  - selection_score = expected_delta × confidence × (1 − risk_factor)

안전등급 A 공정에서 best score가 임계 미만이면 자동 거절 → HITL 강제.

VISION.md §6 Phase 5 "디지털 트윈 시뮬레이션 기반 의사결정" 의 1단계 구현.
"""
import asyncio

from v4.healing import RISK_NUMERIC
from v4.recurrence import (
    RECUR_DEMOTE_AT as _RECUR_DEMOTE_AT,
    RECUR_ESCALATE_AT as _RECUR_ESCALATE_AT,
    incident_signature,
)


# 안전등급별 최소 selection_score 기본값 (engine.preverify_thresholds 미설정 시 폴백).
# 런타임에는 EvolutionAgent의 `tune_preverify_threshold` 전략이 engine 사본을 자기 진화한다.
DEFAULT_SCORE_THRESHOLD_BY_SAFETY = {
    "A": 1e-4,    # 엄격 — 분명한 양의 기대 효과만 자동 실행
    "B": 0.0,     # 손해 안 나는 액션만
    "C": -1e-3,   # 약간의 위험 허용
}

# 하위 호환: 직접 import하던 backtest 등에서 참조
_SCORE_THRESHOLD_BY_SAFETY = DEFAULT_SCORE_THRESHOLD_BY_SAFETY

_COLD_START_ATTEMPTS = 2  # 이력 < 이 값이면 confidence를 success_prob로 사용

# Replay-based simulation — 과거 healing_history에서 같은 (step, action, cause) 결과로 예측
_REPLAY_MIN_SAMPLES = 2   # 이 값 이상이면 replay, 미만이면 휴리스틱 fallback


def _get_score_threshold(engine, safety_level: str) -> float:
    """engine.preverify_thresholds에서 우선 조회, 없으면 모듈 기본값."""
    runtime = getattr(engine, "preverify_thresholds", None)
    if runtime and safety_level in runtime:
        return float(runtime[safety_level])
    return DEFAULT_SCORE_THRESHOLD_BY_SAFETY.get(safety_level, 0.0)


async def run(engine, it: int, delay: float, anomalies: list, diagnoses: list) -> dict:
    """후보 액션 시뮬레이션 + 선택. recover.py가 사용할 plans 리스트 반환.

    Returns: {"plans": [{anomaly, diagnosis, ranked_actions, simulations,
                          selected, rejected_reason}, ...]}
    """
    await engine._emit("phase", {
        "iteration": it + 1,
        "phase": "preverify",
        "message": "복구 액션을 시뮬레이션합니다...",
    })
    await asyncio.sleep(delay)

    plans = []
    for anomaly, diagnosis in zip(anomalies, diagnoses):
        plans.append(_build_plan(engine, anomaly, diagnosis))

    # verify 페이즈에서 회수해 예측 vs 실측 비교에 사용
    engine._latest_preverify_predictions = {
        plan["anomaly"].get("step_id"): plan["simulations"][0]
        for plan in plans
        if plan.get("selected") and plan.get("simulations")
    }
    auto_rejected = sum(1 for p in plans if p["rejected_reason"])
    engine.preverify_counters["auto_rejected_total"] += auto_rejected
    engine.preverify_counters["plans_total"] += len(plans)

    await engine._emit("preverify_done", {
        "iteration": it + 1,
        "plans": [_serialize_plan(p) for p in plans],
        "auto_rejected": auto_rejected,
    })
    await asyncio.sleep(delay)

    return {"plans": plans}


def _build_plan(engine, anomaly: dict, diagnosis: dict) -> dict:
    """단일 anomaly에 대한 plan: 후보 생성 → anti-recurrence 필터 → 시뮬레이션 → 선택."""
    candidates = engine.auto_recovery.plan_recovery(engine.conn, diagnosis, anomaly)

    if not candidates:
        return _empty_plan(anomaly, diagnosis)

    # Anti-recurrence: same (step, anomaly, cause)가 반복되면 이미 시도된 액션 제외
    candidates, recur_reason = _apply_anti_recurrence(engine, anomaly, diagnosis, candidates)
    if recur_reason == "force_escalate":
        return {
            "anomaly": anomaly,
            "diagnosis": diagnosis,
            "ranked_actions": candidates,
            "simulations": [simulate_action(engine, a) for a in candidates[:3]],
            "selected": None,
            "rejected_reason": "anti_recurrence_force_escalate: 동일 (step,cause) 3회+, 모든 옵션 소진",
        }

    simulations = [simulate_action(engine, a) for a in candidates[:3]]
    ranked = sorted(zip(candidates, simulations), key=lambda x: -x[1]["score"])
    ranked_actions = [a for a, _ in ranked]
    best_action, best_sim = ranked[0]

    step_safety = engine._get_step_safety_level(anomaly.get("step_id", ""))
    threshold = _get_score_threshold(engine, step_safety)

    if best_sim["score"] < threshold:
        return {
            "anomaly": anomaly,
            "diagnosis": diagnosis,
            "ranked_actions": ranked_actions,
            "simulations": [s for _, s in ranked],
            "selected": None,
            "rejected_reason": (
                f"preverify_low_score: best={best_sim['score']:.5f} "
                f"< threshold={threshold:.5f} (safety={step_safety})"
            ),
        }

    return {
        "anomaly": anomaly,
        "diagnosis": diagnosis,
        "ranked_actions": ranked_actions,
        "simulations": [s for _, s in ranked],
        "selected": best_action,
        "rejected_reason": None,
    }


def _empty_plan(anomaly: dict, diagnosis: dict) -> dict:
    return {
        "anomaly": anomaly,
        "diagnosis": diagnosis,
        "ranked_actions": [],
        "simulations": [],
        "selected": None,
        "rejected_reason": None,
    }


def _apply_anti_recurrence(engine, anomaly: dict, diagnosis: dict, candidates: list) -> tuple[list, str]:
    """반복되는 incident에 대해 이미 시도된 action_type을 후보에서 demote/배제.

    반환: (수정된_candidates, reason). reason="force_escalate"이면 ESCALATE 강제.
    """
    tracker = getattr(engine, "recurrence_tracker", None)
    if not tracker:
        return candidates, ""

    diag_top = (diagnosis.get("candidates") or [{}])[0]
    # incident_signature와 동일 키 형식으로 tracker 조회 — production/replay 일관성.
    sig = incident_signature({
        "step_id": anomaly.get("step_id"),
        "anomaly_type": anomaly.get("anomaly_type"),
        "top_cause": diag_top.get("cause_type"),
    })
    record = tracker.get(sig)
    if not record or record["count"] < _RECUR_DEMOTE_AT:
        return candidates, ""

    tried = record["tried_actions"]
    untried = [c for c in candidates if c.get("action_type") not in tried]

    # N회 이상 + 시도 안 한 액션 없음 → ESCALATE 강제
    if record["count"] >= _RECUR_ESCALATE_AT and not untried:
        return candidates, "force_escalate"

    # 시도된 액션은 뒤로 보내고 untried 우선 (있으면)
    if untried:
        demoted_tried = [c for c in candidates if c.get("action_type") in tried]
        return untried + demoted_tried, "demoted"

    return candidates, ""


def simulate_action(engine, action: dict) -> dict:
    """액션을 적용하지 않고 기대 효과를 추정한다.

    Replay-based (≥2 샘플): 과거 healing_history에서 같은 (step, action, cause)
    조합의 actual_delta 평균 사용. 실측치라 휴리스틱보다 신뢰도 높음.

    Heuristic fallback: expected_delta = (new_value − old_value) × success_prob.

    Final score: expected_delta × confidence × (1 − risk_factor).
    """
    action_type = action.get("action_type", "unknown")
    cause_type = action.get("cause_type", "unknown")
    target_step = action.get("target_step", "")
    confidence = float(action.get("confidence", 0.0) or 0.0)
    risk_level = str(action.get("risk_level", "MEDIUM"))
    risk_factor = RISK_NUMERIC.get(risk_level, 0.5)

    replay_mean, replay_n = _replay_predicted_delta(engine, target_step, action_type, cause_type)
    if replay_n >= _REPLAY_MIN_SAMPLES:
        expected_delta = replay_mean
        success_prob = _estimate_success_prob(engine, action_type, cause_type, confidence)
        param_delta = _estimate_param_delta(action)
        sim_source = "replay"
    else:
        success_prob = _estimate_success_prob(engine, action_type, cause_type, confidence)
        param_delta = _estimate_param_delta(action)
        expected_delta = param_delta * success_prob
        sim_source = "heuristic"

    score = expected_delta * confidence * (1.0 - risk_factor)

    return {
        "action_type": action_type,
        "cause_type": cause_type,
        "parameter": action.get("parameter"),
        "predicted_new_value": action.get("new_value"),
        "expected_delta": round(expected_delta, 6),
        "param_delta": round(param_delta, 6),
        "success_prob": round(success_prob, 3),
        "risk_factor": risk_factor,
        "confidence": confidence,
        "score": round(score, 6),
        "hist_attempts": _hist_attempts(engine, action_type, cause_type),
        "sim_source": sim_source,
        "replay_samples": replay_n,
    }


def _replay_predicted_delta(engine, step_id: str, action_type: str, cause_type: str) -> tuple[float, int]:
    """과거 healing_history에서 같은 (step, action, cause)의 actual yield delta 평균.

    Returns: (mean_delta, sample_count). 샘플 없으면 (0.0, 0).
    """
    samples = []
    for inc in getattr(engine, "healing_history", []) or []:
        if (
            inc.get("step_id") == step_id
            and inc.get("action_type") == action_type
            and inc.get("top_cause") == cause_type
        ):
            pre = inc.get("pre_yield")
            post = inc.get("post_yield")
            if isinstance(pre, (int, float)) and isinstance(post, (int, float)):
                samples.append(float(post) - float(pre))
    if not samples:
        return 0.0, 0
    return sum(samples) / len(samples), len(samples)


def _estimate_success_prob(engine, action_type: str, cause_type: str, confidence: float) -> float:
    """과거 (action_type, cause_type) 시도/성공 카운트로 success_prob 추정.

    이력 < _COLD_START_ATTEMPTS이면 진단 confidence를 사용 (cold start).
    """
    hist = engine.auto_recovery.success_history.get(
        (action_type, cause_type), {"attempts": 0, "successes": 0},
    )
    if hist["attempts"] >= _COLD_START_ATTEMPTS:
        return hist["successes"] / hist["attempts"]
    return confidence


def _hist_attempts(engine, action_type: str, cause_type: str) -> int:
    return engine.auto_recovery.success_history.get(
        (action_type, cause_type), {"attempts": 0},
    )["attempts"]


def _estimate_param_delta(action: dict) -> float:
    """액션이 만들 파라미터 변화량 (yield_rate / oee delta).

    plan_recovery에서 이미 new_value/old_value 채워줌. 없으면 0.
    Non-numeric 액션(INCREASE_INSPECTION/MATERIAL_SWITCH/ESCALATE)은 0.
    """
    new_value = action.get("new_value")
    old_value = action.get("old_value")
    if new_value is None or old_value is None:
        return 0.0
    try:
        return float(new_value) - float(old_value)
    except (TypeError, ValueError):
        return 0.0


def _serialize_plan(plan: dict) -> dict:
    """이벤트 발행용 직렬화 (anomaly/diagnosis 전체는 빼고 요약만)."""
    selected = plan.get("selected")
    return {
        "step_id": plan["anomaly"].get("step_id"),
        "selected_action": selected.get("action_type") if selected else None,
        "selected_score": (
            plan["simulations"][0]["score"]
            if plan["simulations"] and selected else None
        ),
        "rejected_reason": plan.get("rejected_reason"),
        "candidate_count": len(plan["ranked_actions"]),
        "top_simulations": plan["simulations"][:3],
    }
