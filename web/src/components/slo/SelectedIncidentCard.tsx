'use client';

import { useEffect, useState } from 'react';
import { useEngine } from '@/context/EngineContext';
import { apiUrl } from '@/lib/api';
import GlassCard from '@/components/common/GlassCard';
import { EmptyState } from '@/components/common/StateMessages';
import {
  severityToPill,
  severityShort,
  statusToPill,
} from '@/components/common/severityColors';
import type { HealingIncident, RecurrenceSignature } from '@/types';

interface PersonnelOption {
  id: string;
  name: string;
  role: string;
  safety_level_max: string;
}

function usePersonnel(): PersonnelOption[] {
  const [list, setList] = useState<PersonnelOption[]>([]);
  useEffect(() => {
    let mounted = true;
    fetch(apiUrl('/api/personnel'))
      .then((r) => (r.ok ? r.json() : { personnel: [] }))
      .then((d) => {
        if (mounted && Array.isArray(d.personnel)) setList(d.personnel);
      })
      .catch(() => {
        // graceful — Personnel 노드 없거나 API 실패 시 빈 목록 (anonymous 동작)
      });
    return () => {
      mounted = false;
    };
  }, []);
  return list;
}

/** 선택된 incident의 진단/PRE-VERIFY/복구/검증/학습 풀스토리 + HITL inline action */
export default function SelectedIncidentCard() {
  const { state, selectIncident, sendCommand } = useEngine();
  const id = state.selectedIncidentId;
  const incidents = state.healing?.recentIncidents ?? [];
  const inc = id ? incidents.find((i) => i.id === id) : incidents[incidents.length - 1];
  const personnel = usePersonnel();
  const [selectedPersonnelId, setSelectedPersonnelId] = useState<string>('');

  if (!inc) {
    return (
      <GlassCard>
        <div className="flex items-center justify-between mb-2">
          <span className="ds-label">Heal Lane</span>
        </div>
        <EmptyState
          icon="🛡"
          title="incident 미선택"
          hint="Detect lane에서 incident를 클릭하세요. 클릭하지 않으면 가장 최근 incident가 자동 표시됩니다."
        />
      </GlassCard>
    );
  }

  // 과거 동일 시그니처 추적 (recurrence_tracker)
  const recSig = findMatchingRecurrence(inc, state.recurrence?.top_signatures ?? []);

  return (
    <GlassCard className="p-3 overflow-y-auto">
      <Header inc={inc} onClear={() => selectIncident(null)} hasSelection={!!id} />
      {/* 과거 시그니처 inline (FailureChainExplorer 발췌) */}
      {recSig && <RecurrenceInline rec={recSig} />}
      {/* HITL inline action — Personnel 식별 + 자격 검증 (anonymous 호환) */}
      {inc.hitl_required && inc.hitl_id && (
        <HitlActions
          hitlId={inc.hitl_id}
          personnel={personnel}
          selectedPersonnelId={selectedPersonnelId}
          onSelectPersonnel={setSelectedPersonnelId}
          onApprove={() =>
            sendCommand({
              cmd: 'hitl_approve',
              id: inc.hitl_id!,
              operator: selectedPersonnelId
                ? (personnel.find((p) => p.id === selectedPersonnelId)?.name ?? 'operator-ui')
                : 'operator-ui',
              personnel_id: selectedPersonnelId || undefined,
            })
          }
          onReject={() =>
            sendCommand({
              cmd: 'hitl_reject',
              id: inc.hitl_id!,
              operator: selectedPersonnelId
                ? (personnel.find((p) => p.id === selectedPersonnelId)?.name ?? 'operator-ui')
                : 'operator-ui',
              personnel_id: selectedPersonnelId || undefined,
            })
          }
        />
      )}
      <DiagnoseSection inc={inc} />
      <PreVerifySection inc={inc} />
      <RecoverSection inc={inc} />
      <VerifySection inc={inc} />
      <LearnSection inc={inc} />
    </GlassCard>
  );
}

