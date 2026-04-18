"""프롬프트 빌더 + 한국어 라벨 매핑."""
import json


SYSTEM_PROMPT = """\
You are a manufacturing quality engineer AI analyzing an EV battery pack production line incident.
Given the multi-agent diagnostic data, provide:
1. A clear 2-3 sentence summary of what happened (Korean)
2. Root cause explanation tracing the causal chain (Korean)
3. Cross-process insights if correlations exist (Korean)
4. 3 specific recommended actions with urgency levels (Korean)
5. Risk assessment with current status and future outlook (Korean)

Respond ONLY with valid JSON matching this structure:
{
  "summary": "...",
  "root_cause_explanation": "...",
  "cross_process_insight": "...",
  "recommended_actions": ["1. ...", "2. ...", "3. ..."],
  "risk_assessment": "..."
}
All text values must be in Korean. Be specific, referencing actual values from the data."""


SENSOR_TYPE_KO = {
    "torque_force": "토크 센서",
    "temperature": "온도 센서",
    "vibration": "진동 센서",
    "pressure": "압력 센서",
    "humidity": "습도 센서",
    "current": "전류 센서",
    "voltage": "전압 센서",
    "thickness": "두께 센서",
    "alignment": "정렬 센서",
    "tension": "장력 센서",
    "flow_rate": "유량 센서",
    "vacuum_level": "진공도 센서",
}

CAUSE_TYPE_KO = {
    "equipment_wear": "장비 마모",
    "equipment_mtbf": "설비 MTBF 초과",
    "cooling_failure": "냉각 시스템 이상",
    "material_anomaly": "자재 이상",
    "material_lot_change": "자재 LOT 변경",
    "defect_mode_match": "결함 모드 매칭",
    "upstream_degradation": "상류 공정 열화",
    "sensor_drift": "센서 드리프트",
    "vibration_anomaly": "진동 이상",
    "pressure_drop": "압력 부족",
    "temperature_rise": "온도 상승",
    "unknown": "원인 미상",
}


def sensor_type_korean(sensor_type: str) -> str:
    return SENSOR_TYPE_KO.get(sensor_type, f"{sensor_type} 센서")


def cause_type_korean(cause_type: str) -> str:
    return CAUSE_TYPE_KO.get(cause_type, cause_type)


def build_user_message(incident_data: dict) -> str:
    """LLM에게 전달할 구조화된 incident 설명 (Markdown)."""
    parts = []
    step_id = incident_data.get("step_id", "UNKNOWN")
    step_name = incident_data.get("step_name", "")
    parts.append(f"## 장애 발생 공정: {step_id} ({step_name})")

    _append_anomaly(parts, incident_data.get("anomaly", {}))
    _append_diagnosis(parts, incident_data.get("diagnosis", {}))
    _append_cross(parts, incident_data.get("cross_investigation", {}))
    _append_recovery(parts, incident_data.get("recovery", {}))
    _append_scenario(parts, incident_data.get("scenario", {}))

    return "\n".join(parts)


def _append_anomaly(parts: list, anomaly: dict) -> None:
    if not anomaly:
        return
    parts.append("\n### 이상 감지")
    parts.append(f"- 센서 유형: {anomaly.get('sensor_type', 'N/A')}")
    parts.append(f"- 측정값: {anomaly.get('value', 'N/A')}")
    parts.append(f"- 정상 범위: {anomaly.get('normal_range', 'N/A')}")
    parts.append(f"- 이상 유형: {anomaly.get('anomaly_type', 'N/A')}")
    parts.append(f"- 심각도: {anomaly.get('severity', 'N/A')}")


def _append_diagnosis(parts: list, diagnosis: dict) -> None:
    if not diagnosis:
        return
    parts.append("\n### 원인 진단")
    parts.append(f"- 최우선 원인: {diagnosis.get('top_cause', 'N/A')}")
    parts.append(f"- 신뢰도: {diagnosis.get('confidence', 'N/A')}")
    candidates = diagnosis.get("candidates", [])
    if candidates:
        parts.append(f"- 후보 원인: {json.dumps(candidates, ensure_ascii=False)}")
    parts.append(f"- 인과 체인: {diagnosis.get('causal_chain', 'N/A')}")
    parts.append(f"- 과거 이력 매칭: {diagnosis.get('history_matched', False)}")
    if diagnosis.get("matched_chain_id"):
        parts.append(f"- 매칭 체인 ID: {diagnosis['matched_chain_id']}")


def _append_cross(parts: list, cross: dict) -> None:
    if not cross:
        return
    parts.append("\n### 공정 간 조사")
    correlated = cross.get("correlated_steps", [])
    for cs in correlated[:5]:
        parts.append(
            f"- {cs.get('step_id', '?')}: "
            f"상관계수={cs.get('correlation', 0):.2f}, "
            f"관계={cs.get('relationship', 'N/A')}"
        )
    hidden = cross.get("hidden_dependencies", 0)
    if hidden:
        parts.append(f"- 숨겨진 의존성: {hidden}건")


def _append_recovery(parts: list, recovery: dict) -> None:
    if not recovery:
        return
    parts.append("\n### 복구 결과")
    parts.append(f"- 복구 유형: {recovery.get('action_type', 'N/A')}")
    parts.append(f"- 성공 여부: {recovery.get('success', 'N/A')}")
    if recovery.get("pre_yield") is not None:
        parts.append(f"- 복구 전 수율: {recovery['pre_yield']}")
    if recovery.get("post_yield") is not None:
        parts.append(f"- 복구 후 수율: {recovery['post_yield']}")


def _append_scenario(parts: list, scenario: dict) -> None:
    if not scenario:
        return
    parts.append("\n### 시나리오")
    parts.append(f"- 시나리오 이름: {scenario.get('name', 'N/A')}")
    parts.append(f"- 카테고리: {scenario.get('category', 'N/A')}")
