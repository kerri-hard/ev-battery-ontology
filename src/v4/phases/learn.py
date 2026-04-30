"""LEARN 페이즈 — 에이전트 학습 + Incident 영속화 + L3 그래프 강화."""
import asyncio
from datetime import datetime

from v4.recurrence import update_tracker as _update_recurrence


async def run(engine, it: int, delay: float, anomalies: list, diagnoses: list,
              recovery_results: list, verifications: list) -> dict:
    """이상-진단-복구-검증 결과를 학습 데이터로 통합.

    Returns: {"incidents_recorded": int, "auto_recovered_count": int, ...}
    """
    await engine._emit("phase", {
        "iteration": it + 1,
        "phase": "learn_healing",
        "message": "복구 결과를 학습합니다...",
    })
    await asyncio.sleep(delay)

    incidents_recorded = 0
    knowledge_updates = 0
    auto_recovered_count = 0
    l3_links_created = 0

    for anomaly, diagnosis, rr, verification in zip(
        anomalies, diagnoses, recovery_results, verifications,
    ):
        knowledge_updates += _train_agents(engine, anomaly, diagnosis, rr, verification)

        incident, auto_recovered = _record_incident(engine, it, anomaly, diagnosis, rr, verification)
        incidents_recorded += 1
        if auto_recovered:
            auto_recovered_count += 1

        _update_recurrence_tracker(engine, incident, auto_recovered)
        _persist_incident_node(engine, incident, auto_recovered)
        _link_failure_chain(engine, incident, diagnosis, anomaly)
        _link_escalation(engine, incident, rr)
        _link_step_to_incident(engine, incident, anomaly.get("step_id", "unknown"))
        _link_recovery_action(engine, incident, rr)
        _record_counterfactual_learning_if_candidate(engine, incident)
        l3_links_created += _strengthen_l3_links(engine, incident, anomaly)

    await engine._emit("learn_done_healing", {
        "iteration": it + 1,
        "incidents_recorded": incidents_recorded,
        "auto_recovered_count": auto_recovered_count,
        "knowledge_updates": knowledge_updates,
        "l3_links_created": l3_links_created,
        "l3_snapshot": engine._record_l3_snapshot(it + 1),
        "recent_incidents": engine.healing_history[-5:],
    })

    return {
        "incidents_recorded": incidents_recorded,
        "auto_recovered_count": auto_recovered_count,
        "knowledge_updates": knowledge_updates,
        "l3_links_created": l3_links_created,
    }


def _train_agents(engine, anomaly: dict, diagnosis: dict, rr: dict, verification: dict) -> int:
    """각 에이전트에게 이번 사이클 결과를 학습시킨다."""
    step_id = anomaly.get("step_id", "unknown")
    auto_recovered = rr.get("success", False) and rr.get("action_type") != "ESCALATE"
    improved = verification.get("improved", False)
    top_cause = ""
    if diagnosis.get("candidates"):
        top_cause = diagnosis["candidates"][0].get("cause_type", "")

    updates = 0
    for trainer in (
        lambda: engine.anomaly_detector.learn(anomaly, diagnosis, rr),
        lambda: engine.root_cause_analyzer.learn(step_id, anomaly.get("sensor_type", ""), top_cause),
        lambda: engine.auto_recovery.learn(
            rr.get("action_type", "unknown"), top_cause or "unknown",
            bool(auto_recovered and improved),
        ),
        lambda: engine.causal_reasoner.learn_from_recovery(
            engine.conn, step_id,
            anomaly.get("sensor_type", ""),
            anomaly.get("anomaly_type", ""),
            top_cause,
            bool(auto_recovered and improved),
            float(rr.get("recovery_time_sec", 0.5) or 0.5),
            engine.healing_counters,
        ),
    ):
        try:
            trainer()
            updates += 1
        except Exception:
            pass
    return updates


