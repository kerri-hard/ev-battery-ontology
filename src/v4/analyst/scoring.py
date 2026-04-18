"""Confidence breakdown + 참여 에이전트 식별 로직."""


def build_confidence_breakdown(anomaly: dict, diagnosis: dict, cross: dict, recovery: dict) -> dict:
    """각 분석 컴포넌트의 신뢰도를 LOW/MEDIUM/HIGH 등급화한다."""
    return {
        "anomaly_detection": _anomaly_confidence(anomaly),
        "root_cause": _root_cause_confidence(diagnosis),
        "cross_correlation": _cross_correlation_confidence(cross),
        "recovery_effectiveness": _recovery_effectiveness(recovery),
    }


def determine_agents_involved(incident_data: dict) -> list[str]:
    """이번 incident 분석에 기여한 에이전트 목록."""
    agents = []
    if incident_data.get("anomaly"):
        agents.append("AnomalyDetector")

    diagnosis = incident_data.get("diagnosis", {})
    if diagnosis:
        agents.append("RootCauseAnalyzer")
        if diagnosis.get("causal_chain"):
            agents.append("CausalReasoner")

    cross = incident_data.get("cross_investigation", {})
    if cross:
        if cross.get("correlated_steps"):
            agents.append("CorrelationAnalyzer")
        agents.append("CrossProcessInvestigator")

    return agents


def _anomaly_confidence(anomaly: dict) -> str:
    severity = anomaly.get("severity", "UNKNOWN")
    anomaly_type = anomaly.get("anomaly_type", "")
    if severity in ("HIGH", "CRITICAL"):
        level = "HIGH"
    elif severity == "MEDIUM":
        level = "MEDIUM"
    else:
        level = "LOW"
    return f"{level} ({anomaly_type})"


def _root_cause_confidence(diagnosis: dict) -> str:
    rc_conf = diagnosis.get("confidence", 0)
    history = diagnosis.get("history_matched", False)
    if rc_conf >= 0.8:
        level = "HIGH"
    elif rc_conf >= 0.5:
        level = "MEDIUM"
    else:
        level = "LOW"
    history_str = ", 과거 이력 매칭" if history else ""
    return f"{level} ({int(rc_conf * 100)}%{history_str})"


def _cross_correlation_confidence(cross: dict) -> str:
    correlated = cross.get("correlated_steps", [])
    if not correlated:
        return "N/A (상관 데이터 없음)"
    max_corr = max(abs(cs.get("correlation", 0)) for cs in correlated)
    if max_corr >= 0.8:
        level = "HIGH"
    elif max_corr >= 0.5:
        level = "MEDIUM"
    else:
        level = "LOW"
    return f"{level} (r={max_corr:.2f})"


def _recovery_effectiveness(recovery: dict) -> str:
    success = recovery.get("success", False)
    post_yield = recovery.get("post_yield")
    if not success:
        return "LOW (복구 실패)"
    if post_yield is None:
        return "UNKNOWN (복구 미확인)"
    if post_yield >= 0.99:
        return "HIGH (수율 복귀 확인)"
    return f"MEDIUM (수율 {post_yield * 100:.1f}%)"
