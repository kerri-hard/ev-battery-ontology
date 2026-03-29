'use client';

import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useEngine } from '@/context/EngineContext';
import SparklineChart from '@/components/charts/SparklineChart';
import { apiUrl } from '@/lib/api';

/* ── Types ── */
interface StepData {
  id: string;
  name: string;
  area: string;
  yield: number;
  auto: string;
  oee: number;
  cycle: number;
  safety: string;
  equipment: string;
}
interface EdgeData { source: string; target: string; type: string; }
interface AlarmData { id: string; step_id: string; severity: string; message: string; }
interface CausalRuleData { id: string; name: string; strength: number; confirmations: number; }
interface FailureChainData { id: string; step_id: string; cause: string; successes: number; failures: number; }
interface NodeData { id: string; type: string; [k: string]: unknown; }
interface GraphAPI {
  nodes: NodeData[];
  edges: EdgeData[];
}
interface L3TrendPoint {
  iteration: number;
  timestamp: string;
  counts: {
    causes?: number;
    matched_by?: number;
    chain_uses?: number;
    has_cause?: number;
    has_pattern?: number;
  };
}

/* ── Constants ── */
const AREAS = [
  { id: 'PA-100', name: '셀 어셈블리', color: '#FF6B35', icon: '⚡' },
  { id: 'PA-200', name: '전장 조립', color: '#00B4D8', icon: '🔌' },
  { id: 'PA-300', name: '냉각 시스템', color: '#10b981', icon: '❄' },
  { id: 'PA-400', name: '인클로저', color: '#ef4444', icon: '🛡' },
  { id: 'PA-500', name: '최합조립/검사', color: '#f59e0b', icon: '✓' },
];
const L3_RELATION_TYPES = ['MATCHED_BY', 'CHAIN_USES', 'HAS_CAUSE', 'HAS_PATTERN'];
const MAX_L3_TREND = 30;

interface L3TrendHistory {
  causes: number[];
  matchedBy: number[];
  chainUses: number[];
  hasCause: number[];
  hasPattern: number[];
}

function yieldColor(y: number): string {
  if (y >= 0.995) return '#10b981';
  if (y >= 0.99) return '#f59e0b';
  return '#ef4444';
}


function autoLabel(a: string): { text: string; color: string } {
  if (a === '자동') return { text: 'AUTO', color: '#10b981' };
  if (a === '반자동') return { text: 'SEMI', color: '#f59e0b' };
  return { text: 'MANUAL', color: '#ef4444' };
}

