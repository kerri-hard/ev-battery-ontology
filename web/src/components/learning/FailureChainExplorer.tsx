'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';

/** FailureChain 패턴 매칭 explorer — anti-recurrence 시그니처 + 학습 누적 */
export default function FailureChainExplorer() {
  const { state } = useEngine();
  const rc = state.recurrence;

  if (!rc || rc.total_signatures === 0) {
    return (
      <GlassCard>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-bold text-white/60 uppercase tracking-wider">
            FailureChain — 패턴 매칭 학습
          </span>
        </div>
        <div className="text-[10px] text-white/40 px-2 py-6 text-center">
          아직 학습 데이터 없음 — sim 실행 필요
        </div>
      </GlassCard>
    );
  }

  const sigs = rc.top_signatures ?? [];
  const totalAttempts = sigs.reduce((sum, s) => sum + s.count, 0);
  const repeatingShare = rc.total_signatures > 0
    ? (rc.repeating_count / rc.total_signatures) * 100
    : 0;

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold text-white/60 uppercase tracking-wider">
          FailureChain Explorer
        </span>
        <div className="flex items-center gap-2 text-[9px] font-mono">
          <span className="text-cyan-300">{rc.total_signatures} sigs</span>
          <span className="text-white/40">·</span>
          <span className={repeatingShare > 30 ? 'text-rose-300' : 'text-emerald-300'}>
            {rc.repeating_count} repeating ({repeatingShare.toFixed(0)}%)
          </span>
        </div>
      </div>

      <div className="space-y-1 max-h-[420px] overflow-y-auto pr-1">
        {sigs.map((sig, idx) => (
          <div
            key={idx}
            className="px-2 py-1.5 rounded bg-white/[0.03] border-l-2 border-white/10 hover:bg-white/5 hover:border-cyan-400/40"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="text-[10px] font-mono font-bold text-cyan-300">
                  {sig.step_id}
                </span>
                <span className="text-[8px] text-white/40">·</span>
                <span className="text-[9px] text-white/70 truncate">{sig.cause_type}</span>
              </div>
              <div className="flex items-center gap-1.5 whitespace-nowrap">
                <span className="text-[9px] font-mono text-amber-300">×{sig.count}</span>
                {sig.last_success ? (
                  <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
                    ✓
                  </span>
                ) : (
                  <span className="text-[8px] px-1 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono">
                    ✗
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 mt-1">
              <span className="text-[8px] text-white/30 uppercase tracking-wider">
                tried:
              </span>
              {sig.tried_actions.length === 0 ? (
                <span className="text-[8px] text-white/30">없음</span>
              ) : (
                sig.tried_actions.map((a) => (
                  <span
                    key={a}
                    className="text-[8px] font-mono px-1 py-0.5 rounded bg-cyan-500/15 text-cyan-200"
                  >
                    {a}
                  </span>
                ))
              )}
              <span className="ml-auto text-[8px] text-white/30 font-mono">
                {sig.anomaly_type}
              </span>
            </div>
            {/* anti-recurrence policy 상태 표시 */}
            {sig.count >= 2 && sig.tried_actions.length === 1 && (
              <div className="mt-1 text-[8px] text-amber-300/80">
                ⚠ {sig.count}회 반복인데 1액션만 시도 — anti-recurrence 작동 가능 (다음 회 다른 액션)
              </div>
            )}
            {sig.count >= 3 && sig.tried_actions.length >= 2 && !sig.last_success && (
              <div className="mt-1 text-[8px] text-rose-300/80">
                ⚠ {sig.count}회 반복 + {sig.tried_actions.length}액션 시도 후도 실패 — ESCALATE 임박
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-2 pt-2 border-t border-white/10 grid grid-cols-3 gap-2 text-[9px]">
        <div>
          <div className="text-white/40 uppercase tracking-wider text-[8px]">총 시그니처</div>
          <div className="font-mono text-white/80 font-bold">{rc.total_signatures}</div>
        </div>
        <div>
          <div className="text-white/40 uppercase tracking-wider text-[8px]">반복 시그니처</div>
          <div className={`font-mono font-bold ${repeatingShare > 30 ? 'text-rose-300' : 'text-emerald-300'}`}>
            {rc.repeating_count}
          </div>
        </div>
        <div>
          <div className="text-white/40 uppercase tracking-wider text-[8px]">총 시도</div>
          <div className="font-mono text-white/80 font-bold">{totalAttempts}</div>
        </div>
      </div>
    </GlassCard>
  );
}
