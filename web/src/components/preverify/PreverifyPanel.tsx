'use client';

import { useEngine } from '@/context/EngineContext';

export default function PreverifyPanel() {
  const { state } = useEngine();
  const pv = state.preverify;

  if (!pv) {
    return (
      <div className="glass p-2.5">
        <div className="text-[10px] font-bold text-white/70 uppercase tracking-wider mb-1.5">
          Pre-verify
        </div>
        <div className="text-[10px] text-white/40">데이터 없음 (시뮬레이션 단계 대기)</div>
      </div>
    );
  }

  const accuracyPct = (pv.sign_accuracy_recent * 100).toFixed(0);
  const rejectPct = (pv.auto_reject_rate * 100).toFixed(0);
  const accuracyColor = accuracyHue(pv.sign_accuracy_recent, pv.samples_recent);

  return (
    <div className="glass p-2.5">
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-[10px] font-bold text-white/70 uppercase tracking-wider">
          Pre-verify
        </div>
        <div
          className="text-[9px] px-1.5 py-0.5 rounded"
          style={{ background: `${accuracyColor}25`, color: accuracyColor }}
        >
          sign {accuracyPct}% (n={pv.samples_recent})
        </div>
      </div>

      <div className="grid grid-cols-3 gap-1.5 mb-2">
        <Metric label="MAE" value={pv.mae_recent.toFixed(5)} unit="" />
        <Metric label="auto-reject" value={`${rejectPct}%`} unit={`${pv.auto_rejected_total}/${pv.plans_total}`} />
        <Metric label="last reject" value={String(pv.autoRejectedThisRound)} unit="this round" />
      </div>

      <ThresholdRow thresholds={pv.current_thresholds} />

      <div className="text-[9px] text-white/45 mb-1 mt-2">Latest Plans (top 4)</div>
      <div className="space-y-1 max-h-[120px] overflow-y-auto pr-1">
        {pv.latestPlans.length === 0 ? (
          <div className="text-[10px] text-white/40">계획 없음</div>
        ) : (
          pv.latestPlans.slice(0, 4).map((plan) => (
            <PlanRow key={`${plan.step_id}-${plan.selected_action ?? 'rejected'}`} plan={plan} />
          ))
        )}
      </div>
    </div>
  );
}

function Metric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="rounded border border-white/10 px-1.5 py-1">
      <div className="text-[8px] uppercase tracking-wider text-white/40">{label}</div>
      <div className="font-mono text-[11px] text-white/85">{value}</div>
      {unit && <div className="text-[8px] text-white/40 truncate" title={unit}>{unit}</div>}
    </div>
  );
}

function ThresholdRow({ thresholds }: { thresholds: Record<string, number> }) {
  const keys = ['A', 'B', 'C'].filter((k) => k in thresholds);
  if (keys.length === 0) return null;

  return (
    <div className="flex items-center gap-1.5 text-[9px] py-1 border-y border-white/5">
      <span className="text-white/40 uppercase tracking-wider">threshold</span>
      {keys.map((level) => {
        const val = thresholds[level];
        const color = level === 'A' ? '#ef4444' : level === 'B' ? '#f59e0b' : '#10b981';
        return (
          <span key={level} className="flex items-center gap-0.5">
            <span className="font-bold" style={{ color }}>{level}</span>
            <span className="font-mono text-white/70">{formatScientific(val)}</span>
          </span>
        );
      })}
    </div>
  );
}

function PlanRow({ plan }: { plan: import('@/types').PreverifyPlan }) {
  const rejected = plan.rejected_reason !== null;
  const top = plan.top_simulations[0];
  return (
    <div
      className={`rounded border px-2 py-1 text-[10px] ${
        rejected ? 'border-red-500/40 bg-red-500/5' : 'border-white/10'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-white/75">{plan.step_id}</span>
        <span className={rejected ? 'text-red-400' : 'text-emerald-300'}>
          {rejected ? 'REJECT' : plan.selected_action || 'none'}
        </span>
      </div>
      {top && (
        <div className="font-mono text-[9px] text-white/55 truncate">
          score {top.score.toFixed(5)} · Δ {top.expected_delta.toFixed(5)} · p {(top.success_prob * 100).toFixed(0)}%
        </div>
      )}
      {rejected && (
        <div className="text-[9px] text-red-300/80 truncate" title={plan.rejected_reason ?? ''}>
          {plan.rejected_reason}
        </div>
      )}
    </div>
  );
}

function accuracyHue(acc: number, samples: number): string {
  if (samples < 5) return '#94a3b8';        // grey — not enough data
  if (acc >= 0.85) return '#10b981';        // green
  if (acc >= 0.6) return '#f59e0b';         // amber
  return '#ef4444';                          // red
}

function formatScientific(v: number): string {
  if (v === 0) return '0';
  const abs = Math.abs(v);
  if (abs >= 0.01) return v.toFixed(3);
  return v.toExponential(1);
}