/* ── Step Card ── */
function StepCard({ step, areaColor, alarm, isFlash, innerRef }: {
  step: StepData;
  areaColor: string;
  alarm?: AlarmData;
  isFlash: boolean;
  innerRef?: (el: HTMLDivElement | null) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const yc = yieldColor(step.yield);
  const auto = autoLabel(step.auto);

  return (
    <div
      ref={innerRef}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`relative rounded-lg transition-all duration-200 cursor-default
        ${isFlash ? 'animate-step-flash' : ''}
        ${alarm ? 'ring-1 ring-red-500/60' : ''}
      `}
      style={{
        background: hovered ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
        borderLeft: `3px solid ${areaColor}`,
        padding: '8px 10px',
      }}
    >
      {/* Alarm indicator */}
      {alarm && (
        <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-red-500 animate-pulse"
          title={alarm.message} />
      )}

      {/* Top row: ID + automation badge */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-mono text-white/40">{step.id}</span>
        <span className="text-[8px] font-bold px-1.5 py-0.5 rounded"
          style={{ color: auto.color, background: `${auto.color}15`, border: `1px solid ${auto.color}25` }}>
          {auto.text}
        </span>
      </div>

      {/* Name */}
      <div className="text-xs font-medium text-white/90 mb-1.5 truncate" title={step.name}>
        {step.name}
      </div>

      {/* Yield bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
          <div className="h-full rounded-full transition-all duration-500"
            style={{ width: `${step.yield * 100}%`, background: yc }} />
        </div>
        <span className="text-[10px] font-mono font-bold" style={{ color: yc }}>
          {(step.yield * 100).toFixed(1)}%
        </span>
      </div>

      {/* Hover detail */}
      {hovered && (
        <div className="mt-2 pt-2 border-t border-white/5 grid grid-cols-2 gap-x-3 gap-y-1">
          <div className="text-[9px] text-white/30">장비</div>
          <div className="text-[9px] text-white/70 truncate">{step.equipment}</div>
          <div className="text-[9px] text-white/30">OEE</div>
          <div className="text-[9px] text-white/70">{(step.oee * 100).toFixed(1)}%</div>
          <div className="text-[9px] text-white/30">사이클</div>
          <div className="text-[9px] text-white/70">{step.cycle}초</div>
          <div className="text-[9px] text-white/30">안전등급</div>
          <div className="text-[9px] font-bold" style={{
            color: step.safety === 'A' ? '#ef4444' : step.safety === 'B' ? '#f59e0b' : '#10b981',
          }}>{step.safety}</div>
        </div>
      )}
    </div>
  );
}

/* ── Area Column ── */
function AreaColumn({ area, steps, alarms, flashSteps, registerStepRef }: {
  area: typeof AREAS[0];
  steps: StepData[];
  alarms: AlarmData[];
  flashSteps: Set<string>;
  registerStepRef?: (stepId: string) => (el: HTMLDivElement | null) => void;
}) {
  const areaAlarms = alarms.filter(a => steps.some(s => s.id === a.step_id));
  const avgYield = steps.length > 0 ? steps.reduce((s, st) => s + st.yield, 0) / steps.length : 0;

  return (
    <div className="flex flex-col min-w-0">
      {/* Area header */}
      <div className="rounded-t-lg px-3 py-2 mb-1" style={{
        background: `linear-gradient(135deg, ${area.color}15, ${area.color}08)`,
        borderBottom: `2px solid ${area.color}40`,
      }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="text-sm">{area.icon}</span>
            <span className="text-xs font-bold" style={{ color: area.color }}>{area.name}</span>
          </div>
          {areaAlarms.length > 0 && (
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 animate-pulse">
              {areaAlarms.length} 알람
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-1">
          <div className="flex-1 h-1 rounded-full" style={{ background: `${area.color}15` }}>
            <div className="h-full rounded-full" style={{
              width: `${avgYield * 100}%`,
              background: area.color,
              opacity: 0.6,
            }} />
          </div>
          <span className="text-[9px] font-mono" style={{ color: area.color }}>
            {(avgYield * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Steps */}
      <div className="flex flex-col gap-1 flex-1 overflow-y-auto pr-0.5">
        {steps.sort((a, b) => a.id.localeCompare(b.id)).map(step => (
          <StepCard
            key={step.id}
            step={step}
            areaColor={area.color}
            alarm={alarms.find(a => a.step_id === step.id)}
            isFlash={flashSteps.has(step.id)}
            innerRef={registerStepRef ? registerStepRef(step.id) : undefined}
          />
        ))}
      </div>
    </div>
  );
}

interface StepPosition {
  left: number;
  top: number;
  width: number;
  height: number;
  cx: number;
  cy: number;
}

function clamp(num: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, num));
}

/* ── Cross-Area Edges (SVG overlay) ── */
function CrossAreaEdges({ edges, stepPositions }: {
  edges: EdgeData[]; stepPositions: Map<string, StepPosition>;
}) {
  const crossEdges = edges.filter(e =>
    (e.type === 'FEEDS_INTO' || e.type === 'PARALLEL_WITH') &&
    stepPositions.has(e.source) && stepPositions.has(e.target)
  );

  if (crossEdges.length === 0) return null;

  return (
    <svg className="absolute inset-0 pointer-events-none z-10" style={{ overflow: 'visible' }}>
      <defs>
        <marker id="arrow-cyan" viewBox="0 0 6 6" refX="6" refY="3" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 6 3 L 0 6 z" fill="#00d2ff" opacity="0.95" />
        </marker>
        <marker id="arrow-violet" viewBox="0 0 6 6" refX="6" refY="3" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 6 3 L 0 6 z" fill="#8b5cf6" opacity="0.95" />
        </marker>
        <filter id="edge-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {crossEdges.map((edge, i) => {
        const s = stepPositions.get(edge.source)!;
        const t = stepPositions.get(edge.target)!;
        const isForward = t.cx >= s.cx;
        const startX = isForward ? s.left + s.width : s.left;
        const endX = isForward ? t.left : t.left + t.width;
        const startY = s.cy;
        const endY = t.cy;
        const dx = endX - startX;
        const absDx = Math.abs(dx);
        const baseOffset = clamp(absDx * 0.38, 26, 88);
        const laneOffset = edge.type === 'PARALLEL_WITH' ? 10 : 0;
        const c1x = startX + (isForward ? baseOffset : -baseOffset);
        const c2x = endX - (isForward ? baseOffset : -baseOffset);
        const c1y = startY + laneOffset;
        const c2y = endY + laneOffset;
        const color = edge.type === 'FEEDS_INTO' ? '#00d2ff' : '#8b5cf6';
        const marker = edge.type === 'FEEDS_INTO' ? 'url(#arrow-cyan)' : 'url(#arrow-violet)';

        return (
          <path key={`${edge.source}-${edge.target}-${edge.type}-${i}`}
            d={`M ${startX} ${startY} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${endX} ${endY}`}
            fill="none"
            stroke={color}
            strokeWidth={2.4}
            strokeDasharray={edge.type === 'PARALLEL_WITH' ? '4 3' : undefined}
            opacity={0.92}
            filter="url(#edge-glow)"
            markerEnd={marker}
          />
        );
      })}
    </svg>
  );
}

