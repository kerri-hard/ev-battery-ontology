"""
Skills — 에이전트가 사용하는 분석/실행 도구 모음
각 스킬은 온톨로지(Kuzu)에 대한 특정 분석 또는 변경 능력을 캡슐화한다.
"""
import math
import random
from collections import defaultdict

random.seed(42)


# ─── FMEA 결함 데이터베이스 ───────────────────────────────────
DEFECT_DB = {
    "자동": [
        {"name": "센서 오보정", "cat": "계측", "sev": 6, "occ": 3, "det": 4},
        {"name": "로봇 위치 편차", "cat": "정밀도", "sev": 7, "occ": 2, "det": 3},
        {"name": "PLC 통신 오류", "cat": "제어", "sev": 5, "occ": 2, "det": 2},
    ],
    "반자동": [
        {"name": "작업자 실수", "cat": "인적오류", "sev": 7, "occ": 5, "det": 5},
        {"name": "지그 마모", "cat": "마모", "sev": 6, "occ": 4, "det": 3},
        {"name": "공정 파라미터 편차", "cat": "공정변동", "sev": 6, "occ": 4, "det": 4},
    ],
    "수동": [
        {"name": "조립 오류", "cat": "인적오류", "sev": 8, "occ": 6, "det": 6},
        {"name": "결선 오류", "cat": "인적오류", "sev": 9, "occ": 5, "det": 4},
        {"name": "체결 불량", "cat": "품질", "sev": 7, "occ": 5, "det": 5},
        {"name": "이물질 혼입", "cat": "오염", "sev": 6, "occ": 4, "det": 5},
    ],
}

SPEC_TEMPLATES = {
    "자동": [
        {"name": "공정 Cpk", "type": "statistical", "unit": "Cpk", "min": 1.33, "max": 9999},
        {"name": "사이클타임 편차", "type": "temporal", "unit": "sec", "min": 0, "max": 3},
    ],
    "반자동": [
        {"name": "작업자 숙련도", "type": "human", "unit": "Level", "min": 3, "max": 5},
        {"name": "체크리스트 준수율", "type": "compliance", "unit": "%", "min": 95, "max": 100},
    ],
    "수동": [
        {"name": "육안검사 적합률", "type": "visual", "unit": "%", "min": 98, "max": 100},
        {"name": "작업 표준 준수율", "type": "compliance", "unit": "%", "min": 90, "max": 100},
    ],
}

MATERIAL_TEMPLATES = {
    "PS-102": {"id": "MAT-011", "name": "소팅 트레이", "cat": "소모품", "cost": 0.5, "sup": "자체제작", "qty": 1},
    "PS-103": {"id": "MAT-012", "name": "스태킹 지그 패드", "cat": "소모품", "cost": 1.0, "sup": "자체제작", "qty": 1},
    "PS-105": {"id": "MAT-013", "name": "검사용 기준시편", "cat": "검사자재", "cost": 5.0, "sup": "자체제작", "qty": 0.01},
    "PS-106": {"id": "MAT-014", "name": "모듈 프레임", "cat": "구조부품", "cost": 25.0, "sup": "현대위아", "qty": 1},
    "PS-108": {"id": "MAT-015", "name": "테스트 프로브", "cat": "검사자재", "cost": 3.0, "sup": "자체제작", "qty": 0.1},
    "PS-202": {"id": "MAT-016", "name": "테스트 픽스쳐", "cat": "검사자재", "cost": 2.0, "sup": "자체제작", "qty": 0.05},
    "PS-204": {"id": "MAT-017", "name": "통전 테스트 리드", "cat": "검사자재", "cost": 1.5, "sup": "자체제작", "qty": 0.02},
    "PS-302": {"id": "MAT-018", "name": "세척액 (IPA)", "cat": "소모품", "cost": 2.0, "sup": "삼전순약", "qty": 0.5},
    "PS-303": {"id": "MAT-019", "name": "냉각 호스/피팅", "cat": "냉각부품", "cost": 8.0, "sup": "Gates", "qty": 1},
    "PS-304": {"id": "MAT-020", "name": "헬륨 가스", "cat": "검사자재", "cost": 5.0, "sup": "Air Liquide", "qty": 0.1},
    "PS-402": {"id": "MAT-021", "name": "차폐 가스 (Ar)", "cat": "소모품", "cost": 3.0, "sup": "Air Liquide", "qty": 0.2},
    "PS-403": {"id": "MAT-022", "name": "X-ray 필름", "cat": "검사자재", "cost": 4.0, "sup": "GE", "qty": 0.05},
    "PS-501": {"id": "MAT-023", "name": "인서트 가이드핀", "cat": "소모품", "cost": 1.0, "sup": "자체제작", "qty": 0.1},
    "PS-504": {"id": "MAT-024", "name": "커버 볼트", "cat": "체결부품", "cost": 0.3, "sup": "볼트원", "qty": 24},
    "PS-505": {"id": "MAT-025", "name": "HiPot 테스트 리드", "cat": "검사자재", "cost": 2.0, "sup": "자체제작", "qty": 0.02},
    "PS-506": {"id": "MAT-026", "name": "기밀검사 커넥터", "cat": "검사자재", "cost": 1.5, "sup": "자체제작", "qty": 0.01},
    "PS-507": {"id": "MAT-027", "name": "HIL 시뮬레이션 케이블", "cat": "검사자재", "cost": 3.0, "sup": "자체제작", "qty": 0.01},
    "PS-508": {"id": "MAT-028", "name": "출하 라벨", "cat": "소모품", "cost": 0.1, "sup": "자체제작", "qty": 1},
}


