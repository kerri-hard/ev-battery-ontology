"""
Agents — 전문 에이전트 시스템
각 에이전트는 고유한 관점에서 온톨로지를 분석하고, 개선안을 제안하며, 다른 에이전트의 제안을 비평한다.
"""
import random
from collections import defaultdict

random.seed(42)


class Proposal:
    """에이전트가 제안하는 개선안."""

    _counter = 0

    def __init__(self, agent_name, action_type, skill_name, params,
                 reason, priority, expected_impact):
        Proposal._counter += 1
        self.id = f"P-{Proposal._counter:04d}"
        self.agent_name = agent_name
        self.action_type = action_type  # ADD_DEFECT, ADD_SPEC, UPGRADE, etc.
        self.skill_name = skill_name    # 실행할 스킬 이름
        self.params = params            # 스킬 파라미터
        self.reason = reason
        self.priority = priority        # CRITICAL, HIGH, MEDIUM, LOW
        self.expected_impact = expected_impact
        self.critiques = []             # 다른 에이전트의 비평
        self.votes = {}                 # agent_name → score (-2 ~ +2)
        self.final_score = 0.0
        self.status = "proposed"        # proposed → approved/rejected → applied/failed

    def to_dict(self):
        return {
            "id": self.id, "agent": self.agent_name,
            "action": self.action_type, "skill": self.skill_name,
            "params": self.params, "reason": self.reason,
            "priority": self.priority, "expected_impact": self.expected_impact,
            "critiques": self.critiques,
            "votes": self.votes, "final_score": self.final_score,
            "status": self.status,
        }


class BaseAgent:
    """에이전트 기본 클래스."""

    ROLE = "base"
    DESCRIPTION = ""
    SKILLS = []  # 사용 가능한 스킬 목록

    def __init__(self, name=None):
        self.name = name or self.ROLE
        self.trust_score = 1.0           # 신뢰도 (0.0 ~ 2.0)
        self.proposal_history = []       # 제안 이력
        self.success_count = 0
        self.fail_count = 0

    def observe(self, conn, skill_registry, metrics):
        """① 관찰: 자신의 관점에서 온톨로지를 분석한다."""
        raise NotImplementedError

    def propose(self, conn, skill_registry, observations, iteration):
        """② 제안: 관찰 결과를 바탕으로 개선안을 제안한다."""
        raise NotImplementedError

    def critique(self, proposal, own_observations):
        """③ 비평: 다른 에이전트의 제안을 평가한다."""
        raise NotImplementedError

    def vote(self, proposal, own_observations):
        """④ 투표: 제안에 점수를 매긴다 (-2 ~ +2)."""
        raise NotImplementedError

    def update_trust(self, delta):
        self.trust_score = max(0.1, min(2.0, self.trust_score + delta))

    def record_result(self, success):
        if success:
            self.success_count += 1
        else:
            self.fail_count += 1

    def stats(self):
        total = self.success_count + self.fail_count
        return {
            "name": self.name, "role": self.ROLE,
            "trust": round(self.trust_score, 3),
            "proposals": len(self.proposal_history),
            "success_rate": round(self.success_count / max(total, 1), 3),
        }


# ═══════════════════════════════════════════════════════════════
#  SPECIALIST AGENTS
# ═══════════════════════════════════════════════════════════════

