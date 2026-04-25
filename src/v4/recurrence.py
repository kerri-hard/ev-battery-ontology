"""Anti-recurrence 정책의 단일 진실 소스 — VISION §9.5 (실패에서 성장).

learn 페이즈와 backtest replay에서 동일한 시그니처·tracker 갱신 규칙을 사용하도록
공유 헬퍼를 제공한다. preverify 페이즈는 demote/escalate 임계값을 여기서 import.

tracker 형식: dict[tuple, dict]
  키: (step_id, anomaly_type, top_cause) — incident의 시그니처
  값: {
    "count": int,                # 같은 시그니처 발생 횟수
    "tried_actions": set[str],   # 시도된 action_type ("ESCALATE"/"none"/"error" 제외)
    "last_success": bool,        # 마지막 시도의 auto_recovery 성공 여부
  }
"""
from __future__ import annotations


# Anti-recurrence 정책 임계값 (preverify._apply_anti_recurrence가 적용)
RECUR_DEMOTE_AT = 2     # 같은 시그니처가 N회 이상 발생 → 시도된 액션 demote
RECUR_ESCALATE_AT = 3   # N회 이상 + 모든 후보 소진 → ESCALATE 강제

# 시도 카운트에서 제외하는 sentinel action types
_NON_TRIED_ACTIONS = ("ESCALATE", "none", "error")


def incident_signature(incident: dict) -> tuple[str, str, str]:
    """Incident dict에서 anti-recurrence 시그니처 튜플을 추출한다.

    None/누락 필드는 'unknown'으로 정규화하여 tracker key 충돌을 막는다.
    """
    return (
        incident.get("step_id", "unknown") or "unknown",
        incident.get("anomaly_type", "unknown") or "unknown",
        incident.get("top_cause", "unknown") or "unknown",
    )


def update_tracker(tracker: dict, incident: dict, auto_recovered: bool) -> None:
    """In-place로 tracker에 incident 결과를 누적한다.

    learn.py(production)와 backtest.py(replay) 둘 다 이 함수를 호출 → 정책 일치 보장.
    """
    sig = incident_signature(incident)
    record = tracker.setdefault(
        sig, {"count": 0, "tried_actions": set(), "last_success": False},
    )
    record["count"] += 1
    action_type = incident.get("action_type")
    if action_type and action_type not in _NON_TRIED_ACTIONS:
        record["tried_actions"].add(action_type)
    record["last_success"] = bool(auto_recovered)
