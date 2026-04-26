'use client';

import { useState } from 'react';
import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import type { MicroserviceSLI, AreaSLI } from '@/types';

const AREA_NAMES: Record<string, string> = {
  'PA-100': '셀 어셈블리',
  'PA-200': '전장 조립',
  'PA-300': '냉각 시스템',
  'PA-400': '인클로저',
  'PA-500': '최합조립/검사',
};

/** ProcessStep을 microservice로 보고 step별 SLI 바 + error budget. */
export default function MicroservicePanel() {
  const { state } = useEngine();
  const slo = state.slo;
  const [filter, setFilter] = useState<string>('all');

  if (!slo || slo.per_step.length === 0) {
    return (
      <GlassCard>
        <div className="text-[10px] text-white/40">아직 incident 데이터 없음 — sim 실행 필요</div>
      </GlassCard>
    );
  }

  const filtered =
    filter === 'all'
      ? slo.per_step
      : slo.per_step.filter((s) => s.area_id === filter);

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold text-white/60 uppercase tracking-wider">
          Microservice SLI ({filtered.length} step)
        </span>
        <div className="flex items-center gap-1">
          <FilterBtn active={filter === 'all'} onClick={() => setFilter('all')}>
            전체
          </FilterBtn>
          {slo.per_area.map((a) => (
            <FilterBtn
              key={a.area_id}
              active={filter === a.area_id}
              onClick={() => setFilter(a.area_id)}
            >
              {a.area_id}
            </FilterBtn>
          ))}
        </div>
      </div>

      {/* Area roll-up */}
      <div className="grid grid-cols-5 gap-1.5 mb-3">
        {slo.per_area.map((a) => (
          <AreaCard key={a.area_id} area={a} />
        ))}
      </div>

      {/* Per-step grid */}
      <div className="space-y-1 max-h-[420px] overflow-y-auto">
        {filtered.map((s) => (
          <StepRow key={s.step_id} step={s} />
        ))}
      </div>
    </GlassCard>
  );
}

function FilterBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-1.5 py-0.5 text-[9px] font-mono rounded ${
        active
          ? 'bg-cyan-500/30 text-cyan-200 border border-cyan-400/40'
          : 'bg-white/5 text-white/40 hover:bg-white/10 border border-white/10'
      }`}
    >
      {children}
    </button>
  );
}

function AreaCard({ area }: { area: AreaSLI }) {
  const arOk = area.auto_recovery_rate >= 0.95;
  const yieldOk = area.yield_compliance_rate >= 0.95;
  const hitlOk = area.hitl_rate <= 0.05;
  const allOk = arOk && yieldOk && hitlOk;

  return (
    <div
      className={`p-1.5 rounded border ${
        allOk ? 'border-emerald-400/30 bg-emerald-950/30' : 'border-amber-400/30 bg-amber-950/30'
      }`}
    >
      <div className="text-[9px] font-bold text-white/80 truncate">
        {AREA_NAMES[area.area_id] || area.area_id}
      </div>
      <div className="text-[8px] text-white/40 font-mono">
        {area.area_id} · {area.step_count} steps
      </div>
      <div className="mt-1 grid grid-cols-3 gap-0.5">
        <SLIBadge label="AR" value={area.auto_recovery_rate} ok={arOk} />
        <SLIBadge label="Y" value={area.yield_compliance_rate} ok={yieldOk} />
        <SLIBadge label="H" value={area.hitl_rate} ok={hitlOk} invert />
      </div>
    </div>
  );
}

function SLIBadge({
  label,
  value,
  ok,
  invert = false,
}: {
  label: string;
  value: number;
  ok: boolean;
  invert?: boolean;
}) {
  void invert;
  return (
    <div
      className={`text-center py-0.5 rounded text-[8px] font-mono ${
        ok ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
      }`}
      title={label}
    >
      {(value * 100).toFixed(0)}%
    </div>
  );
}

function StepRow({ step }: { step: MicroserviceSLI }) {
  const arOk = step.auto_recovery_rate >= 0.95;
  const yieldOk = step.yield_meets_slo;
  const ok = arOk && yieldOk;

  return (
    <div className="grid grid-cols-[80px_1fr_70px_70px_70px_70px] gap-1.5 items-center px-1.5 py-1 hover:bg-white/5 rounded text-[9px]">
      <div className="font-mono">
        <div className={`font-bold ${ok ? 'text-cyan-300' : 'text-amber-300'}`}>
          {step.step_id}
        </div>
        <div className="text-white/30 text-[8px]">{step.area_id}</div>
      </div>
      <div className="space-y-0.5">
        <div className="flex items-center gap-1">
          <span className="text-white/40 text-[8px] w-8">AR</span>
          <Bar value={step.auto_recovery_rate} ok={arOk} />
          <span className={`text-[8px] font-mono w-9 text-right ${arOk ? 'text-emerald-400' : 'text-rose-400'}`}>
            {(step.auto_recovery_rate * 100).toFixed(0)}%
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-white/40 text-[8px] w-8">YIELD</span>
          <Bar value={step.current_yield} ok={yieldOk} threshold={0.99} />
          <span className={`text-[8px] font-mono w-9 text-right ${yieldOk ? 'text-emerald-400' : 'text-rose-400'}`}>
            {(step.current_yield * 100).toFixed(1)}%
          </span>
        </div>
      </div>
      <div className="text-center text-white/60 font-mono text-[8px]">
        n={step.incident_count}
      </div>
      <div className="text-center font-mono text-[8px] text-white/60">
        p50 {step.p50_recovery_sec.toFixed(3)}s
      </div>
      <div className="text-center font-mono text-[8px] text-white/60">
        p95 {step.p95_recovery_sec.toFixed(3)}s
      </div>
      <div className="text-right">
        <BudgetGauge remaining={step.error_budget_remaining} />
      </div>
    </div>
  );
}

function Bar({
  value,
  ok,
  threshold = 0.95,
}: {
  value: number;
  ok: boolean;
  threshold?: number;
}) {
  const pct = Math.max(0, Math.min(1, value));
  return (
    <div className="flex-1 h-1.5 bg-white/10 rounded relative overflow-hidden">
      <div
        className={`absolute h-full ${ok ? 'bg-emerald-400' : 'bg-rose-400'}`}
        style={{ width: `${(pct * 100).toFixed(0)}%` }}
      />
      <div
        className="absolute top-0 bottom-0 w-px bg-white/40"
        style={{ left: `${(threshold * 100).toFixed(0)}%` }}
      />
    </div>
  );
}

function BudgetGauge({ remaining }: { remaining: number }) {
  const pct = Math.max(0, Math.min(1, remaining));
  const color =
    pct > 0.5 ? 'text-emerald-300' : pct > 0.2 ? 'text-amber-300' : 'text-rose-400';
  return (
    <div className="text-[8px] font-mono">
      <div className={color}>{(pct * 100).toFixed(0)}%</div>
      <div className="text-white/30 text-[7px]">budget</div>
    </div>
  );
}
