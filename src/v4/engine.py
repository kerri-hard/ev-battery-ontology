"""
SelfHealingEngine --- v4 자율 복구 엔진
=========================================
v3 온톨로지 개선 루프(OBSERVE→PROPOSE→DEBATE→APPLY→EVALUATE→LEARN) 위에
실시간 자율 복구 루프(SENSE→DETECT→DIAGNOSE→RECOVER→VERIFY→LEARN)를 추가한다.

페이즈 로직은 `v4/phases/*.py`에, HITL 정책은 `_engine_hitl.py`에,
상태/영속화는 `_engine_state.py`에 분리되어 있다. 본 모듈은 오케스트레이션만 담당.
"""
import asyncio
import os
import traceback
from datetime import datetime

from v3.engine import HarnessEngine
from v4.sensor_simulator import SensorSimulator, extend_schema_l2
from v4.healing_agents import (
    AnomalyDetector,
    RootCauseAnalyzer,
    AutoRecoveryAgent,
    ResilienceOrchestrator,
)
from v4.causal import extend_schema_l3, seed_causal_knowledge, CausalReasoner
from v4.correlation import extend_schema_correlation, CorrelationAnalyzer, CrossProcessInvestigator
from v4.scenarios import ScenarioEngine
from v4.llm_analyst import LLMAnalyst
from v4.llm_agents import PredictiveAgent, NaturalLanguageDiagnoser
from v4.decision_layer import extend_schema_l4, seed_l4_policy, load_active_policy
from v4.isa95 import extend_schema_isa95, seed_default_isa95
from v4.advanced_detection import AdvancedAnomalyDetector
from v4.weibull_rul import WeibullRULEstimator, extend_schema_rul_estimate
from v4.learning_layer import extend_schema_l5
from v4.traceability import extend_schema_traceability, TraceabilityManager
from v4.protocol_bridge import SimulatedBridge
from v4.event_bus import EventBus
from v4.causal_discovery import CausalDiscoveryEngine
from v4.evolution_agent import EvolutionAgent
from v4.llm_orchestrator import LLMOrchestrator

from v4._engine_hitl import HITLMixin
from v4._engine_state import StateMixin
from v4.phases import sense, detect, diagnose, preverify, recover, verify, learn, periodic


