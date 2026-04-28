'use client';

import { useEffect, useState } from 'react';
import { useEngine } from '@/context/EngineContext';
import type { ViewKey } from '@/types';

const KEY_TO_VIEW: Record<string, ViewKey> = {
  o: 'overview',
  h: 'healing',
  s: 'slo',
  l: 'learning',
  c: 'console',
};

/** 전역 키보드 단축키 — operator agency의 마지막 조각.
 *  - g + (o/h/s/l/c): 페이지 전환 (Vim/GitHub 패턴)
 *  - Esc: 선택 해제 (incident/SLO/step/scenario)
 *  - ?: 단축키 도움말 토글
 *
 *  input/textarea focus 시 비활성화 (검색박스 입력 방해 방지).
 */
export default function KeyboardShortcuts() {
  const { state, navigateTo } = useEngine();
  const [waitingForG, setWaitingForG] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    function isFormElement(el: EventTarget | null): boolean {
      if (!(el instanceof HTMLElement)) return false;
      const tag = el.tagName.toLowerCase();
      return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
    }

    function handleKey(e: KeyboardEvent) {
      if (isFormElement(e.target)) return;
      // ? 도움말 토글
      if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        setShowHelp((p) => !p);
        e.preventDefault();
        return;
      }
      // Esc — 선택 해제
      if (e.key === 'Escape') {
        navigateTo({ incidentId: null, sloKey: null, stepId: null, scenarioId: null });
        return;
      }
      // g leader
      if (e.key === 'g' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        setWaitingForG(true);
        // 1.5s timeout
        setTimeout(() => setWaitingForG(false), 1500);
        return;
      }
      // g + view key
      if (waitingForG) {
        const view = KEY_TO_VIEW[e.key.toLowerCase()];
        if (view) {
          navigateTo({ view });
          e.preventDefault();
        }
        setWaitingForG(false);
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [waitingForG, navigateTo]);

  return (
    <>
      {/* g 입력 후 다음 키 대기 안내 */}
      {waitingForG && (
        <div
          className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[200] pill-info px-3 py-1.5 rounded-lg shadow-2xl animate-fade-in"
          role="status"
          aria-live="polite"
        >
          <span className="ds-body font-bold">g</span>
          <span className="ds-caption ml-2">다음: o (Overview), h (Healing), s (SLO), l (Learning), c (Console)</span>
        </div>
      )}

      {/* 도움말 패널 (? 키로 토글) */}
      {showHelp && (
        <div
          className="fixed inset-0 bg-black/60 z-[200] flex items-center justify-center p-4"
          onClick={() => setShowHelp(false)}
          role="dialog"
          aria-modal="true"
          aria-label="키보드 단축키 도움말"
        >
          <div
            className="glass max-w-md w-full p-4 rounded-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="ds-heading">⌨ 키보드 단축키</span>
              <button
                onClick={() => setShowHelp(false)}
                className="ds-caption hover:text-white/80 px-1"
                aria-label="닫기"
              >
                ✕
              </button>
            </div>
            <div className="space-y-2">
              <ShortcutRow keys="g o" desc="🏠 Overview" />
              <ShortcutRow keys="g h" desc="🛡 Healing" />
              <ShortcutRow keys="g s" desc="📊 SLO" />
              <ShortcutRow keys="g l" desc="🧠 Learning" />
              <ShortcutRow keys="g c" desc="🖥 Console" />
              <div className="border-t border-white/10 my-2" />
              <ShortcutRow keys="Esc" desc="선택 해제 (incident/SLI/step/scenario)" />
              <ShortcutRow keys="?" desc="이 도움말" />
            </div>
            <div className="ds-caption mt-3 text-center opacity-60">
              현재 페이지: <span className="text-cyan-300 font-mono">{state.currentView ?? 'healing'}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function ShortcutRow({ keys, desc }: { keys: string; desc: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <kbd className="text-[10px] font-mono px-2 py-0.5 rounded border border-white/20 bg-white/5 text-white/80 min-w-[40px] text-center">
        {keys}
      </kbd>
      <span className="ds-body text-white/70 flex-1">{desc}</span>
    </div>
  );
}
