'use client';

import React from 'react';

export interface GraphNode {
  id: string;
  type: string;
  name?: string;
  area?: string;
  yield?: number;
  auto?: string;
  oee?: number;
  cycle?: number;
  safety?: string;
  equipment?: string;
  sigma?: number;
  cost?: number;
  mtbf?: number;
  mttr?: number;
  category?: string;
  rpn?: number;
  message?: string;
  severity?: string;
  step_id?: string;
  sensor_type?: string;
}

interface GraphTooltipProps {
  node: GraphNode;
  x: number;
  y: number;
}

const areaNames: Record<string, string> = {
  'PA-100': '셀 입고/검사',
  'PA-200': '모듈 조립',
  'PA-300': '팩 조립',
  'PA-400': '전장/BMS',
  'PA-500': '최종 검사',
};

function TooltipRow({ label, value }: { label: string; value: string | number | undefined }) {
  if (value === undefined || value === null) return null;
  return (
    <div className="flex justify-between gap-4">
      <span className="text-[#8888aa] whitespace-nowrap">{label}</span>
      <span className="text-white font-mono text-right">{value}</span>
    </div>
  );
}

function ProcessStepTooltip({ node }: { node: GraphNode }) {
  return (
    <>
      <div className="text-xs font-bold text-cyan mb-1">{node.id}</div>
      <div className="text-[11px] text-white mb-2">{node.name}</div>
      <div className="space-y-0.5 text-[10px]">
        <TooltipRow label="공정영역" value={node.area ? `${node.area} ${areaNames[node.area] || ''}` : undefined} />
        <TooltipRow label="수율" value={node.yield !== undefined ? `${(node.yield * 100).toFixed(2)}%` : undefined} />
        <TooltipRow label="자동화" value={node.auto} />
        <TooltipRow label="장비" value={node.equipment} />
        <TooltipRow label="안전등급" value={node.safety} />
        <TooltipRow label="OEE" value={node.oee !== undefined ? `${(node.oee * 100).toFixed(1)}%` : undefined} />
        <TooltipRow label="시그마" value={node.sigma !== undefined ? node.sigma.toFixed(2) : undefined} />
        <TooltipRow label="사이클(s)" value={node.cycle} />
      </div>
    </>
  );
}

function EquipmentTooltip({ node }: { node: GraphNode }) {
  return (
    <>
      <div className="text-xs font-bold text-[#6b7280] mb-1">{node.id}</div>
      <div className="text-[11px] text-white mb-2">{node.name}</div>
      <div className="space-y-0.5 text-[10px]">
        <TooltipRow label="비용" value={node.cost !== undefined ? `$${node.cost.toLocaleString()}` : undefined} />
        <TooltipRow label="MTBF(h)" value={node.mtbf} />
        <TooltipRow label="MTTR(h)" value={node.mttr} />
      </div>
    </>
  );
}

function DefectModeTooltip({ node }: { node: GraphNode }) {
  return (
    <>
      <div className="text-xs font-bold text-[#f59e0b] mb-1">{node.id}</div>
      <div className="text-[11px] text-white mb-2">{node.name}</div>
      <div className="space-y-0.5 text-[10px]">
        <TooltipRow label="유형" value={node.category} />
        <TooltipRow label="RPN" value={node.rpn} />
      </div>
    </>
  );
}

function AlarmTooltip({ node }: { node: GraphNode }) {
  return (
    <>
      <div className="text-xs font-bold text-[#ef4444] mb-1">{node.id}</div>
      <div className="text-[11px] text-white mb-2">{node.message}</div>
      <div className="space-y-0.5 text-[10px]">
        <TooltipRow label="심각도" value={node.severity} />
        <TooltipRow label="공정" value={node.step_id} />
        <TooltipRow label="센서" value={node.sensor_type} />
      </div>
    </>
  );
}

function GraphTooltip({ node, x, y }: GraphTooltipProps) {
  const tooltipContent = () => {
    switch (node.type) {
      case 'ProcessStep': return <ProcessStepTooltip node={node} />;
      case 'Equipment': return <EquipmentTooltip node={node} />;
      case 'DefectMode': return <DefectModeTooltip node={node} />;
      case 'Alarm': return <AlarmTooltip node={node} />;
      default: return (
        <>
          <div className="text-xs font-bold text-white mb-1">{node.id}</div>
          <div className="text-[11px] text-[#8888aa]">{node.type}</div>
        </>
      );
    }
  };

  return (
    <div
      className="absolute z-50 pointer-events-none"
      style={{
        left: x,
        top: y,
        transform: 'translate(-50%, -100%) translateY(-12px)',
      }}
    >
      <div
        className="px-3 py-2 rounded-lg text-xs min-w-[180px] max-w-[260px]"
        style={{
          background: 'rgba(12, 12, 29, 0.95)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          backdropFilter: 'blur(20px)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
        }}
      >
        {tooltipContent()}
      </div>
    </div>
  );
}

export default React.memo(GraphTooltip);