/* ── Summary Bar ── */
function SummaryBar({ steps, alarms, edges, causalRules, failureChains }: {
  steps: StepData[];
  alarms: AlarmData[];
  edges: EdgeData[];
  causalRules: CausalRuleData[];
  failureChains: FailureChainData[];
}) {
  const totalYield = steps.reduce((p, s) => p * s.yield, 1);
  const lowYield = steps.filter(s => s.yield < 0.99).length;
  const autoCount = steps.filter(s => s.auto === '자동').length;
  const causesEdges = edges.filter(e => e.type === 'CAUSES').length;
  const matchedByEdges = edges.filter(e => e.type === 'MATCHED_BY').length;
  const chainUsesEdges = edges.filter(e => e.type === 'CHAIN_USES').length;
  const hasCauseEdges = edges.filter(e => e.type === 'HAS_CAUSE').length;
  const hasPatternEdges = edges.filter(e => e.type === 'HAS_PATTERN').length;
  const learnedRules = causalRules.filter(r => r.confirmations > 0).length;

  return (
    <div className="flex items-center gap-4 px-4 py-2 rounded-lg overflow-x-auto whitespace-nowrap" style={{
      background: 'rgba(255,255,255,0.02)',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
    }}>
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-cyan" />
        <span className="text-[10px] text-white/50">공정</span>
        <span className="text-xs font-mono font-bold text-white/80">{steps.length}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-white/20" />
        <span className="text-[10px] text-white/50">연결</span>
        <span className="text-xs font-mono font-bold text-white/80">{edges.length}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full" style={{ background: yieldColor(totalYield > 0.5 ? 0.99 : 0.98) }} />
        <span className="text-[10px] text-white/50">라인 수율</span>
        <span className="text-xs font-mono font-bold" style={{ color: yieldColor(totalYield > 0.91 ? 0.995 : totalYield > 0.88 ? 0.99 : 0.98) }}>
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
        <span className="text-xs font-mono text-white/60">{autoCount}/{steps.length}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-violet-400" />
        <span className="text-[10px] text-white/50">인과규칙</span>
        <span className="text-xs font-mono font-bold text-white/80">{causalRules.length}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
        <span className="text-[10px] text-white/50">실패체인</span>
        <span className="text-xs font-mono font-bold text-white/80">{failureChains.length}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-white/30">CAUSES</span>
        <span className="text-xs font-mono text-white/60">{causesEdges}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-white/30">MATCHED</span>
        <span className="text-xs font-mono text-white/60">{matchedByEdges}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-white/30">CHAIN_USES</span>
        <span className="text-xs font-mono text-white/60">{chainUsesEdges}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-white/30">HAS_CAUSE</span>
        <span className="text-xs font-mono text-white/60">{hasCauseEdges}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-white/30">HAS_PATTERN</span>
        <span className="text-xs font-mono text-white/60">{hasPatternEdges}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-white/30">학습된 규칙</span>
        <span className="text-xs font-mono text-emerald-300">{learnedRules}</span>
      </div>
    </div>
  );
}

