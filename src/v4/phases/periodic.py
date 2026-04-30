"""PERIODIC 페이즈 — 주기적 메타 작업 (캘리브레이션/진화/시나리오/LLM 분석)."""
from v4.learning_layer import sync_learning_to_ontology


async def maybe_calibrate_causal(engine, it: int) -> None:
    """3 이터레이션마다 인과 규칙 강도 재보정."""
    if (it + 1) % 3 != 0:
        return
    cal = engine.causal_reasoner.replay_calibration(engine.conn)
    await engine._emit("causal_calibrated", {"iteration": it + 1, **cal})


async def maybe_mutate_playbook(engine, it: int) -> None:
    """5 이터레이션마다 복구 플레이북 자기 진화."""
    if (it + 1) % 5 != 0:
        return
    mutation_result = engine.auto_recovery.mutate_playbook()
    if mutation_result.get("mutations_applied", 0) > 0:
        await engine._emit("playbook_mutated", {"iteration": it + 1, **mutation_result})


async def maybe_adapt_scenario(engine, it: int) -> None:
    """5 이터레이션마다 시나리오 난이도 적응."""
    if (it + 1) % 5 != 0:
        return
    total_inc = len(engine.healing_history)
    auto_rec = sum(1 for h in engine.healing_history if h.get("auto_recovered"))
    adapt_result = engine.scenario_engine.adapt_difficulty({
        "total_incidents": total_inc,
        "auto_recovered": auto_rec,
    })
    await engine._emit("scenario_difficulty_adapted", {"iteration": it + 1, **adapt_result})


async def maybe_discover_causal(engine, it: int) -> None:
    """5 이터레이션마다 Granger causality 기반 자동 인과 발견."""
    if not engine.causal_discovery or (it + 1) % 5 != 0:
        return
    try:
        candidates = engine.causal_discovery.discover(engine.correlation_analyzer)
        pruned = engine.causal_discovery.prune_conditional_independence(
            candidates, engine.correlation_analyzer,
        )
        promoted = engine.causal_discovery.promote_to_ontology(
            engine.conn, pruned, engine.healing_counters,
        )
        await engine._emit("causal_discovery_done", {
            "iteration": it + 1,
            "candidates_tested": len(candidates),
            "after_pruning": len(pruned),
            "promoted_rules": [
                {"id": r["id"], "cause": r["cause_type"],
                 "effect": r["effect_type"], "strength": r["strength"],
                 "p_value": r.get("p_value")}
                for r in promoted
            ],
            "total_discovered": len(engine.causal_discovery.discovered_pairs),
        })
        engine.causal_discovery.save_state(engine._causal_disc_path)
    except Exception:
        pass

    # Bayesian conditional discovery — context 분리 Granger.
    # 별도 try (실패 시 기본 discovery 결과는 보존).
    try:
        await _discover_conditional_with_context(engine, it)
    except Exception:
        pass


