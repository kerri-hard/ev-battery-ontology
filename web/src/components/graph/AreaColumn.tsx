'use client';

import type { StepData, AlarmData, Area } from './types';
import { StepCard } from './StepCard';

interface Props {
  area: Area;
  steps: StepData[];
  alarms: AlarmData[];
  flashSteps: Set<string>;
  selectedStepId?: string | null;
  registerStepRef?: (stepId: string) => (el: HTMLDivElement | null) => void;
}

export function AreaColumn({
  area,
  steps,
  alarms,
  flashSteps,
  selectedStepId,
  registerStepRef,
}: Props) {
  const areaAlarms = alarms.filter((a) => steps.some((s) => s.id === a.step_id));
  const avgYield = steps.length > 0 ? steps.reduce((s, st) => s + st.yield, 0) / steps.length : 0;

  return (
    <div className="flex flex-col min-w-0">
      <div
        className="rounded-t-lg px-3 py-2 mb-1"
        style={{
          background: `linear-gradient(135deg, ${area.color}15, ${area.color}08)`,
          borderBottom: `2px solid ${area.color}40`,
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="text-sm">{area.icon}</span>
            <span className="text-xs font-bold" style={{ color: area.color }}>
              {area.name}
            </span>
          </div>
          {areaAlarms.length > 0 && (
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 animate-pulse">
              {areaAlarms.length} 알람
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-1">
          <div className="flex-1 h-1 rounded-full" style={{ background: `${area.color}15` }}>
            <div
              className="h-full rounded-full"
              style={{ width: `${avgYield * 100}%`, background: area.color, opacity: 0.6 }}
            />
          </div>
          <span className="text-[9px] font-mono" style={{ color: area.color }}>
            {(avgYield * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-1 flex-1 overflow-y-auto pr-0.5">
        {steps
          .sort((a, b) => a.id.localeCompare(b.id))
          .map((step) => (
            <StepCard
              key={step.id}
              step={step}
              areaColor={area.color}
              alarm={alarms.find((a) => a.step_id === step.id)}
              isFlash={flashSteps.has(step.id)}
              isSelected={selectedStepId === step.id}
              innerRef={registerStepRef ? registerStepRef(step.id) : undefined}
            />
          ))}
      </div>
    </div>
  );
}
