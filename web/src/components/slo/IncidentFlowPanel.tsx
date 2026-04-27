'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import type { HealingIncident } from '@/types';

/** 7-페이즈 자율 복구 루프 — incident가 흐르는 단계 */
const PHASES = [
  { key: 'detect', label: 'DETECT', desc: '이상 감지' },
  { key: 'diagnose', label: 'DIAGNOSE', desc: '원인 진단' },
  { key: 'preverify', label: 'PRE-VERIFY', desc: '시뮬 게이트' },
  { key: 'recover', label: 'RECOVER', desc: '복구 실행' },
  { key: 'verify', label: 'VERIFY', desc: 'yield 검증' },
  { key: 'learn', label: 'LEARN', desc: '학습/영속화' },
] as const;

type PhaseStatus = 'pending' | 'success' | 'fail' | 'rejected';

/** 실시간 incident 라이프사이클 — 7-페이즈 진행 상태 + 결과 */
export default function IncidentFlowPanel() {
  const { state, selectIncident, navigateTo } = useEngine();
  const incidents = state.healing?.recentIncidents ?? [];
  const selectedStepId = state.selectedStepId;
  // step 선택 시 해당 step의 incident만 노출 (drill-down 필터)
  const filtered = selectedStepId
    ? incidents.filter((i) => i.step_id === selectedStepId)
    : incidents;
  const sorted = [...filtered]
    .sort((a, b) => (b.iteration ?? 0) - (a.iteration ?? 0))
    .slice(0, 12);
  const selectedId = state.selectedIncidentId;

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="ds-label">Incident Flow — 라이프사이클</span>
        <div className="flex items-center gap-2">
          {selectedStepId && (
            <button
              onClick={() => navigateTo({ stepId: null })}
              className="text-[8px] px-1.5 py-0.5 rounded pill-info font-mono hover:opacity-90"
              title="필터 해제"
            >
              {selectedStepId} ✕
            </button>
          )}
          <span className="ds-caption">
            최근 {sorted.length} / {incidents.length}건
          </span>
        </div>
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
          <div className="text-[10px] text-white/40 px-2 py-4 text-center">
            아직 incident 없음 — sim 실행 대기
          </div>
        ) : (
          sorted.map((inc, idx) => (
            <IncidentRow
              key={inc.id}
              incident={inc}
              fresh={idx < 3}
              selected={inc.id === selectedId}
              onClick={() =>
                selectIncident(inc.id === selectedId ? null : inc.id ?? null)
              }
            />
          ))
        )}
      </div>
    </GlassCard>
  );
}

function IncidentRow({
  incident,
  fresh,
  selected,
  onClick,
}: {
  incident: HealingIncident;
  fresh: boolean;
  selected: boolean;
  onClick: () => void;
}) {
  const phases = inferPhaseStatuses(incident);
  const sevColor = severityColor(incident.severity);
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
          <span className={`text-[7px] px-1 rounded ${sevColor}`}>
            {(incident.severity || '?').slice(0, 1)}
          </span>
        </div>
        <div className="text-[8px] text-white/40 font-mono truncate">
          {incident.step_id} · {time}
        </div>
        <div className="text-[8px] text-white/30 truncate">
          {incident.top_cause}
        </div>
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
  const cfg: Record<PhaseStatus, { bg: string; mark: string }> = {
    pending: { bg: 'bg-white/10', mark: '' },
    success: { bg: 'bg-emerald-500/70', mark: '✓' },
    fail: { bg: 'bg-rose-500/70', mark: '✗' },
    rejected: { bg: 'bg-amber-500/70', mark: '!' },
  };
  const c = cfg[status];
  return (
    <div
      className={`h-4 rounded flex items-center justify-center text-[8px] font-bold text-white/90 ${c.bg}`}
      title={`${label}: ${status}`}
    >
      {c.mark}
    </div>
  );
}

function ResultBadge({ incident }: { incident: HealingIncident }) {
  if (incident.hitl_required) {
    return (
      <span className="text-[8px] px-1 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono">
        HITL
      </span>
    );
  }
  if (incident.action_type === 'ESCALATE') {
    return (
      <span className="text-[8px] px-1 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono">
        ESCALATE
      </span>
    );
  }
  if (incident.auto_recovered && incident.improved) {
    return (
      <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
        ✓ 복구
      </span>
    );
  }
  if (incident.auto_recovered) {
    return (
      <span className="text-[8px] px-1 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono">
        실행
      </span>
    );
  }
  return (
    <span className="text-[8px] px-1 py-0.5 rounded bg-white/10 text-white/50 font-mono">
      ?
    </span>
  );
}

function inferPhaseStatuses(inc: HealingIncident): PhaseStatus[] {
  const out: PhaseStatus[] = ['pending', 'pending', 'pending', 'pending', 'pending', 'pending'];

  // DETECT — anomaly_type 있으면 항상 success
  if (inc.anomaly_type) out[0] = 'success';

  // DIAGNOSE — top_cause + confidence > 0
  if (inc.top_cause && (inc.confidence ?? 0) > 0) out[1] = 'success';

  // PRE-VERIFY — action_type 선택됐으면 success, escalation_reason에 preverify 거절 정보 있으면 rejected
  if (inc.escalation_reason && /preverify|reject/i.test(inc.escalation_reason)) {
    out[2] = 'rejected';
  } else if (inc.action_type && inc.action_type !== 'none') {
    out[2] = 'success';
  }

  // RECOVER — action_type 실행 (HITL 강제거나 ESCALATE면 fail)
  if (inc.action_type === 'ESCALATE') {
    out[3] = 'fail';
  } else if (inc.hitl_required) {
    out[3] = 'rejected';
  } else if (inc.auto_recovered) {
    out[3] = 'success';
  }

  // VERIFY — pre/post yield 비교
  if (inc.pre_yield !== null && inc.pre_yield !== undefined) {
    out[4] = inc.improved ? 'success' : 'fail';
  }

  // LEARN — incident persist (id가 있으면 항상 success)
  if (inc.id) out[5] = 'success';

  return out;
}

function severityColor(sev?: string): string {
  switch (sev) {
    case 'CRITICAL':
      return 'bg-rose-600/40 text-rose-200';
    case 'HIGH':
      return 'bg-orange-500/40 text-orange-200';
    case 'MEDIUM':
      return 'bg-amber-500/40 text-amber-200';
    case 'LOW':
      return 'bg-emerald-500/40 text-emerald-200';
    default:
      return 'bg-white/10 text-white/50';
  }
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
