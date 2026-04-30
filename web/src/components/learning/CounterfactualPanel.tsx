'use client';

import { useEffect, useState } from 'react';
import { apiUrl } from '@/lib/api';
import GlassCard from '@/components/common/GlassCard';
import { EmptyState, LoadingState } from '@/components/common/StateMessages';

interface CFLItem {
  id: string;
  incident_id: string;
  step_id: string;
  chosen_action: string;
  best_alternative: string;
  missed_value: number;
  created_at: string;
}

/** Learning 페이지: 누적 CounterfactualLearning 노드 — "시스템이 더 좋은 선택을 놓친 사례".
 *
 *  비전: §9.5 학습 자동화. missed_value ≥ 0.005 인 incident가 자동 누적되며,
 *  향후 EvolutionAgent fitness 신호 / 진단 score 가중치 보정 데이터로 활용.
 */
export default function CounterfactualPanel() {
  const [items, setItems] = useState<CFLItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    fetch(apiUrl('/api/counterfactual-learning'))
      .then((r) => r.json())
      .then((d) => {
        if (mounted) {
          if (d.error) setError(d.error);
          else setItems(d.items ?? []);
        }
      })
      .catch((e) => {
        if (mounted) setError(String(e));
      });
    return () => {
      mounted = false;
    };
  }, []);

  if (error) {
    return (
      <GlassCard className="p-3">
        <div className="ds-label">🎓 Counterfactual Learning</div>
        <div className="ds-caption text-rose-300 mt-1">에러: {error}</div>
      </GlassCard>
    );
  }
  if (items === null) {
    return (
      <GlassCard className="p-3">
        <LoadingState label="학습 후보 로딩..." />
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-3">
      <div className="ds-label mb-2 flex items-center gap-2">
        <span>🎓 Counterfactual Learning</span>
        <span className="pill-info ds-caption font-bold px-1.5 py-0.5 rounded">
          {items.length}건 누적
        </span>
      </div>
      {items.length === 0 ? (
        <EmptyState
          icon="🎓"
          title="학습 후보 없음"
          hint="system이 매 incident에 더 좋은 선택을 한 상태 — 시뮬상 최적 운영 중"
        />
      ) : (
        <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
          {items.map((cfl) => (
            <div
              key={cfl.id}
              className="px-2 py-1.5 rounded bg-amber-500/5 border-l-2 border-amber-400/40"
            >
              <div className="flex items-center justify-between mb-0.5">
                <div className="ds-body font-mono text-amber-200/90">{cfl.step_id}</div>
                <div className="ds-caption font-mono text-rose-300 font-bold">
                  +{cfl.missed_value.toFixed(4)} 놓침
                </div>
              </div>
              <div className="ds-caption text-white/70">
                선택: <span className="font-mono">{cfl.chosen_action}</span>
                <span className="text-white/30 mx-1">→</span>
                더 나은: <span className="font-mono text-emerald-300">{cfl.best_alternative}</span>
              </div>
              <div className="ds-caption text-white/40 mt-0.5 font-mono">
                {cfl.incident_id} · {cfl.created_at}
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="ds-caption text-white/50 mt-2">
        💡 각 사례 = missed_value ≥ 0.005 (yield 0.5%p) 임계 통과. 향후 EvolutionAgent
        fitness 신호 + 진단 score 가중치 보정 데이터로 활용.
      </div>
    </GlassCard>
  );
}
