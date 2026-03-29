"""
HarnessEngine — 실시간 시뮬레이션 엔진
WebSocket을 통해 매 단계마다 이벤트를 발행하는 하네스 루프 엔진.
"""
import asyncio
import json
import os
import shutil
import time
from datetime import datetime
from collections import defaultdict

import kuzu

from .agents import create_agents, Moderator, Proposal
from .skills import create_skill_registry


class HarnessEngine:
    """실시간 하네스 루프 엔진. 매 단계마다 콜백을 호출한다."""

    def __init__(self, data_path="data/graph_data.json", db_path="kuzu_v3_live"):
        self.data_path = data_path
        self.db_path = db_path
        self.db = None
        self.conn = None
        self.agents = []
        self.moderator = None
        self.skill_registry = None
        self.raw = None

        # State
        self.iteration = 0
        self.max_iterations = 10
        self.convergence_threshold = 0.3
        self.running = False
        self.paused = False
        self.speed = 1.0  # 1.0 = normal, 0.5 = fast, 2.0 = slow
        self.history = []
        self.initial_metrics = None
        self.current_metrics = None

        # Event callback
        self._listeners = []

    def add_listener(self, fn):
        self._listeners.append(fn)

    def remove_listener(self, fn):
        if fn in self._listeners:
            self._listeners.remove(fn)

    async def _emit(self, event_type, data):
        for fn in self._listeners:
            try:
                await fn(event_type, data)
            except Exception:
                pass

    # ── INIT ──────────────────────────────────────────────

    async def initialize(self):
        """DB와 에이전트를 초기화한다."""
        with open(self.data_path) as f:
            self.raw = json.load(f)

        for p in [self.db_path, self.db_path + ".wal", self.db_path + ".lock"]:
            if os.path.exists(p):
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
        self.db = kuzu.Database(self.db_path)
        self.conn = kuzu.Connection(self.db)

        self._create_schema()
        self._populate_base()

        self.agents = create_agents()
        self.moderator = Moderator()
        self.skill_registry = create_skill_registry()
        Proposal._counter = 0

        self.iteration = 0
        self.history = []
        self.running = False
        self.paused = False

        gm = self.skill_registry.execute("graph_metrics", self.conn, {}, "system")
        self.initial_metrics = gm["metrics"]
        self.current_metrics = dict(self.initial_metrics)

        await self._emit("initialized", {
            "agents": [{"name": a.name, "role": a.ROLE, "description": a.DESCRIPTION} for a in self.agents],
            "skills": self.skill_registry.list_skills(),
            "initial_metrics": self.initial_metrics,
            "graph": self.raw,
        })

    def _create_schema(self):
        c = self.conn
        c.execute("CREATE NODE TABLE ProcessArea (id STRING, name STRING, color STRING, cycle_time INT64, step_count INT64, takt_time DOUBLE DEFAULT 0.0, PRIMARY KEY(id))")
        c.execute("CREATE NODE TABLE ProcessStep (id STRING, name STRING, area_id STRING, cycle_time INT64, yield_rate DOUBLE, automation STRING, equipment STRING, equip_cost INT64, operators INT64, safety_level STRING, oee DOUBLE DEFAULT 0.85, sigma_level DOUBLE DEFAULT 3.0, PRIMARY KEY(id))")
        c.execute("CREATE NODE TABLE Equipment (id STRING, name STRING, cost INT64, mtbf_hours DOUBLE DEFAULT 2000.0, mttr_hours DOUBLE DEFAULT 4.0, PRIMARY KEY(id))")
        c.execute("CREATE NODE TABLE Material (id STRING, name STRING, category STRING, cost DOUBLE, supplier STRING, lead_time_days INT64 DEFAULT 7, PRIMARY KEY(id))")
        c.execute("CREATE NODE TABLE QualitySpec (id STRING, name STRING, type STRING, unit STRING, min_val DOUBLE, max_val DOUBLE, PRIMARY KEY(id))")
        c.execute("CREATE NODE TABLE DefectMode (id STRING, name STRING, category STRING, severity INT64, occurrence INT64, detection INT64, rpn INT64, PRIMARY KEY(id))")
        c.execute("CREATE NODE TABLE AutomationPlan (id STRING, name STRING, from_level STRING, to_level STRING, investment INT64, expected_yield_gain DOUBLE, expected_cycle_reduction INT64, PRIMARY KEY(id))")
        c.execute("CREATE NODE TABLE MaintenancePlan (id STRING, name STRING, strategy STRING, interval_hours INT64, cost_per_event INT64, PRIMARY KEY(id))")
        for rel in [
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
        ]:
            c.execute(rel)

    def _populate_base(self):
        c, raw = self.conn, self.raw
        equip_map = {}
        for a in raw["areas"]:
            c.execute("CREATE (pa:ProcessArea {id:$id,name:$name,color:$color,cycle_time:$ct,step_count:$sc,takt_time:$tt})",
                      {"id": a["id"], "name": a["name"], "color": a["color"], "ct": a["cycle"], "sc": a["steps"], "tt": round(a["cycle"]/a["steps"],2)})
        for s in raw["steps"]:
            sigma = 3.0 + (s["yield_rate"] - 0.98) * 100
            c.execute("CREATE (ps:ProcessStep {id:$id,name:$name,area_id:$area,cycle_time:$ct,yield_rate:$yr,automation:$auto,equipment:$eq,equip_cost:$ec,operators:$op,safety_level:$sl,oee:$oee,sigma_level:$sig})",
                      {"id":s["id"],"name":s["name"],"area":s["area"],"ct":s["cycle"],"yr":s["yield_rate"],"auto":s["auto"],"eq":s["equipment"],"ec":s["equip_cost"],"op":s["operators"],"sl":s["safety"],"oee":round(0.75+s["yield_rate"]*0.1,3),"sig":round(sigma,2)})
        for i, s in enumerate(raw["steps"]):
            eid = f"EQ-{i+1:03d}"
            if s["equipment"] not in equip_map:
                equip_map[s["equipment"]] = eid
                c.execute("CREATE (e:Equipment {id:$id,name:$name,cost:$cost,mtbf_hours:$mtbf,mttr_hours:$mttr})",
                          {"id":eid,"name":s["equipment"],"cost":s["equip_cost"],"mtbf":round(1500+s["equip_cost"]/100),"mttr":round(4+s["equip_cost"]/200000,1)})
        mat_seen = set()
        for m in raw["materials"]:
            if m["mat_id"] not in mat_seen:
                mat_seen.add(m["mat_id"])
                c.execute("CREATE (m:Material {id:$id,name:$name,category:$cat,cost:$cost,supplier:$sup,lead_time_days:7})",
                          {"id":m["mat_id"],"name":m["mat_name"],"cat":m["category"],"cost":m["cost"],"sup":m["supplier"]})
        qs_seen = set()
        for q in raw["quality"]:
            if q["spec_id"] not in qs_seen:
                qs_seen.add(q["spec_id"])
                c.execute("CREATE (q:QualitySpec {id:$id,name:$name,type:$type,unit:$unit,min_val:$mn,max_val:$mx})",
                          {"id":q["spec_id"],"name":q["spec_name"],"type":q["type"],"unit":q["unit"],"mn":q["min"],"mx":q["max"]})
        for e in raw["edges"]:
            c.execute(f"MATCH (a:ProcessStep),(b:ProcessStep) WHERE a.id=$s AND b.id=$t CREATE (a)-[:{e['type']}]->(b)", {"s":e["source"],"t":e["target"]})
        for s in raw["steps"]:
            c.execute("MATCH (ps:ProcessStep),(pa:ProcessArea) WHERE ps.id=$sid AND pa.id=$aid CREATE (ps)-[:BELONGS_TO]->(pa)", {"sid":s["id"],"aid":s["area"]})
        for s in raw["steps"]:
            eid = equip_map[s["equipment"]]
            c.execute("MATCH (ps:ProcessStep),(eq:Equipment) WHERE ps.id=$sid AND eq.id=$eid CREATE (ps)-[:USES_EQUIPMENT]->(eq)", {"sid":s["id"],"eid":eid})
        for m in raw["materials"]:
            c.execute("MATCH (ps:ProcessStep),(mat:Material) WHERE ps.id=$sid AND mat.id=$mid CREATE (ps)-[:CONSUMES {qty:$qty}]->(mat)", {"sid":m["step_id"],"mid":m["mat_id"],"qty":m["qty"]})
        for q in raw["quality"]:
            c.execute("MATCH (ps:ProcessStep),(qs:QualitySpec) WHERE ps.id=$sid AND qs.id=$qid CREATE (ps)-[:REQUIRES_SPEC]->(qs)", {"sid":q["step_id"],"qid":q["spec_id"]})

    # ── SINGLE ITERATION ──────────────────────────────────

    async def run_single_iteration(self):
        """1회 반복을 실행하고, 매 단계마다 이벤트를 발행한다."""
        i = self.iteration
        delay = 0.3 * self.speed

        # ① OBSERVE
        await self._emit("phase", {"iteration": i+1, "phase": "observe", "message": "각 에이전트가 온톨로지를 분석합니다..."})
        await asyncio.sleep(delay)

        gm = self.skill_registry.execute("graph_metrics", self.conn, {}, "system")
        pre_metrics = gm["metrics"]
        all_observations = {}
        for agent in self.agents:
            obs = agent.observe(self.conn, self.skill_registry, pre_metrics)
            all_observations[agent.name] = obs

        await self._emit("observe_done", {
            "iteration": i+1,
            "metrics": pre_metrics,
            "agents": {a.name: {"observed": True} for a in self.agents},
        })
        await asyncio.sleep(delay)

        # ② PROPOSE
        await self._emit("phase", {"iteration": i+1, "phase": "propose", "message": "에이전트들이 개선안을 제안합니다..."})
        await asyncio.sleep(delay)

        all_proposals = []
        agent_proposals = {}
        for agent in self.agents:
            proposals = agent.propose(self.conn, self.skill_registry, all_observations[agent.name], i)
            all_proposals.extend(proposals)
            agent_proposals[agent.name] = len(proposals)

        await self._emit("propose_done", {
            "iteration": i+1,
            "total": len(all_proposals),
            "by_agent": agent_proposals,
            "by_type": self._count_by_type(all_proposals),
        })
        await asyncio.sleep(delay)

        if not all_proposals:
            await self._emit("converged", {"iteration": i+1, "reason": "no_proposals", "metrics": pre_metrics})
            self.running = False
            return

        # ③ DEBATE
        await self._emit("phase", {"iteration": i+1, "phase": "debate", "message": "상호 비평 및 투표 진행 중..."})
        await asyncio.sleep(delay)

        approved, debate_log = self.moderator.run_debate(self.agents, all_proposals, all_observations)
        sorted_votes = sorted(debate_log["vote_summary"], key=lambda x: -x["score"])

        await self._emit("debate_done", {
            "iteration": i+1,
            "total_proposals": debate_log["total_proposals"],
            "critiques": len(debate_log["critiques"]),
            "approved_count": len(approved),
            "rejected_count": len(debate_log["rejected"]),
            "top_votes": sorted_votes[:10],
            "threshold": self.moderator.APPROVAL_THRESHOLD,
        })
        await asyncio.sleep(delay)

        if not approved:
            await self._emit("phase", {"iteration": i+1, "phase": "skip", "message": "승인된 제안 없음"})
            self.iteration += 1
            return

        # ④ APPLY
        await self._emit("phase", {"iteration": i+1, "phase": "apply", "message": f"승인된 {len(approved)}건을 적용합니다..."})
        await asyncio.sleep(delay)

        applied_count = 0
        failed_count = 0
        applied_details = []
        for p in approved:
            result = self.skill_registry.execute(p.skill_name, self.conn, p.params, p.agent_name)
            if result.get("success"):
                p.status = "applied"
                applied_count += 1
                applied_details.append({"id": p.id, "action": p.action_type, "skill": p.skill_name, "agent": p.agent_name, "status": "applied"})
            else:
                p.status = "failed"
                failed_count += 1
                applied_details.append({"id": p.id, "action": p.action_type, "skill": p.skill_name, "agent": p.agent_name, "status": "failed", "error": result.get("error","")})

        await self._emit("apply_done", {
            "iteration": i+1,
            "applied": applied_count,
            "failed": failed_count,
            "details": applied_details,
        })
        await asyncio.sleep(delay)

        # ⑤ EVALUATE
        await self._emit("phase", {"iteration": i+1, "phase": "evaluate", "message": "개선 효과를 측정합니다..."})
        await asyncio.sleep(delay)

        gm_post = self.skill_registry.execute("graph_metrics", self.conn, {}, "system")
        post_metrics = gm_post["metrics"]
        evaluation = self._evaluate(pre_metrics, post_metrics, i)

        await self._emit("evaluate_done", {
            "iteration": i+1,
            "pre": pre_metrics,
            "post": post_metrics,
            "evaluation": evaluation,
        })
        await asyncio.sleep(delay)

        # ⑥ LEARN
        await self._emit("phase", {"iteration": i+1, "phase": "learn", "message": "에이전트 신뢰도를 업데이트합니다..."})
        await asyncio.sleep(delay)

        learning_log = self._learn(approved, pre_metrics, post_metrics)
        agent_states = [{"name": a.name, "role": a.ROLE, "trust": round(a.trust_score, 3),
                         "success_rate": round(a.success_count / max(a.success_count + a.fail_count, 1), 3),
                         "proposals": len(a.proposal_history)} for a in self.agents]

        await self._emit("learn_done", {
            "iteration": i+1,
            "learning_log": learning_log,
            "agents": agent_states,
        })

        # ⑦ ITERATION COMPLETE
        self.current_metrics = post_metrics
        self.iteration += 1
        self.history.append({
            "iteration": self.iteration,
            "pre": pre_metrics, "post": post_metrics,
            "proposals": len(all_proposals), "approved": len(approved),
            "applied": applied_count, "failed": failed_count,
            "evaluation": evaluation,
            "trust": {a.name: round(a.trust_score, 3) for a in self.agents},
        })

        # Get updated step data for process visualization
        steps_data = self._get_current_steps()

        await self._emit("iteration_complete", {
            "iteration": self.iteration,
            "metrics": post_metrics,
            "evaluation": evaluation,
            "agents": agent_states,
            "skills": self.skill_registry.get_stats(),
            "steps": steps_data,
            "converged": evaluation["converged"],
        })

        if evaluation["converged"]:
            await self._emit("converged", {"iteration": self.iteration, "reason": "threshold", "metrics": post_metrics})
            self.running = False

    def _get_current_steps(self):
        """현재 공정 스텝 상태를 쿼리한다."""
        r = self.conn.execute("MATCH (ps:ProcessStep) RETURN ps.id, ps.name, ps.area_id, ps.yield_rate, ps.automation, ps.oee, ps.cycle_time, ps.safety_level, ps.equipment, ps.sigma_level")
        steps = []
        while r.has_next():
            row = r.get_next()
            steps.append({"id":row[0],"name":row[1],"area":row[2],"yield":round(float(row[3]),4),"auto":row[4],"oee":round(float(row[5]),3),"cycle":int(row[6]),"safety":row[7],"equipment":row[8],"sigma":round(float(row[9]),2)})
        return steps

    def _count_by_type(self, proposals):
        counts = defaultdict(int)
        for p in proposals:
            counts[p.action_type] += 1
        return dict(counts)

    def _evaluate(self, prev, curr, iteration):
        deltas = {}
        for key, label in [("total_nodes","노드"),("total_edges","엣지"),("density","밀도"),
                           ("spec_coverage","품질커버리지"),("material_coverage","자재커버리지"),
                           ("defect_coverage","결함커버리지"),("maintenance_coverage","보전커버리지"),
                           ("inspection_coverage","검사커버리지"),("cross_area_edges","영역간연결"),
                           ("line_yield","라인수율"),("avg_oee","OEE"),("avg_sigma","시그마"),
                           ("completeness_score","완성도")]:
            p = prev.get(key, 0)
            c = curr.get(key, 0)
            change = c - p if isinstance(c, (int, float)) else 0
            pct = round((change / p * 100), 1) if p else 0
            deltas[key] = {"label": label, "prev": round(p,4) if isinstance(p,float) else p,
                           "curr": round(c,4) if isinstance(c,float) else c,
                           "change": round(change,4), "pct": pct, "improved": change > 0}
        improved = sum(1 for d in deltas.values() if d["improved"])
        score_delta = deltas["completeness_score"]["change"]
        return {"deltas": deltas, "improvement_rate": round(improved/len(deltas)*100,1),
                "converged": abs(score_delta) < self.convergence_threshold and iteration > 2,
                "score_delta": round(score_delta, 2)}

    def _learn(self, approved, pre, post):
        score_change = post.get("completeness_score",0) - pre.get("completeness_score",0)
        agent_map = {a.name: a for a in self.agents}
        contrib = defaultdict(lambda: {"applied":0,"success":0})
        for p in approved:
            contrib[p.agent_name]["applied"] += 1
            if p.status == "applied":
                contrib[p.agent_name]["success"] += 1
        overall_improved = score_change > 0
        log = []
        for a in self.agents:
            c = contrib[a.name]
            if c["applied"] == 0:
                continue
            sr = c["success"] / max(c["applied"],1)
            if overall_improved and sr > 0.5:
                delta = round(0.05 * sr, 3)
                a.update_trust(delta)
                a.record_result(True)
                log.append({"agent":a.name,"delta":delta,"trust":round(a.trust_score,3),"reason":f"개선 기여 (성공률 {sr:.0%})"})
            elif not overall_improved:
                a.update_trust(-0.03)
                a.record_result(False)
                log.append({"agent":a.name,"delta":-0.03,"trust":round(a.trust_score,3),"reason":f"개선 미달 (Δ{score_change:+.1f})"})
        return log

    # ── AUTO RUN ──────────────────────────────────────────

    async def run_loop(self):
        """전체 루프를 자동으로 실행한다."""
        self.running = True
        await self._emit("loop_started", {"max_iterations": self.max_iterations})

        while self.running and self.iteration < self.max_iterations:
            if self.paused:
                await asyncio.sleep(0.5)
                continue
            await self.run_single_iteration()
            await asyncio.sleep(0.2 * self.speed)

        self.running = False
        overall = self._evaluate(self.initial_metrics, self.current_metrics, self.iteration)
        await self._emit("loop_finished", {
            "total_iterations": self.iteration,
            "initial": self.initial_metrics,
            "final": self.current_metrics,
            "overall": overall,
            "agents": [{"name":a.name,"trust":round(a.trust_score,3),"role":a.ROLE} for a in self.agents],
            "skills": self.skill_registry.get_stats(),
            "history": self.history,
        })

    def get_state(self):
        """현재 엔진 상태를 반환한다."""
        return {
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "running": self.running,
            "paused": self.paused,
            "speed": self.speed,
            "metrics": self.current_metrics,
            "initial_metrics": self.initial_metrics,
            "agents": [{"name":a.name,"role":a.ROLE,"description":a.DESCRIPTION,
                        "trust":round(a.trust_score,3),
                        "success_rate":round(a.success_count/max(a.success_count+a.fail_count,1),3),
                        "proposals":len(a.proposal_history)} for a in self.agents] if self.agents else [],
            "skills": self.skill_registry.get_stats() if self.skill_registry else {},
            "history": self.history,
        }
