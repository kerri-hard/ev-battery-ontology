"""DETECT 페이즈 — SPC + Advanced 이상 감지 + 알람 저장."""
import asyncio

from v4.sensor_simulator import store_alarm


async def run(engine, it: int, delay: float, readings: list) -> dict:
    """이상 감지: SPC 기본 + Matrix Profile/Isolation Forest 보강.

    Returns: {"anomalies": [...], "alarm_count": int, "steps_affected": [...]}
    """
    await engine._emit("phase", {
        "iteration": it + 1,
        "phase": "detect",
        "message": "이상 패턴을 감지합니다...",
    })
    await asyncio.sleep(delay)

    anomalies = _detect_anomalies(engine, readings)
    alarms = _store_alarms(engine, readings)

    steps_affected = list({a.get("step_id", "unknown") for a in anomalies})

    await engine._emit("detect_done", {
        "iteration": it + 1,
        "anomalies": [
            {
                "step_id": a.get("step_id"),
                "sensor": a.get("sensor"),
                "type": a.get("type", "unknown"),
                "severity": a.get("severity", "medium"),
                "value": a.get("value"),
            }
            for a in anomalies
        ],
        "alarm_count": len(alarms),
        "steps_affected": steps_affected,
    })
    await asyncio.sleep(delay)

    if not anomalies:
        await engine._emit("all_clear", {
            "iteration": it + 1,
            "message": "이상 없음 - 모든 센서 정상 범위",
            "reading_count": len(readings),
        })

    return {
        "anomalies": anomalies,
        "alarm_count": len(alarms),
        "steps_affected": steps_affected,
    }


def _detect_anomalies(engine, readings: list) -> list:
    """SPC + Advanced 감지 — 중복(step_id 기준) 제외하여 advanced 결과 보강."""
    engine.anomaly_detector.update(readings)
    anomalies = engine.anomaly_detector.detect(readings)

    engine.advanced_detector.update(readings)
    advanced_anomalies = engine.advanced_detector.detect(readings)
    spc_steps = {a.get("step_id") for a in anomalies}
    for adv in advanced_anomalies:
        if adv.get("step_id") not in spc_steps:
            anomalies.append(adv)
    return anomalies


def _store_alarms(engine, readings: list) -> list:
    """경보 임계 초과 시 Alarm 노드 생성."""
    alarms = engine.sensor_sim.check_alarms(readings)
    for alarm in alarms:
        store_alarm(engine.conn, alarm, engine.healing_counters)
    return alarms
