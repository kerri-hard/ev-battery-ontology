'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import ControlPanel from '@/components/controls/ControlPanel';
import SidebarMetrics from '@/components/metrics/SidebarMetrics';
import AgentList from '@/components/agents/AgentList';

export default function Sidebar() {
  // Ensure we are within EngineProvider
  useEngine();

  return (
    <aside className="w-[240px] h-full overflow-y-auto border-r border-white/5 p-2.5 space-y-2.5 flex-shrink-0"
      style={{ background: 'rgba(12, 12, 29, 0.5)' }}>
      <GlassCard>
        <ControlPanel />
      </GlassCard>

      <GlassCard>
        <SidebarMetrics />
      </GlassCard>

      <GlassCard>
        <AgentList />
      </GlassCard>
    </aside>
  );
}
