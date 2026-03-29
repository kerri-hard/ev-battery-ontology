'use client';

import { useReducer, useEffect, useRef, useCallback } from 'react';
import type { EngineState, WSCommand, Phase, LogEntry, Agent, Metrics, ProcessStep, HealingPhase, HealingIncident, IncidentAnalysis } from '@/types';
import { wsUrl } from '@/lib/api';
const MAX_LOG = 200;
const MAX_HISTORY = 30;

const initialState: EngineState = {
  connectionStatus: 'connecting',
  iteration: 0,
  maxIterations: 10,
  running: false,
  paused: false,
  speed: 1.0,
  metrics: null,
  prevMetrics: null,
  initialMetrics: null,
  agents: [],
  skills: {},
  history: [],
  graphData: null,
  steps: [],
  currentPhase: null,
  debate: { proposals: null, votes: null, applied: null, evaluation: null, learning: null },
  eventLog: [],
  metricsHistory: { nodes: [], edges: [], yield: [], completeness: [] },
  latestAnalysis: null,
  correlations: [],
  healing: {
    iteration: 0,
    running: false,
    incidents: 0,
    autoRecovered: 0,
    recentIncidents: [],
    recurrenceKpis: {
      matched_chain_rate: 0,
      repeat_incident_rate: 0,
      matched_auto_recovery_rate: 0,
      matched_avg_recovery_sec: 0,
      unmatched_avg_recovery_sec: 0,
      total: 0,
    },
    hitlPending: [],
    hitlAudit: [],
    hitlPolicy: { min_confidence: 0.62, high_risk_threshold: 0.6, medium_requires_history: true },
  },
  healingPhase: null,
  phase4: {
    predictive_agent: false,
    nl_diagnoser: false,
    llm_orchestrator: false,
    model: 'none',
    latest_predictive: [],
    orchestrator_traces: [],
  },
};

type Action =
  | { type: 'SET_CONNECTED' }
  | { type: 'SET_DISCONNECTED' }
  | { type: 'WS_EVENT'; event: string; data: Record<string, unknown> };

function now() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
}

function addLog(logs: LogEntry[], phase: Phase | null, message: string): LogEntry[] {
  const next = [...logs, { ts: now(), phase, message }];
  return next.length > MAX_LOG ? next.slice(-MAX_LOG) : next;
}

function pushHist(arr: number[], val: number): number[] {
  const next = [...arr, val];
  return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next;
}

