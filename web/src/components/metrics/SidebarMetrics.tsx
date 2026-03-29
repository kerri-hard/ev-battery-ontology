'use client';

import { useEngine } from '@/context/EngineContext';
import type { Metrics } from '@/types';

interface MetricRow {
  label: string;
  value: (m: Metrics) => string;
  rawValue: (m: Metrics) => number;
  higherIsBetter: boolean;
}

const rows: MetricRow[] = [
  {
    label: '반복',
    value: () => '',
    rawValue: () => 0,
    higherIsBetter: true,
  },
  {
    label: '노드',
    value: (m) => String(m.total_nodes),
    rawValue: (m) => m.total_nodes,
    higherIsBetter: true,
  },
  {
    label: '엣지',
    value: (m) => String(m.total_edges),
    rawValue: (m) => m.total_edges,
    higherIsBetter: true,
  },
  {
    label: '라인 수율(%)',
    value: (m) => (m.line_yield * 100).toFixed(1),
    rawValue: (m) => m.line_yield,
    higherIsBetter: true,
  },
  {
    label: '완성도',
    value: (m) => m.completeness_score.toFixed(1),
    rawValue: (m) => m.completeness_score,
    higherIsBetter: true,
  },
  {
    label: 'OEE',
    value: (m) => m.avg_oee.toFixed(3),
    rawValue: (m) => m.avg_oee,
    higherIsBetter: true,
  },
  {
    label: '시그마',
    value: (m) => m.avg_sigma.toFixed(2),
    rawValue: (m) => m.avg_sigma,
    higherIsBetter: true,
  },
];

function DeltaArrow({ curr, prev, higherIsBetter }: { curr: number; prev: number; higherIsBetter: boolean }) {
  if (curr === prev) return null;
  const improved = higherIsBetter ? curr > prev : curr < prev;
  return (
    <span className={`text-[10px] ml-1 ${improved ? 'text-neon-green' : 'text-neon-red'}`}>
      {improved ? '▲' : '▼'}
    </span>
  );
}

export default function SidebarMetrics() {
  const { state } = useEngine();
  const { metrics, prevMetrics, iteration } = state;

  return (
    <div>
      <h3 className="text-xs text-text-dim mb-2 font-medium">주요 지표</h3>
      <div className="space-y-1.5">
        {rows.map((row) => {
          // Special case for iteration row
          if (row.label === '반복') {
            return (
              <div key={row.label} className="flex items-center justify-between">
                <span className="text-text-dim text-xs">{row.label}</span>
                <span className="text-white font-mono text-sm">
                  {iteration}/{state.maxIterations}
                </span>
              </div>
            );
          }

          return (
            <div key={row.label} className="flex items-center justify-between">
              <span className="text-text-dim text-xs">{row.label}</span>
              <div className="flex items-center">
                <span className="text-white font-mono text-sm">
                  {metrics ? row.value(metrics) : '—'}
                </span>
                {metrics && prevMetrics && (
                  <DeltaArrow
                    curr={row.rawValue(metrics)}
                    prev={row.rawValue(prevMetrics)}
                    higherIsBetter={row.higherIsBetter}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* v4 Healing Stats */}
      {(state.healing.incidents > 0 || state.healing.running) && (
        <div className="mt-3 pt-3 border-t border-white/5">
          <h4 className="text-[10px] text-neon-purple uppercase tracking-wider mb-1.5">자율 복구</h4>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-text-dim text-xs">장애 감지</span>
              <span className="text-neon-red font-mono text-sm">{state.healing.incidents}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-dim text-xs">자동 복구</span>
              <span className="text-neon-green font-mono text-sm">{state.healing.autoRecovered}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-dim text-xs">복구율</span>
              <span className="text-white font-mono text-sm">
                {state.healing.incidents > 0
                  ? `${((state.healing.autoRecovered / state.healing.incidents) * 100).toFixed(0)}%`
                  : '—'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
