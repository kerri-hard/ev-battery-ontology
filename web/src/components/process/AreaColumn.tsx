'use client';

import type { ProcessStep } from '@/types';
import StepNode from '@/components/process/StepNode';

interface AreaColumnProps {
  areaId: string;
  areaName: string;
  areaColor: string;
  steps: ProcessStep[];
  changedSteps?: Set<string>;
}

export default function AreaColumn({ areaId, areaName, areaColor, steps, changedSteps }: AreaColumnProps) {
  const sorted = [...steps].sort((a, b) => a.id.localeCompare(b.id));

  return (
    <div className="flex-1 min-w-0 flex flex-col" data-area={areaId}>
      {/* Header */}
      <div
        className="rounded-t-lg text-center text-xs font-bold py-1.5 text-white"
        style={{ backgroundColor: `${areaColor}33` }}
      >
        {areaName}
      </div>

      {/* Steps */}
      <div className="flex flex-col gap-1 p-1">
        {sorted.map((step) => (
          <StepNode
            key={step.id}
            step={step}
            areaColor={areaColor}
            changed={changedSteps?.has(step.id)}
          />
        ))}
      </div>
    </div>
  );
}