# ═══════════════════════════════════════════════════════════════
#  SKILL REGISTRY — 에이전트가 호출 가능한 스킬 목록
# ═══════════════════════════════════════════════════════════════

class SkillRegistry:
    """스킬을 등록/실행/추적하는 레지스트리."""

    def __init__(self):
        self._skills = {}
        self._usage_log = []  # (skill_name, agent, success, impact_score)
        self._counters = {"defect": 0, "spec": 100, "auto": 0, "maint": 0}

    def register(self, name, fn, description, category):
        self._skills[name] = {
            "fn": fn, "description": description, "category": category,
            "call_count": 0, "success_count": 0, "total_impact": 0.0,
        }

    def execute(self, name, conn, params, agent_name="unknown"):
        if name not in self._skills:
            return {"success": False, "error": f"스킬 '{name}' 없음"}
        skill = self._skills[name]
        skill["call_count"] += 1
        try:
            result = skill["fn"](conn, params, self._counters)
            success = result.get("success", False)
            impact = result.get("impact", 0.0)
            if success:
                skill["success_count"] += 1
                skill["total_impact"] += impact
            self._usage_log.append({
                "skill": name, "agent": agent_name,
                "success": success, "impact": impact,
            })
            return result
        except Exception as e:
            self._usage_log.append({
                "skill": name, "agent": agent_name,
                "success": False, "impact": 0.0,
            })
            return {"success": False, "error": str(e)[:200]}

    def get_stats(self):
        return {
            name: {
                "calls": s["call_count"],
                "successes": s["success_count"],
                "avg_impact": round(s["total_impact"] / max(s["success_count"], 1), 3),
                "category": s["category"],
            }
            for name, s in self._skills.items()
        }

    def list_skills(self):
        return {
            name: {"description": s["description"], "category": s["category"]}
            for name, s in self._skills.items()
        }


# ═══════════════════════════════════════════════════════════════
#  SKILL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════

def skill_bottleneck_analysis(conn, params, counters):
    """병목 공정을 식별하고 순위를 매긴다."""
    threshold = params.get("yield_threshold", 0.995)
    r = conn.execute("""
        MATCH (ps:ProcessStep)
        WHERE ps.yield_rate < $thr
        RETURN ps.id, ps.name, ps.yield_rate, ps.automation,
               ps.cycle_time, ps.oee, ps.area_id
        ORDER BY ps.yield_rate ASC
    """, {"thr": threshold})
    bottlenecks = []
    while r.has_next():
        row = r.get_next()
        bottlenecks.append({
            "id": row[0], "name": row[1], "yield": round(float(row[2]), 4),
            "auto": row[3], "cycle": int(row[4]),
            "oee": round(float(row[5]), 3), "area": row[6],
        })
    return {
        "success": True, "impact": len(bottlenecks) * 0.5,
        "bottlenecks": bottlenecks, "count": len(bottlenecks),
    }


