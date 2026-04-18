"""LLMAnalyst 패키지 — 다중 에이전트 진단 결과의 인간 친화적 요약 생성.

- client.LLMAnalyst — 메인 진입점 (OpenAI + 캐시 + fallback)
- prompts — system/user 프롬프트 빌더 + 한국어 라벨 매핑
- fallback — API 미사용 시 템플릿 기반 요약
- scoring — confidence breakdown + 참여 에이전트 판단
- cache — LRU + TTL 캐시
"""
from v4.analyst.client import LLMAnalyst
from v4.analyst.prompts import SYSTEM_PROMPT

__all__ = ["LLMAnalyst", "SYSTEM_PROMPT"]
