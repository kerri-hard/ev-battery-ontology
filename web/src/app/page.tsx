'use client';

import { useEffect, useRef, useState } from 'react';
import { EngineProvider, useEngine } from '@/context/EngineContext';
import Header from '@/components/layout/Header';
import Sidebar from '@/components/layout/Sidebar';
import OntologyGraph from '@/components/graph/OntologyGraph';
import IncidentAnalysis from '@/components/issues/IncidentAnalysis';
import PreverifyPanel from '@/components/preverify/PreverifyPanel';
import AutonomyHero from '@/components/autonomy/AutonomyHero';
import RecurrencePanel from '@/components/autonomy/RecurrencePanel';
import SparklineChart from '@/components/charts/SparklineChart';
import Badge from '@/components/common/Badge';
import { apiUrl } from '@/lib/api';

type PhaseKpiRules = {
  phase1: { min_nodes: number; min_edges: number; min_completeness_score: number };
  phase2: { min_healing_iterations: number; min_incidents: number; min_recovery_rate: number };
  phase3: { min_causal_rules: number; min_causes: number; min_matched_by: number; min_chain_uses: number; min_has_pattern: number };
  phase4: { min_llm_orchestrator: number; min_nl_diagnoser: number; min_realtime_sensor_bridge: number };
  phase5: { min_resilience_orchestrator: number; min_strategy_evolution: number; min_multi_factory_federation: number };
};

const DEFAULT_KPI_RULES: PhaseKpiRules = {
  phase1: { min_nodes: 70, min_edges: 180, min_completeness_score: 75 },
  phase2: { min_healing_iterations: 3, min_incidents: 3, min_recovery_rate: 0.7 },
  phase3: { min_causal_rules: 5, min_causes: 5, min_matched_by: 1, min_chain_uses: 1, min_has_pattern: 1 },
  phase4: { min_llm_orchestrator: 1, min_nl_diagnoser: 1, min_realtime_sensor_bridge: 1 },
  phase5: { min_resilience_orchestrator: 1, min_strategy_evolution: 1, min_multi_factory_federation: 1 },
};

