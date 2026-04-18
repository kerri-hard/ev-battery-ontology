"""
Phase 4 agents: PredictiveAgent + NaturalLanguageDiagnoser.

This module adds practical "LLM-style" analysis capabilities without requiring
external API keys, while keeping interfaces ready for future real LLM wiring.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime



class PredictiveAgent:
    """Estimate equipment/step risk and rough RUL for maintenance planning.

    업계 참조:
      - Uptake/Samsara: Weibull 생존분석 기반 fleet-level RUL
      - ABB Ability: Bayesian Weibull update
      - NASA C-MAPSS: Transformer 기반 RUL (향후 Phase 3)
    """

    def rank_rul_risks(self, conn, limit: int = 5):
        rows = []
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep)-[:USES_EQUIPMENT]->(eq:Equipment) "
                "OPTIONAL MATCH (inc:Incident) WHERE inc.step_id = ps.id "
                "RETURN ps.id, ps.name, eq.id, eq.name, eq.mtbf_hours, eq.mttr_hours, count(inc)"
            )
            while r.has_next():
                row = r.get_next()
                step_id = row[0]
                step_name = row[1]
                eq_id = row[2]
                eq_name = row[3]
                mtbf = float(row[4]) if row[4] is not None else 2000.0
                mttr = float(row[5]) if row[5] is not None else 4.0
                incidents = int(row[6]) if row[6] is not None else 0

                # Simple risk model: lower MTBF + more incidents => higher risk.
                mtbf_risk = max(0.05, min(0.95, (5000.0 - mtbf) / 5000.0))
                incident_risk = min(0.6, incidents * 0.08)
                risk_score = max(0.05, min(0.99, mtbf_risk * 0.7 + incident_risk * 0.3))

                # Approximate RUL in hours (heuristic, configurable later).
                rul_hours = max(24.0, mtbf * (1.0 - risk_score) * 0.6)

                rows.append(
                    {
                        "step_id": step_id,
                        "step_name": step_name,
                        "equipment_id": eq_id,
                        "equipment_name": eq_name,
                        "mtbf_hours": round(mtbf, 1),
                        "mttr_hours": round(mttr, 1),
                        "incident_count": incidents,
                        "risk_score": round(risk_score, 3),
                        "rul_hours": round(rul_hours, 1),
                        "priority": self._priority(risk_score, rul_hours),
                    }
                )
        except Exception:
            return []

        rows.sort(key=lambda x: (-x["risk_score"], x["rul_hours"]))
        return rows[: max(1, limit)]

    def rank_rul_risks_v1(self, conn, limit: int = 5):
        """Feature-based RUL v1 (incidents + alarms + sensor variance + incident recency).

        Steps with more past incidents get lower RUL scores.  Recent incidents
        (resolved=False) weigh more heavily than old resolved ones.
        """
        base = self.rank_rul_risks(conn, limit=max(10, limit * 3))
        out = []
        for row in base:
            step_id = row.get("step_id")
            if not step_id:
                continue
            alarm_count = self._count_recent_alarms(conn, step_id, n=40)
            # 온톨로지 경로 기반 분산을 우선 사용, 0이면 기존 방식 폴백
            variance = self._compute_sensor_variance(conn, step_id)
            if variance == 0.0:
                variance = self._estimate_sensor_variance(conn, step_id, n=40)
            incident_count = int(row.get("incident_count", 0) or 0)
            base_risk = float(row.get("risk_score", 0.1) or 0.1)

            # New: count unresolved incidents (higher weight)
            unresolved_count = self._count_unresolved_incidents(conn, step_id)

            alarm_component = min(0.35, alarm_count * 0.04)
            variance_component = min(0.3, variance * 0.12)
            incident_component = min(0.25, incident_count * 0.05)
            # Unresolved incidents are a strong degradation signal
            unresolved_component = min(0.30, unresolved_count * 0.10)

            risk_score = max(0.05, min(0.99,
                base_risk * 0.35
                + alarm_component
                + variance_component
                + incident_component
                + unresolved_component
            ))
            mtbf = float(row.get("mtbf_hours", 2000.0) or 2000.0)
            # Heavier penalty: more incidents = shorter RUL
            incident_penalty = max(0.5, 1.0 - incident_count * 0.04)
            rul_hours = max(12.0, mtbf * (1.0 - risk_score) * 0.55 * incident_penalty)
            out.append(
                {
                    **row,
                    "model_version": "rul_feature_v1.1",
                    "features": {
                        "base_risk": round(base_risk, 3),
                        "alarm_count_recent": alarm_count,
                        "sensor_variance_recent": round(variance, 4),
                        "incident_count": incident_count,
                        "unresolved_incidents": unresolved_count,
                    },
                    "risk_score": round(risk_score, 3),
                    "rul_hours": round(rul_hours, 1),
                    "priority": self._priority(risk_score, rul_hours),
                }
            )
        out.sort(key=lambda x: (-x["risk_score"], x["rul_hours"]))
        return out[: max(1, limit)]

    @staticmethod
    def _count_unresolved_incidents(conn, step_id: str) -> int:
        """Count incidents for this step that were not auto-recovered."""
        try:
            r = conn.execute(
                "MATCH (inc:Incident) WHERE inc.step_id=$sid AND inc.auto_recovered=false "
                "RETURN count(inc)",
                {"sid": step_id},
            )
            if r.has_next():
                return int(r.get_next()[0] or 0)
        except Exception:
            pass
        return 0

    @staticmethod
    def _count_recent_alarms(conn, step_id: str, n: int = 40) -> int:
        try:
            r = conn.execute(
                "MATCH (a:Alarm) WHERE a.step_id=$sid RETURN count(a)",
                {"sid": step_id},
            )
            if r.has_next():
                return int(r.get_next()[0] or 0)
        except Exception:
            pass
        return 0

    @staticmethod
    def _estimate_sensor_variance(conn, step_id: str, n: int = 40) -> float:
        vals = []
        try:
            r = conn.execute(
                "MATCH (sr:SensorReading) WHERE sr.step_id=$sid "
                "RETURN sr.value LIMIT $n",
                {"sid": step_id, "n": int(max(5, n))},
            )
            while r.has_next():
                row = r.get_next()
                if row[0] is not None:
                    vals.append(float(row[0]))
        except Exception:
            return 0.0
        if len(vals) < 5:
            return 0.0
        mean = sum(vals) / len(vals)
        var = sum((x - mean) ** 2 for x in vals) / len(vals)
        return var

    @staticmethod
    def _compute_sensor_variance(conn, step_id: str) -> float:
        """최근 센서 읽기값의 분산을 계산한다.

        온톨로지의 USES_EQUIPMENT → HAS_READING 경로를 사용하여
        해당 공정에 연결된 장비의 최근 센서 데이터 분산을 구한다.
        """
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep)-[:USES_EQUIPMENT]->(eq:Equipment)-[:HAS_READING]->(sr:SensorReading) "
                "WHERE ps.id = $id "
                "RETURN sr.value ORDER BY sr.timestamp DESC LIMIT 20",
                {"id": step_id})
            values = []
            while r.has_next():
                v = r.get_next()[0]
                if v is not None:
                    values.append(float(v))
            if len(values) < 3:
                return 0.0
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            return round(variance, 4)
        except Exception:
            return 0.0

    @staticmethod
    def _priority(risk_score: float, rul_hours: float) -> str:
        if risk_score >= 0.75 or rul_hours <= 72:
            return "P1"
        if risk_score >= 0.5 or rul_hours <= 168:
            return "P2"
        return "P3"


class NaturalLanguageDiagnoser:
    """Analyze free-text issue queries using ontology + incident history."""

    STEP_RE = re.compile(r"PS-\d{3}", re.IGNORECASE)

    def __init__(self):
        self.api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        self.model = (os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()
        self.llm_enabled = bool(self.api_key) and os.getenv("LLM_USE_OPENAI", "1") != "0"

    def analyze(self, conn, query: str):
        q = (query or "").strip()
        if not q:
            return {"error": "query is empty"}

        step_id = self._extract_step_id(q)
        incidents = self._fetch_incidents(conn, step_id=step_id, limit=10)
        if step_id and not incidents:
            # step-specific 기록이 없으면 최근 전역 사례를 사용해 답변 공백을 줄인다.
            incidents = self._fetch_incidents(conn, step_id=None, limit=10)
        top_causes = self._aggregate_causes(incidents)
        related_rules = self._fetch_related_rules(conn, top_causes, limit=6)
        context = self._build_context(step_id, incidents, related_rules)

        llm_result = None
        if self.llm_enabled:
            llm_result = self._analyze_with_openai(q, context)
        if llm_result:
            hypotheses = self._sanitize_hypotheses(llm_result.get("hypotheses", []))
            recommendations = self._sanitize_recommendations(llm_result.get("recommendations", []))
            mode = "openai_llm"
        else:
            hypotheses = []
            default_refs = self._build_default_refs(incidents, related_rules)
            for cause, count in top_causes[:3]:
                hypotheses.append(
                    {
                        "cause_type": cause,
                        "support_cases": count,
                        "confidence": round(min(0.92, 0.55 + count * 0.08), 3),
                        "reasoning": f"최근 유사 이슈에서 '{cause}'가 {count}회 확인됨",
                        "evidence_refs": default_refs[:4],
                    }
                )
            recommendations = self._build_recommendations(hypotheses)
            mode = "symbolic_llm_style"

        return {
            "query": q,
            "step_id": step_id,
            "analysis_mode": mode,
            "model": self.model if self.llm_enabled else "none",
            "timestamp": datetime.now().isoformat(),
            "incidents_considered": len(incidents),
            "hypotheses": hypotheses,
            "related_rules": related_rules,
            "recommendations": recommendations,
        }

    def get_status(self):
        return {
            "llm_enabled": self.llm_enabled,
            "model": self.model if self.llm_enabled else "none",
        }

    def _extract_step_id(self, query: str):
        m = self.STEP_RE.search(query or "")
        return m.group(0).upper() if m else None

    def _fetch_incidents(self, conn, step_id=None, limit=10):
        try:
            if step_id:
                r = conn.execute(
                    "MATCH (inc:Incident) WHERE inc.step_id=$sid "
                    "RETURN inc.id, inc.step_id, inc.root_cause, inc.recovery_action, inc.auto_recovered, inc.timestamp "
                    "ORDER BY inc.timestamp DESC LIMIT $n",
                    {"sid": step_id, "n": int(limit)},
                )
            else:
                r = conn.execute(
                    "MATCH (inc:Incident) "
                    "RETURN inc.id, inc.step_id, inc.root_cause, inc.recovery_action, inc.auto_recovered, inc.timestamp "
                    "ORDER BY inc.timestamp DESC LIMIT $n",
                    {"n": int(limit)},
                )
            out = []
            while r.has_next():
                row = r.get_next()
                out.append(
                    {
                        "id": row[0],
                        "step_id": row[1],
                        "root_cause": row[2] or "unknown",
                        "recovery_action": row[3] or "unknown",
                        "auto_recovered": bool(row[4]),
                        "timestamp": row[5],
                    }
                )
            return out
        except Exception:
            return []

    @staticmethod
    def _aggregate_causes(incidents):
        counts = {}
        for inc in incidents:
            c = inc.get("root_cause") or "unknown"
            counts[c] = counts.get(c, 0) + 1
        return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)

    def _fetch_related_rules(self, conn, top_causes, limit=6):
        rules = []
        for cause, _ in top_causes[:3]:
            try:
                r = conn.execute(
                    "MATCH (cr:CausalRule) "
                    "WHERE cr.cause_type=$cause OR cr.effect_type=$cause "
                    "RETURN cr.id, cr.name, cr.cause_type, cr.effect_type, cr.strength, cr.confirmation_count "
                    "ORDER BY cr.confirmation_count DESC, cr.strength DESC LIMIT $n",
                    {"cause": cause, "n": int(limit)},
                )
                while r.has_next():
                    row = r.get_next()
                    rules.append(
                        {
                            "id": row[0],
                            "name": row[1],
                            "cause_type": row[2],
                            "effect_type": row[3],
                            "strength": float(row[4]) if row[4] is not None else 0.5,
                            "confirmations": int(row[5]) if row[5] is not None else 0,
                        }
                    )
            except Exception:
                continue
        # dedupe by id
        dedup = {}
        for rr in rules:
            dedup[rr["id"]] = rr
        return list(dedup.values())[:limit]

    @staticmethod
    def _build_context(step_id, incidents, rules):
        return {
            "step_id": step_id,
            "recent_incidents": incidents[:8],
            "causal_rules": rules[:6],
        }

    def _analyze_with_openai(self, query: str, context: dict):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "hypotheses": {
                    "type": "array",
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "cause_type": {"type": "string"},
                            "confidence": {"type": "number"},
                            "reasoning": {"type": "string"},
                            "evidence_refs": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 6,
                            },
                        },
                        "required": ["cause_type", "confidence", "reasoning", "evidence_refs"],
                    },
                },
                "recommendations": {
                    "type": "array",
                    "maxItems": 5,
                    "items": {"type": "string"},
                },
            },
            "required": ["hypotheses", "recommendations"],
        }
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a manufacturing fault diagnosis assistant. "
                                "Use only given context. "
                                "If evidence is weak, lower confidence. "
                                "Never output commands that alter real machinery. "
                                "Return concise Korean output in the required JSON schema."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"질문: {query}\n\n컨텍스트(JSON): {json.dumps(context, ensure_ascii=False)}",
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "diagnosis",
                    "strict": True,
                    "schema": schema,
                }
            },
            "max_output_tokens": 700,
        }

        req = urllib.request.Request(
            url="https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            text = body.get("output_text")
            if not text:
                text = self._extract_output_text(body)
            if not text:
                return None
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_output_text(body: dict):
        output = body.get("output", [])
        for item in output:
            content = item.get("content", [])
            for c in content:
                txt = c.get("text")
                if txt:
                    return txt
        return None

    @staticmethod
    def _sanitize_hypotheses(hypotheses):
        clean = []
        for h in hypotheses[:5]:
            if not isinstance(h, dict):
                continue
            cause = str(h.get("cause_type", "unknown"))[:80]
            try:
                conf = float(h.get("confidence", 0.5))
            except (TypeError, ValueError):
                conf = 0.5
            conf = max(0.0, min(0.99, conf))
            reasoning = str(h.get("reasoning", ""))[:240]
            clean.append(
                {
                    "cause_type": cause or "unknown",
                    "support_cases": 0,
                    "confidence": round(conf, 3),
                    "reasoning": reasoning or "컨텍스트 기반 추정",
                    "evidence_refs": NaturalLanguageDiagnoser._sanitize_evidence_refs(h.get("evidence_refs", [])),
                }
            )
        return clean

    @staticmethod
    def _sanitize_recommendations(recommendations):
        out = []
        seen = set()
        for rec in recommendations[:8]:
            text = str(rec).strip()[:140]
            if text and text not in seen:
                seen.add(text)
                out.append(text)
            if len(out) >= 5:
                break
        return out

    @staticmethod
    def _build_recommendations(hypotheses):
        recs = []
        for h in hypotheses:
            cause = h["cause_type"]
            if cause == "equipment_mtbf":
                recs.append("설비 상태 점검 및 예방정비 일정을 앞당기세요.")
                recs.append("동일 Step의 MTBF/MTTR 추세를 확인하고 고장 전 징후를 재학습하세요.")
            elif cause == "material_anomaly":
                recs.append("자재 LOT 변경 이력 및 입고 검사 결과를 우선 점검하세요.")
            elif cause == "upstream_degradation":
                recs.append("상류 공정의 수율/OEE 회복 후 하류 공정을 재평가하세요.")
            else:
                recs.append(f"원인 후보 '{cause}' 관련 playbook을 우선 실행하세요.")
        # preserve order, dedupe
        out = []
        seen = set()
        for x in recs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out[:5]

    @staticmethod
    def _build_default_refs(incidents, related_rules):
        refs = []
        for inc in incidents[:4]:
            if inc.get("id"):
                refs.append(f"Incident:{inc['id']}")
        for rr in related_rules[:4]:
            if rr.get("id"):
                refs.append(f"CausalRule:{rr['id']}")
        # dedupe keep order
        out = []
        seen = set()
        for r in refs:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out[:6]

    @staticmethod
    def _sanitize_evidence_refs(refs):
        out = []
        seen = set()
        if not isinstance(refs, list):
            return out
        for r in refs[:10]:
            s = str(r).strip()[:80]
            if s and s not in seen:
                seen.add(s)
                out.append(s)
            if len(out) >= 6:
                break
        return out

