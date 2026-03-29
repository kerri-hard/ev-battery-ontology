"""
Harness Loop v3 — Multi-Agent Debate Harness
=============================================
6종 전문 에이전트가 토론/투표를 통해 온톨로지를 자율 개선하는 루프 시스템.

Loop:
  ① OBSERVE  — 각 에이전트가 자기 관점으로 온톨로지 분석
  ② PROPOSE  — 분석 결과를 바탕으로 개선안 제안
  ③ DEBATE   — 상호 비평 + 투표 (신뢰도 가중)
  ④ APPLY    — 승인된 제안을 스킬로 실행
  ⑤ EVALUATE — 개선 효과 측정
  ⑥ LEARN    — 에이전트 신뢰도/스킬 효과 업데이트
"""
import kuzu
import json
import os
import shutil
import copy
from datetime import datetime
from collections import defaultdict

from .agents import create_agents, Moderator, Proposal
from .skills import create_skill_registry


# ─── Configuration ────────────────────────────────────────────
DEFAULT_CONFIG = {
    "db_path": "kuzu_v3_db",
    "data_path": "data/graph_data.json",
    "output_path": "results/harness_v3_results.json",
    "max_iterations": 10,
    "convergence_threshold": 0.3,
}


# ═══════════════════════════════════════════════════════════════
#  DB INITIALIZATION (v2 스키마 재사용)
# ═══════════════════════════════════════════════════════════════

def init_db(db_path):
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    conn.execute("""CREATE NODE TABLE ProcessArea (
        id STRING, name STRING, color STRING,
        cycle_time INT64, step_count INT64,
        takt_time DOUBLE DEFAULT 0.0, PRIMARY KEY(id))""")
    conn.execute("""CREATE NODE TABLE ProcessStep (
        id STRING, name STRING, area_id STRING,
        cycle_time INT64, yield_rate DOUBLE,
        automation STRING, equipment STRING,
        equip_cost INT64, operators INT64,
        safety_level STRING,
        oee DOUBLE DEFAULT 0.85,
        sigma_level DOUBLE DEFAULT 3.0, PRIMARY KEY(id))""")
    conn.execute("""CREATE NODE TABLE Equipment (
        id STRING, name STRING, cost INT64,
        mtbf_hours DOUBLE DEFAULT 2000.0,
        mttr_hours DOUBLE DEFAULT 4.0, PRIMARY KEY(id))""")
    conn.execute("""CREATE NODE TABLE Material (
        id STRING, name STRING, category STRING,
        cost DOUBLE, supplier STRING,
        lead_time_days INT64 DEFAULT 7, PRIMARY KEY(id))""")
    conn.execute("""CREATE NODE TABLE QualitySpec (
        id STRING, name STRING, type STRING,
        unit STRING, min_val DOUBLE, max_val DOUBLE, PRIMARY KEY(id))""")
    conn.execute("""CREATE NODE TABLE DefectMode (
        id STRING, name STRING, category STRING,
        severity INT64, occurrence INT64, detection INT64,
        rpn INT64, PRIMARY KEY(id))""")
    conn.execute("""CREATE NODE TABLE AutomationPlan (
        id STRING, name STRING, from_level STRING,
        to_level STRING, investment INT64,
        expected_yield_gain DOUBLE,
        expected_cycle_reduction INT64, PRIMARY KEY(id))""")
    conn.execute("""CREATE NODE TABLE MaintenancePlan (
        id STRING, name STRING, strategy STRING,
        interval_hours INT64, cost_per_event INT64, PRIMARY KEY(id))""")

    conn.execute("CREATE REL TABLE NEXT_STEP (FROM ProcessStep TO ProcessStep)")
    conn.execute("CREATE REL TABLE FEEDS_INTO (FROM ProcessStep TO ProcessStep)")
    conn.execute("CREATE REL TABLE PARALLEL_WITH (FROM ProcessStep TO ProcessStep)")
    conn.execute("CREATE REL TABLE TRIGGERS_REWORK (FROM ProcessStep TO ProcessStep)")
    conn.execute("CREATE REL TABLE BELONGS_TO (FROM ProcessStep TO ProcessArea)")
    conn.execute("CREATE REL TABLE USES_EQUIPMENT (FROM ProcessStep TO Equipment)")
    conn.execute("CREATE REL TABLE CONSUMES (FROM ProcessStep TO Material, qty DOUBLE)")
    conn.execute("CREATE REL TABLE REQUIRES_SPEC (FROM ProcessStep TO QualitySpec)")
    conn.execute("CREATE REL TABLE HAS_DEFECT (FROM ProcessStep TO DefectMode)")
    conn.execute("CREATE REL TABLE PREVENTS (FROM QualitySpec TO DefectMode)")
    conn.execute("CREATE REL TABLE PLANNED_UPGRADE (FROM ProcessStep TO AutomationPlan)")
    conn.execute("CREATE REL TABLE HAS_MAINTENANCE (FROM Equipment TO MaintenancePlan)")
    conn.execute("CREATE REL TABLE DEPENDS_ON (FROM ProcessStep TO ProcessStep, dependency_type STRING)")
    conn.execute("CREATE REL TABLE INSPECTS (FROM ProcessStep TO ProcessStep)")

    return db, conn


