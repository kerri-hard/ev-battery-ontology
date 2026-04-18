'use client';

import { useMemo } from 'react';
import SparklineChart from '@/components/charts/SparklineChart';
import type {
  CausalRuleData,
  FailureChainData,
  EdgeData,
  NodeData,
  L3TrendHistory,
} from './types';
import { L3_RELATION_TYPES } from './constants';

export function L3InsightsPanel({
  causalRules,
  failureChains,
}: {
  causalRules: CausalRuleData[];
  failureChains: FailureChainData[];
}) {
  const topRules = [...causalRules].sort((a, b) => b.confirmations - a.confirmations).slice(0, 3);
  const topChains = [...failureChains]
    .sort((a, b) => {
      const aRate = a.successes / Math.max(a.successes + a.failures, 1);
      const bRate = b.successes / Math.max(b.successes + b.failures, 1);
      return bRate - aRate;
    })
    .slice(0, 3);

  if (topRules.length === 0 && topChains.length === 0) return null;

  return (
    <div
      className="absolute right-3 bottom-3 z-20 w-[320px] rounded-lg p-3"
      style={{
        background: 'rgba(8, 10, 24, 0.88)',
        border: '1px solid rgba(99, 102, 241, 0.25)',
        backdropFilter: 'blur(14px)',
      }}
    >
      <div className="text-[10px] font-bold text-indigo-300 uppercase tracking-wider mb-2">
        L3 Causal Insights
      </div>
      <div className="space-y-2">
        <div>
          <div className="text-[10px] text-white/60 mb-1">Top Learned Rules</div>
          {topRules.length === 0 ? (
            <div className="text-[10px] text-white/30">학습 데이터 없음</div>
          ) : (
            topRules.map((r) => (
              <div key={r.id} className="flex items-center justify-between text-[10px] py-0.5">
                <span className="text-white/80 truncate mr-2">{r.name}</span>
                <span className="font-mono text-emerald-300">{r.confirmations}</span>
              </div>
            ))
          )}
        </div>
        <div>
          <div className="text-[10px] text-white/60 mb-1">Top Failure Chains</div>
          {topChains.length === 0 ? (
            <div className="text-[10px] text-white/30">실패 체인 없음</div>
          ) : (
            topChains.map((c) => {
              const rate = c.successes / Math.max(c.successes + c.failures, 1);
              return (
                <div key={c.id} className="flex items-center justify-between text-[10px] py-0.5">
                  <span className="text-white/80 truncate mr-2">
                    {c.step_id} / {c.cause || 'unknown'}
                  </span>
                  <span className="font-mono text-cyan">{(rate * 100).toFixed(0)}%</span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export function L3RelationOverlay({ edges, nodes }: { edges: EdgeData[]; nodes: NodeData[] }) {
  const links = useMemo(() => {
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    return edges
      .filter((e) => L3_RELATION_TYPES.includes(e.type))
      .slice(-10)
      .map((e) => {
        const s = nodeMap.get(e.source);
        const t = nodeMap.get(e.target);
        const sLabel = (s?.name as string) || (s?.step_id as string) || e.source;
        const tLabel = (t?.name as string) || (t?.cause as string) || (t?.step_id as string) || e.target;
        return { type: e.type, source: sLabel, target: tLabel };
      });
  }, [edges, nodes]);

  if (links.length === 0) return null;

  return (
    <div
      className="absolute left-3 bottom-3 z-20 w-[360px] rounded-lg p-3"
      style={{
        background: 'rgba(8, 10, 24, 0.88)',
        border: '1px solid rgba(0, 210, 255, 0.2)',
        backdropFilter: 'blur(14px)',
      }}
    >
      <div className="text-[10px] font-bold text-cyan uppercase tracking-wider mb-2">
        L3 Relation Flow
      </div>
      <div className="space-y-1 max-h-[180px] overflow-y-auto pr-1">
        {links.map((l, idx) => (
          <div key={`${l.type}-${idx}`} className="text-[10px] flex items-center gap-2">
            <span className="text-white/70 truncate">{l.source}</span>
            <span className="text-cyan/70 font-mono">{l.type}</span>
            <span className="text-white/70 truncate">{l.target}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function L3TrendPanel({ history }: { history: L3TrendHistory }) {
  const isEmpty =
    history.causes.length === 0 &&
    history.matchedBy.length === 0 &&
    history.chainUses.length === 0 &&
    history.hasCause.length === 0 &&
    history.hasPattern.length === 0;

  if (isEmpty) return null;

  const last = {
    causes: history.causes[history.causes.length - 1] ?? 0,
    matchedBy: history.matchedBy[history.matchedBy.length - 1] ?? 0,
    chainUses: history.chainUses[history.chainUses.length - 1] ?? 0,
    hasCause: history.hasCause[history.hasCause.length - 1] ?? 0,
    hasPattern: history.hasPattern[history.hasPattern.length - 1] ?? 0,
  };

  return (
    <div
      className="absolute left-[390px] bottom-3 z-20 w-[320px] rounded-lg p-3"
      style={{
        background: 'rgba(8, 10, 24, 0.88)',
        border: '1px solid rgba(16, 185, 129, 0.2)',
        backdropFilter: 'blur(14px)',
      }}
    >
      <div className="text-[10px] font-bold text-emerald-300 uppercase tracking-wider mb-2">
        L3 Trend
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-2">
        <TrendCell label={`CAUSES (${last.causes})`} data={history.causes} color="#a78bfa" />
        <TrendCell label={`MATCHED_BY (${last.matchedBy})`} data={history.matchedBy} color="#22d3ee" />
        <TrendCell label={`CHAIN_USES (${last.chainUses})`} data={history.chainUses} color="#60a5fa" />
        <TrendCell label={`HAS_CAUSE (${last.hasCause})`} data={history.hasCause} color="#34d399" />
        <div className="col-span-2">
          <div className="text-[9px] text-white/50 mb-0.5">HAS_PATTERN ({last.hasPattern})</div>
          <SparklineChart data={history.hasPattern} color="#fbbf24" width={290} height={24} />
        </div>
      </div>
    </div>
  );
}

function TrendCell({ label, data, color }: { label: string; data: number[]; color: string }) {
  return (
    <div>
      <div className="text-[9px] text-white/50 mb-0.5">{label}</div>
      <SparklineChart data={data} color={color} width={140} height={24} />
    </div>
  );
}