def _record_incident(engine, it: int, anomaly: dict, diagnosis: dict,
                      rr: dict, verification: dict) -> tuple[dict, bool]:
    """Incident 레코드 생성 + healing_history에 추가."""
    step_id = anomaly.get("step_id", "unknown")
    auto_recovered = rr.get("success", False) and rr.get("action_type") != "ESCALATE"

    top_cause = "unknown"
    top_confidence = 0.0
    causal_chain = ""
    top_evidence_refs = []
    rca_breakdown = None
    if diagnosis.get("candidates"):
        c = diagnosis["candidates"][0]
        top_cause = c.get("cause_type", "unknown")
        top_confidence = c.get("confidence", 0.0)
        causal_chain = c.get("causal_chain", "") or ""
        top_evidence_refs = c.get("evidence_refs", []) or []
        rca_breakdown = c.get("rca_score_breakdown")

    incident = {
        "id": f"INC-{engine.healing_counters['incident'] + 1:04d}",
        "iteration": it + 1,
        "timestamp": datetime.now().isoformat(),
        "step_id": step_id,
        "anomaly_type": anomaly.get("type", anomaly.get("anomaly_type", "unknown")),
        "severity": anomaly.get("severity", "medium"),
        "top_cause": top_cause,
        "confidence": round(top_confidence, 3),
        "causal_chain": causal_chain,
        "history_matched": diagnosis.get("failure_chain_matched", False),
        "matched_chain_id": diagnosis.get("matched_chain_id"),
        "candidates_count": len(diagnosis.get("candidates", [])),
        "causal_chains_found": diagnosis.get("causal_chains_found", 0),
        "analysis_method": diagnosis.get("analysis_method", "causal_reasoning"),
        "matched_pattern_id": diagnosis.get("matched_pattern_id"),
        "matched_pattern_type": diagnosis.get("matched_pattern_type"),
        "evidence_refs": top_evidence_refs[:6],
        "rca_score_breakdown": rca_breakdown,
        "action_type": rr.get("action_type", "none"),
        "risk_level": rr.get("risk_level"),
        "playbook_id": rr.get("playbook_id"),
        "playbook_source": rr.get("playbook_source"),
        "hitl_required": bool(rr.get("hitl_required", False)),
        "hitl_id": rr.get("hitl_id"),
        "escalation_reason": rr.get("detail") if rr.get("action_type") == "ESCALATE" else None,
        "recovery_time_sec": rr.get("recovery_time_sec"),
        "auto_recovered": auto_recovered,
        "improved": verification.get("improved", False),
        "pre_yield": verification.get("pre_yield"),
        "post_yield": verification.get("post_yield"),
    }
    engine.healing_history.append(incident)
    engine.healing_counters["incident"] += 1
    return incident, auto_recovered


def _update_recurrence_tracker(engine, incident: dict, auto_recovered: bool) -> None:
    """anti-recurrence 정책의 데이터 소스. v4.recurrence.update_tracker로 위임."""
    _update_recurrence(engine.recurrence_tracker, incident, auto_recovered)


def _record_counterfactual_learning_if_candidate(engine, incident: dict) -> None:
    """Counterfactual 결과가 학습 후보 (missed_value 임계 통과) 면 그래프에 영속.

    incident.preverify_counterfactual.is_learning_candidate=True 일 때 실행.
    learning_layer.record_counterfactual_learning 위임 (idempotent + graceful).
    실패 시 silent skip — 학습 큐 영속이 운영 흐름을 막아선 안 됨.
    """
    cf = incident.get("preverify_counterfactual") if isinstance(incident, dict) else None
    if not cf or not cf.get("is_learning_candidate"):
        return
    try:
        from v4.learning_layer import record_counterfactual_learning
        record_counterfactual_learning(
            engine.conn,
            str(incident.get("id", "")),
            str(incident.get("step_id", "")),
            cf,
        )
    except Exception:
        pass


def _persist_incident_node(engine, incident: dict, auto_recovered: bool) -> None:
    """Incident 노드를 그래프 DB에 저장."""
    try:
        engine.conn.execute(
            "CREATE (inc:Incident {"
            "id: $id, step_id: $step_id, alarm_id: '', "
            "root_cause: $cause, recovery_action: $action, "
            "resolved: $resolved, auto_recovered: $recovered, timestamp: $ts"
            "})",
            {
                "id": incident["id"],
                "step_id": incident["step_id"],
                "cause": incident["top_cause"],
                "action": incident["action_type"],
                "resolved": auto_recovered,
                "recovered": auto_recovered,
                "ts": incident["timestamp"],
            },
        )
    except Exception:
        pass


