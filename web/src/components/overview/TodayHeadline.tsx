'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import type { NavTarget } from '@/types';

/** Overview 최상단 헤드라인 — 24h(또는 sim 누적) 핵심 지표 한 줄 narrative + drill-down */
export default function TodayHeadline() {
  const { state, navigateTo } = useEngine();
  const h = state.healing;
  const slo = state.slo?.global;
  const incidents = h?.incidents ?? 0;
  const autoRecovered = h?.autoRecovered ?? 0;
  const recoveryRate = incidents > 0 ? (autoRecovered / incidents) : 1;
  const mttrMs = (slo?.p50_recovery_latency ?? 0) * 1000;
  const violations = state.slo?.violations.length ?? 0;
  const repeatRate = slo?.repeat_rate ?? 0;
  const yieldCompliance = slo?.yield_compliance ?? 0;

  // 한 줄 narrative
  const narrative = buildNarrative({
    incidents,
    autoRecovered,
    recoveryRate,
    mttrMs,
    violations,
    repeatRate,
  });

  return (
    <GlassCard className="p-4">
      <div className="flex items-center justify-between gap-4">
        {/* Headline */}
        <div className="flex-1 min-w-0">
          <div className="ds-label mb-1.5">📊 오늘의 요약 — sim 누적</div>
          <div className="ds-heading text-base leading-snug">{narrative}</div>
        </div>

        {/* Quick KPI grid — 클릭하면 해당 view로 drill-down */}
        <div className="grid grid-cols-4 gap-3 shrink-0">
          <KPI label="자동 복구" value={incidents > 0 ? `${autoRecovered}/${incidents}` : '0/0'}
            sub={`${(recoveryRate * 100).toFixed(0)}%`} ok={recoveryRate >= 0.95}
            nav={{ view: 'healing' }} navigateTo={navigateTo} />
          <KPI label="MTTR (p50)" value={`${mttrMs.toFixed(1)}ms`}
            sub="복구 지연" ok={mttrMs < 50}
            nav={{ view: 'slo', sloKey: 'p95_recovery_latency' }} navigateTo={navigateTo} />
          <KPI label="수율 준수" value={`${(yieldCompliance * 100).toFixed(1)}%`}
            sub="≥0.99" ok={yieldCompliance >= 0.95}
            nav={{ view: 'slo', sloKey: 'yield_compliance' }} navigateTo={navigateTo} />
          <KPI label="재발률" value={`${(repeatRate * 100).toFixed(0)}%`}
            sub="동일 시그니처" ok={repeatRate < 0.25}
            nav={{ view: 'learning' }} navigateTo={navigateTo} />
        </div>
      </div>
    </GlassCard>
  );
}

interface NarrativeArgs {
  incidents: number;
  autoRecovered: number;
  recoveryRate: number;
  mttrMs: number;
  violations: number;
  repeatRate: number;
}

function buildNarrative(a: NarrativeArgs): string {
  if (a.incidents === 0) {
    return '🟢 sim 시작 대기 — 좌측 Control Panel에서 시뮬레이션을 시작하세요.';
  }
  const ar = (a.recoveryRate * 100).toFixed(0);
  const parts: string[] = [];
  parts.push(`✓ ${a.autoRecovered}/${a.incidents}건 자동 복구 (${ar}%)`);
  parts.push(`평균 ${a.mttrMs.toFixed(1)}ms`);
  if (a.repeatRate > 0) {
    parts.push(`재발 ${(a.repeatRate * 100).toFixed(0)}%`);
  }
  if (a.violations > 0) {
    parts.push(`⚠ SLO 위반 ${a.violations}건`);
  } else {
    parts.push('🟢 모든 SLO 충족');
  }
  return parts.join(' · ');
}

function KPI({
  label,
  value,
  sub,
  ok,
  nav,
  navigateTo,
}: {
  label: string;
  value: string;
  sub: string;
  ok: boolean;
  nav: NavTarget;
  navigateTo: (t: NavTarget) => void;
}) {
  return (
    <button
      onClick={() => navigateTo(nav)}
      className="text-right hover:bg-white/5 rounded px-2 py-1 transition cursor-pointer"
      title={`${label} 상세 보기 →`}
    >
      <div className="ds-caption">{label}</div>
      <div className={`text-xl font-mono font-bold ${ok ? 'text-emerald-300' : 'text-amber-300'}`}>
        {value}
      </div>
      <div className="ds-caption">{sub}</div>
    </button>
  );
}