def skill_coverage_analysis(conn, params, counters):
    """온톨로지 커버리지 갭을 분석한다."""
    gaps = {}

    # 품질기준 커버리지
    r = conn.execute("""
        MATCH (ps:ProcessStep)
        WHERE NOT (ps)-[:REQUIRES_SPEC]->(:QualitySpec)
        RETURN ps.id, ps.name, ps.automation
    """)
    gaps["spec_missing"] = []
    while r.has_next():
        row = r.get_next()
        gaps["spec_missing"].append({"id": row[0], "name": row[1], "auto": row[2]})

    # 결함모드 커버리지
    r = conn.execute("""
        MATCH (ps:ProcessStep)
        WHERE NOT (ps)-[:HAS_DEFECT]->(:DefectMode)
        RETURN ps.id, ps.name, ps.automation, ps.yield_rate
    """)
    gaps["defect_missing"] = []
    while r.has_next():
        row = r.get_next()
        gaps["defect_missing"].append({
            "id": row[0], "name": row[1], "auto": row[2], "yield": float(row[3]),
        })

    # 자재 커버리지
    r = conn.execute("""
        MATCH (ps:ProcessStep)
        WHERE NOT (ps)-[:CONSUMES]->(:Material)
        RETURN ps.id, ps.name
    """)
    gaps["material_missing"] = []
    while r.has_next():
        row = r.get_next()
        gaps["material_missing"].append({"id": row[0], "name": row[1]})

    # 보전계획 커버리지
    r = conn.execute("""
        MATCH (eq:Equipment)
        WHERE NOT (eq)-[:HAS_MAINTENANCE]->(:MaintenancePlan) AND eq.cost > 50000
        RETURN eq.id, eq.name, eq.cost, eq.mtbf_hours
    """)
    gaps["maintenance_missing"] = []
    while r.has_next():
        row = r.get_next()
        gaps["maintenance_missing"].append({
            "id": row[0], "name": row[1], "cost": int(row[2]), "mtbf": float(row[3]),
        })

    # 검사 연결 커버리지
    r = conn.execute("""
        MATCH (ps:ProcessStep)
        WHERE ps.yield_rate < 0.996 AND NOT (:ProcessStep)-[:INSPECTS]->(ps)
        RETURN ps.id, ps.name, ps.yield_rate
    """)
    gaps["inspection_missing"] = []
    while r.has_next():
        row = r.get_next()
        gaps["inspection_missing"].append({
            "id": row[0], "name": row[1], "yield": float(row[2]),
        })

    total_gaps = sum(len(v) for v in gaps.values())
    return {"success": True, "impact": total_gaps * 0.3, "gaps": gaps, "total_gaps": total_gaps}