async def _discover_conditional_with_context(engine, it: int) -> None:
    """Context-conditional Granger discovery + ConditionalStrength 영속.

    sensor_simulator의 누적 context_history 가 충분하면 (≥ min_samples × 2)
    각 context_factor 별 bucket masks 추출 → discover_with_context →
    record_conditional_strength 자동 영속.

    부수 효과 — 운영 흐름 미차단 (실패 silent skip).
    """
    sim = getattr(engine, "sensor_sim", None)
    if not sim or not hasattr(sim, "get_context_masks"):
        return
    history_len = len(getattr(sim, "_context_history", []))
    if history_len < (engine.causal_discovery.min_samples * 2):
        return  # 데이터 부족

    from v4.causal import record_conditional_strength

    persisted_count = 0
    for factor in ("time_of_day", "shift", "batch_phase"):
        masks = sim.get_context_masks(factor)
        if len(masks) < 2:
            continue
        results = engine.causal_discovery.discover_with_context(
            engine.correlation_analyzer, factor, masks,
        )
        for bucket_value, candidates in results.items():
            for cand in candidates[:3]:  # 상위 3개만 영속
                # promoted_rule_id 매핑이 가능한 경우만 (cause_type 기반)
                # 단순화: cause_type 으로 CausalRule 검색 → record_conditional
                cause_type = cand.get("cause_type", "")
                if not cause_type:
                    continue
                # CausalRule lookup
                cr_id = None
                try:
                    r = engine.conn.execute(
                        "MATCH (cr:CausalRule) WHERE cr.cause_type=$ct "
                        "RETURN cr.id LIMIT 1",
                        {"ct": cause_type},
                    )
                    if r.has_next():
                        cr_id = r.get_next()[0]
                except Exception:
                    continue
                if not cr_id:
                    continue
                # 영속화
                # f_stat 기반 conditional_prob 추정 (정규화)
                f_stat = float(cand.get("f_stat", 0.0))
                cond_prob = max(0.05, min(0.95, 0.5 + min(f_stat, 10.0) / 25.0))
                cs_id = record_conditional_strength(
                    engine.conn, cr_id, factor, bucket_value,
                    cond_prob, sample_count=int(cand.get("n_samples", 1)),
                )
                if cs_id:
                    persisted_count += 1

    if persisted_count > 0:
        await engine._emit("conditional_strength_discovered", {
            "iteration": it + 1,
            "persisted_count": persisted_count,
        })


async def maybe_evolve_agents(engine, it: int) -> None:
    """EvolutionAgent 메타 최적화 사이클 (자체 should_run 정책)."""
    if not engine.evolution_agent or not engine.evolution_agent.should_run(it + 1):
        return
    try:
        evo_metrics = _build_evolution_metrics(engine)
        prev_evo_metrics = getattr(engine, "_last_evo_metrics", None) or evo_metrics
        evo_result = engine.evolution_agent.run_evolution_cycle(
            engine.conn, prev_evo_metrics, evo_metrics,
        )
        engine._last_evo_metrics = evo_metrics

        learning_sync = _sync_evolution_to_ontology(engine, evo_result)

        await engine._emit("evolution_cycle_done", {
            "iteration": it + 1,
            "cycle_number": engine.evolution_agent.cycle_count,
            "strategies_run": evo_result.get("strategies_run", 0),
            "strategies_improved": evo_result.get("strategies_improved", 0),
            "strategy_summary": engine.evolution_agent.get_strategy_summary(),
            "mutations_tested": evo_result.get("mutations_tested", 0),
            "best_strategy": evo_result.get("best_strategy"),
            "overall_fitness": evo_result.get("overall_fitness", 0.5),
            "learning_record": learning_sync,
        })
        if learning_sync.get("record_id"):
            await engine._emit("learning_record_created", {
                "iteration": it + 1,
                "record_id": learning_sync["record_id"],
                "cycle_number": engine.evolution_agent.cycle_count,
                "overall_fitness": evo_result.get("overall_fitness", 0.5),
                "improvement_delta": learning_sync.get("improvement_delta", 0.0),
                "mutations_created": learning_sync.get("mutations_created", 0),
                "supersedes_linked": learning_sync.get("supersedes_linked", False),
            })
        engine.evolution_agent.save_state(engine._evo_state_path)
    except Exception:
        pass


def _build_evolution_metrics(engine) -> dict:
    total = len(engine.healing_history)
    auto = sum(1 for h in engine.healing_history if h.get("auto_recovered"))
    return {
        "total_incidents": total,
        "auto_recovered": auto,
        "recovery_rate": auto / max(total, 1),
        "correlations": len(engine.correlation_analyzer.known_correlations),
        **(engine.current_metrics or {}),
    }


