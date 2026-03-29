'use client';

import SparklineChart from '@/components/charts/SparklineChart';

interface MetricCardProps {
  label: string;
  value: string;
  delta: number | null;
  sparkData: number[];
  sparkColor: string;
}

export default function MetricCard({ label, value, delta, sparkData, sparkColor }: MetricCardProps) {
  return (
    <div className="glass p-3 flex flex-col gap-1.5">
      <span className="text-text-dim text-xs">{label}</span>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold font-mono text-white">{value}</span>
        {delta !== null && delta !== 0 && (
          <span className={`text-xs font-mono ${delta > 0 ? 'text-neon-green' : 'text-neon-red'}`}>
            {delta > 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}
          </span>
        )}
      </div>
      <SparklineChart data={sparkData} color={sparkColor} />
    </div>
  );
}
