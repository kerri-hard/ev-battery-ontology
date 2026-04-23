'use client';

import { useEngine } from '@/context/EngineContext';

/**
 * VISION 9.4 (자동 복구가 목적) + 9.6 (점진적 자율성) 가시화.
 * 운영자가 한눈에 "사람이 안 봐도 잘 돌아가는가?" 판단할 수 있어야 한다.
 */
export default function AutonomyHero() {
  const { state } = useEngine();
  const h = state.healing;
  const pv = state.preverify;
  const recoveryRate = h.incidents > 0 ? (h.autoRecovered / h.incidents) * 100 : 100;
  const hitlPending = h.hitlPending?.length ?? 0;
  const autoRejectRate = pv ? pv.auto_reject_rate * 100 : 0;
  // 자율도 점수 (0-100): 자동복구율 가중 + HITL 대기 페널티 + preverify 거절 페널티
  const autonomyScore = Math.max(
    0,
    Math.min(100, recoveryRate - hitlPending * 5 - autoRejectRate * 0.5),
  );
  const scoreColor = autonomyScore >= 90 ? '#10b981' : autonomyScore >= 70 ? '#f59e0b' : '#ef4444';
  const scoreLabel = autonomyScore >= 90 ? 'AUTONOMOUS' : autonomyScore >= 70 ? 'SUPERVISED' : 'INTERVENTION';

  return (
    <div
      className="glass p-3 col-span-2"
      style={{
        background: `linear-gradient(135deg, ${scoreColor}10, transparent)`,
        borderLeft: `3px solid ${scoreColor}`,
      }}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-white/50">
            Autonomy Status
          </div>
          <div className="text-[9px] text-white/40">VISION 9.4 — 자동 복구가 목적, 모니터링은 수단</div>
        </div>
        <div
          className="text-[9px] font-bold px-2 py-0.5 rounded"
          style={{ background: `${scoreColor}25`, color: scoreColor }}
        >
          {scoreLabel}
        </div>
      </div>

      <div className="flex items-baseline gap-3 mb-3">
        <div className="font-mono text-3xl font-bold" style={{ color: scoreColor }}>
          {autonomyScore.toFixed(0)}
        </div>
        <div className="text-[10px] text-white/45">/ 100 자율도</div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <KpiCell
          label="자동 복구"
          primary={`${recoveryRate.toFixed(0)}%`}
          secondary={`${h.autoRecovered}/${h.incidents}`}
          color="#10b981"
        />
        <KpiCell
          label="HITL 대기"
          primary={String(hitlPending)}
          secondary={hitlPending === 0 ? '사람 개입 X' : '승인 필요'}
          color={hitlPending === 0 ? '#94a3b8' : '#f59e0b'}
        />
        <KpiCell
          label="Pre-verify 거절"
          primary={pv ? `${autoRejectRate.toFixed(0)}%` : '—'}
          secondary={pv ? `${pv.auto_rejected_total}/${pv.plans_total}` : 'no data'}
          color={autoRejectRate < 10 ? '#10b981' : autoRejectRate < 25 ? '#f59e0b' : '#ef4444'}
        />
      </div>
    </div>
  );
}

function KpiCell({
  label,
  primary,
  secondary,
  color,
}: {
  label: string;
  primary: string;
  secondary: string;
  color: string;
}) {
  return (
    <div className="rounded border border-white/5 px-2 py-1.5">
      <div className="text-[8px] uppercase tracking-wider text-white/40">{label}</div>
      <div className="font-mono text-base font-bold" style={{ color }}>
        {primary}
      </div>
      <div className="text-[8px] text-white/40 truncate" title={secondary}>
        {secondary}
      </div>
    </div>
  );
}
