'use client';

import { useState } from 'react';
import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import { EmptyState } from '@/components/common/StateMessages';
import {
  severityToPill,
  severityShort,
  phaseStatusToColor,
} from '@/components/common/severityColors';
import type { HealingIncident, RecurrenceSignature } from '@/types';

/** 7-페이즈 자율 복구 루프 */
const PHASES = [
  { key: 'detect', label: 'DETECT', desc: '이상 감지' },
  { key: 'diagnose', label: 'DIAGNOSE', desc: '원인 진단' },
  { key: 'preverify', label: 'PRE-VERIFY', desc: '시뮬 게이트' },
  { key: 'recover', label: 'RECOVER', desc: '복구 실행' },
  { key: 'verify', label: 'VERIFY', desc: 'yield 검증' },
  { key: 'learn', label: 'LEARN', desc: '학습/영속화' },
] as const;

type PhaseStatus = 'pending' | 'success' | 'fail' | 'rejected';
type SeverityFilter = 'ALL' | 'CRITICAL_HIGH' | 'MEDIUM' | 'LOW';
type SortMode = 'recent' | 'severity';

const SEVERITY_RANK: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

/** 실시간 incident 라이프사이클 — severity 필터/정렬 + 반복 배지 + 토큰 적용 */
export default function IncidentFlowPanel() {
  const { state, selectIncident, navigateTo } = useEngine();
  const [sevFilter, setSevFilter] = useState<SeverityFilter>('ALL');
  const [sortMode, setSortMode] = useState<SortMode>('recent');

  const incidents = state.healing?.recentIncidents ?? [];
  const selectedStepId = state.selectedStepId;
  const recurrenceSigs = state.recurrence?.top_signatures ?? [];

  // 1. step 필터 (drill-down)
  let filtered = selectedStepId
    ? incidents.filter((i) => i.step_id === selectedStepId)
    : [...incidents];
  // 2. severity 필터
  filtered = filtered.filter((i) => matchSeverityFilter(i, sevFilter));
  // 3. 정렬
  filtered.sort((a, b) => {
    if (sortMode === 'severity') {
      const sa = SEVERITY_RANK[a.severity ?? ''] ?? 0;
      const sb = SEVERITY_RANK[b.severity ?? ''] ?? 0;
      if (sa !== sb) return sb - sa;
    }
    return (b.iteration ?? 0) - (a.iteration ?? 0);
  });
  const sorted = filtered.slice(0, 12);
  const selectedId = state.selectedIncidentId;

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
        <span className="ds-label">Incident Flow — 라이프사이클</span>
        <div className="flex items-center gap-1.5 flex-wrap">
          {/* Severity 필터 */}
          <FilterChip active={sevFilter === 'ALL'} onClick={() => setSevFilter('ALL')}>
            전체
          </FilterChip>
          <FilterChip
            active={sevFilter === 'CRITICAL_HIGH'}
            onClick={() => setSevFilter('CRITICAL_HIGH')}
            danger
          >
            🔴 H/C
          </FilterChip>
          <FilterChip active={sevFilter === 'MEDIUM'} onClick={() => setSevFilter('MEDIUM')}>
            ⚠ M
          </FilterChip>
          <FilterChip active={sevFilter === 'LOW'} onClick={() => setSevFilter('LOW')}>
            ● L
          </FilterChip>
          <span className="ds-caption">·</span>
          <FilterChip
            active={sortMode === 'severity'}
            onClick={() => setSortMode((m) => (m === 'severity' ? 'recent' : 'severity'))}
            title="severity 우선 정렬"
          >
            {sortMode === 'severity' ? '↓ severity' : '↓ recent'}
          </FilterChip>
          {selectedStepId && (
            <button
              onClick={() => navigateTo({ stepId: null })}
              className="text-[8px] px-1.5 py-0.5 rounded pill-info font-mono hover:opacity-90"
              title="필터 해제"
            >
              {selectedStepId} ✕
            </button>
          )}
        </div>
      </div>

      <div className="ds-caption mb-1.5">
        {sorted.length} / {incidents.length}건
      </div>

      {/* Phase 헤더 */}
      <div className="grid grid-cols-[120px_1fr_55px] gap-1.5 mb-1 px-1">
        <div></div>
        <div className="grid grid-cols-6 gap-0.5">
          {PHASES.map((p) => (
            <div key={p.key} className="text-center">
              <div className="text-[8px] text-white/50 font-mono">{p.label}</div>
              <div className="text-[7px] text-white/30">{p.desc}</div>
            </div>
          ))}
        </div>
        <div className="text-[8px] text-white/40 text-right">결과</div>
      </div>

      <div className="space-y-1 max-h-[380px] overflow-y-auto">
        {sorted.length === 0 ? (
          <EmptyState
            icon="📭"
            title={incidents.length === 0 ? '아직 incident 없음' : '필터 결과 없음'}
            hint={
              incidents.length === 0
                ? 'sim 시작 시 자동으로 채워집니다'
                : '필터를 변경하거나 ✕로 해제하세요'
            }
          />
        ) : (
          sorted.map((inc, idx) => (
            <IncidentRow
              key={inc.id}
              incident={inc}
              fresh={idx < 3}
              selected={inc.id === selectedId}
              recurCount={getRecurrenceCount(inc, recurrenceSigs)}
              onClick={() => selectIncident(inc.id === selectedId ? null : inc.id ?? null)}
            />
          ))
        )}
      </div>
    </GlassCard>
  );
}

