"""
LLM Analyst --- OpenAI API 기반 장애 분석 요약 에이전트
======================================================
다중 에이전트(AnomalyDetector, RootCauseAnalyzer, CausalReasoner,
CorrelationAnalyzer, CrossProcessInvestigator)의 진단 결과를 종합하여
사람이 이해할 수 있는 장애 분석 리포트를 생성한다.

기능:
  1. 사람이 이해할 수 있는 장애 설명 생성
  2. 근본 원인을 논리적으로 설명
  3. 구체적 대응 권고 제시

OpenAI API 키가 없는 환경에서도 템플릿 기반 fallback으로 동작한다.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# ---------------------------------------------------------------------------
#  .env 로드 (dotenv 가 없어도 동작)
# ---------------------------------------------------------------------------
_env_path = Path(__file__).parent.parent.parent / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(_env_path)
except ImportError:
    # python-dotenv 미설치 시 수동 파싱
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


# ---------------------------------------------------------------------------
#  LRU 캐시 (최근 N 개 요약을 보관해 동일 incident 중복 호출 방지)
# ---------------------------------------------------------------------------
class _LRUCache:
    """Simple ordered-dict LRU cache with TTL."""

    def __init__(self, maxsize: int = 64, ttl_seconds: float = 300.0):
        self._store: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[dict]:
        if key not in self._store:
            return None
        ts, val = self._store[key]
        if time.time() - ts > self._ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return val

    def put(self, key: str, value: dict) -> None:
        self._store[key] = (time.time(), value)
        self._store.move_to_end(key)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)


# ═══════════════════════════════════════════════════════════════
#  SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
You are a manufacturing quality engineer AI analyzing an EV battery pack production line incident.
Given the multi-agent diagnostic data, provide:
1. A clear 2-3 sentence summary of what happened (Korean)
2. Root cause explanation tracing the causal chain (Korean)
3. Cross-process insights if correlations exist (Korean)
4. 3 specific recommended actions with urgency levels (Korean)
5. Risk assessment with current status and future outlook (Korean)

Respond ONLY with valid JSON matching this structure:
{
  "summary": "...",
  "root_cause_explanation": "...",
  "cross_process_insight": "...",
  "recommended_actions": ["1. ...", "2. ...", "3. ..."],
  "risk_assessment": "..."
}
All text values must be in Korean. Be specific, referencing actual values from the data."""


# ═══════════════════════════════════════════════════════════════
#  LLMAnalyst
# ═══════════════════════════════════════════════════════════════

