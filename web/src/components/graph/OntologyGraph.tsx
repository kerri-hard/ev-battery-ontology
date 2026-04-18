'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useEngine } from '@/context/EngineContext';
import type { L3TrendPoint } from './types';
import { AREAS } from './constants';
import { AreaColumn } from './AreaColumn';
import { CrossAreaEdges } from './CrossAreaEdges';
import { SummaryBar } from './SummaryBar';
import { L3InsightsPanel, L3RelationOverlay, L3TrendPanel } from './L3Panels';
import { useOntologyData } from './useOntologyData';
import { useStepPositions } from './useStepPositions';

function OntologyGraph({ className = '' }: { className?: string }) {
  const { state } = useEngine();
  const data = useOntologyData();
  const positions = useStepPositions(data.steps.length);

  const [flashSteps, setFlashSteps] = useState<Set<string>>(new Set());
  const prevIter = useRef(0);

  // L3 trend WS sync
  useEffect(() => {
    data.setL3TrendFromState((state.l3Trends || []) as unknown as L3TrendPoint[]);
  }, [state.l3Trends, data]);

  // Refetch on v3 iteration
  useEffect(() => {
    if (state.iteration !== prevIter.current && state.iteration > 0) {
      prevIter.current = state.iteration;
      data.refetch();
    }
  }, [state.iteration, data]);

  // Refetch on healing iteration
  useEffect(() => {
    if (state.healing.iteration > 0) data.refetch();
  }, [state.healing.iteration, data]);

  // Flash incident steps for 3s
  useEffect(() => {
    const ri = state.healing.recentIncidents;
    if (ri.length === 0) return;
    setFlashSteps(new Set(ri.map((i) => i.step_id)));
    const t = setTimeout(() => setFlashSteps(new Set()), 3000);
    return () => clearTimeout(t);
  }, [state.healing.recentIncidents]);

  if (data.steps.length === 0) {
    return (
      <div className={`glass flex items-center justify-center ${className}`}>
        <div className="text-center py-20">
          <div className="text-5xl mb-4 opacity-20">🏭</div>
          <div className="text-white/40 text-sm">엔진을 초기화하세요</div>
          <div className="text-white/20 text-xs mt-1">제어판에서 시작 버튼을 누르세요</div>
        </div>
      </div>
    );
  }

  const grouped = AREAS.map((area) => ({
    area,
    steps: data.steps.filter((s) => s.area === area.id),
  }));

  return (
    <div className={`glass flex flex-col overflow-hidden relative ${className}`}>
      <SummaryBar
        steps={data.steps}
        alarms={data.alarms}
        edges={data.edges}
        causalRules={data.causalRules}
        failureChains={data.failureChains}
      />

      <div
        ref={positions.graphBodyRef}
        className="flex-1 grid grid-cols-5 gap-2 p-2 min-h-0 overflow-hidden relative"
      >
        <CrossAreaEdges edges={data.edges} stepPositions={positions.stepPositions} />

        {grouped.map(({ area, steps: areaSteps }) => (
          <div key={area.id} className="min-h-0 overflow-hidden flex flex-col">
            <AreaColumn
              area={area}
              steps={areaSteps}
              alarms={data.alarms}
              flashSteps={flashSteps}
              registerStepRef={positions.registerStepRef}
            />
          </div>
        ))}

        <L3RelationOverlay edges={data.edges} nodes={data.nodes} />
        <L3TrendPanel history={data.l3Trend} />
        <L3InsightsPanel causalRules={data.causalRules} failureChains={data.failureChains} />
      </div>
    </div>
  );
}

export default React.memo(OntologyGraph);
