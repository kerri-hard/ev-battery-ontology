'use client';

import { useEngine } from '@/context/EngineContext';
import ProposalList from '@/components/debate/ProposalList';
import VoteResults from '@/components/debate/VoteResults';
import ApplyResults from '@/components/debate/ApplyResults';
import EvalResults from '@/components/debate/EvalResults';
import LearnResults from '@/components/debate/LearnResults';

export default function DebatePanel() {
  const { state } = useEngine();
  const { currentPhase, debate } = state;

  const sections: { phase: string; label: string; available: boolean; component: React.ReactNode }[] = [
    {
      phase: 'propose',
      label: '제안',
      available: currentPhase === 'propose' || debate.proposals !== null,
      component: <ProposalList />,
    },
    {
      phase: 'debate',
      label: '투표',
      available: currentPhase === 'debate' || debate.votes !== null,
      component: <VoteResults />,
    },
    {
      phase: 'apply',
      label: '적용',
      available: currentPhase === 'apply' || debate.applied !== null,
      component: <ApplyResults />,
    },
    {
      phase: 'evaluate',
      label: '평가',
      available: currentPhase === 'evaluate' || debate.evaluation !== null,
      component: <EvalResults />,
    },
    {
      phase: 'learn',
      label: '학습',
      available: currentPhase === 'learn' || debate.learning !== null,
      component: <LearnResults />,
    },
  ];

  const hasAny = sections.some((s) => s.available);

  if (!hasAny) {
    return (
      <div>
        <h3 className="text-sm font-bold text-text-primary mb-3">에이전트 토론</h3>
        <div className="flex items-center justify-center h-40 text-text-dim text-xs">
          시뮬레이션을 시작하세요
        </div>
      </div>
    );
  }

  return (
    <div>
      <h3 className="text-sm font-bold text-text-primary mb-3">에이전트 토론</h3>
      <div className="space-y-4">
        {sections.map((section) => {
          if (!section.available) return null;

          const isActive = currentPhase === section.phase;

          return (
            <div
              key={section.phase}
              className={`rounded-lg p-2.5 transition-all ${
                isActive
                  ? 'bg-white/[0.06] border border-cyan/20 shadow-[0_0_8px_rgba(0,210,255,0.1)]'
                  : 'bg-white/[0.02] border border-white/[0.05]'
              }`}
            >
              {section.component}
            </div>
          );
        })}
      </div>
    </div>
  );
}
