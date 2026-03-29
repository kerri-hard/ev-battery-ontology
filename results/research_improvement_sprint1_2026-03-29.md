# Research Sprint 1 Implementation (2026-03-29)

## Scope
- Vision-aligned improvements implemented:
  1) L4 decision ontology foundation,
  2) hybrid orchestrator routing API,
  3) FD-LLM evidence reference enhancement.

## Implemented

### 1) L4 Decision Layer
- New file: `src/v4/decision_layer.py`
  - Added schema extension:
    - `EscalationPolicy`
    - `ResponsePlaybook`
    - `OptimizationGoal`
  - Added relations:
    - `TRIGGERS_ACTION`
    - `ESCALATES_TO`
    - `OPTIMIZES`
  - Added default seeding and active policy load/update helpers.

- Updated: `src/v4/engine.py`
  - Calls `extend_schema_l4()` + `seed_l4_policy()` in initialize.
  - Loads active escalation policy from graph into runtime HITL policy.
  - Syncs runtime policy updates back to graph.
  - On escalation incident, creates `Incident-[:ESCALATES_TO]->EscalationPolicy`.

### 2) Hybrid Orchestrator Route API
- Updated: `src/v4/engine.py`
  - Added `route_intent(intent, payload)`:
    - `nl_diagnose` → `NaturalLanguageDiagnoser`
    - `predictive_priority` → `PredictiveAgent`
    - `healing_status` → engine status
    - `explain_step` → incidents + NL summary

- Updated: `server.py`
  - Added `POST /api/agent/route` endpoint.

### 3) FD-LLM Evidence References
- Updated: `src/v4/llm_agents.py`
  - Extended LLM JSON schema:
    - hypotheses now include `evidence_refs`.
  - Added sanitation for `evidence_refs`.
  - Symbolic fallback now emits default evidence refs from `Incident`/`CausalRule`.

- Updated UI detail:
  - `web/src/components/issues/LiveIssuePanel.tsx` shows matched chain id as evidence id.

## Validation
- Python compile: pass
- Frontend lint: pass
- Smoke checks:
  - orchestrator route delegation works,
  - policy update syncs to graph policy row,
  - NL diagnosis hypotheses can include `evidence_refs`.
