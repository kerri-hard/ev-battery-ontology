"""상태 집계/영속화/KPI 믹스인 — get_state, L3 trend, 케이스 분석, 정책 sweep."""
import json
import os
from datetime import datetime

from v4.healing_agents import RISK_NUMERIC


class StateMixin:
    """엔진 상태 집계, 영속화, 운영 메트릭 산출."""

    def get_state(self):
        """현재 엔진 상태를 반환한다 (v3 + v4)."""
        state = super().get_state()
        state["healing"] = {
            "iteration": self.healing_iteration,
            "running": self.healing_running,
            "incidents": len(self.healing_history),
            "auto_recovered": sum(1 for h in self.healing_history if h.get("auto_recovered")),
            "counters": dict(self.healing_counters),
            "recent_incidents": self.healing_history[-5:],
            "recurrence_kpis": self._compute_recurrence_kpis(),
            "hitl_pending": self.hitl_pending[-20:],
            "hitl_audit": self.hitl_audit[-30:],
            "hitl_policy": dict(self.hitl_policy),
        }
        state["phase4"] = {
            "predictive_agent": self.predictive_agent is not None,
            "nl_diagnoser": self.nl_diagnoser is not None,
            "llm_orchestrator": bool(self.llm_orchestrator and self.llm_orchestrator.enabled),
            "llm_orchestrator_status": self.llm_orchestrator.get_status() if self.llm_orchestrator else {},
            "model": self.nl_diagnoser.get_status().get("model") if self.nl_diagnoser else "none",
            "latest_predictive": self.latest_predictive[:5],
            "weibull_rul": self.latest_weibull_rul[:5],
            "orchestrator_traces": self.orchestrator_traces[-20:],
            "causal_discovery": self.causal_discovery.get_status() if self.causal_discovery else {},
            "evolution_agent": self.evolution_agent.get_status() if self.evolution_agent else {},
        }
        state["industry_modules"] = {
            "advanced_detection": self.advanced_detector.get_status() if self.advanced_detector else {},
            "traceability": self.traceability.get_batch_stats(self.conn) if self.traceability else {},
            "sensor_bridge": self.sensor_bridge.get_status() if self.sensor_bridge else {},
            "event_bus": self.event_bus.get_stats() if self.event_bus else {},
        }
        state["l3_trends"] = self.l3_trend_history[-30:]
        state["l3_snapshot"] = dict(self.latest_l3_snapshot) if self.latest_l3_snapshot else {}
        return state

    # ── L3 trend persistence ──────────────────────

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
            with open(os.path.join(self.results_dir, "l3_trend_latest.json"), "w", encoding="utf-8") as f:
                json.dump(self.latest_l3_snapshot, f, ensure_ascii=False, indent=2)
            with open(os.path.join(self.results_dir, "l3_trend_history.json"), "w", encoding="utf-8") as f:
                json.dump(self.l3_trend_history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── Healing summary ──────────────────────────

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
            with open(os.path.join(self.results_dir, "self_healing_v4_latest.json"), "w", encoding="utf-8") as f:
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
                return float(v) if v is not None else None
        except Exception:
            pass
        return None

    def _get_step_safety_level(self, step_id: str) -> str:
        """ProcessStep의 safety_level. 실패 시 기본값 'C'."""
        try:
            r = self.conn.execute(
                "MATCH (ps:ProcessStep) WHERE ps.id=$id RETURN ps.safety_level",
                {"id": step_id},
            )
            if r.has_next():
                return r.get_next()[0] or "C"
        except Exception:
            pass
        return "C"

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
        repeat_count = len(keys) - len(set(keys))
        matched_auto = [x for x in matched if x.get("auto_recovered")]
        matched_times = [float(x.get("recovery_time_sec")) for x in matched if isinstance(x.get("recovery_time_sec"), (int, float))]
        unmatched = [x for x in incidents if not x.get("history_matched")]
        unmatched_times = [float(x.get("recovery_time_sec")) for x in unmatched if isinstance(x.get("recovery_time_sec"), (int, float))]
        with_playbook = [x for x in incidents if x.get("playbook_source")]
        graph_playbook = [x for x in with_playbook if str(x.get("playbook_source", "")).startswith("graph")]
        hardcoded_fallback = [x for x in with_playbook if str(x.get("playbook_source", "")) == "hardcoded"]
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

    def evaluate_policy_variants(self):
        """녹화된 인시던트에서 오프라인 replay로 정책 sweep을 수행한다."""
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
