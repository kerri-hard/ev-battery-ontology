'use client';

import { useCallback, useEffect, useState } from 'react';
import { apiUrl } from '@/lib/api';
import type {
  StepData,
  EdgeData,
  AlarmData,
  CausalRuleData,
  FailureChainData,
  NodeData,
  GraphAPI,
  L3TrendHistory,
  L3TrendPoint,
} from './types';
import { EMPTY_L3_TREND, MAX_L3_TREND } from './constants';

interface OntologyData {
  steps: StepData[];
  edges: EdgeData[];
  alarms: AlarmData[];
  causalRules: CausalRuleData[];
  failureChains: FailureChainData[];
  nodes: NodeData[];
  l3Trend: L3TrendHistory;
  refetch: () => Promise<void>;
  setL3TrendFromState: (points: L3TrendPoint[]) => void;
}

/** /api/graph + /api/l3-trend 폴링 + 메모리 상태 관리. */
export function useOntologyData(): OntologyData {
  const [steps, setSteps] = useState<StepData[]>([]);
  const [edges, setEdges] = useState<EdgeData[]>([]);
  const [alarms, setAlarms] = useState<AlarmData[]>([]);
  const [causalRules, setCausalRules] = useState<CausalRuleData[]>([]);
  const [failureChains, setFailureChains] = useState<FailureChainData[]>([]);
  const [nodes, setNodes] = useState<NodeData[]>([]);
  const [l3Trend, setL3Trend] = useState<L3TrendHistory>(EMPTY_L3_TREND);

  const setL3TrendFromState = useCallback((points: L3TrendPoint[]) => {
    if (points.length === 0) return;
    const sliced = points.slice(-MAX_L3_TREND);
    setL3Trend({
      causes: sliced.map((p) => Number(p.counts?.causes ?? 0)),
      matchedBy: sliced.map((p) => Number(p.counts?.matched_by ?? 0)),
      chainUses: sliced.map((p) => Number(p.counts?.chain_uses ?? 0)),
      hasCause: sliced.map((p) => Number(p.counts?.has_cause ?? 0)),
      hasPattern: sliced.map((p) => Number(p.counts?.has_pattern ?? 0)),
    });
  }, []);

  const loadPersistedL3Trend = useCallback(async () => {
    try {
      const resp = await fetch(apiUrl('/api/l3-trend'));
      if (!resp.ok) return;
      const data = await resp.json();
      setL3TrendFromState((data.history as L3TrendPoint[]) || []);
    } catch {
      // ignore
    }
  }, [setL3TrendFromState]);

  const refetch = useCallback(async () => {
    try {
      const resp = await fetch(apiUrl('/api/graph'));
      if (!resp.ok) return;
      const data: GraphAPI = await resp.json();

      setSteps(extractSteps(data.nodes));
      setNodes(data.nodes);
      setEdges(data.edges);
      setAlarms(extractAlarms(data.nodes));
      setCausalRules(extractCausalRules(data.nodes));
      setFailureChains(extractFailureChains(data.nodes));
    } catch {
      // API unavailable
    }
  }, []);

  useEffect(() => {
    loadPersistedL3Trend();
    refetch();
  }, [refetch, loadPersistedL3Trend]);

  return {
    steps,
    edges,
    alarms,
    causalRules,
    failureChains,
    nodes,
    l3Trend,
    refetch,
    setL3TrendFromState,
  };
}

function extractSteps(nodes: NodeData[]): StepData[] {
  return nodes
    .filter((n) => n.type === 'ProcessStep')
    .map((n) => ({
      id: n.id,
      name: n.name as string,
      area: (n.area || n.area_id || '') as string,
      yield: (n.yield ?? n.yield_rate ?? 0.99) as number,
      auto: (n.auto ?? '자동') as string,
      oee: (n.oee ?? 0.85) as number,
      cycle: (n.cycle ?? n.cycle_time ?? 0) as number,
      safety: (n.safety ?? n.safety_level ?? 'C') as string,
      equipment: (n.equipment ?? '') as string,
    }));
}

function extractAlarms(nodes: NodeData[]): AlarmData[] {
  return nodes
    .filter((n) => n.type === 'Alarm')
    .map((n) => ({
      id: n.id,
      step_id: n.step_id as string,
      severity: n.severity as string,
      message: (n.message ?? '') as string,
    }));
}

function extractCausalRules(nodes: NodeData[]): CausalRuleData[] {
  return nodes
    .filter((n) => n.type === 'CausalRule')
    .map((n) => ({
      id: n.id,
      name: (n.name ?? '') as string,
      strength: Number(n.strength ?? 0),
      confirmations: Number(n.confirmations ?? 0),
    }));
}

function extractFailureChains(nodes: NodeData[]): FailureChainData[] {
  return nodes
    .filter((n) => n.type === 'FailureChain')
    .map((n) => ({
      id: n.id,
      step_id: (n.step_id ?? '') as string,
      cause: (n.cause ?? '') as string,
      successes: Number(n.successes ?? 0),
      failures: Number(n.failures ?? 0),
    }));
}