class ProcessAnalyst(BaseAgent):
    """공정 흐름/병목/사이클타임 전문가."""

    ROLE = "process_analyst"
    DESCRIPTION = "공정 흐름 분석, 병목 식별, 사이클타임 최적화"
    SKILLS = ["bottleneck_analysis", "graph_metrics", "add_rework_link", "cross_dependency_mapping"]

    def observe(self, conn, skill_registry, metrics):
        bn = skill_registry.execute("bottleneck_analysis", conn, {"yield_threshold": 0.995}, self.name)
        return {"bottlenecks": bn.get("bottlenecks", []), "metrics": metrics}

    def propose(self, conn, skill_registry, observations, iteration):
        proposals = []
        bottlenecks = observations.get("bottlenecks", [])

        # 재작업 경로 추가 제안
        for bn in bottlenecks:
            if bn["yield"] < 0.995:
                proposals.append(Proposal(
                    agent_name=self.name,
                    action_type="ADD_REWORK_LINK",
                    skill_name="add_rework_link",
                    params={"step_id": bn["id"]},
                    reason=f"[공정분석] '{bn['name']}' 수율 {bn['yield']:.1%} — 재작업 경로 필요",
                    priority="HIGH",
                    expected_impact=0.5,
                ))

        # 영역 간 의존성 매핑
        metrics = observations.get("metrics", {})
        if metrics.get("cross_area_edges", 0) < 8:
            proposals.append(Proposal(
                agent_name=self.name,
                action_type="ADD_CROSS_DEPENDENCY",
                skill_name="cross_dependency_mapping",
                params={},
                reason=f"[공정분석] 영역 간 의존성 부족 ({metrics.get('cross_area_edges', 0)}개) — 매핑 필요",
                priority="MEDIUM",
                expected_impact=0.4 * 3,
            ))

        self.proposal_history.extend(proposals)
        return proposals

    def critique(self, proposal, own_observations):
        if proposal.action_type == "AUTOMATION_UPGRADE":
            # 자동화 업그레이드가 병목에 해당하는지 검증
            bns = {b["id"] for b in own_observations.get("bottlenecks", [])}
            step = proposal.params.get("step_id", "")
            if step in bns:
                return {"support": True, "comment": f"병목 공정({step}) 자동화 지지 — 수율 개선 기대"}
            return {"support": False, "comment": f"{step}은 현재 병목 아님 — 다른 공정 우선 추천"}
        return {"support": True, "comment": "해당 영역 외 — 중립"}

    def vote(self, proposal, own_observations):
        bns = {b["id"] for b in own_observations.get("bottlenecks", [])}
        if proposal.params.get("step_id", "") in bns:
            return 2  # 병목 관련이면 강력 지지
        if proposal.action_type in ("ADD_REWORK_LINK", "ADD_CROSS_DEPENDENCY"):
            return 1
        return 0


class QualityEngineer(BaseAgent):
    """품질 기준/결함 모드/FMEA 전문가."""

    ROLE = "quality_engineer"
    DESCRIPTION = "FMEA 분석, 품질 기준 관리, 결함 모드 식별"
    SKILLS = ["coverage_analysis", "add_defect_fmea", "add_quality_spec", "add_inspection_link"]

    def observe(self, conn, skill_registry, metrics):
        cov = skill_registry.execute("coverage_analysis", conn, {}, self.name)
        return {"gaps": cov.get("gaps", {}), "total_gaps": cov.get("total_gaps", 0)}

    def propose(self, conn, skill_registry, observations, iteration):
        proposals = []
        gaps = observations.get("gaps", {})

        # FMEA 결함모드 추가
        for step in gaps.get("defect_missing", []):
            proposals.append(Proposal(
                agent_name=self.name,
                action_type="ADD_DEFECT_FMEA",
                skill_name="add_defect_fmea",
                params={"step_id": step["id"], "automation": step.get("auto", "자동")},
                reason=f"[품질] '{step['name']}' FMEA 결함모드 미분석 (수율 {step.get('yield', 0):.1%})",
                priority="HIGH" if step.get("yield", 1) < 0.995 else "MEDIUM",
                expected_impact=0.8 * 3,
            ))

        # 품질기준 추가
        for step in gaps.get("spec_missing", []):
            proposals.append(Proposal(
                agent_name=self.name,
                action_type="ADD_QUALITY_SPEC",
                skill_name="add_quality_spec",
                params={"step_id": step["id"], "automation": step.get("auto", "자동")},
                reason=f"[품질] '{step['name']}' 품질기준 누락",
                priority="HIGH",
                expected_impact=0.7 * 2,
            ))

        # 검사 연결 추가
        for step in gaps.get("inspection_missing", []):
            proposals.append(Proposal(
                agent_name=self.name,
                action_type="ADD_INSPECTION_LINK",
                skill_name="add_inspection_link",
                params={"step_id": step["id"]},
                reason=f"[품질] '{step['name']}' 검사 연결 없음 (수율 {step.get('yield', 0):.1%})",
                priority="HIGH",
                expected_impact=0.6,
            ))

        self.proposal_history.extend(proposals)
        return proposals

    def critique(self, proposal, own_observations):
        if proposal.action_type == "YIELD_IMPROVEMENT":
            return {"support": True, "comment": "수율 개선은 품질에 직접 기여 — 지지"}
        if proposal.action_type == "AUTOMATION_UPGRADE":
            return {"support": True, "comment": "자동화는 인적오류 감소 — 품질 향상 기대"}
        return {"support": True, "comment": "중립"}

    def vote(self, proposal, own_observations):
        if proposal.action_type in ("ADD_DEFECT_FMEA", "ADD_QUALITY_SPEC", "ADD_INSPECTION_LINK"):
            return 2
        if proposal.action_type in ("YIELD_IMPROVEMENT", "AUTOMATION_UPGRADE"):
            return 1
        return 0