def populate_base(conn, raw):
    equip_map = {}
    for a in raw["areas"]:
        conn.execute(
            "CREATE (pa:ProcessArea {id:$id,name:$name,color:$color,"
            "cycle_time:$ct,step_count:$sc,takt_time:$tt})",
            {"id": a["id"], "name": a["name"], "color": a["color"],
             "ct": a["cycle"], "sc": a["steps"],
             "tt": round(a["cycle"] / a["steps"], 2)})
    for s in raw["steps"]:
        sigma = 3.0 + (s["yield_rate"] - 0.98) * 100
        conn.execute(
            "CREATE (ps:ProcessStep {id:$id,name:$name,area_id:$area,"
            "cycle_time:$ct,yield_rate:$yr,automation:$auto,equipment:$eq,"
            "equip_cost:$ec,operators:$op,safety_level:$sl,oee:$oee,sigma_level:$sig})",
            {"id": s["id"], "name": s["name"], "area": s["area"],
             "ct": s["cycle"], "yr": s["yield_rate"], "auto": s["auto"],
             "eq": s["equipment"], "ec": s["equip_cost"], "op": s["operators"],
             "sl": s["safety"], "oee": round(0.75 + s["yield_rate"] * 0.1, 3),
             "sig": round(sigma, 2)})
    for i, s in enumerate(raw["steps"]):
        eid = f"EQ-{i+1:03d}"
        if s["equipment"] not in equip_map:
            equip_map[s["equipment"]] = eid
            mtbf = 1500 + s["equip_cost"] / 100
            conn.execute(
                "CREATE (e:Equipment {id:$id,name:$name,cost:$cost,"
                "mtbf_hours:$mtbf,mttr_hours:$mttr})",
                {"id": eid, "name": s["equipment"], "cost": s["equip_cost"],
                 "mtbf": round(mtbf), "mttr": round(4 + s["equip_cost"] / 200000, 1)})
    mat_seen = set()
    for m in raw["materials"]:
        if m["mat_id"] not in mat_seen:
            mat_seen.add(m["mat_id"])
            conn.execute(
                "CREATE (m:Material {id:$id,name:$name,category:$cat,"
                "cost:$cost,supplier:$sup,lead_time_days:7})",
                {"id": m["mat_id"], "name": m["mat_name"], "cat": m["category"],
                 "cost": m["cost"], "sup": m["supplier"]})
    qs_seen = set()
    for q in raw["quality"]:
        if q["spec_id"] not in qs_seen:
            qs_seen.add(q["spec_id"])
            conn.execute(
                "CREATE (q:QualitySpec {id:$id,name:$name,type:$type,"
                "unit:$unit,min_val:$mn,max_val:$mx})",
                {"id": q["spec_id"], "name": q["spec_name"], "type": q["type"],
                 "unit": q["unit"], "mn": q["min"], "mx": q["max"]})
    for e in raw["edges"]:
        conn.execute(
            f"MATCH (a:ProcessStep),(b:ProcessStep) WHERE a.id=$s AND b.id=$t "
            f"CREATE (a)-[:{e['type']}]->(b)",
            {"s": e["source"], "t": e["target"]})
    for s in raw["steps"]:
        conn.execute(
            "MATCH (ps:ProcessStep),(pa:ProcessArea) WHERE ps.id=$sid AND pa.id=$aid "
            "CREATE (ps)-[:BELONGS_TO]->(pa)",
            {"sid": s["id"], "aid": s["area"]})
    for s in raw["steps"]:
        eid = equip_map[s["equipment"]]
        conn.execute(
            "MATCH (ps:ProcessStep),(eq:Equipment) WHERE ps.id=$sid AND eq.id=$eid "
            "CREATE (ps)-[:USES_EQUIPMENT]->(eq)",
            {"sid": s["id"], "eid": eid})
    for m in raw["materials"]:
        conn.execute(
            "MATCH (ps:ProcessStep),(mat:Material) WHERE ps.id=$sid AND mat.id=$mid "
            "CREATE (ps)-[:CONSUMES {qty:$qty}]->(mat)",
            {"sid": m["step_id"], "mid": m["mat_id"], "qty": m["qty"]})
    for q in raw["quality"]:
        conn.execute(
            "MATCH (ps:ProcessStep),(qs:QualitySpec) WHERE ps.id=$sid AND qs.id=$qid "
            "CREATE (ps)-[:REQUIRES_SPEC]->(qs)",
            {"sid": q["step_id"], "qid": q["spec_id"]})
    return equip_map


