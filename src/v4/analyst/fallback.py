"""OpenAI API 미사용 시 템플릿 기반 incident 요약."""
from v4.analyst.prompts import sensor_type_korean, cause_type_korean
from v4.analyst.scoring import build_confidence_breakdown, determine_agents_involved


def generate_fallback(incident_data: dict) -> dict:
    """진단 데이터에서 직접 추출한 값으로 사람이 읽을 요약을 만든다."""
    step_id = incident_data.get("step_id", "UNKNOWN")
    step_name = incident_data.get("step_name", "알 수 없는 공정")
    anomaly = incident_data.get("anomaly", {})
    diagnosis = incident_data.get("diagnosis", {})
    cross = incident_data.get("cross_investigation", {})
    recovery = incident_data.get("recovery", {})

    correlated_steps = cross.get("correlated_steps", [])

    return {
        "summary": _build_summary(step_id, step_name, anomaly),
        "root_cause_explanation": _build_root_cause(diagnosis),
        "cross_process_insight": _build_cross_insight(correlated_steps),
        "recommended_actions": _build_actions(
            diagnosis.get("top_cause", "unknown"),
            recovery.get("action_type", "UNKNOWN"),
            correlated_steps,
            anomaly.get("severity", "UNKNOWN"),
        ),
        "risk_assessment": _build_risk(recovery),
        "confidence_breakdown": build_confidence_breakdown(anomaly, diagnosis, cross, recovery),
        "agents_involved": determine_agents_involved(incident_data),
        "model": "fallback_template",
        "tokens_used": 0,
    }


def _build_summary(step_id: str, step_name: str, anomaly: dict) -> str:
    sensor_type = anomaly.get("sensor_type", "sensor")
    value = anomaly.get("value", "N/A")
    severity = anomaly.get("severity", "UNKNOWN")
    anomaly_type = anomaly.get("anomaly_type", "unknown")
    normal_range = anomaly.get("normal_range", [None, None])

    if normal_range and len(normal_range) == 2 and normal_range[0] is not None:
        range_str = f"정상 범위({normal_range[0]}-{normal_range[1]})"
    else:
        range_str = "정상 범위"

    return (
        f"{step_id}({step_name})에서 {sensor_type_korean(sensor_type)}가 "
        f"{range_str}를 초과한 {value}을(를) 기록했습니다. "
        f"이상 유형: {anomaly_type}, 심각도: {severity}."
    )


def _build_root_cause(diagnosis: dict) -> str:
    top_cause = diagnosis.get("top_cause", "unknown")
    confidence = diagnosis.get("confidence", 0.0)
    causal_chain = diagnosis.get("causal_chain", "원인 체인 미확인")
    history_matched = diagnosis.get("history_matched", False)

    history_str = "과거 이력 매칭 확인" if history_matched else "과거 이력 매칭 없음"
    return (
        f"인과관계 분석에 따르면, {cause_type_korean(top_cause)}이(가) 근본 원인으로 추정됩니다 "
        f"(신뢰도 {int(confidence * 100)}%, {history_str}). "
        f"인과 체인: {causal_chain}."
    )


def _build_cross_insight(correlated_steps: list) -> str:
    if not correlated_steps:
        return "유의미한 공정 간 상관관계가 발견되지 않았습니다."
    top = correlated_steps[0]
    corr_step = top.get("step_id", "?")
    corr_val = top.get("correlation", 0)
    corr_rel = top.get("relationship", "관련 공정")
    return (
        f"{corr_rel} {corr_step}과(와) {corr_val:.2f}의 상관관계가 발견되었습니다. "
        f"해당 공정의 연관 센서를 함께 점검할 것을 권장합니다."
    )


def _build_actions(top_cause: str, action_type: str, correlated_steps: list, severity: str) -> list[str]:
    cause_actions = {
        "equipment_wear": "크림핑 프레스 실린더 교체 또는 재보정",
        "equipment_mtbf": "설비 예방정비 일정 앞당기기 및 상태 점검",
        "cooling_failure": "냉각 시스템 점검 및 냉매 보충",
        "material_anomaly": "자재 LOT 변경 이력 및 입고 검사 결과 점검",
        "material_lot_change": "신규 자재 LOT 품질 검증 및 공정 파라미터 재조정",
        "defect_mode_match": "결함 모드에 대응하는 품질 검사 강화",
        "upstream_degradation": "상류 공정 설비 점검 및 파라미터 재조정",
        "sensor_drift": "센서 캘리브레이션 실시",
        "vibration_anomaly": "진동 발생 장비 베어링 및 축 정렬 점검",
    }
    primary = cause_actions.get(top_cause, f"'{top_cause}' 원인에 대한 playbook 실행")
    urgency = "즉시" if severity in ("HIGH", "CRITICAL") else "24시간 내"
    actions = [f"1. {primary} ({urgency})"]

    if correlated_steps:
        top_corr = correlated_steps[0]
        corr_step = top_corr.get("step_id", "관련 공정")
        corr_rel = top_corr.get("relationship", "관련 공정")
        actions.append(f"2. {corr_rel} {corr_step} 설비 및 센서 점검 (24시간 내)")
    else:
        actions.append("2. 인접 공정 센서 추이 모니터링 강화 (24시간 내)")

    actions.append("3. 다음 5개 배치에 대한 품질 전수검사 실시")
    return actions


def _build_risk(recovery: dict) -> str:
    success = recovery.get("success", False)
    post_yield = recovery.get("post_yield")
    if success and post_yield is not None:
        level = "LOW" if post_yield >= 0.995 else "MEDIUM"
        return (
            f"{level} — 현재 자동 복구로 수율이 {post_yield * 100:.1f}%로 복귀했으나, "
            "근본 원인 미해결 시 재발 가능성 높음"
        )
    return f"HIGH — 복구 {'실패' if not success else '미확인'}, 즉각적인 조치가 필요합니다"
