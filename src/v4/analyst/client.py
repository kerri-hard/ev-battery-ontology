"""LLMAnalyst — OpenAI API 호출 + 캐시 + fallback 오케스트레이션."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from v4.analyst.cache import LRUCache, make_cache_key
from v4.analyst.fallback import generate_fallback
from v4.analyst.prompts import SYSTEM_PROMPT, build_user_message
from v4.analyst.scoring import build_confidence_breakdown, determine_agents_involved


_env_path = Path(__file__).parent.parent.parent.parent / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(_env_path)
except ImportError:
    if _env_path.is_file():
        for _line in _env_path.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                _k = _k.strip()
                _v = _v.strip().strip("\"'")
                if _k and _k not in os.environ:
                    os.environ[_k] = _v

logger = logging.getLogger(__name__)


class LLMAnalyst:
    """다중 에이전트 진단 결과를 OpenAI로 요약하는 분석 에이전트.

    OpenAI 키가 없거나 호출이 실패하면 `analyst.fallback.generate_fallback`로 폴백한다.
    """

    def __init__(self, api_key: str = None):
        self.model = "gpt-4o-mini"
        self.available = False
        self.client = None
        self._cache = LRUCache(maxsize=64, ttl_seconds=300)
        self._total_tokens_used = 0

        resolved_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()

        if not resolved_key:
            logger.warning("OPENAI_API_KEY not found — LLMAnalyst will use fallback summaries")
            return
        if not HAS_OPENAI:
            logger.warning("openai package not installed — LLMAnalyst will use fallback summaries")
            return

        try:
            self.client = openai.OpenAI(api_key=resolved_key)
            self.available = True
            logger.info("LLMAnalyst initialized with model=%s", self.model)
        except Exception as exc:
            logger.warning("Failed to initialize OpenAI client: %s", exc)

    # ── PUBLIC ────────────────────────────────────────────

    async def analyze_incident(self, incident_data: dict) -> dict:
        """비동기 분석 — 캐시 → OpenAI → fallback 순으로 시도."""
        cache_key = make_cache_key(incident_data)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if not self.available:
            return self._cache_and_return(cache_key, generate_fallback(incident_data))

        try:
            result = await self._call_openai(incident_data)
        except Exception as exc:
            logger.error("OpenAI API call failed: %s — returning fallback", exc)
            result = generate_fallback(incident_data)
        return self._cache_and_return(cache_key, result)

    def analyze_incident_sync(self, incident_data: dict) -> dict:
        """동기 진입점 — 이벤트 루프가 있으면 동기 호출, 없으면 asyncio.run."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            return asyncio.run(self.analyze_incident(incident_data))

        cache_key = make_cache_key(incident_data)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if not self.available:
            return self._cache_and_return(cache_key, generate_fallback(incident_data))

        try:
            result = self._call_openai_sync(incident_data)
        except Exception as exc:
            logger.error("Sync OpenAI call failed: %s — returning fallback", exc)
            result = generate_fallback(incident_data)
        return self._cache_and_return(cache_key, result)

    def generate_fallback(self, incident_data: dict) -> dict:
        """기존 호출자(`engine.llm_analyst.generate_fallback(...)`) 호환을 위한 wrapper."""
        return generate_fallback(incident_data)

    def get_status(self) -> dict:
        return {
            "available": self.available,
            "model": self.model if self.available else "fallback_template",
            "has_openai_package": HAS_OPENAI,
            "total_tokens_used": self._total_tokens_used,
            "cache_size": len(self._cache),
        }

    # ── INTERNAL — OpenAI ─────────────────────────────────

    async def _call_openai(self, incident_data: dict) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_openai_sync, incident_data)

    def _call_openai_sync(self, incident_data: dict) -> dict:
        user_message = build_user_message(incident_data)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=1200,
            timeout=10,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0
        self._total_tokens_used += tokens_used
        logger.info("OpenAI response: model=%s, tokens=%d", response.model, tokens_used)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse OpenAI JSON response, using fallback")
            result = generate_fallback(incident_data)
            result["model"] = self.model
            result["tokens_used"] = tokens_used
            return result

        return self._merge_llm_response(parsed, incident_data, tokens_used)

    def _merge_llm_response(self, parsed: dict, incident_data: dict, tokens_used: int) -> dict:
        """LLM JSON 응답에 confidence breakdown / agents / 메타데이터를 합친다."""
        actions = parsed.get("recommended_actions", [])
        if isinstance(actions, str):
            actions = [actions]

        return {
            "summary": parsed.get("summary", "요약 생성 실패"),
            "root_cause_explanation": parsed.get("root_cause_explanation", ""),
            "cross_process_insight": parsed.get("cross_process_insight", ""),
            "recommended_actions": actions[:5],
            "risk_assessment": parsed.get("risk_assessment", ""),
            "confidence_breakdown": build_confidence_breakdown(
                incident_data.get("anomaly", {}),
                incident_data.get("diagnosis", {}),
                incident_data.get("cross_investigation", {}),
                incident_data.get("recovery", {}),
            ),
            "agents_involved": determine_agents_involved(incident_data),
            "model": self.model,
            "tokens_used": tokens_used,
        }

    def _cache_and_return(self, key: str, result: dict) -> dict:
        self._cache.put(key, result)
        return result
