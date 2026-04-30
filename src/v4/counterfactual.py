"""Counterfactual runtime — "만약 다른 액션을 골랐다면?" 정량 시뮬.

Explainable RCA(causal.py:_explain_exclusion)가 *왜 다른 cause 아닌지* 답한다면,
본 모듈은 *왜 다른 action 아닌지* 답한다. 운영자 신뢰 + HITL 검토 보조.

backtest.py:_compute_counterfactuals 는 *과거 사례 통계* 기반 (집계).
본 모듈은 *runtime 단일 incident* 기반 — 현재 선택 vs 후보 alternative 의
expected_delta 차이를 계산해 *놓친 가치* (missed_value) 정량화.

학술 근거: CausalTrace (arXiv 2025) — counterfactual reasoning 의 시작점.

사용 패턴:
    chosen_sim = simulate_action(engine, chosen_action)  # preverify에서 이미 계산
    alt_sims = [simulate_action(engine, a) for a in alternatives]
    cf = compute_runtime_counterfactual(chosen_sim, alt_sims)
    # cf["best_alternative"] = 가장 좋았을 대안
    # cf["missed_value"] = 그 대안 vs 현 선택 expected_delta 차이
    # cf["interpretation"] = 자연어 설명
"""

from __future__ import annotations

from typing import Any


def compute_runtime_counterfactual(
    chosen_sim: dict[str, Any] | None,
    alternative_sims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Chosen action 시뮬 vs alternative 시뮬 비교.

    Args:
        chosen_sim: 시스템이 선택한 액션의 simulate_action 결과 dict
                    (action_type, expected_delta, success_prob, score 포함).
        alternative_sims: 같은 시뮬 결과 리스트 (chosen 외 후보들).

    Returns:
        {
          "chosen_action": str,                # 시스템 선택
          "chosen_expected_delta": float,
          "chosen_score": float,
          "best_alternative": str | None,      # 가장 큰 expected_delta 대안
          "best_alt_expected_delta": float,
          "best_alt_score": float,
          "missed_value": float,               # best_alt - chosen (양수면 놓친 가치)
          "score_gap": float,                  # 같은 정의로 score 비교
          "n_alternatives": int,
          "interpretation": str,               # "현 선택이 최적" 또는 "X로 골랐으면 +Y%p 더 나았을 것"
          "ranked_alternatives": list[dict],   # 모든 대안 정렬 (alt_action / delta / gap)
        }
    """
    if not chosen_sim:
        return {
            "chosen_action": None,
            "chosen_expected_delta": 0.0,
            "chosen_score": 0.0,
            "best_alternative": None,
            "best_alt_expected_delta": 0.0,
            "best_alt_score": 0.0,
            "missed_value": 0.0,
            "score_gap": 0.0,
            "n_alternatives": 0,
            "interpretation": "no_chosen_action",
            "ranked_alternatives": [],
        }

    chosen_action = chosen_sim.get("action_type", "?")
    chosen_delta = float(chosen_sim.get("expected_delta", 0.0))
    chosen_score = float(chosen_sim.get("score", 0.0))

    if not alternative_sims:
        return {
            "chosen_action": chosen_action,
            "chosen_expected_delta": round(chosen_delta, 6),
            "chosen_score": round(chosen_score, 6),
            "best_alternative": None,
            "best_alt_expected_delta": 0.0,
            "best_alt_score": 0.0,
            "missed_value": 0.0,
            "score_gap": 0.0,
            "n_alternatives": 0,
            "interpretation": "no_alternatives",
            "ranked_alternatives": [],
        }

    # 대안 정렬 — expected_delta 내림차순
    ranked = sorted(
        [
            {
                "action_type": a.get("action_type", "?"),
                "cause_type": a.get("cause_type", "?"),
                "expected_delta": round(float(a.get("expected_delta", 0.0)), 6),
                "score": round(float(a.get("score", 0.0)), 6),
                "delta_gap_vs_chosen": round(
                    float(a.get("expected_delta", 0.0)) - chosen_delta, 6
                ),
            }
            for a in alternative_sims
        ],
        key=lambda x: -x["expected_delta"],
    )

    best = ranked[0]
    missed_value = round(best["expected_delta"] - chosen_delta, 6)
    score_gap = round(best["score"] - chosen_score, 6)

    if missed_value <= 0.0:
        interpretation = (
            f"현 선택({chosen_action}) 이 시뮬상 최적 — "
            f"가장 가까운 대안({best['action_type']}) Δ={missed_value:+.4f}"
        )
    else:
        interpretation = (
            f"{best['action_type']} 을 골랐으면 expected_delta "
            f"{missed_value:+.4f} 더 컸을 것 — runtime counterfactual"
        )

    return {
        "chosen_action": chosen_action,
        "chosen_expected_delta": round(chosen_delta, 6),
        "chosen_score": round(chosen_score, 6),
        "best_alternative": best["action_type"],
        "best_alt_expected_delta": best["expected_delta"],
        "best_alt_score": best["score"],
        "missed_value": missed_value,
        "score_gap": score_gap,
        "n_alternatives": len(ranked),
        "interpretation": interpretation,
        "ranked_alternatives": ranked,
    }
