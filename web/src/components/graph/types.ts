export interface StepData {
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

export interface EdgeData {
  source: string;
  target: string;
  type: string;
}

export interface AlarmData {
  id: string;
  step_id: string;
  severity: string;
  message: string;
}

export interface CausalRuleData {
  id: string;
  name: string;
  strength: number;
  confirmations: number;
}

export interface FailureChainData {
  id: string;
  step_id: string;
  cause: string;
  successes: number;
  failures: number;
}

export interface NodeData {
  id: string;
  type: string;
  [k: string]: unknown;
}

export interface GraphAPI {
  nodes: NodeData[];
  edges: EdgeData[];
}

export interface L3TrendPoint {
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

export interface L3TrendHistory {
  causes: number[];
  matchedBy: number[];
  chainUses: number[];
  hasCause: number[];
  hasPattern: number[];
}

export interface StepPosition {
  left: number;
  top: number;
  width: number;
  height: number;
  cx: number;
  cy: number;
}

export interface Area {
  id: string;
  name: string;
  color: string;
  icon: string;
}
