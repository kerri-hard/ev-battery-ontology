import type { EngineState, Metrics, HealingPhase, IncidentAnalysis } from '@/types';
import { addLog, pushHist, normalizeIncident, type EventHandler } from './helpers';

const healingInitialized: EventHandler = (state) => ({
  ...state,
  eventLog: addLog(state.eventLog, null, '자율 복구 엔진 초기화 완료'),
});

const healingLoopStarted: EventHandler = (state) => ({
  ...state,
  healing: { ...state.healing, running: true },
  eventLog: addLog(state.eventLog, null, '자율 복구 루프 시작'),
});

const healingLoopFinished: EventHandler = (state, data) => ({
  ...state,
  healing: {
    ...state.healing,
    iteration: (data.total_iterations as number) || state.healing.iteration,
    running: false,
    incidents: (data.total_incidents as number) || state.healing.incidents,
    autoRecovered: (data.auto_recovered as number) || state.healing.autoRecovered,
  },
  healingPhase: null,
  eventLog: addLog(
    state.eventLog,
    null,
    `자율 복구 완료 — ${data.total_incidents}건 중 ${data.auto_recovered}건 자동 복구`,
  ),
});

const healingError: EventHandler = (state, data) => ({
  ...state,
  eventLog: addLog(state.eventLog, null, `복구 오류: ${data.error}`),
});

const senseDone: EventHandler = (state, data) => ({
  ...state,
  healingPhase: 'sense' as HealingPhase,
  eventLog: addLog(
    state.eventLog,
    null,
    `센서 ${data.reading_count}건 수집, 이상 ${data.anomaly_count_raw}건`,
  ),
});

const detectDone: EventHandler = (state, data) => {
  const anomalies = (data.anomalies as unknown[]) || [];
  const steps = (data.steps_affected as string[]) || [];
  return {
    ...state,
    healingPhase: 'detect' as HealingPhase,
    eventLog: addLog(
      state.eventLog,
      null,
      anomalies.length > 0 ? `이상 감지: ${anomalies.length}건 (${steps.join(', ')})` : '정상 — 이상 없음',
    ),
  };
};

const allClear: EventHandler = (state) => ({
  ...state,
  healingPhase: null,
  eventLog: addLog(state.eventLog, null, '모든 센서 정상'),
});

const diagnoseDone: EventHandler = (state, data) => {
  const diags = (data.diagnoses as Record<string, unknown>[]) || [];
  const crossInv = (data.cross_investigations as Record<string, unknown>[]) || [];
  const msgs = diags.map((d) => {
    const base = `${d.step_id}: ${d.top_cause} (${((d.confidence as number) * 100).toFixed(0)}%)`;
    const chain = d.causal_chain as string | undefined;
    const history = Boolean(d.history_matched);
    if (chain && history) return `${base} [체인+이력]`;
    if (chain) return `${base} [체인]`;
    if (history) return `${base} [이력]`;
    return base;
  });
  return {
    ...state,
    healingPhase: 'diagnose' as HealingPhase,
    crossInvestigations: crossInv.length > 0 ? crossInv : state.crossInvestigations,
    eventLog: addLog(state.eventLog, null, `원인 진단: ${msgs.join(', ')}`),
  };
};

const recoverDone: EventHandler = (state, data) => {
  const actions = (data.actions as Record<string, unknown>[]) || [];
  const ok = actions.filter((a) => a.success).length;
  const top = actions[0] || {};
  const src = (top.playbook_source as string) || 'n/a';
  const pid = (top.playbook_id as string) || '-';
  return {
    ...state,
    healingPhase: 'recover' as HealingPhase,
    eventLog: addLog(
      state.eventLog,
      null,
      `자동 복구 ${ok}/${actions.length}건 성공 (playbook ${pid}/${src})`,
    ),
  };
};

const verifyDone: EventHandler = (state, data) => {
  const vm = data.metrics as Metrics | undefined;
  const predictive = (data.predictive as Record<string, unknown>[]) || state.phase4?.latest_predictive || [];
  if (!vm) {
    return { ...state, healingPhase: 'verify' as HealingPhase };
  }
  return {
    ...state,
    healingPhase: 'verify' as HealingPhase,
    prevMetrics: state.metrics,
    metrics: vm,
    metricsHistory: {
      nodes: pushHist(state.metricsHistory.nodes, vm.total_nodes),
      edges: pushHist(state.metricsHistory.edges, vm.total_edges),
      yield: pushHist(state.metricsHistory.yield, vm.line_yield * 100),
      completeness: pushHist(state.metricsHistory.completeness, vm.completeness_score),
    },
    phase4: {
      predictive_agent: true,
      nl_diagnoser: state.phase4?.nl_diagnoser ?? false,
      llm_orchestrator: state.phase4?.llm_orchestrator ?? false,
      model: state.phase4?.model ?? 'none',
      latest_predictive: predictive,
      orchestrator_traces: state.phase4?.orchestrator_traces || [],
    },
    eventLog: addLog(state.eventLog, null, `검증 완료 — 수율: ${(vm.line_yield * 100).toFixed(2)}%`),
  };
};

const learnDoneHealing: EventHandler = (state, data) => {
  const incidents = (data.incidents_recorded as number) || 0;
  const autoRecovered = (data.auto_recovered_count as number) || 0;
  const l3Links = (data.l3_links_created as number) || 0;
  const recent = ((data.recent_incidents as Record<string, unknown>[]) || []).map(normalizeIncident);
  return {
    ...state,
    healingPhase: 'learn_healing' as HealingPhase,
    healing: {
      ...state.healing,
      iteration: state.healing.iteration + 1,
      incidents: state.healing.incidents + incidents,
      autoRecovered: state.healing.autoRecovered + autoRecovered,
      recentIncidents: recent.length > 0 ? recent : state.healing.recentIncidents,
    },
    l3Snapshot: (data.l3_snapshot as Record<string, unknown>) || state.l3Snapshot,
    eventLog: addLog(state.eventLog, null, `학습 완료 — ${incidents}건 이력, L3 링크 ${l3Links}건`),
  };
};

const incidentAnalysis: EventHandler = (state, data) => ({
  ...state,
  latestAnalysis: data as unknown as IncidentAnalysis,
  eventLog: addLog(state.eventLog, null, `LLM 분석 완료: ${(data.summary as string)?.slice(0, 40)}...`),
});

const correlationFound: EventHandler = (state, data) => ({
  ...state,
  correlations: (data.correlations as EngineState['correlations']) || state.correlations,
  eventLog: addLog(state.eventLog, null, `상관분석: ${data.total_found}개 발견, ${data.stored_new}개 저장`),
});

export const healingHandlers: Record<string, EventHandler> = {
  healing_initialized: healingInitialized,
  healing_loop_started: healingLoopStarted,
  healing_loop_finished: healingLoopFinished,
  healing_error: healingError,
  sense_done: senseDone,
  detect_done: detectDone,
  all_clear: allClear,
  diagnose_done: diagnoseDone,
  recover_done: recoverDone,
  verify_done: verifyDone,
  learn_done_healing: learnDoneHealing,
  incident_analysis: incidentAnalysis,
  correlation_found: correlationFound,
};
