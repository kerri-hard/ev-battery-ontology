"""RECOVER 페이즈 — 다단계 복구 + HITL escalation + 대체 경로."""
import asyncio
import time
from datetime import datetime

from v4.healing_agents import requires_hitl


async def run(engine, it: int, delay: float, anomalies: list, diagnoses: list) -> dict:
    """진단 → 복구 액션 실행. HITL 필요 시 큐에 적재.

    Returns: {"recovery_results": [...]}
    """
    await engine._emit("phase", {
        "iteration": it + 1,
        "phase": "recover",
        "message": "자동 복구를 실행합니다...",
    })
    await asyncio.sleep(delay)

    recovery_results = []
    for diagnosis, anomaly in zip(diagnoses, anomalies):
        rr = await _recover_one(engine, it, diagnosis, anomaly)
        recovery_results.append(rr)

    await engine._emit("recover_done", {
        "iteration": it + 1,
        "actions": recovery_results,
    })
    await asyncio.sleep(delay)

    return {"recovery_results": recovery_results}


async def _recover_one(engine, it: int, diagnosis: dict, anomaly: dict) -> dict:
    """단일 이상에 대한 복구 시도 — escalating risk + 백오프 재시도."""
    step_id = anomaly.get("step_id")
    pre_yield_baseline = engine._get_step_yield(step_id)

    try:
        actions = engine.auto_recovery.plan_recovery(engine.conn, diagnosis, anomaly)
    except Exception as exc:
        return _error_result(anomaly, str(exc))

    if not actions:
        return {
            "step_id": step_id,
            "action_type": "none",
            "target": None,
            "success": False,
            "pre_yield": pre_yield_baseline,
            "detail": "복구 액션을 생성하지 못함",
        }

    hitl_needed, hitl_reason = _check_hitl(engine, actions[0], diagnosis, step_id)

    recovery_success, executed_action, result, retries, recovery_time = \
        await _execute_actions(engine, it, step_id, actions, hitl_needed)

    if retries > 0:
        await engine._emit("recovery_retry_backoff", {
            "iteration": it + 1,
            "step_id": step_id,
            "total_retries": retries,
            "final_success": recovery_success,
        })

    if not recovery_success:
        recovery_success, executed_action = _try_alternate_path(
            engine, step_id, recovery_success, executed_action,
        )

    if not recovery_success and hitl_needed:
        return await _enqueue_hitl(
            engine, it, anomaly, diagnosis, actions, step_id,
            hitl_reason, pre_yield_baseline,
        )

    final_action = executed_action or (actions[0] if actions else {})
    return {
        "step_id": step_id,
        "action_type": final_action.get("action_type", "unknown"),
        "target": final_action.get("target_step"),
        "success": recovery_success,
        "recovery_id": result.get("recovery_id") if recovery_success else None,
        "pre_yield": pre_yield_baseline,
        "detail": result.get("detail", "") if recovery_success else "모든 복구 액션 실패",
        "risk_level": final_action.get("risk_level"),
        "confidence": final_action.get("confidence"),
        "playbook_id": final_action.get("playbook_id"),
        "playbook_source": final_action.get("playbook_source"),
        "hitl_required": False,
        "recovery_time_sec": round(recovery_time, 4),
    }


def _check_hitl(engine, first_action: dict, diagnosis: dict, step_id: str) -> tuple[bool, str]:
    """안전등급별 confidence 임계로 HITL 필요 여부 판정."""
    step_safety = engine._get_step_safety_level(step_id)
    base_min = float(engine.hitl_policy.get("min_confidence", 0.40))
    safety_confidence = {
        'A': max(0.65, base_min),
        'B': base_min,
        'C': min(0.35, base_min),
    }.get(step_safety, base_min)

    return requires_hitl(
        first_action,
        diagnosis,
        min_confidence=safety_confidence,
        high_risk_threshold=float(engine.hitl_policy.get("high_risk_threshold", 0.6)),
        medium_requires_history=bool(engine.hitl_policy.get("medium_requires_history", True)),
    )


