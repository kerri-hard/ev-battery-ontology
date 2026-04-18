'use client';

import type { EdgeData, StepPosition } from './types';
import { clamp } from './constants';

interface Props {
  edges: EdgeData[];
  stepPositions: Map<string, StepPosition>;
}

export function CrossAreaEdges({ edges, stepPositions }: Props) {
  const crossEdges = edges.filter(
    (e) =>
      (e.type === 'FEEDS_INTO' || e.type === 'PARALLEL_WITH') &&
      stepPositions.has(e.source) &&
      stepPositions.has(e.target),
  );

  if (crossEdges.length === 0) return null;

  return (
    <svg className="absolute inset-0 pointer-events-none z-10" style={{ overflow: 'visible' }}>
      <defs>
        <marker
          id="arrow-cyan"
          viewBox="0 0 6 6"
          refX="6"
          refY="3"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 6 3 L 0 6 z" fill="#00d2ff" opacity="0.95" />
        </marker>
        <marker
          id="arrow-violet"
          viewBox="0 0 6 6"
          refX="6"
          refY="3"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
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
        const baseOffset = clamp(Math.abs(endX - startX) * 0.38, 26, 88);
        const laneOffset = edge.type === 'PARALLEL_WITH' ? 10 : 0;
        const c1x = startX + (isForward ? baseOffset : -baseOffset);
        const c2x = endX - (isForward ? baseOffset : -baseOffset);
        const c1y = startY + laneOffset;
        const c2y = endY + laneOffset;
        const color = edge.type === 'FEEDS_INTO' ? '#00d2ff' : '#8b5cf6';
        const marker = edge.type === 'FEEDS_INTO' ? 'url(#arrow-cyan)' : 'url(#arrow-violet)';

        return (
          <path
            key={`${edge.source}-${edge.target}-${edge.type}-${i}`}
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