function findMatchingRecurrence(
  inc: HealingIncident,
  sigs: RecurrenceSignature[],
): RecurrenceSignature | undefined {
  return sigs.find(
    (s) =>
      s.step_id === inc.step_id &&
      s.anomaly_type === inc.anomaly_type &&
      s.cause_type === (inc.top_cause ?? ''),
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
          <span className="ds-label">{hasSelection ? 'Selected' : 'Latest'} Incident</span>
          <span className="text-[11px] font-mono font-bold text-cyan-300">{inc.id}</span>
          {inc.severity && (
            <span
              className={`text-[8px] px-1 py-0.5 rounded font-mono ${severityToPill(inc.severity)}`}
              title={inc.severity}
            >
              {severityShort(inc.severity)}
            </span>
          )}
        </div>
        {hasSelection && (
          <button
            onClick={onClear}
            className="ds-caption hover:text-white/80 px-1"
          >
            ✕ 해제
          </button>
        )}
      </div>
      <div className="flex items-center gap-2 mt-1.5">
        <span className="ds-body font-mono">{inc.step_id}</span>
        <span className="ds-caption">
          iter {inc.iteration ?? '?'} · {parseTime(inc.timestamp)}
        </span>
        {inc.history_matched && (
          <span className="text-[8px] px-1 py-0.5 rounded pill-info font-mono">
            ✓ pattern matched
          </span>
        )}
      </div>
    </div>
  );
}

function RecurrenceInline({ rec }: { rec: RecurrenceSignature }) {
  return (
    <div className="mb-2 px-2 py-1.5 rounded bg-white/[0.03] border-l-2 border-purple-400/40">
      <div className="ds-label text-purple-300 mb-0.5">📈 과거 동일 시그니처</div>
      <div className="flex items-center justify-between gap-2">
        <div className="ds-caption">
          {rec.count}회 반복 ·{' '}
          {rec.tried_actions.length === 0
            ? '액션 없음'
            : `시도: ${rec.tried_actions.join(', ')}`}
        </div>
        <span
          className={`text-[8px] px-1 py-0.5 rounded font-mono ${
            rec.last_success ? 'pill-success' : 'pill-danger'
          }`}
        >
          {rec.last_success ? '마지막 ✓' : '마지막 ✗'}
        </span>
      </div>
      {rec.count >= 3 && rec.tried_actions.length >= 2 && !rec.last_success && (
        <div className="ds-caption text-rose-300 mt-1">
          ⚠ {rec.count}회 + {rec.tried_actions.length}액션 시도 후도 실패 — ESCALATE 임박
        </div>
      )}
    </div>
  );
}