def skill_graph_metrics(conn, params, counters):
    """그래프 구조 메트릭을 계산한다."""
    m = {}
    for label in ["ProcessArea", "ProcessStep", "Equipment", "Material",
                   "QualitySpec", "DefectMode", "AutomationPlan", "MaintenancePlan"]:
        try:
            r = conn.execute(f"MATCH (n:{label}) RETURN count(n) AS c")
            m[f"node_{label}"] = r.get_next()[0]
        except Exception:
            m[f"node_{label}"] = 0

    total_edges = 0
    edge_counts = {}
    for rel in ["NEXT_STEP", "FEEDS_INTO", "PARALLEL_WITH", "TRIGGERS_REWORK",
                "BELONGS_TO", "USES_EQUIPMENT", "CONSUMES", "REQUIRES_SPEC",
                "HAS_DEFECT", "PREVENTS", "PLANNED_UPGRADE", "HAS_MAINTENANCE",
                "DEPENDS_ON", "INSPECTS"]:
        try:
            r = conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c")
            c = r.get_next()[0]
        except Exception:
            c = 0
        edge_counts[rel] = c
        total_edges += c

    m["edge_counts"] = edge_counts
    m["total_edges"] = total_edges
    m["total_nodes"] = sum(m[f"node_{l}"] for l in
        ["ProcessArea", "ProcessStep", "Equipment", "Material", "QualitySpec",
         "DefectMode", "AutomationPlan", "MaintenancePlan"])
    n = m["total_nodes"]
    m["density"] = round(total_edges / (n * (n - 1)), 6) if n > 1 else 0

    # Yield
    r = conn.execute("""
        MATCH (ps:ProcessStep)
        RETURN avg(ps.yield_rate), min(ps.yield_rate), collect(ps.yield_rate),
               avg(ps.sigma_level), avg(ps.oee)
    """)
    row = r.get_next()
    m["avg_yield"] = round(float(row[0]), 5)
    m["min_yield"] = round(float(row[1]), 5)
    line_yield = 1.0
    for y in row[2]:
        line_yield *= y
    m["line_yield"] = round(line_yield, 6)
    m["avg_sigma"] = round(float(row[3]), 2)
    m["avg_oee"] = round(float(row[4]), 3)

    # Coverage ratios
    for cov_name, query in [
        ("spec_coverage", "MATCH (ps:ProcessStep) OPTIONAL MATCH (ps)-[:REQUIRES_SPEC]->(qs:QualitySpec) WITH ps, count(qs) AS sc RETURN sum(CASE WHEN sc > 0 THEN 1 ELSE 0 END), count(ps)"),
        ("material_coverage", "MATCH (ps:ProcessStep) OPTIONAL MATCH (ps)-[:CONSUMES]->(mat:Material) WITH ps, count(mat) AS mc RETURN sum(CASE WHEN mc > 0 THEN 1 ELSE 0 END), count(ps)"),
    ]:
        r = conn.execute(query)
        row = r.get_next()
        m[cov_name] = round(int(row[0]) / max(int(row[1]), 1), 3)

    for cov_name, query in [
        ("defect_coverage", "MATCH (ps:ProcessStep) OPTIONAL MATCH (ps)-[:HAS_DEFECT]->(d:DefectMode) WITH ps, count(d) AS dc RETURN sum(CASE WHEN dc > 0 THEN 1 ELSE 0 END), count(ps)"),
        ("maintenance_coverage", "MATCH (eq:Equipment) OPTIONAL MATCH (eq)-[:HAS_MAINTENANCE]->(mp:MaintenancePlan) WITH eq, count(mp) AS mc RETURN sum(CASE WHEN mc > 0 THEN 1 ELSE 0 END), count(eq)"),
        ("inspection_coverage", "MATCH (ps:ProcessStep) OPTIONAL MATCH (insp:ProcessStep)-[:INSPECTS]->(ps) WITH ps, count(insp) AS ic RETURN sum(CASE WHEN ic > 0 THEN 1 ELSE 0 END), count(ps)"),
    ]:
        try:
            r = conn.execute(query)
            row = r.get_next()
            m[cov_name] = round(int(row[0]) / max(int(row[1]), 1), 3)
        except Exception:
            m[cov_name] = 0.0

    # Cross-area
    r = conn.execute("MATCH (a:ProcessStep)-[:FEEDS_INTO]->(b:ProcessStep) WHERE a.area_id <> b.area_id RETURN count(*)")
    m["cross_area_edges"] = r.get_next()[0]

    # Automation distribution
    r = conn.execute("MATCH (ps:ProcessStep) RETURN ps.automation, count(ps) ORDER BY count(ps) DESC")
    auto_dist = {}
    while r.has_next():
        row = r.get_next()
        auto_dist[row[0]] = int(row[1])
    m["automation_distribution"] = auto_dist

    # Completeness score
    score = 0
    score += min(m["spec_coverage"] * 15, 15)
    score += min(m["material_coverage"] * 10, 10)
    score += min(m["defect_coverage"] * 15, 15)
    score += min(m["maintenance_coverage"] * 10, 10)
    score += min(m["inspection_coverage"] * 10, 10)
    score += min(m["density"] * 3000, 10)
    score += min(m["cross_area_edges"] / 10 * 10, 10)
    score += min((m["avg_yield"] - 0.98) * 500, 10)
    score += min(m.get("avg_oee", 0.85) * 10, 10)
    m["completeness_score"] = round(score, 1)

    return {"success": True, "impact": 0, "metrics": m}


