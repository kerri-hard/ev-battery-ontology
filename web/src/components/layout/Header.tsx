'use client';

import { useEngine } from '@/context/EngineContext';
import ConnectionDot from '@/components/common/ConnectionDot';
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

const healingPhaseLabels: Record<string, string> = {
  sense: 'SENSE',
  detect: 'DETECT',
  diagnose: 'DIAGNOSE',
  recover: 'RECOVER',
  verify: 'VERIFY',
  learn_healing: 'LEARN',
};

export default function Header() {
  const { state } = useEngine();
  const currentIndex = state.currentPhase ? phases.indexOf(state.currentPhase) : -1;
  const pendingHitlCount = (state.healing.hitlPending || []).filter((x) => String(x.status || 'pending') === 'pending').length;

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 flex items-center justify-between px-4"
      style={{
        background: 'rgba(6, 6, 14, 0.8)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
      }}>
      {/* Left: Title + Status Pill (5초 룰) */}
      <div className="flex items-center gap-3">
        <span className="font-bold text-lg text-text-primary tracking-tight">
          EV Battery
        </span>
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full"
          style={{
            background: 'rgba(139, 92, 246, 0.15)',
            border: '1px solid rgba(139, 92, 246, 0.3)',
            color: '#a78bfa',
          }}>
          Self-Healing Factory
        </span>
        <SystemStatusPill />
      </div>

      {/* Center: Phase indicator (compact horizontal) */}
      <div className="hidden md:flex items-center gap-1">
        {phases.map((phase, i) => {
          const isCurrent = phase === state.currentPhase;
          const isCompleted = currentIndex >= 0 && i < currentIndex;

          let dotBg = 'rgba(255,255,255,0.1)';
          let textColor = '#8888aa';
          let dotBorder = 'transparent';

          if (isCurrent) {
            dotBg = '#00d2ff';
            textColor = '#00d2ff';
            dotBorder = '#00d2ff';
          } else if (isCompleted) {
            dotBg = 'rgba(6, 214, 160, 0.5)';
            textColor = '#06d6a0';
            dotBorder = 'transparent';
          }

          return (
            <div key={phase} className="flex items-center">
              {i > 0 && (
                <div className="w-3 h-px mx-0.5"
                  style={{ background: i <= currentIndex ? 'rgba(6, 214, 160, 0.4)' : 'rgba(255,255,255,0.08)' }}
                />
              )}
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full"
                  style={{
                    background: dotBg,
                    border: `1px solid ${dotBorder}`,
                    boxShadow: isCurrent ? '0 0 8px rgba(0, 210, 255, 0.5)' : 'none',
                    transition: 'all 0.3s ease',
                  }}
                />
                <span className="text-[10px] font-medium" style={{ color: textColor, transition: 'color 0.3s ease' }}>
                  {phaseLabels[phase]}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Right: Connection + version info + healing status */}
      <div className="flex items-center gap-3">
        {/* Healing running indicator */}
        {state.healing.running && (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full"
            style={{
              background: 'rgba(139, 92, 246, 0.12)',
              border: '1px solid rgba(139, 92, 246, 0.25)',
            }}>
            <div className="w-1.5 h-1.5 rounded-full bg-[#a855f7] animate-pulse" />
            <span className="text-[10px] text-[#a78bfa] font-medium">자율복구 중</span>
          </div>
        )}

        {/* v3 iteration info */}
        <span className="text-[10px] font-mono text-text-dim bg-white/5 rounded-full px-2 py-0.5">
          v3: iter {state.iteration}/{state.maxIterations}
        </span>

        {/* v4 healing stats */}
        {(state.healing.incidents > 0 || state.healing.running) && (
          <span className="text-[10px] font-mono rounded-full px-2 py-0.5"
            style={{
              color: '#f59e0b',
              background: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.15)',
            }}>
            v4: {state.healing.incidents}건/{state.healing.autoRecovered}복구
          </span>
        )}
        {state.healing.running && state.healingPhase && (
          <span className="text-[10px] font-mono rounded-full px-2 py-0.5"
            style={{
              color: '#22d3ee',
              background: 'rgba(34, 211, 238, 0.08)',
              border: '1px solid rgba(34, 211, 238, 0.2)',
            }}>
            {healingPhaseLabels[state.healingPhase] || state.healingPhase}
          </span>
        )}
        {pendingHitlCount > 0 && (
          <span className="text-[10px] font-mono rounded-full px-2 py-0.5"
            style={{
              color: '#fbbf24',
              background: 'rgba(251, 191, 36, 0.1)',
              border: '1px solid rgba(251, 191, 36, 0.28)',
            }}>
            HITL 대기 {pendingHitlCount}
          </span>
        )}

        <ConnectionDot status={state.connectionStatus} />
      </div>
    </header>
  );
}

/** 전역 시스템 상태 신호등 — 5초 룰 (모든 페이지에서 보임) */
function SystemStatusPill() {
  const { state, setView } = useEngine();
  const violations = state.slo?.violations.length ?? 0;
  const incidents = state.healing.incidents ?? 0;
  const autoRecovered = state.healing.autoRecovered ?? 0;
  const recovery_rate = incidents > 0 ? autoRecovered / incidents : 1;

  let level: 'success' | 'warning' | 'danger' = 'success';
  let label = '● 모든 SLO 충족';
  let detail = '시스템 안정';
  if (violations >= 2 || recovery_rate < 0.8) {
    level = 'danger';
    label = '🔴 주의';
    detail = `${violations}건 SLO 위반 / 복구율 ${(recovery_rate * 100).toFixed(0)}%`;
  } else if (violations >= 1) {
    level = 'warning';
    label = '⚠ 1건 위반';
    detail = `복구율 ${(recovery_rate * 100).toFixed(0)}%`;
  }

  const cls =
    level === 'success'
      ? 'pill-success'
      : level === 'warning'
        ? 'pill-warning'
        : 'pill-danger';

  return (
    <button
      onClick={() => setView('slo')}
      className={`px-3 py-1 rounded-full ${cls} flex items-center gap-2 hover:opacity-90 transition`}
      title="SLO 페이지로 이동"
    >
      <span className="text-[11px] font-bold">{label}</span>
      <span className="text-[9px] font-mono opacity-80">{detail}</span>
    </button>
  );
}
