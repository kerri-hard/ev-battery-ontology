'use client';

import { useState } from 'react';
import type { ProcessStep } from '@/types';
import StepTooltip from '@/components/process/StepTooltip';

interface StepNodeProps {
  step: ProcessStep;
  areaColor: string;
  changed?: boolean;
}

export default function StepNode({ step, areaColor, changed }: StepNodeProps) {
  const [hovered, setHovered] = useState(false);

  const yieldPct = step.yield * 100;
  const yieldColor =
    yieldPct >= 99.5 ? 'text-neon-green' : yieldPct >= 99 ? 'text-neon-yellow' : 'text-neon-red';

  return (
    <div
      className={`relative px-2 py-1.5 rounded-lg cursor-pointer transition-all
        bg-white/[0.04] backdrop-blur border border-white/[0.08]
        hover:bg-white/[0.07] hover:border-white/[0.15]
        ${changed ? 'animate-step-flash' : ''}`}
      style={{ borderLeftWidth: '2px', borderLeftColor: areaColor }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="flex items-center justify-between gap-1">
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-mono text-text-dim">{step.id}</div>
          <div className="text-xs text-text-primary truncate">{step.name}</div>
        </div>
        <div className={`font-mono text-xs whitespace-nowrap ${yieldColor}`}>
          {yieldPct.toFixed(1)}%
        </div>
      </div>

      {hovered && <StepTooltip step={step} />}
    </div>
  );
}
