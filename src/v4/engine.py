"""
SelfHealingEngine --- v4 자율 복구 엔진
=========================================
v3의 온톨로지 개선 루프(OBSERVE->PROPOSE->DEBATE->APPLY->EVALUATE->LEARN) 위에
실시간 자율 복구 루프(DETECT->DIAGNOSE->RECOVER->VERIFY->LEARN)를 추가한다.

WebSocket을 통해 매 단계마다 이벤트를 발행하여 프론트엔드에서 실시간 시각화 가능.
"""
import asyncio
import json
import os
import time
import traceback
from datetime import datetime

from v3.engine import HarnessEngine
from v4.sensor_simulator import SensorSimulator, extend_schema_l2, store_readings, store_alarm
from v4.healing_agents import (
    AnomalyDetector,
    RootCauseAnalyzer,
    AutoRecoveryAgent,
    RISK_NUMERIC,
    requires_hitl,
)
from v4.causal import extend_schema_l3, seed_causal_knowledge, CausalReasoner
from v4.correlation import extend_schema_correlation, CorrelationAnalyzer, CrossProcessInvestigator
from v4.scenarios import ScenarioEngine
from v4.llm_analyst import LLMAnalyst
from v4.llm_agents import PredictiveAgent, NaturalLanguageDiagnoser
from v4.decision_layer import extend_schema_l4, seed_l4_policy, load_active_policy, update_active_policy


