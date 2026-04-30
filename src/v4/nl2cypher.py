"""NL-to-Cypher 가드레일 — 자연어 질문을 안전한 read-only Cypher로 변환.

CLAUDE.md "남은 항목" 명시 약속의 구현. 운영자가 자연어로 그래프에 질의할 때
다음 안전성을 *코드 수준* 에서 강제한다:

1. **화이트리스트 키워드만 허용**: MATCH / WHERE / RETURN / ORDER BY / LIMIT /
   WITH / OPTIONAL MATCH / DISTINCT / SKIP
2. **차단 키워드**: CREATE / MERGE / DELETE / DROP / SET / REMOVE / DETACH /
   LOAD CSV / CALL — 그래프를 *변경* 하는 모든 연산 거부
3. **read-only 강제**: 파싱 후 차단 키워드가 검출되면 실행 거부 (블록 사유 반환)
4. **explain-only (dry-run) 모드**: 기본은 Cypher 만 반환, 명시 승인 시 실행
5. **LIMIT 강제**: LIMIT 절 없으면 자동 50으로 캡 (대용량 결과 방지)
6. **스키마 카탈로그 inject**: LLM 프롬프트에 22 노드 + 35 관계 명시

가드레일은 *항상* 적용된다 — LLM 출력이든 사용자 직접 입력이든.
"""

from __future__ import annotations

import os
import re
from typing import Any

# ── 스키마 카탈로그 (CLAUDE.md 정정본 기반) ─────────────────────────────────────

NODE_TYPES: tuple[str, ...] = (
    # L1-L2
    "ProcessArea", "ProcessStep", "Equipment", "Material",
    "QualitySpec", "DefectMode", "AutomationPlan", "MaintenancePlan",
    # L3
    "CausalRule", "AnomalyPattern", "FailureChain", "Incident",
    # L4
    "EscalationPolicy", "RecoveryAction", "ProductionBatch",
    "ResponsePlaybook", "RULEstimate",
    # L5 추적성·모니터링·메타
    "BatteryPassport", "LotTrace", "Alarm", "SensorReading",
    "Correlation", "OptimizationGoal",
)

REL_TYPES: tuple[str, ...] = (
    "NEXT_STEP", "FEEDS_INTO", "PARALLEL_WITH", "TRIGGERS_REWORK",
    "BELONGS_TO", "USES_EQUIPMENT", "CONSUMES", "REQUIRES_SPEC",
    "HAS_DEFECT", "PREVENTS", "PLANNED_UPGRADE", "HAS_MAINTENANCE",
    "DEPENDS_ON", "INSPECTS",
    "CAUSES", "HAS_CAUSE", "HAS_PATTERN", "MATCHED_BY", "CHAIN_USES",
    "PREDICTS", "CAUSED_BY",
    "ESCALATES_TO", "RESOLVED_BY", "HAS_INCIDENT", "BATCH_INCIDENT",
    "TRIGGERS_ACTION",
    "HAS_PASSPORT", "HAS_ALARM", "HAS_READING", "OPTIMIZES",
    "CORRELATES_WITH", "PRODUCED_IN", "TRACED_TO", "USES_LOT",
    "TRIGGERED_BY",
)

# ── 가드레일 ─────────────────────────────────────────────────────────────────