class SelfHealingEngine(HITLMixin, StateMixin, HarnessEngine):
    """v4 자율 복구 엔진. v3 온톨로지 개선 + 실시간 이상 감지/진단/복구."""

    def __init__(self, data_path="data/graph_data.json", db_path="kuzu_v4_live", results_dir="results"):
        super().__init__(data_path=data_path, db_path=db_path)

        # Healing-specific agents and state
        self.sensor_sim = None
        self.anomaly_detector = None
        self.advanced_detector = None
        self.root_cause_analyzer = None
        self.auto_recovery = None
        self.resilience = None
        self.causal_reasoner = None
        self.predictive_agent = None
        self.weibull_rul = None
        self.nl_diagnoser = None
        self.traceability = None
        self.sensor_bridge = None
        self.event_bus = None
        self.causal_discovery = None
        self.evolution_agent = None
        self.llm_orchestrator = None
        self.healing_counters = {"reading": 0, "alarm": 0, "incident": 0, "recovery": 0}
        self.healing_history = []
        self.healing_iteration = 0
        self.healing_running = False
        self.results_dir = results_dir
        self.l3_trend_history = []
        self.latest_l3_snapshot = {}
        self.latest_predictive = []
        self.latest_weibull_rul = []
        self.orchestrator_traces = []
        self.hitl_pending = []
        self.hitl_audit = []
        self.hitl_policy = {
            "min_confidence": 0.40,
            "high_risk_threshold": 0.75,
            "medium_requires_history": False,
        }
        # PRE-VERIFY 메타 — 예측 vs 실측 정확도 추적 + 자기 진화하는 임계값
        self._latest_preverify_predictions: dict = {}
        self.preverify_accuracy_history: list = []
        self.preverify_counters = {"plans_total": 0, "auto_rejected_total": 0}
        self.preverify_thresholds = {"A": 1e-4, "B": 0.0, "C": -1e-3}
        # Threshold 시계열 — EvolutionAgent 진화 추적
        self.preverify_thresholds_history: list = []
        # Anti-recurrence — VISION 9.5: 같은 (step, anomaly, cause) 재발 시 다른 액션 강제
        # tracker[(step, anomaly, cause)] = {count, tried_actions: set, last_success: bool}
        self.recurrence_tracker: dict = {}

    # ── INIT ──────────────────────────────────────────────

    async def initialize(self):
        """DB 스키마, 에이전트, 센서 시뮬레이터 초기화."""
        await super().initialize()

        self._extend_schemas()
        self._init_agents()
        self._init_evolution_state()
        self._reset_runtime_state()
        self._load_persisted_policy()

        await self._emit("healing_initialized", {
            "sensor_count": getattr(self.sensor_sim, "sensor_count", 0),
            "agents": _agent_descriptions(self.llm_orchestrator),
        })

    def _extend_schemas(self):
        extend_schema_l2(self.conn)
        extend_schema_l3(self.conn)
        seed_causal_knowledge(self.conn, self.healing_counters)
        extend_schema_l4(self.conn)
        seed_l4_policy(self.conn)
        extend_schema_correlation(self.conn)
        extend_schema_traceability(self.conn)
        extend_schema_rul_estimate(self.conn)
        extend_schema_l5(self.conn)
        # ISA-95 (IEC 62264) 4-level 시작점 — Enterprise/Site/EquipmentClass + 기본 시드
        extend_schema_isa95(self.conn)
        seed_default_isa95(self.conn)

    def _init_agents(self):
        self.sensor_sim = SensorSimulator(self.conn)
        self.anomaly_detector = AnomalyDetector()
        self.advanced_detector = AdvancedAnomalyDetector()
        self.root_cause_analyzer = RootCauseAnalyzer()
        self.auto_recovery = AutoRecoveryAgent()
        self.resilience = ResilienceOrchestrator()
        self.causal_reasoner = CausalReasoner()
        self.correlation_analyzer = CorrelationAnalyzer()
        self.cross_investigator = CrossProcessInvestigator()
        self.scenario_engine = ScenarioEngine(self.sensor_sim)
        self.llm_analyst = LLMAnalyst()
        self.predictive_agent = PredictiveAgent()
        self.weibull_rul = WeibullRULEstimator()
        self.nl_diagnoser = NaturalLanguageDiagnoser()
        self.traceability = TraceabilityManager()
        self.sensor_bridge = SimulatedBridge(self.sensor_sim)
        self.sensor_bridge.connect()
        self.event_bus = EventBus()

        self.causal_discovery = CausalDiscoveryEngine()
        self.llm_orchestrator = LLMOrchestrator()
        self.evolution_agent = EvolutionAgent(evolution_interval=5)
        self.evolution_agent.register_strategies(
            self.conn, self.anomaly_detector, self.causal_reasoner,
            self.correlation_analyzer, self.auto_recovery, self.scenario_engine,
            causal_discovery=self.causal_discovery,
            engine=self,  # PRE-VERIFY threshold 자기 진화에 필요
        )

    def _init_evolution_state(self):
        """L5 LearningRecord 영속 경로 + 재시작 복원."""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._evo_state_path = os.path.join(project_root, "results", "evolution_state.json")
        self._causal_disc_path = os.path.join(project_root, "results", "causal_discovery_state.json")
        if self.evolution_agent.load_state(self._evo_state_path):
            print(f"  [L5] EvolutionAgent 상태 복원: cycle={self.evolution_agent.cycle_count}")
        if self.causal_discovery.load_state(self._causal_disc_path):
            print(f"  [L5] CausalDiscovery 상태 복원: pairs={len(self.causal_discovery.discovered_pairs)}")

    def _reset_runtime_state(self):
        self.healing_counters = {"reading": 0, "alarm": 0, "incident": 0, "recovery": 0}
        self.healing_history = []
        self.healing_iteration = 0
        self.healing_running = False
        self.l3_trend_history = []
        self.latest_l3_snapshot = {}
        self.latest_predictive = []
        self.latest_weibull_rul = []
        self.orchestrator_traces = []
        self.hitl_pending = []
        self.hitl_audit = []
        self.hitl_policy = {
            "min_confidence": 0.40,
            "high_risk_threshold": 0.75,
            "medium_requires_history": False,
        }
        self._latest_preverify_predictions = {}
        self.preverify_accuracy_history = []
        self.preverify_counters = {"plans_total": 0, "auto_rejected_total": 0}
        self.preverify_thresholds = {"A": 1e-4, "B": 0.0, "C": -1e-3}
        self.preverify_thresholds_history = []
        self.recurrence_tracker = {}

    def _load_persisted_policy(self):
        self._load_hitl_runtime_state()
        graph_policy = load_active_policy(self.conn)
        if graph_policy:
            self.hitl_policy.update({
                "min_confidence": graph_policy["min_confidence"],
                "high_risk_threshold": graph_policy["high_risk_threshold"],
                "medium_requires_history": graph_policy["medium_requires_history"],
            })

    # ── SINGLE HEALING ITERATION ──────────────────────────

    async def run_healing_iteration(self):
        """SENSE → DETECT → DIAGNOSE → RECOVER → VERIFY → LEARN 1 사이클."""
        it = self.healing_iteration
        delay = 0.3 * self.speed

        try:
            await sense.maybe_activate_scenario(self, it)
            sense_out = await sense.run(self, it, delay)

            detect_out = await detect.run(self, it, delay, sense_out["readings"])
            anomalies = detect_out["anomalies"]
            if not anomalies:
                return

            diag_out = await diagnose.run(self, it, delay, anomalies)
            pv_out = await preverify.run(self, it, delay, anomalies, diag_out["diagnoses"])
            recover_out = await recover.run(self, it, delay, pv_out["plans"])
            verify_out = await verify.run(
                self, it, delay, recover_out["recovery_results"], anomalies,
            )
            await learn.run(
                self, it, delay, anomalies, diag_out["diagnoses"],
                recover_out["recovery_results"], verify_out["verifications"],
            )

            await self._run_periodic(it, recover_out["recovery_results"])
            # Threshold 시계열 누적 — EvolutionAgent가 변경한 임계값을 매 iter 기록
            self.preverify_thresholds_history.append({
                "iteration": it + 1,
                "A": float(self.preverify_thresholds.get("A", 0.0)),
                "B": float(self.preverify_thresholds.get("B", 0.0)),
                "C": float(self.preverify_thresholds.get("C", 0.0)),
            })
            if len(self.preverify_thresholds_history) > 60:
                self.preverify_thresholds_history = self.preverify_thresholds_history[-60:]
            self._persist_healing_summary()

        except Exception as exc:
            await self._emit("healing_error", {
                "iteration": it + 1,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            })
        finally:
            self.healing_iteration += 1

    async def _run_periodic(self, it: int, recovery_results: list):
        """주기적 메타 작업 — 캘리브레이션/진화/시나리오/LLM 분석."""
        await periodic.maybe_calibrate_causal(self, it)
        await periodic.maybe_mutate_playbook(self, it)
        await periodic.maybe_adapt_scenario(self, it)
        await periodic.maybe_discover_causal(self, it)
        await periodic.maybe_evolve_agents(self, it)
        periodic.update_traceability(self, recovery_results)
        periodic.publish_recovery_events(self, recovery_results)
        await periodic.llm_batch_analysis(self, it)

    # ── HEALING LOOP ──────────────────────────────────────

    async def run_healing_loop(self):
        """자율 복구 루프를 연속 실행한다."""
        self.healing_running = True
        await self._emit("healing_loop_started", {"max_iterations": self.max_iterations})

        while self.healing_running and self.healing_iteration < self.max_iterations:
            if self.paused:
                await asyncio.sleep(0.5)
                continue
            await self.run_healing_iteration()
            await asyncio.sleep(0.5 * self.speed)

        self.healing_running = False
        self._persist_healing_summary()
        await self._emit("healing_loop_finished", {
            "total_iterations": self.healing_iteration,
            "total_incidents": len(self.healing_history),
            "auto_recovered": sum(1 for h in self.healing_history if h.get("auto_recovered")),
            "metrics": self.current_metrics,
        })

    async def run_full_cycle(self):
        """v3 온톨로지 개선 + v4 자율 복구를 순차 실행한다."""
        original_max = self.max_iterations
        self.max_iterations = 5
        await self._emit("phase_ontology", {
            "message": "Phase 1: 온톨로지 개선 루프 시작 (5 iterations)...",
        })
        await self.run_loop()  # v3 loop

        self.max_iterations = 10
        await self._emit("phase_healing", {
            "message": "Phase 2: 자율 복구 시뮬레이션 시작 (10 iterations)...",
        })
        await self.run_healing_loop()

        self.max_iterations = original_max

    # ── INTENT ROUTING ────────────────────────────────────

    async def route_intent(self, intent: str, payload: dict | None = None):
        """Hybrid orchestrator-style intent routing."""
        p = payload or {}
        intent_key = (intent or "").strip().lower()

        if intent_key in ("nl_diagnose", "diagnose_query", "ask_why"):
            result = self.nl_diagnoser.analyze(self.conn, str(p.get("query", "")))
            return await self._emit_route_trace(intent_key, "NaturalLanguageDiagnoser", result)
        if intent_key in ("predictive_priority", "rul", "maintenance_priority"):
            limit = max(1, min(20, int(p.get("limit", 5) or 5)))
            result = self.predictive_agent.rank_rul_risks_v1(self.conn, limit=limit)
            return await self._emit_route_trace(intent_key, "PredictiveAgent", result)
        if intent_key in ("healing_status", "status"):
            result = self.get_state().get("healing", {})
            return await self._emit_route_trace(intent_key, "SelfHealingEngine", result)
        if intent_key == "explain_step":
            step_id = str(p.get("step_id", ""))
            incidents = [x for x in self.healing_history if x.get("step_id") == step_id][-10:]
            result = {
                "step_id": step_id,
                "recent_incidents": incidents,
                "summary": self.nl_diagnoser.analyze(self.conn, f"{step_id} 최근 이슈 원인과 재발 리스크 요약"),
            }
            return await self._emit_route_trace(intent_key, "Hybrid(History+NL)", result)
        if intent_key in ("llm_analyze", "deep_analyze"):
            return await self._handle_deep_analyze(intent_key, p)
        if intent_key == "evolution_status":
            result = self.evolution_agent.get_status() if self.evolution_agent else {}
            return await self._emit_route_trace(intent_key, "EvolutionAgent", result)
        if intent_key == "causal_discovery_status":
            result = self.causal_discovery.get_status() if self.causal_discovery else {}
            return await self._emit_route_trace(intent_key, "CausalDiscoveryEngine", result)

        await self._emit("orchestrator_trace", {"intent": intent_key, "delegated_to": "none", "ok": False})
        return {"intent": intent_key, "delegated_to": "none", "error": "unsupported_intent"}

    async def _handle_deep_analyze(self, intent_key: str, p: dict):
        step_id = str(p.get("step_id", ""))
        recent = [x for x in self.healing_history if x.get("step_id") == step_id][-5:]
        if not recent or not self.llm_orchestrator:
            return await self._emit_route_trace(
                intent_key, "LLMOrchestrator",
                {"error": "no_recent_incidents", "step_id": step_id},
            )
        latest = recent[-1]
        anomaly = {"step_id": step_id, "anomaly_type": latest.get("anomaly_type")}
        diagnosis = {
            "candidates": [{
                "cause_type": latest.get("top_cause"),
                "confidence": latest.get("confidence", 0.5),
            }],
            "failure_chain_matched": latest.get("history_matched", False),
        }
        result = await self.llm_orchestrator.invoke_llm_reasoning(self.conn, anomaly, diagnosis)
        return await self._emit_route_trace(intent_key, "LLMOrchestrator", result)

    async def _emit_route_trace(self, intent: str, delegated_to: str, result):
        trace = {
            "ts": datetime.now().isoformat(),
            "intent": intent,
            "delegated_to": delegated_to,
            "ok": True,
        }
        self.orchestrator_traces.append(trace)
        self.orchestrator_traces = self.orchestrator_traces[-200:]
        await self._emit("orchestrator_trace", trace)
        return {"intent": intent, "delegated_to": delegated_to, "result": result}

    # ── RECOVERY HELPERS (used by phases) ─────────────────

    async def _execute_recovery_with_backoff(
        self, action: dict, max_attempts: int = 3, base_delay: float = 0.05,
    ) -> tuple[dict, int]:
        """복구 액션을 transient 실패에 대해 지수 백오프로 재시도한다.

        - execute_recovery()가 예외를 던지거나 success=False + transient=True면 재시도
        - 지수 백오프: base * 2^(attempt-1)
        - 영구 실패는 즉시 반환

        Returns: (result_dict, attempts_count)
        """
        last_result: dict = {"success": False}
        for attempt in range(1, max_attempts + 1):
            try:
                last_result = self.auto_recovery.execute_recovery(
                    self.conn, action, self.healing_counters,
                )
                if last_result.get("success"):
                    return last_result, attempt
                if not last_result.get("transient"):
                    return last_result, attempt
            except Exception as exc:
                last_result = {"success": False, "error": str(exc), "transient": True}
            if attempt < max_attempts:
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
        return last_result, max_attempts

    async def _merge_llm_hypotheses(
        self, iteration: int, anomaly: dict, causal_diag: dict,
        llm_result: dict | None, orch_decision: dict,
    ) -> None:
        """LLM 가설을 causal_diag에 병합 + 안전등급 A는 자동실행 차단을 위해 confidence 캡."""
        anomaly_step_id = anomaly.get("step_id", "")
        step_safety = self._get_step_safety_level(anomaly_step_id)
        hypotheses = (llm_result.get("hypotheses") or []) if llm_result else []
        guarded = False

        if hypotheses:
            requires_llm_hitl = (step_safety == "A")
            for hyp in hypotheses[:2]:
                hyp_conf = float(hyp.get("confidence", 0.5))
                if requires_llm_hitl:
                    # min_confidence(0.65) 미달로 캡하여 HITL 강제
                    hyp_conf = min(hyp_conf, 0.59)
                    guarded = True
                causal_diag.setdefault("candidates", []).append({
                    "cause_type": hyp.get("cause_type", "llm_hypothesis"),
                    "confidence": hyp_conf,
                    "evidence": hyp.get("reasoning", ""),
                    "source": "llm_orchestrator",
                    "causal_chain": "",
                    "requires_hitl_override": requires_llm_hitl,
                    "safety_level": step_safety,
                })
            causal_diag["candidates"].sort(key=lambda c: -c.get("confidence", 0))

            if guarded:
                hypotheses_capped = len(hypotheses[:2])
                causal_diag["llm_safety_guard"] = {
                    "triggered": True,
                    "safety_level": step_safety,
                    "step_id": anomaly_step_id,
                    "hypotheses_capped": hypotheses_capped,
                }
                await self._emit("llm_hypothesis_guarded", {
                    "iteration": iteration,
                    "step_id": anomaly_step_id,
                    "safety_level": step_safety,
                    "hypotheses_capped": hypotheses_capped,
                    "reason": "safety_level_A_requires_HITL",
                })

        await self._emit("orchestrator_decision", {
            "iteration": iteration,
            "step_id": anomaly_step_id,
            "path": orch_decision["path"],
            "reason": orch_decision["reason"],
            "complexity_score": orch_decision["complexity_score"],
            "llm_hypotheses": len(hypotheses),
            "safety_guarded": guarded,
        })