async def _execute_actions(engine, it: int, step_id: str, actions: list,
                            hitl_needed: bool) -> tuple[bool, dict | None, dict, int, float]:
    """LOW → MEDIUM → HIGH 순으로 최대 3개 액션 시도. HITL 필요 시 HIGH/CRITICAL 스킵."""
    recovery_success = False
    executed_action = None
    result: dict = {}
    total_retries = 0
    started = time.time()

    for action in actions[:3]:
        if hitl_needed and action.get("risk_level") in ("HIGH", "CRITICAL"):
            continue
        result, attempts = await engine._execute_recovery_with_backoff(action)
        total_retries += max(0, attempts - 1)
        if result.get("success"):
            recovery_success = True
            executed_action = action
            break

    return recovery_success, executed_action, result, total_retries, time.time() - started


def _try_alternate_path(engine, step_id: str, recovery_success: bool,
                        executed_action: dict | None) -> tuple[bool, dict | None]:
    """모든 1차 복구 실패 시 ResilienceOrchestrator로 대체 경로 시도."""
    if recovery_success:
        return recovery_success, executed_action

    alts = engine.resilience.find_alternate_path(engine.conn, step_id)
    if not alts:
        return recovery_success, executed_action

    alt_result = engine.resilience.activate_alternate(engine.conn, step_id, alts[0])
    if not alt_result.get("success"):
        return recovery_success, executed_action

    return True, {
        "action_type": "ALTERNATE_PATH",
        "target_step": step_id,
        "parameter": None,
        "old_value": None,
        "new_value": alt_result.get("alternate"),
        "confidence": 0.5,
        "risk_level": "MEDIUM",
        "cause_type": "alternate_path",
        "cause_name": f"alternate via {alt_result.get('type', 'unknown')}",
        "playbook_source": "resilience_orchestrator",
        "playbook_id": None,
    }


async def _enqueue_hitl(engine, it: int, anomaly: dict, diagnosis: dict,
                         actions: list, step_id: str, hitl_reason: str,
                         pre_yield_baseline) -> dict:
    """HITL 큐에 대기 항목 적재."""
    best_action = actions[0] if actions else {"risk_level": "CRITICAL", "confidence": 0.0}
    pending_id = f"HITL-{it + 1:04d}-{len(engine.hitl_pending) + 1:03d}"
    pending = {
        "id": pending_id,
        "iteration": it + 1,
        "created_at": datetime.now().isoformat(),
        "step_id": step_id,
        "anomaly_type": anomaly.get("anomaly_type", "unknown"),
        "top_cause": diagnosis["candidates"][0]["cause_type"] if diagnosis.get("candidates") else "unknown",
        "reason": hitl_reason,
        "action": best_action,
        "status": "pending",
    }
    engine.hitl_pending.append(pending)
    engine.hitl_pending = engine.hitl_pending[-50:]
    engine._append_hitl_audit("queued", "system", {
        "hitl_id": pending_id,
        "step_id": step_id,
        "reason": hitl_reason,
    })
    engine._persist_hitl_runtime_state()
    await engine._emit("recover_pending_hitl", pending)

    return {
        "step_id": step_id,
        "action_type": "ESCALATE",
        "target": best_action.get("target_step"),
        "success": False,
        "recovery_id": None,
        "pre_yield": pre_yield_baseline,
        "detail": f"HITL required: {hitl_reason}",
        "risk_level": best_action.get("risk_level"),
        "confidence": best_action.get("confidence"),
        "playbook_id": best_action.get("playbook_id"),
        "playbook_source": best_action.get("playbook_source"),
        "hitl_required": True,
        "hitl_id": pending_id,
    }


def _error_result(anomaly: dict, err: str) -> dict:
    return {
        "step_id": anomaly.get("step_id"),
        "action_type": "error",
        "target": None,
        "success": False,
        "pre_yield": None,
        "detail": err,
        "recovery_time_sec": None,
    }