function matchSeverityFilter(inc: HealingIncident, f: SeverityFilter): boolean {
  if (f === 'ALL') return true;
  const s = inc.severity ?? '';
  if (f === 'CRITICAL_HIGH') return s === 'CRITICAL' || s === 'HIGH';
  return s === f;
}

function getRecurrenceCount(inc: HealingIncident, sigs: RecurrenceSignature[]): number {
  const match = sigs.find(
    (s) =>
      s.step_id === inc.step_id &&
      s.anomaly_type === inc.anomaly_type &&
      s.cause_type === (inc.top_cause ?? ''),
  );
  return match?.count ?? 0;
}

function FilterChip({
  active,
  onClick,
  children,
  danger = false,
  title,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  danger?: boolean;
  title?: string;
}) {
  const baseCls = 'text-[8px] px-1.5 py-0.5 rounded font-mono transition border';
  const activeCls = danger
    ? 'pill-danger border-current'
    : 'pill-info border-current';
  const inactiveCls = 'bg-white/5 text-white/50 border-white/10 hover:bg-white/10';
  return (
    <button
      onClick={onClick}
      title={title}
      className={`${baseCls} ${active ? activeCls : inactiveCls}`}
    >
      {children}
    </button>
  );
}

function IncidentRow({
  incident,
  fresh,
  selected,
  recurCount,
  onClick,
}: {
  incident: HealingIncident;
  fresh: boolean;
  selected: boolean;
  recurCount: number;
  onClick: () => void;
}) {
  const phases = inferPhaseStatuses(incident);
  const time = parseTime(incident.timestamp);

  const borderClass = selected
    ? 'bg-cyan-500/15 border-l-2 border-cyan-300 ring-1 ring-cyan-400/40'
    : fresh
      ? 'bg-cyan-500/5 border-l-2 border-cyan-400/40'
      : 'border-l-2 border-white/5 hover:bg-white/5';

  return (
    <button
      onClick={onClick}
      className={`grid w-full text-left grid-cols-[120px_1fr_55px] gap-1.5 items-center px-1.5 py-1 rounded text-[9px] cursor-pointer transition ${borderClass}`}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-1">
          <span className="font-mono font-bold text-white/80">{incident.id}</span>
          <span className={`text-[7px] px-1 rounded font-mono ${severityToPill(incident.severity)}`}>
            {severityShort(incident.severity)}
          </span>
          {recurCount >= 2 && (
            <span
              className="text-[7px] px-1 rounded pill-warning font-mono"
              title={`동일 시그니처 ${recurCount}회 반복`}
            >
              ×{recurCount}
            </span>
          )}
        </div>
        <div className="text-[8px] text-white/40 font-mono truncate">
          {incident.step_id} · {time}
        </div>
        <div className="text-[8px] text-white/30 truncate">{incident.top_cause}</div>
      </div>

      <div className="grid grid-cols-6 gap-0.5">
        {PHASES.map((p, i) => (
          <PhaseDot key={p.key} status={phases[i]} label={p.label} />
        ))}
      </div>

      <div className="text-right">
        <ResultBadge incident={incident} />
      </div>
    </button>
  );
}

function PhaseDot({ status, label }: { status: PhaseStatus; label: string }) {
  const marks: Record<PhaseStatus, string> = {
    pending: '',
    success: '✓',
    fail: '✗',
    rejected: '!',
  };
  const bg = phaseStatusToColor(status);
  return (
    <div
      className="h-4 rounded flex items-center justify-center text-[8px] font-bold text-white/90"
      style={{ background: bg }}
      title={`${label}: ${status}`}
    >
      {marks[status]}
    </div>
  );
}

function ResultBadge({ incident }: { incident: HealingIncident }) {
  if (incident.hitl_required) {
    return <span className="text-[8px] px-1 py-0.5 rounded pill-warning font-mono">HITL</span>;
  }
  if (incident.action_type === 'ESCALATE') {
    return <span className="text-[8px] px-1 py-0.5 rounded pill-danger font-mono">ESCALATE</span>;
  }
  if (incident.auto_recovered && incident.improved) {
    return <span className="text-[8px] px-1 py-0.5 rounded pill-success font-mono">✓ 복구</span>;
  }
  if (incident.auto_recovered) {
    return <span className="text-[8px] px-1 py-0.5 rounded pill-info font-mono">실행</span>;
  }
  return <span className="text-[8px] px-1 py-0.5 rounded bg-white/10 text-white/50 font-mono">?</span>;
}

function inferPhaseStatuses(inc: HealingIncident): PhaseStatus[] {
  const out: PhaseStatus[] = ['pending', 'pending', 'pending', 'pending', 'pending', 'pending'];
  if (inc.anomaly_type) out[0] = 'success';
  if (inc.top_cause && (inc.confidence ?? 0) > 0) out[1] = 'success';
  if (inc.escalation_reason && /preverify|reject/i.test(inc.escalation_reason)) {
    out[2] = 'rejected';
  } else if (inc.action_type && inc.action_type !== 'none') {
    out[2] = 'success';
  }
  if (inc.action_type === 'ESCALATE') {
    out[3] = 'fail';
  } else if (inc.hitl_required) {
    out[3] = 'rejected';
  } else if (inc.auto_recovered) {
    out[3] = 'success';
  }
  if (inc.pre_yield !== null && inc.pre_yield !== undefined) {
    out[4] = inc.improved ? 'success' : 'fail';
  }
  if (inc.id) out[5] = 'success';
  return out;
}

function parseTime(ts?: string): string {
  if (!ts) return '?';
  try {
    const d = new Date(ts);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  } catch {
    return '?';
  }
}
