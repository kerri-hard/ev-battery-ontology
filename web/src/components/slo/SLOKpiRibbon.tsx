'use client';

import { useEngine } from '@/context/EngineContext';
import type { SLOGlobalSLI, SLODefinition } from '@/types';

/** 상단 KPI 리본 — 5 SLI 칩 + 글로벌 error budget gauge */
export default function SLOKpiRibbon() {
  const { state } = useEngine();
  const slo = state.slo;
  const g = slo?.global;
  const defs = slo?.definitions ?? {};
  const violationCount = slo?.violations.length ?? 0;

  // 글로벌 error budget = SLO 미달 SLI 수 / 전체 SLI 수 (낮을수록 좋음)
  const totalSlis = Object.keys(defs).length || 1;
  const budgetPct = Math.max(0, Math.min(1, 1 - violationCount / totalSlis));

  return (
    <div className="glass px-3 py-2 flex items-center gap-2 overflow-x-auto">
      <span className="text-[9px] text-white/40 uppercase tracking-wider whitespace-nowrap">
        SLO 상태
      </span>
      <div className="flex items-center gap-1.5 flex-1">
        {Object.entries(defs).map(([key, def]) => (
          <SLIChip
            key={key}
            sliKey={key}
            def={def}
            current={getCurrent(g, key)}
            violated={!!slo?.violations.find((v) => v.sli === key)}
          />
        ))}
      </div>
      <BudgetGauge pct={budgetPct} violations={violationCount} totalSlis={totalSlis} />
      <div className="text-[9px] text-white/40 font-mono whitespace-nowrap">
        {g?.total_incidents ?? 0} inc · {g?.total_auto_recovered ?? 0} auto
      </div>
    </div>
  );
}

function SLIChip({
  sliKey,
  def,
  current,
  violated,
}: {
  sliKey: string;
  def: SLODefinition;
  current: number;
  violated: boolean;
}) {
  const fmt = (v: number) =>
    def.unit === 'ratio' ? `${(v * 100).toFixed(1)}%` : `${v.toFixed(3)}s`;
  const bg = violated
    ? 'bg-rose-500/15 border-rose-400/40 text-rose-200'
    : 'bg-emerald-500/15 border-emerald-400/40 text-emerald-200';
  return (
    <div
      className={`px-2 py-1 rounded border ${bg} flex items-center gap-1.5 whitespace-nowrap`}
      title={`${def.name} — ${def.description}`}
    >
      <div className="text-[8px] uppercase tracking-wider text-white/50">
        {sliKey.replace(/_/g, ' ').slice(0, 16)}
      </div>
      <div className="text-[10px] font-mono font-bold">{fmt(current)}</div>
      <div className="text-[8px] text-white/40 font-mono">
        / {def.higher_is_better ? '≥' : '≤'}
        {fmt(def.target)}
      </div>
    </div>
  );
}

function BudgetGauge({
  pct,
  violations,
  totalSlis,
}: {
  pct: number;
  violations: number;
  totalSlis: number;
}) {
  const color =
    pct >= 0.8 ? 'text-emerald-300' : pct >= 0.5 ? 'text-amber-300' : 'text-rose-400';
  const fillColor =
    pct >= 0.8 ? 'bg-emerald-400' : pct >= 0.5 ? 'bg-amber-400' : 'bg-rose-400';
  return (
    <div className="border-l border-white/10 pl-3 flex items-center gap-2 whitespace-nowrap">
      <div>
        <div className={`text-xs font-mono font-bold ${color}`}>
          {(pct * 100).toFixed(0)}%
        </div>
        <div className="text-[8px] text-white/40 uppercase tracking-wider">
          error budget
        </div>
      </div>
      <div className="w-20 h-1.5 bg-white/10 rounded overflow-hidden">
        <div className={`h-full ${fillColor}`} style={{ width: `${pct * 100}%` }} />
      </div>
      {violations > 0 && (
        <span className="text-[8px] px-1 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono">
          {violations}/{totalSlis} 위반
        </span>
      )}
    </div>
  );
}

function getCurrent(g: SLOGlobalSLI | undefined, key: string): number {
  if (!g) return 0;
  switch (key) {
    case 'auto_recovery_rate':
      return g.auto_recovery_rate;
    case 'p95_recovery_latency':
      return g.p95_recovery_latency;
    case 'yield_compliance':
      return g.yield_compliance;
    case 'hitl_rate':
      return g.hitl_rate;
    case 'repeat_rate':
      return g.repeat_rate;
    default:
      return 0;
  }
}
