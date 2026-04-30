// ── Graph Data ──

export interface ProcessArea {
  id: string;
  name: string;
  color: string;
  cycle: number;
  steps: number;
}

export interface ProcessStep {
  id: string;
  name: string;
  area: string;
  yield: number;
  auto: string;
  oee: number;
  cycle: number;
  safety: string;
  equipment: string;
  sigma: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface MaterialLink {
  step_id: string;
  mat_id: string;
  mat_name: string;
  category: string;
  cost: number;
  supplier: string;
  qty: number;
}

export interface QualityLink {
  step_id: string;
  spec_id: string;
  spec_name: string;
  type: string;
  unit: string;
  min: number;
  max: number;
}

export interface GraphData {
  areas: ProcessArea[];
  steps: ProcessStep[];
  edges: GraphEdge[];
  materials: MaterialLink[];
  quality: QualityLink[];
}

// ── Metrics ──

export interface Metrics {
  total_nodes: number;
  total_edges: number;
  density: number;
  line_yield: number;
  avg_yield: number;
  min_yield: number;
  avg_oee: number;
  avg_sigma: number;
  completeness_score: number;
  spec_coverage: number;
  material_coverage: number;
  defect_coverage: number;
  maintenance_coverage: number;
  inspection_coverage: number;
  cross_area_edges: number;
  automation_distribution: Record<string, number>;
  edge_counts: Record<string, number>;
  node_ProcessArea: number;
  node_ProcessStep: number;
  node_Equipment: number;
  node_Material: number;
  node_QualitySpec: number;
  node_DefectMode: number;
  node_AutomationPlan: number;
  node_MaintenancePlan: number;
}

// ── Agent ──

export interface Agent {
  name: string;
  role: string;
  description: string;
  trust: number;
  success_rate: number;
  proposals: number;
}

// ── Debate ──

export interface VoteSummary {
  proposal: string;
  action: string;
  agent: string;
  score: number;
  votes: Record<string, number>;
}

// ── Skill ──

export interface SkillStat {
  calls: number;
  successes: number;
  avg_impact: number;
  category: string;
}

export type SkillStats = Record<string, SkillStat>;

// ── Evaluation ──

export interface MetricDelta {
  label: string;
  prev: number;
  curr: number;
  change: number;
  pct: number;
  improved: boolean;
}

export interface Evaluation {
  deltas: Record<string, MetricDelta>;
  improvement_rate: number;
  converged: boolean;
  score_delta: number;
}

// ── History ──

export interface HistoryEntry {
  iteration: number;
  pre: Metrics;
  post: Metrics;
  proposals: number;
  approved: number;
  applied: number;
  failed: number;
  evaluation: Evaluation;
  trust: Record<string, number>;
}

// ── Phase ──

export type Phase =
  | 'observe'
  | 'propose'
  | 'debate'
  | 'apply'
  | 'evaluate'
  | 'learn'
  | 'skip'
  | 'sense'
  | 'detect'
  | 'diagnose'
  | 'recover'
  | 'verify'
  | 'learn_healing';

// ── Debate State ──

export interface ProposeDoneData {
  iteration: number;
  total: number;
  by_agent: Record<string, number>;
  by_type: Record<string, number>;
}

export interface DebateDoneData {
  iteration: number;
  total_proposals: number;
  critiques: number;
  approved_count: number;
  rejected_count: number;
  top_votes: VoteSummary[];
  threshold: number;
}

export interface ApplyDetail {
  id: string;
  action: string;
  skill: string;
  agent: string;
  status: string;
  error?: string;
}

export interface ApplyDoneData {
  iteration: number;
  applied: number;
  failed: number;
  details: ApplyDetail[];
}

export interface LearningLogEntry {
  agent: string;
  delta: number;
  trust: number;
  reason: string;
}

export interface LearnDoneData {
  iteration: number;
  learning_log: LearningLogEntry[];
  agents: Agent[];
}

export interface DebateState {
  proposals: ProposeDoneData | null;
  votes: DebateDoneData | null;
  applied: ApplyDoneData | null;
  evaluation: { iteration: number; pre: Metrics; post: Metrics; evaluation: Evaluation } | null;
  learning: LearnDoneData | null;
}

// ── Log ──

export interface LogEntry {
  ts: string;
  phase: Phase | null;
  message: string;
}

// ── Metrics History ──

export interface MetricsHistory {
  nodes: number[];
  edges: number[];
  yield: number[];
  completeness: number[];
}

// ── Healing (v4) ──

export interface ExcludedRCACandidate {
  cause_type: string;
  cause_name?: string;
  confidence?: number;
  rca_score_breakdown?: Record<string, number>;
  exclusion_reason?: string;
}

export interface HealingIncident {
  id?: string;
  iteration?: number;
  step_id: string;
  cause?: string;
  action?: string;
  top_cause?: string;
  action_type?: string;
  severity?: string;
  anomaly_type?: string;
  confidence?: number;
  causal_chain?: string;
  history_matched?: boolean;
  matched_chain_id?: string;
  candidates_count?: number;
  causal_chains_found?: number;
  analysis_method?: string;
  matched_pattern_id?: string;
  matched_pattern_type?: string;
  evidence_refs?: string[];
  rca_score_breakdown?: Record<string, number>;
  excluded_candidates?: ExcludedRCACandidate[];
  risk_level?: string;
  playbook_id?: string;
  playbook_source?: string;
  hitl_required?: boolean;
  hitl_id?: string;
  escalation_reason?: string | null;
  recovery_time_sec?: number;
  improved?: boolean;
  pre_yield?: number;
  post_yield?: number;
  auto_recovered: boolean;
  timestamp?: string;
}

export interface HealingState {
  iteration: number;
  running: boolean;
  incidents: number;
  autoRecovered: number;
  recentIncidents: HealingIncident[];
  recurrenceKpis?: {
    matched_chain_rate: number;
    repeat_incident_rate: number;
    matched_auto_recovery_rate: number;
    matched_avg_recovery_sec: number;
    unmatched_avg_recovery_sec: number;
    graph_playbook_rate?: number;
    hardcoded_fallback_rate?: number;
    total: number;
  };
  hitlPending?: Array<Record<string, unknown>>;
  hitlAudit?: Array<Record<string, unknown>>;
  hitlPolicy?: {
    min_confidence: number;
    high_risk_threshold: number;
    medium_requires_history: boolean;
  };
}

export type HealingPhase = 'sense' | 'detect' | 'diagnose' | 'recover' | 'verify' | 'learn_healing';

// ── Incident Analysis (LLM) ──

export interface IncidentAnalysis {
  summary: string;
  root_cause_explanation: string;
  cross_process_insight: string;
  recommended_actions: string[];
  risk_assessment: string;
  confidence_breakdown: Record<string, string>;
  agents_involved: string[];
  model: string;
  tokens_used: number;
}

// ── Causal Discovery ──

export interface CausalDiscoveryResult {
  candidates_tested: number;
  after_pruning: number;
  promoted_rules: Array<{
    id: string;
    cause: string;
    effect: string;
    strength: number;
    p_value?: number;
  }>;
  total_discovered: number;
}

// ── Evolution Agent ──

export interface EvolutionCycleResult {
  cycle_number: number;
  strategies_run: number;
  strategies_improved: number;
  strategy_summary: Array<{
    name: string;
    fitness: number;
    executions: number;
    active: boolean;
  }>;
  mutations_tested: number;
  best_strategy?: string;
  overall_fitness: number;
}

// ── LLM Orchestrator ──

export interface OrchestratorDecision {
  step_id: string;
  path: 'rule_based' | 'llm' | 'llm_fallback';
  reason: string;
  complexity_score: number;
}

// ── L5 Learning Layer (Evolution → Ontology) ──

export interface LearningRecordEvent {
  iteration: number;
  record_id: string;
  cycle_number: number;
  overall_fitness: number;
  improvement_delta: number;
  mutations_created: number;
  supersedes_linked: boolean;
}

// ── Safety Guard (LLM → HITL) ──

export interface LLMSafetyGuardEvent {
  iteration: number;
  step_id: string;
  safety_level: string;
  hypotheses_capped: number;
  reason: string;
}

// ── Predictive Maintenance (RUL → Ontology) ──

export interface RULCriticalEntry {
  equipment_id: string;
  step_id?: string;
  priority: string;
  rul_hours_median: number;
  risk_score: number;
}

export interface RULCriticalEvent {
  iteration: number;
  upserted: number;
  critical_equipment: RULCriticalEntry[];
}

// ── Engine State ──

export interface EngineState {
  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  iteration: number;
  maxIterations: number;
  running: boolean;
  paused: boolean;
  speed: number;
  metrics: Metrics | null;
  prevMetrics: Metrics | null;
  initialMetrics: Metrics | null;
  agents: Agent[];
  skills: SkillStats;
  history: HistoryEntry[];
  graphData: GraphData | null;
  steps: ProcessStep[];
  currentPhase: Phase | null;
  debate: DebateState;
  eventLog: LogEntry[];
  metricsHistory: MetricsHistory;
  // v5 Incident Analysis
  latestAnalysis: IncidentAnalysis | null;
  correlations: Array<{
    source: string;
    target: string;
    coefficient: number;
    direction: string;
    sensors: string;
  }>;
  // v4 Healing
  healing: HealingState;
  healingPhase: HealingPhase | null;
  phase4?: {
    predictive_agent: boolean;
    nl_diagnoser: boolean;
    llm_orchestrator: boolean;
    model?: string;
    latest_predictive: Array<Record<string, unknown>>;
    orchestrator_traces?: Array<Record<string, unknown>>;
  };
  l3Snapshot?: Record<string, unknown>;
  l3Trends?: Record<string, unknown>[];
  crossInvestigations?: Array<Record<string, unknown>>;
  // L4 Tier 1: Causal Discovery + Evolution + LLM Orchestrator
  causalDiscovery?: CausalDiscoveryResult;
  evolutionCycle?: EvolutionCycleResult;
  latestOrchestratorDecision?: OrchestratorDecision;
  latestRULCritical?: RULCriticalEvent;
  latestLearningRecord?: LearningRecordEvent;
  latestLLMSafetyGuard?: LLMSafetyGuardEvent;
  // L4 Tier 2: PRE-VERIFY phase (CDT decision validation)
  preverify?: PreverifyState;
  // VISION 9.5 — anti-recurrence visibility
  recurrence?: RecurrenceState;
  // SRE-style SLI/SLO per microservice (ProcessStep)
  slo?: SLOState;
  // 사용자가 클릭한 incident ID — Triptych의 lane 동기화에 사용
  selectedIncidentId?: string | null;
  // SLO drill-down — 클릭한 SLI key (auto_recovery_rate, yield_compliance 등)
  selectedSloKey?: string | null;
  // step drill-down — 클릭한 ProcessStep id (PS-301 등)
  selectedStepId?: string | null;
  // 시나리오 drill-down — 클릭한 scenario id (SCN-009 등)
  selectedScenarioId?: string | null;
  // Sidebar nav로 선택한 페이지
  currentView?: ViewKey;
}

/** Drill-down 통합 페이로드 — 한 클릭으로 view + selection 동기화 */
export interface NavTarget {
  view?: ViewKey;
  incidentId?: string | null;
  sloKey?: string | null;
  stepId?: string | null;
  scenarioId?: string | null;
}

export type ViewKey = 'overview' | 'healing' | 'slo' | 'learning' | 'console' | 'settings';

export interface RecurrenceSignature {
  step_id: string;
  anomaly_type: string;
  cause_type: string;
  count: number;
  tried_actions: string[];
  last_success: boolean;
}

export interface RecurrenceState {
  total_signatures: number;
  repeating_count: number;
  top_signatures: RecurrenceSignature[];
}

export interface PreverifySimulation {
  action_type: string;
  cause_type: string;
  parameter: string | null;
  predicted_new_value: number | null;
  expected_delta: number;
  param_delta: number;
  success_prob: number;
  risk_factor: number;
  confidence: number;
  score: number;
  hist_attempts: number;
}

export interface PreverifyPlan {
  step_id: string;
  selected_action: string | null;
  selected_score: number | null;
  rejected_reason: string | null;
  candidate_count: number;
  top_simulations: PreverifySimulation[];
}

export interface PreverifyState {
  latestPlans: PreverifyPlan[];
  iteration: number;
  autoRejectedThisRound: number;
  // Accumulated metrics from server state
  mae_recent: number;
  sign_accuracy_recent: number;
  samples_recent: number;
  auto_rejected_total: number;
  plans_total: number;
  auto_reject_rate: number;
  current_thresholds: Record<string, number>;
  thresholds_history?: Array<{ iteration: number; A: number; B: number; C: number }>;
}

// ── Scenario ──

export interface ActiveScenario {
  scenario_id: string;
  name: string;
  category: string;
  severity: string;
  root_cause: string;
  elapsed_ticks: number;
  effects_injected: number;
  total_effects: number;
  degradation?: Record<string, { sensor: string; progress: number; total: number }> | null;
  activated_at: string;
}

export interface ScenarioStatus {
  active: ActiveScenario[];
  library_stats: {
    by_severity?: Record<string, number>;
    by_category?: Record<string, number>;
  };
  total_library: number;
}

// ── SLO / SLI ──

export interface SLODefinition {
  name: string;
  description: string;
  data_source: string;
  target: number;
  higher_is_better: boolean;
  unit: string;
}

export interface SLOGlobalSLI {
  auto_recovery_rate: number;
  p95_recovery_latency: number;
  p50_recovery_latency: number;
  yield_compliance: number;
  hitl_rate: number;
  repeat_rate: number;
  total_incidents: number;
  total_auto_recovered: number;
}

export interface MicroserviceSLI {
  step_id: string;
  area_id: string;
  incident_count: number;
  auto_recovery_rate: number;
  hitl_rate: number;
  improvement_rate: number;
  p50_recovery_sec: number;
  p95_recovery_sec: number;
  current_yield: number;
  yield_meets_slo: boolean;
  severity_dist: Record<string, number>;
  error_budget_remaining: number;
}

export interface AreaSLI {
  area_id: string;
  step_count: number;
  total_incidents: number;
  auto_recovery_rate: number;
  hitl_rate: number;
  yield_compliance_rate: number;
}

export interface SLOViolation {
  sli: string;
  name: string;
  current: number;
  target: number;
  delta: number;
  affected_steps: string[];
}

export interface SLOState {
  definitions: Record<string, SLODefinition>;
  global: SLOGlobalSLI;
  per_step: MicroserviceSLI[];
  per_area: AreaSLI[];
  violations: SLOViolation[];
}

// ── WS Command ──

export type WSCommand =
  | { cmd: 'init' }
  | { cmd: 'run' }
  | { cmd: 'step' }
  | { cmd: 'pause' }
  | { cmd: 'resume' }
  | { cmd: 'speed'; speed: number }
  | { cmd: 'reset' }
  | { cmd: 'state' }
  | { cmd: 'heal' }
  | { cmd: 'heal_step' }
  | { cmd: 'full_cycle' }
  | { cmd: 'hitl_approve'; id: string; operator?: string; role?: 'operator' | 'supervisor'; supervisor_token?: string }
  | { cmd: 'hitl_reject'; id: string; operator?: string; role?: 'operator' | 'supervisor'; supervisor_token?: string }
  | {
      cmd: 'hitl_policy_update';
      min_confidence: number;
      high_risk_threshold: number;
      medium_requires_history: boolean;
      operator?: string;
      role?: 'operator' | 'supervisor';
      supervisor_token?: string;
    };
