'use client';

interface MainContentProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  children?: React.ReactNode;
}

const tabs = [
  { id: 'process', label: '공정 맵' },
  { id: 'debate', label: '에이전트 토론' },
  { id: 'history', label: '분석 이력' },
];

export default function MainContent({ activeTab, onTabChange, children }: MainContentProps) {
  return (
    <div className="flex-1 overflow-y-auto p-4">
      {/* Tab navigation */}
      <div className="flex gap-4 border-b border-white/5 mb-4">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`pb-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'border-b-2 border-cyan text-white'
                  : 'text-text-dim hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {children}
    </div>
  );
}
