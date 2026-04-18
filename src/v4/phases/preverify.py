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


# 안전등급별 최소 selection_score (이 값 미만이면 자동 거절)
_SCORE_THRESHOLD_BY_SAFETY = {
    "A": 1e-4,    # 엄격 — 분명한 양의 기대 효과만 자동 실행
    "B": 0.0,     # 손해 안 나는 액션만
    "C": -1e-3,   # 약간의 위험 허용
}

_COLD_START_ATTEMPTS = 2  # 이력 < 이 값이면 confidence를 success_prob로 사용


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
    """단일 anomaly에 대한 plan: 후보 생성 → 시뮬레이션 → 선택."""
    candidates = engine.auto_recovery.plan_recovery(engine.conn, diagnosis, anomaly)
    simulations = [simulate_action(engine, a) for a in candidates[:3]]

    if not candidates:
        return {
            "anomaly": anomaly,
            "diagnosis": diagnosis,
            "ranked_actions": [],
            "simulations": [],
            "selected": None,
            "rejected_reason": None,  # no candidates ≠ rejected; recover handles "none"
        }

    ranked = sorted(zip(candidates, simulations), key=lambda x: -x[1]["score"])
    ranked_actions = [a for a, _ in ranked]
    best_action, best_sim = ranked[0]

    step_safety = engine._get_step_safety_level(anomaly.get("step_id", ""))
    threshold = _SCORE_THRESHOLD_BY_SAFETY.get(step_safety, 0.0)

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


def simulate_action(engine, action: dict) -> dict:
    """액션을 적용하지 않고 기대 효과를 추정한다.

    score = expected_delta × confidence × (1 − risk_factor)
    expected_delta = (new_value − old_value) × success_prob
    success_prob   = 과거 (action_type, cause_type) 성공률 (이력 부족 시 confidence)
    """
    action_type = action.get("action_type", "unknown")
    cause_type = action.get("cause_type", "unknown")
    confidence = float(action.get("confidence", 0.0) or 0.0)
    risk_level = str(action.get("risk_level", "MEDIUM"))
    risk_factor = RISK_NUMERIC.get(risk_level, 0.5)

    success_prob = _estimate_success_prob(engine, action_type, cause_type, confidence)
    param_delta = _estimate_param_delta(action)
    expected_delta = param_delta * success_prob
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
    }


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
