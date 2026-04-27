'use client';

import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import SparklineChart from '@/components/charts/SparklineChart';

interface StrategyRow {
  name: string;
  description?: string;
  fitness: number;
  executions: number;
  improvements: number;
  success_rate: number;
  active: boolean;
  cooldown: number;
}

interface RecentCycle {
  cycle: number;
  strategies_run?: number;
  strategies_improved?: number;
  overall_fitness: number;
  best_strategy?: string;
  best_fitness?: number;
}

/** EvolutionAgent 8 전략의 fitness 진화 timeline + 활성/쿨다운 상태 */
export default function EvolutionTimeline() {
  const { state } = useEngine();
  const ev = state.phase4 ? (state.phase4 as unknown as { evolution_agent?: { strategies?: StrategyRow[]; recent_cycles?: RecentCycle[]; cycle_count?: number; trust_score?: number } }).evolution_agent : undefined;

  if (!ev || !ev.strategies) {
    return (
      <GlassCard>
        <div className="text-[10px] text-white/40">EvolutionAgent 데이터 대기 중...</div>
      </GlassCard>
    );
  }

  const strategies = ev.strategies ?? [];
  const cycles = (ev.recent_cycles ?? []).slice(-10);
  const overallSeries = cycles.map((c) => c.overall_fitness);
  const sortedStrategies = [...strategies].sort((a, b) => b.fitness - a.fitness);

  return (
    <GlassCard className="p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold text-white/60 uppercase tracking-wider">
          Evolution Timeline — 자가 진화 ({strategies.length} 전략)
        </span>
        <span className="text-[9px] text-white/40 font-mono">
          cycle {ev.cycle_count} · trust {ev.trust_score?.toFixed(2)}
        </span>
      </div>

      {/* 전체 fitness sparkline */}
      <div className="mb-3 px-2 py-1.5 rounded bg-white/5">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] text-white/60 font-bold">overall_fitness</span>
          <span className="text-[10px] font-mono text-emerald-300">
            {cycles.length > 0 ? overallSeries[overallSeries.length - 1].toFixed(4) : '-'}
          </span>
        </div>
        {overallSeries.length > 1 ? (
          <SparklineChart data={overallSeries} color="#34d399" width={520} height={28} />
        ) : (
          <div className="text-[8px] text-white/30">사이클 누적 대기...</div>
        )}
      </div>

      {/* 전략별 fitness 바 */}
      <div className="space-y-1 max-h-[300px] overflow-y-auto pr-1">
        {sortedStrategies.map((s) => (
          <StrategyRow key={s.name} strategy={s} />
        ))}
      </div>

      {/* 최근 사이클 요약 */}
      {cycles.length > 0 && (
        <div className="mt-3 pt-2 border-t border-white/10">
          <div className="text-[9px] text-white/50 mb-1">최근 사이클 (best strategy)</div>
          <div className="space-y-0.5 max-h-[80px] overflow-y-auto">
            {cycles.slice(-5).reverse().map((c) => (
              <div
                key={c.cycle}
                className="grid grid-cols-[40px_1fr_60px_50px] gap-2 text-[9px] font-mono"
              >
                <span className="text-white/40">#{c.cycle}</span>
                <span className="text-cyan-300 truncate">{c.best_strategy ?? '-'}</span>
                <span className="text-emerald-300 text-right">
                  {c.best_fitness?.toFixed(4) ?? '-'}
                </span>
                <span className="text-white/40 text-right">
                  {c.strategies_improved}/{c.strategies_run}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </GlassCard>
  );
}

function StrategyRow({ strategy }: { strategy: StrategyRow }) {
  const isHigh = strategy.fitness >= 0.6;
  const isLow = strategy.fitness < 0.5;
  const color = isHigh ? 'bg-emerald-400' : isLow ? 'bg-rose-400' : 'bg-amber-400';

  return (
    <div className="grid grid-cols-[1fr_120px_60px_30px] gap-2 items-center px-1.5 py-1 hover:bg-white/5 rounded">
      <div className="min-w-0">
        <div className="text-[10px] font-bold text-white/80 truncate" title={strategy.description}>
          {strategy.name}
        </div>
        <div className="text-[8px] text-white/40 font-mono">
          {strategy.executions} exec · {strategy.improvements} improved · success {(strategy.success_rate * 100).toFixed(0)}%
        </div>
      </div>
      <div className="h-1.5 rounded bg-white/10 overflow-hidden relative">
        <div
          className={`absolute h-full ${color}`}
          style={{ width: `${Math.max(0, Math.min(1, strategy.fitness)) * 100}%` }}
        />
        {/* 0.5 baseline marker */}
        <div className="absolute top-0 bottom-0 w-px bg-white/40" style={{ left: '50%' }} />
      </div>
      <div
        className={`text-[10px] font-mono text-right ${isHigh ? 'text-emerald-300' : isLow ? 'text-rose-300' : 'text-amber-300'}`}
      >
        {strategy.fitness.toFixed(3)}
      </div>
      <div className="text-center">
        {strategy.active ? (
          <span className="text-[8px] text-emerald-400">●</span>
        ) : (
          <span className="text-[8px] text-amber-400" title={`cooldown ${strategy.cooldown}`}>
            ⏸
          </span>
        )}
      </div>
    </div>
  );
}