def skill_add_defect_fmea(conn, params, counters):
    """특정 공정에 FMEA 결함모드를 추가한다."""
    step_id = params["step_id"]
    auto = params.get("automation", "자동")
    defects = DEFECT_DB.get(auto, DEFECT_DB["자동"])
    added = 0
    for d in defects:
        counters["defect"] += 1
        did = f"DM-{counters['defect']:03d}"
        rpn = d["sev"] * d["occ"] * d["det"]
        r = conn.execute("MATCH (n:DefectMode) WHERE n.id=$id RETURN count(n)", {"id": did})
        if r.get_next()[0] == 0:
            conn.execute(
                "CREATE (d:DefectMode {id:$id,name:$name,category:$cat,"
                "severity:$sev,occurrence:$occ,detection:$det,rpn:$rpn})",
                {"id": did, "name": d["name"], "cat": d["cat"],
                 "sev": d["sev"], "occ": d["occ"], "det": d["det"], "rpn": rpn})
        conn.execute(
            "MATCH (ps:ProcessStep),(dm:DefectMode) WHERE ps.id=$sid AND dm.id=$did "
            "CREATE (ps)-[:HAS_DEFECT]->(dm)",
            {"sid": step_id, "did": did})
        added += 1
    return {"success": True, "impact": added * 0.8, "added": added, "step_id": step_id}


def skill_add_quality_spec(conn, params, counters):
    """특정 공정에 품질기준을 추가한다."""
    step_id = params["step_id"]
    auto = params.get("automation", "자동")
    templates = SPEC_TEMPLATES.get(auto, SPEC_TEMPLATES["자동"])
    added = 0
    for tmpl in templates:
        counters["spec"] += 1
        sid = f"QS-{counters['spec']:03d}"
        r = conn.execute("MATCH (q:QualitySpec) WHERE q.id=$id RETURN count(q)", {"id": sid})
        if r.get_next()[0] == 0:
            conn.execute(
                "CREATE (q:QualitySpec {id:$id,name:$name,type:$type,unit:$unit,min_val:$mn,max_val:$mx})",
                {"id": sid, "name": tmpl["name"], "type": tmpl["type"],
                 "unit": tmpl["unit"], "mn": tmpl["min"], "mx": tmpl["max"]})
        conn.execute(
            "MATCH (ps:ProcessStep),(qs:QualitySpec) WHERE ps.id=$sid AND qs.id=$qid "
            "CREATE (ps)-[:REQUIRES_SPEC]->(qs)",
            {"sid": step_id, "qid": sid})
        conn.execute(
            "MATCH (ps:ProcessStep)-[:HAS_DEFECT]->(dm:DefectMode),"
            "(qs:QualitySpec) WHERE ps.id=$sid AND qs.id=$qid "
            "AND NOT (qs)-[:PREVENTS]->(dm) "
            "CREATE (qs)-[:PREVENTS]->(dm)",
            {"sid": step_id, "qid": sid})
        added += 1
    return {"success": True, "impact": added * 0.7, "added": added, "step_id": step_id}


def skill_add_material_link(conn, params, counters):
    """자재 연결이 없는 공정에 자재를 추가한다."""
    step_id = params["step_id"]
    if step_id not in MATERIAL_TEMPLATES:
        return {"success": False, "error": f"자재 템플릿 없음: {step_id}"}
    mt = MATERIAL_TEMPLATES[step_id]
    r = conn.execute("MATCH (m:Material) WHERE m.id=$id RETURN count(m)", {"id": mt["id"]})
    if r.get_next()[0] == 0:
        conn.execute(
            "CREATE (m:Material {id:$id,name:$name,category:$cat,cost:$cost,supplier:$sup,lead_time_days:7})",
            {"id": mt["id"], "name": mt["name"], "cat": mt["cat"],
             "cost": mt["cost"], "sup": mt["sup"]})
    conn.execute(
        "MATCH (ps:ProcessStep),(m:Material) WHERE ps.id=$sid AND m.id=$mid "
        "CREATE (ps)-[:CONSUMES {qty:$qty}]->(m)",
        {"sid": step_id, "mid": mt["id"], "qty": mt["qty"]})
    return {"success": True, "impact": 0.5, "material": mt["name"], "step_id": step_id}


