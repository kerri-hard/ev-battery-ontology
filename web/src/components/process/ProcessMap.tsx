'use client';

import { useEffect, useRef, useState } from 'react';
import { useEngine } from '@/context/EngineContext';
import type { ProcessStep } from '@/types';
import AreaColumn from '@/components/process/AreaColumn';

const AREA_ORDER = ['PA-100', 'PA-200', 'PA-300', 'PA-400', 'PA-500'] as const;

const AREA_NAMES: Record<string, string> = {
  'PA-100': '셀 어셈블리',
  'PA-200': '전장 조립',
  'PA-300': '냉각 시스템',
  'PA-400': '인클로저',
  'PA-500': '최합조립/검사',
};

const AREA_COLORS: Record<string, string> = {
  'PA-100': '#FF6B35',
  'PA-200': '#00B4D8',
  'PA-300': '#06D6A0',
  'PA-400': '#E63946',
  'PA-500': '#FFD166',
};

export default function ProcessMap() {
  const { state } = useEngine();
  const prevYieldsRef = useRef<Map<string, number>>(new Map());
  const [changedSteps, setChangedSteps] = useState<Set<string>>(new Set());

  // Track yield changes
  useEffect(() => {
    if (state.steps.length === 0) return;

    const changed = new Set<string>();
    const prev = prevYieldsRef.current;

    for (const step of state.steps) {
      const prevYield = prev.get(step.id);
      if (prevYield !== undefined && prevYield !== step.yield) {
        changed.add(step.id);
      }
    }

    if (changed.size > 0) {
      setChangedSteps(changed);
      const timer = setTimeout(() => setChangedSteps(new Set()), 2500);
      return () => clearTimeout(timer);
    }

    // Update previous yields
    const next = new Map<string, number>();
    for (const step of state.steps) {
      next.set(step.id, step.yield);
    }
    prevYieldsRef.current = next;
  }, [state.steps]);

  // Also update prev yields after change detection
  useEffect(() => {
    const next = new Map<string, number>();
    for (const step of state.steps) {
      next.set(step.id, step.yield);
    }
    prevYieldsRef.current = next;
  }, [state.steps]);

  // Group steps by area
  const grouped = state.steps.reduce<Record<string, ProcessStep[]>>((acc, step) => {
    const area = step.area;
    if (!acc[area]) acc[area] = [];
    acc[area].push(step);
    return acc;
  }, {});

  if (state.steps.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-text-dim text-sm">
        엔진을 초기화하세요
      </div>
    );
  }

  return (
    <div className="flex gap-2 overflow-x-auto">
      {AREA_ORDER.map((areaId) => (
        <AreaColumn
          key={areaId}
          areaId={areaId}
          areaName={AREA_NAMES[areaId] || areaId}
          areaColor={AREA_COLORS[areaId] || '#888'}
          steps={grouped[areaId] || []}
          changedSteps={changedSteps}
        />
      ))}
    </div>
  );
}
