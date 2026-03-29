'use client';

import { useEngine } from '@/context/EngineContext';

export default function LearnResults() {
  const { state } = useEngine();
  const data = state.debate.learning;

  if (!data) {
    return <div className="text-text-dim text-xs py-2">학습 결과 대기 중...</div>;
  }

  const sortedAgents = [...(data.agents || [])].sort((a, b) => b.trust - a.trust);

  return (
    <div className="space-y-3">
      <h4 className="text-xs font-bold text-text-primary">학습 결과</h4>

      {/* Learning log */}
      <div className="space-y-1 max-h-[160px] overflow-y-auto">
        {data.learning_log.map((entry, idx) => {
          const deltaColor = entry.delta > 0 ? 'text-neon-green' : entry.delta < 0 ? 'text-neon-red' : 'text-text-dim';
          const arrow = entry.delta > 0 ? '\u25B2' : entry.delta < 0 ? '\u25BC' : '\u2014';

          return (
            <div
              key={idx}
              className="flex items-center gap-2 text-xs py-1 px-1.5 rounded bg-white/[0.02]"
            >
              <span className="text-text-primary w-20 truncate font-medium">{entry.agent}</span>
              <span className={`font-mono w-14 ${deltaColor}`}>
                {arrow} {entry.delta > 0 ? '+' : ''}{entry.delta.toFixed(3)}
              </span>
              <span className="font-mono text-cyan w-12">{entry.trust.toFixed(2)}</span>
              <span className="text-text-dim flex-1 truncate">{entry.reason}</span>
            </div>
          );
        })}
      </div>

      {/* Agent trust ranking */}
      {sortedAgents.length > 0 && (
        <div>
          <div className="text-[10px] text-text-dim mb-1 font-medium">에이전트 신뢰도 순위</div>
          <div className="space-y-0.5">
            {sortedAgents.map((agent, idx) => (
              <div key={agent.name} className="flex items-center gap-2 text-xs">
                <span className="font-mono text-text-dim w-4">{idx + 1}</span>
                <span className="text-text-primary w-20 truncate">{agent.name}</span>
                <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-neon-purple/60 rounded-full"
                    style={{ width: `${agent.trust * 100}%` }}
                  />
                </div>
                <span className="font-mono text-text-primary w-10 text-right">
                  {agent.trust.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