function HitlActions({
  hitlId,
  personnel,
  selectedPersonnelId,
  onSelectPersonnel,
  onApprove,
  onReject,
}: {
  hitlId: string;
  personnel: PersonnelOption[];
  selectedPersonnelId: string;
  onSelectPersonnel: (id: string) => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const selected = personnel.find((p) => p.id === selectedPersonnelId);
  return (
    <div className="mb-2 px-2 py-2 rounded pill-warning">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div>
          <div className="ds-body font-bold">⏸ HITL 승인 대기</div>
          <div className="ds-caption font-mono">{hitlId}</div>
        </div>
      </div>
      {/* Personnel 식별 (선택, anonymous 호환) — 그래프 Personnel 노드 */}
      {personnel.length > 0 && (
        <div className="mb-1.5">
          <select
            value={selectedPersonnelId}
            onChange={(e) => onSelectPersonnel(e.target.value)}
            className="w-full ds-caption bg-white/5 border border-white/10 rounded px-1.5 py-0.5"
            aria-label="승인자 선택"
          >
            <option value="">— 익명 (anonymous, 자격 검증 없음) —</option>
            {personnel.map((p) => (
              <option key={p.id} value={p.id}>
                {p.id} · {p.name} · {p.role} (max {p.safety_level_max})
              </option>
            ))}
          </select>
          {selected && (
            <div className="ds-caption text-white/60 mt-0.5">
              자격 max: <span className="text-cyan-300 font-bold">{selected.safety_level_max}</span>
              {' '}— action.safety_level &gt; {selected.safety_level_max} 이면 자동 deny
            </div>
          )}
        </div>
      )}
      <div className="flex gap-2">
        <button
          onClick={onApprove}
          className="flex-1 px-2 py-1 rounded pill-success hover:opacity-90 transition text-[11px] font-bold"
          title="자동 복구 액션 승인"
        >
          ✓ 승인
        </button>
        <button
          onClick={onReject}
          className="flex-1 px-2 py-1 rounded pill-danger hover:opacity-90 transition text-[11px] font-bold"
          title="액션 거부 (ESCALATE)"
        >
          ✗ 거부
        </button>
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
          <div className="ds-label text-purple-300/70">인과 체인</div>
          <div className="ds-body text-purple-100 mt-0.5">{inc.causal_chain}</div>
        </div>
      )}
      {inc.matched_pattern_type && <KV k="패턴" v={inc.matched_pattern_type} />}
      {inc.evidence_refs && inc.evidence_refs.length > 0 && (
        <div className="ds-caption mt-1">증거: {inc.evidence_refs.slice(0, 3).join(' · ')}</div>
      )}
      {inc.excluded_candidates && inc.excluded_candidates.length > 0 && (
        <div className="mt-1.5 px-1.5 py-1 rounded bg-amber-500/5 border-l-2 border-amber-400/40">
          <div className="ds-label text-amber-300/70">왜 다른 후보 아닌가 (배제 사유)</div>
          <div className="mt-0.5 space-y-0.5">
            {inc.excluded_candidates.slice(0, 3).map((c, i) => (
              <div key={i} className="ds-caption text-white/70">
                <span className="text-amber-200/90 font-mono">
                  {c.cause_type || '?'}
                </span>
                <span className="text-white/40 mx-1">·</span>
                <span className="font-mono">
                  {((c.confidence ?? 0) * 100).toFixed(0)}%
                </span>
                <span className="text-white/40 mx-1">→</span>
                <span className="text-white/60">{c.exclusion_reason || '?'}</span>
              </div>
            ))}
          </div>
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
        <div className="ds-body text-amber-300">{inc.escalation_reason}</div>
      ) : (
        <div className="ds-body text-emerald-300/80">시뮬레이션 통과 — anti-recurrence 정책 적용</div>
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
        <KV k="실행 시간" v={`${(inc.recovery_time_sec * 1000).toFixed(1)}ms`} />
      )}
      {inc.hitl_required && (
        <div className="mt-1 px-1.5 py-1 rounded pill-warning">
          <div className="ds-caption">HITL 게이트 — 운영자 승인 대기 (위 버튼)</div>
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
    <Section title="④ 검증" phase="VERIFY" status={inc.improved ? 'success' : 'fail'}>
      {inc.pre_yield !== undefined && (
        <>
          <KV k="pre yield" v={`${(inc.pre_yield * 100).toFixed(2)}%`} />
          <KV k="post yield" v={`${((inc.post_yield ?? 0) * 100).toFixed(2)}%`} highlight />
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
        <div className="ds-body text-rose-300/80 mt-1">
          개선 미감지 — 다음 사이클에 anti-recurrence가 다른 액션 강제
        </div>
      )}
    </Section>
  );
}

function LearnSection({ inc }: { inc: HealingIncident }) {
  return (
    <Section title="⑤ 학습" phase="LEARN" status="success">
      <div className="ds-caption">
        FailureChain {inc.matched_chain_id ? `매칭 (${inc.matched_chain_id})` : '신규 생성'}
      </div>
      <div className="ds-caption">recurrence_tracker 갱신 + L3 그래프 강화</div>
      {inc.playbook_source && (
        <div className="ds-caption mt-1">playbook source: {inc.playbook_source}</div>
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
  const pillCls = statusToPill(status);
  return (
    <div className={`border-l-2 pl-2 py-1 mb-1.5 rounded ${pillCls} border-current/40`}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <span className="ds-body font-bold">{title}</span>
        <span className="text-[7px] px-1 rounded bg-white/10 text-white/50 font-mono">{phase}</span>
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function KV({ k, v, highlight = false }: { k: string; v: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="ds-caption">{k}</span>
      <span className={`text-[10px] font-mono ${highlight ? 'text-cyan-200 font-bold' : 'text-white/80'}`}>
        {v}
      </span>
    </div>
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