class MaintenanceEngineer(BaseAgent):
    """설비 보전/예지정비 전문가."""

    ROLE = "maintenance_engineer"
    DESCRIPTION = "설비 보전 계획, MTBF/MTTR 분석, 예지정비"
    SKILLS = ["coverage_analysis", "add_maintenance_plan", "graph_metrics"]

    def observe(self, conn, skill_registry, metrics):
        cov = skill_registry.execute("coverage_analysis", conn, {}, self.name)
        return {"maint_gaps": cov.get("gaps", {}).get("maintenance_missing", []),
                "maintenance_coverage": metrics.get("maintenance_coverage", 0)}

    def propose(self, conn, skill_registry, observations, iteration):
        proposals = []
        if iteration < 2:
            return proposals  # 보전 계획은 iteration 2부터
        for eq in observations.get("maint_gaps", []):
            proposals.append(Proposal(
                agent_name=self.name,
                action_type="ADD_MAINTENANCE",
                skill_name="add_maintenance_plan",
                params={
                    "equip_id": eq["id"], "equip_name": eq["name"],
                    "equip_cost": eq["cost"],
                },
                reason=f"[보전] '{eq['name']}' 보전계획 미수립 (MTBF: {eq['mtbf']}h, 투자: {eq['cost']:,})",
                priority="HIGH" if eq["cost"] > 200000 else "MEDIUM",
                expected_impact=0.8,
            ))
        self.proposal_history.extend(proposals)
        return proposals

    def critique(self, proposal, own_observations):
        if proposal.action_type == "AUTOMATION_UPGRADE":
            return {"support": True, "comment": "자동화 장비에 대한 보전계획 연계 필요 — 조건부 지지"}
        return {"support": True, "comment": "중립"}

    def vote(self, proposal, own_observations):
        if proposal.action_type == "ADD_MAINTENANCE":
            return 2
        if proposal.action_type == "AUTOMATION_UPGRADE":
            return 1  # 장비 교체 → 보전 필요
        return 0


class AutomationArchitect(BaseAgent):
    """자동화/OEE 최적화 전문가."""

    ROLE = "automation_architect"
    DESCRIPTION = "자동화 업그레이드, OEE 최적화, 투자 ROI 분석"
    SKILLS = ["bottleneck_analysis", "automation_upgrade", "cost_benefit_analysis", "yield_improvement"]

    def observe(self, conn, skill_registry, metrics):
        bn = skill_registry.execute("bottleneck_analysis", conn, {"yield_threshold": 0.995}, self.name)
        cba = skill_registry.execute("cost_benefit_analysis", conn, {}, self.name)
        return {
            "bottlenecks": bn.get("bottlenecks", []),
            "cost_analyses": cba.get("analyses", []),
            "auto_dist": metrics.get("automation_distribution", {}),
        }

    def propose(self, conn, skill_registry, observations, iteration):
        proposals = []
        if iteration < 1:
            return proposals

        # ROI 기반 자동화 업그레이드 제안
        for analysis in observations.get("cost_analyses", [])[:3]:
            if analysis["recommended"]:
                auto = analysis["automation"]
                target = "반자동" if auto == "수동" else "자동"
                proposals.append(Proposal(
                    agent_name=self.name,
                    action_type="AUTOMATION_UPGRADE",
                    skill_name="automation_upgrade",
                    params={
                        "step_id": analysis["step_id"],
                        "step_name": analysis["step_name"],
                        "from_level": auto, "to_level": target,
                    },
                    reason=f"[자동화] '{analysis['step_name']}' {auto}→{target} "
                           f"(ROI: {analysis['roi_months']}개월, 투자: {analysis['investment']:,})",
                    priority="CRITICAL",
                    expected_impact=2.0,
                ))

        # 수율 개선 시뮬레이션 (iteration 3부터)
        if iteration >= 3:
            for bn in observations.get("bottlenecks", [])[:3]:
                proposals.append(Proposal(
                    agent_name=self.name,
                    action_type="YIELD_IMPROVEMENT",
                    skill_name="yield_improvement",
                    params={"step_id": bn["id"]},
                    reason=f"[자동화] '{bn['name']}' 수율 개선 목표 {bn['yield']:.1%} → +0.3%",
                    priority="CRITICAL",
                    expected_impact=0.3,
                ))

        self.proposal_history.extend(proposals)
        return proposals

    def critique(self, proposal, own_observations):
        if proposal.action_type == "ADD_MAINTENANCE":
            return {"support": True, "comment": "보전계획은 OEE 유지에 필수 — 강력 지지"}
        if proposal.action_type == "ADD_QUALITY_SPEC":
            return {"support": True, "comment": "품질기준은 자동화 전제조건 — 지지"}
        return {"support": True, "comment": "중립"}

    def vote(self, proposal, own_observations):
        if proposal.action_type in ("AUTOMATION_UPGRADE", "YIELD_IMPROVEMENT"):
            return 2
        if proposal.action_type == "ADD_MAINTENANCE":
            return 1
        return 0


