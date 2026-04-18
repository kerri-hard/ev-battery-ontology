"""VERIFY 페이즈 — 복구 후 yield 검증 + RUL 예측 + Weibull."""
import asyncio


async def run(engine, it: int, delay: float, recovery_results: list, anomalies: list) -> dict:
    """복구 결과 검증 + 예지정비 RUL 갱신.

    Returns: {"verifications": [...], "predictive": [...], "weibull_rul": [...], "rul_sync": {...}}
    """
    await engine._emit("phase", {
        "iteration": it + 1,
        "phase": "verify",
        "message": "복구 결과를 검증합니다...",
    })
    await asyncio.sleep(delay)

    verifications = _verify_yields(engine, recovery_results, anomalies)
    updated_metrics = _refresh_metrics(engine)
    predictive = _refresh_predictive(engine)
    weibull_results, rul_sync = _refresh_weibull(engine)

    await engine._emit("verify_done", {
        "iteration": it + 1,
        "verifications": verifications,
        "metrics": updated_metrics,
        "predictive": predictive,
        "weibull_rul": weibull_results,
        "rul_ontology_sync": rul_sync,
    })

    if rul_sync.get("critical_equipment"):
        await engine._emit("rul_critical", {
            "iteration": it + 1,
            "critical_equipment": rul_sync["critical_equipment"],
            "upserted": rul_sync["upserted"],
        })
    await asyncio.sleep(delay)

    return {
        "verifications": verifications,
        "predictive": predictive,
        "weibull_rul": weibull_results,
        "rul_sync": rul_sync,
    }


def _verify_yields(engine, recovery_results: list, anomalies: list) -> list:
    verifications = []
    for rr, anomaly in zip(recovery_results, anomalies):
        step_id = rr.get("step_id") or anomaly.get("step_id")
        pre_yield = rr.get("pre_yield")
        if pre_yield is None:
            pre_yield = engine._get_step_yield(step_id)
        if pre_yield is None:
            pre_yield = anomaly.get("pre_yield", 0.0)

        try:
            verification = engine.auto_recovery.verify_recovery(engine.conn, step_id, pre_yield)
            post_yield = verification.get("post_yield")
            verifications.append({
                "step_id": step_id,
                "pre_yield": pre_yield,
                "post_yield": post_yield,
                "improved": verification.get("improved", verification.get("verified", False)),
            })
            _record_preverify_accuracy(engine, step_id, pre_yield, post_yield)
        except Exception as exc:
            verifications.append({
                "step_id": step_id,
                "pre_yield": pre_yield,
                "post_yield": None,
                "improved": False,
                "error": str(exc),
            })
    return verifications


def _record_preverify_accuracy(engine, step_id: str, pre_yield, post_yield) -> None:
    """preverify가 예측한 expected_delta와 실제 yield delta를 비교하여 누적.

    이 메트릭이 곧 PRE-VERIFY 게이트의 신뢰도. EvolutionAgent가 향후
    안전등급별 score 임계값을 조정할 때 fitness signal로 사용 가능.
    """
    if pre_yield is None or post_yield is None:
        return
    predicted = engine._latest_preverify_predictions.get(step_id)
    if not predicted:
        return

    actual_delta = float(post_yield) - float(pre_yield)
    predicted_delta = float(predicted.get("expected_delta", 0.0))
    error = actual_delta - predicted_delta

    engine.preverify_accuracy_history.append({
        "step_id": step_id,
        "predicted_delta": round(predicted_delta, 6),
        "actual_delta": round(actual_delta, 6),
        "error": round(error, 6),
        "abs_error": round(abs(error), 6),
        "sign_match": (predicted_delta > 0) == (actual_delta > 0),
        "iteration": engine.healing_iteration + 1,
    })
    engine.preverify_accuracy_history = engine.preverify_accuracy_history[-200:]


def _refresh_metrics(engine) -> dict:
    try:
        gm = engine.skill_registry.execute("graph_metrics", engine.conn, {}, "system")
        engine.current_metrics = gm.get("metrics", engine.current_metrics)
    except Exception:
        pass
    return engine.current_metrics


def _refresh_predictive(engine) -> list:
    try:
        predictive = engine.predictive_agent.rank_rul_risks_v1(engine.conn, limit=5)
        engine.latest_predictive = predictive
        return predictive
    except Exception:
        return engine.latest_predictive


def _refresh_weibull(engine) -> tuple[list, dict]:
    rul_sync = {"upserted": 0, "critical_equipment": []}
    try:
        weibull_results = engine.weibull_rul.estimate(engine.conn, limit=5)
        engine.latest_weibull_rul = weibull_results
        try:
            rul_sync = engine.weibull_rul.sync_to_ontology(engine.conn, weibull_results)
        except Exception:
            pass
        return weibull_results, rul_sync
    except Exception:
        return engine.latest_weibull_rul, rul_sync
