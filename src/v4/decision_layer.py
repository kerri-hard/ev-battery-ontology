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
                "min_confidence:0.40, high_risk_threshold:0.75, "
                "medium_requires_history:false, active:true, version:'v2', updated_at:$ts"
                "})",
                {"ts": ts},
            )
    except Exception:
        pass

    playbooks = [
        # 기존 플레이북
        ("PB-001", "equipment_mtbf", "ADJUST_PARAMETER", "LOW", 1),
        ("PB-002", "equipment_mtbf", "EQUIPMENT_RESET", "MEDIUM", 2),
        ("PB-003", "material_anomaly", "MATERIAL_SWITCH", "HIGH", 3),
        ("PB-005", "defect_mode_match", "INCREASE_INSPECTION", "LOW", 2),
        ("PB-006", "upstream_degradation", "ADJUST_PARAMETER", "LOW", 2),
        ("PB-004", "unknown", "ESCALATE", "CRITICAL", 99),
        # 인과 체인 원인 유형 (L3 CausalRule에서 도출)
        ("PB-010", "precision_loss", "EQUIPMENT_RESET", "MEDIUM", 2),
        ("PB-011", "coating_defect", "ADJUST_PARAMETER", "LOW", 1),
        ("PB-012", "contact_failure", "EQUIPMENT_RESET", "MEDIUM", 2),
        ("PB-013", "yield_drop", "ADJUST_PARAMETER", "LOW", 1),
        ("PB-014", "temperature_rise", "ADJUST_PARAMETER", "LOW", 1),
        ("PB-015", "pressure_drop", "EQUIPMENT_RESET", "MEDIUM", 2),
        ("PB-016", "vibration_increase", "EQUIPMENT_RESET", "MEDIUM", 2),
        ("PB-017", "welding_defect", "INCREASE_INSPECTION", "LOW", 1),
        ("PB-018", "joint_weakness", "INCREASE_INSPECTION", "LOW", 1),
        ("PB-019", "bearing_wear", "EQUIPMENT_RESET", "MEDIUM", 2),
        ("PB-020", "cooling_failure", "EQUIPMENT_RESET", "MEDIUM", 2),
        ("PB-021", "current_anomaly", "ADJUST_PARAMETER", "LOW", 1),
        ("PB-022", "process_variation", "ADJUST_PARAMETER", "LOW", 1),
        ("PB-023", "property_deviation", "INCREASE_INSPECTION", "LOW", 1),
        ("PB-024", "equipment_wear", "EQUIPMENT_RESET", "MEDIUM", 2),
        ("PB-025", "material_lot_change", "INCREASE_INSPECTION", "LOW", 1),
        ("PB-026", "no_inspection", "INCREASE_INSPECTION", "LOW", 1),
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

    goals = [
        ("OG-001", "Recovery Quality", "auto_recovery_rate", 0.85, 1.0),
        ("OG-002", "Energy Efficiency", "energy_kwh_per_batch", 0.5, 0.8),
        ("OG-003", "Line Yield", "line_yield", 0.95, 1.0),
        ("OG-004", "HITL Reduction", "hitl_escalation_rate", 0.1, 0.6),
    ]
    for gid, name, metric, target, weight in goals:
        try:
            r = conn.execute("MATCH (g:OptimizationGoal) WHERE g.id=$id RETURN count(g)", {"id": gid})
            exists = r.get_next()[0] if r.has_next() else 0
            if int(exists) == 0:
                conn.execute(
                    "CREATE (g:OptimizationGoal {id:$id, name:$name, target_metric:$metric, "
                    "target_value:$target, weight:$weight, active:true})",
                    {"id": gid, "name": name, "metric": metric, "target": target, "weight": weight},
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
                "min_confidence": float(row[1]) if row[1] is not None else 0.40,
                "high_risk_threshold": float(row[2]) if row[2] is not None else 0.75,
                "medium_requires_history": bool(row[3]) if row[3] is not None else False,
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

