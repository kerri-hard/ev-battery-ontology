'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import { EmptyState } from '@/components/common/StateMessages';
import { statusToPill } from '@/components/common/severityColors';

/** FailureChain 패턴 매칭 explorer — anti-recurrence 시그니처 + 학습 누적 */
export default function FailureChainExplorer() {
  const { state, navigateTo } = useEngine();
  const rc = state.recurrence;

  if (!rc || rc.total_signatures === 0) {
    return (
      <GlassCard>
        <div className="flex items-center justify-between mb-2">
          <span className="ds-label">FailureChain — 패턴 매칭 학습</span>
        </div>
        <EmptyState
          icon="🧠"
          title="학습 데이터 없음"
          hint="sim이 실행되면 anti-recurrence 시그니처가 누적됩니다"
        />
      </GlassCard>
    );
  }

  const sigs = rc.top_signatures ?? [];
  const totalAttempts = sigs.reduce((sum, s) => sum + s.count, 0);
  const repeatingShare =
    rc.total_signatures > 0 ? (rc.repeating_count / rc.total_signatures) * 100 : 0;

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="ds-label">FailureChain Explorer</span>
        <div className="flex items-center gap-2">
          <span className="ds-caption text-cyan-300">{rc.total_signatures} sigs</span>
          <span className="ds-caption">·</span>
          <span
            className={`ds-caption font-bold ${
              repeatingShare > 30 ? 'text-rose-300' : 'text-emerald-300'
            }`}
          >
            {rc.repeating_count} repeating ({repeatingShare.toFixed(0)}%)
          </span>
        </div>
      </div>

      <div className="space-y-1 max-h-[420px] overflow-y-auto pr-1">
        {sigs.map((sig, idx) => (
          <button
            key={idx}
            onClick={() =>
              navigateTo({ view: 'healing', stepId: sig.step_id })
            }
            className="w-full text-left px-2 py-1.5 rounded bg-white/[0.03] border-l-2 border-white/10 hover:bg-white/5 hover:border-cyan-400/40 transition"
            title={`Healing 페이지에서 ${sig.step_id} incident 보기 →`}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="text-[10px] font-mono font-bold text-cyan-300">
                  {sig.step_id}
                </span>
                <span className="ds-caption">·</span>
                <span className="ds-body truncate">{sig.cause_type}</span>
              </div>
              <div className="flex items-center gap-1.5 whitespace-nowrap">
                <span className="ds-caption text-amber-300 font-bold">×{sig.count}</span>
                <span
                  className={`text-[8px] px-1 py-0.5 rounded font-mono ${
                    sig.last_success ? statusToPill('success') : statusToPill('fail')
                  }`}
                >
                  {sig.last_success ? '✓' : '✗'}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-1 mt-1">
              <span className="ds-label text-[8px]">tried:</span>
              {sig.tried_actions.length === 0 ? (
                <span className="ds-caption">없음</span>
              ) : (
                sig.tried_actions.map((a) => (
                  <span
                    key={a}
                    className="text-[8px] font-mono px-1 py-0.5 rounded pill-info"
                  >
                    {a}
                  </span>
                ))
              )}
              <span className="ml-auto ds-caption">{sig.anomaly_type}</span>
            </div>
            {sig.count >= 2 && sig.tried_actions.length === 1 && (
              <div className="mt-1 ds-caption text-amber-300">
                ⚠ {sig.count}회 반복인데 1액션만 시도 — anti-recurrence 작동 가능 (다음 회 다른 액션)
              </div>
            )}
            {sig.count >= 3 && sig.tried_actions.length >= 2 && !sig.last_success && (
              <div className="mt-1 ds-caption text-rose-300">
                ⚠ {sig.count}회 반복 + {sig.tried_actions.length}액션 시도 후도 실패 — ESCALATE 임박
              </div>
            )}
          </button>
        ))}
      </div>

      <div className="mt-2 pt-2 border-t border-white/10 grid grid-cols-3 gap-2">
        <div>
          <div className="ds-label text-[8px]">총 시그니처</div>
          <div className="font-mono text-white/80 font-bold ds-body">{rc.total_signatures}</div>
        </div>
        <div>
          <div className="ds-label text-[8px]">반복 시그니처</div>
          <div
            className={`font-mono font-bold ds-body ${
              repeatingShare > 30 ? 'text-rose-300' : 'text-emerald-300'
            }`}
          >
            {rc.repeating_count}
          </div>
        </div>
        <div>
          <div className="ds-label text-[8px]">총 시도</div>
          <div className="font-mono text-white/80 font-bold ds-body">{totalAttempts}</div>
        </div>
      </div>
    </GlassCard>
  );
}
