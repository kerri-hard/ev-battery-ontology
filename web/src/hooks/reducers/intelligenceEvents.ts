import type { CausalDiscoveryResult, EvolutionCycleResult, OrchestratorDecision } from '@/types';
import { addLog, type EventHandler } from './helpers';

const orchestratorTrace: EventHandler = (state, data) => {
  const traces = [...(state.phase4?.orchestrator_traces || []), data].slice(-30);
  return {
    ...state,
    phase4: {
      predictive_agent: state.phase4?.predictive_agent ?? false,
      nl_diagnoser: state.phase4?.nl_diagnoser ?? false,
      llm_orchestrator: state.phase4?.llm_orchestrator ?? false,
      model: state.phase4?.model ?? 'none',
      latest_predictive: state.phase4?.latest_predictive || [],
      orchestrator_traces: traces,
    },
    eventLog: addLog(
      state.eventLog,
      null,
      `Orchestrator: ${(data.intent as string) || 'intent'} -> ${(data.delegated_to as string) || 'agent'}`,
    ),
  };
};

const causalCalibrated: EventHandler = (state, data) => ({
  ...state,
  eventLog: addLog(
    state.eventLog,
    null,
    `인과 보정 완료 — chains ${(data.scanned_chains as number) || 0}, rules ${(data.updated_rules as number) || 0}`,
  ),
});

const causalDiscoveryDone: EventHandler = (state, data) => {
  const promoted = (data.promoted_rules as unknown[]) || [];
  return {
    ...state,
    causalDiscovery: {
      candidates_tested: (data.candidates_tested as number) || 0,
      after_pruning: (data.after_pruning as number) || 0,
      promoted_rules: promoted as CausalDiscoveryResult['promoted_rules'],
      total_discovered: (data.total_discovered as number) || 0,
    },
    eventLog: addLog(
      state.eventLog,
      null,
      `인과 발견: ${data.candidates_tested}쌍 테스트 → ${promoted.length}개 신규 규칙 승격`,
    ),
  };
};

const evolutionCycleDone: EventHandler = (state, data) => ({
  ...state,
  evolutionCycle: {
    cycle_number: (data.cycle_number as number) || 0,
    strategies_run: (data.strategies_run as number) || 0,
    strategies_improved: (data.strategies_improved as number) || 0,
    strategy_summary: (data.strategy_summary as EvolutionCycleResult['strategy_summary']) || [],
    mutations_tested: (data.mutations_tested as number) || 0,
    best_strategy: data.best_strategy as string | undefined,
    overall_fitness: (data.overall_fitness as number) || 0.5,
  },
  eventLog: addLog(
    state.eventLog,
    null,
    `진화 사이클 #${data.cycle_number}: ${data.strategies_run}전략, ${data.strategies_improved}개선, 최적=${data.best_strategy || 'none'}`,
  ),
});

const orchestratorDecision: EventHandler = (state, data) => ({
  ...state,
  latestOrchestratorDecision: {
    step_id: (data.step_id as string) || '',
    path: (data.path as OrchestratorDecision['path']) || 'rule_based',
    reason: (data.reason as string) || '',
    complexity_score: (data.complexity_score as number) || 0,
  },
  eventLog: addLog(
    state.eventLog,
    null,
    `Orchestrator: ${data.step_id} → ${data.path} (복잡도 ${(((data.complexity_score as number) || 0) * 100).toFixed(0)}%)`,
  ),
});

const learningRecordCreated: EventHandler = (state, data) => ({
  ...state,
  latestLearningRecord: {
    iteration: (data.iteration as number) || state.iteration,
    record_id: (data.record_id as string) || '',
    cycle_number: (data.cycle_number as number) || 0,
    overall_fitness: (data.overall_fitness as number) || 0.5,
    improvement_delta: (data.improvement_delta as number) || 0,
    mutations_created: (data.mutations_created as number) || 0,
    supersedes_linked: Boolean(data.supersedes_linked),
  },
  eventLog: addLog(
    state.eventLog,
    null,
    `L5 학습 이력: ${data.record_id} 온톨로지 기록 — 전략 변형 ${data.mutations_created}개, 개선 ${(((data.improvement_delta as number) || 0) * 100).toFixed(2)}%p`,
  ),
});

const llmHypothesisGuarded: EventHandler = (state, data) => ({
  ...state,
  latestLLMSafetyGuard: {
    iteration: (data.iteration as number) || state.iteration,
    step_id: (data.step_id as string) || '',
    safety_level: (data.safety_level as string) || 'C',
    hypotheses_capped: (data.hypotheses_capped as number) || 0,
    reason: (data.reason as string) || '',
  },
  eventLog: addLog(
    state.eventLog,
    null,
    `안전 가드: ${data.step_id} (등급 ${data.safety_level}) — LLM 가설 ${data.hypotheses_capped}개 HITL 강제`,
  ),
});

const rulCritical: EventHandler = (state, data) => {
  const criticalList = (data.critical_equipment as Array<Record<string, unknown>>) || [];
  return {
    ...state,
    latestRULCritical: {
      iteration: (data.iteration as number) || state.iteration,
      upserted: (data.upserted as number) || 0,
      critical_equipment: criticalList.map((item) => ({
        equipment_id: (item.equipment_id as string) || '',
        step_id: item.step_id as string | undefined,
        priority: (item.priority as string) || 'P4-LOW',
        rul_hours_median: (item.rul_hours_median as number) || 0,
        risk_score: (item.risk_score as number) || 0,
      })),
    },
    eventLog: addLog(
      state.eventLog,
      null,
      `예지정비 경보: P1/P2 장비 ${criticalList.length}대 — RUL 온톨로지 ${(data.upserted as number) || 0}건 동기화`,
    ),
  };
};

export const intelligenceHandlers: Record<string, EventHandler> = {
  orchestrator_trace: orchestratorTrace,
  causal_calibrated: causalCalibrated,
  causal_discovery_done: causalDiscoveryDone,
  evolution_cycle_done: evolutionCycleDone,
  orchestrator_decision: orchestratorDecision,
  learning_record_created: learningRecordCreated,
  llm_hypothesis_guarded: llmHypothesisGuarded,
  rul_critical: rulCritical,
};
