'use client';

import { useEngine } from '@/context/EngineContext';
import AgentRow from '@/components/agents/AgentRow';

const AGENT_COLORS = ['#00d2ff', '#06d6a0', '#f5576c', '#ffd166', '#a855f7', '#FF6B35'];

export default function AgentList() {
  const { state } = useEngine();

  return (
    <div>
      <h3 className="text-xs text-text-dim mb-2 font-medium">에이전트</h3>
      <div className="space-y-0.5">
        {state.agents.map((agent, i) => (
          <AgentRow
            key={agent.name}
            agent={agent}
            color={AGENT_COLORS[i % AGENT_COLORS.length]}
            isActive={false}
          />
        ))}
        {state.agents.length === 0 && (
          <p className="text-xs text-text-dim italic">에이전트 없음</p>
        )}
      </div>
    </div>
  );
}
