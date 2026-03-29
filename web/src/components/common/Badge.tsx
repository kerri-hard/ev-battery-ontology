'use client';

import type { Phase } from '@/types';

interface BadgeProps {
  phase: Phase;
  children?: React.ReactNode;
}

const phaseColors: Record<Phase, string> = {
  observe: '#3a7bd5',
  propose: '#06d6a0',
  debate: '#a855f7',
  apply: '#00d2ff',
  evaluate: '#ffd166',
  learn: '#FF6B35',
  skip: '#6b7280',
  sense: '#3a7bd5',
  detect: '#ef4444',
  diagnose: '#f59e0b',
  recover: '#10b981',
  verify: '#00d2ff',
  learn_healing: '#FF6B35',
};

const phaseLabels: Record<Phase, string> = {
  observe: '관찰',
  propose: '제안',
  debate: '토론',
  apply: '적용',
  evaluate: '평가',
  learn: '학습',
  skip: '건너뜀',
  sense: '수집',
  detect: '감지',
  diagnose: '진단',
  recover: '복구',
  verify: '검증',
  learn_healing: '학습',
};

export default function Badge({ phase, children }: BadgeProps) {
  const color = phaseColors[phase];

  return (
    <span
      className="inline-block rounded-full text-xs px-2 py-0.5 font-medium text-white"
      style={{ backgroundColor: color }}
    >
      {children ?? phaseLabels[phase]}
    </span>
  );
}
