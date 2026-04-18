import type { EngineState, Metrics, Agent, ProcessStep, Phase, HealingPhase } from '@/types';
import { addLog, pushHist, type EventHandler } from './helpers';

const HEALING_PHASES = new Set(['sense', 'detect', 'diagnose', 'recover', 'verify', 'learn_healing']);

const phase: EventHandler = (state, data) => {
  if (HEALING_PHASES.has(String(data.phase))) {
    return {
      ...state,
      healingPhase: data.phase as HealingPhase,
      eventLog: addLog(state.eventLog, null, data.message as string),
    };
  }
  return {
    ...state,
    currentPhase: data.phase as Phase,
    iteration: (data.iteration as number) || state.iteration,
    eventLog: addLog(state.eventLog, data.phase as Phase, data.message as string),
  };
};

const observeDone: EventHandler = (state, data) => {
  const m = data.metrics as Metrics;
  return {
    ...state,
    prevMetrics: state.metrics,
    metrics: m,
    eventLog: addLog(
      state.eventLog,
      'observe',
      `노드: ${m.total_nodes}, 엣지: ${m.total_edges}, 수율: ${(m.line_yield * 100).toFixed(2)}%`,
    ),
  };
};

const proposeDone: EventHandler = (state, data) => ({
  ...state,
  debate: { ...state.debate, proposals: data as unknown as EngineState['debate']['proposals'] },
  eventLog: addLog(state.eventLog, 'propose', `${data.total}개 제안 생성`),
});

const debateDone: EventHandler = (state, data) => ({
  ...state,
  debate: { ...state.debate, votes: data as unknown as EngineState['debate']['votes'] },
  eventLog: addLog(state.eventLog, 'debate', `승인: ${data.approved_count}, 거부: ${data.rejected_count}`),
});

const applyDone: EventHandler = (state, data) => ({
  ...state,
  debate: { ...state.debate, applied: data as unknown as EngineState['debate']['applied'] },
  eventLog: addLog(state.eventLog, 'apply', `적용: ${data.applied}, 실패: ${data.failed}`),
});

const evaluateDone: EventHandler = (state, data) => {
  const postM = data.post as Metrics;
  return {
    ...state,
    prevMetrics: data.pre as Metrics,
    metrics: postM,
    debate: { ...state.debate, evaluation: data as unknown as EngineState['debate']['evaluation'] },
    eventLog: addLog(
      state.eventLog,
      'evaluate',
      `완성도 Δ${(data.evaluation as Record<string, unknown>)?.score_delta ?? 0}`,
    ),
  };
};

const learnDone: EventHandler = (state, data) => ({
  ...state,
  agents: (data.agents as Agent[]) || state.agents,
  debate: { ...state.debate, learning: data as unknown as EngineState['debate']['learning'] },
  eventLog: addLog(
    state.eventLog,
    'learn',
    `${(data.learning_log as unknown[])?.length || 0}명 신뢰도 변경`,
  ),
});

const iterationComplete: EventHandler = (state, data) => {
  const m = data.metrics as Metrics;
  const newSteps = (data.steps as ProcessStep[]) || state.steps;
  return {
    ...state,
    metrics: m,
    agents: (data.agents as Agent[]) || state.agents,
    skills: (data.skills as EngineState['skills']) || state.skills,
    steps: newSteps,
    currentPhase: null,
    debate: { proposals: null, votes: null, applied: null, evaluation: null, learning: null },
    metricsHistory: {
      nodes: pushHist(state.metricsHistory.nodes, m.total_nodes),
      edges: pushHist(state.metricsHistory.edges, m.total_edges),
      yield: pushHist(state.metricsHistory.yield, m.line_yield * 100),
      completeness: pushHist(state.metricsHistory.completeness, m.completeness_score),
    },
    eventLog: addLog(state.eventLog, null, `── 반복 ${data.iteration} 완료 ──`),
  };
};

export const v3Handlers: Record<string, EventHandler> = {
  phase,
  observe_done: observeDone,
  propose_done: proposeDone,
  debate_done: debateDone,
  apply_done: applyDone,
  evaluate_done: evaluateDone,
  learn_done: learnDone,
  iteration_complete: iterationComplete,
};
