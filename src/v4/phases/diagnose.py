"""DIAGNOSE 페이즈 — RCA(경로 + 인과) + 교차 원인 + LLM 가설 병합."""
import asyncio


async def run(engine, it: int, delay: float, anomalies: list) -> dict:
    """이상 → 원인 진단. RCA + Causal + LLM 오케스트레이션 + 교차 원인.

    Returns: {"diagnoses": [...], "cross_investigations": [...]}
    """
    await engine._emit("phase", {
        "iteration": it + 1,
        "phase": "diagnose",
        "message": "원인을 진단합니다...",
    })
    await asyncio.sleep(delay)

    diagnoses = []
    for anomaly in anomalies:
        diagnoses.append(await _diagnose_one(engine, it, anomaly))

    cross_investigations = _investigate_cross_causes(engine, anomalies)

    await engine._emit("diagnose_done", {
        "iteration": it + 1,
        "diagnoses": [_serialize_diagnosis(d) for d in diagnoses],
        "cross_investigations": [_serialize_cross(inv) for inv in cross_investigations],
    })
    await asyncio.sleep(delay)

    return {"diagnoses": diagnoses, "cross_investigations": cross_investigations}


async def _diagnose_one(engine, it: int, anomaly: dict) -> dict:
    """단일 이상에 대한 3단계 진단: 경로 → 인과 → LLM 보강."""
    try:
        basic_diag = engine.root_cause_analyzer.analyze(engine.conn, anomaly)
        causal_diag = engine.causal_reasoner.analyze(engine.conn, anomaly, basic_diag)

        await _maybe_invoke_llm(engine, it, anomaly, causal_diag)
        return causal_diag
    except Exception as exc:
        return {
            "step_id": anomaly.get("step_id"),
            "candidates": [],
            "causal_chains_found": 0,
            "failure_chain_matched": False,
            "analysis_method": "failed",
            "error": str(exc),
        }


async def _maybe_invoke_llm(engine, it: int, anomaly: dict, causal_diag: dict) -> None:
    """복잡도 점수에 따라 LLM 추론 호출 여부 결정."""
    if not engine.llm_orchestrator:
        return

    orch_decision = engine.llm_orchestrator.decide_path(anomaly, causal_diag)
    if orch_decision["path"] in ("llm", "llm_fallback"):
        try:
            llm_result = await engine.llm_orchestrator.invoke_llm_reasoning(
                engine.conn, anomaly, causal_diag,
            )
            await engine._merge_llm_hypotheses(
                it + 1, anomaly, causal_diag, llm_result, orch_decision,
            )
        except Exception:
            pass
    else:
        await engine._emit("orchestrator_decision", {
            "iteration": it + 1,
            "step_id": anomaly.get("step_id"),
            "path": "rule_based",
            "reason": orch_decision["reason"],
            "complexity_score": orch_decision["complexity_score"],
        })


def _investigate_cross_causes(engine, anomalies: list) -> list:
    """상관관계 기반 교차 원인 조사."""
    cross_investigations = []
    for anomaly in anomalies:
        try:
            inv = engine.cross_investigator.investigate(
                engine.conn, anomaly, engine.correlation_analyzer,
            )
            if inv.get("cross_causes"):
                cross_investigations.append(inv)
        except Exception:
            pass
    return cross_investigations


def _serialize_diagnosis(d: dict) -> dict:
    candidates = d.get("candidates", [])
    top = candidates[0] if candidates else None
    return {
        "step_id": d.get("step_id"),
        "top_cause": top["cause_type"] if top else "unknown",
        "confidence": round(top["confidence"], 3) if top else 0.0,
        "causal_chain": top.get("causal_chain") if top else None,
        "candidates_count": len(candidates),
        "causal_chains": d.get("causal_chains_found", 0),
        "history_matched": d.get("failure_chain_matched", False),
        "method": d.get("analysis_method", "basic"),
    }


def _serialize_cross(inv: dict) -> dict:
    return {
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
