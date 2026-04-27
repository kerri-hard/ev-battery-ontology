'use client';

import { useEffect, useState } from 'react';
import { apiUrl } from '@/lib/api';
import GlassCard from '@/components/common/GlassCard';
import { LoadingState, EmptyState } from '@/components/common/StateMessages';

interface CausalRule {
  id: string;
  cause_type: string;
  effect_type: string;
  strength: number;
  source_step?: string;
  target_step?: string;
  p_value?: number;
  f_stat?: number;
  best_lag?: number;
  timestamp?: string;
}

interface CausalDiscoveryStatus {
  total_discovered: number;
  total_promoted: number;
  recent_promotions: CausalRule[];
  scipy_available: boolean;
}

/** L3 인과 추론 시각화 — multi-hop chain 추적 */
export default function CausalChainTracer() {
  const [data, setData] = useState<CausalDiscoveryStatus | null>(null);

  useEffect(() => {
    let mounted = true;
    const tick = async () => {
      try {
        const r = await fetch(apiUrl('/api/causal-discovery'));
        if (!r.ok) return;
        const json = (await r.json()) as CausalDiscoveryStatus;
        if (mounted) setData(json);
      } catch {
        // ignore
      }
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  if (!data) {
    return (
      <GlassCard>
        <LoadingState label="CausalDiscovery 데이터 로딩..." />
      </GlassCard>
    );
  }

  const promotions = data.recent_promotions ?? [];
  const chains = buildMultiHopChains(promotions);

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="ds-label">L3 Causal Chain Tracer</span>
        <div className="flex items-center gap-2">
          <span className="ds-caption">
            <span className="text-emerald-300 font-bold">{data.total_promoted}</span> promoted /{' '}
            {data.total_discovered} discovered
          </span>
          {!data.scipy_available && (
            <span className="text-[8px] px-1 py-0.5 rounded pill-warning font-mono">scipy 미설치</span>
          )}
        </div>
      </div>

      {/* Multi-hop chains */}
      <div className="mb-2">
        <div className="ds-label text-[8px] mb-1 opacity-60">Multi-hop chains ({chains.length})</div>
        {chains.length === 0 ? (
          <EmptyState
            icon="🔗"
            title="multi-hop chain 미형성"
            hint="추가 인과 발견 시 자동 연결 (Granger F-test 기반)"
          />
        ) : (
          <div className="space-y-1 max-h-[200px] overflow-y-auto pr-1">
            {chains.slice(0, 8).map((chain, idx) => (
              <ChainRow key={idx} chain={chain} />
            ))}
          </div>
        )}
      </div>

      {/* Recent promotions */}
      <div className="border-t border-white/10 pt-2">
        <div className="ds-label text-[8px] mb-1 opacity-60">최근 promoted 인과 규칙 ({promotions.length})</div>
        <div className="space-y-1 max-h-[180px] overflow-y-auto pr-1">
          {promotions.length === 0 ? (
            <div className="ds-caption">아직 promotion 없음</div>
          ) : (
            promotions.slice(0, 6).map((rule) => <RuleRow key={rule.id} rule={rule} />)
          )}
        </div>
      </div>
    </GlassCard>
  );
}

function ChainRow({ chain }: { chain: { steps: CausalRule[]; total_strength: number } }) {
  return (
    <div className="px-2 py-1.5 rounded bg-white/[0.03] border-l-2 border-purple-400/40">
      <div className="flex items-center gap-1 flex-wrap">
        {chain.steps.map((step, i) => (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <span className="text-purple-300">→</span>}
            <span className="text-[9px] font-mono text-cyan-300">{step.cause_type}</span>
          </span>
        ))}
        <span className="text-[9px] text-purple-300">→</span>
        <span className="text-[9px] font-mono text-emerald-300">
          {chain.steps[chain.steps.length - 1].effect_type}
        </span>
      </div>
      <div className="ds-caption mt-0.5">
        chain length {chain.steps.length} · cumulative strength{' '}
        <span className="text-white/70 font-mono">{chain.total_strength.toFixed(3)}</span>
      </div>
    </div>
  );
}

function RuleRow({ rule }: { rule: CausalRule }) {
  const sigStrong = rule.strength >= 0.7;
  const colorCls = sigStrong ? 'text-emerald-300' : rule.strength >= 0.5 ? 'text-amber-300' : 'text-rose-300';
  return (
    <div className="px-2 py-1 rounded bg-white/[0.03] border-l-2 border-cyan-400/40">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[9px] font-mono text-cyan-300 font-bold">{rule.id}</span>
        <span className={`text-[9px] font-mono ${colorCls}`}>str {rule.strength.toFixed(3)}</span>
      </div>
      <div className="ds-caption truncate">
        <span className="text-white/80">{rule.cause_type}</span>
        <span className="text-purple-300 mx-1">→</span>
        <span className="text-white/80">{rule.effect_type}</span>
      </div>
      <div className="ds-caption">
        {rule.source_step}{rule.target_step ? ` → ${rule.target_step}` : ''}
        {rule.p_value !== undefined && ` · p=${rule.p_value.toExponential(1)}`}
        {rule.best_lag !== undefined && ` · lag=${rule.best_lag}`}
      </div>
    </div>
  );
}

/** 인과 규칙 리스트에서 multi-hop chain 추출 (effect → cause 매칭). */
function buildMultiHopChains(rules: CausalRule[]): { steps: CausalRule[]; total_strength: number }[] {
  if (rules.length < 2) return [];
  const byCause = new Map<string, CausalRule[]>();
  for (const r of rules) {
    const arr = byCause.get(r.cause_type) ?? [];
    arr.push(r);
    byCause.set(r.cause_type, arr);
  }
  const chains: { steps: CausalRule[]; total_strength: number }[] = [];
  for (const start of rules) {
    // start.effect → 다른 rule의 cause로 이어지는지
    const next = byCause.get(start.effect_type);
    if (!next || next.length === 0) continue;
    for (const cont of next) {
      if (cont.id === start.id) continue;
      chains.push({
        steps: [start, cont],
        total_strength: start.strength * cont.strength,
      });
      // 3-hop 시도
      const next2 = byCause.get(cont.effect_type);
      if (next2) {
        for (const cont2 of next2) {
          if (cont2.id === start.id || cont2.id === cont.id) continue;
          chains.push({
            steps: [start, cont, cont2],
            total_strength: start.strength * cont.strength * cont2.strength,
          });
        }
      }
    }
  }
  return chains.sort((a, b) => b.total_strength - a.total_strength).slice(0, 12);
}
