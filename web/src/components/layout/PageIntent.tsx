'use client';

import type { ViewKey } from '@/types';

/** 페이지 정체성 헤더 — 5 페이지마다 다른 한 질문.
 *  4번째 UX 사이클의 핵심: 5 페이지가 같은 머리(SLOKpiRibbon)로 시작하던 문제 해결.
 *  각 페이지의 의도를 한 줄로 명시 → 운영자가 "이 페이지에서 무엇을 답해야 하는지" 즉시 파악.
 */

interface PageMeta {
  icon: string;
  title: string;
  question: string; // 한 질문 — 페이지의 정체성
  hint: string; // supporting context
  accent: 'cyan' | 'purple' | 'emerald' | 'amber' | 'white';
}

const PAGE_META: Record<ViewKey, PageMeta> = {
  overview: {
    icon: '🏠',
    title: 'Overview',
    question: '지금 어떻게 돌아가는가?',
    hint: '시스템 전체 상태 한눈 — 사람이 안 봐도 자율 복구 진행',
    accent: 'cyan',
  },
  healing: {
    icon: '🛡',
    title: 'Healing',
    question: '이 incident는 누가, 어떻게 잡고 있는가?',
    hint: 'Detect → Diagnose → Heal — 클릭 한 번으로 풀 라이프사이클',
    accent: 'purple',
  },
  slo: {
    icon: '📊',
    title: 'SLO',
    question: '어떤 약속이 깨지고 있는가?',
    hint: '5 SLI · 31 step microservice · error budget',
    accent: 'amber',
  },
  learning: {
    icon: '🧠',
    title: 'Learning',
    question: '어제와 무엇이 달라졌는가?',
    hint: '8 전략 진화 · FailureChain 패턴 학습 · 자가 보정',
    accent: 'emerald',
  },
  console: {
    icon: '🖥',
    title: 'Console',
    question: '원본 데이터 그대로 보여줘',
    hint: 'Raw observability — 디버그 채널',
    accent: 'white',
  },
};

const ACCENT_COLOR: Record<PageMeta['accent'], string> = {
  cyan: 'text-cyan-300',
  purple: 'text-purple-300',
  emerald: 'text-emerald-300',
  amber: 'text-amber-300',
  white: 'text-white/80',
};

const ACCENT_BORDER: Record<PageMeta['accent'], string> = {
  cyan: 'border-cyan-400/30',
  purple: 'border-purple-400/30',
  emerald: 'border-emerald-400/30',
  amber: 'border-amber-400/30',
  white: 'border-white/15',
};

export default function PageIntent({ view }: { view: ViewKey }) {
  const meta = PAGE_META[view];
  if (!meta) return null;
  return (
    <div
      className={`flex items-center gap-3 px-3 py-2 border-b ${ACCENT_BORDER[meta.accent]}`}
    >
      <span className="text-2xl leading-none">{meta.icon}</span>
      <div className="flex-1 min-w-0">
        <div className={`text-base font-bold ${ACCENT_COLOR[meta.accent]} leading-tight`}>
          {meta.question}
        </div>
        <div className="ds-caption mt-0.5">{meta.hint}</div>
      </div>
      <div className="ds-label opacity-60 whitespace-nowrap">{meta.title}</div>
    </div>
  );
}
