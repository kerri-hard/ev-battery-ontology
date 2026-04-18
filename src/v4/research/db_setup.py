"""연구 루프용 Kuzu DB 부트스트랩 — L1 스키마 생성 + graph_data.json 적재."""
import json
import os
import shutil

import kuzu

from v4.sensor_simulator import extend_schema_l2
from v4.causal import extend_schema_l3, seed_causal_knowledge
from v4.correlation import extend_schema_correlation


_NODE_DDL = (
    "CREATE NODE TABLE ProcessArea (id STRING, name STRING, color STRING, "
    "cycle_time INT64, step_count INT64, takt_time DOUBLE DEFAULT 0.0, PRIMARY KEY(id))",
    "CREATE NODE TABLE ProcessStep (id STRING, name STRING, area_id STRING, "
    "cycle_time INT64, yield_rate DOUBLE, automation STRING, equipment STRING, "
    "equip_cost INT64, operators INT64, safety_level STRING, oee DOUBLE DEFAULT 0.85, "
    "sigma_level DOUBLE DEFAULT 3.0, PRIMARY KEY(id))",
    "CREATE NODE TABLE Equipment (id STRING, name STRING, cost INT64, "
    "mtbf_hours DOUBLE DEFAULT 2000.0, mttr_hours DOUBLE DEFAULT 4.0, PRIMARY KEY(id))",
    "CREATE NODE TABLE Material (id STRING, name STRING, category STRING, cost DOUBLE, "
    "supplier STRING, lead_time_days INT64 DEFAULT 7, PRIMARY KEY(id))",
    "CREATE NODE TABLE QualitySpec (id STRING, name STRING, type STRING, unit STRING, "
    "min_val DOUBLE, max_val DOUBLE, PRIMARY KEY(id))",
    "CREATE NODE TABLE DefectMode (id STRING, name STRING, category STRING, severity INT64, "
    "occurrence INT64, detection INT64, rpn INT64, PRIMARY KEY(id))",
    "CREATE NODE TABLE AutomationPlan (id STRING, name STRING, from_level STRING, "
    "to_level STRING, investment INT64, expected_yield_gain DOUBLE, "
    "expected_cycle_reduction INT64, PRIMARY KEY(id))",
    "CREATE NODE TABLE MaintenancePlan (id STRING, name STRING, strategy STRING, "
    "interval_hours INT64, cost_per_event INT64, PRIMARY KEY(id))",
)

_REL_DDL = (
    "CREATE REL TABLE NEXT_STEP (FROM ProcessStep TO ProcessStep)",
    "CREATE REL TABLE FEEDS_INTO (FROM ProcessStep TO ProcessStep)",
    "CREATE REL TABLE PARALLEL_WITH (FROM ProcessStep TO ProcessStep)",
    "CREATE REL TABLE TRIGGERS_REWORK (FROM ProcessStep TO ProcessStep)",
    "CREATE REL TABLE BELONGS_TO (FROM ProcessStep TO ProcessArea)",
    "CREATE REL TABLE USES_EQUIPMENT (FROM ProcessStep TO Equipment)",
    "CREATE REL TABLE CONSUMES (FROM ProcessStep TO Material, qty DOUBLE)",
    "CREATE REL TABLE REQUIRES_SPEC (FROM ProcessStep TO QualitySpec)",
    "CREATE REL TABLE HAS_DEFECT (FROM ProcessStep TO DefectMode)",
    "CREATE REL TABLE PREVENTS (FROM QualitySpec TO DefectMode)",
    "CREATE REL TABLE PLANNED_UPGRADE (FROM ProcessStep TO AutomationPlan)",
    "CREATE REL TABLE HAS_MAINTENANCE (FROM Equipment TO MaintenancePlan)",
    "CREATE REL TABLE DEPENDS_ON (FROM ProcessStep TO ProcessStep, dependency_type STRING)",
    "CREATE REL TABLE INSPECTS (FROM ProcessStep TO ProcessStep)",
)


def setup_db(db_path: str, data_path: str):
    """기존 DB를 정리하고 L1 + L2 + L3 + 상관 스키마로 재생성한다."""
    _purge_db(db_path)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    for ddl in _NODE_DDL + _REL_DDL:
        conn.execute(ddl)

    with open(data_path) as f:
        raw = json.load(f)

    _seed_areas(conn, raw["areas"])
    _seed_steps(conn, raw["steps"])
    equip_map = _seed_equipment(conn, raw["steps"])
    _seed_materials(conn, raw["materials"])
    _seed_quality(conn, raw["quality"])
    _seed_edges(conn, raw["edges"])
    _seed_step_relations(conn, raw["steps"], equip_map)
    _seed_consumes(conn, raw["materials"])
    _seed_quality_links(conn, raw["quality"])

    extend_schema_l2(conn)
    extend_schema_l3(conn)
    seed_causal_knowledge(conn, {})
    extend_schema_correlation(conn)

    return db, conn


# ── Internal seeding helpers ──────────────────────────


