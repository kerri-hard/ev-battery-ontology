'use client';

import { useEngine } from '@/context/EngineContext';
import MetricCard from '@/components/metrics/MetricCard';

export default function MetricsBar() {
  const { state } = useEngine();
  const { metrics, prevMetrics, metricsHistory } = state;

  const nodeDelta = metrics && prevMetrics
    ? metrics.total_nodes - prevMetrics.total_nodes
    : null;

  const edgeDelta = metrics && prevMetrics
    ? metrics.total_edges - prevMetrics.total_edges
    : null;

  const yieldDelta = metrics && prevMetrics
    ? (metrics.line_yield - prevMetrics.line_yield) * 100
    : null;

  const completeDelta = metrics && prevMetrics
    ? metrics.completeness_score - prevMetrics.completeness_score
    : null;

  return (
    <div className="grid grid-cols-4 gap-3">
      <MetricCard
        label="총 노드"
        value={metrics ? String(metrics.total_nodes) : '—'}
        delta={nodeDelta}
        sparkData={metricsHistory.nodes}
        sparkColor="#00d2ff"
      />
      <MetricCard
        label="총 엣지"
        value={metrics ? String(metrics.total_edges) : '—'}
        delta={edgeDelta}
        sparkData={metricsHistory.edges}
        sparkColor="#a855f7"
      />
      <MetricCard
        label="라인 수율"
        value={metrics ? `${(metrics.line_yield * 100).toFixed(1)}%` : '—'}
        delta={yieldDelta}
        sparkData={metricsHistory.yield}
        sparkColor="#06d6a0"
      />
      <MetricCard
        label="완성도"
        value={metrics ? metrics.completeness_score.toFixed(1) : '—'}
        delta={completeDelta}
        sparkData={metricsHistory.completeness}
        sparkColor="#ffd166"
      />
    </div>
  );
}