function L3InsightsPanel({ causalRules, failureChains }: {
  causalRules: CausalRuleData[];
  failureChains: FailureChainData[];
}) {
  const topRules = [...causalRules]
    .sort((a, b) => b.confirmations - a.confirmations)
    .slice(0, 3);
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
                  <span className="text-white/80 truncate mr-2">{c.step_id} / {c.cause || 'unknown'}</span>
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

function L3RelationOverlay({ edges, nodes }: { edges: EdgeData[]; nodes: NodeData[] }) {
  const nodeMap = useMemo(
    () => new Map(nodes.map((n) => [n.id, n])),
    [nodes],
  );
  const links = useMemo(
    () =>
      edges
        .filter((e) => L3_RELATION_TYPES.includes(e.type))
        .slice(-10)
        .map((e) => {
          const s = nodeMap.get(e.source);
          const t = nodeMap.get(e.target);
          const sLabel = (s?.name as string) || (s?.step_id as string) || e.source;
          const tLabel = (t?.name as string) || (t?.cause as string) || (t?.step_id as string) || e.target;
          return {
            type: e.type,
            source: sLabel,
            target: tLabel,
          };
        }),
    [edges, nodeMap],
  );

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

function L3TrendPanel({ history }: { history: L3TrendHistory }) {
  const last = {
    causes: history.causes[history.causes.length - 1] ?? 0,
    matchedBy: history.matchedBy[history.matchedBy.length - 1] ?? 0,
    chainUses: history.chainUses[history.chainUses.length - 1] ?? 0,
    hasCause: history.hasCause[history.hasCause.length - 1] ?? 0,
    hasPattern: history.hasPattern[history.hasPattern.length - 1] ?? 0,
  };

  if (
    history.causes.length === 0 &&
    history.matchedBy.length === 0 &&
    history.chainUses.length === 0 &&
    history.hasCause.length === 0 &&
    history.hasPattern.length === 0
  ) {
    return null;
  }

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
        <div>
          <div className="text-[9px] text-white/50 mb-0.5">CAUSES ({last.causes})</div>
          <SparklineChart data={history.causes} color="#a78bfa" width={140} height={24} />
        </div>
        <div>
          <div className="text-[9px] text-white/50 mb-0.5">MATCHED_BY ({last.matchedBy})</div>
          <SparklineChart data={history.matchedBy} color="#22d3ee" width={140} height={24} />
        </div>
        <div>
          <div className="text-[9px] text-white/50 mb-0.5">CHAIN_USES ({last.chainUses})</div>
          <SparklineChart data={history.chainUses} color="#60a5fa" width={140} height={24} />
        </div>
        <div>
          <div className="text-[9px] text-white/50 mb-0.5">HAS_CAUSE ({last.hasCause})</div>
          <SparklineChart data={history.hasCause} color="#34d399" width={140} height={24} />
        </div>
        <div className="col-span-2">
          <div className="text-[9px] text-white/50 mb-0.5">HAS_PATTERN ({last.hasPattern})</div>
          <SparklineChart data={history.hasPattern} color="#fbbf24" width={290} height={24} />
        </div>
      </div>
    </div>
  );
}

/* ── Main Component ── */
function OntologyGraph({ className = '' }: { className?: string }) {
  const { state } = useEngine();
  const [steps, setSteps] = useState<StepData[]>([]);
  const [edges, setEdges] = useState<EdgeData[]>([]);
  const [alarms, setAlarms] = useState<AlarmData[]>([]);
  const [causalRules, setCausalRules] = useState<CausalRuleData[]>([]);
  const [failureChains, setFailureChains] = useState<FailureChainData[]>([]);
  const [nodes, setNodes] = useState<NodeData[]>([]);
  const [l3Trend, setL3Trend] = useState<L3TrendHistory>({
    causes: [],
    matchedBy: [],
    chainUses: [],
    hasCause: [],
    hasPattern: [],
  });
  const [flashSteps, setFlashSteps] = useState<Set<string>>(new Set());
  const prevIter = useRef(0);
  const stepRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const graphBodyRef = useRef<HTMLDivElement>(null);
  const [stepPositions, setStepPositions] = useState<Map<string, StepPosition>>(new Map());
  const registerStepRef = useCallback((stepId: string) => (el: HTMLDivElement | null) => {
    if (el) {
      stepRefs.current.set(stepId, el);
    } else {
      stepRefs.current.delete(stepId);
    }
  }, []);

  const loadPersistedL3Trend = useCallback(async () => {
    try {
      const resp = await fetch(apiUrl('/api/l3-trend'));
      if (!resp.ok) return;
      const data = await resp.json();
      const history = (data.history as L3TrendPoint[]) || [];
      if (history.length === 0) return;
      const sliced = history.slice(-MAX_L3_TREND);
      setL3Trend({
        causes: sliced.map((p) => Number(p.counts?.causes ?? 0)),
        matchedBy: sliced.map((p) => Number(p.counts?.matched_by ?? 0)),
        chainUses: sliced.map((p) => Number(p.counts?.chain_uses ?? 0)),
        hasCause: sliced.map((p) => Number(p.counts?.has_cause ?? 0)),
        hasPattern: sliced.map((p) => Number(p.counts?.has_pattern ?? 0)),
      });
    } catch {
      // ignore
    }
  }, []);

  const fetchGraph = useCallback(async () => {
    try {
      const resp = await fetch(apiUrl('/api/graph'));
      if (!resp.ok) return;
      const data: GraphAPI = await resp.json();

      const processSteps: StepData[] = data.nodes
        .filter(n => n.type === 'ProcessStep')
        .map(n => ({
          id: n.id, name: n.name as string,
          area: (n.area || n.area_id || '') as string,
          yield: (n.yield ?? n.yield_rate ?? 0.99) as number,
          auto: (n.auto ?? '자동') as string,
          oee: (n.oee ?? 0.85) as number,
          cycle: (n.cycle ?? n.cycle_time ?? 0) as number,
          safety: (n.safety ?? n.safety_level ?? 'C') as string,
          equipment: (n.equipment ?? '') as string,
        }));

      const activeAlarms: AlarmData[] = data.nodes
        .filter(n => n.type === 'Alarm')
        .map(n => ({
          id: n.id, step_id: n.step_id as string,
          severity: n.severity as string, message: (n.message ?? '') as string,
        }));

      const l3Rules: CausalRuleData[] = data.nodes
        .filter(n => n.type === 'CausalRule')
        .map(n => ({
          id: n.id,
          name: (n.name ?? '') as string,
          strength: Number(n.strength ?? 0),
          confirmations: Number(n.confirmations ?? 0),
        }));

      const l3Chains: FailureChainData[] = data.nodes
        .filter(n => n.type === 'FailureChain')
        .map(n => ({
          id: n.id,
          step_id: (n.step_id ?? '') as string,
          cause: (n.cause ?? '') as string,
          successes: Number(n.successes ?? 0),
          failures: Number(n.failures ?? 0),
        }));

      setSteps(processSteps);
      setNodes(data.nodes);
      setEdges(data.edges);
      setAlarms(activeAlarms);
      setCausalRules(l3Rules);
      setFailureChains(l3Chains);
    } catch { /* API unavailable */ }
  }, []);

  useEffect(() => {
    const history = (state.l3Trends || []) as unknown as L3TrendPoint[];
    if (history.length === 0) return;
    const sliced = history.slice(-MAX_L3_TREND);
    setL3Trend({
      causes: sliced.map((p) => Number(p.counts?.causes ?? 0)),
      matchedBy: sliced.map((p) => Number(p.counts?.matched_by ?? 0)),
      chainUses: sliced.map((p) => Number(p.counts?.chain_uses ?? 0)),
      hasCause: sliced.map((p) => Number(p.counts?.has_cause ?? 0)),
      hasPattern: sliced.map((p) => Number(p.counts?.has_pattern ?? 0)),
    });
  }, [state.l3Trends]);

  useEffect(() => {
    loadPersistedL3Trend();
    fetchGraph();
  }, [fetchGraph, loadPersistedL3Trend]);

  useEffect(() => {
    if (state.iteration !== prevIter.current && state.iteration > 0) {
      prevIter.current = state.iteration;
      fetchGraph();
    }
  }, [state.iteration, fetchGraph]);

  // Also refetch when healing iteration changes
  useEffect(() => {
    if (state.healing.iteration > 0) fetchGraph();
  }, [state.healing.iteration, fetchGraph]);

  // Flash affected steps
  useEffect(() => {
    const ri = state.healing.recentIncidents;
    if (ri.length > 0) {
      setFlashSteps(new Set(ri.map(i => i.step_id)));
      const t = setTimeout(() => setFlashSteps(new Set()), 3000);
      return () => clearTimeout(t);
    }
  }, [state.healing.recentIncidents]);

  const measureStepPositions = useCallback(() => {
    const container = graphBodyRef.current;
    if (!container) return;
    const cRect = container.getBoundingClientRect();
    const positions = new Map<string, StepPosition>();
    stepRefs.current.forEach((el, id) => {
      const r = el.getBoundingClientRect();
      const left = r.left - cRect.left;
      const top = r.top - cRect.top;
      positions.set(id, {
        left,
        top,
        width: r.width,
        height: r.height,
        cx: left + r.width / 2,
        cy: top + r.height / 2,
      });
    });
    setStepPositions(positions);
  }, []);

  // Track step positions for edge overlay (including scroll/resize)
  useEffect(() => {
    if (steps.length === 0 || !graphBodyRef.current) return;
    let raf = 0;
    const requestMeasure = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        measureStepPositions();
      });
    };
    requestMeasure();

    const container = graphBodyRef.current;
    const onResize = () => requestMeasure();
    window.addEventListener('resize', onResize);
    container.addEventListener('scroll', requestMeasure, true);

    const ro = new ResizeObserver(() => requestMeasure());
    ro.observe(container);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      container.removeEventListener('scroll', requestMeasure, true);
      ro.disconnect();
    };
  }, [steps, measureStepPositions]);

  // Group steps by area
  const grouped = AREAS.map(area => ({
    area,
    steps: steps.filter(s => s.area === area.id),
  }));

  if (steps.length === 0) {
    return (
      <div className={`glass flex items-center justify-center ${className}`}>
        <div className="text-center py-20">
          <div className="text-5xl mb-4 opacity-20">🏭</div>
          <div className="text-white/40 text-sm">엔진을 초기화하세요</div>
          <div className="text-white/20 text-xs mt-1">제어판에서 시작 버튼을 누르세요</div>
        </div>
      </div>
    );
  }

  return (
    <div className={`glass flex flex-col overflow-hidden relative ${className}`}>
      {/* Summary bar */}
      <SummaryBar
        steps={steps}
        alarms={alarms}
        edges={edges}
        causalRules={causalRules}
        failureChains={failureChains}
      />

      {/* 5 Area Columns */}
      <div ref={graphBodyRef} className="flex-1 grid grid-cols-5 gap-2 p-2 min-h-0 overflow-hidden relative">
        {/* Cross-area edge overlay */}
        <CrossAreaEdges edges={edges} stepPositions={stepPositions} />

        {grouped.map(({ area, steps: areaSteps }) => (
          <div key={area.id} className="min-h-0 overflow-hidden flex flex-col">
            <AreaColumn
              area={area}
              steps={areaSteps}
              alarms={alarms}
              flashSteps={flashSteps}
              registerStepRef={registerStepRef}
            />
          </div>
        ))}
        <L3RelationOverlay edges={edges} nodes={nodes} />
        <L3TrendPanel history={l3Trend} />
        <L3InsightsPanel causalRules={causalRules} failureChains={failureChains} />
      </div>
    </div>
  );
}

export default React.memo(OntologyGraph);
