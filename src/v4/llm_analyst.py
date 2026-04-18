"""Backward-compatibility shim — 실제 구현은 `v4.analyst` 패키지로 이동.

기존 `from v4.llm_analyst import LLMAnalyst` 호출을 깨지 않는다.
"""
from v4.analyst import LLMAnalyst, SYSTEM_PROMPT

__all__ = ["LLMAnalyst", "SYSTEM_PROMPT"]
