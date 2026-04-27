'use client';

import { useEffect, useState } from 'react';
import { apiUrl } from '@/lib/api';
import GlassCard from '@/components/common/GlassCard';
import { severityToPill } from '@/components/common/severityColors';

interface ScenarioLibraryItem {
  id: string;
  name: string;
  description?: string;
  category: string;
  severity: string;
  root_cause: string;
}

interface LibraryResp {
  scenarios?: ScenarioLibraryItem[];
  total_library?: number;
  active_count?: number;
}

const CATEGORY_LABELS: Record<string, string> = {
  cascading: '연쇄',
  single: '단일',
  degradation: '열화',
  environmental: '환경',
  external: '외부',
  transient: '일시',
  multi_root: '복합',
};

/** Sim Control — 시나리오 강제 트리거 + 라이브러리 카탈로그 */
export default function ScenarioPicker() {
  const [scenarios, setScenarios] = useState<ScenarioLibraryItem[]>([]);
  const [active, setActive] = useState<Set<string>>(new Set());
  const [activityCounts, setActivityCounts] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');
  const [busy, setBusy] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'ok' | 'err'; msg: string } | null>(null);

  // 시나리오 라이브러리 + active 상태 + 활성화 카운트 폴링
  useEffect(() => {
    let mounted = true;
    const tick = async () => {
      try {
        const r = await fetch(apiUrl('/api/scenarios/library'));
        if (r.ok) {
          const data = (await r.json()) as LibraryResp;
          if (mounted && data.scenarios) setScenarios(data.scenarios);
        }
      } catch {
        // ignore
      }
      try {
        const r = await fetch(apiUrl('/api/active-scenarios'));
        if (r.ok) {
          const data = await r.json();
          const ids = new Set<string>();
          for (const a of data.active ?? []) ids.add(a.scenario_id);
          if (mounted) setActive(ids);
        }
      } catch {
        // ignore
      }
      try {
        const r = await fetch(apiUrl('/api/scenarios/activity'));
        if (r.ok) {
          const data = await r.json();
          if (mounted) setActivityCounts((data.counts ?? {}) as Record<string, number>);
        }
      } catch {
        // ignore
      }
    };
    tick();
    const id = setInterval(tick, 4000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  const filtered = scenarios.filter(
    (s) => filter === 'ALL' || s.severity === filter,
  );

  async function trigger(sid: string) {
    setBusy(sid);
    setFeedback(null);
    try {
      const r = await fetch(apiUrl('/api/scenarios/trigger'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: sid }),
      });
      const data = await r.json();
      if (r.ok && data.status === 'activated') {
        setFeedback({ type: 'ok', msg: `▶ ${sid} 활성화` });
        setActive((prev) => new Set(prev).add(sid));
      } else {
        setFeedback({ type: 'err', msg: data.error || '트리거 실패' });
      }
    } catch (e) {
      setFeedback({ type: 'err', msg: String(e) });
    } finally {
      setBusy(null);
      setTimeout(() => setFeedback(null), 3000);
    }
  }

  return (
    <GlassCard className="p-2">
      <div className="flex items-center justify-between mb-1.5">
        <span className="ds-label">⚙ Sim Control</span>
        <span className="ds-caption">{scenarios.length}건 / {active.size}활성</span>
      </div>

      {/* 필터 */}
      <div className="flex items-center gap-1 mb-1.5 flex-wrap">
        {(['ALL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-[8px] px-1.5 py-0.5 rounded font-mono border transition ${
              filter === f
                ? f === 'HIGH'
                  ? 'pill-danger border-current'
                  : f === 'MEDIUM'
                    ? 'pill-warning border-current'
                    : f === 'LOW'
                      ? 'pill-success border-current'
                      : 'pill-info border-current'
                : 'bg-white/5 text-white/50 border-white/10 hover:bg-white/10'
            }`}
          >
            {f === 'ALL' ? '전체' : f}
          </button>
        ))}
      </div>

      {/* 시나리오 리스트 */}
      <div className="space-y-0.5 max-h-[260px] overflow-y-auto pr-1">
        {filtered.length === 0 ? (
          <div className="ds-caption text-center py-2">시나리오 로딩...</div>
        ) : (
          filtered.map((s) => {
            const isActive = active.has(s.id);
            const isBusy = busy === s.id;
            return (
              <button
                key={s.id}
                disabled={isActive || isBusy}
                onClick={() => trigger(s.id)}
                className={`w-full text-left px-1.5 py-1 rounded transition ${
                  isActive
                    ? 'pill-info opacity-60 cursor-not-allowed'
                    : 'bg-white/[0.03] hover:bg-white/10 border-l-2 border-white/10 hover:border-cyan-400/40'
                }`}
                title={s.description || s.root_cause}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="text-[9px] font-mono font-bold text-cyan-300">{s.id}</span>
                  <div className="flex items-center gap-1">
                    {(activityCounts[s.id] ?? 0) > 0 && (
                      <span
                        className="text-[7px] px-1 rounded font-mono bg-white/10 text-white/60"
                        title={`이 sim에서 ${activityCounts[s.id]}회 활성화`}
                      >
                        ×{activityCounts[s.id]}
                      </span>
                    )}
                    <span
                      className={`text-[7px] px-1 rounded font-mono ${severityToPill(s.severity)}`}
                    >
                      {s.severity[0]}
                    </span>
                  </div>
                </div>
                <div className="text-[9px] text-white/80 truncate font-medium">{s.name}</div>
                <div className="ds-caption">
                  {CATEGORY_LABELS[s.category] || s.category}
                  {isActive && <span className="text-cyan-300"> · 진행 중</span>}
                  {isBusy && <span className="text-amber-300"> · 활성화 중...</span>}
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* 피드백 */}
      {feedback && (
        <div
          className={`mt-1.5 px-1.5 py-1 rounded ds-caption ${
            feedback.type === 'ok' ? 'pill-success' : 'pill-danger'
          }`}
        >
          {feedback.msg}
        </div>
      )}
    </GlassCard>
  );
}
