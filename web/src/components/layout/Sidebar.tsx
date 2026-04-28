'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import ControlPanel from '@/components/controls/ControlPanel';
import SidebarMetrics from '@/components/metrics/SidebarMetrics';
import AgentList from '@/components/agents/AgentList';
import ScenarioPicker from '@/components/scenarios/ScenarioPicker';
import type { ViewKey } from '@/types';

const NAV_ITEMS: { key: ViewKey; label: string; icon: string; desc: string }[] = [
  { key: 'overview', label: 'Overview', icon: '🏠', desc: '시스템 한눈' },
  { key: 'healing', label: 'Healing', icon: '🛡', desc: 'Detect → Diagnose → Heal' },
  { key: 'slo', label: 'SLO', icon: '📊', desc: 'SLI / per-step / 위반' },
  { key: 'learning', label: 'Learning', icon: '🧠', desc: '학습 / 진화 / 패턴' },
  { key: 'console', label: 'Console', icon: '🖥', desc: 'Raw 로그 / HITL' },
  { key: 'settings', label: 'Settings', icon: '⚙', desc: 'HITL 정책 / 단축키' },
];

export default function Sidebar() {
  const { state, setView } = useEngine();
  const current = state.currentView ?? 'healing';

  return (
    <aside
      className="w-[180px] md:w-[200px] lg:w-[240px] h-full overflow-y-auto border-r border-white/5 p-2 md:p-2.5 space-y-2 md:space-y-2.5 flex-shrink-0"
      style={{ background: 'rgba(12, 12, 29, 0.5)' }}
    >
      {/* 페이지 네비게이션 */}
      <nav className="space-y-1">
        <div className="text-[9px] font-bold text-white/40 uppercase tracking-wider px-1 mb-1">
          페이지
        </div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            onClick={() => setView(item.key)}
            aria-label={`${item.label} 페이지로 이동 (단축키 g ${item.key[0]})`}
            aria-current={current === item.key ? 'page' : undefined}
            className={`w-full text-left px-2.5 py-2 rounded-lg flex items-start gap-2 transition border focus:outline-none focus:ring-2 focus:ring-cyan-400/60 ${
              current === item.key
                ? 'bg-cyan-500/15 border-cyan-400/40 text-cyan-100'
                : 'bg-transparent border-white/5 text-white/60 hover:bg-white/5 hover:text-white/90 hover:border-white/15'
            }`}
          >
            <span className="text-base leading-none mt-0.5">{item.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="text-[11px] font-bold">{item.label}</div>
              <div className="text-[9px] opacity-60 truncate">{item.desc}</div>
            </div>
            <kbd className="text-[8px] font-mono opacity-40 px-1 mt-0.5">g{item.key[0]}</kbd>
          </button>
        ))}
      </nav>

      <div className="h-px bg-white/5 my-2" />

      <GlassCard>
        <ControlPanel />
      </GlassCard>

      {/* Sim Control — 시나리오 강제 트리거 */}
      <ScenarioPicker />

      <GlassCard>
        <SidebarMetrics />
      </GlassCard>

      <GlassCard>
        <AgentList />
      </GlassCard>
    </aside>
  );
}