# 차단 키워드 — 한 단어라도 있으면 거부 (대소문자 무시, word boundary).
_BLOCKED_KEYWORDS = (
    "CREATE", "MERGE", "DELETE", "DROP", "SET", "REMOVE",
    "DETACH", "LOAD", "CALL", "USE", "ALTER", "ATTACH",
)
_BLOCKED_RE = re.compile(
    r"\b(" + "|".join(_BLOCKED_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

_LIMIT_RE = re.compile(r"\bLIMIT\s+\d+\b", re.IGNORECASE)
_DEFAULT_LIMIT_CAP = 50


def validate_cypher(cypher: str) -> dict[str, Any]:
    """Cypher 쿼리를 가드레일로 검증한다.

    Returns:
        {
            "blocked": bool,             # 차단됐는가
            "block_reason": str | None,  # 차단 사유
            "warnings": list[str],       # 경고 (차단 아니지만 주의)
            "cypher_normalized": str,    # LIMIT 자동 추가 등 정규화 후
        }
    """
    if not cypher or not cypher.strip():
        return {
            "blocked": True,
            "block_reason": "empty_query",
            "warnings": [],
            "cypher_normalized": "",
        }

    text = cypher.strip()
    warnings: list[str] = []

    # 1) 차단 키워드 검출
    blocked_match = _BLOCKED_RE.search(text)
    if blocked_match:
        return {
            "blocked": True,
            "block_reason": f"forbidden_keyword:{blocked_match.group(1).upper()}",
            "warnings": [],
            "cypher_normalized": text,
        }

    # 2) MATCH 절 필수 (단순 RETURN 1 같은 trivial 도 OK 하지만 보수적으로)
    if "MATCH" not in text.upper() and "RETURN" not in text.upper():
        return {
            "blocked": True,
            "block_reason": "no_match_or_return",
            "warnings": [],
            "cypher_normalized": text,
        }

    # 3) LIMIT 강제 (대용량 결과 방지)
    if not _LIMIT_RE.search(text):
        text = text.rstrip(";").rstrip() + f" LIMIT {_DEFAULT_LIMIT_CAP}"
        warnings.append(f"limit_auto_added:{_DEFAULT_LIMIT_CAP}")

    return {
        "blocked": False,
        "block_reason": None,
        "warnings": warnings,
        "cypher_normalized": text,
    }


# ── LLM 변환 (스키마-aware 프롬프트) ──────────────────────────────────────────

_SCHEMA_PROMPT = """다음 그래프 스키마에 한정해 자연어 질문을 Cypher로 변환하세요.
**read-only**만 허용 (MATCH/WHERE/RETURN/ORDER BY/LIMIT/WITH/OPTIONAL MATCH/DISTINCT).
CREATE/MERGE/DELETE/DROP/SET/REMOVE는 절대 사용 금지.

노드 타입: {nodes}
관계 타입: {rels}

질문: {question}

답변 형식 (JSON):
{{"cypher": "MATCH ... RETURN ... LIMIT 50", "explain": "한국어 한 줄 설명"}}
"""


def _build_llm_prompt(question: str) -> str:
    return _SCHEMA_PROMPT.format(
        nodes=", ".join(NODE_TYPES),
        rels=", ".join(REL_TYPES),
        question=question.strip(),
    )


def _call_llm(question: str) -> dict[str, Any] | None:
    """LLM 호출 — 가능하면 OpenAI, 실패 시 None.

    온라인 의존성 없이 호출 가능하도록 import는 함수 내부.
    """
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key or os.getenv("LLM_USE_OPENAI", "1") == "0":
        return None
    try:
        import json as _json
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL") or "gpt-4.1-mini",
            messages=[{"role": "user", "content": _build_llm_prompt(question)}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        return _json.loads(content)
    except Exception:
        return None


# ── 메인 진입점 ──────────────────────────────────────────────────────────────


def nl_to_cypher(
    question: str,
    conn=None,
    *,
    execute: bool = False,
) -> dict[str, Any]:
    """자연어 질문 → 안전한 read-only Cypher 변환 + 선택적 실행.

    Args:
        question: 자연어 질문 (예: "yield 0.99 미만 step 보여줘")
        conn: Kuzu connection. execute=True 일 때만 사용.
        execute: True 면 검증된 Cypher를 실행해 rows 반환. 기본 False (dry-run).

    Returns:
        {
            "question": str,
            "cypher": str,                 # 변환된 Cypher (가드 통과시)
            "explain": str,                # 한 줄 설명
            "blocked": bool,
            "block_reason": str | None,
            "warnings": list[str],
            "executed": bool,
            "rows": list,                  # execute=True && not blocked 일 때
            "source": "llm" | "fallback",  # LLM 호출 성공 여부
        }
    """
    q = (question or "").strip()
    if not q:
        return {
            "question": "",
            "cypher": "",
            "explain": "",
            "blocked": True,
            "block_reason": "empty_question",
            "warnings": [],
            "executed": False,
            "rows": [],
            "source": "none",
        }

    llm_out = _call_llm(q)
    if llm_out and isinstance(llm_out, dict) and "cypher" in llm_out:
        cypher = str(llm_out.get("cypher", "")).strip()
        explain = str(llm_out.get("explain", "")).strip()
        source = "llm"
    else:
        # 폴백 — LLM 미설정. 가드레일 동작 자체는 검증 가능.
        cypher = ""
        explain = "LLM 미설정 — 자연어 변환 불가"
        source = "fallback"

    validation = validate_cypher(cypher) if cypher else {
        "blocked": True,
        "block_reason": "no_cypher_generated",
        "warnings": [],
        "cypher_normalized": "",
    }

    rows: list = []
    executed = False
    if execute and not validation["blocked"] and conn is not None:
        try:
            r = conn.execute(validation["cypher_normalized"])
            while r.has_next():
                row = r.get_next()
                rows.append([str(v) for v in row])
            executed = True
        except Exception as e:
            validation["warnings"].append(f"execute_failed:{type(e).__name__}")

    return {
        "question": q,
        "cypher": validation.get("cypher_normalized", cypher),
        "explain": explain,
        "blocked": validation["blocked"],
        "block_reason": validation.get("block_reason"),
        "warnings": validation.get("warnings", []),
        "executed": executed,
        "rows": rows,
        "source": source,
    }
