'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import type { HealingIncident } from '@/types';

/** 선택된 incident의 진단/PRE-VERIFY/복구/검증/학습 풀스토리 */
export default function SelectedIncidentCard() {
  const { state, selectIncident } = useEngine();
  const id = state.selectedIncidentId;
  const incidents = state.healing?.recentIncidents ?? [];
  const inc = id ? incidents.find((i) => i.id === id) : incidents[incidents.length - 1];

  if (!inc) {
    return (
      <GlassCard>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-bold text-white/60 uppercase tracking-wider">
            Heal Lane
          </span>
        </div>
        <div className="text-[10px] text-white/40 px-2 py-6 text-center">
          incident 선택 안됨 — Detect lane에서 클릭
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-3 overflow-y-auto">
      <Header inc={inc} onClear={() => selectIncident(null)} hasSelection={!!id} />
      <DiagnoseSection inc={inc} />
      <PreVerifySection inc={inc} />
      <RecoverSection inc={inc} />
      <VerifySection inc={inc} />
      <LearnSection inc={inc} />
    </GlassCard>
  );
}

function Header({
  inc,
  onClear,
  hasSelection,
}: {
  inc: HealingIncident;
  onClear: () => void;
  hasSelection: boolean;
}) {
  return (
    <div className="border-b border-white/10 pb-2 mb-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold text-white/60 uppercase tracking-wider">
            {hasSelection ? 'Selected' : 'Latest'} Incident
          </span>
          <span className="text-[11px] font-mono font-bold text-cyan-300">{inc.id}</span>
          <SeverityPill sev={inc.severity} />
        </div>
        {hasSelection && (
          <button
            onClick={onClear}
            className="text-[9px] text-white/30 hover:text-white/60 px-1"
          >
            ✕ 해제
          </button>
        )}
      </div>
      <div className="flex items-center gap-2 mt-1.5">
        <span className="text-[10px] font-mono text-white/80">{inc.step_id}</span>
        <span className="text-[9px] text-white/40">
          iter {inc.iteration ?? '?'} · {parseTime(inc.timestamp)}
        </span>
        {inc.history_matched && (
          <span className="text-[8px] px-1 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono">
            ✓ pattern matched
          </span>
        )}
      </div>
    </div>
  );
}

function DiagnoseSection({ inc }: { inc: HealingIncident }) {
  return (
    <Section title="① 진단" phase="DIAGNOSE">
      <KV k="원인" v={inc.top_cause || '?'} highlight />
      <KV k="신뢰도" v={`${((inc.confidence ?? 0) * 100).toFixed(0)}%`} />
      <KV k="이상 유형" v={inc.anomaly_type || '?'} />
      <KV k="후보 수" v={String(inc.candidates_count ?? '?')} />
      {inc.causal_chain && (
        <div className="mt-1 px-1.5 py-1 rounded bg-purple-500/10 border-l-2 border-purple-400">
          <div className="text-[8px] uppercase tracking-wider text-purple-300/70">
            인과 체인
          </div>
          <div className="text-[10px] text-purple-100 mt-0.5">{inc.causal_chain}</div>
        </div>
      )}
      {inc.matched_pattern_type && (
        <KV k="패턴" v={inc.matched_pattern_type} />
      )}
      {inc.evidence_refs && inc.evidence_refs.length > 0 && (
        <div className="text-[8px] text-white/40 mt-1 font-mono">
          증거: {inc.evidence_refs.slice(0, 3).join(' · ')}
        </div>
      )}
    </Section>
  );
}

function PreVerifySection({ inc }: { inc: HealingIncident }) {
  const rejected = inc.escalation_reason && /preverify|reject/i.test(inc.escalation_reason);
  return (
    <Section title="② PRE-VERIFY" phase="PRE-VERIFY" status={rejected ? 'rejected' : 'pass'}>
      {rejected ? (
        <div className="text-[10px] text-amber-300">{inc.escalation_reason}</div>
      ) : (
        <div className="text-[10px] text-emerald-300/80">
          시뮬레이션 통과 — anti-recurrence 정책 적용
        </div>
      )}
    </Section>
  );
}

function RecoverSection({ inc }: { inc: HealingIncident }) {
  const escalated = inc.action_type === 'ESCALATE' || inc.hitl_required;
  return (
    <Section title="③ 복구 실행" phase="RECOVER" status={escalated ? 'escalate' : 'success'}>
      <KV k="액션" v={inc.action_type || '?'} highlight />
      <KV k="위험도" v={inc.risk_level || '?'} />
      <KV k="플레이북" v={inc.playbook_id || '?'} />
      {inc.recovery_time_sec !== undefined && (
        <KV
          k="실행 시간"
          v={`${(inc.recovery_time_sec * 1000).toFixed(1)}ms`}
        />
      )}
      {inc.hitl_required && (
        <div className="mt-1 px-1.5 py-1 rounded bg-amber-500/10 border-l-2 border-amber-400">
          <div className="text-[9px] text-amber-200">HITL 게이트 — 운영자 승인 대기</div>
        </div>
      )}
    </Section>
  );
}

function VerifySection({ inc }: { inc: HealingIncident }) {
  const delta =
    inc.pre_yield !== undefined && inc.post_yield !== undefined
      ? inc.post_yield - inc.pre_yield
      : null;
  return (
    <Section
      title="④ 검증"
      phase="VERIFY"
      status={inc.improved ? 'success' : 'fail'}
    >
      {inc.pre_yield !== undefined && (
        <>
          <KV k="pre yield" v={`${(inc.pre_yield * 100).toFixed(2)}%`} />
          <KV
            k="post yield"
            v={`${((inc.post_yield ?? 0) * 100).toFixed(2)}%`}
            highlight
          />
          {delta !== null && (
            <KV
              k="Δ yield"
              v={`${delta > 0 ? '+' : ''}${(delta * 100).toFixed(3)}%p`}
              highlight
            />
          )}
        </>
      )}
      {!inc.improved && (
        <div className="text-[10px] text-rose-300/80 mt-1">
          개선 미감지 — 다음 사이클에 anti-recurrence가 다른 액션 강제
        </div>
      )}
    </Section>
  );
}

function LearnSection({ inc }: { inc: HealingIncident }) {
  return (
    <Section title="⑤ 학습" phase="LEARN" status="success">
      <div className="text-[9px] text-white/60">
        FailureChain {inc.matched_chain_id ? `매칭 (${inc.matched_chain_id})` : '신규 생성'}
      </div>
      <div className="text-[9px] text-white/50">
        recurrence_tracker 갱신 + L3 그래프 강화
      </div>
      {inc.playbook_source && (
        <div className="text-[8px] text-white/40 font-mono mt-1">
          playbook source: {inc.playbook_source}
        </div>
      )}
    </Section>
  );
}

function Section({
  title,
  phase,
  status = 'success',
  children,
}: {
  title: string;
  phase: string;
  status?: 'success' | 'fail' | 'escalate' | 'rejected' | 'pass';
  children: React.ReactNode;
}) {
  const colors: Record<string, string> = {
    success: 'border-emerald-400/40 bg-emerald-950/20',
    pass: 'border-emerald-400/40 bg-emerald-950/20',
    fail: 'border-rose-400/40 bg-rose-950/20',
    escalate: 'border-amber-400/40 bg-amber-950/20',
    rejected: 'border-amber-400/40 bg-amber-950/20',
  };
  return (
    <div className={`border-l-2 pl-2 py-1 mb-1.5 ${colors[status]}`}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <span className="text-[10px] font-bold text-white/80">{title}</span>
        <span className="text-[7px] px-1 rounded bg-white/10 text-white/50 font-mono">
          {phase}
        </span>
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function KV({ k, v, highlight = false }: { k: string; v: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[9px] text-white/40">{k}</span>
      <span
        className={`text-[10px] font-mono ${
          highlight ? 'text-cyan-200 font-bold' : 'text-white/80'
        }`}
      >
        {v}
      </span>
    </div>
  );
}

function SeverityPill({ sev }: { sev?: string }) {
  if (!sev) return null;
  const colors: Record<string, string> = {
    CRITICAL: 'bg-rose-600/40 text-rose-200',
    HIGH: 'bg-orange-500/40 text-orange-200',
    MEDIUM: 'bg-amber-500/40 text-amber-200',
    LOW: 'bg-emerald-500/40 text-emerald-200',
  };
  return (
    <span className={`text-[8px] px-1 py-0.5 rounded font-mono ${colors[sev] || 'bg-white/10'}`}>
      {sev}
    </span>
  );
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
