'use client';

import type { StepData, AlarmData, EdgeData, CausalRuleData, FailureChainData } from './types';
import { yieldColor } from './constants';

interface Props {
  steps: StepData[];
  alarms: AlarmData[];
  edges: EdgeData[];
  causalRules: CausalRuleData[];
  failureChains: FailureChainData[];
}

export function SummaryBar({ steps, alarms, edges, causalRules, failureChains }: Props) {
  const totalYield = steps.reduce((p, s) => p * s.yield, 1);
  const lowYield = steps.filter((s) => s.yield < 0.99).length;
  const autoCount = steps.filter((s) => s.auto === '자동').length;

  const edgeCounts = {
    causes: edges.filter((e) => e.type === 'CAUSES').length,
    matchedBy: edges.filter((e) => e.type === 'MATCHED_BY').length,
    chainUses: edges.filter((e) => e.type === 'CHAIN_USES').length,
    hasCause: edges.filter((e) => e.type === 'HAS_CAUSE').length,
    hasPattern: edges.filter((e) => e.type === 'HAS_PATTERN').length,
  };
  const learnedRules = causalRules.filter((r) => r.confirmations > 0).length;

  const yieldBucket = totalYield > 0.91 ? 0.995 : totalYield > 0.88 ? 0.99 : 0.98;

  return (
    <div
      className="flex items-center gap-4 px-4 py-2 rounded-lg overflow-x-auto whitespace-nowrap"
      style={{
        background: 'rgba(255,255,255,0.02)',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      <Stat color="bg-cyan" label="공정" value={steps.length} />
      <Stat color="bg-white/20" label="연결" value={edges.length} />

      <div className="flex items-center gap-1.5">
        <div
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: yieldColor(totalYield > 0.5 ? 0.99 : 0.98) }}
        />
        <span className="text-[10px] text-white/50">라인 수율</span>
        <span className="text-xs font-mono font-bold" style={{ color: yieldColor(yieldBucket) }}>
          {(totalYield * 100).toFixed(2)}%
        </span>
      </div>

      {lowYield > 0 && (
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
          <span className="text-[10px] text-white/50">저수율</span>
          <span className="text-xs font-mono font-bold text-red-400">{lowYield}개</span>
        </div>
      )}

      {alarms.length > 0 && (
        <div className="flex items-center gap-1.5 ml-auto">
          <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
          <span className="text-[10px] text-red-400 font-bold">{alarms.length} 활성 알람</span>
        </div>
      )}

      <div className="flex items-center gap-1.5 ml-auto">
        <span className="text-[10px] text-white/30">자동화</span>
        <span className="text-xs font-mono text-white/60">
          {autoCount}/{steps.length}
        </span>
      </div>

      <Stat color="bg-violet-400" label="인과규칙" value={causalRules.length} />
      <Stat color="bg-indigo-400" label="실패체인" value={failureChains.length} />

      <EdgeStat label="CAUSES" value={edgeCounts.causes} />
      <EdgeStat label="MATCHED" value={edgeCounts.matchedBy} />
      <EdgeStat label="CHAIN_USES" value={edgeCounts.chainUses} />
      <EdgeStat label="HAS_CAUSE" value={edgeCounts.hasCause} />
      <EdgeStat label="HAS_PATTERN" value={edgeCounts.hasPattern} />

      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-white/30">학습된 규칙</span>
        <span className="text-xs font-mono text-emerald-300">{learnedRules}</span>
      </div>
    </div>
  );
}

function Stat({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-1.5 h-1.5 rounded-full ${color}`} />
      <span className="text-[10px] text-white/50">{label}</span>
      <span className="text-xs font-mono font-bold text-white/80">{value}</span>
    </div>
  );
}

function EdgeStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] text-white/30">{label}</span>
      <span className="text-xs font-mono text-white/60">{value}</span>
    </div>
  );
}
