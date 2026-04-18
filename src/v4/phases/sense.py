"""SENSE 페이즈 — 센서 데이터 수집 + 상관분석.

ⓘ 시나리오 주입 (4 이터레이션마다 무작위 활성화)
ⓘ 원시 readings 수집/저장
ⓘ 센서 간 상관계수 계산 → 새로운 상관관계 온톨로지 등록
"""
import asyncio

from v4.sensor_simulator import store_readings


async def maybe_activate_scenario(engine, it: int) -> None:
    """4 이터레이션마다 활성 시나리오가 없으면 무작위로 주입한다."""
    engine.scenario_engine.tick()
    if it % 4 == 1 and not engine.scenario_engine.get_active_scenarios():
        activated = engine.scenario_engine.activate_random()
        if activated:
            await engine._emit("scenario_activated", {
                "iteration": it + 1,
                "scenario": activated,
            })


async def run(engine, it: int, delay: float) -> dict:
    """센서 readings 수집 + 상관분석.

    Returns: {"readings": [...], "anomaly_count_raw": int}
    """
    await engine._emit("phase", {
        "iteration": it + 1,
        "phase": "sense",
        "message": "센서 데이터를 수집합니다...",
    })
    await asyncio.sleep(delay)

    readings = engine.sensor_sim.generate_readings()
    store_readings(engine.conn, readings, engine.healing_counters)

    anomaly_count_raw = sum(1 for r in readings if r.get("out_of_range", False))

    await engine._emit("sense_done", {
        "iteration": it + 1,
        "reading_count": len(readings),
        "anomaly_count_raw": anomaly_count_raw,
    })
    await asyncio.sleep(delay)

    await _correlate(engine, it, readings)

    return {"readings": readings, "anomaly_count_raw": anomaly_count_raw}


async def _correlate(engine, it: int, readings: list) -> None:
    """센서 간 상관관계 분석 — it >= 1 부터 매 이터레이션 실행."""
    engine.correlation_analyzer.ingest(readings)
    if it < 1:
        return

    correlations = engine.correlation_analyzer.analyze_all()
    if not correlations:
        return

    stored = engine.cross_investigator.store_discovered_correlations(
        engine.conn, correlations, engine.healing_counters,
    )
    await engine._emit("correlation_found", {
        "iteration": it + 1,
        "correlations": [
            {
                "source": c["source_step"],
                "target": c["target_step"],
                "coefficient": c["coefficient"],
                "direction": c["direction"],
                "sensors": f"{c['source_sensor']}↔{c['target_sensor']}",
            }
            for c in correlations[:5]
        ],
        "total_found": len(correlations),
        "stored_new": stored,
    })
