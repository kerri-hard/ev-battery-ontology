'use client';

import { useEngine } from '@/context/EngineContext';

/**
 * VISION 9.5 (실패에서 성장) 가시화.
 * 같은 (step, anomaly, cause) 가 반복되는 패턴을 표시 →
 * 운영자가 학습이 안 되고 있는 영역을 즉시 인지.
 */
export default function RecurrencePanel() {
  const { state } = useEngine();
  const rec = state.recurrence;

  if (!rec || rec.total_signatures === 0) {
    return (
      <div className="glass p-2.5">
        <div className="text-[10px] font-bold text-white/70 uppercase tracking-wider mb-1.5">
          Recurrence Watch
        </div>
        <div className="text-[10px] text-white/40">데이터 누적 중</div>
      </div>
    );
  }

  const recurringPct = rec.total_signatures > 0
    ? (rec.repeating_count / rec.total_signatures) * 100
    : 0;
  const headerColor = recurringPct >= 40 ? '#ef4444' : recurringPct >= 25 ? '#f59e0b' : '#10b981';

  return (
    <div className="glass p-2.5">
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-[10px] font-bold text-white/70 uppercase tracking-wider">
          Recurrence Watch
        </div>
        <div
          className="text-[9px] font-bold px-1.5 py-0.5 rounded"
          style={{ background: `${headerColor}25`, color: headerColor }}
        >
          {rec.repeating_count}/{rec.total_signatures} repeating ({recurringPct.toFixed(0)}%)
        </div>
      </div>
      <div className="text-[9px] text-white/45 mb-1.5">
        VISION 9.5 — 실패에서 성장: 같은 (step, anomaly, cause) 반복 시그니처
      </div>

      <div className="space-y-1 max-h-[180px] overflow-y-auto pr-1">
        {rec.top_signatures.map((sig, i) => (
          <SignatureRow key={`${sig.step_id}-${sig.cause_type}-${i}`} sig={sig} />
        ))}
      </div>
    </div>
  );
}

function SignatureRow({ sig }: { sig: import('@/types').RecurrenceSignature }) {
  const isRepeating = sig.count >= 2;
  const isExhausted = sig.tried_actions.length >= 3;

  return (
    <div
      className={`rounded border px-2 py-1 text-[10px] ${
        isExhausted
          ? 'border-red-500/40 bg-red-500/5'
          : isRepeating
            ? 'border-amber-500/30 bg-amber-500/5'
            : 'border-white/10'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-white/75 truncate" title={`${sig.step_id} / ${sig.anomaly_type}`}>
          {sig.step_id}
        </span>
        <span className="flex items-center gap-1">
          <span className="font-mono text-white/85">x{sig.count}</span>
          <span className={sig.last_success ? 'text-emerald-300' : 'text-red-400'}>
            {sig.last_success ? '✓' : '✗'}
          </span>
        </span>
      </div>
      <div className="text-[9px] text-white/55 truncate" title={sig.cause_type}>
        cause: {sig.cause_type}
      </div>
      {sig.tried_actions.length > 0 && (
        <div className="text-[9px] text-cyan-300/80 truncate" title={sig.tried_actions.join(', ')}>
          tried: {sig.tried_actions.join(', ')}
          {isExhausted && <span className="text-red-300"> (exhausted)</span>}
        </div>
      )}
    </div>
  );
}
