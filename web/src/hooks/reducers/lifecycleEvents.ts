import type { EngineState, Metrics, Agent, ProcessStep, PreverifyState } from '@/types';
import { addLog, normalizeHealingFromState, type EventHandler } from './helpers';

const stateSync: EventHandler = (state, data) => {
  const m = data.metrics as Metrics | null;
  return {
    ...state,
    connectionStatus: 'connected',
    iteration: (data.iteration as number) || 0,
    maxIterations: (data.max_iterations as number) || 10,
    running: (data.running as boolean) || false,
    paused: (data.paused as boolean) || false,
    speed: (data.speed as number) || 1.0,
    metrics: m,
    initialMetrics: (data.initial_metrics as Metrics | null) || state.initialMetrics,
    agents: (data.agents as Agent[]) || [],
    skills: ((data.skills as Record<string, unknown>) as EngineState['skills']) || {},
    history: (data.history as EngineState['history']) || [],
    healing: normalizeHealingFromState(data, state.healing),
    phase4: (data.phase4 as EngineState['phase4']) || state.phase4,
    preverify: mergePreverifyMetrics(state.preverify, data.preverify as Record<string, unknown> | undefined),
    recurrence: (data.recurrence as EngineState['recurrence']) ?? state.recurrence,
    slo: (data.slo as EngineState['slo']) ?? state.slo,
    l3Snapshot: (data.l3_snapshot as Record<string, unknown>) || state.l3Snapshot,
    l3Trends: (data.l3_trends as Record<string, unknown>[]) || state.l3Trends,
    eventLog: addLog(state.eventLog, null, '서버 연결됨'),
  };
};

function mergePreverifyMetrics(
  prev: PreverifyState | undefined,
  raw: Record<string, unknown> | undefined,
): PreverifyState | undefined {
  if (!raw) return prev;
  return {
    latestPlans: prev?.latestPlans ?? [],
    iteration: prev?.iteration ?? 0,
    autoRejectedThisRound: prev?.autoRejectedThisRound ?? 0,
    mae_recent: Number(raw.mae_recent ?? 0),
    sign_accuracy_recent: Number(raw.sign_accuracy_recent ?? 0),
    samples_recent: Number(raw.samples_recent ?? 0),
    auto_rejected_total: Number(raw.auto_rejected_total ?? 0),
    plans_total: Number(raw.plans_total ?? 0),
    auto_reject_rate: Number(raw.auto_reject_rate ?? 0),
    current_thresholds: (raw.current_thresholds as Record<string, number>) ?? prev?.current_thresholds ?? {},
    thresholds_history: (raw.thresholds_history as PreverifyState['thresholds_history']) ?? prev?.thresholds_history,
  };
}

const initialized: EventHandler = (state, data) => {
  const im = data.initial_metrics as Metrics;
  const graph = data.graph as EngineState['graphData'];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rawSteps = (graph?.steps || []) as any[];
  const steps: ProcessStep[] = rawSteps.map((s) => ({
    id: s.id as string, name: s.name as string,
    area: (s.area || s.area_id) as string,
    yield: (s.yield_rate || s.yield) as number,
    auto: s.auto as string, oee: (s.oee || 0.85) as number,
    cycle: s.cycle as number, safety: s.safety as string,
    equipment: s.equipment as string, sigma: (s.sigma || 3.0) as number,
  }));
  return {
    ...state,
    initialMetrics: im,
    metrics: im,
    prevMetrics: null,
    graphData: graph,
    steps,
    agents: (data.agents as Agent[]) || [],
    iteration: 0,
    currentPhase: null,
    debate: { proposals: null, votes: null, applied: null, evaluation: null, learning: null },
    metricsHistory: {
      nodes: [im.total_nodes],
      edges: [im.total_edges],
      yield: [im.line_yield * 100],
      completeness: [im.completeness_score],
    },
    eventLog: addLog(state.eventLog, null, '엔진 초기화 완료'),
  };
};

const loopStarted: EventHandler = (state, data) => ({
  ...state,
  running: true,
  maxIterations: (data.max_iterations as number) || 10,
  eventLog: addLog(state.eventLog, null, '자동 루프 시작'),
});

const loopFinished: EventHandler = (state, data) => ({
  ...state,
  running: false,
  eventLog: addLog(state.eventLog, null, `루프 완료 — ${data.total_iterations}회 반복`),
});

const converged: EventHandler = (state, data) => ({
  ...state,
  running: false,
  eventLog: addLog(state.eventLog, null, `수렴 감지 (반복 ${data.iteration})`),
});

const paused: EventHandler = (state) => ({
  ...state,
  paused: true,
  eventLog: addLog(state.eventLog, null, '일시정지'),
});

const resumed: EventHandler = (state) => ({
  ...state,
  paused: false,
  eventLog: addLog(state.eventLog, null, '재개'),
});

const speedChanged: EventHandler = (state, data) => ({
  ...state,
  speed: data.speed as number,
});

const phaseMessage: EventHandler = (state, data) => ({
  ...state,
  eventLog: addLog(state.eventLog, null, data.message as string),
});

export const lifecycleHandlers: Record<string, EventHandler> = {
  connected: stateSync,
  state: stateSync,
  initialized,
  loop_started: loopStarted,
  loop_finished: loopFinished,
  converged,
  paused,
  resumed,
  speed_changed: speedChanged,
  phase_ontology: phaseMessage,
  phase_healing: phaseMessage,
};