class SupplyChainAnalyst(BaseAgent):
    """자재/공급망 전문가."""

    ROLE = "supply_chain_analyst"
    DESCRIPTION = "자재 연결, 공급망 리스크, 비용 분석"
    SKILLS = ["coverage_analysis", "add_material_link", "cost_benefit_analysis"]

    def observe(self, conn, skill_registry, metrics):
        cov = skill_registry.execute("coverage_analysis", conn, {}, self.name)
        return {"material_gaps": cov.get("gaps", {}).get("material_missing", []),
                "material_coverage": metrics.get("material_coverage", 0)}

    def propose(self, conn, skill_registry, observations, iteration):
        proposals = []
        for step in observations.get("material_gaps", []):
            if step["id"] in self._get_material_templates():
                proposals.append(Proposal(
                    agent_name=self.name,
                    action_type="ADD_MATERIAL_LINK",
                    skill_name="add_material_link",
                    params={"step_id": step["id"]},
                    reason=f"[공급망] '{step['name']}' 자재 정보 누락 — BOM 완성 필요",
                    priority="MEDIUM",
                    expected_impact=0.5,
                ))
        self.proposal_history.extend(proposals)
        return proposals

    def _get_material_templates(self):
        from .skills import MATERIAL_TEMPLATES
        return MATERIAL_TEMPLATES

    def critique(self, proposal, own_observations):
        if proposal.action_type == "AUTOMATION_UPGRADE":
            invest = proposal.params.get("investment", 0)
            if invest > 100000:
                return {"support": False, "comment": f"투자 {invest:,} — 비용 대비 효과 검증 필요"}
        return {"support": True, "comment": "중립"}

    def vote(self, proposal, own_observations):
        if proposal.action_type == "ADD_MATERIAL_LINK":
            return 2
        if proposal.action_type == "ADD_CROSS_DEPENDENCY":
            return 1  # 공급망 가시성 향상
        if proposal.action_type == "AUTOMATION_UPGRADE":
            return -1  # 비용 우려
        return 0


class SafetyAuditor(BaseAgent):
    """안전/위험 평가 전문가."""

    ROLE = "safety_auditor"
    DESCRIPTION = "안전 위험도 평가, 안전등급 관리, 리스크 감소"
    SKILLS = ["safety_risk_assessment", "graph_metrics"]

    def observe(self, conn, skill_registry, metrics):
        risk = skill_registry.execute("safety_risk_assessment", conn, {}, self.name)
        return {"risks": risk.get("risks", [])}

    def propose(self, conn, skill_registry, observations, iteration):
        # 안전 에이전트는 직접 변경을 제안하지 않지만,
        # 고위험 공정의 자동화/검사 강화를 지지한다
        return []

    def critique(self, proposal, own_observations):
        high_risk_steps = {
            r["step_id"] for r in own_observations.get("risks", [])
            if r["risk_score"] >= 10
        }
        step = proposal.params.get("step_id", "")
        if step in high_risk_steps:
            if proposal.action_type == "AUTOMATION_UPGRADE":
                return {"support": True, "comment": f"고위험 공정({step}) 자동화 — 안전 필수 조치, 강력 지지"}
            if proposal.action_type in ("ADD_QUALITY_SPEC", "ADD_INSPECTION_LINK"):
                return {"support": True, "comment": f"고위험 공정 품질 강화 — 안전 지지"}
        return {"support": True, "comment": "안전 영향 없음 — 중립"}

    def vote(self, proposal, own_observations):
        high_risk_steps = {
            r["step_id"] for r in own_observations.get("risks", [])
            if r["risk_score"] >= 10
        }
        step = proposal.params.get("step_id", "")
        if step in high_risk_steps:
            if proposal.action_type in ("AUTOMATION_UPGRADE", "ADD_INSPECTION_LINK"):
                return 2  # 고위험 공정 자동화/검사 = 안전 최우선
            return 1
        return 0


