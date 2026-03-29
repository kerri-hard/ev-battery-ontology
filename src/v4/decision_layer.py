"""
L4 Decision Layer (policy/playbook/goal) for hybrid orchestration.
"""

from __future__ import annotations

from datetime import datetime


def extend_schema_l4(conn):
    node_tables = [
        ("CREATE NODE TABLE EscalationPolicy ("
         "id STRING, name STRING, min_confidence DOUBLE, "
         "high_risk_threshold DOUBLE, medium_requires_history BOOL, "
         "active BOOL DEFAULT true, version STRING, updated_at STRING, "
         "PRIMARY KEY(id))"),
        ("CREATE NODE TABLE ResponsePlaybook ("
         "id STRING, cause_type STRING, action_type STRING, risk_level STRING, "
         "priority INT64 DEFAULT 1, active BOOL DEFAULT true, PRIMARY KEY(id))"),
        ("CREATE NODE TABLE OptimizationGoal ("
         "id STRING, name STRING, target_metric STRING, target_value DOUBLE, "
         "weight DOUBLE DEFAULT 1.0, active BOOL DEFAULT true, PRIMARY KEY(id))"),
    ]
    rel_tables = [
        "CREATE REL TABLE TRIGGERS_ACTION (FROM CausalRule TO ResponsePlaybook)",
        "CREATE REL TABLE ESCALATES_TO (FROM Incident TO EscalationPolicy)",
        "CREATE REL TABLE OPTIMIZES (FROM ResponsePlaybook TO OptimizationGoal)",
    ]
    for ddl in node_tables + rel_tables:
        try:
            conn.execute(ddl)
        except Exception:
            pass


def seed_l4_policy(conn):
    ts = datetime.now().isoformat()
    try:
        r = conn.execute("MATCH (p:EscalationPolicy) WHERE p.id='EP-DEFAULT' RETURN count(p)")
        exists = r.get_next()[0] if r.has_next() else 0
        if int(exists) == 0:
            conn.execute(
                "CREATE (p:EscalationPolicy {"
                "id:'EP-DEFAULT', name:'Default HITL Policy', "
                "min_confidence:0.62, high_risk_threshold:0.6, "
                "medium_requires_history:true, active:true, version:'v1', updated_at:$ts"
                "})",
                {"ts": ts},
            )
    except Exception:
        pass

    playbooks = [
        ("PB-001", "equipment_mtbf", "ADJUST_PARAMETER", "LOW", 1),
        ("PB-002", "equipment_mtbf", "EQUIPMENT_RESET", "MEDIUM", 2),
        ("PB-003", "material_anomaly", "MATERIAL_SWITCH", "HIGH", 3),
        ("PB-005", "defect_mode_match", "INCREASE_INSPECTION", "LOW", 2),
        ("PB-006", "upstream_degradation", "ADJUST_PARAMETER", "LOW", 2),
        ("PB-004", "unknown", "ESCALATE", "CRITICAL", 99),
    ]
    for pid, cause, action, risk, pri in playbooks:
        try:
            r = conn.execute("MATCH (pb:ResponsePlaybook) WHERE pb.id=$id RETURN count(pb)", {"id": pid})
            exists = r.get_next()[0] if r.has_next() else 0
            if int(exists) == 0:
                conn.execute(
                    "CREATE (pb:ResponsePlaybook {id:$id, cause_type:$cause, action_type:$action, risk_level:$risk, priority:$pri, active:true})",
                    {"id": pid, "cause": cause, "action": action, "risk": risk, "pri": pri},
                )
        except Exception:
            pass

    # CausalRule -> ResponsePlaybook 연결 (L4 의사결정 계층 활성화)
    for pid, cause, _, _, _ in playbooks:
        try:
            conn.execute(
                "MATCH (cr:CausalRule), (pb:ResponsePlaybook) "
                "WHERE pb.id=$pid AND (cr.cause_type=$cause OR cr.effect_type=$cause) "
                "AND NOT (cr)-[:TRIGGERS_ACTION]->(pb) "
                "CREATE (cr)-[:TRIGGERS_ACTION]->(pb)",
                {"pid": pid, "cause": cause},
            )
        except Exception:
            pass

    try:
        r = conn.execute("MATCH (g:OptimizationGoal) WHERE g.id='OG-001' RETURN count(g)")
        exists = r.get_next()[0] if r.has_next() else 0
        if int(exists) == 0:
            conn.execute(
                "CREATE (g:OptimizationGoal {id:'OG-001', name:'Recovery Quality', target_metric:'auto_recovery_rate', target_value:0.85, weight:1.0, active:true})"
            )
    except Exception:
        pass


def load_active_policy(conn):
    try:
        r = conn.execute(
            "MATCH (p:EscalationPolicy) WHERE p.active=true "
            "RETURN p.id, p.min_confidence, p.high_risk_threshold, p.medium_requires_history "
            "ORDER BY p.updated_at DESC LIMIT 1"
        )
        if r.has_next():
            row = r.get_next()
            return {
                "id": row[0],
                "min_confidence": float(row[1]) if row[1] is not None else 0.62,
                "high_risk_threshold": float(row[2]) if row[2] is not None else 0.6,
                "medium_requires_history": bool(row[3]) if row[3] is not None else True,
            }
    except Exception:
        pass
    return None


def update_active_policy(conn, policy: dict):
    ts = datetime.now().isoformat()
    try:
        conn.execute(
            "MATCH (p:EscalationPolicy) WHERE p.id='EP-DEFAULT' "
            "SET p.min_confidence=$mc, p.high_risk_threshold=$hr, "
            "p.medium_requires_history=$mh, p.updated_at=$ts",
            {
                "mc": float(policy.get("min_confidence", 0.62)),
                "hr": float(policy.get("high_risk_threshold", 0.6)),
                "mh": bool(policy.get("medium_requires_history", True)),
                "ts": ts,
            },
        )
    except Exception:
        pass

