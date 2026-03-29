'use client';

import type { ProcessStep } from '@/types';

interface StepTooltipProps {
  step: ProcessStep;
}

export default function StepTooltip({ step }: StepTooltipProps) {
  const yieldPct = step.yield * 100;
  const yieldColor =
    yieldPct >= 99.5 ? 'text-neon-green' : yieldPct >= 99 ? 'text-neon-yellow' : 'text-neon-red';

  return (
    <div className="absolute left-full top-0 ml-2 z-50 min-w-[180px] p-2.5 rounded-lg text-xs
      bg-bg3/90 backdrop-blur-xl border border-white/10 shadow-lg shadow-black/40 pointer-events-none">
      <div className="font-bold text-text-primary mb-1.5">{step.name}</div>
      <div className="space-y-1 text-text-dim">
        <div className="flex justify-between">
          <span>수율:</span>
          <span className={`font-mono ${yieldColor}`}>{yieldPct.toFixed(2)}%</span>
        </div>
        <div className="flex justify-between">
          <span>자동화:</span>
          <span className="text-text-primary">{step.auto}</span>
        </div>
        <div className="flex justify-between">
          <span>장비:</span>
          <span className="text-text-primary">{step.equipment}</span>
        </div>
        <div className="flex justify-between">
          <span>사이클:</span>
          <span className="font-mono text-text-primary">{step.cycle}초</span>
        </div>
        <div className="flex justify-between">
          <span>OEE:</span>
          <span className="font-mono text-text-primary">{(step.oee * 100).toFixed(1)}%</span>
        </div>
        <div className="flex justify-between">
          <span>안전:</span>
          <span className="text-text-primary">{step.safety}</span>
        </div>
      </div>
    </div>
  );
}
