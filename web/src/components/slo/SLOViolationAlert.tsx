'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';

/** SLO 위반 알림 카드 — Overview 핵심 강조 + drill-down */
export default function SLOViolationAlert() {
  const { state, navigateTo } = useEngine();
  const slo = state.slo;
  const violations = slo?.violations ?? [];

  if (violations.length === 0) {
    return (
      <GlassCard className="p-3 pill-success">
        <div className="flex items-center gap-2">
          <span className="text-lg">✓</span>
          <div>
            <div className="ds-heading">모든 SLO 충족</div>
            <div className="ds-caption">
              {Object.keys(slo?.definitions ?? {}).length}개 SLI 모두 목표 내 — error budget 안정
            </div>
          </div>
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-rose-400 text-lg animate-pulse">⚠</span>
          <span className="ds-heading text-rose-300">
            SLO 위반 {violations.length}건
          </span>
        </div>
        <button
          onClick={() => navigateTo({ view: 'slo' })}
          className="ds-caption text-cyan-300 hover:text-cyan-100 underline"
        >
          전체 SLO 보기 →
        </button>
      </div>
      <div className="space-y-1">
        {violations.slice(0, 4).map((v) => (
          <button
            key={v.sli}
            onClick={() => navigateTo({ view: 'slo', sloKey: v.sli })}
            className="w-full grid grid-cols-[1fr_60px_60px] gap-2 items-center px-1.5 py-1 rounded pill-danger hover:opacity-90 transition text-left"
            title={`SLO 페이지에서 ${v.name} 강조 →`}
          >
            <div className="min-w-0">
              <div className="ds-body font-bold truncate">{v.name}</div>
              <div className="ds-caption truncate">
                {v.affected_steps.length > 0 ? (
                  <>
                    영향:{' '}
                    {v.affected_steps.slice(0, 3).map((s, i) => (
                      <span
                        key={s}
                        role="button"
                        tabIndex={0}
                        onClick={(e) => {
                          e.stopPropagation();
                          navigateTo({ view: 'healing', stepId: s });
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.stopPropagation();
                            navigateTo({ view: 'healing', stepId: s });
                          }
                        }}
                        className="text-cyan-300 hover:text-cyan-100 underline cursor-pointer"
                      >
                        {s}
                        {i < Math.min(2, v.affected_steps.length - 1) && ', '}
                      </span>
                    ))}
                  </>
                ) : (
                  v.sli
                )}
              </div>
            </div>
            <div className="text-right">
              <div className="ds-body font-mono font-bold">{(v.current * 100).toFixed(1)}%</div>
              <div className="ds-caption">현재</div>
            </div>
            <div className="text-right">
              <div className="ds-body font-mono opacity-80">{(v.target * 100).toFixed(1)}%</div>
              <div className="ds-caption">목표</div>
            </div>
          </button>
        ))}
      </div>
    </GlassCard>
  );
}