function normalizeIncident(raw: Record<string, unknown>): HealingIncident {
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

function normalizeHealingFromState(data: Record<string, unknown>, prev: EngineState['healing']): EngineState['healing'] {
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

function reducer(state: EngineState, action: Action): EngineState {
  switch (action.type) {
    case 'SET_CONNECTED':
      return { ...state, connectionStatus: 'connected' };
    case 'SET_DISCONNECTED':
      return { ...state, connectionStatus: 'disconnected' };
    case 'WS_EVENT': {
      const { event, data } = action;

      switch (event) {
        case 'connected':
        case 'state': {
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
            skills: (data.skills as Record<string, unknown>) as EngineState['skills'] || {},
            history: (data.history as EngineState['history']) || [],
            healing: normalizeHealingFromState(data, state.healing),
            phase4: (data.phase4 as EngineState['phase4']) || state.phase4,
            l3Snapshot: (data.l3_snapshot as Record<string, unknown>) || state.l3Snapshot,
            l3Trends: (data.l3_trends as Record<string, unknown>[]) || state.l3Trends,
            eventLog: addLog(state.eventLog, null, '서버 연결됨'),
          };
        }

        case 'initialized': {
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
            metricsHistory: { nodes: [im.total_nodes], edges: [im.total_edges], yield: [im.line_yield * 100], completeness: [im.completeness_score] },
            eventLog: addLog(state.eventLog, null, '엔진 초기화 완료'),
          };
        }

        case 'phase':
          if (['sense', 'detect', 'diagnose', 'recover', 'verify', 'learn_healing'].includes(String(data.phase))) {
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

        case 'observe_done': {
          const m = data.metrics as Metrics;
          return {
            ...state,
            prevMetrics: state.metrics,
            metrics: m,
            eventLog: addLog(state.eventLog, 'observe', `노드: ${m.total_nodes}, 엣지: ${m.total_edges}, 수율: ${(m.line_yield * 100).toFixed(2)}%`),
          };
        }

        case 'propose_done':
          return {
            ...state,
            debate: { ...state.debate, proposals: data as unknown as EngineState['debate']['proposals'] },
            eventLog: addLog(state.eventLog, 'propose', `${data.total}개 제안 생성`),
          };

        case 'debate_done':
          return {
            ...state,
            debate: { ...state.debate, votes: data as unknown as EngineState['debate']['votes'] },
            eventLog: addLog(state.eventLog, 'debate', `승인: ${data.approved_count}, 거부: ${data.rejected_count}`),
          };

        case 'apply_done':
          return {
            ...state,
            debate: { ...state.debate, applied: data as unknown as EngineState['debate']['applied'] },
            eventLog: addLog(state.eventLog, 'apply', `적용: ${data.applied}, 실패: ${data.failed}`),
          };

        case 'evaluate_done': {
          const postM = data.post as Metrics;
          return {
            ...state,
            prevMetrics: data.pre as Metrics,
            metrics: postM,
            debate: { ...state.debate, evaluation: data as unknown as EngineState['debate']['evaluation'] },
            eventLog: addLog(state.eventLog, 'evaluate', `완성도 Δ${(data.evaluation as Record<string, unknown>)?.score_delta ?? 0}`),
          };
        }

        case 'learn_done':
          return {
            ...state,
            agents: (data.agents as Agent[]) || state.agents,
            debate: { ...state.debate, learning: data as unknown as EngineState['debate']['learning'] },
            eventLog: addLog(state.eventLog, 'learn', `${(data.learning_log as unknown[])?.length || 0}명 신뢰도 변경`),
          };

        case 'iteration_complete': {
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
        }

        case 'loop_started':
          return { ...state, running: true, maxIterations: (data.max_iterations as number) || 10,
            eventLog: addLog(state.eventLog, null, '자동 루프 시작') };

        case 'loop_finished':
          return { ...state, running: false,
            eventLog: addLog(state.eventLog, null, `루프 완료 — ${data.total_iterations}회 반복`) };

        case 'converged':
          return { ...state, running: false,
            eventLog: addLog(state.eventLog, null, `수렴 감지 (반복 ${data.iteration})`) };

        case 'paused':
          return { ...state, paused: true, eventLog: addLog(state.eventLog, null, '일시정지') };

        case 'resumed':
          return { ...state, paused: false, eventLog: addLog(state.eventLog, null, '재개') };

        case 'speed_changed':
          return { ...state, speed: data.speed as number };

        // ── v4 Self-Healing Events ──

        case 'healing_initialized':
          return { ...state, eventLog: addLog(state.eventLog, null, '자율 복구 엔진 초기화 완료') };

        case 'healing_loop_started':
          return { ...state,
            healing: { ...state.healing, running: true },
            eventLog: addLog(state.eventLog, null, '자율 복구 루프 시작'),
          };

        case 'sense_done':
          return { ...state,
            healingPhase: 'sense' as HealingPhase,
            eventLog: addLog(state.eventLog, null, `센서 ${data.reading_count}건 수집, 이상 ${data.anomaly_count_raw}건`),
          };

        case 'detect_done': {
          const anomalies = (data.anomalies as unknown[]) || [];
          const steps = (data.steps_affected as string[]) || [];
          return { ...state,
            healingPhase: 'detect' as HealingPhase,
            eventLog: addLog(state.eventLog, null,
              anomalies.length > 0
                ? `이상 감지: ${anomalies.length}건 (${steps.join(', ')})`
                : '정상 — 이상 없음'),
          };
        }

        case 'all_clear':
          return { ...state,
            healingPhase: null,
            eventLog: addLog(state.eventLog, null, '모든 센서 정상'),
          };

        case 'diagnose_done': {
          const diags = (data.diagnoses as Record<string, unknown>[]) || [];
          const msgs = diags.map((d) => {
            const base = `${d.step_id}: ${d.top_cause} (${((d.confidence as number) * 100).toFixed(0)}%)`;
            const chain = d.causal_chain as string | undefined;
            const history = Boolean(d.history_matched);
            if (chain && history) return `${base} [체인+이력]`;
            if (chain) return `${base} [체인]`;
            if (history) return `${base} [이력]`;
            return base;
          });
          return { ...state,
            healingPhase: 'diagnose' as HealingPhase,
            eventLog: addLog(state.eventLog, null, `원인 진단: ${msgs.join(', ')}`),
          };
        }

        case 'recover_done': {
          const actions = (data.actions as Record<string, unknown>[]) || [];
          const ok = actions.filter(a => a.success).length;
          const top = actions[0] || {};
          const src = (top.playbook_source as string) || 'n/a';
          const pid = (top.playbook_id as string) || '-';
          return { ...state,
            healingPhase: 'recover' as HealingPhase,
            eventLog: addLog(state.eventLog, null, `자동 복구 ${ok}/${actions.length}건 성공 (playbook ${pid}/${src})`),
          };
        }

        case 'recover_pending_hitl': {
          const id = (data.id as string) || 'HITL';
          const stepId = (data.step_id as string) || 'unknown';
          const reason = (data.reason as string) || 'policy_gate';
          const nextPending = [...(state.healing.hitlPending || []), data].slice(-30);
          const nextAudit = [...(state.healing.hitlAudit || []), {
            ts: new Date().toISOString(),
            action: 'queued',
            operator: 'system',
            detail: { id, step_id: stepId, reason },
          }].slice(-120);
          return {
            ...state,
            healing: { ...state.healing, hitlPending: nextPending, hitlAudit: nextAudit },
            eventLog: addLog(state.eventLog, null, `HITL 대기 ${id} (${stepId}) - ${reason}`),
          };
        }

        case 'hitl_resolved': {
          const id = data.id as string;
          const status = (data.status as string) || 'resolved';
          const nextPending = (state.healing.hitlPending || []).map((p) =>
            (p.id === id ? { ...p, status } : p),
          );
          const nextAudit = [...(state.healing.hitlAudit || []), {
            ts: new Date().toISOString(),
            action: status,
            operator: (data.operator as string) || 'operator',
            detail: { id },
          }].slice(-120);
          return {
            ...state,
            healing: { ...state.healing, hitlPending: nextPending, hitlAudit: nextAudit },
            eventLog: addLog(state.eventLog, null, `HITL ${id} 처리: ${status}`),
          };
        }

        case 'hitl_policy_updated': {
          const policy = (data.policy as EngineState['healing']['hitlPolicy']) || state.healing.hitlPolicy;
          const diff = (data.diff as Record<string, { from: unknown; to: unknown }>) || {};
          const diffKeys = Object.keys(diff);
          return {
            ...state,
            healing: {
              ...state.healing,
              hitlPolicy: policy,
              hitlAudit: [...(state.healing.hitlAudit || []), {
                ts: new Date().toISOString(),
                action: 'policy_updated',
                operator: (data.operator as string) || 'operator',
                role: (data.role as string) || 'operator',
                detail: { policy, diff },
              }].slice(-120),
            },
            eventLog: addLog(
              state.eventLog,
              null,
              `HITL 정책 업데이트 (${(data.role as string) || 'operator'}) — ${diffKeys.length}개 변경`,
            ),
          };
        }

        case 'hitl_policy_update_denied': {
          return {
            ...state,
            eventLog: addLog(state.eventLog, null, 'HITL 정책 업데이트 거절: supervisor 권한 필요'),
          };
        }

        case 'verify_done': {
          const vm = data.metrics as Metrics | undefined;
          const predictive = (data.predictive as Record<string, unknown>[]) || state.phase4?.latest_predictive || [];
          if (vm) {
            return { ...state,
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
          }
          return { ...state, healingPhase: 'verify' as HealingPhase };
        }

        case 'orchestrator_trace': {
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
        }

        case 'learn_done_healing': {
          const incidents = (data.incidents_recorded as number) || 0;
          const autoRecovered = (data.auto_recovered_count as number) || 0;
          const l3Links = (data.l3_links_created as number) || 0;
          const recent = ((data.recent_incidents as Record<string, unknown>[]) || []).map(normalizeIncident);
          return { ...state,
            healingPhase: 'learn_healing' as HealingPhase,
            healing: {
              ...state.healing,
              iteration: state.healing.iteration + 1,
              incidents: state.healing.incidents + incidents,
              autoRecovered: state.healing.autoRecovered + autoRecovered,
              recentIncidents: recent.length > 0 ? recent : state.healing.recentIncidents,
            },
            l3Snapshot: (data.l3_snapshot as Record<string, unknown>) || state.l3Snapshot,
            eventLog: addLog(
              state.eventLog,
              null,
              `학습 완료 — ${incidents}건 이력, L3 링크 ${l3Links}건`,
            ),
          };
        }

        case 'causal_calibrated': {
          return {
            ...state,
            eventLog: addLog(
              state.eventLog,
              null,
              `인과 보정 완료 — chains ${(data.scanned_chains as number) || 0}, rules ${(data.updated_rules as number) || 0}`,
            ),
          };
        }

        case 'healing_loop_finished':
          return { ...state,
            healing: {
              ...state.healing,
              iteration: (data.total_iterations as number) || state.healing.iteration,
              running: false,
              incidents: (data.total_incidents as number) || state.healing.incidents,
              autoRecovered: (data.auto_recovered as number) || state.healing.autoRecovered,
            },
            healingPhase: null,
            eventLog: addLog(state.eventLog, null,
              `자율 복구 완료 — ${data.total_incidents}건 중 ${data.auto_recovered}건 자동 복구`),
          };

        case 'healing_error':
          return { ...state,
            eventLog: addLog(state.eventLog, null, `복구 오류: ${data.error}`),
          };

        case 'incident_analysis':
          return { ...state,
            latestAnalysis: data as unknown as IncidentAnalysis,
            eventLog: addLog(state.eventLog, null, `LLM 분석 완료: ${(data.summary as string)?.slice(0, 40)}...`),
          };

        case 'correlation_found':
          return { ...state,
            correlations: (data.correlations as EngineState['correlations']) || state.correlations,
            eventLog: addLog(state.eventLog, null, `상관분석: ${data.total_found}개 발견, ${data.stored_new}개 저장`),
          };

        case 'phase_ontology':
        case 'phase_healing':
          return { ...state,
            eventLog: addLog(state.eventLog, null, data.message as string),
          };

        default:
          return state;
      }
    }
    default:
      return state;
  }
}

export function useHarnessEngine() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(wsUrl('/ws'));
    wsRef.current = ws;

    ws.onopen = () => dispatch({ type: 'SET_CONNECTED' });

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        dispatch({ type: 'WS_EVENT', event: msg.event, data: msg.data || {} });
      } catch { /* ignore parse errors */ }
    };

    ws.onclose = () => {
      dispatch({ type: 'SET_DISCONNECTED' });
      reconnectRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendCommand = useCallback((cmd: WSCommand) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  return { state, sendCommand };
}
