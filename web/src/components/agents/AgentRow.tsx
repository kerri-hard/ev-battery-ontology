'use client';

import type { Agent } from '@/types';
import TrustBar from '@/components/agents/TrustBar';

interface AgentRowProps {
  agent: Agent;
  color: string;
  isActive?: boolean;
}

export default function AgentRow({ agent, color, isActive = false }: AgentRowProps) {
  return (
    <div
      className={`flex items-center gap-2 py-1 px-1 rounded transition-colors ${
        isActive ? 'bg-white/5' : ''
      }`}
      style={isActive ? { borderLeft: `2px solid ${color}`, boxShadow: `inset 4px 0 8px -4px ${color}40` } : { borderLeft: '2px solid transparent' }}
    >
      {/* Color dot */}
      <span
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{ backgroundColor: color }}
      />

      {/* Name */}
      <span className="text-xs text-text-primary truncate flex-1" title={agent.name}>
        {agent.name}
      </span>

      {/* Trust bar + value */}
      <TrustBar trust={agent.trust ?? 1.0} />
      <span className="text-xs font-mono text-text-dim w-8 text-right">
        {(agent.trust ?? 1.0).toFixed(2)}
      </span>
    </div>
  );
}