def _link_failure_chain(engine, incident: dict, diagnosis: dict, anomaly: dict) -> None:
    """Incident → FailureChain 매칭 링크."""
    matched_chain_id = diagnosis.get("matched_chain_id")
    if not matched_chain_id:
        matched_chain_id = engine.causal_reasoner.chain_cache.get(
            (incident["step_id"], anomaly.get("sensor_type", "")),
        )
    if not matched_chain_id:
        return

    try:
        engine.conn.execute(
            "MATCH (inc:Incident), (fc:FailureChain) "
            "WHERE inc.id = $inc_id AND fc.id = $fc_id "
            "CREATE (inc)-[:MATCHED_BY]->(fc)",
            {"inc_id": incident["id"], "fc_id": matched_chain_id},
        )
    except Exception:
        pass


def _link_escalation(engine, incident: dict, rr: dict) -> None:
    if rr.get("action_type") != "ESCALATE":
        return
    try:
        engine.conn.execute(
            "MATCH (inc:Incident), (p:EscalationPolicy) "
            "WHERE inc.id=$inc_id AND p.id='EP-DEFAULT' "
            "CREATE (inc)-[:ESCALATES_TO]->(p)",
            {"inc_id": incident["id"]},
        )
    except Exception:
        pass


def _link_step_to_incident(engine, incident: dict, step_id: str) -> None:
    try:
        engine.conn.execute(
            "MATCH (ps:ProcessStep), (inc:Incident) "
            "WHERE ps.id = $step_id AND inc.id = $inc_id "
            "CREATE (ps)-[:HAS_INCIDENT]->(inc)",
            {"step_id": step_id, "inc_id": incident["id"]},
        )
    except Exception:
        pass


def _link_recovery_action(engine, incident: dict, rr: dict) -> None:
    recovery_id = rr.get("recovery_id")
    if not recovery_id:
        return
    try:
        engine.conn.execute(
            "MATCH (inc:Incident), (ra:RecoveryAction) "
            "WHERE inc.id = $inc_id AND ra.id = $ra_id "
            "CREATE (inc)-[:RESOLVED_BY]->(ra)",
            {"inc_id": incident["id"], "ra_id": recovery_id},
        )
    except Exception:
        pass
    # action_type 기반 ComplianceItem 자동 매핑 (UN R150 / IATF 16949 / EU Battery)
    action_type = incident.get("action_type") or (rr.get("action") or {}).get("action_type")
    if action_type:
        try:
            from v4.regulation import link_action_to_compliance
            link_action_to_compliance(engine.conn, str(recovery_id), str(action_type))
        except Exception:
            pass


def _strengthen_l3_links(engine, incident: dict, anomaly: dict) -> int:
    """ProcessStep ↔ CausalRule ↔ AnomalyPattern 그래프 강화."""
    top_cause = incident.get("top_cause")
    if not top_cause:
        return 0

    links = 0
    try:
        engine.conn.execute(
            "MATCH (ps:ProcessStep), (cr:CausalRule) "
            "WHERE ps.id = $step_id AND (cr.cause_type = $cause OR cr.effect_type = $cause) "
            "AND NOT (ps)-[:HAS_CAUSE]->(cr) "
            "CREATE (ps)-[:HAS_CAUSE]->(cr)",
            {"step_id": incident["step_id"], "cause": top_cause},
        )
        links += 1
    except Exception:
        pass

    anomaly_type = anomaly.get("anomaly_type", "threshold_breach")
    pattern_type = {
        "trend_shift": "drift",
        "statistical_outlier": "spike",
        "threshold_breach": "level_shift",
    }.get(anomaly_type, "spike")

    try:
        engine.conn.execute(
            "MATCH (cr:CausalRule), (ap:AnomalyPattern) "
            "WHERE (cr.cause_type = $cause OR cr.effect_type = $cause) "
            "AND ap.pattern_type = $ptype "
            "AND NOT (cr)-[:HAS_PATTERN]->(ap) "
            "CREATE (cr)-[:HAS_PATTERN]->(ap)",
            {"cause": top_cause, "ptype": pattern_type},
        )
        links += 1
    except Exception:
        pass

    return links
