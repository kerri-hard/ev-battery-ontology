'use client';

import { useEngine } from '@/context/EngineContext';

export default function ProposalList() {
  const { state } = useEngine();
  const data = state.debate.proposals;

  if (!data) {
    return <div className="text-text-dim text-xs py-2">대기 중...</div>;
  }

  const agentEntries = Object.entries(data.by_agent);
  const maxAgent = Math.max(...agentEntries.map(([, v]) => v), 1);
  const typeEntries = Object.entries(data.by_type);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold text-text-primary">제안 목록</h4>
        <span className="text-xs font-mono text-cyan">{data.total}개</span>
      </div>

      {/* Agent bar chart */}
      <div className="space-y-1">
        {agentEntries.map(([agent, count]) => (
          <div key={agent} className="flex items-center gap-2 text-xs">
            <span className="w-[80px] truncate text-text-dim">{agent}</span>
            <div className="flex-1 h-3 bg-white/5 rounded overflow-hidden">
              <div
                className="h-full bg-cyan/60 rounded transition-all"
                style={{ width: `${(count / maxAgent) * 100}%` }}
              />
            </div>
            <span className="font-mono text-text-primary w-6 text-right">{count}</span>
          </div>
        ))}
      </div>

      {/* Type badges */}
      <div className="flex flex-wrap gap-1.5">
        {typeEntries.map(([type, count]) => (
          <span
            key={type}
            className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-text-dim"
          >
            {type}
            <span className="font-mono text-text-primary">{count}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
