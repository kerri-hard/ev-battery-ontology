'use client';

import React, { useMemo, useState } from 'react';
import { useEngine } from '@/context/EngineContext';
import { severityToColor } from '@/components/common/severityColors';
import { EmptyState } from '@/components/common/StateMessages';
import type { HealingIncident } from '@/types';

/* ── Agent display config ── */
const AGENT_META: Record<string, { label: string; color: string; icon: string }> = {
  AnomalyDetector:    { label: 'AnomalyDetector',    color: 'var(--color-danger)', icon: '\u2460' },
  RootCauseAnalyzer:  { label: 'RootCauseAnalyzer',  color: 'var(--color-warning)', icon: '\u2461' },
  CausalReasoner:     { label: 'CausalReasoner',     color: 'var(--color-meta)', icon: '\u2462' },
  CorrelationAnalyzer:{ label: 'CorrelationAnalyzer', color: 'var(--color-info)', icon: '\u2463' },
  CrossInvestigator:  { label: 'CrossInvestigator',   color: 'var(--color-success)', icon: '\u2464' },
  AutoRecovery:       { label: 'AutoRecovery',        color: 'var(--color-success)', icon: '\u2465' },
};

/** 외부 통합 함수에 위임 — severity → CSS 변수 색상 (semantic 토큰) */
function severityColor(severity: string | undefined): string {
  return severityToColor(severity?.toUpperCase());
}

/* ── Collapsible section ── */
function Section({ title, defaultOpen = true, children }: {
  title: string; defaultOpen?: boolean; children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 text-left text-[10px] font-bold text-white/60 uppercase tracking-wider mb-1 hover:text-white/80 transition-colors"
      >
        <span className="text-[9px]">{open ? '\u25BC' : '\u25B6'}</span>
        {title}
      </button>
      {open && children}
    </div>
  );
}