def skill_automation_upgrade(conn, params, counters):
    """병목 공정의 자동화 레벨을 업그레이드한다."""
    step_id = params["step_id"]
    from_lvl = params["from_level"]
    to_lvl = params["to_level"]
    counters["auto"] += 1
    aid = f"AP-{counters['auto']:03d}"
    yield_gain = 0.003 if from_lvl == "수동" else 0.002
    cycle_red = 5 if from_lvl == "수동" else 3
    invest = 150000 if to_lvl == "자동" else 50000

    conn.execute(
        "CREATE (ap:AutomationPlan {id:$id,name:$name,from_level:$fl,to_level:$tl,"
        "investment:$inv,expected_yield_gain:$yg,expected_cycle_reduction:$cr})",
        {"id": aid, "name": f"{params.get('step_name', step_id)} 자동화",
         "fl": from_lvl, "tl": to_lvl, "inv": invest,
         "yg": yield_gain, "cr": cycle_red})
    conn.execute(
        "MATCH (ps:ProcessStep),(ap:AutomationPlan) WHERE ps.id=$sid AND ap.id=$aid "
        "CREATE (ps)-[:PLANNED_UPGRADE]->(ap)",
        {"sid": step_id, "aid": aid})

    r = conn.execute("MATCH (ps:ProcessStep) WHERE ps.id=$id RETURN ps.yield_rate, ps.oee", {"id": step_id})
    row = r.get_next()
    new_yield = min(round(float(row[0]) + yield_gain, 5), 0.999)
    new_oee = min(round(float(row[1]) + 0.03, 3), 0.95)
    conn.execute(
        "MATCH (ps:ProcessStep) WHERE ps.id=$id SET ps.yield_rate=$yr, ps.oee=$oee, ps.automation=$auto",
        {"id": step_id, "yr": new_yield, "oee": new_oee, "auto": to_lvl})

    return {
        "success": True, "impact": yield_gain * 100 + 1.0,
        "yield_gain": yield_gain, "investment": invest, "step_id": step_id,
    }


def skill_add_maintenance_plan(conn, params, counters):
    """설비에 보전 계획을 추가한다."""
    equip_id = params["equip_id"]
    equip_cost = params.get("equip_cost", 100000)
    counters["maint"] += 1
    mid = f"MP-{counters['maint']:03d}"
    strategy = "예방보전" if equip_cost > 200000 else "상태기반보전"
    interval = 500 if equip_cost > 200000 else 1000
    conn.execute(
        "CREATE (mp:MaintenancePlan {id:$id,name:$name,strategy:$strat,"
        "interval_hours:$ih,cost_per_event:$cpe})",
        {"id": mid, "name": f"{params.get('equip_name', equip_id)[:12]} 보전계획",
         "strat": strategy, "ih": interval,
         "cpe": round(equip_cost * 0.02)})
    conn.execute(
        "MATCH (eq:Equipment),(mp:MaintenancePlan) WHERE eq.id=$eid AND mp.id=$mid "
        "CREATE (eq)-[:HAS_MAINTENANCE]->(mp)",
        {"eid": equip_id, "mid": mid})
    return {"success": True, "impact": 0.8, "strategy": strategy, "equip_id": equip_id}


def skill_add_inspection_link(conn, params, counters):
    """저수율 공정에 검사 연결을 추가한다."""
    step_id = params["step_id"]
    ra = conn.execute("MATCH (ps:ProcessStep) WHERE ps.id=$id RETURN ps.area_id", {"id": step_id})
    area = ra.get_next()[0] if ra.has_next() else ""
    r = conn.execute(
        "MATCH (insp:ProcessStep) WHERE insp.name CONTAINS '검사' AND insp.id <> $sid AND insp.area_id = $area "
        "RETURN insp.id LIMIT 1", {"sid": step_id, "area": area})
    if not r.has_next():
        r = conn.execute(
            "MATCH (insp:ProcessStep) WHERE insp.name CONTAINS '검사' AND insp.id <> $sid "
            "RETURN insp.id LIMIT 1", {"sid": step_id})
    if not r.has_next():
        return {"success": False, "error": "검사 공정 없음"}
    insp_id = r.get_next()[0]
    r2 = conn.execute(
        "MATCH (a:ProcessStep)-[:INSPECTS]->(b:ProcessStep) WHERE a.id=$a AND b.id=$b RETURN count(*)",
        {"a": insp_id, "b": step_id})
    if r2.get_next()[0] > 0:
        return {"success": False, "error": "이미 연결됨"}
    conn.execute(
        "MATCH (a:ProcessStep),(b:ProcessStep) WHERE a.id=$a AND b.id=$b CREATE (a)-[:INSPECTS]->(b)",
        {"a": insp_id, "b": step_id})
    return {"success": True, "impact": 0.6, "inspector": insp_id, "step_id": step_id}


