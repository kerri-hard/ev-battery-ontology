# Research Improvement Round 2 (2026-03-29)

## Multi-agent analysis summary

- Parallel agents were used for:
  - vision/code gap scan,
  - reliability/safety review,
  - frontend research-visibility gap review.
- Common top priorities:
  1) HITL gating for risky recovery actions,
  2) risk-aware action ranking bug fix,
  3) recurrence KPI exposure,
  4) incident-level causal evidence visibility.

## Implemented in this round

### 1) Safety and policy alignment
- File: `src/v4/healing_agents.py`
  - Added `requires_hitl(...)` policy gate helper.
  - Changed `ESCALATE` execution to `success=False` (no longer counted as auto recovery).

- File: `src/v4/engine.py`
  - Fixed action ranking to use `risk_level` + `RISK_NUMERIC` (previous key mismatch risk bug removed).
  - Added HITL queue (`hitl_pending`) with `recover_pending_hitl` event.
  - Added HITL resolve method (`resolve_hitl`) for approve/reject workflows.
  - Learning success now uses `auto_recovered AND improved`.

### 2) Runtime/API support for HITL
- File: `server.py`
  - Added REST endpoints:
    - `POST /api/hitl/approve`
    - `POST /api/hitl/reject`
  - Added WebSocket commands:
    - `hitl_approve`
    - `hitl_reject`

### 3) Recurrence and evidence visibility
- File: `src/v4/engine.py`
  - Added recurrence KPIs:
    - `matched_chain_rate`
    - `repeat_incident_rate`
    - `matched_auto_recovery_rate`
  - Included KPIs and HITL queue in `state["healing"]`.
  - Extended incident payload with:
    - `history_matched`, `matched_chain_id`, `candidates_count`,
      `causal_chains_found`, `analysis_method`,
      `risk_level`, `hitl_required`, `hitl_id`, `escalation_reason`.

- Files: `web/src/types/index.ts`, `web/src/hooks/useHarnessEngine.ts`, `web/src/components/issues/LiveIssuePanel.tsx`
  - Added TS types + normalization for new incident fields/KPIs/HITL queue.
  - Added HITL pending indicator in issue panel.
  - Added recurrence KPI mini-cards.
  - Added modal “관련 이벤트 로그 자동 필터” (by `step_id`) timeline section.
  - Added evidence quality/risk/HITL details in issue modal.

## Validation

- `python3 -m py_compile`: pass
- `npm run lint` (web): pass
- Smoke test:
  - HITL queue generated and resolvable,
  - recurrence KPI present in state,
  - extended incident fields emitted.
