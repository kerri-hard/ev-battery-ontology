import type { EngineState } from '@/types';
import { addLog, type EventHandler } from './helpers';

const recoverPendingHitl: EventHandler = (state, data) => {
  const id = (data.id as string) || 'HITL';
  const stepId = (data.step_id as string) || 'unknown';
  const reason = (data.reason as string) || 'policy_gate';
  const nextPending = [...(state.healing.hitlPending || []), data].slice(-30);
  const nextAudit = [
    ...(state.healing.hitlAudit || []),
    {
      ts: new Date().toISOString(),
      action: 'queued',
      operator: 'system',
      detail: { id, step_id: stepId, reason },
    },
  ].slice(-120);
  return {
    ...state,
    healing: { ...state.healing, hitlPending: nextPending, hitlAudit: nextAudit },
    eventLog: addLog(state.eventLog, null, `HITL 대기 ${id} (${stepId}) - ${reason}`),
  };
};

const hitlResolved: EventHandler = (state, data) => {
  const id = data.id as string;
  const status = (data.status as string) || 'resolved';
  const nextPending = (state.healing.hitlPending || []).map((p) =>
    p.id === id ? { ...p, status } : p,
  );
  const nextAudit = [
    ...(state.healing.hitlAudit || []),
    {
      ts: new Date().toISOString(),
      action: status,
      operator: (data.operator as string) || 'operator',
      detail: { id },
    },
  ].slice(-120);
  return {
    ...state,
    healing: { ...state.healing, hitlPending: nextPending, hitlAudit: nextAudit },
    eventLog: addLog(state.eventLog, null, `HITL ${id} 처리: ${status}`),
  };
};

const hitlPolicyUpdated: EventHandler = (state, data) => {
  const policy = (data.policy as EngineState['healing']['hitlPolicy']) || state.healing.hitlPolicy;
  const diff = (data.diff as Record<string, { from: unknown; to: unknown }>) || {};
  const diffKeys = Object.keys(diff);
  return {
    ...state,
    healing: {
      ...state.healing,
      hitlPolicy: policy,
      hitlAudit: [
        ...(state.healing.hitlAudit || []),
        {
          ts: new Date().toISOString(),
          action: 'policy_updated',
          operator: (data.operator as string) || 'operator',
          role: (data.role as string) || 'operator',
          detail: { policy, diff },
        },
      ].slice(-120),
    },
    eventLog: addLog(
      state.eventLog,
      null,
      `HITL 정책 업데이트 (${(data.role as string) || 'operator'}) — ${diffKeys.length}개 변경`,
    ),
  };
};

const hitlPolicyUpdateDenied: EventHandler = (state) => ({
  ...state,
  eventLog: addLog(state.eventLog, null, 'HITL 정책 업데이트 거절: supervisor 권한 필요'),
});

export const hitlHandlers: Record<string, EventHandler> = {
  recover_pending_hitl: recoverPendingHitl,
  hitl_resolved: hitlResolved,
  hitl_policy_updated: hitlPolicyUpdated,
  hitl_policy_update_denied: hitlPolicyUpdateDenied,
};