# ═══════════════════════════════════════════════════════════════
#  EVALUATION & LEARNING
# ═══════════════════════════════════════════════════════════════

def evaluate_iteration(prev_metrics, curr_metrics, iteration):
    deltas = {}
    keys = [
        ("total_nodes", "총 노드 수", "up"),
        ("total_edges", "총 엣지 수", "up"),
        ("density", "그래프 밀도", "up"),
        ("spec_coverage", "품질기준 커버리지", "up"),
        ("material_coverage", "자재 커버리지", "up"),
        ("defect_coverage", "결함모드 커버리지", "up"),
        ("maintenance_coverage", "보전계획 커버리지", "up"),
        ("inspection_coverage", "검사 연결 커버리지", "up"),
        ("cross_area_edges", "영역 간 연결", "up"),
        ("line_yield", "라인 수율", "up"),
        ("avg_oee", "평균 OEE", "up"),
        ("avg_sigma", "평균 시그마", "up"),
        ("completeness_score", "온톨로지 완성도", "up"),
    ]
    for key, label, direction in keys:
        prev = prev_metrics.get(key, 0)
        curr = curr_metrics.get(key, 0)
        change = curr - prev if isinstance(curr, (int, float)) else 0
        pct = (change / prev * 100) if prev != 0 else 0
        deltas[key] = {
            "label": label,
            "prev": round(prev, 4) if isinstance(prev, float) else prev,
            "curr": round(curr, 4) if isinstance(curr, float) else curr,
            "change": round(change, 4),
            "pct": round(pct, 1),
            "improved": (change > 0 and direction == "up"),
        }
    improved_count = sum(1 for d in deltas.values() if d["improved"])
    eval_score = round(improved_count / len(deltas) * 100, 1)
    score_delta = deltas["completeness_score"]["change"]
    converged = abs(score_delta) < DEFAULT_CONFIG["convergence_threshold"] and iteration > 2
    return {
        "deltas": deltas, "improvement_rate": eval_score,
        "converged": converged, "score_delta": round(score_delta, 2),
    }


def learn_from_results(agents, approved_proposals, pre_metrics, post_metrics):
    """
    ⑥ LEARN: 제안 결과를 바탕으로 에이전트 신뢰도를 업데이트한다.
    - 제안이 실제로 메트릭을 개선했으면 → 신뢰도 +0.05
    - 제안이 실패했거나 악화시켰으면 → 신뢰도 -0.03
    """
    score_change = post_metrics.get("completeness_score", 0) - pre_metrics.get("completeness_score", 0)
    yield_change = post_metrics.get("line_yield", 0) - pre_metrics.get("line_yield", 0)

    agent_map = {a.name: a for a in agents}
    agent_contributions = defaultdict(lambda: {"applied": 0, "success": 0})

    for p in approved_proposals:
        agent_name = p.agent_name
        if p.status == "applied":
            agent_contributions[agent_name]["applied"] += 1
            agent_contributions[agent_name]["success"] += 1
        elif p.status in ("failed", "approved"):
            agent_contributions[agent_name]["applied"] += 1

    overall_improved = score_change > 0

    learning_log = []
    for agent in agents:
        contrib = agent_contributions[agent.name]
        if contrib["applied"] == 0:
            continue

        success_rate = contrib["success"] / max(contrib["applied"], 1)
        if overall_improved and success_rate > 0.5:
            delta = 0.05 * success_rate
            agent.update_trust(delta)
            agent.record_result(True)
            learning_log.append({
                "agent": agent.name, "trust_delta": round(delta, 3),
                "new_trust": round(agent.trust_score, 3),
                "reason": f"개선 기여 (적용 {contrib['applied']}, 성공률 {success_rate:.0%})",
            })
        elif not overall_improved:
            delta = -0.03
            agent.update_trust(delta)
            agent.record_result(False)
            learning_log.append({
                "agent": agent.name, "trust_delta": delta,
                "new_trust": round(agent.trust_score, 3),
                "reason": f"개선 미달 (완성도 Δ{score_change:+.1f})",
            })

    return learning_log