/* ── Compact Event Log ── */
function EventLog() {
  const { state } = useEngine();
  const listRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;

    // 사용자가 로그 하단을 보고 있을 때만 자동 스크롤한다.
    if (stickToBottomRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [state.eventLog.length]);

  const handleLogScroll = () => {
    const el = listRef.current;
    if (!el) return;
    const threshold = 24; // px
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottomRef.current = distFromBottom <= threshold;
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/5">
        <span className="text-[10px] font-bold text-white/30 uppercase tracking-wider">이벤트 로그</span>
        <span className="text-[9px] font-mono text-white/20">{state.eventLog.length}</span>
      </div>
      <div
        ref={listRef}
        onScroll={handleLogScroll}
        className="flex-1 overflow-y-auto px-3 py-1 space-y-0.5 min-h-0"
      >
        {state.eventLog.slice(-60).map((entry, i) => (
          <div key={i} className="flex items-start gap-1.5 text-[10px] leading-relaxed animate-fade-in">
            <span className="font-mono text-white/20 whitespace-nowrap">{entry.ts}</span>
            {entry.phase && <Badge phase={entry.phase} />}
            <span className="text-white/50 truncate">{entry.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Metric Mini Card ── */
function MiniMetric({ label, value, delta, sparkData, color }: {
  label: string; value: string; delta: number | null; sparkData: number[]; color: string;
}) {
  return (
    <div className="glass p-2.5 flex flex-col justify-between">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9px] text-white/30 uppercase tracking-wider">{label}</span>
        {delta !== null && delta !== 0 && (
          <span className={`text-[9px] font-mono ${delta > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {delta > 0 ? '▲' : '▼'}{Math.abs(delta).toFixed(1)}
          </span>
        )}
      </div>
      <div className="text-lg font-bold font-mono text-white/90">{value}</div>
      <div className="mt-1">
        <SparklineChart data={sparkData} color={color} width={120} height={20} />
      </div>
    </div>
  );
}

function ResearchProgressPanel() {
  const { state } = useEngine();
  const [rules, setRules] = useState<PhaseKpiRules>(DEFAULT_KPI_RULES);
  const [rulesSource, setRulesSource] = useState<'default' | 'config'>('default');

  useEffect(() => {
    let mounted = true;
    const loadRules = async () => {
      try {
        const resp = await fetch('/phase_kpi_rules.json');
        if (!resp.ok) return;
        const data = await resp.json();
        if (mounted) {
          setRules({
            phase1: { ...DEFAULT_KPI_RULES.phase1, ...(data.phase1 || {}) },
            phase2: { ...DEFAULT_KPI_RULES.phase2, ...(data.phase2 || {}) },
            phase3: { ...DEFAULT_KPI_RULES.phase3, ...(data.phase3 || {}) },
            phase4: { ...DEFAULT_KPI_RULES.phase4, ...(data.phase4 || {}) },
            phase5: { ...DEFAULT_KPI_RULES.phase5, ...(data.phase5 || {}) },
          });
          setRulesSource('config');
        }
      } catch {
        // default rules fallback
      }
    };
    loadRules();
    return () => {
      mounted = false;
    };
  }, []);
  const yieldDelta = state.metrics && state.initialMetrics
    ? (state.metrics.line_yield - state.initialMetrics.line_yield) * 100
    : 0;
  const scoreDelta = state.metrics && state.initialMetrics
    ? state.metrics.completeness_score - state.initialMetrics.completeness_score
    : 0;
  const l3Counts = (state.l3Snapshot?.counts as Record<string, number> | undefined) || {};
  const hasL3 = (l3Counts.causal_rules || 0) > 0 && (l3Counts.causes || 0) > 0;
  const hasLearningLoop = state.healing.incidents > 0;
  const phase4Runtime = state.phase4 || { predictive_agent: false, nl_diagnoser: false, llm_orchestrator: false, latest_predictive: [] };
  const recoveryRate = state.healing.incidents > 0
    ? state.healing.autoRecovered / state.healing.incidents
    : 0;

  const phaseChecks = [
    {
      label: 'Phase 1 온톨로지/토론',
      color: '#22d3ee',
      checks: [
        Boolean(state.metrics && state.metrics.total_nodes >= rules.phase1.min_nodes),
        Boolean(state.metrics && state.metrics.total_edges >= rules.phase1.min_edges),
        Boolean(state.metrics && state.metrics.completeness_score >= rules.phase1.min_completeness_score),
      ],
    },
    {
      label: 'Phase 2 자율복구',
      color: '#34d399',
      checks: [
        state.healing.iteration >= rules.phase2.min_healing_iterations,
        state.healing.incidents >= rules.phase2.min_incidents,
        recoveryRate >= rules.phase2.min_recovery_rate,
      ],
    },
    {
      label: 'Phase 3 인과추론',
      color: '#a78bfa',
      checks: [
        (l3Counts.causal_rules || 0) >= rules.phase3.min_causal_rules,
        (l3Counts.causes || 0) >= rules.phase3.min_causes,
        (l3Counts.matched_by || 0) >= rules.phase3.min_matched_by,
        (l3Counts.chain_uses || 0) >= rules.phase3.min_chain_uses,
        (l3Counts.has_pattern || 0) >= rules.phase3.min_has_pattern,
      ],
    },
    {
      label: 'Phase 4 LLM 통합',
      color: '#f59e0b',
      checks: [
        (phase4Runtime.llm_orchestrator ? 1 : 0) >= rules.phase4.min_llm_orchestrator,
        (phase4Runtime.nl_diagnoser ? 1 : 0) >= rules.phase4.min_nl_diagnoser,
        ((phase4Runtime.latest_predictive?.length || 0) > 0 ? 1 : 0) >= rules.phase4.min_realtime_sensor_bridge,
      ],
    },
    {
      label: 'Phase 5 다크팩토리',
      color: '#ef4444',
      checks: [
        0 >= rules.phase5.min_resilience_orchestrator, // 미연동(현재 0)
        0 >= rules.phase5.min_strategy_evolution, // 미연동(현재 0)
        0 >= rules.phase5.min_multi_factory_federation, // 미연동(현재 0)
      ],
    },
  ];

  const roadmap = phaseChecks.map((p) => {
    const done = p.checks.filter(Boolean).length;
    const total = p.checks.length;
    return {
      label: p.label,
      color: p.color,
      value: Math.round((done / total) * 100),
      done,
      total,
    };
  });

  const rows = [
    { name: 'KG + DT 통합 (Sensors 2024)', done: Boolean(state.metrics?.total_nodes && state.metrics.total_nodes > 0), detail: `노드 ${state.metrics?.total_nodes ?? 0}` },
    { name: 'KG 기반 Fault Diagnosis (Sensors 2025)', done: hasL3, detail: `CausalRule ${l3Counts.causal_rules ?? 0}, CAUSES ${l3Counts.causes ?? 0}` },
    { name: 'FailureChain 학습 루프', done: hasLearningLoop, detail: `Incident ${state.healing.incidents}, Auto ${state.healing.autoRecovered}` },
    { name: '성과 개선 지표', done: state.metrics !== null && state.initialMetrics !== null, detail: `수율 Δ${yieldDelta.toFixed(2)}%p / 완성도 Δ${scoreDelta.toFixed(1)}` },
  ];

  return (
    <div className="glass p-2.5">
      <div className="text-[10px] font-bold text-white/70 uppercase tracking-wider mb-1.5">논문 기반 진행현황</div>
      <div className="space-y-1.5 max-h-[170px] overflow-y-auto pr-1">
        {rows.map((r) => (
          <div key={r.name} className="flex items-start gap-2 text-[10px]">
            <span className={r.done ? 'text-emerald-400' : 'text-yellow-400'}>{r.done ? '✓' : '…'}</span>
            <div className="min-w-0">
              <div className="text-white/85 truncate">{r.name}</div>
              <div className="text-white/45 font-mono">{r.detail}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 pt-1.5 border-t border-white/10">
        <div className="text-[9px] text-white/60 mb-1">VISION 로드맵 달성률</div>
        <div className="space-y-1.5 max-h-[120px] overflow-y-auto pr-1">
          {roadmap.map((r) => (
            <div key={r.label}>
              <div className="flex items-center justify-between text-[9px] mb-0.5">
                <span className="text-white/65">{r.label}</span>
                <span className="font-mono" style={{ color: r.color }}>{r.value}% ({r.done}/{r.total})</span>
              </div>
              <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${r.value}%`, background: r.color }} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-2 pt-1.5 border-t border-white/10 text-[9px] text-white/40 leading-relaxed">
        규칙: <span className={rulesSource === 'config' ? 'text-emerald-300' : 'text-yellow-300'}>
          {rulesSource === 'config' ? 'phase_kpi_rules.json' : 'default'}
        </span><br />
        근거: <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC11054090/" target="_blank" rel="noreferrer" className="text-cyan-300">Sensors 2024</a>,
        {' '}<a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC12252116/" target="_blank" rel="noreferrer" className="text-cyan-300">Sensors 2025</a>
      </div>
    </div>
  );
}

function RecoveryCasePanel() {
  const { state } = useEngine();
  const cases = [...state.healing.recentIncidents].slice(-3).reverse();

  return (
    <div className="glass p-2.5">
      <div className="text-[10px] font-bold text-white/70 uppercase tracking-wider mb-1.5">복구 사례 분석</div>
      {cases.length === 0 ? (
        <div className="text-[10px] text-white/40">사례 데이터가 없습니다.</div>
      ) : (
        <div className="space-y-1.5 max-h-[150px] overflow-y-auto pr-1">
          {cases.map((c) => {
            const pre = typeof c.pre_yield === 'number' ? c.pre_yield : undefined;
            const post = typeof c.post_yield === 'number' ? c.post_yield : undefined;
            const delta = pre !== undefined && post !== undefined ? post - pre : undefined;
            return (
              <div key={c.id || `${c.step_id}-${c.timestamp}`} className="rounded border border-white/10 px-2 py-1.5">
                <div className="flex items-center justify-between text-[9px] mb-0.5">
                  <span className="text-white/70 font-mono">{c.step_id}</span>
                  <span className={c.auto_recovered ? 'text-emerald-300' : 'text-red-300'}>
                    {c.auto_recovered ? 'AUTO' : 'MANUAL'}
                  </span>
                </div>
                <div className="text-[10px] text-white/80 truncate">
                  이슈: {c.anomaly_type || 'unknown'} / 원인: {c.top_cause || c.cause || 'unknown'}
                </div>
                <div className="text-[10px] text-white/65">
                  조치: {c.action_type || c.action || 'unknown'} / 결과: {c.improved ? '개선' : '유지/악화'}
                </div>
                {delta !== undefined && (
                  <div className={`text-[10px] font-mono ${delta >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                    Δyield: {delta >= 0 ? '+' : ''}{delta.toFixed(4)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function PredictiveRiskPanel() {
  const { state } = useEngine();
  const items = (state.phase4?.latest_predictive || []) as Array<Record<string, unknown>>;
  const llmOn = Boolean(state.phase4?.llm_orchestrator);
  const model = state.phase4?.model || 'none';

  return (
    <div className="glass p-2.5">
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-[10px] font-bold text-white/70 uppercase tracking-wider">Predictive RUL</div>
        <div className={`text-[9px] px-1.5 py-0.5 rounded ${llmOn ? 'bg-emerald-500/20 text-emerald-300' : 'bg-white/10 text-white/50'}`}>
          LLM {llmOn ? `ON (${model})` : 'OFF'}
        </div>
      </div>
      {items.length === 0 ? (
        <div className="text-[10px] text-white/40">예측 데이터 없음 (검증 단계 실행 필요)</div>
      ) : (
        <div className="space-y-1.5 max-h-[130px] overflow-y-auto pr-1">
          {items.slice(0, 4).map((it, idx) => (
            <div key={`${it.step_id || 'step'}-${idx}`} className="rounded border border-white/10 px-2 py-1.5 text-[10px]">
              <div className="flex items-center justify-between">
                <span className="font-mono text-white/75">{String(it.step_id || '-')}</span>
                <span className="text-amber-300">{String(it.priority || '-')}</span>
              </div>
              <div className="text-white/65 truncate">{String(it.equipment_name || '-')}</div>
              <div className="font-mono text-cyan-300">RUL {Number(it.rul_hours || 0).toFixed(1)}h / risk {Number(it.risk_score || 0).toFixed(3)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function OrchestratorPanel() {
  const { state } = useEngine();
  const traces = (state.phase4?.orchestrator_traces || []) as Array<Record<string, unknown>>;
  const [replay, setReplay] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    let mounted = true;
    const loadReplay = async () => {
      try {
        const resp = await fetch(apiUrl('/api/replay-eval'));
        if (!resp.ok) return;
        const data = await resp.json();
        if (mounted) {
          setReplay(((data.variants as Array<Record<string, unknown>>) || []).slice(0, 4));
        }
      } catch {
        // ignore
      }
    };
    loadReplay();
    const t = setInterval(loadReplay, 10000);
    return () => {
      mounted = false;
      clearInterval(t);
    };
  }, []);

  return (
    <div className="glass p-2.5">
      <div className="text-[10px] font-bold text-white/70 uppercase tracking-wider mb-1.5">Orchestrator</div>
      <div className="text-[9px] text-white/45 mb-1">Intent Trace</div>
      <div className="space-y-1 max-h-[90px] overflow-y-auto pr-1 mb-2">
        {traces.length === 0 ? (
          <div className="text-[10px] text-white/40">trace 없음</div>
        ) : (
          [...traces].slice(-4).reverse().map((t, i) => (
            <div key={`trace-${i}`} className="rounded border border-white/10 px-2 py-1 text-[10px]">
              <span className="text-cyan-300">{String(t.intent || '-')}</span>
              <span className="text-white/55">{' -> '}</span>
              <span className="text-violet-300">{String(t.delegated_to || '-')}</span>
            </div>
          ))
        )}
      </div>
      <div className="text-[9px] text-white/45 mb-1">Replay Eval (Top)</div>
      <div className="space-y-1 max-h-[90px] overflow-y-auto pr-1">
        {replay.length === 0 ? (
          <div className="text-[10px] text-white/40">replay 데이터 없음</div>
        ) : (
          replay.map((r, i) => (
            <div key={`replay-${i}`} className="rounded border border-white/10 px-2 py-1 text-[10px]">
              <div className="font-mono text-white/70">
                conf {Number(r.min_confidence || 0).toFixed(2)} / risk {Number(r.high_risk_threshold || 0).toFixed(2)}
              </div>
              <div className="text-emerald-300">auto {Number((Number(r.auto_rate || 0) * 100)).toFixed(0)}%</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ── Dashboard Content ── */
function Dashboard() {
  const { state } = useEngine();
  const { metrics, prevMetrics, metricsHistory } = state;

  return (
    <div className="min-h-screen flex flex-col bg-[#06060e]">
      <Header />

      <div className="flex flex-1 overflow-auto pt-14 min-h-0">
        <Sidebar />

        {/* Main area */}
        <main className="flex-1 flex flex-col gap-2 p-2 overflow-auto min-h-0">

          {/* Top: Ontology Graph — takes majority of space */}
          <div className="flex-[5] min-h-[520px]">
            <OntologyGraph className="h-full" />
          </div>

          {/* Bottom: 3-column info bar */}
          <div className="flex-[2] min-h-[320px] grid grid-cols-12 gap-2 overflow-auto">

            {/* Metrics (4 mini cards in 2x2) + panels */}
            <div className="col-span-3 flex flex-col gap-1.5">
              <div className="grid grid-cols-2 gap-1.5">
              <MiniMetric label="노드" value={metrics ? String(metrics.total_nodes) : '--'}
                delta={metrics && prevMetrics ? metrics.total_nodes - prevMetrics.total_nodes : null}
                sparkData={metricsHistory.nodes} color="#00d2ff" />
              <MiniMetric label="엣지" value={metrics ? String(metrics.total_edges) : '--'}
                delta={metrics && prevMetrics ? metrics.total_edges - prevMetrics.total_edges : null}
                sparkData={metricsHistory.edges} color="#8b5cf6" />
              <MiniMetric label="수율" value={metrics ? `${(metrics.line_yield * 100).toFixed(1)}%` : '--'}
                delta={metrics && prevMetrics ? (metrics.line_yield - prevMetrics.line_yield) * 100 : null}
                sparkData={metricsHistory.yield} color="#10b981" />
              <MiniMetric label="완성도" value={metrics ? metrics.completeness_score.toFixed(1) : '--'}
                delta={metrics && prevMetrics ? metrics.completeness_score - prevMetrics.completeness_score : null}
                sparkData={metricsHistory.completeness} color="#f59e0b" />
              </div>
              <AutonomyHero />
              <ResearchProgressPanel />
              <PreverifyPanel />
              <RecurrencePanel />
              <PredictiveRiskPanel />
              <OrchestratorPanel />
              <RecoveryCasePanel />
            </div>

            {/* Incident Analysis (main focus) */}
            <div className="col-span-4 glass overflow-hidden">
              <IncidentAnalysis />
            </div>

            {/* Event Log */}
            <div className="col-span-5 glass overflow-hidden">
              <EventLog />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <EngineProvider>
      <Dashboard />
    </EngineProvider>
  );
}