/* ── Causal chain visualisation ── */
function CausalChainFlow({ chain }: { chain: string }) {
  const parts = chain.split(/\s*(?:->|→|──→)\s*/);
  if (parts.length === 0) return null;

  return (
    <div className="flex items-center gap-1 overflow-x-auto py-1">
      {parts.map((part, i) => {
        // Try to extract a percentage from the part e.g. "마모 (85%)"
        const match = part.match(/^(.+?)\s*\((\d+)%?\)$/);
        const label = match ? match[1].trim() : part.trim();
        const pct = match ? match[2] : null;

        return (
          <React.Fragment key={i}>
            <div className="flex-shrink-0 rounded border border-violet-400/30 bg-violet-500/10 px-2 py-1 text-[10px] text-violet-200 text-center">
              <div>{label}</div>
              {pct && <div className="text-[9px] text-violet-300/80 font-mono">{pct}%</div>}
            </div>
            {i < parts.length - 1 && (
              <span className="text-white/30 text-[10px] flex-shrink-0">&rarr;</span>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

/* ── Correlation bar ── */
function CorrelationBar({ source, target, coefficient, direction }: {
  source: string; target: string; coefficient: number; direction: string;
}) {
  const pct = Math.min(Math.abs(coefficient) * 100, 100);
  const dirLabel = direction === 'upstream' ? '\uC0C1\uB958' : direction === 'downstream' ? '\uD558\uB958' : '\uC228\uACA8\uC9C4';
  return (
    <div className="mb-1.5">
      <div className="flex items-center justify-between text-[10px] mb-0.5">
        <span className="text-white/70">
          <span className="font-mono text-cyan-300">{source}</span>
          <span className="text-white/30 mx-1">&larr; r={coefficient.toFixed(2)} &rarr;</span>
          <span className="font-mono text-cyan-300">{target}</span>
        </span>
        <span className="text-[9px] text-white/40">{dirLabel}</span>
      </div>
      <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #00d2ff, #8b5cf6)' }}
        />
      </div>
    </div>
  );
}

/* ── Agent step finding summary ── */
function agentFinding(incident: HealingIncident, agentName: string): { text: string; status: 'found' | 'uncertain' | 'none' } {
  switch (agentName) {
    case 'AnomalyDetector':
      if (incident.anomaly_type) return { text: `${incident.anomaly_type} (\uBC94\uC704 \uCD08\uACFC)`, status: 'found' };
      return { text: '\uC774\uC0C1 \uBBF8\uAC10\uC9C0', status: 'none' };
    case 'RootCauseAnalyzer':
      if (incident.top_cause) {
        const conf = incident.confidence !== undefined ? ` (${(incident.confidence * 100).toFixed(0)}%)` : '';
        return { text: `${incident.top_cause}${conf}`, status: 'found' };
      }
      return { text: '\uBBF8\uD655\uC778', status: 'uncertain' };
    case 'CausalReasoner':
      if (incident.causal_chain) return { text: incident.causal_chain, status: 'found' };
      return { text: '\uCCB4\uC778 \uBBF8\uBC1C\uACAC', status: 'none' };
    case 'CorrelationAnalyzer':
      if (incident.history_matched) return { text: `\uC774\uB825 \uB9E4\uCE6D (${incident.matched_chain_id || '-'})`, status: 'found' };
      return { text: '\uC0C1\uAD00\uAD00\uACC4 \uD0D0\uC0C9 \uC911', status: 'uncertain' };
    case 'CrossInvestigator':
      if (incident.analysis_method) return { text: `${incident.analysis_method} \uBD84\uC11D`, status: 'found' };
      return { text: '\uAD50\uCC28 \uBD84\uC11D \uBBF8\uC2E4\uD589', status: 'none' };
    case 'AutoRecovery':
      if (incident.auto_recovered) {
        const delta = incident.pre_yield !== undefined && incident.post_yield !== undefined
          ? ` (\u0394${((incident.post_yield - incident.pre_yield) * 100).toFixed(2)}%p)`
          : '';
        return { text: `${incident.action_type || incident.action || '\uBCF5\uAD6C'} \uC131\uACF5${delta}`, status: 'found' };
      }
      return { text: '\uC790\uB3D9 \uBCF5\uAD6C \uC2E4\uD328', status: 'uncertain' };
    default:
      return { text: '-', status: 'none' };
  }
}

function statusColor(status: 'found' | 'uncertain' | 'none'): string {
  switch (status) {
    case 'found':     return 'text-emerald-300';
    case 'uncertain': return 'text-yellow-300';
    case 'none':      return 'text-white/30';
  }
}

/* ── Step name lookup helper ── */
function useStepName() {
  const { state } = useEngine();
  const map = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of state.steps) m.set(s.id, s.name);
    return m;
  }, [state.steps]);
  return (id: string) => map.get(id) || id;
}

/* ── Main Component ── */
function IncidentAnalysis() {
  const { state } = useEngine();
  const { healing, latestAnalysis, correlations } = state;
  const stepName = useStepName();

  const incident: HealingIncident | null = useMemo(() => {
    if (healing.recentIncidents.length === 0) return null;
    return healing.recentIncidents[healing.recentIncidents.length - 1];
  }, [healing.recentIncidents]);

  const relevantCorrelations = useMemo(() => {
    if (!incident || correlations.length === 0) return [];
    return correlations.filter(
      (c) => c.source === incident.step_id || c.target === incident.step_id,
    );
  }, [correlations, incident]);

  /* ── Empty state ── */
  if (!incident) {
    return (
      <div className="flex flex-col h-full items-center justify-center">
        <EmptyState
          icon="📋"
          title="장애 분석 리포트 대기 중"
          hint="시뮬레이션이 시작되면 6개 에이전트의 진단·복구·학습 리포트가 표시됩니다"
        />
      </div>
    );
  }

  const severity = incident.severity || incident.risk_level || 'MEDIUM';
  const sevCol = severityColor(severity);

  return (
    <div className="flex flex-col h-full overflow-y-auto px-3 py-2 space-y-2">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-bold text-white/90">장애 분석 리포트</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] text-white/70">{incident.step_id}</span>
          <span
            className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
            style={{ color: sevCol, background: `${sevCol}22`, border: `1px solid ${sevCol}44` }}
          >
            {severity}
          </span>
        </div>
      </div>

      {incident.step_id && (
        <div className="text-[10px] text-white/50">
          {stepName(incident.step_id)}
          {incident.timestamp && <span className="ml-2 font-mono text-white/30">{incident.timestamp}</span>}
        </div>
      )}

      {/* ── 1. LLM Summary ── */}
      <Section title="LLM 요약" defaultOpen={true}>
        <div
          className="rounded-lg px-3 py-2"
          style={{ background: 'rgba(0, 210, 255, 0.06)', border: '1px solid rgba(0, 210, 255, 0.25)' }}
        >
          {latestAnalysis ? (
            <>
              <div className="text-[11px] text-white/85 leading-relaxed whitespace-pre-wrap">
                {latestAnalysis.summary}
              </div>
              {latestAnalysis.root_cause_explanation && (
                <div className="mt-1.5 text-[10px] text-white/60 leading-relaxed">
                  {latestAnalysis.root_cause_explanation}
                </div>
              )}
              <div className="mt-2 flex items-center gap-2 text-[9px] text-white/30">
                <span className="font-mono">{latestAnalysis.model || 'unknown'}</span>
                <span>{latestAnalysis.tokens_used?.toLocaleString() || '?'} tokens</span>
              </div>
            </>
          ) : (
            <div className="text-[10px] text-cyan-300/60 animate-pulse">LLM 분석 대기 중...</div>
          )}
        </div>
      </Section>

      {/* ── 2. Agent Analysis Pipeline ── */}
      <Section title="에이전트 분석 과정" defaultOpen={true}>
        <div className="space-y-1">
          {Object.entries(AGENT_META).map(([key, meta]) => {
            const finding = agentFinding(incident, key);
            return (
              <div
                key={key}
                className="flex items-start gap-2 rounded px-2 py-1.5"
                style={{ background: `${meta.color}08`, borderLeft: `2px solid ${meta.color}66` }}
              >
                <span className="text-[10px] flex-shrink-0" style={{ color: meta.color }}>{meta.icon}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-[10px] font-mono" style={{ color: meta.color }}>{meta.label}</div>
                  <div className={`text-[10px] truncate ${statusColor(finding.status)}`}>
                    {finding.text}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ── 3. Causal Chain ── */}
      {incident.causal_chain && (
        <Section title="인과관계 체인" defaultOpen={true}>
          <CausalChainFlow chain={incident.causal_chain} />
        </Section>
      )}

      {/* ── 4. Cross-Process Correlations ── */}
      <Section title="공정 간 상관관계" defaultOpen={true}>
        {relevantCorrelations.length > 0 ? (
          <div className="space-y-1">
            {relevantCorrelations.map((c, i) => (
              <CorrelationBar
                key={`corr-${i}`}
                source={`${c.source}(${stepName(c.source)})`}
                target={`${c.target}(${stepName(c.target)})`}
                coefficient={c.coefficient}
                direction={c.direction}
              />
            ))}
            {latestAnalysis?.cross_process_insight && (
              <div className="text-[10px] text-white/50 mt-1 italic leading-relaxed">
                &ldquo;{latestAnalysis.cross_process_insight}&rdquo;
              </div>
            )}
          </div>
        ) : (
          <div className="text-[10px] text-white/30">상관관계 데이터 없음</div>
        )}
      </Section>

      {/* ── 5. Recovery Result ── */}
      <Section title="복구 결과" defaultOpen={true}>
        <div
          className="rounded-lg px-3 py-2"
          style={{
            background: incident.auto_recovered ? 'rgba(16, 185, 129, 0.06)' : 'rgba(239, 68, 68, 0.06)',
            border: incident.auto_recovered
              ? '1px solid rgba(16, 185, 129, 0.25)'
              : '1px solid rgba(239, 68, 68, 0.25)',
          }}
        >
          <div className="flex items-center gap-2 text-[11px]">
            <span className={incident.auto_recovered ? 'text-emerald-300' : 'text-red-300'}>
              {incident.auto_recovered ? '\u2713' : '\u2717'}
            </span>
            <span className="text-white/80">
              {incident.action_type || incident.action || 'unknown'}
              {' '}
              {incident.auto_recovered ? '\uC131\uACF5' : '\uC2E4\uD328'}
            </span>
          </div>
          {incident.pre_yield !== undefined && incident.post_yield !== undefined && (
            <div className="mt-1 text-[10px] font-mono text-white/70">
              수율: {(incident.pre_yield * 100).toFixed(1)}%
              <span className="text-white/30 mx-1">&rarr;</span>
              {(incident.post_yield * 100).toFixed(1)}%
              {(() => {
                const delta = (incident.post_yield! - incident.pre_yield!) * 100;
                return (
                  <span className={`ml-1.5 ${delta >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                    ({delta >= 0 ? '+' : ''}{delta.toFixed(1)}%p)
                  </span>
                );
              })()}
            </div>
          )}
          {incident.playbook_id && (
            <div className="mt-1 text-[9px] text-white/40 font-mono">
              playbook: {incident.playbook_id} / {incident.playbook_source || '-'}
            </div>
          )}
        </div>
      </Section>

      {/* ── 6. Recommended Actions ── */}
      {latestAnalysis?.recommended_actions && latestAnalysis.recommended_actions.length > 0 && (
        <Section title="권고 사항" defaultOpen={true}>
          <div className="space-y-1">
            {latestAnalysis.recommended_actions.map((action, i) => {
              // Detect urgency markers like (즉시), (24시간 내), etc.
              const isUrgent = /즉시|긴급|immediate/i.test(action);
              const isSoon = /24시간|48시간|soon/i.test(action);
              const urgencyColor = isUrgent ? 'text-red-300' : isSoon ? 'text-amber-300' : 'text-white/60';
              const urgencyDot = isUrgent ? '#ef4444' : isSoon ? '#f59e0b' : '#6b7280';

              return (
                <div
                  key={i}
                  className="flex items-start gap-2 rounded px-2 py-1.5 bg-white/[0.03] border border-white/10"
                >
                  <div className="flex-shrink-0 mt-0.5">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: urgencyDot }} />
                  </div>
                  <div className="min-w-0">
                    <span className={`text-[10px] font-mono mr-1 ${urgencyColor}`}>{i + 1}.</span>
                    <span className="text-[10px] text-white/75">{action}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* ── Risk Assessment (from LLM) ── */}
      {latestAnalysis?.risk_assessment && (
        <Section title="리스크 평가" defaultOpen={false}>
          <div className="text-[10px] text-white/60 leading-relaxed px-2">
            {latestAnalysis.risk_assessment}
          </div>
        </Section>
      )}

      {/* ── Confidence Breakdown ── */}
      {latestAnalysis?.confidence_breakdown && Object.keys(latestAnalysis.confidence_breakdown).length > 0 && (
        <Section title="신뢰도 분석" defaultOpen={false}>
          <div className="space-y-0.5 px-2">
            {Object.entries(latestAnalysis.confidence_breakdown).map(([key, val]) => (
              <div key={key} className="flex items-center justify-between text-[10px]">
                <span className="text-white/50">{key}</span>
                <span className="font-mono text-white/70">{val}</span>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

export default React.memo(IncidentAnalysis);
