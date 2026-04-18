"""
LLM Orchestrator — Hybrid Agentic 아키텍처 오케스트레이션 레이어
================================================================
복잡도에 따라 규칙 기반 에이전트와 LLM 추론을 동적으로 전환하는
하이브리드 오케스트레이션 레이어.

학술 근거:
  - Hybrid Agentic AI + Multi-Agent Systems (NAMRC 2026)
    "LLM은 전략적 오케스트레이션에, 경량 에이전트는 에지에서 빠른 실행에"
  - FD-LLM for Equipment Diagnosis (Adv.Eng.Inf., 2025)
  - Toward Autonomous LLM-Based AI Agents for PdM (Applied Sciences, 2025)

의사결정 로직:
  - 단순 이상 (높은 confidence, 알려진 패턴) → 규칙 기반 에이전트만
  - 복잡/미지 이상 (낮은 confidence, 패턴 미매칭, 교차 공정) → LLM 추론
  - 규칙 기반 실패 → LLM 폴백

지원 LLM:
  - Anthropic Claude (api.anthropic.com)
  - OpenAI 호환 API
  - 오프라인 모드: 기존 NaturalLanguageDiagnoser 심볼릭 모드로 폴백
"""
import json
import os
import ssl
import time
import hashlib
import urllib.request
import urllib.error
from datetime import datetime


