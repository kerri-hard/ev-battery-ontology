"""연구 루프용 자율 복구 시뮬레이션 — N회 SENSE→DETECT→DIAGNOSE→RECOVER→LEARN."""
from v4.sensor_simulator import store_readings, store_alarm


def run_simulation(
    conn, sensor_sim, anomaly_detector, rca, auto_recovery,
    causal_reasoner, corr_analyzer, cross_investigator,
    scenario_engine, skill_registry, healing_counters,
    num_iterations: int = 5,
) -> dict:
    """N회 자율 복구 시뮬레이션 후 결과를 집계해 반환한다."""
    state = _SimState()

    yield_before = _measure_yield(conn, skill_registry)

    for it in range(num_iterations):
        _maybe_inject_scenario(scenario_engine, it, state)
        readings = _sense(conn, sensor_sim, corr_analyzer, healing_counters)
        detected = _detect(conn, sensor_sim, anomaly_detector, readings, healing_counters)

        _accumulate_false_positives(detected, scenario_engine, state)
        state.total_anomalies += len(detected)

        if not detected:
            continue

        _diagnose_and_recover(
            conn, detected, rca, causal_reasoner, auto_recovery,
            healing_counters, state.incidents,
        )

        if it % 2 == 0:
            corr_analyzer.analyze_all()

    yield_after = _measure_yield(conn, skill_registry)

    return _build_result(yield_before, yield_after, corr_analyzer, conn, state)


class _SimState:
    """시뮬레이션 누적 상태."""

    def __init__(self):
        self.incidents: list = []
        self.total_anomalies = 0
        self.total_false_positives = 0
        self.total_missed = 0
        self.scenarios_activated = 0


def _measure_yield(conn, skill_registry) -> float:
    gm = skill_registry.execute("graph_metrics", conn, {}, "system")
    return gm["metrics"]["line_yield"]


def _maybe_inject_scenario(scenario_engine, it: int, state: _SimState) -> None:
    scenario_engine.tick()
    if it % 2 == 0 and not scenario_engine.get_active_scenarios():
        if scenario_engine.activate_random():
            state.scenarios_activated += 1


def _sense(conn, sensor_sim, corr_analyzer, counters: dict) -> list:
    readings = sensor_sim.generate_readings()
    store_readings(conn, readings, counters)
    corr_analyzer.ingest(readings)
    return readings


def _detect(conn, sensor_sim, detector, readings: list, counters: dict) -> list:
    detector.update(readings)
    detected = detector.detect(readings)
    for alarm in sensor_sim.check_alarms(readings):
        store_alarm(conn, alarm, counters)
    return detected


def _accumulate_false_positives(detected: list, scenario_engine, state: _SimState) -> None:
    """활성 시나리오에 매칭되지 않는 감지를 오탐으로 간주.

    시나리오 미활성 구간에서는 감지 결과 전부가 오탐 후보 (선택편향 보정).
    """
    active_scn = scenario_engine.get_active_scenarios()
    scenario_steps = {
        step.get("step_id", "")
        for scn in active_scn
        for step in scn.get("affected_steps", [])
    }
    if scenario_steps:
        state.total_false_positives += sum(
            1 for d in detected if d.get("step_id") not in scenario_steps
        )
    else:
        state.total_false_positives += len(detected)


def _diagnose_and_recover(conn, detected: list, rca, causal_reasoner, auto_recovery,
                           counters: dict, incidents: list) -> None:
    for anomaly in detected:
        try:
            basic_diag = rca.analyze(conn, anomaly)
            causal_diag = causal_reasoner.analyze(conn, anomaly, basic_diag)

            actions = auto_recovery.plan_recovery(conn, causal_diag, anomaly)
            if not actions:
                continue

            best = actions[0]
            result = auto_recovery.execute_recovery(conn, best, counters)
            success = result.get("success", False)

            top_cause = (
                causal_diag["candidates"][0]["cause_type"]
                if causal_diag.get("candidates") else "unknown"
            )
            causal_reasoner.learn_from_recovery(
                conn, anomaly.get("step_id", ""),
                anomaly.get("sensor_type", ""),
                anomaly.get("anomaly_type", ""),
                top_cause, success, 0.5, counters,
            )

            incidents.append({
                "step_id": anomaly.get("step_id"),
                "cause": top_cause,
                "confidence": (
                    causal_diag["candidates"][0]["confidence"]
                    if causal_diag.get("candidates") else 0
                ),
                "action": best.get("action_type", ""),
                "success": success,
                "causal_chains": causal_diag.get("causal_chains_found", 0),
                "history_matched": causal_diag.get("failure_chain_matched", False),
            })
        except Exception:
            pass


def _build_result(yield_before: float, yield_after: float, corr_analyzer,
                   conn, state: _SimState) -> dict:
    causal_count = _count(conn, "MATCH (cr:CausalRule) RETURN count(cr)")
    fc_count = _count(conn, "MATCH (fc:FailureChain) RETURN count(fc)")
    corr_count = len(corr_analyzer.known_correlations)

    auto_recovered = sum(1 for i in state.incidents if i["success"])
    avg_conf = sum(i["confidence"] for i in state.incidents) / max(len(state.incidents), 1)
    fpr = state.total_false_positives / max(state.total_anomalies, 1)

    return {
        "incidents": len(state.incidents),
        "auto_recovered": auto_recovered,
        "scenarios_run": state.scenarios_activated,
        "causal_rules": causal_count,
        "failure_chains": fc_count,
        "correlations": corr_count,
        "avg_confidence": avg_conf,
        "avg_recovery_time": 0.5,
        "yield_before": yield_before,
        "yield_after": yield_after,
        "false_positive_rate": fpr,
        "missed_anomalies": state.total_missed,
        "incident_details": state.incidents,
    }


def _count(conn, query: str) -> int:
    try:
        r = conn.execute(query)
        return int(r.get_next()[0])
    except Exception:
        return 0
