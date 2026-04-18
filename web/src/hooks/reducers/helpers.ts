import type { EngineState, Phase, LogEntry, HealingIncident } from '@/types';

export const MAX_LOG = 200;
export const MAX_HISTORY = 30;

export type EventHandler = (state: EngineState, data: Record<string, unknown>) => EngineState;

export function now(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
}

export function addLog(logs: LogEntry[], phase: Phase | null, message: string): LogEntry[] {
  const next = [...logs, { ts: now(), phase, message }];
  return next.length > MAX_LOG ? next.slice(-MAX_LOG) : next;
}

export function pushHist(arr: number[], val: number): number[] {
  const next = [...arr, val];
  return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next;
}

export function normalizeIncident(raw: Record<string, unknown>): HealingIncident {
  return {
    id: raw.id as string | undefined,
    step_id: (raw.step_id as string) || 'unknown',
    cause: (raw.cause as string) || (raw.top_cause as string) || 'unknown',
    action: (raw.action as string) || (raw.action_type as string) || 'none',
    top_cause: raw.top_cause as string | undefined,
    action_type: raw.action_type as string | undefined,
    severity: raw.severity as string | undefined,
    anomaly_type: raw.anomaly_type as string | undefined,
    confidence: raw.confidence as number | undefined,
    causal_chain: raw.causal_chain as string | undefined,
    history_matched: raw.history_matched as boolean | undefined,
    matched_chain_id: raw.matched_chain_id as string | undefined,
    candidates_count: raw.candidates_count as number | undefined,
    causal_chains_found: raw.causal_chains_found as number | undefined,
    analysis_method: raw.analysis_method as string | undefined,
    matched_pattern_id: raw.matched_pattern_id as string | undefined,
    matched_pattern_type: raw.matched_pattern_type as string | undefined,
    evidence_refs: raw.evidence_refs as string[] | undefined,
    rca_score_breakdown: raw.rca_score_breakdown as Record<string, number> | undefined,
    risk_level: raw.risk_level as string | undefined,
    playbook_id: raw.playbook_id as string | undefined,
    playbook_source: raw.playbook_source as string | undefined,
    hitl_required: raw.hitl_required as boolean | undefined,
    hitl_id: raw.hitl_id as string | undefined,
    escalation_reason: (raw.escalation_reason as string | undefined) ?? null,
    improved: raw.improved as boolean | undefined,
    pre_yield: raw.pre_yield as number | undefined,
    post_yield: raw.post_yield as number | undefined,
    auto_recovered: Boolean(raw.auto_recovered),
    timestamp: raw.timestamp as string | undefined,
  };
}

export function normalizeHealingFromState(
  data: Record<string, unknown>,
  prev: EngineState['healing'],
): EngineState['healing'] {
  const healingRaw = (data.healing as Record<string, unknown>) || {};
  const rawIncidents = (healingRaw.recent_incidents as Record<string, unknown>[]) || [];
  return {
    iteration: (healingRaw.iteration as number) ?? prev.iteration,
    running: (healingRaw.running as boolean) ?? prev.running,
    incidents: (healingRaw.incidents as number) ?? prev.incidents,
    autoRecovered: (healingRaw.auto_recovered as number) ?? prev.autoRecovered,
    recentIncidents: rawIncidents.map(normalizeIncident),
    recurrenceKpis: (healingRaw.recurrence_kpis as EngineState['healing']['recurrenceKpis']) || prev.recurrenceKpis,
    hitlPending: (healingRaw.hitl_pending as Record<string, unknown>[]) || prev.hitlPending || [],
    hitlAudit: (healingRaw.hitl_audit as Record<string, unknown>[]) || prev.hitlAudit || [],
    hitlPolicy: (healingRaw.hitl_policy as EngineState['healing']['hitlPolicy']) || prev.hitlPolicy,
  };
}
