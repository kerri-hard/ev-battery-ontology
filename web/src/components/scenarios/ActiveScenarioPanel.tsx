'use client';

import { useEffect, useState } from 'react';
import { apiUrl } from '@/lib/api';
import GlassCard from '@/components/common/GlassCard';
import type { ActiveScenario, ScenarioStatus } from '@/types';

/** 진행 중 시나리오 + 라이브러리 통계 — Healing/Learning view에 표시 */
export default function ActiveScenarioPanel() {
  const [data, setData] = useState<ScenarioStatus | null>(null);

  useEffect(() => {
    let mounted = true;
    const tick = async () => {
      try {
        const r = await fetch(apiUrl('/api/active-scenarios'));
        if (!r.ok) return;
        const json = (await r.json()) as ScenarioStatus;
        if (mounted) setData(json);
      } catch {
        // ignore
      }
    };
    tick();
    const id = setInterval(tick, 3000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  if (!data) {
    return (
      <GlassCard>
        <div className="ds-caption text-white/40">시나리오 데이터 대기 중...</div>
      </GlassCard>
    );
  }

  const active = data.active ?? [];
  const sevDist = data.library_stats?.by_severity ?? {};
  const catDist = data.library_stats?.by_category ?? {};

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="ds-label text-white/55">📌 활성 시나리오</span>
        <span className="ds-caption">
          {active.length}개 진행 / {data.total_library} 라이브러리
        </span>
      </div>

      {/* 라이브러리 통계 */}
      <div className="flex items-center gap-1 mb-2 flex-wrap">
        {Object.entries(sevDist).map(([sev, n]) => (
          <span
            key={sev}
            className={`ds-caption px-1.5 py-0.5 rounded font-mono ${
              sev === 'HIGH'
                ? 'pill-danger'
                : sev === 'MEDIUM'
                  ? 'pill-warning'
                  : 'pill-success'
            }`}
          >
            {sev} {n}
          </span>
        ))}
        <span className="ds-caption text-white/25 px-1">·</span>
        {Object.entries(catDist).slice(0, 4).map(([cat, n]) => (
          <span
            key={cat}
            className="ds-caption px-1.5 py-0.5 rounded bg-white/5 text-white/60 font-mono"
          >
            {cat} {n}
          </span>
        ))}
      </div>

      {/* 진행 중 시나리오 */}
      {active.length === 0 ? (
        <div className="ds-caption text-white/40 px-2 py-4 text-center">
          진행 중 시나리오 없음 — 다음 sim tick에서 무작위 활성화
        </div>
      ) : (
        <div className="space-y-1.5">
          {active.map((s) => (
            <ActiveScenarioRow key={s.scenario_id} scenario={s} />
          ))}
        </div>
      )}
    </GlassCard>
  );
}

function ActiveScenarioRow({ scenario }: { scenario: ActiveScenario }) {
  const sevClass =
    scenario.severity === 'HIGH'
      ? 'pill-danger'
      : scenario.severity === 'MEDIUM'
        ? 'pill-warning'
        : 'pill-success';
  const progress = scenario.total_effects > 0
    ? scenario.effects_injected / scenario.total_effects
    : 0;

  return (
    <div className="px-2 py-1.5 rounded bg-white/[0.03] border-l-2 border-cyan-400/40">
      <div className="flex items-center justify-between gap-2 mb-0.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="ds-caption text-cyan-300 font-bold">{scenario.scenario_id}</span>
          <span className="ds-body text-white/80 truncate font-medium">{scenario.name}</span>
        </div>
        <div className="flex items-center gap-1 whitespace-nowrap">
          <span className={`ds-caption px-1.5 py-0.5 rounded font-mono ${sevClass}`}>
            {scenario.severity}
          </span>
          <span className="ds-caption text-white/50 font-mono">
            T+{scenario.elapsed_ticks}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div className="ds-caption text-white/40 truncate flex-1">
          {scenario.category} · root_cause: <span className="text-purple-300">{scenario.root_cause}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-20 h-1 rounded bg-white/10 overflow-hidden">
            <div
              className="h-full bg-cyan-400"
              style={{ width: `${(progress * 100).toFixed(0)}%` }}
            />
          </div>
          <span className="ds-caption text-white/60 font-mono">
            {scenario.effects_injected}/{scenario.total_effects}
          </span>
        </div>
      </div>
    </div>
  );
}