class LLMOrchestrator:
    """Hybrid Agentic 오케스트레이터.

    anomaly의 복잡도를 평가하여 rule-based vs LLM 경로를 판단하고,
    LLM 호출 시 온톨로지 컨텍스트를 구성하여 정밀한 진단을 수행한다.
    """

    def __init__(self):
        self.enabled = False
        self.provider = "none"  # "anthropic", "openai", "none"
        self.model = ""
        self.api_key = ""
        self.endpoint = ""

        # 판단 임계값 (Hybrid Agentic 활성화율을 현실적 수준으로 조정)
        # 기존 0.50은 스코어링 상한(~0.55)과 너무 가까워 LLM 경로가 실질적으로
        # 활성화되지 않았음 (운영 로그: 26/26 rule-based, 0 LLM).
        self.confidence_threshold = 0.55
        self.complexity_threshold = 0.40
        self.max_cross_for_rule = 2

        # 감사 로그
        self.decision_log: list[dict] = []
        self._max_log = 200

        # 통계
        self._stats = {
            "total_decisions": 0,
            "rule_based": 0,
            "llm": 0,
            "llm_fallback": 0,
            "llm_calls": 0,
            "llm_errors": 0,
            "cache_hits_context": 0,
            "cache_hits_response": 0,
        }

        # 캐시 — 중복 LLM 호출/DB 쿼리 방지 (NAMRC 2026 "지능형 캐싱")
        self._context_cache: dict[str, tuple[float, dict]] = {}
        self._response_cache: dict[str, tuple[float, dict]] = {}
        self._cache_ttl_sec = 300.0  # 5분
        self._cache_max_entries = 128

        self._configure()

    # ── CONFIGURATION ─────────────────────────────────────

    def _configure(self):
        """환경 변수에서 LLM 백엔드를 자동 감지한다."""
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        openai_key = os.environ.get("OPENAI_API_KEY", "")

        if anthropic_key:
            self.enabled = True
            self.provider = "anthropic"
            self.api_key = anthropic_key
            self.model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
            self.endpoint = "https://api.anthropic.com/v1/messages"
        elif openai_key:
            self.enabled = True
            self.provider = "openai"
            self.api_key = openai_key
            self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")
            self.endpoint = os.environ.get(
                "OPENAI_ENDPOINT", "https://api.openai.com/v1/chat/completions"
            )
        else:
            self.enabled = False
            self.provider = "none"

    # ── DECISION: RULE-BASED vs LLM ──────────────────────

    def decide_path(self, anomaly: dict, diagnosis: dict,
                    cross_investigation: dict | None = None) -> dict:
        """anomaly의 복잡도를 평가하여 처리 경로를 결정한다.

        Returns:
            {"path": "rule_based"|"llm"|"llm_fallback",
             "reason": str,
             "complexity_score": float,
             "factors": dict}
        """
        self._stats["total_decisions"] += 1

        # Factor 추출
        candidates = diagnosis.get("candidates", [])
        top_confidence = candidates[0]["confidence"] if candidates else 0.0
        history_matched = diagnosis.get("failure_chain_matched", False)
        candidates_count = len(candidates)
        cross_count = 0
        if cross_investigation and cross_investigation.get("cross_causes"):
            cross_count = len(cross_investigation["cross_causes"])
        causal_chains = diagnosis.get("causal_chains_found", 0)

        factors = {
            "confidence": round(top_confidence, 3),
            "failure_chain_matched": history_matched,
            "cross_process_count": cross_count,
            "candidates_count": candidates_count,
            "causal_chains_found": causal_chains,
        }

        # Complexity score (0.0 ~ 1.0)
        complexity = 0.0
        complexity += 0.30 * (1.0 - top_confidence)  # 낮은 신뢰도 = 높은 복잡도
        complexity += 0.25 * (0.0 if history_matched else 1.0)  # 패턴 미매칭
        complexity += 0.20 * min(1.0, cross_count / max(self.max_cross_for_rule, 1))  # 교차 공정
        complexity += 0.15 * (1.0 if candidates_count < 2 else 0.0)  # 후보 부족
        complexity += 0.10 * (0.0 if causal_chains > 0 else 1.0)  # 인과 체인 없음
        complexity = max(0.0, min(1.0, complexity))

        # 판단
        if not self.enabled:
            path = "rule_based"
            reason = "LLM 미설정 — 규칙 기반 처리"
        elif complexity > self.complexity_threshold:
            path = "llm"
            reason = self._explain_complexity(factors, complexity)
        else:
            path = "rule_based"
            reason = f"충분한 신��도 (complexity={complexity:.2f} < {self.complexity_threshold})"

        self._stats[path] = self._stats.get(path, 0) + 1

        decision = {
            "path": path,
            "reason": reason,
            "complexity_score": round(complexity, 3),
            "factors": factors,
        }

        self._log_decision(decision)
        return decision

    # ── LLM REASONING ─────────────────────────────────────

    async def invoke_llm_reasoning(self, conn, anomaly: dict, diagnosis: dict,
                                    cross_investigation: dict | None = None) -> dict:
        """LLM을 호출하여 복잡한 이상에 대한 추론을 수행한다.

        Returns:
            {"hypotheses": [...], "recommended_actions": [...],
             "reasoning_chain": str, "confidence": float,
             "model": str, "tokens_used": int}
        """
        if not self.enabled:
            return self._symbolic_fallback(anomaly, diagnosis)

        # 응답 캐시 히트 — 동일 step_id+원인+신뢰도 버켓+패턴매칭 상태의
        # 반복 호출은 5분간 캐시된 결과를 재사용한다 (토큰 비용 절감).
        resp_key = self._response_cache_key(anomaly, diagnosis)
        cached_resp = self._cache_get(self._response_cache, resp_key)
        if cached_resp is not None:
            self._stats["cache_hits_response"] += 1
            return {**cached_resp, "from_cache": True}

        self._stats["llm_calls"] += 1

        step_id = anomaly.get("step_id", "")
        candidates = diagnosis.get("candidates", [])
        cause_types = [c.get("cause_type", "") for c in candidates[:5]]

        # 온톨로지 컨텍스트 구축
        context = self._build_ontology_context(conn, step_id, cause_types)

        # 프롬프트 구성
        messages = self._construct_prompt(anomaly, diagnosis, cross_investigation, context)

        # LLM 호출
        try:
            if self.provider == "anthropic":
                raw = await self._call_anthropic(messages)
            elif self.provider == "openai":
                raw = await self._call_openai(messages)
            else:
                return self._symbolic_fallback(anomaly, diagnosis)

            result = self._parse_llm_response(raw)
            result["model"] = self.model
            self._log_decision({"llm_result": result}, llm_result=result)
            self._cache_put(self._response_cache, resp_key, result)
            return result

        except Exception as exc:
            self._stats["llm_errors"] += 1
            return {
                **self._symbolic_fallback(anomaly, diagnosis),
                "llm_error": str(exc),
            }

    # ── ONTOLOGY CONTEXT ──────────────────────────────────

    def _build_ontology_context(self, conn, step_id: str,
                                 cause_types: list[str]) -> dict:
        """LLM에 제공할 온톨로지 컨텍스트를 구축한다. 5분 TTL 캐시."""
        cache_key = f"ctx|{step_id}|{'|'.join(sorted(cause_types[:3]))}"
        cached = self._cache_get(self._context_cache, cache_key)
        if cached is not None:
            self._stats["cache_hits_context"] += 1
            return cached

        context = {
            "step_info": self._load_step_info(conn, step_id),
            "causal_rules": self._load_causal_rules(conn, cause_types),
            "failure_chains": self._load_failure_chains(conn, step_id),
            "recent_incidents": self._load_recent_incidents(conn, step_id),
            "equipment": self._load_equipment_for_step(conn, step_id),
        }

        self._cache_put(self._context_cache, cache_key, context)
        return context

    # ── CONTEXT LOADERS ───────────────────────────────────

    @staticmethod
    def _load_step_info(conn, step_id: str) -> dict:
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep) WHERE ps.id=$id "
                "RETURN ps.name, ps.yield_rate, ps.oee, ps.safety_level, ps.automation_level",
                {"id": step_id},
            )
            if r.has_next():
                row = r.get_next()
                return {
                    "name": row[0], "yield": row[1], "oee": row[2],
                    "safety": row[3], "automation": row[4],
                }
        except Exception:
            pass
        return {}

    @staticmethod
    def _load_causal_rules(conn, cause_types: list[str]) -> list[dict]:
        rules: list[dict] = []
        for cause in cause_types[:3]:
            try:
                r = conn.execute(
                    "MATCH (cr:CausalRule) "
                    "WHERE cr.cause_type=$c OR cr.effect_type=$c "
                    "RETURN cr.id, cr.name, cr.cause_type, cr.effect_type, cr.strength "
                    "LIMIT 5",
                    {"c": cause},
                )
                while r.has_next():
                    row = r.get_next()
                    rules.append({
                        "id": row[0], "name": row[1],
                        "cause": row[2], "effect": row[3],
                        "strength": row[4],
                    })
            except Exception:
                continue
        return rules

    @staticmethod
    def _load_failure_chains(conn, step_id: str) -> list[dict]:
        chains: list[dict] = []
        try:
            r = conn.execute(
                "MATCH (fc:FailureChain) WHERE fc.step_id=$id "
                "RETURN fc.id, fc.cause_sequence, fc.resolution, "
                "fc.success_count, fc.fail_count "
                "ORDER BY fc.success_count DESC LIMIT 5",
                {"id": step_id},
            )
            while r.has_next():
                row = r.get_next()
                chains.append({
                    "id": row[0], "cause": row[1], "resolution": row[2],
                    "successes": row[3], "failures": row[4],
                })
        except Exception:
            pass
        return chains

    @staticmethod
    def _load_recent_incidents(conn, step_id: str) -> list[dict]:
        incidents: list[dict] = []
        try:
            r = conn.execute(
                "MATCH (inc:Incident) WHERE inc.step_id=$id "
                "RETURN inc.id, inc.anomaly_type, inc.top_cause, inc.recovery_action "
                "ORDER BY inc.timestamp DESC LIMIT 5",
                {"id": step_id},
            )
            while r.has_next():
                row = r.get_next()
                incidents.append({
                    "id": row[0], "anomaly": row[1],
                    "cause": row[2], "action": row[3],
                })
        except Exception:
            pass
        return incidents

    @staticmethod
    def _load_equipment_for_step(conn, step_id: str) -> list[dict]:
        equipment: list[dict] = []
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep)-[:USES_EQUIPMENT]->(eq:Equipment) "
                "WHERE ps.id=$id "
                "RETURN eq.id, eq.name, eq.mtbf_hours, eq.mttr_hours",
                {"id": step_id},
            )
            while r.has_next():
                row = r.get_next()
                equipment.append({
                    "id": row[0], "name": row[1],
                    "mtbf": row[2], "mttr": row[3],
                })
        except Exception:
            pass
        return equipment

    # ── LRU-lite CACHE HELPERS ────────────────────────────

    def _cache_get(self, cache: dict, key: str):
        entry = cache.get(key)
        if not entry:
            return None
        ts, value = entry
        if time.time() - ts > self._cache_ttl_sec:
            cache.pop(key, None)
            return None
        return value

    def _cache_put(self, cache: dict, key: str, value):
        cache[key] = (time.time(), value)
        if len(cache) > self._cache_max_entries:
            # 가장 오래된 10개 축출
            oldest = sorted(cache.items(), key=lambda kv: kv[1][0])[:10]
            for k, _ in oldest:
                cache.pop(k, None)

    @staticmethod
    def _response_cache_key(anomaly: dict, diagnosis: dict) -> str:
        step_id = str(anomaly.get("step_id", ""))
        cands = diagnosis.get("candidates", [])
        top = cands[0] if cands else {}
        cause = str(top.get("cause_type", ""))
        # 신뢰도 버켓(0.1 단위)으로 근사 매칭 — 미세한 noise로 캐시 miss 방지
        conf_bucket = round(float(top.get("confidence", 0)) * 10)
        history = "m" if diagnosis.get("failure_chain_matched") else "u"
        raw = f"{step_id}|{cause}|{conf_bucket}|{history}"
        return "resp|" + hashlib.md5(raw.encode()).hexdigest()[:16]

    # ── PROMPT CONSTRUCTION ───────────────────────────────

    def _construct_prompt(self, anomaly: dict, diagnosis: dict,
                          cross_investigation: dict | None,
                          context: dict) -> list[dict]:
        """LLM 프롬프트를 구성한다."""
        system_msg = (
            "You are an expert manufacturing fault diagnosis engineer for EV battery pack production. "
            "You have access to a knowledge graph ontology containing process steps, equipment, "
            "causal rules, and failure chain histories. Analyze the anomaly and provide structured diagnosis.\n\n"
            "Respond in JSON format with these fields:\n"
            '{"hypotheses": [{"cause_type": str, "confidence": float, "reasoning": str}], '
            '"recommended_actions": [{"action": str, "risk_level": str, "priority": int}], '
            '"reasoning_chain": str, "confidence": float}'
        )

        user_parts = [f"## Anomaly\n{json.dumps(anomaly, ensure_ascii=False, default=str)}"]

        if diagnosis.get("candidates"):
            top3 = diagnosis["candidates"][:3]
            user_parts.append(f"## Current Diagnosis Candidates\n{json.dumps(top3, ensure_ascii=False, default=str)}")

        if cross_investigation and cross_investigation.get("cross_causes"):
            user_parts.append(f"## Cross-Process Investigation\n{json.dumps(cross_investigation['cross_causes'][:3], ensure_ascii=False, default=str)}")

        if context.get("step_info"):
            user_parts.append(f"## Process Step Info\n{json.dumps(context['step_info'], ensure_ascii=False, default=str)}")

        if context.get("causal_rules"):
            user_parts.append(f"## Related Causal Rules\n{json.dumps(context['causal_rules'][:5], ensure_ascii=False, default=str)}")

        if context.get("failure_chains"):
            user_parts.append(f"## Failure Chain History\n{json.dumps(context['failure_chains'][:3], ensure_ascii=False, default=str)}")

        if context.get("equipment"):
            user_parts.append(f"## Equipment\n{json.dumps(context['equipment'], ensure_ascii=False, default=str)}")

        user_msg = "\n\n".join(user_parts)

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    # ── LLM API CALLS ─────────────────────────────────────

    async def _call_anthropic(self, messages: list[dict]) -> dict:
        """Anthropic Claude API를 호출한다."""
        system_content = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                user_messages.append(msg)

        body = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_content,
            "messages": user_messages,
        }

        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content_text += block["text"]

        tokens = data.get("usage", {})
        return {
            "text": content_text,
            "tokens_used": tokens.get("input_tokens", 0) + tokens.get("output_tokens", 0),
        }

    async def _call_openai(self, messages: list[dict]) -> dict:
        """OpenAI 호환 API를 호출한다."""
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.3,
        }

        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        choice = data.get("choices", [{}])[0]
        text = choice.get("message", {}).get("content", "")
        tokens = data.get("usage", {}).get("total_tokens", 0)

        return {"text": text, "tokens_used": tokens}

    # ── RESPONSE PARSING ──────────────────────────────────

    def _parse_llm_response(self, raw: dict) -> dict:
        """LLM 응답 텍스트를 구조화된 형식으로 파싱한다."""
        text = raw.get("text", "")
        tokens = raw.get("tokens_used", 0)

        # JSON 블록 추출 시도
        try:
            # ```json ... ``` 또는 { ... } 패턴 찾기
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
                return {
                    "hypotheses": parsed.get("hypotheses", []),
                    "recommended_actions": parsed.get("recommended_actions", []),
                    "reasoning_chain": parsed.get("reasoning_chain", ""),
                    "confidence": parsed.get("confidence", 0.5),
                    "tokens_used": tokens,
                }
        except (json.JSONDecodeError, KeyError):
            pass

        # JSON 파싱 실패 시 텍스트를 가설로 래핑
        return {
            "hypotheses": [{"cause_type": "llm_analysis", "confidence": 0.5, "reasoning": text[:500]}],
            "recommended_actions": [],
            "reasoning_chain": text[:500],
            "confidence": 0.5,
            "tokens_used": tokens,
        }

    # ── SYMBOLIC FALLBACK ─────────────────────────────────

    def _symbolic_fallback(self, anomaly: dict, diagnosis: dict) -> dict:
        """LLM 미사용 시 규칙 기반 심볼릭 추론으로 폴백한다."""
        candidates = diagnosis.get("candidates", [])
        hypotheses = []
        for cand in candidates[:3]:
            hypotheses.append({
                "cause_type": cand.get("cause_type", "unknown"),
                "confidence": cand.get("confidence", 0.3),
                "reasoning": cand.get("evidence", "규칙 기반 진단"),
            })

        return {
            "hypotheses": hypotheses,
            "recommended_actions": [],
            "reasoning_chain": "심볼릭 폴백 모드 — 규칙 기반 후보를 LLM 가설로 전환",
            "confidence": max((h["confidence"] for h in hypotheses), default=0.3),
            "model": "symbolic_fallback",
            "tokens_used": 0,
        }

    # ── AUDIT LOGGING ─────────────────────────────────────

    def _log_decision(self, decision: dict, llm_result: dict | None = None):
        """의사결정을 감사 로그에 기록한다."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            **{k: v for k, v in decision.items() if k != "llm_result"},
        }
        if llm_result:
            entry["llm_model"] = llm_result.get("model", "")
            entry["llm_tokens"] = llm_result.get("tokens_used", 0)
            entry["llm_confidence"] = llm_result.get("confidence", 0)

        self.decision_log.append(entry)
        if len(self.decision_log) > self._max_log:
            self.decision_log = self.decision_log[-self._max_log:]

    # ── COMPLEXITY EXPLANATION ────────────────────────────

    @staticmethod
    def _explain_complexity(factors: dict, complexity: float) -> str:
        """복잡도 판단의 근거를 한국어로 설명한다."""
        reasons = []
        if factors["confidence"] < 0.55:
            reasons.append(f"낮은 신뢰도({factors['confidence']:.2f})")
        if not factors["failure_chain_matched"]:
            reasons.append("패턴 미매칭")
        if factors["cross_process_count"] > 0:
            reasons.append(f"교차공정 {factors['cross_process_count']}건")
        if factors["candidates_count"] < 2:
            reasons.append("후보 부족")
        if factors["causal_chains_found"] == 0:
            reasons.append("인과체인 없음")
        return f"복잡도 {complexity:.2f}: " + ", ".join(reasons) if reasons else f"복잡도 {complexity:.2f}"

    # ── STATUS ────────────────────────────────────────────

    def get_status(self) -> dict:
        """오케스트레이터 상태를 반환한다."""
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "confidence_threshold": self.confidence_threshold,
            "complexity_threshold": self.complexity_threshold,
            "stats": dict(self._stats),
            "cache": {
                "context_entries": len(self._context_cache),
                "response_entries": len(self._response_cache),
                "ttl_sec": self._cache_ttl_sec,
            },
        }

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        """감사 로그를 반환한다."""
        return self.decision_log[-max(1, min(self._max_log, limit)):]
