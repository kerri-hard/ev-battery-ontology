'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';

/** SLO 위반 알림 카드 — Overview 페이지 핵심 강조 */
export default function SLOViolationAlert() {
  const { state, setView } = useEngine();
  const slo = state.slo;
  const violations = slo?.violations ?? [];

  if (violations.length === 0) {
    return (
      <GlassCard className="p-3">
        <div className="flex items-center gap-2">
          <span className="text-emerald-400 text-lg">✓</span>
          <div>
            <div className="text-[11px] font-bold text-emerald-300">모든 SLO 충족</div>
            <div className="text-[9px] text-white/40">
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
          <span className="text-[11px] font-bold text-rose-300">
            SLO 위반 {violations.length}건
          </span>
        </div>
        <button
          onClick={() => setView('slo')}
          className="text-[9px] text-cyan-300 hover:text-cyan-100 underline"
        >
          상세 보기 →
        </button>
      </div>
      <div className="space-y-1">
        {violations.slice(0, 4).map((v) => (
          <div
            key={v.sli}
            className="grid grid-cols-[1fr_60px_60px] gap-2 items-center px-1.5 py-1 rounded bg-rose-500/10 border-l-2 border-rose-400"
          >
            <div className="min-w-0">
              <div className="text-[10px] font-bold text-rose-200 truncate">{v.name}</div>
              <div className="text-[8px] text-white/40 font-mono truncate">
                {v.affected_steps.length > 0
                  ? `영향: ${v.affected_steps.slice(0, 3).join(', ')}`
                  : v.sli}
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-mono text-rose-300 font-bold">
                {(v.current * 100).toFixed(1)}%
              </div>
              <div className="text-[8px] text-white/40 font-mono">현재</div>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-mono text-white/60">
                {(v.target * 100).toFixed(1)}%
              </div>
              <div className="text-[8px] text-white/40 font-mono">목표</div>
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
