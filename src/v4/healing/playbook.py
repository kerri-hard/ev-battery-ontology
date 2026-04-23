"""복구 플레이북 상수 + HITL 게이트 정책.

원인 유형(`cause_type`)별 우선 순위 액션 시퀀스를 선언한다.
실제 액션 디스패치는 `recovery.AutoRecoveryAgent.execute_recovery()`가 수행한다.
"""

RECOVERY_PLAYBOOK = {
    "equipment_mtbf": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.003, "risk": "LOW"},
    ],
    "defect_mode_match": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.005, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    "material_anomaly": [
        {"action": "MATERIAL_SWITCH", "param": None, "adjustment": None, "risk": "HIGH"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    "upstream_degradation": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
    ],
    "no_inspection": [
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    # 인과 체인에서 도출되는 원인 유형들
    "precision_loss": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.003, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
        {"action": "ESCALATE", "param": None, "adjustment": None, "risk": "CRITICAL"},
    ],
    "coating_defect": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.004, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.015, "risk": "MEDIUM"},
        {"action": "ESCALATE", "param": None, "adjustment": None, "risk": "CRITICAL"},
    ],
    "contact_failure": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.005, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
        {"action": "ESCALATE", "param": None, "adjustment": None, "risk": "CRITICAL"},
    ],
    "yield_drop": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.003, "risk": "LOW"},
    ],
    "temperature_rise": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.01, "risk": "LOW"},
    ],
    "pressure_drop": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.003, "risk": "LOW"},
    ],
    "vibration_increase": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.015, "risk": "MEDIUM"},
    ],
    "welding_defect": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.005, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.015, "risk": "MEDIUM"},
        {"action": "ESCALATE", "param": None, "adjustment": None, "risk": "CRITICAL"},
    ],
    "joint_weakness": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.004, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
        {"action": "MATERIAL_SWITCH", "param": None, "adjustment": None, "risk": "HIGH"},
        {"action": "ESCALATE", "param": None, "adjustment": None, "risk": "CRITICAL"},
    ],
    "bearing_wear": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.025, "risk": "MEDIUM"},
    ],
    "cooling_failure": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
    ],
    "current_anomaly": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.003, "risk": "LOW"},
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.015, "risk": "MEDIUM"},
    ],
    "process_variation": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
    ],
    "property_deviation": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    "equipment_wear": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
    ],
    "material_lot_change": [
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
    ],
    "unknown": [
        {"action": "ESCALATE", "param": None, "adjustment": None, "risk": "CRITICAL"},
    ],
}

ACTION_DEFAULTS = {
    "ADJUST_PARAMETER": {"param": "yield_rate", "adjustment": 0.003},
    "EQUIPMENT_RESET": {"param": "oee", "adjustment": 0.02},
    "MATERIAL_SWITCH": {"param": None, "adjustment": None},
    "INCREASE_INSPECTION": {"param": None, "adjustment": None},
    "ESCALATE": {"param": None, "adjustment": None},
}

RISK_NUMERIC = {"LOW": 0.1, "MEDIUM": 0.3, "HIGH": 0.6, "CRITICAL": 0.9}


def requires_hitl(
    action: dict,
    diagnosis: dict,
    min_confidence: float = 0.62,
    high_risk_threshold: float = 0.6,
    medium_requires_history: bool = True,
) -> tuple[bool, str]:
    """고위험/저신뢰 복구 액션에 대해 HITL 게이트를 판단한다."""
    risk_level = str(action.get("risk_level", "MEDIUM"))
    risk_num = RISK_NUMERIC.get(risk_level, 0.5)
    confidence = float(action.get("confidence", 0.0) or 0.0)
    history_matched = bool(diagnosis.get("failure_chain_matched", False))

    if confidence < min_confidence:
        return True, f"low_confidence<{min_confidence:.2f}"
    if risk_num >= high_risk_threshold:
        return True, f"high_risk={risk_level}"
    if medium_requires_history and risk_num >= 0.3 and not history_matched:
        return True, "no_history_match_for_medium_plus_risk"
    return False, ""