class SelfHealingEngine(HarnessEngine):
    """v4 자율 복구 엔진. v3의 온톨로지 개선 + 실시간 이상 감지/진단/복구."""

    def __init__(self, data_path="data/graph_data.json", db_path="kuzu_v4_live", results_dir="results"):
        super().__init__(data_path=data_path, db_path=db_path)

        # Healing-specific agents and state
        self.sensor_sim = None
        self.anomaly_detector = None
        self.root_cause_analyzer = None
        self.auto_recovery = None
        self.causal_reasoner = None
        self.predictive_agent = None
        self.nl_diagnoser = None
        self.healing_counters = {"reading": 0, "alarm": 0, "incident": 0, "recovery": 0}
        self.healing_history = []       # list of incident records
        self.healing_iteration = 0
        self.healing_running = False
        self.results_dir = results_dir
        self.l3_trend_history = []
        self.latest_l3_snapshot = {}
        self.latest_predictive = []
        self.orchestrator_traces = []
        self.hitl_pending = []
        self.hitl_audit = []
        self.hitl_policy = {
            "min_confidence": 0.62,
            "high_risk_threshold": 0.6,
            "medium_requires_history": True,
        }

    # ── INIT ──────────────────────────────────────────────

    async def initialize(self):
        """DB, 에이전트, 센서 시뮬레이터를 초기화한다."""
        # v3 초기화 (스키마 + 에이전트 + 메트릭)
        await super().initialize()

        # L2 스키마 확장 (SensorReading, Alarm, Incident, RecoveryAction 등)
        extend_schema_l2(self.conn)

        # L3 인과 추론 계층 확장
        extend_schema_l3(self.conn)
        seed_causal_knowledge(self.conn, self.healing_counters)
        extend_schema_l4(self.conn)
        seed_l4_policy(self.conn)

        # 상관분석 스키마 확장
        extend_schema_correlation(self.conn)

        # 자율 복구 에이전트 초기화
        self.sensor_sim = SensorSimulator(self.conn)
        self.anomaly_detector = AnomalyDetector()
        self.root_cause_analyzer = RootCauseAnalyzer()
        self.auto_recovery = AutoRecoveryAgent()
        self.causal_reasoner = CausalReasoner()
        self.correlation_analyzer = CorrelationAnalyzer()
        self.cross_investigator = CrossProcessInvestigator()
        self.scenario_engine = ScenarioEngine(self.sensor_sim)
        self.llm_analyst = LLMAnalyst()
        self.predictive_agent = PredictiveAgent()
        self.nl_diagnoser = NaturalLanguageDiagnoser()

        # 카운터/이력 리셋
        self.healing_counters = {"reading": 0, "alarm": 0, "incident": 0, "recovery": 0}
        self.healing_history = []
        self.healing_iteration = 0
        self.healing_running = False
        self.l3_trend_history = []
        self.latest_l3_snapshot = {}
        self.latest_predictive = []
        self.orchestrator_traces = []
        self.hitl_pending = []
        self.hitl_audit = []
        self.hitl_policy = {
            "min_confidence": 0.62,
            "high_risk_threshold": 0.6,
            "medium_requires_history": True,
        }
        self._load_hitl_runtime_state()
        graph_policy = load_active_policy(self.conn)
        if graph_policy:
            self.hitl_policy.update({
                "min_confidence": graph_policy["min_confidence"],
                "high_risk_threshold": graph_policy["high_risk_threshold"],
                "medium_requires_history": graph_policy["medium_requires_history"],
            })

        await self._emit("healing_initialized", {
            "sensor_count": self.sensor_sim.sensor_count
                if hasattr(self.sensor_sim, "sensor_count") else 0,
            "agents": {
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
            },
        })

    # ── SINGLE HEALING ITERATION ──────────────────────────

    async def run_healing_iteration(self):
        """자율 복구 루프 1회: SENSE -> DETECT -> DIAGNOSE -> RECOVER -> VERIFY -> LEARN."""
        it = self.healing_iteration
        delay = 0.3 * self.speed

        try:
            # ⓪ SCENARIO — 장애 시나리오 주입
            scenario_effects = self.scenario_engine.tick()
            if it % 4 == 1 and not self.scenario_engine.get_active_scenarios():
                activated = self.scenario_engine.activate_random()
                if activated:
                    await self._emit("scenario_activated", {
                        "iteration": it + 1,
                        "scenario": activated,
                    })

            # ① SENSE ─────────────────────────────────────
            await self._emit("phase", {
                "iteration": it + 1,
                "phase": "sense",
                "message": "센서 데이터를 수집합니다...",
            })
            await asyncio.sleep(delay)

            readings = self.sensor_sim.generate_readings()
            stored_count = store_readings(self.conn, readings, self.healing_counters)

            # 원시 readings에서 정상범위 이탈 개수 (간이 카운트)
            anomaly_count_raw = sum(
                1 for r in readings if r.get("out_of_range", False)
            )

            await self._emit("sense_done", {
                "iteration": it + 1,
                "reading_count": len(readings),
                "anomaly_count_raw": anomaly_count_raw,
            })
            await asyncio.sleep(delay)

            # ①-b CORRELATE — 센서 간 상관분석
            self.correlation_analyzer.ingest(readings)
            if it > 0 and it % 3 == 0:  # 3 이터레이션마다 상관분석 실행
                correlations = self.correlation_analyzer.analyze_all()
                if correlations:
                    stored = self.cross_investigator.store_discovered_correlations(
                        self.conn, correlations, self.healing_counters
                    )
                    await self._emit("correlation_found", {
                        "iteration": it + 1,
                        "correlations": [
                            {
                                "source": c["source_step"],
                                "target": c["target_step"],
                                "coefficient": c["coefficient"],
                                "direction": c["direction"],
                                "sensors": f"{c['source_sensor']}↔{c['target_sensor']}",
                            }
                            for c in correlations[:5]
                        ],
                        "total_found": len(correlations),
                        "stored_new": stored,
                    })

            # ② DETECT ────────────────────────────────────
            await self._emit("phase", {
                "iteration": it + 1,
                "phase": "detect",
                "message": "이상 패턴을 감지합니다...",
            })
            await asyncio.sleep(delay)

            self.anomaly_detector.update(readings)
            anomalies = self.anomaly_detector.detect(readings)

            # 알람 체크
            alarms = self.sensor_sim.check_alarms(readings)
            for alarm in alarms:
                store_alarm(self.conn, alarm, self.healing_counters)

            steps_affected = list({
                a.get("step_id", "unknown") for a in anomalies
            })

            await self._emit("detect_done", {
                "iteration": it + 1,
                "anomalies": [
                    {
                        "step_id": a.get("step_id"),
                        "sensor": a.get("sensor"),
                        "type": a.get("type", "unknown"),
                        "severity": a.get("severity", "medium"),
                        "value": a.get("value"),
                    }
                    for a in anomalies
                ],
                "alarm_count": len(alarms),
                "steps_affected": steps_affected,
            })
            await asyncio.sleep(delay)

            if not anomalies:
                await self._emit("all_clear", {
                    "iteration": it + 1,
                    "message": "이상 없음 - 모든 센서 정상 범위",
                    "reading_count": len(readings),
                })
                return

            # ③ DIAGNOSE ──────────────────────────────────
            await self._emit("phase", {
                "iteration": it + 1,
                "phase": "diagnose",
                "message": "원인을 진단합니다...",
            })
            await asyncio.sleep(delay)

            diagnoses = []
            for anomaly in anomalies:
                try:
                    # 1단계: 경로 기반 기본 진단
                    basic_diag = self.root_cause_analyzer.analyze(self.conn, anomaly)
                    # 2단계: 인과관계 기반 강화 진단
                    causal_diag = self.causal_reasoner.analyze(self.conn, anomaly, basic_diag)
                    diagnoses.append(causal_diag)
                except Exception as exc:
                    diagnoses.append({
                        "step_id": anomaly.get("step_id"),
                        "candidates": [],
                        "causal_chains_found": 0,
                        "failure_chain_matched": False,
                        "analysis_method": "failed",
                        "error": str(exc),
                    })

            # ③-b 교차 원인 분석 (상관관계 기반)
            cross_investigations = []
            for anomaly in anomalies:
                try:
                    inv = self.cross_investigator.investigate(
                        self.conn, anomaly, self.correlation_analyzer
                    )
                    if inv.get("cross_causes"):
                        cross_investigations.append(inv)
                except Exception:
                    pass

            await self._emit("diagnose_done", {
                "iteration": it + 1,
                "diagnoses": [
                    {
                        "step_id": d.get("step_id"),
                        "top_cause": d["candidates"][0]["cause_type"] if d.get("candidates") else "unknown",
                        "confidence": round(d["candidates"][0]["confidence"], 3) if d.get("candidates") else 0.0,
                        "causal_chain": d["candidates"][0].get("causal_chain") if d.get("candidates") else None,
                        "candidates_count": len(d.get("candidates", [])),
                        "causal_chains": d.get("causal_chains_found", 0),
                        "history_matched": d.get("failure_chain_matched", False),
                        "method": d.get("analysis_method", "basic"),
                    }
                    for d in diagnoses
                ],
                "cross_investigations": [
                    {
                        "step_id": inv["step_id"],
                        "cross_causes": [
                            {
                                "other_step": c["step_id"],
                                "other_name": c["step_name"],
                                "relationship": c["relationship"],
                                "correlation": c["correlation"],
                                "confidence": c["confidence"],
                                "evidence": c["evidence"],
                                "action": c["recommended_action"],
                            }
                            for c in inv["cross_causes"][:3]
                        ],
                        "hidden_dependencies": inv["hidden_dependencies"],
                    }
                    for inv in cross_investigations
                ],
            })
            await asyncio.sleep(delay)

            # ④ RECOVER ───────────────────────────────────
            await self._emit("phase", {
                "iteration": it + 1,
                "phase": "recover",
                "message": "자동 복구를 실행합니다...",
            })
            await asyncio.sleep(delay)

            recovery_results = []
            for diagnosis, anomaly in zip(diagnoses, anomalies):
                try:
                    step_id = anomaly.get("step_id")
                    pre_yield_baseline = self._get_step_yield(step_id)
                    actions = self.auto_recovery.plan_recovery(
                        self.conn, diagnosis, anomaly,
                    )
                    if not actions:
                        recovery_results.append({
                            "step_id": anomaly.get("step_id"),
                            "action_type": "none",
                            "target": None,
                            "success": False,
                            "pre_yield": pre_yield_baseline,
                            "detail": "복구 액션을 생성하지 못함",
                        })
                        continue

                    # 최적 액션 선택: confidence 높고 risk 낮은 것
                    best_action = max(
                        actions,
                        key=lambda a: a.get("confidence", 0)
                        * (1 - RISK_NUMERIC.get(str(a.get("risk_level", "MEDIUM")), 0.5)),
                    )

                    hitl_needed, hitl_reason = requires_hitl(
                        best_action,
                        diagnosis,
                        min_confidence=float(self.hitl_policy.get("min_confidence", 0.62)),
                        high_risk_threshold=float(self.hitl_policy.get("high_risk_threshold", 0.6)),
                        medium_requires_history=bool(self.hitl_policy.get("medium_requires_history", True)),
                    )
                    if hitl_needed:
                        pending_id = f"HITL-{it + 1:04d}-{len(self.hitl_pending) + 1:03d}"
                        pending = {
                            "id": pending_id,
                            "iteration": it + 1,
                            "created_at": datetime.now().isoformat(),
                            "step_id": step_id,
                            "anomaly_type": anomaly.get("anomaly_type", "unknown"),
                            "top_cause": diagnosis["candidates"][0]["cause_type"] if diagnosis.get("candidates") else "unknown",
                            "reason": hitl_reason,
                            "action": best_action,
                            "status": "pending",
                        }
                        self.hitl_pending.append(pending)
                        self.hitl_pending = self.hitl_pending[-50:]
                        self._append_hitl_audit("queued", "system", {
                            "hitl_id": pending_id,
                            "step_id": step_id,
                            "reason": hitl_reason,
                        })
                        self._persist_hitl_runtime_state()
                        await self._emit("recover_pending_hitl", pending)
                        recovery_results.append({
                            "step_id": anomaly.get("step_id"),
                            "action_type": "ESCALATE",
                            "target": best_action.get("target_step"),
                            "success": False,
                            "recovery_id": None,
                            "pre_yield": pre_yield_baseline,
                            "detail": f"HITL required: {hitl_reason}",
                            "risk_level": best_action.get("risk_level"),
                            "confidence": best_action.get("confidence"),
                            "playbook_id": best_action.get("playbook_id"),
                            "playbook_source": best_action.get("playbook_source"),
                            "hitl_required": True,
                            "hitl_id": pending_id,
                        })
                        continue

                    recover_started = time.time()
                    result = self.auto_recovery.execute_recovery(
                        self.conn, best_action, self.healing_counters,
                    )
                    recovery_time_sec = max(0.0, time.time() - recover_started)
                    recovery_results.append({
                        "step_id": anomaly.get("step_id"),
                        "action_type": best_action.get("action_type", "unknown"),
                        "target": best_action.get("target_step"),
                        "success": result.get("success", False),
                        "recovery_id": result.get("recovery_id"),
                        "pre_yield": pre_yield_baseline,
                        "detail": result.get("detail", ""),
                        "risk_level": best_action.get("risk_level"),
                        "confidence": best_action.get("confidence"),
                        "playbook_id": best_action.get("playbook_id"),
                        "playbook_source": best_action.get("playbook_source"),
                        "hitl_required": False,
                        "recovery_time_sec": round(recovery_time_sec, 4),
                    })
                except Exception as exc:
                    recovery_results.append({
                        "step_id": anomaly.get("step_id"),
                        "action_type": "error",
                        "target": None,
                        "success": False,
                        "pre_yield": None,
                        "detail": str(exc),
                        "recovery_time_sec": None,
                    })

            await self._emit("recover_done", {
                "iteration": it + 1,
                "actions": recovery_results,
            })
            await asyncio.sleep(delay)

            # ⑤ VERIFY ────────────────────────────────────
            await self._emit("phase", {
                "iteration": it + 1,
                "phase": "verify",
                "message": "복구 결과를 검증합니다...",
            })
            await asyncio.sleep(delay)

            verifications = []
            for rr, anomaly in zip(recovery_results, anomalies):
                step_id = rr.get("step_id") or anomaly.get("step_id")
                pre_yield = rr.get("pre_yield")
                if pre_yield is None:
                    pre_yield = self._get_step_yield(step_id)
                if pre_yield is None:
                    pre_yield = anomaly.get("pre_yield", 0.0)
                try:
                    verification = self.auto_recovery.verify_recovery(
                        self.conn, step_id, pre_yield,
                    )
                    verifications.append({
                        "step_id": step_id,
                        "pre_yield": pre_yield,
                        "post_yield": verification.get("post_yield"),
                        "improved": verification.get(
                            "improved", verification.get("verified", False)
                        ),
                    })
                except Exception as exc:
                    verifications.append({
                        "step_id": step_id,
                        "pre_yield": pre_yield,
                        "post_yield": None,
                        "improved": False,
                        "error": str(exc),
                    })

            # 최신 전체 메트릭 갱신
            try:
                gm = self.skill_registry.execute("graph_metrics", self.conn, {}, "system")
                updated_metrics = gm.get("metrics", self.current_metrics)
                self.current_metrics = updated_metrics
            except Exception:
                updated_metrics = self.current_metrics

            # Phase4: PredictiveAgent RUL 추정
            predictive = []
            try:
                predictive = self.predictive_agent.rank_rul_risks_v1(self.conn, limit=5)
                self.latest_predictive = predictive
            except Exception:
                predictive = self.latest_predictive

            await self._emit("verify_done", {
                "iteration": it + 1,
                "verifications": verifications,
                "metrics": updated_metrics,
                "predictive": predictive,
            })
            await asyncio.sleep(delay)

            # ⑥ LEARN (healing) ───────────────────────────
            await self._emit("phase", {
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
                step_id = anomaly.get("step_id", "unknown")
                auto_recovered = rr.get("success", False)
                improved = verification.get("improved", False)
                if rr.get("action_type") == "ESCALATE":
                    auto_recovered = False
                top_cause = ""
                if diagnosis.get("candidates"):
                    top_cause = diagnosis["candidates"][0].get("cause_type", "")

                # 에이전트 지식 업데이트
                try:
                    self.anomaly_detector.learn(anomaly, diagnosis, rr)
                    knowledge_updates += 1
                except Exception:
                    pass

                try:
                    self.root_cause_analyzer.learn(
                        step_id, anomaly.get("sensor_type", ""), top_cause
                    )
                    knowledge_updates += 1
                except Exception:
                    pass

                try:
                    self.auto_recovery.learn(
                        rr.get("action_type", "unknown"),
                        top_cause or "unknown",
                        bool(auto_recovered and improved),
                    )
                    knowledge_updates += 1
                except Exception:
                    pass

                # 인과 추론 학습 (FailureChain 축적)
                try:
                    self.causal_reasoner.learn_from_recovery(
                        self.conn, step_id,
                        anomaly.get("sensor_type", ""),
                        anomaly.get("anomaly_type", ""),
                        top_cause,
                        bool(auto_recovered and improved),
                        float(rr.get("recovery_time_sec", 0.5) or 0.5),
                        self.healing_counters,
                    )
                    knowledge_updates += 1
                except Exception:
                    pass

                # 이력 기록
                # 인과 추론 결과에서 원인 추출
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
                    "id": f"INC-{self.healing_counters['incident'] + 1:04d}",
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
                    "improved": improved,
                    "pre_yield": verification.get("pre_yield"),
                    "post_yield": verification.get("post_yield"),
                }
                self.healing_history.append(incident)
                self.healing_counters["incident"] += 1
                incidents_recorded += 1
                if auto_recovered:
                    auto_recovered_count += 1

                # Incident 노드를 DB에 저장
                try:
                    self.conn.execute(
                        "CREATE (inc:Incident {"
                        "id: $id, step_id: $step_id, alarm_id: '', "
                        "root_cause: $cause, recovery_action: $action, "
                        "resolved: $resolved, auto_recovered: $recovered, timestamp: $ts"
                        "})",
                        {
                            "id": incident["id"],
                            "step_id": step_id,
                            "cause": incident["top_cause"],
                            "action": incident["action_type"],
                            "resolved": auto_recovered,
                            "recovered": auto_recovered,
                            "ts": incident["timestamp"],
                        },
                    )
                except Exception:
                    # Incident 테이블이 없거나 중복일 수 있음 - 무시
                    pass

                # 과거 FailureChain 매칭이 있으면 Incident와 연결
                matched_chain_id = diagnosis.get("matched_chain_id")
                if not matched_chain_id:
                    matched_chain_id = self.causal_reasoner.chain_cache.get(
                        (step_id, anomaly.get("sensor_type", ""))
                    )
                if matched_chain_id:
                    try:
                        self.conn.execute(
                            "MATCH (inc:Incident), (fc:FailureChain) "
                            "WHERE inc.id = $inc_id AND fc.id = $fc_id "
                            "CREATE (inc)-[:MATCHED_BY]->(fc)",
                            {"inc_id": incident["id"], "fc_id": matched_chain_id},
                        )
                    except Exception:
                        pass

                if rr.get("action_type") == "ESCALATE":
                    try:
                        self.conn.execute(
                            "MATCH (inc:Incident), (p:EscalationPolicy) "
                            "WHERE inc.id=$inc_id AND p.id='EP-DEFAULT' "
                            "CREATE (inc)-[:ESCALATES_TO]->(p)",
                            {"inc_id": incident["id"]},
                        )
                    except Exception:
                        pass

                # 기본 L2 관계 연결: ProcessStep -> Incident, Incident -> RecoveryAction
                try:
                    self.conn.execute(
                        "MATCH (ps:ProcessStep), (inc:Incident) "
                        "WHERE ps.id = $step_id AND inc.id = $inc_id "
                        "CREATE (ps)-[:HAS_INCIDENT]->(inc)",
                        {"step_id": step_id, "inc_id": incident["id"]},
                    )
                except Exception:
                    pass

                recovery_id = rr.get("recovery_id")
                if recovery_id:
                    try:
                        self.conn.execute(
                            "MATCH (inc:Incident), (ra:RecoveryAction) "
                            "WHERE inc.id = $inc_id AND ra.id = $ra_id "
                            "CREATE (inc)-[:RESOLVED_BY]->(ra)",
                            {"inc_id": incident["id"], "ra_id": recovery_id},
                        )
                    except Exception:
                        pass

                # ProcessStep -> CausalRule, CausalRule -> AnomalyPattern 연결 강화
                if top_cause:
                    try:
                        self.conn.execute(
                            "MATCH (ps:ProcessStep), (cr:CausalRule) "
                            "WHERE ps.id = $step_id AND (cr.cause_type = $cause OR cr.effect_type = $cause) "
                            "AND NOT (ps)-[:HAS_CAUSE]->(cr) "
                            "CREATE (ps)-[:HAS_CAUSE]->(cr)",
                            {"step_id": step_id, "cause": top_cause},
                        )
                        l3_links_created += 1
                    except Exception:
                        pass

                    anomaly_type = anomaly.get("anomaly_type", "threshold_breach")
                    pattern_type = {
                        "trend_shift": "drift",
                        "statistical_outlier": "spike",
                        "threshold_breach": "level_shift",
                    }.get(anomaly_type, "spike")

                    try:
                        self.conn.execute(
                            "MATCH (cr:CausalRule), (ap:AnomalyPattern) "
                            "WHERE (cr.cause_type = $cause OR cr.effect_type = $cause) "
                            "AND ap.pattern_type = $ptype "
                            "AND NOT (cr)-[:HAS_PATTERN]->(ap) "
                            "CREATE (cr)-[:HAS_PATTERN]->(ap)",
                            {"cause": top_cause, "ptype": pattern_type},
                        )
                        l3_links_created += 1
                    except Exception:
                        pass

            await self._emit("learn_done_healing", {
                "iteration": it + 1,
                "incidents_recorded": incidents_recorded,
                "auto_recovered_count": auto_recovered_count,
                "knowledge_updates": knowledge_updates,
                "l3_links_created": l3_links_created,
                "l3_snapshot": self._record_l3_snapshot(it + 1),
                "recent_incidents": self.healing_history[-5:],
            })
            # 3회마다 replay calibration
            if (it + 1) % 3 == 0:
                cal = self.causal_reasoner.replay_calibration(self.conn)
                await self._emit("causal_calibrated", {"iteration": it + 1, **cal})

            # LLM 분석 — 가장 최근 인시던트에 대해 실행
            if self.healing_history and self.llm_analyst.available:
                latest_inc = self.healing_history[-1]
                try:
                    # 인시던트 데이터 구성
                    step_name = ""
                    try:
                        r = self.conn.execute("MATCH (ps:ProcessStep) WHERE ps.id=$id RETURN ps.name", {"id": latest_inc.get("step_id","")})
                        if r.has_next():
                            step_name = r.get_next()[0]
                    except Exception:
                        pass

                    inc_data = {
                        "step_id": latest_inc.get("step_id", ""),
                        "step_name": step_name,
                        "anomaly": {
                            "sensor_type": latest_inc.get("anomaly_type", ""),
                            "severity": latest_inc.get("severity", "MEDIUM"),
                            "anomaly_type": latest_inc.get("anomaly_type", ""),
                        },
                        "diagnosis": {
                            "top_cause": latest_inc.get("top_cause", ""),
                            "confidence": latest_inc.get("confidence", 0),
                            "causal_chain": latest_inc.get("causal_chain", ""),
                            "history_matched": latest_inc.get("history_matched", False),
                        },
                        "cross_investigation": {
                            "correlated_steps": self.correlation_analyzer.get_correlations_for_step(latest_inc.get("step_id","")),
                        },
                        "recovery": {
                            "action_type": latest_inc.get("action_type", ""),
                            "success": latest_inc.get("auto_recovered", False),
                            "pre_yield": latest_inc.get("pre_yield"),
                            "post_yield": latest_inc.get("post_yield"),
                        },
                    }
                    # 활성 시나리오가 있으면 포함
                    active_scn = self.scenario_engine.get_active_scenarios()
                    if active_scn:
                        inc_data["scenario"] = {"name": active_scn[0].get("name",""), "category": active_scn[0].get("category","")}

                    analysis = self.llm_analyst.analyze_incident_sync(inc_data)
                    await self._emit("incident_analysis", analysis)
                except Exception:
                    pass

            self._persist_healing_summary()

        except Exception as exc:
            await self._emit("healing_error", {
                "iteration": it + 1,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            })
        finally:
            self.healing_iteration += 1

    # ── HEALING LOOP ──────────────────────────────────────

    async def run_healing_loop(self):
        """자율 복구 루프를 연속 실행한다."""
        self.healing_running = True
        await self._emit("healing_loop_started", {
            "max_iterations": self.max_iterations,
        })

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
            "auto_recovered": sum(
                1 for h in self.healing_history if h.get("auto_recovered")
            ),
            "metrics": self.current_metrics,
        })

    # ── FULL CYCLE (v3 + v4) ─────────────────────────────

    async def run_full_cycle(self):
        """v3 온톨로지 개선 + v4 자율 복구를 순차 실행한다."""
        # Phase 1: 온톨로지 개선 (v3)
        await self._emit("phase_ontology", {
            "message": "Phase 1: 온톨로지 개선 루프 시작...",
        })
        await self.run_loop()  # v3 loop

        # Phase 2: 자율 복구 시뮬레이션 (v4)
        await self._emit("phase_healing", {
            "message": "Phase 2: 자율 복구 시뮬레이션 시작...",
        })
        await self.run_healing_loop()

    async def resolve_hitl(
        self,
        hitl_id: str,
        approve: bool,
        operator: str = "operator",
        role: str = "operator",
    ):
        """HITL 대기 액션을 승인/거절한다."""
        item = None
        for h in self.hitl_pending:
            if h.get("id") == hitl_id and h.get("status") == "pending":
                item = h
                break
        if not item:
            return {"ok": False, "reason": "not_found_or_already_resolved", "id": hitl_id}

        if not approve:
            item["status"] = "rejected"
            item["resolved_at"] = datetime.now().isoformat()
            item["operator"] = operator
            item["operator_role"] = role
            self._append_hitl_audit("rejected", operator, {"hitl_id": hitl_id}, role=role)
            self._persist_hitl_runtime_state()
            await self._emit("hitl_resolved", {"id": hitl_id, "status": "rejected", "operator": operator})
            return {"ok": True, "status": "rejected", "id": hitl_id}

        # 고위험/저신뢰 액션은 supervisor 이상만 승인 가능
        reason = str(item.get("reason", "") or "")
        if role != "supervisor" and ("high_risk" in reason or "low_confidence" in reason):
            item["status"] = "denied"
            item["resolved_at"] = datetime.now().isoformat()
            item["operator"] = operator
            item["operator_role"] = role
            self._append_hitl_audit(
                "approve_denied",
                operator,
                {"hitl_id": hitl_id, "reason": "supervisor_required"},
                role=role,
            )
            self._persist_hitl_runtime_state()
            await self._emit(
                "hitl_resolved",
                {
                    "id": hitl_id,
                    "status": "denied",
                    "operator": operator,
                    "reason": "supervisor_required",
                },
            )
            return {"ok": False, "status": "denied", "id": hitl_id, "reason": "supervisor_required"}

        action = item.get("action", {})
        item["status"] = "approved"
        item["resolved_at"] = datetime.now().isoformat()
        item["operator"] = operator
        item["operator_role"] = role
        try:
            result = self.auto_recovery.execute_recovery(self.conn, action, self.healing_counters)
            payload = {
                "id": hitl_id,
                "status": "approved",
                "operator": operator,
                "action_type": action.get("action_type"),
                "step_id": action.get("target_step"),
                "result": result,
            }
            self._append_hitl_audit(
                "approved",
                operator,
                {"hitl_id": hitl_id, "action_type": action.get("action_type")},
                role=role,
            )
            self._persist_hitl_runtime_state()
            await self._emit("hitl_resolved", payload)
            return {"ok": True, **payload}
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
            self._append_hitl_audit("approve_failed", operator, {"hitl_id": hitl_id, "error": str(exc)}, role=role)
            self._persist_hitl_runtime_state()
            await self._emit("hitl_resolved", {
                "id": hitl_id,
                "status": "failed",
                "operator": operator,
                "error": str(exc),
            })
            return {"ok": False, "status": "failed", "id": hitl_id, "error": str(exc)}

    # ── STATE ─────────────────────────────────────────────

    def get_state(self):
        """현재 엔진 상태를 반환한다 (v3 + v4)."""
        state = super().get_state()
        state["healing"] = {
            "iteration": self.healing_iteration,
            "running": self.healing_running,
            "incidents": len(self.healing_history),
            "auto_recovered": sum(
                1 for h in self.healing_history if h.get("auto_recovered")
            ),
            "counters": dict(self.healing_counters),
            "recent_incidents": self.healing_history[-5:],  # last 5
            "recurrence_kpis": self._compute_recurrence_kpis(),
            "hitl_pending": self.hitl_pending[-20:],
            "hitl_audit": self.hitl_audit[-30:],
            "hitl_policy": dict(self.hitl_policy),
        }
        state["phase4"] = {
            "predictive_agent": self.predictive_agent is not None,
            "nl_diagnoser": self.nl_diagnoser is not None,
            "llm_orchestrator": bool(self.nl_diagnoser and self.nl_diagnoser.get_status().get("llm_enabled")),
            "model": self.nl_diagnoser.get_status().get("model") if self.nl_diagnoser else "none",
            "latest_predictive": self.latest_predictive[:5],
            "orchestrator_traces": self.orchestrator_traces[-20:],
        }
        state["l3_trends"] = self.l3_trend_history[-30:]
        state["l3_snapshot"] = dict(self.latest_l3_snapshot) if self.latest_l3_snapshot else {}
        return state

    # ── L3 TREND PERSISTENCE ─────────────────────────────

    def _safe_count_nodes(self, label: str) -> int:
        try:
            r = self.conn.execute(f"MATCH (n:{label}) RETURN count(n)")
            if r.has_next():
                return int(r.get_next()[0])
        except Exception:
            pass
        return 0

    def _safe_count_rel(self, rel_type: str) -> int:
        try:
            r = self.conn.execute(f"MATCH ()-[r:{rel_type}]->() RETURN count(r)")
            if r.has_next():
                return int(r.get_next()[0])
        except Exception:
            pass
        return 0

    def _collect_l3_snapshot(self, iteration: int) -> dict:
        return {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "counts": {
                "causal_rules": self._safe_count_nodes("CausalRule"),
                "failure_chains": self._safe_count_nodes("FailureChain"),
                "causes": self._safe_count_rel("CAUSES"),
                "matched_by": self._safe_count_rel("MATCHED_BY"),
                "chain_uses": self._safe_count_rel("CHAIN_USES"),
                "has_cause": self._safe_count_rel("HAS_CAUSE"),
                "has_pattern": self._safe_count_rel("HAS_PATTERN"),
            },
        }

    def _record_l3_snapshot(self, iteration: int) -> dict:
        snapshot = self._collect_l3_snapshot(iteration)
        self.latest_l3_snapshot = snapshot
        self.l3_trend_history.append(snapshot)
        self._persist_l3_trend_files()
        return snapshot

    def _persist_l3_trend_files(self):
        try:
            os.makedirs(self.results_dir, exist_ok=True)
            latest_path = os.path.join(self.results_dir, "l3_trend_latest.json")
            history_path = os.path.join(self.results_dir, "l3_trend_history.json")
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(self.latest_l3_snapshot, f, ensure_ascii=False, indent=2)
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(self.l3_trend_history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _persist_healing_summary(self):
        try:
            os.makedirs(self.results_dir, exist_ok=True)
            cases = self._build_case_analyses()
            out = {
                "system": "SelfHealingEngine v4",
                "timestamp": datetime.now().isoformat(),
                "healing_iterations": self.healing_iteration,
                "total_incidents": len(self.healing_history),
                "auto_recovered": sum(1 for h in self.healing_history if h.get("auto_recovered")),
                "current_metrics": self.current_metrics,
                "healing_counters": dict(self.healing_counters),
                "latest_l3_snapshot": self.latest_l3_snapshot,
                "l3_trend_points": len(self.l3_trend_history),
                "recent_incidents": self.healing_history[-20:],
                "case_analyses": cases,
                "recurrence_kpis": self._compute_recurrence_kpis(),
                "hitl_pending": self.hitl_pending[-20:],
                "hitl_audit": self.hitl_audit[-30:],
                "hitl_policy": dict(self.hitl_policy),
            }
            latest_path = os.path.join(self.results_dir, "self_healing_v4_latest.json")
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _get_step_yield(self, step_id):
        if not step_id:
            return None
        try:
            r = self.conn.execute(
                "MATCH (ps:ProcessStep) WHERE ps.id=$sid RETURN ps.yield_rate",
                {"sid": step_id},
            )
            if r.has_next():
                v = r.get_next()[0]
                if v is None:
                    return None
                return float(v)
        except Exception:
            pass
        return None

    def _build_case_analyses(self):
        analyses = []
        for inc in self.healing_history[-20:]:
            pre = inc.get("pre_yield")
            post = inc.get("post_yield")
            delta = None
            delta_pct = None
            quality_flag = None
            if isinstance(pre, (int, float)) and isinstance(post, (int, float)):
                delta = round(post - pre, 6)
                if pre != 0:
                    delta_pct = round((delta / pre) * 100, 2)
            if isinstance(pre, (int, float)) and (pre < 0 or pre > 1.2):
                quality_flag = "pre_yield_outlier"

            analyses.append({
                "incident_id": inc.get("id"),
                "step_id": inc.get("step_id"),
                "issue": {
                    "anomaly_type": inc.get("anomaly_type"),
                    "severity": inc.get("severity"),
                    "top_cause": inc.get("top_cause"),
                    "confidence": inc.get("confidence"),
                },
                "recovery": {
                    "action_type": inc.get("action_type"),
                    "auto_recovered": inc.get("auto_recovered"),
                    "improved": inc.get("improved"),
                },
                "effect": {
                    "pre_yield": pre,
                    "post_yield": post,
                    "delta": delta,
                    "delta_pct": delta_pct,
                },
                "quality_flag": quality_flag,
                "timestamp": inc.get("timestamp"),
            })
        return analyses

    def _compute_recurrence_kpis(self):
        incidents = self.healing_history
        if not incidents:
            return {
                "matched_chain_rate": 0.0,
                "repeat_incident_rate": 0.0,
                "matched_auto_recovery_rate": 0.0,
                "matched_avg_recovery_sec": 0.0,
                "unmatched_avg_recovery_sec": 0.0,
                "graph_playbook_rate": 0.0,
                "hardcoded_fallback_rate": 0.0,
                "total": 0,
            }
        matched = [x for x in incidents if x.get("history_matched")]
        keys = [f"{x.get('step_id')}|{x.get('anomaly_type')}|{x.get('top_cause')}" for x in incidents]
        uniq = set(keys)
        repeat_count = len(keys) - len(uniq)
        matched_auto = [x for x in matched if x.get("auto_recovered")]
        matched_times = [float(x.get("recovery_time_sec")) for x in matched if isinstance(x.get("recovery_time_sec"), (int, float))]
        unmatched = [x for x in incidents if not x.get("history_matched")]
        unmatched_times = [float(x.get("recovery_time_sec")) for x in unmatched if isinstance(x.get("recovery_time_sec"), (int, float))]
        with_playbook = [x for x in incidents if x.get("playbook_source")]
        graph_playbook = [
            x for x in with_playbook
            if str(x.get("playbook_source", "")).startswith("graph")
        ]
        hardcoded_fallback = [
            x for x in with_playbook
            if str(x.get("playbook_source", "")) == "hardcoded"
        ]
        total = len(incidents)
        return {
            "matched_chain_rate": round(len(matched) / total, 4),
            "repeat_incident_rate": round(repeat_count / total, 4),
            "matched_auto_recovery_rate": round(len(matched_auto) / max(len(matched), 1), 4),
            "matched_avg_recovery_sec": round(sum(matched_times) / max(len(matched_times), 1), 4),
            "unmatched_avg_recovery_sec": round(sum(unmatched_times) / max(len(unmatched_times), 1), 4),
            "graph_playbook_rate": round(len(graph_playbook) / max(len(with_playbook), 1), 4),
            "hardcoded_fallback_rate": round(len(hardcoded_fallback) / max(len(with_playbook), 1), 4),
            "total": total,
        }

    async def update_hitl_policy(self, patch: dict, operator: str = "operator", role: str = "operator"):
        """HITL 정책을 런타임에서 업데이트한다."""
        prev_policy = dict(self.hitl_policy)
        if role != "supervisor":
            self._append_hitl_audit(
                "policy_update_denied",
                operator,
                {"reason": "supervisor_required", "patch": patch or {}},
                role=role,
            )
            await self._emit("hitl_policy_update_denied", {"reason": "supervisor_required", "operator": operator, "role": role})
            return dict(self.hitl_policy)

        def _clip(v, lo, hi):
            try:
                f = float(v)
            except Exception:
                f = lo
            return max(lo, min(hi, f))

        if "min_confidence" in patch:
            self.hitl_policy["min_confidence"] = _clip(patch.get("min_confidence"), 0.3, 0.95)
        if "high_risk_threshold" in patch:
            self.hitl_policy["high_risk_threshold"] = _clip(patch.get("high_risk_threshold"), 0.3, 0.95)
        if "medium_requires_history" in patch:
            self.hitl_policy["medium_requires_history"] = bool(patch.get("medium_requires_history"))

        self._append_hitl_audit(
            "policy_updated",
            operator,
            {
                "prev": prev_policy,
                "next": dict(self.hitl_policy),
                "diff": self._policy_diff(prev_policy, self.hitl_policy),
            },
            role=role,
        )
        update_active_policy(self.conn, self.hitl_policy)
        self._persist_hitl_runtime_state()
        await self._emit(
            "hitl_policy_updated",
            {
                "policy": dict(self.hitl_policy),
                "prev_policy": prev_policy,
                "diff": self._policy_diff(prev_policy, self.hitl_policy),
                "operator": operator,
                "role": role,
            },
        )
        return dict(self.hitl_policy)

    async def route_intent(self, intent: str, payload: dict | None = None):
        """Hybrid orchestrator-style intent routing."""
        p = payload or {}
        intent_key = (intent or "").strip().lower()
        if intent_key in ("nl_diagnose", "diagnose_query", "ask_why"):
            q = str(p.get("query", ""))
            result = self.nl_diagnoser.analyze(self.conn, q)
            return await self._emit_route_trace(intent_key, "NaturalLanguageDiagnoser", result)
        if intent_key in ("predictive_priority", "rul", "maintenance_priority"):
            limit = int(p.get("limit", 5) or 5)
            result = self.predictive_agent.rank_rul_risks_v1(self.conn, limit=max(1, min(20, limit)))
            return await self._emit_route_trace(intent_key, "PredictiveAgent", result)
        if intent_key in ("healing_status", "status"):
            result = self.get_state().get("healing", {})
            return await self._emit_route_trace(intent_key, "SelfHealingEngine", result)
        if intent_key in ("explain_step",):
            step_id = str(p.get("step_id", ""))
            incidents = [x for x in self.healing_history if x.get("step_id") == step_id][-10:]
            result = {
                "step_id": step_id,
                "recent_incidents": incidents,
                "summary": self.nl_diagnoser.analyze(self.conn, f"{step_id} 최근 이슈 원인과 재발 리스크 요약"),
            }
            return await self._emit_route_trace(intent_key, "Hybrid(History+NL)", result)
        result = {"intent": intent_key, "delegated_to": "none", "error": "unsupported_intent"}
        await self._emit("orchestrator_trace", {"intent": intent_key, "delegated_to": "none", "ok": False})
        return result

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
        return {
            "intent": intent,
            "delegated_to": delegated_to,
            "result": result,
        }

    def evaluate_policy_variants(self):
        """Offline replay-style policy sweep on recorded incidents."""
        incidents = self.healing_history[-300:]
        if not incidents:
            return {"variants": [], "base_total": 0}
        variants = []
        for conf in (0.55, 0.62, 0.7, 0.78):
            for risk in (0.5, 0.6, 0.7):
                hitl = 0
                auto = 0
                for inc in incidents:
                    c = float(inc.get("confidence", 0.0) or 0.0)
                    rname = str(inc.get("risk_level", "MEDIUM"))
                    rnum = RISK_NUMERIC.get(rname, 0.5)
                    hmatched = bool(inc.get("history_matched", False))
                    if c < conf or rnum >= risk or (rnum >= 0.3 and not hmatched):
                        hitl += 1
                    else:
                        auto += 1
                variants.append({
                    "min_confidence": conf,
                    "high_risk_threshold": risk,
                    "hitl_rate": round(hitl / max(len(incidents), 1), 4),
                    "auto_rate": round(auto / max(len(incidents), 1), 4),
                    "sample": len(incidents),
                })
        variants.sort(key=lambda x: (x["hitl_rate"], -x["auto_rate"]))
        return {"variants": variants[:12], "base_total": len(incidents)}

    def _append_hitl_audit(
        self,
        action: str,
        operator: str,
        detail: dict | None = None,
        role: str = "operator",
    ):
        self.hitl_audit.append({
            "ts": datetime.now().isoformat(),
            "action": action,
            "operator": operator,
            "role": role,
            "detail": detail or {},
        })
        self.hitl_audit = self.hitl_audit[-200:]

    @staticmethod
    def _policy_diff(prev: dict, nxt: dict):
        keys = ("min_confidence", "high_risk_threshold", "medium_requires_history")
        out = {}
        for k in keys:
            pv = prev.get(k)
            nv = nxt.get(k)
            if pv != nv:
                out[k] = {"from": pv, "to": nv}
        return out

    def _persist_hitl_runtime_state(self):
        try:
            os.makedirs(self.results_dir, exist_ok=True)
            path = os.path.join(self.results_dir, "hitl_runtime_state.json")
            payload = {
                "policy": dict(self.hitl_policy),
                "pending": self.hitl_pending[-200:],
                "audit": self.hitl_audit[-500:],
                "updated_at": datetime.now().isoformat(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_hitl_runtime_state(self):
        try:
            path = os.path.join(self.results_dir, "hitl_runtime_state.json")
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            policy = payload.get("policy", {})
            if isinstance(policy, dict):
                self.hitl_policy.update({
                    "min_confidence": float(policy.get("min_confidence", self.hitl_policy["min_confidence"])),
                    "high_risk_threshold": float(policy.get("high_risk_threshold", self.hitl_policy["high_risk_threshold"])),
                    "medium_requires_history": bool(policy.get("medium_requires_history", self.hitl_policy["medium_requires_history"])),
                })
            pending = payload.get("pending", [])
            audit = payload.get("audit", [])
            if isinstance(pending, list):
                self.hitl_pending = pending[-200:]
            if isinstance(audit, list):
                self.hitl_audit = audit[-500:]
        except Exception:
            pass
