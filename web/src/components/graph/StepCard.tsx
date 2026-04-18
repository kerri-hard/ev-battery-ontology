'use client';

import { useState } from 'react';
import type { StepData, AlarmData } from './types';
import { yieldColor, autoLabel } from './constants';

interface Props {
  step: StepData;
  areaColor: string;
  alarm?: AlarmData;
  isFlash: boolean;
  innerRef?: (el: HTMLDivElement | null) => void;
}

export function StepCard({ step, areaColor, alarm, isFlash, innerRef }: Props) {
  const [hovered, setHovered] = useState(false);
  const yc = yieldColor(step.yield);
  const auto = autoLabel(step.auto);

  return (
    <div
      ref={innerRef}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`relative rounded-lg transition-all duration-200 cursor-default
        ${isFlash ? 'animate-step-flash' : ''}
        ${alarm ? 'ring-1 ring-red-500/60' : ''}
      `}
      style={{
        background: hovered ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
        borderLeft: `3px solid ${areaColor}`,
        padding: '8px 10px',
      }}
    >
      {alarm && (
        <div
          className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-red-500 animate-pulse"
          title={alarm.message}
        />
      )}

      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-mono text-white/40">{step.id}</span>
        <span
          className="text-[8px] font-bold px-1.5 py-0.5 rounded"
          style={{ color: auto.color, background: `${auto.color}15`, border: `1px solid ${auto.color}25` }}
        >
          {auto.text}
        </span>
      </div>

      <div className="text-xs font-medium text-white/90 mb-1.5 truncate" title={step.name}>
        {step.name}
      </div>

      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${step.yield * 100}%`, background: yc }}
          />
        </div>
        <span className="text-[10px] font-mono font-bold" style={{ color: yc }}>
          {(step.yield * 100).toFixed(1)}%
        </span>
      </div>

      {hovered && (
        <div className="mt-2 pt-2 border-t border-white/5 grid grid-cols-2 gap-x-3 gap-y-1">
          <div className="text-[9px] text-white/30">장비</div>
          <div className="text-[9px] text-white/70 truncate">{step.equipment}</div>
          <div className="text-[9px] text-white/30">OEE</div>
          <div className="text-[9px] text-white/70">{(step.oee * 100).toFixed(1)}%</div>
          <div className="text-[9px] text-white/30">사이클</div>
          <div className="text-[9px] text-white/70">{step.cycle}초</div>
          <div className="text-[9px] text-white/30">안전등급</div>
          <div
            className="text-[9px] font-bold"
            style={{
              color: step.safety === 'A' ? '#ef4444' : step.safety === 'B' ? '#f59e0b' : '#10b981',
            }}
          >
            {step.safety}
          </div>
        </div>
      )}
    </div>
  );
}
