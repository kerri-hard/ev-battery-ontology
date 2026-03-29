'use client';

import { useEngine } from '@/context/EngineContext';
import type { Phase } from '@/types';

const phases: Phase[] = ['observe', 'propose', 'debate', 'apply', 'evaluate', 'learn'];

const phaseLabels: Partial<Record<Phase, string>> = {
  observe: '관찰',
  propose: '제안',
  debate: '토론',
  apply: '적용',
  evaluate: '평가',
  learn: '학습',
};

export default function PhaseIndicator() {
  const { state } = useEngine();
  const currentIndex = state.currentPhase ? phases.indexOf(state.currentPhase) : -1;

  return (
    <div>
      <h3 className="text-xs text-text-dim mb-3 font-medium">진행 단계</h3>
      <div className="flex items-center justify-between">
        {phases.map((phase, i) => {
          const isCurrent = phase === state.currentPhase;
          const isCompleted = currentIndex >= 0 && i < currentIndex;

          let circleClass = 'bg-white/10 text-text-dim';
          if (isCurrent) circleClass = 'bg-cyan text-white animate-glow-pulse';
          else if (isCompleted) circleClass = 'bg-neon-green/50 text-white';

          return (
            <div key={phase} className="flex flex-col items-center relative">
              {/* Connector line */}
              {i > 0 && (
                <div
                  className={`absolute top-3 -left-[calc(50%-3px)] w-[calc(100%-6px)] h-px
                    -translate-x-1/2
                    ${i <= currentIndex ? 'bg-neon-green/50' : 'bg-white/10'}`}
                  style={{ left: '-50%', width: '100%' }}
                />
              )}
              {/* Circle */}
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold z-10 ${circleClass}`}
              >
                {i + 1}
              </div>
              {/* Label */}
              <span className={`text-[10px] mt-1 ${isCurrent ? 'text-cyan' : 'text-text-dim'}`}>
                {phaseLabels[phase]}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