def _agent_descriptions(llm_orch) -> dict:
    """healing_initialized 이벤트의 agents 블록."""
    return {
        "anomaly_detector": {
            "name": "AnomalyDetector",
            "description": "SPC 기반 실시간 이상 감지",
        },
        "root_cause_analyzer": {
            "name": "RootCauseAnalyzer",
            "description": "온톨로지 경로 역추적 원인 진단",
        },
        "auto_recovery": {
            "name": "AutoRecoveryAgent",
            "description": "파라미터 자동 보정 및 복구",
        },
        "causal_reasoner": {
            "name": "CausalReasoner",
            "description": "인과관계 체인 기반 RCA 강화",
        },
        "correlation_analyzer": {
            "name": "CorrelationAnalyzer",
            "description": "공정 간 센서 상관분석 — 교차 원인 추적",
        },
        "cross_investigator": {
            "name": "CrossProcessInvestigator",
            "description": "상관관계 + 온톨로지 경로 교차 검증",
        },
        "predictive_agent": {
            "name": "PredictiveAgent",
            "description": "RUL 기반 선제적 정비 우선순위",
        },
        "nl_diagnoser": {
            "name": "NaturalLanguageDiagnoser",
            "description": "자연어 질의 기반 진단 요약",
        },
        "causal_discovery": {
            "name": "CausalDiscoveryEngine",
            "description": "Granger causality 기반 자동 인과 발견",
        },
        "evolution_agent": {
            "name": "EvolutionAgent",
            "description": "전략 자기진화 메타 에이전트 — 6+α 개선 전략 관리",
        },
        "llm_orchestrator": {
            "name": "LLMOrchestrator",
            "description": f"Hybrid Agentic 오케스트레이터 ({llm_orch.provider})" if llm_orch else "비활성",
        },
    }
