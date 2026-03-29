'use client';

import { useEngine } from '@/context/EngineContext';

const KEY_DELTAS: { key: string; label: string }[] = [
  { key: 'total_nodes', label: '노드 수' },
  { key: 'total_edges', label: '엣지 수' },
  { key: 'line_yield', label: '라인 수율' },
  { key: 'completeness_score', label: '완성도' },
  { key: 'spec_coverage', label: '스펙 커버리지' },
  { key: 'defect_coverage', label: '결함 커버리지' },
];

export default function EvalResults() {
  const { state } = useEngine();
  const data = state.debate.evaluation;

  if (!data) {
    return <div className="text-text-dim text-xs py-2">평가 결과 대기 중...</div>;
  }

  const evalData = data.evaluation;
  const scoreDelta = evalData.score_delta;
  const deltaColor = scoreDelta > 0 ? 'text-neon-green' : scoreDelta < 0 ? 'text-neon-red' : 'text-text-dim';
  const deltaSign = scoreDelta > 0 ? '+' : '';
  const improvementPct = evalData.improvement_rate * 100;

  return (
    <div className="space-y-3">
      <h4 className="text-xs font-bold text-text-primary">평가 결과</h4>

      {/* Score delta + improvement rate */}
      <div className="flex items-center gap-4">
        <div className="text-center">
          <div className={`text-2xl font-bold font-mono ${deltaColor}`}>
            {deltaSign}{scoreDelta.toFixed(3)}
          </div>
          <div className="text-[10px] text-text-dim">점수 변화</div>
        </div>
        <div className="flex-1">
          <div className="flex justify-between text-[10px] text-text-dim mb-0.5">
            <span>개선율</span>
            <span className="font-mono">{improvementPct.toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-cyan/60 rounded-full transition-all"
              style={{ width: `${Math.min(improvementPct, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Key deltas grid */}
      <div className="grid grid-cols-2 gap-1.5">
        {KEY_DELTAS.map(({ key, label }) => {
          const delta = evalData.deltas[key];
          if (!delta) return null;

          const chgColor = delta.change > 0 ? 'text-neon-green' : delta.change < 0 ? 'text-neon-red' : 'text-text-dim';
          const chgSign = delta.change > 0 ? '+' : '';

          return (
            <div
              key={key}
              className="rounded-lg bg-white/[0.03] border border-white/[0.05] p-1.5"
            >
              <div className="text-[10px] text-text-dim mb-0.5">{label}</div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-text-dim">
                  {typeof delta.prev === 'number' ? delta.prev.toFixed(3) : delta.prev}
                  {' \u2192 '}
                  {typeof delta.curr === 'number' ? delta.curr.toFixed(3) : delta.curr}
                </span>
                <span className={`text-xs font-mono font-bold ${chgColor}`}>
                  {chgSign}{typeof delta.change === 'number' ? delta.change.toFixed(3) : delta.change}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
