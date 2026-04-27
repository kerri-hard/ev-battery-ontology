'use client';

import { useEffect, useRef } from 'react';
import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import SparklineChart from '@/components/charts/SparklineChart';
import type { SLODefinition, SLOGlobalSLI } from '@/types';

const HISTORY_LEN = 30;

type SLOHistory = {
  ts: number[];
  series: Record<string, number[]>;
};

/** SLI 시계열 + error budget burn rate alert */
export default function SLOSparklines() {
  const { state } = useEngine();
  const slo = state.slo;
  const histRef = useRef<SLOHistory>({ ts: [], series: {} });

  // 매 sim tick마다 SLI 값 누적
  useEffect(() => {
    if (!slo?.global) return;
    const g = slo.global;
    const hist = histRef.current;
    hist.ts.push(Date.now());
    if (hist.ts.length > HISTORY_LEN) hist.ts.shift();
    const fields: (keyof SLOGlobalSLI)[] = [
      'auto_recovery_rate',
      'p95_recovery_latency',
      'yield_compliance',
      'hitl_rate',
      'repeat_rate',
    ];
    fields.forEach((f) => {
      if (!hist.series[f]) hist.series[f] = [];
      hist.series[f].push(Number(g[f] ?? 0));
      if (hist.series[f].length > HISTORY_LEN) hist.series[f].shift();
    });
  }, [slo?.global]);

  if (!slo) {
    return (
      <GlassCard>
        <div className="text-[10px] text-white/40">SLO 시계열 대기 중...</div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold text-white/60 uppercase tracking-wider">
          SLI 시계열 (최근 30 tick)
        </span>
        <span className="text-[9px] text-white/40 font-mono">
          {histRef.current.ts.length} samples
        </span>
      </div>
      <div className="space-y-2">
        {Object.entries(slo.definitions).map(([key, def]) => (
          <SparklineRow
            key={key}
            sliKey={key}
            def={def}
            data={histRef.current.series[key] ?? []}
            current={getCurrent(slo.global, key)}
            violated={!!slo.violations.find((v) => v.sli === key)}
          />
        ))}
      </div>
    </GlassCard>
  );
}

function SparklineRow({
  sliKey,
  def,
  data,
  current,
  violated,
}: {
  sliKey: string;
  def: SLODefinition;
  data: number[];
  current: number;
  violated: boolean;
}) {
  const fmt = (v: number) =>
    def.unit === 'ratio' ? `${(v * 100).toFixed(1)}%` : `${v.toFixed(3)}s`;
  const color = violated ? '#fb7185' : '#34d399';

  // burn rate: 최근 5 샘플의 변화율 (지표 악화 방향)
  const recent = data.slice(-5);
  let burnRate = 0;
  if (recent.length >= 2) {
    const delta = recent[recent.length - 1] - recent[0];
    burnRate = def.higher_is_better ? -delta : delta;
  }
  const burning = burnRate > 0 && violated;

  return (
    <div className="grid grid-cols-[1fr_180px_70px] gap-2 items-center">
      <div className="min-w-0">
        <div className="flex items-center gap-1">
          <span className={`text-[10px] font-bold ${violated ? 'text-rose-300' : 'text-white/80'}`}>
            {def.name}
          </span>
          {burning && (
            <span className="text-[8px] px-1 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono animate-pulse">
              BURN
            </span>
          )}
        </div>
        <div className="text-[8px] text-white/40 font-mono">
          {sliKey} · {def.higher_is_better ? '≥' : '≤'} {fmt(def.target)}
        </div>
      </div>
      <div className="min-h-[24px]">
        {data.length > 1 ? (
          <SparklineChart data={data} color={color} width={170} height={24} />
        ) : (
          <div className="text-[8px] text-white/30 font-mono">데이터 누적 중...</div>
        )}
      </div>
      <div className="text-right">
        <div className={`text-[11px] font-mono font-bold ${violated ? 'text-rose-300' : 'text-emerald-300'}`}>
          {fmt(current)}
        </div>
        {burnRate !== 0 && (
          <div
            className={`text-[8px] font-mono ${
              burnRate > 0 ? 'text-rose-400' : 'text-emerald-400'
            }`}
          >
            {burnRate > 0 ? '↑' : '↓'} {Math.abs(burnRate * 100).toFixed(2)}%
          </div>
        )}
      </div>
    </div>
  );
}

function getCurrent(g: SLOGlobalSLI, key: string): number {
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