def skill_yield_improvement(conn, params, counters):
    """수율 개선 시뮬레이션을 실행한다."""
    step_id = params["step_id"]
    r = conn.execute("MATCH (ps:ProcessStep) WHERE ps.id=$id RETURN ps.yield_rate, ps.sigma_level", {"id": step_id})
    if not r.has_next():
        return {"success": False, "error": "공정 없음"}
    row = r.get_next()
    old_yield = float(row[0])
    new_yield = min(round(old_yield + 0.003, 5), 0.999)
    new_sigma = round(float(row[1]) + 0.3, 2)
    conn.execute(
        "MATCH (ps:ProcessStep) WHERE ps.id=$id SET ps.yield_rate=$yr, ps.sigma_level=$sig",
        {"id": step_id, "yr": new_yield, "sig": new_sigma})
    return {
        "success": True, "impact": (new_yield - old_yield) * 100,
        "old_yield": old_yield, "new_yield": new_yield, "step_id": step_id,
    }


def skill_add_rework_link(conn, params, counters):
    """재작업 경로를 추가한다."""
    step_id = params["step_id"]
    r = conn.execute(
        "MATCH (prev:ProcessStep)-[:NEXT_STEP]->(ps:ProcessStep) WHERE ps.id=$id RETURN prev.id",
        {"id": step_id})
    if not r.has_next():
        return {"success": False, "error": "이전 공정 없음"}
    prev_id = r.get_next()[0]
    r2 = conn.execute(
        "MATCH (a:ProcessStep)-[:TRIGGERS_REWORK]->(b:ProcessStep) WHERE a.id=$a AND b.id=$b RETURN count(*)",
        {"a": step_id, "b": prev_id})
    if r2.get_next()[0] > 0:
        return {"success": False, "error": "이미 존재"}
    conn.execute(
        "MATCH (a:ProcessStep),(b:ProcessStep) WHERE a.id=$a AND b.id=$b CREATE (a)-[:TRIGGERS_REWORK]->(b)",
        {"a": step_id, "b": prev_id})
    return {"success": True, "impact": 0.5, "from": step_id, "to": prev_id}


def skill_cross_dependency_mapping(conn, params, counters):
    """영역 간 의존성을 매핑한다."""
    r = conn.execute("""
        MATCH (a:ProcessStep)-[:CONSUMES]->(m:Material)<-[:CONSUMES]-(b:ProcessStep)
        WHERE a.id < b.id AND a.area_id <> b.area_id AND NOT (a)-[:DEPENDS_ON]->(b)
        RETURN a.id, b.id, m.name LIMIT 5
    """)
    added = 0
    while r.has_next():
        row = r.get_next()
        conn.execute(
            "MATCH (a:ProcessStep),(b:ProcessStep) WHERE a.id=$a AND b.id=$b "
            "CREATE (a)-[:DEPENDS_ON {dependency_type:$dt}]->(b)",
            {"a": row[0], "b": row[1], "dt": f"공유자재:{row[2]}"})
        added += 1
    return {"success": added > 0, "impact": added * 0.4, "added": added}