# ═══════════════════════════════════════════════════════════════
#  MAIN HARNESS LOOP v3
# ═══════════════════════════════════════════════════════════════

def run_harness_loop(config=None):
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    print("=" * 65)
    print("  EV Battery Manufacturing Ontology — Harness Loop v3")
    print("  Multi-Agent Debate System")
    print("  6 Specialist Agents + Moderator / 14 Skills")
    print("=" * 65)

    # ── Initialize ──
    with open(cfg["data_path"]) as f:
        raw = json.load(f)

    db, conn = init_db(cfg["db_path"])
    populate_base(conn, raw)
    print("  [INIT] 온톨로지 초기화 완료\n")

    agents = create_agents()
    moderator = Moderator()
    skill_registry = create_skill_registry()

    print(f"  [AGENTS] {len(agents)}명 에이전트 참여:")
    for a in agents:
        print(f"    - {a.name:25s} | {a.DESCRIPTION}")
    print(f"\n  [SKILLS] {len(skill_registry.list_skills())}개 스킬 등록:")
    for name, info in skill_registry.list_skills().items():
        print(f"    - {name:30s} | {info['description'][:40]}")
    print()

    # ── Initial metrics ──
    init_result = skill_registry.execute("graph_metrics", conn, {}, "system")
    initial_metrics = init_result["metrics"]
    iteration_history = []

    # ── Reset Proposal counter ──
    Proposal._counter = 0

    for i in range(cfg["max_iterations"]):
        print(f"\n{'━' * 65}")
        print(f"  ITERATION {i+1}/{cfg['max_iterations']}")
        print(f"{'━' * 65}")

        # ① OBSERVE
        print(f"  [①] OBSERVE — 각 에이전트가 온톨로지를 분석합니다...")
        gm = skill_registry.execute("graph_metrics", conn, {}, "system")
        pre_metrics = gm["metrics"]
        all_observations = {}
        for agent in agents:
            obs = agent.observe(conn, skill_registry, pre_metrics)
            all_observations[agent.name] = obs

        print(f"      노드: {pre_metrics['total_nodes']}, 엣지: {pre_metrics['total_edges']}, "
              f"밀도: {pre_metrics['density']:.4f}")
        print(f"      수율: {pre_metrics['line_yield']:.4f}, OEE: {pre_metrics['avg_oee']:.3f}, "
              f"완성도: {pre_metrics['completeness_score']}")

        # ② PROPOSE
        print(f"  [②] PROPOSE — 에이전트들이 개선안을 제안합니다...")
        all_proposals = []
        for agent in agents:
            proposals = agent.propose(conn, skill_registry, all_observations[agent.name], i)
            all_proposals.extend(proposals)
            if proposals:
                print(f"      {agent.name:25s} → {len(proposals)}개 제안")

        if not all_proposals:
            print(f"      (제안 없음 — 수렴 상태)")
            if i > 2:
                print(f"\n  ★ 수렴 감지! 더 이상 개선 제안이 없습니다.")
                break
            continue

        # ③ DEBATE (Critique + Vote)
        print(f"  [③] DEBATE — 상호 비평 및 투표 진행 중...")
        approved, debate_log = moderator.run_debate(agents, all_proposals, all_observations)
        print(f"      총 제안: {debate_log['total_proposals']}, "
              f"비평: {len(debate_log['critiques'])}건, "
              f"승인: {len(approved)}건, "
              f"거부: {len(debate_log['rejected'])}건")

        # 투표 결과 상위 표시
        sorted_votes = sorted(debate_log["vote_summary"], key=lambda x: -x["score"])
        for v in sorted_votes[:5]:
            status = "✓" if v["score"] >= moderator.APPROVAL_THRESHOLD else "✗"
            print(f"      {status} [{v['score']:+5.1f}] {v['action']:25s} by {v['agent']}")

        if not approved:
            print(f"      (승인된 제안 없음)")
            continue

        # ④ APPLY
        print(f"  [④] APPLY — 승인된 {len(approved)}건을 적용합니다...")
        applied_count = 0
        failed_count = 0
        for p in approved:
            result = skill_registry.execute(p.skill_name, conn, p.params, p.agent_name)
            if result.get("success"):
                p.status = "applied"
                applied_count += 1
            else:
                p.status = "failed"
                failed_count += 1
        print(f"      적용: {applied_count}건, 실패: {failed_count}건")

        # ⑤ EVALUATE
        print(f"  [⑤] EVALUATE — 개선 효과를 측정합니다...")
        gm_post = skill_registry.execute("graph_metrics", conn, {}, "system")
        post_metrics = gm_post["metrics"]
        evaluation = evaluate_iteration(pre_metrics, post_metrics, i)
        print(f"      완성도: {pre_metrics['completeness_score']} → {post_metrics['completeness_score']} "
              f"(Δ{evaluation['score_delta']:+.1f})")
        print(f"      수율: {pre_metrics['line_yield']:.4f} → {post_metrics['line_yield']:.4f}")
        print(f"      개선률: {evaluation['improvement_rate']:.0f}%")

        # ⑥ LEARN
        print(f"  [⑥] LEARN — 에이전트 신뢰도를 업데이트합니다...")
        learning_log = learn_from_results(agents, approved, pre_metrics, post_metrics)
        for ll in learning_log:
            arrow = "↑" if ll["trust_delta"] > 0 else "↓"
            print(f"      {ll['agent']:25s} 신뢰도 {arrow} {ll['new_trust']:.3f} ({ll['reason']})")

        # Record iteration
        iteration_history.append({
            "iteration": i + 1,
            "pre_metrics": pre_metrics,
            "post_metrics": post_metrics,
            "proposals_total": len(all_proposals),
            "proposals_approved": len(approved),
            "proposals_applied": applied_count,
            "proposals_failed": failed_count,
            "debate_log": {
                "critiques_count": len(debate_log["critiques"]),
                "approved_count": len(debate_log["approved"]),
                "rejected_count": len(debate_log["rejected"]),
                "top_votes": sorted_votes[:10],
            },
            "evaluation": evaluation,
            "learning_log": learning_log,
            "agent_trust": {a.name: round(a.trust_score, 3) for a in agents},
        })

        if evaluation["converged"]:
            print(f"\n  ★ 수렴 감지! (Δ완성도: {evaluation['score_delta']:.2f} < {cfg['convergence_threshold']})")
            break

    # ── Final Summary ──
    gm_final = skill_registry.execute("graph_metrics", conn, {}, "system")
    final_metrics = gm_final["metrics"]
    overall_eval = evaluate_iteration(initial_metrics, final_metrics, len(iteration_history))

    result = {
        "system": "EV Battery Pack Manufacturing Ontology — Harness Loop v3",
        "architecture": "Multi-Agent Debate System",
        "db_engine": "Kuzu (Extended Schema)",
        "agents": [a.stats() for a in agents],
        "skills": skill_registry.get_stats(),
        "total_iterations": len(iteration_history),
        "initial_metrics": initial_metrics,
        "final_metrics": final_metrics,
        "overall_evaluation": overall_eval,
        "iteration_history": iteration_history,
        "moderator_log": moderator.debate_log,
        "v3_features": {
            "agent_types": [a.ROLE for a in agents],
            "agent_count": len(agents),
            "skill_count": len(skill_registry.list_skills()),
            "debate_protocol": "OBSERVE → PROPOSE → CRITIQUE → VOTE → APPLY → EVALUATE → LEARN",
            "trust_weighted_voting": True,
            "adaptive_learning": True,
            "convergence_detection": True,
        },
        "timestamp": datetime.now().isoformat(),
    }

    os.makedirs(os.path.dirname(cfg["output_path"]) or ".", exist_ok=True)
    with open(cfg["output_path"], "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'=' * 65}")
    print(f"  하네스 루프 v3 완료!")
    print(f"{'─' * 65}")
    print(f"  반복 횟수:  {len(iteration_history)}")
    print(f"  노드:       {initial_metrics['total_nodes']} → {final_metrics['total_nodes']}")
    print(f"  엣지:       {initial_metrics['total_edges']} → {final_metrics['total_edges']}")
    print(f"  밀도:       {initial_metrics['density']:.4f} → {final_metrics['density']:.4f}")
    print(f"  라인수율:   {initial_metrics['line_yield']:.4f} → {final_metrics['line_yield']:.4f}")
    print(f"  완성도:     {initial_metrics['completeness_score']} → {final_metrics['completeness_score']}")
    print(f"{'─' * 65}")
    print(f"  에이전트 최종 신뢰도:")
    for a in agents:
        bar = "█" * int(a.trust_score * 10) + "░" * (20 - int(a.trust_score * 10))
        print(f"    {a.name:25s} [{bar}] {a.trust_score:.3f}")
    print(f"{'─' * 65}")
    print(f"  스킬 사용 통계:")
    for name, stat in skill_registry.get_stats().items():
        if stat["calls"] > 0:
            print(f"    {name:30s} | 호출: {stat['calls']:3d}, 성공: {stat['successes']:3d}, "
                  f"평균 임팩트: {stat['avg_impact']:.2f}")
    print(f"{'=' * 65}")

    return result