class LLMAnalyst:
    """OpenAI API 기반 장애 분석 요약 에이전트.

    다중 에이전트의 진단 결과를 종합하여:
    1. 사람이 이해할 수 있는 장애 설명을 생성
    2. 근본 원인을 논리적으로 설명
    3. 구체적 대응 권고를 제시
    """

    def __init__(self, api_key: str = None):
        self.model = "gpt-4o-mini"
        self.available = False
        self.client = None
        self._cache = _LRUCache(maxsize=64, ttl_seconds=300)
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

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    async def analyze_incident(self, incident_data: dict) -> dict:
        """Analyze an incident and return a human-readable summary.

        Parameters
        ----------
        incident_data : dict
            Comprehensive incident dict containing anomaly, diagnosis,
            cross_investigation, recovery, and optional scenario data.

        Returns
        -------
        dict
            Analysis result with summary, root_cause_explanation,
            cross_process_insight, recommended_actions, risk_assessment,
            confidence_breakdown, agents_involved, model, and tokens_used.
        """
        cache_key = self._make_cache_key(incident_data)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for incident %s", incident_data.get("step_id"))
            return cached

        if not self.available:
            result = self.generate_fallback(incident_data)
            self._cache.put(cache_key, result)
            return result

        try:
            result = await self._call_openai(incident_data)
            self._cache.put(cache_key, result)
            return result
        except Exception as exc:
            logger.error("OpenAI API call failed: %s — returning fallback", exc)
            result = self.generate_fallback(incident_data)
            self._cache.put(cache_key, result)
            return result

    def analyze_incident_sync(self, incident_data: dict) -> dict:
        """Synchronous wrapper for use in non-async contexts.

        Tries ``asyncio.run()`` first; if an event loop is already running,
        falls back to a direct synchronous OpenAI call.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            # No event loop — safe to use asyncio.run()
            return asyncio.run(self.analyze_incident(incident_data))

        # An event loop is already running — do a sync call directly to avoid
        # "cannot call asyncio.run() while another loop is running".
        cache_key = self._make_cache_key(incident_data)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if not self.available:
            result = self.generate_fallback(incident_data)
            self._cache.put(cache_key, result)
            return result

        try:
            result = self._call_openai_sync(incident_data)
            self._cache.put(cache_key, result)
            return result
        except Exception as exc:
            logger.error("Sync OpenAI call failed: %s — returning fallback", exc)
            result = self.generate_fallback(incident_data)
            self._cache.put(cache_key, result)
            return result

    # ------------------------------------------------------------------
    #  Fallback (template-based, no API needed)
    # ------------------------------------------------------------------

    def generate_fallback(self, incident_data: dict) -> dict:
        """Generate a template-based summary when OpenAI API is unavailable.

        Still useful — fills in actual values from the diagnostic data,
        just not as eloquent as an LLM-generated summary.
        """
        step_id = incident_data.get("step_id", "UNKNOWN")
        step_name = incident_data.get("step_name", "알 수 없는 공정")

        anomaly = incident_data.get("anomaly", {})
        sensor_type = anomaly.get("sensor_type", "sensor")
        value = anomaly.get("value", "N/A")
        normal_range = anomaly.get("normal_range", [None, None])
        severity = anomaly.get("severity", "UNKNOWN")
        anomaly_type = anomaly.get("anomaly_type", "unknown")

        diagnosis = incident_data.get("diagnosis", {})
        top_cause = diagnosis.get("top_cause", "unknown")
        confidence = diagnosis.get("confidence", 0.0)
        causal_chain = diagnosis.get("causal_chain", "원인 체인 미확인")
        history_matched = diagnosis.get("history_matched", False)

        cross = incident_data.get("cross_investigation", {})
        correlated_steps = cross.get("correlated_steps", [])

        recovery = incident_data.get("recovery", {})
        action_type = recovery.get("action_type", "UNKNOWN")
        recovery_success = recovery.get("success", False)
        pre_yield = recovery.get("pre_yield", None)
        post_yield = recovery.get("post_yield", None)

        scenario = incident_data.get("scenario", {})

        # --- summary ---
        range_str = ""
        if normal_range and len(normal_range) == 2 and normal_range[0] is not None:
            range_str = f"정상 범위({normal_range[0]}-{normal_range[1]})"
        else:
            range_str = "정상 범위"

        sensor_label = self._sensor_type_korean(sensor_type)
        summary = (
            f"{step_id}({step_name})에서 {sensor_label}가 "
            f"{range_str}를 초과한 {value}을(를) 기록했습니다. "
            f"이상 유형: {anomaly_type}, 심각도: {severity}."
        )

        # --- root cause ---
        cause_label = self._cause_type_korean(top_cause)
        confidence_pct = int(confidence * 100)
        history_str = "과거 이력 매칭 확인" if history_matched else "과거 이력 매칭 없음"
        root_cause_explanation = (
            f"인과관계 분석에 따르면, {cause_label}이(가) 근본 원인으로 추정됩니다 "
            f"(신뢰도 {confidence_pct}%, {history_str}). "
            f"인과 체인: {causal_chain}."
        )

        # --- cross process insight ---
        if correlated_steps:
            top_corr = correlated_steps[0]
            corr_step = top_corr.get("step_id", "?")
            corr_val = top_corr.get("correlation", 0)
            corr_rel = top_corr.get("relationship", "관련 공정")
            cross_process_insight = (
                f"{corr_rel} {corr_step}과(와) {corr_val:.2f}의 상관관계가 발견되었습니다. "
                f"해당 공정의 연관 센서를 함께 점검할 것을 권장합니다."
            )
        else:
            cross_process_insight = "유의미한 공정 간 상관관계가 발견되지 않았습니다."

        # --- recommended actions ---
        recommended_actions = self._build_fallback_actions(
            top_cause, action_type, correlated_steps, severity
        )

        # --- risk assessment ---
        if recovery_success and post_yield is not None:
            yield_pct = f"{post_yield * 100:.1f}%"
            risk_assessment = (
                f"{'LOW' if post_yield >= 0.995 else 'MEDIUM'} — "
                f"현재 자동 복구로 수율이 {yield_pct}로 복귀했으나, "
                f"근본 원인 미해결 시 재발 가능성 높음"
            )
        else:
            risk_assessment = (
                f"HIGH — 복구 {'실패' if not recovery_success else '미확인'}, "
                f"즉각적인 조치가 필요합니다"
            )

        # --- confidence breakdown ---
        confidence_breakdown = self._build_confidence_breakdown(
            anomaly, diagnosis, cross, recovery
        )

        # --- agents involved ---
        agents_involved = self._determine_agents_involved(incident_data)

        return {
            "summary": summary,
            "root_cause_explanation": root_cause_explanation,
            "cross_process_insight": cross_process_insight,
            "recommended_actions": recommended_actions,
            "risk_assessment": risk_assessment,
            "confidence_breakdown": confidence_breakdown,
            "agents_involved": agents_involved,
            "model": "fallback_template",
            "tokens_used": 0,
        }

    # ------------------------------------------------------------------
    #  Status / metrics
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "available": self.available,
            "model": self.model if self.available else "fallback_template",
            "has_openai_package": HAS_OPENAI,
            "total_tokens_used": self._total_tokens_used,
            "cache_size": len(self._cache._store),
        }

    # ------------------------------------------------------------------
    #  Internal — OpenAI calls
    # ------------------------------------------------------------------

    async def _call_openai(self, incident_data: dict) -> dict:
        """Make an async-compatible OpenAI API call.

        The ``openai`` Python SDK >= 1.x exposes synchronous methods by
        default.  We run the blocking call in a thread executor so the
        event loop is not blocked.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_openai_sync, incident_data)

    def _call_openai_sync(self, incident_data: dict) -> dict:
        """Synchronous OpenAI chat completion call."""
        user_message = self._build_user_message(incident_data)

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

        # Parse response
        content = response.choices[0].message.content or ""
        tokens_used = 0
        if response.usage:
            tokens_used = response.usage.total_tokens
            self._total_tokens_used += tokens_used

        logger.info(
            "OpenAI response: model=%s, tokens=%d",
            response.model, tokens_used,
        )

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse OpenAI JSON response, using fallback")
            result = self.generate_fallback(incident_data)
            result["model"] = self.model
            result["tokens_used"] = tokens_used
            return result

        # Merge LLM output with structured metadata
        confidence_breakdown = self._build_confidence_breakdown(
            incident_data.get("anomaly", {}),
            incident_data.get("diagnosis", {}),
            incident_data.get("cross_investigation", {}),
            incident_data.get("recovery", {}),
        )
        agents_involved = self._determine_agents_involved(incident_data)

        # Ensure recommended_actions is a list
        actions = parsed.get("recommended_actions", [])
        if isinstance(actions, str):
            actions = [actions]

        return {
            "summary": parsed.get("summary", "요약 생성 실패"),
            "root_cause_explanation": parsed.get("root_cause_explanation", ""),
            "cross_process_insight": parsed.get("cross_process_insight", ""),
            "recommended_actions": actions[:5],
            "risk_assessment": parsed.get("risk_assessment", ""),
            "confidence_breakdown": confidence_breakdown,
            "agents_involved": agents_involved,
            "model": self.model,
            "tokens_used": tokens_used,
        }

    # ------------------------------------------------------------------
    #  Message construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_message(incident_data: dict) -> str:
        """Build a structured user message from incident data for the LLM."""
        parts = []

        step_id = incident_data.get("step_id", "UNKNOWN")
        step_name = incident_data.get("step_name", "")
        parts.append(f"## 장애 발생 공정: {step_id} ({step_name})")

        # Anomaly
        anomaly = incident_data.get("anomaly", {})
        if anomaly:
            parts.append(f"\n### 이상 감지")
            parts.append(f"- 센서 유형: {anomaly.get('sensor_type', 'N/A')}")
            parts.append(f"- 측정값: {anomaly.get('value', 'N/A')}")
            parts.append(f"- 정상 범위: {anomaly.get('normal_range', 'N/A')}")
            parts.append(f"- 이상 유형: {anomaly.get('anomaly_type', 'N/A')}")
            parts.append(f"- 심각도: {anomaly.get('severity', 'N/A')}")

        # Diagnosis
        diagnosis = incident_data.get("diagnosis", {})
        if diagnosis:
            parts.append(f"\n### 원인 진단")
            parts.append(f"- 최우선 원인: {diagnosis.get('top_cause', 'N/A')}")
            parts.append(f"- 신뢰도: {diagnosis.get('confidence', 'N/A')}")
            candidates = diagnosis.get("candidates", [])
            if candidates:
                parts.append(f"- 후보 원인: {json.dumps(candidates, ensure_ascii=False)}")
            parts.append(f"- 인과 체인: {diagnosis.get('causal_chain', 'N/A')}")
            parts.append(f"- 과거 이력 매칭: {diagnosis.get('history_matched', False)}")
            if diagnosis.get("matched_chain_id"):
                parts.append(f"- 매칭 체인 ID: {diagnosis['matched_chain_id']}")

        # Cross-process investigation
        cross = incident_data.get("cross_investigation", {})
        if cross:
            parts.append(f"\n### 공정 간 조사")
            correlated = cross.get("correlated_steps", [])
            if correlated:
                for cs in correlated[:5]:
                    parts.append(
                        f"- {cs.get('step_id', '?')}: "
                        f"상관계수={cs.get('correlation', 0):.2f}, "
                        f"관계={cs.get('relationship', 'N/A')}"
                    )
            hidden = cross.get("hidden_dependencies", 0)
            if hidden:
                parts.append(f"- 숨겨진 의존성: {hidden}건")

        # Recovery
        recovery = incident_data.get("recovery", {})
        if recovery:
            parts.append(f"\n### 복구 결과")
            parts.append(f"- 복구 유형: {recovery.get('action_type', 'N/A')}")
            parts.append(f"- 성공 여부: {recovery.get('success', 'N/A')}")
            if recovery.get("pre_yield") is not None:
                parts.append(f"- 복구 전 수율: {recovery['pre_yield']}")
            if recovery.get("post_yield") is not None:
                parts.append(f"- 복구 후 수율: {recovery['post_yield']}")

        # Scenario (optional)
        scenario = incident_data.get("scenario", {})
        if scenario:
            parts.append(f"\n### 시나리오")
            parts.append(f"- 시나리오 이름: {scenario.get('name', 'N/A')}")
            parts.append(f"- 카테고리: {scenario.get('category', 'N/A')}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    #  Helpers — confidence breakdown
    # ------------------------------------------------------------------

    @staticmethod
    def _build_confidence_breakdown(
        anomaly: dict, diagnosis: dict, cross: dict, recovery: dict
    ) -> dict:
        """Build a structured confidence assessment for each analysis component."""
        breakdown = {}

        # Anomaly detection confidence
        severity = anomaly.get("severity", "UNKNOWN")
        anomaly_type = anomaly.get("anomaly_type", "")
        if severity == "HIGH" or severity == "CRITICAL":
            breakdown["anomaly_detection"] = f"HIGH ({anomaly_type})"
        elif severity == "MEDIUM":
            breakdown["anomaly_detection"] = f"MEDIUM ({anomaly_type})"
        else:
            breakdown["anomaly_detection"] = f"LOW ({anomaly_type})"

        # Root cause confidence
        rc_conf = diagnosis.get("confidence", 0)
        history = diagnosis.get("history_matched", False)
        if rc_conf >= 0.8:
            level = "HIGH"
        elif rc_conf >= 0.5:
            level = "MEDIUM"
        else:
            level = "LOW"
        rc_pct = int(rc_conf * 100)
        history_str = ", 과거 이력 매칭" if history else ""
        breakdown["root_cause"] = f"{level} ({rc_pct}%{history_str})"

        # Cross-correlation confidence
        correlated = cross.get("correlated_steps", [])
        if correlated:
            max_corr = max(abs(cs.get("correlation", 0)) for cs in correlated)
            if max_corr >= 0.8:
                level = "HIGH"
            elif max_corr >= 0.5:
                level = "MEDIUM"
            else:
                level = "LOW"
            breakdown["cross_correlation"] = f"{level} (r={max_corr:.2f})"
        else:
            breakdown["cross_correlation"] = "N/A (상관 데이터 없음)"

        # Recovery effectiveness
        success = recovery.get("success", False)
        post_yield = recovery.get("post_yield")
        if success and post_yield is not None:
            if post_yield >= 0.99:
                breakdown["recovery_effectiveness"] = "HIGH (수율 복귀 확인)"
            else:
                breakdown["recovery_effectiveness"] = f"MEDIUM (수율 {post_yield * 100:.1f}%)"
        elif not success:
            breakdown["recovery_effectiveness"] = "LOW (복구 실패)"
        else:
            breakdown["recovery_effectiveness"] = "UNKNOWN (복구 미확인)"

        return breakdown

    # ------------------------------------------------------------------
    #  Helpers — agents involved
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_agents_involved(incident_data: dict) -> list[str]:
        """Determine which agents contributed to the incident analysis."""
        agents = []

        if incident_data.get("anomaly"):
            agents.append("AnomalyDetector")

        diagnosis = incident_data.get("diagnosis", {})
        if diagnosis:
            agents.append("RootCauseAnalyzer")
            if diagnosis.get("causal_chain"):
                agents.append("CausalReasoner")

        cross = incident_data.get("cross_investigation", {})
        if cross:
            if cross.get("correlated_steps"):
                agents.append("CorrelationAnalyzer")
            # CrossProcessInvestigator is always involved when cross data exists
            agents.append("CrossProcessInvestigator")

        return agents

    # ------------------------------------------------------------------
    #  Helpers — fallback action generation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_fallback_actions(
        top_cause: str, action_type: str, correlated_steps: list, severity: str
    ) -> list[str]:
        """Build template-based recommended actions."""
        actions = []

        # Primary action based on cause type
        cause_actions = {
            "equipment_wear": "크림핑 프레스 실린더 교체 또는 재보정",
            "equipment_mtbf": "설비 예방정비 일정 앞당기기 및 상태 점검",
            "cooling_failure": "냉각 시스템 점검 및 냉매 보충",
            "material_anomaly": "자재 LOT 변경 이력 및 입고 검사 결과 점검",
            "material_lot_change": "신규 자재 LOT 품질 검증 및 공정 파라미터 재조정",
            "defect_mode_match": "결함 모드에 대응하는 품질 검사 강화",
            "upstream_degradation": "상류 공정 설비 점검 및 파라미터 재조정",
            "sensor_drift": "센서 캘리브레이션 실시",
            "vibration_anomaly": "진동 발생 장비 베어링 및 축 정렬 점검",
        }
        primary = cause_actions.get(top_cause, f"'{top_cause}' 원인에 대한 playbook 실행")
        urgency = "즉시" if severity in ("HIGH", "CRITICAL") else "24시간 내"
        actions.append(f"1. {primary} ({urgency})")

        # Cross-process action
        if correlated_steps:
            top_corr = correlated_steps[0]
            corr_step = top_corr.get("step_id", "관련 공정")
            corr_rel = top_corr.get("relationship", "관련 공정")
            actions.append(f"2. {corr_rel} {corr_step} 설비 및 센서 점검 (24시간 내)")
        else:
            actions.append("2. 인접 공정 센서 추이 모니터링 강화 (24시간 내)")

        # Verification action
        actions.append("3. 다음 5개 배치에 대한 품질 전수검사 실시")

        return actions

    # ------------------------------------------------------------------
    #  Helpers — Korean labels
    # ------------------------------------------------------------------

    @staticmethod
    def _sensor_type_korean(sensor_type: str) -> str:
        labels = {
            "torque_force": "토크 센서",
            "temperature": "온도 센서",
            "vibration": "진동 센서",
            "pressure": "압력 센서",
            "humidity": "습도 센서",
            "current": "전류 센서",
            "voltage": "전압 센서",
            "thickness": "두께 센서",
            "alignment": "정렬 센서",
            "tension": "장력 센서",
            "flow_rate": "유량 센서",
            "vacuum_level": "진공도 센서",
        }
        return labels.get(sensor_type, f"{sensor_type} 센서")

    @staticmethod
    def _cause_type_korean(cause_type: str) -> str:
        labels = {
            "equipment_wear": "장비 마모",
            "equipment_mtbf": "설비 MTBF 초과",
            "cooling_failure": "냉각 시스템 이상",
            "material_anomaly": "자재 이상",
            "material_lot_change": "자재 LOT 변경",
            "defect_mode_match": "결함 모드 매칭",
            "upstream_degradation": "상류 공정 열화",
            "sensor_drift": "센서 드리프트",
            "vibration_anomaly": "진동 이상",
            "pressure_drop": "압력 부족",
            "temperature_rise": "온도 상승",
            "unknown": "원인 미상",
        }
        return labels.get(cause_type, cause_type)

    # ------------------------------------------------------------------
    #  Cache key generation
    # ------------------------------------------------------------------

    @staticmethod
    def _make_cache_key(incident_data: dict) -> str:
        """Create a deterministic hash from incident data for caching."""
        # Use a subset of key fields that uniquely identify the incident state
        key_parts = {
            "step_id": incident_data.get("step_id"),
            "anomaly_value": incident_data.get("anomaly", {}).get("value"),
            "anomaly_type": incident_data.get("anomaly", {}).get("anomaly_type"),
            "top_cause": incident_data.get("diagnosis", {}).get("top_cause"),
            "confidence": incident_data.get("diagnosis", {}).get("confidence"),
            "recovery_success": incident_data.get("recovery", {}).get("success"),
            "post_yield": incident_data.get("recovery", {}).get("post_yield"),
        }
        raw = json.dumps(key_parts, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