def skill_cost_benefit_analysis(conn, params, counters):
    """자동화 업그레이드의 비용 대비 효과를 분석한다."""
    r = conn.execute("""
        MATCH (ps:ProcessStep)
        WHERE ps.yield_rate < 0.995 AND ps.automation IN ['수동', '반자동']
        RETURN ps.id, ps.name, ps.yield_rate, ps.automation,
               ps.cycle_time, ps.operators, ps.equip_cost
    """)
    analyses = []
    while r.has_next():
        row = r.get_next()
        auto = row[3]
        operators = int(row[5])
        yearly_labor_saving = operators * 50000 if auto == "수동" else operators * 25000
        invest = 150000 if auto == "수동" else 80000
        yield_gain = 0.003 if auto == "수동" else 0.002
        yield_value = yield_gain * 1000000  # approximate yearly value of yield gain
        roi_months = round(invest / max((yearly_labor_saving + yield_value) / 12, 1), 1)
        analyses.append({
            "step_id": row[0], "step_name": row[1],
            "current_yield": float(row[2]), "automation": auto,
            "investment": invest, "yearly_saving": yearly_labor_saving + yield_value,
            "roi_months": roi_months, "recommended": roi_months < 18,
        })
    analyses.sort(key=lambda x: x["roi_months"])
    return {"success": True, "impact": len(analyses) * 0.3, "analyses": analyses}


def skill_safety_risk_assessment(conn, params, counters):
    """안전 위험도를 평가한다."""
    r = conn.execute("""
        MATCH (ps:ProcessStep)
        RETURN ps.id, ps.name, ps.safety_level, ps.automation, ps.operators
    """)
    risks = []
    while r.has_next():
        row = r.get_next()
        safety = row[2]
        auto = row[3]
        ops = int(row[4])
        risk_score = {"A": 9, "B": 5, "C": 2}.get(safety, 5)
        if auto == "수동":
            risk_score += 3
        risk_score += min(ops, 4)
        risks.append({
            "step_id": row[0], "step_name": row[1],
            "safety_level": safety, "automation": auto,
            "operators": ops, "risk_score": risk_score,
            "priority": "CRITICAL" if risk_score >= 12 else "HIGH" if risk_score >= 8 else "MEDIUM",
        })
    risks.sort(key=lambda x: -x["risk_score"])
    return {"success": True, "impact": 0.2, "risks": risks}


def create_skill_registry():
    """모든 스킬이 등록된 레지스트리를 생성한다."""
    reg = SkillRegistry()
    reg.register("bottleneck_analysis", skill_bottleneck_analysis,
                 "수율/OEE 기준 병목 공정 식별 및 순위 산출", "analysis")
    reg.register("coverage_analysis", skill_coverage_analysis,
                 "온톨로지 커버리지 갭 분석 (품질/결함/자재/보전/검사)", "analysis")
    reg.register("graph_metrics", skill_graph_metrics,
                 "그래프 구조 메트릭 및 온톨로지 완전성 점수 산출", "analysis")
    reg.register("add_defect_fmea", skill_add_defect_fmea,
                 "FMEA 기반 결함모드 추가 및 HAS_DEFECT 관계 생성", "mutation")
    reg.register("add_quality_spec", skill_add_quality_spec,
                 "품질기준 추가 및 REQUIRES_SPEC/PREVENTS 관계 생성", "mutation")
    reg.register("add_material_link", skill_add_material_link,
                 "누락된 자재 연결 추가 (CONSUMES 관계)", "mutation")
    reg.register("automation_upgrade", skill_automation_upgrade,
                 "자동화 업그레이드 계획 생성 및 수율/OEE 시뮬레이션", "mutation")
    reg.register("add_maintenance_plan", skill_add_maintenance_plan,
                 "설비 보전 계획 생성 (예방/상태기반)", "mutation")
    reg.register("add_inspection_link", skill_add_inspection_link,
                 "검사 공정 연결 추가 (INSPECTS 관계)", "mutation")
    reg.register("yield_improvement", skill_yield_improvement,
                 "수율 개선 시뮬레이션 (시그마 레벨 향상)", "mutation")
    reg.register("add_rework_link", skill_add_rework_link,
                 "재작업 경로 추가 (TRIGGERS_REWORK 관계)", "mutation")
    reg.register("cross_dependency_mapping", skill_cross_dependency_mapping,
                 "영역 간 공유자재 의존성 매핑 (DEPENDS_ON 관계)", "mutation")
    reg.register("cost_benefit_analysis", skill_cost_benefit_analysis,
                 "자동화 투자 ROI 분석", "analysis")
    reg.register("safety_risk_assessment", skill_safety_risk_assessment,
                 "안전 위험도 평가 및 우선순위 산출", "analysis")
    return reg