def _purge_db(db_path: str) -> None:
    for p in (db_path, db_path + ".wal", db_path + ".lock"):
        if not os.path.exists(p):
            continue
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)


def _seed_areas(conn, areas: list) -> None:
    for a in areas:
        conn.execute(
            "CREATE (pa:ProcessArea {id:$id,name:$name,color:$color,"
            "cycle_time:$ct,step_count:$sc,takt_time:$tt})",
            {
                "id": a["id"], "name": a["name"], "color": a["color"],
                "ct": a["cycle"], "sc": a["steps"],
                "tt": round(a["cycle"] / a["steps"], 2),
            },
        )


def _seed_steps(conn, steps: list) -> None:
    for s in steps:
        sigma = 3.0 + (s["yield_rate"] - 0.98) * 100
        conn.execute(
            "CREATE (ps:ProcessStep {id:$id,name:$name,area_id:$area,cycle_time:$ct,"
            "yield_rate:$yr,automation:$auto,equipment:$eq,equip_cost:$ec,"
            "operators:$op,safety_level:$sl,oee:$oee,sigma_level:$sig})",
            {
                "id": s["id"], "name": s["name"], "area": s["area"],
                "ct": s["cycle"], "yr": s["yield_rate"], "auto": s["auto"],
                "eq": s["equipment"], "ec": s["equip_cost"], "op": s["operators"],
                "sl": s["safety"],
                "oee": round(0.75 + s["yield_rate"] * 0.1, 3),
                "sig": round(sigma, 2),
            },
        )


def _seed_equipment(conn, steps: list) -> dict:
    equip_map = {}
    for i, s in enumerate(steps):
        eid = f"EQ-{i + 1:03d}"
        if s["equipment"] in equip_map:
            continue
        equip_map[s["equipment"]] = eid
        conn.execute(
            "CREATE (e:Equipment {id:$id,name:$name,cost:$cost,"
            "mtbf_hours:$mtbf,mttr_hours:$mttr})",
            {
                "id": eid, "name": s["equipment"], "cost": s["equip_cost"],
                "mtbf": round(1500 + s["equip_cost"] / 100),
                "mttr": round(4 + s["equip_cost"] / 200000, 1),
            },
        )
    return equip_map


def _seed_materials(conn, materials: list) -> None:
    seen = set()
    for m in materials:
        if m["mat_id"] in seen:
            continue
        seen.add(m["mat_id"])
        conn.execute(
            "CREATE (m:Material {id:$id,name:$name,category:$cat,cost:$cost,"
            "supplier:$sup,lead_time_days:7})",
            {
                "id": m["mat_id"], "name": m["mat_name"], "cat": m["category"],
                "cost": m["cost"], "sup": m["supplier"],
            },
        )


def _seed_quality(conn, quality: list) -> None:
    seen = set()
    for q in quality:
        if q["spec_id"] in seen:
            continue
        seen.add(q["spec_id"])
        conn.execute(
            "CREATE (q:QualitySpec {id:$id,name:$name,type:$type,unit:$unit,"
            "min_val:$mn,max_val:$mx})",
            {
                "id": q["spec_id"], "name": q["spec_name"], "type": q["type"],
                "unit": q["unit"], "mn": q["min"], "mx": q["max"],
            },
        )


def _seed_edges(conn, edges: list) -> None:
    for e in edges:
        conn.execute(
            f"MATCH (a:ProcessStep),(b:ProcessStep) WHERE a.id=$s AND b.id=$t "
            f"CREATE (a)-[:{e['type']}]->(b)",
            {"s": e["source"], "t": e["target"]},
        )


def _seed_step_relations(conn, steps: list, equip_map: dict) -> None:
    for s in steps:
        conn.execute(
            "MATCH (ps:ProcessStep),(pa:ProcessArea) WHERE ps.id=$sid AND pa.id=$aid "
            "CREATE (ps)-[:BELONGS_TO]->(pa)",
            {"sid": s["id"], "aid": s["area"]},
        )
        conn.execute(
            "MATCH (ps:ProcessStep),(eq:Equipment) WHERE ps.id=$sid AND eq.id=$eid "
            "CREATE (ps)-[:USES_EQUIPMENT]->(eq)",
            {"sid": s["id"], "eid": equip_map[s["equipment"]]},
        )


def _seed_consumes(conn, materials: list) -> None:
    for m in materials:
        conn.execute(
            "MATCH (ps:ProcessStep),(mat:Material) WHERE ps.id=$sid AND mat.id=$mid "
            "CREATE (ps)-[:CONSUMES {qty:$qty}]->(mat)",
            {"sid": m["step_id"], "mid": m["mat_id"], "qty": m["qty"]},
        )


def _seed_quality_links(conn, quality: list) -> None:
    for q in quality:
        conn.execute(
            "MATCH (ps:ProcessStep),(qs:QualitySpec) WHERE ps.id=$sid AND qs.id=$qid "
            "CREATE (ps)-[:REQUIRES_SPEC]->(qs)",
            {"sid": q["step_id"], "qid": q["spec_id"]},
        )
