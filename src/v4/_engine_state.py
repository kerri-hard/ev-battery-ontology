"""상태 집계/영속화/KPI 믹스인 — get_state, L3 trend, 케이스 분석, 정책 sweep."""
import json
import os
from datetime import datetime

from v4.healing_agents import RISK_NUMERIC


def _percentile(values: list, pct: float) -> float:
    """단순 percentile (numpy 의존성 없이). 빈 리스트면 0."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    if lo == hi:
        return s[lo]
    frac = k - lo
    return s[lo] * (1 - frac) + s[hi] * frac


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
        state["preverify"] = self._preverify_state_block()
        state["recurrence"] = self._recurrence_state_block()
        state["slo"] = self._slo_state_block()
        state["l3_trends"] = self.l3_trend_history[-30:]
        state["l3_snapshot"] = dict(self.latest_l3_snapshot) if self.latest_l3_snapshot else {}
        return state

    def _preverify_state_block(self) -> dict:
        """PRE-VERIFY 페이즈 메트릭: 예측 정확도 + auto-reject 누적."""
        history = getattr(self, "preverify_accuracy_history", []) or []
        counters = getattr(self, "preverify_counters", {"plans_total": 0, "auto_rejected_total": 0})

        recent = history[-30:]
        if recent:
            mae = sum(s["abs_error"] for s in recent) / len(recent)
            sign_matches = sum(1 for s in recent if s["sign_match"])
            sign_accuracy = sign_matches / len(recent)
        else:
            mae = 0.0
            sign_accuracy = 0.0

        plans_total = counters.get("plans_total", 0)
        rejected_total = counters.get("auto_rejected_total", 0)
        return {
            "mae_recent": round(mae, 6),
            "sign_accuracy_recent": round(sign_accuracy, 4),
            "samples_recent": len(recent),
            "auto_rejected_total": rejected_total,
            "plans_total": plans_total,
            "auto_reject_rate": round(rejected_total / plans_total, 4) if plans_total else 0.0,
            "recent_predictions": recent[-10:],
            "current_thresholds": dict(getattr(self, "preverify_thresholds", {})),
            "thresholds_history": list(getattr(self, "preverify_thresholds_history", [])),
        }

    # ── SLO/SLI ─────────────────────────────────
    # SRE 스타일: 각 ProcessStep을 microservice로 보고 incidents → SLI 집계.
    # SLO 미달 시 error budget burn 가시화.

    # SLI 정의 + SLO 목표값 (display + 계산 동시에 사용)
    SLO_TARGETS = {
        "auto_recovery_rate": {
            "name": "자동 복구 성공률",
            "description": "auto_recovered / total_incidents",
            "data_source": "healing_history.auto_recovered",
            "target": 0.95,
            "higher_is_better": True,
            "unit": "ratio",
        },
        "p95_recovery_latency": {
            "name": "복구 지연 p95",
            "description": "recovery_time_sec 95퍼센타일 (sim time)",
            "data_source": "healing_history.recovery_time_sec",
            "target": 0.05,
            "higher_is_better": False,
            "unit": "sec",
        },
        "yield_compliance": {
            "name": "수율 준수율",
            "description": "yield_rate ≥ 0.99 인 step 비율",
            "data_source": "ProcessStep.yield_rate",
            "target": 0.95,
            "higher_is_better": True,
            "unit": "ratio",
        },
        "hitl_rate": {
            "name": "HITL 에스컬레이션율",
            "description": "hitl_required / total_incidents",
            "data_source": "healing_history.hitl_required",
            "target": 0.05,
            "higher_is_better": False,
            "unit": "ratio",
        },
        "repeat_rate": {
            "name": "재발률 (학습 SLI)",
            "description": "동일 시그니처 재발 incidents / total",
            "data_source": "recurrence_kpis.repeat_incident_rate",
            "target": 0.25,
            "higher_is_better": False,
            "unit": "ratio",
        },
    }

    def _slo_state_block(self) -> dict:
        """incidents 집계 → step/area별 SLI + global SLO + error budget."""
        incidents = self.healing_history
        per_step = self._compute_per_step_sli(incidents)
        per_area = self._compute_per_area_sli(per_step)
        global_sli = self._compute_global_sli(incidents)
        violations = self._compute_slo_violations(global_sli, per_step)
        return {
            "definitions": self.SLO_TARGETS,
            "global": global_sli,
            "per_step": per_step,
            "per_area": per_area,
            "violations": violations,
        }

    def _compute_per_step_sli(self, incidents: list) -> list:
        """step_id별로 incidents 그룹핑 후 SLI 계산."""
        from collections import defaultdict
        bucket = defaultdict(list)
        for inc in incidents:
            sid = inc.get("step_id")
            if sid:
                bucket[sid].append(inc)

        out = []
        for step_id, sub in bucket.items():
            n = len(sub)
            auto = sum(1 for x in sub if x.get("auto_recovered"))
            hitl = sum(1 for x in sub if x.get("hitl_required"))
            improved = sum(1 for x in sub if x.get("improved"))
            times = [float(x.get("recovery_time_sec") or 0.0) for x in sub if x.get("recovery_time_sec") is not None]
            sevs = [x.get("severity") for x in sub if x.get("severity")]

            current_yield = self._get_step_yield(step_id) or 0.0
            area_id = self._get_step_area(step_id)

            out.append({
                "step_id": step_id,
                "area_id": area_id,
                "incident_count": n,
                "auto_recovery_rate": round(auto / n, 4) if n else 0.0,
                "hitl_rate": round(hitl / n, 4) if n else 0.0,
                "improvement_rate": round(improved / n, 4) if n else 0.0,
                "p50_recovery_sec": round(_percentile(times, 50), 4) if times else 0.0,
                "p95_recovery_sec": round(_percentile(times, 95), 4) if times else 0.0,
                "current_yield": round(current_yield, 4),
                "yield_meets_slo": current_yield >= 0.99,
                "severity_dist": {s: sevs.count(s) for s in set(sevs)},
                "error_budget_remaining": round(
                    max(0.0, 1.0 - (auto / n if n else 0.0) - (1.0 - 0.95)), 4
                ),
            })
        out.sort(key=lambda x: -x["incident_count"])
        return out

    def _compute_per_area_sli(self, per_step: list) -> list:
        """ProcessArea별 SLI roll-up (step들의 가중 평균)."""
        from collections import defaultdict
        groups = defaultdict(list)
        for s in per_step:
            aid = s.get("area_id")
            if aid:
                groups[aid].append(s)
        out = []
        for area_id, steps in groups.items():
            total_inc = sum(s["incident_count"] for s in steps)
            if total_inc == 0:
                continue
            auto_weighted = sum(s["auto_recovery_rate"] * s["incident_count"] for s in steps) / total_inc
            hitl_weighted = sum(s["hitl_rate"] * s["incident_count"] for s in steps) / total_inc
            yield_meets = sum(1 for s in steps if s["yield_meets_slo"]) / len(steps)
            out.append({
                "area_id": area_id,
                "step_count": len(steps),
                "total_incidents": total_inc,
                "auto_recovery_rate": round(auto_weighted, 4),
                "hitl_rate": round(hitl_weighted, 4),
                "yield_compliance_rate": round(yield_meets, 4),
            })
        out.sort(key=lambda x: x["area_id"])
        return out

    def _compute_global_sli(self, incidents: list) -> dict:
        """전체 시스템 SLI — 단일 microservice 집합으로서의 platform SLI."""
        n = len(incidents)
        if n == 0:
            return {sli: 0.0 for sli in self.SLO_TARGETS}

        auto = sum(1 for x in incidents if x.get("auto_recovered"))
        hitl = sum(1 for x in incidents if x.get("hitl_required"))
        times = [float(x.get("recovery_time_sec") or 0.0) for x in incidents if x.get("recovery_time_sec") is not None]
        kpis = self._compute_recurrence_kpis()

        # yield_compliance: 전체 step 중 yield ≥ 0.99 비율
        yield_meets = 0
        total_steps = 0
        try:
            r = self.conn.execute("MATCH (ps:ProcessStep) RETURN ps.yield_rate")
            while r.has_next():
                yield_rate = r.get_next()[0]
                if yield_rate is not None:
                    total_steps += 1
                    if float(yield_rate) >= 0.99:
                        yield_meets += 1
        except Exception:
            pass

        return {
            "auto_recovery_rate": round(auto / n, 4),
            "p95_recovery_latency": round(_percentile(times, 95), 4) if times else 0.0,
            "p50_recovery_latency": round(_percentile(times, 50), 4) if times else 0.0,
            "yield_compliance": round(yield_meets / max(total_steps, 1), 4),
            "hitl_rate": round(hitl / n, 4),
            "repeat_rate": float(kpis.get("repeat_incident_rate", 0.0)),
            "total_incidents": n,
            "total_auto_recovered": auto,
        }

    def _compute_slo_violations(self, global_sli: dict, per_step: list) -> list:
        """SLO 미달 항목 + 영향받는 step 리스트."""
        violations = []
        for sli_key, spec in self.SLO_TARGETS.items():
            if sli_key not in global_sli:
                continue
            current = global_sli[sli_key]
            target = spec["target"]
            ok = current >= target if spec["higher_is_better"] else current <= target
            if ok:
                continue
            # 영향 step (per_step에 해당 SLI 가시화 가능 시)
            affected_steps = []
            if sli_key == "auto_recovery_rate":
                affected_steps = [s["step_id"] for s in per_step if s["auto_recovery_rate"] < target][:5]
            elif sli_key == "hitl_rate":
                affected_steps = [s["step_id"] for s in per_step if s["hitl_rate"] > target][:5]
            elif sli_key == "yield_compliance":
                affected_steps = [s["step_id"] for s in per_step if not s["yield_meets_slo"]][:5]
            violations.append({
                "sli": sli_key,
                "name": spec["name"],
                "current": current,
                "target": target,
                "delta": round(current - target, 4),
                "affected_steps": affected_steps,
            })
        return violations

    def _get_step_area(self, step_id: str) -> str:
        try:
            r = self.conn.execute(
                "MATCH (ps:ProcessStep)-[:BELONGS_TO]->(pa:ProcessArea) "
                "WHERE ps.id=$id RETURN pa.id LIMIT 1",
                {"id": step_id},
            )
            if r.has_next():
                return r.get_next()[0] or ""
        except Exception:
            pass
        return ""

    def _recurrence_state_block(self) -> dict:
        """Anti-recurrence tracker — VISION 9.5 가시화. 반복되는 incident signature top-N."""
        tracker = getattr(self, "recurrence_tracker", {}) or {}
        if not tracker:
            return {"total_signatures": 0, "repeating_count": 0, "top_signatures": []}

        items = []
        for sig, rec in tracker.items():
            step, anomaly_type, cause = sig
            items.append({
                "step_id": step,
                "anomaly_type": anomaly_type,
                "cause_type": cause,
                "count": rec["count"],
                "tried_actions": sorted(list(rec["tried_actions"])),
                "last_success": rec["last_success"],
            })
        items.sort(key=lambda x: -x["count"])
        repeating = sum(1 for r in items if r["count"] >= 2)
        return {
            "total_signatures": len(items),
            "repeating_count": repeating,
            "top_signatures": items[:8],
        }

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
                "preverify": self._preverify_state_block(),
                "recurrence": self._recurrence_state_block(),
                "slo": self._slo_state_block(),
                "phase4": {
                    "evolution_agent": self.evolution_agent.get_status() if self.evolution_agent else {},
                    "causal_discovery": self.causal_discovery.get_status() if self.causal_discovery else {},
                    "llm_orchestrator": self.llm_orchestrator.get_status() if self.llm_orchestrator else {},
                },
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