# ═══════════════════════════════════════════════════════════════
#  MODERATOR — 토론 진행자, 최종 결정권
# ═══════════════════════════════════════════════════════════════

class Moderator:
    """토론을 진행하고, 투표를 집계하며, 최종 승인/거부를 결정한다."""

    APPROVAL_THRESHOLD = 2.0   # 이 점수 이상이면 승인
    MAX_PROPOSALS_PER_ROUND = 15  # 한 라운드 최대 적용 수

    def __init__(self):
        self.debate_log = []

    def run_debate(self, agents, all_proposals, all_observations):
        """
        토론 프로토콜:
        1. 모든 제안 수집
        2. 각 에이전트가 다른 에이전트의 제안을 비평
        3. 각 에이전트가 모든 제안에 투표
        4. 신뢰도 가중 점수로 최종 결정
        """
        round_log = {
            "total_proposals": len(all_proposals),
            "critiques": [],
            "vote_summary": [],
            "approved": [],
            "rejected": [],
        }

        if not all_proposals:
            self.debate_log.append(round_log)
            return [], round_log

        # ── Phase 1: CRITIQUE ──
        for proposal in all_proposals:
            for agent in agents:
                if agent.name == proposal.agent_name:
                    continue
                obs = all_observations.get(agent.name, {})
                critique = agent.critique(proposal, obs)
                proposal.critiques.append({
                    "agent": agent.name,
                    "support": critique["support"],
                    "comment": critique["comment"],
                })
                round_log["critiques"].append({
                    "proposal": proposal.id,
                    "critic": agent.name,
                    "support": critique["support"],
                    "comment": critique["comment"],
                })

        # ── Phase 2: VOTE ──
        for proposal in all_proposals:
            for agent in agents:
                obs = all_observations.get(agent.name, {})
                raw_vote = agent.vote(proposal, obs)
                # 신뢰도 가중
                weighted_vote = raw_vote * agent.trust_score
                proposal.votes[agent.name] = round(weighted_vote, 2)

            # 총점 계산
            proposal.final_score = round(sum(proposal.votes.values()), 2)
            round_log["vote_summary"].append({
                "proposal": proposal.id, "action": proposal.action_type,
                "agent": proposal.agent_name, "score": proposal.final_score,
                "votes": dict(proposal.votes),
            })

        # ── Phase 3: DECIDE ──
        # 점수 순 정렬
        sorted_proposals = sorted(all_proposals, key=lambda p: -p.final_score)

        approved = []
        seen_targets = set()  # 같은 대상에 중복 적용 방지

        for p in sorted_proposals:
            if len(approved) >= self.MAX_PROPOSALS_PER_ROUND:
                p.status = "deferred"
                continue

            target_key = f"{p.action_type}:{p.params.get('step_id', p.params.get('equip_id', 'n/a'))}"

            if p.final_score >= self.APPROVAL_THRESHOLD and target_key not in seen_targets:
                p.status = "approved"
                approved.append(p)
                seen_targets.add(target_key)
                round_log["approved"].append(p.to_dict())
            else:
                p.status = "rejected"
                round_log["rejected"].append({
                    "id": p.id, "action": p.action_type,
                    "score": p.final_score, "reason": "점수 미달" if p.final_score < self.APPROVAL_THRESHOLD else "중복 대상",
                })

        self.debate_log.append(round_log)
        return approved, round_log


def create_agents():
    """전체 에이전트 팀을 생성한다."""
    return [
        ProcessAnalyst(),
        QualityEngineer(),
        MaintenanceEngineer(),
        AutomationArchitect(),
        SupplyChainAnalyst(),
        SafetyAuditor(),
    ]