def _sync_evolution_to_ontology(engine, evo_result: dict) -> dict:
    """LearningRecord + StrategyMutation 노드 영속화."""
    learning_sync = {"record_id": "", "mutations_created": 0, "supersedes_linked": False}
    try:
        prev_fitness = getattr(engine, "_last_evo_overall_fitness", 0.5)
        prev_record_id = getattr(engine, "_last_learning_record_id", None)
        learning_sync = sync_learning_to_ontology(
            engine.conn, evo_result, prev_fitness, prev_record_id,
        )
        engine._last_evo_overall_fitness = evo_result.get("overall_fitness", 0.5)
        if learning_sync.get("record_id"):
            engine._last_learning_record_id = learning_sync["record_id"]
    except Exception:
        pass
    return learning_sync


def update_traceability(engine, recovery_results: list) -> None:
    """Tesla/Samsung SDI 방식의 배치 추적성 — 매 사이클."""
    try:
        for rr in recovery_results:
            if not rr.get("step_id"):
                continue
            batch = engine.traceability.create_batch(
                engine.conn, rr["step_id"], batch_size=96,
                energy_kwh=round(0.5 + 0.3 * len(recovery_results), 2),
            )
            yield_val = rr.get("pre_yield", 0.95)
            defects = 1 if not rr.get("success") else 0
            engine.traceability.complete_batch(
                engine.conn, batch["batch_id"],
                yield_rate=yield_val, defect_count=defects,
            )
    except Exception:
        pass


def publish_recovery_events(engine, recovery_results: list) -> None:
    """이벤트 버스에 복구 결과 발행."""
    try:
        for rr in recovery_results:
            evt_type = "recovery_success" if rr.get("success") else "recovery_failed"
            engine.event_bus.publish_sync(evt_type, rr, source="healing_loop")
    except Exception:
        pass


async def llm_batch_analysis(engine, it: int, max_batch: int = 3) -> None:
    """이번 이터레이션 인시던트에 대한 LLM 심층 분석 (최대 N건)."""
    if not engine.llm_analyst.available:
        return

    this_iteration_incidents = [
        inc for inc in engine.healing_history if inc.get("iteration") == it + 1
    ]
    for batch_inc in this_iteration_incidents[:max_batch]:
        try:
            inc_data = _build_llm_incident_data(engine, batch_inc)
            analysis = engine.llm_analyst.analyze_incident_sync(inc_data)
            await engine._emit("incident_analysis", analysis)
        except Exception:
            pass


def _build_llm_incident_data(engine, batch_inc: dict) -> dict:
    step_id = batch_inc.get("step_id", "")
    step_name = ""
    try:
        r = engine.conn.execute(
            "MATCH (ps:ProcessStep) WHERE ps.id=$id RETURN ps.name",
            {"id": step_id},
        )
        if r.has_next():
            step_name = r.get_next()[0]
    except Exception:
        pass

    inc_data = {
        "incident_id": batch_inc.get("id", ""),
        "step_id": step_id,
        "step_name": step_name,
        "anomaly": {
            "sensor_type": batch_inc.get("anomaly_type", ""),
            "severity": batch_inc.get("severity", "MEDIUM"),
            "anomaly_type": batch_inc.get("anomaly_type", ""),
        },
        "diagnosis": {
            "top_cause": batch_inc.get("top_cause", ""),
            "confidence": batch_inc.get("confidence", 0),
            "causal_chain": batch_inc.get("causal_chain", ""),
            "history_matched": batch_inc.get("history_matched", False),
        },
        "cross_investigation": {
            "correlated_steps": engine.correlation_analyzer.get_correlations_for_step(step_id),
        },
        "recovery": {
            "action_type": batch_inc.get("action_type", ""),
            "success": batch_inc.get("auto_recovered", False),
            "pre_yield": batch_inc.get("pre_yield"),
            "post_yield": batch_inc.get("post_yield"),
        },
    }
    active_scn = engine.scenario_engine.get_active_scenarios()
    if active_scn:
        inc_data["scenario"] = {
            "name": active_scn[0].get("name", ""),
            "category": active_scn[0].get("category", ""),
        }
    return inc_data
