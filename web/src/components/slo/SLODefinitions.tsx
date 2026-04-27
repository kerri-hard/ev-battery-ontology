'use client';

import { useEffect, useRef } from 'react';
import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import type { SLODefinition, SLOGlobalSLI, SLOViolation } from '@/types';

/** SLI 카탈로그 — 정의·데이터 소스·SLO 목표·현재값을 한 카드에. selectedSloKey 강조. */
export default function SLODefinitions() {
  const { state } = useEngine();
  const slo = state.slo;
  const selectedKey = state.selectedSloKey;
  const selectedRowRef = useRef<HTMLDivElement>(null!);

  // selectedSloKey가 바뀌면 자동 scroll
  useEffect(() => {
    if (selectedRowRef.current) {
      selectedRowRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [selectedKey]);

  if (!slo) {
    return (
      <GlassCard>
        <div className="ds-caption">SLO 데이터 대기 중...</div>
      </GlassCard>
    );
  }

  const defs = slo.definitions;
  const g = slo.global;

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="ds-label">SLI / SLO 카탈로그</span>
        <span className="ds-caption">
          {g.total_incidents} incidents · {g.total_auto_recovered} auto
        </span>
      </div>
      <div className="space-y-1.5">
        {Object.entries(defs).map(([key, def]) => (
          <SLIRow
            key={key}
            sliKey={key}
            def={def}
            current={getCurrent(g, key)}
            violation={slo.violations.find((v) => v.sli === key)}
            selected={key === selectedKey}
            innerRef={key === selectedKey ? selectedRowRef : undefined}
          />
        ))}
      </div>
    </GlassCard>
  );
}

function SLIRow({
  sliKey,
  def,
  current,
  violation,
  selected = false,
  innerRef,
}: {
  sliKey: string;
  def: SLODefinition;
  current: number;
  violation?: SLOViolation;
  selected?: boolean;
  innerRef?: React.RefObject<HTMLDivElement>;
}) {
  const ok = !violation;
  const color = ok ? 'text-emerald-400' : 'text-rose-400';
  const bgBar = ok ? 'bg-emerald-500/30' : 'bg-rose-500/30';
  const fillColor = ok ? 'bg-emerald-400' : 'bg-rose-400';

  // ratio normalize for display bar (0-1)
  const fillPct =
    def.unit === 'ratio'
      ? Math.max(0, Math.min(1, current))
      : Math.max(0, Math.min(1, current / Math.max(def.target * 2, 0.001)));

  const fmt = (v: number) =>
    def.unit === 'ratio' ? `${(v * 100).toFixed(1)}%` : `${v.toFixed(3)}s`;

  return (
    <div
      ref={innerRef}
      className={`border-l-2 pl-2 py-1 transition rounded ${
        selected
          ? 'border-cyan-300 bg-cyan-500/10 ring-1 ring-cyan-400/40'
          : 'border-white/10 hover:border-white/30'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className={`text-[10px] font-bold ${color}`}>{def.name}</span>
            <span className="text-[8px] text-white/30 font-mono">{sliKey}</span>
            {selected && (
              <span className="text-[8px] px-1 rounded bg-cyan-500/30 text-cyan-100 font-mono">
                selected
              </span>
            )}
          </div>
          <div className="text-[9px] text-white/40 mt-0.5">{def.description}</div>
          <div className="text-[8px] text-white/25 font-mono mt-0.5">
            ← {def.data_source}
          </div>
        </div>
        <div className="text-right whitespace-nowrap">
          <div className={`text-xs font-mono font-bold ${color}`}>{fmt(current)}</div>
          <div className="text-[9px] text-white/40 font-mono">
            {def.higher_is_better ? '≥' : '≤'} {fmt(def.target)}
          </div>
        </div>
      </div>
      <div className={`h-1 mt-1 rounded-full ${bgBar} overflow-hidden`}>
        <div
          className={`h-full ${fillColor}`}
          style={{ width: `${(fillPct * 100).toFixed(0)}%` }}
        />
      </div>
      {violation && violation.affected_steps.length > 0 && (
        <div className="text-[9px] text-rose-300/80 mt-1 font-mono">
          영향 step: {violation.affected_steps.slice(0, 3).join(', ')}
          {violation.affected_steps.length > 3 ? ` +${violation.affected_steps.length - 3}` : ''}
        </div>
      )}
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
