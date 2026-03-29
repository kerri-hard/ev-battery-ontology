# Research-Driven Improvement Review (2026-03-29)

## Verified paper references

- [Digital Twin Meets Knowledge Graph for Intelligent Manufacturing Processes (Sensors 2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11054090/)
- [Knowledge-Graph-Driven Fault Diagnosis Methods for Intelligent Production Lines (Sensors 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12252116/)
- [Hybrid Agentic AI and Multi-Agent Systems in Smart Manufacturing (NAMRC 2026 preprint)](https://www.emergentmind.com/papers/2511.18258)
- [FD-LLM: Large Language Model for Fault Diagnosis of Machines (AEI 2025)](https://arxiv.org/html/2412.01218v1)
- [A Comprehensive Survey of Self-Evolving AI Agents (2025)](https://www.emergentmind.com/papers/2508.07407)

## Direction extracted from papers

1. KG + DT coupling should drive autonomous context retrieval, anomaly interpretation, and maintenance logic.
2. Root-cause quality increases when fault history is structured as graph entities/relations, not text-only logs.
3. Hybrid architecture should separate strategic planning (LLM-level) and fast deterministic edge actions.
4. Learning loop should persist causal evidence over time for recurrence handling.

## What has been implemented in this project

- L3 ontology layer operational (`CausalRule`, `FailureChain`, `CAUSES`, `MATCHED_BY`, `CHAIN_USES`, `HAS_CAUSE`, `HAS_PATTERN`).
- Healing loop persistence aligned to graph schema (`Incident`, `RecoveryAction`, `HAS_INCIDENT`, `RESOLVED_BY`).
- L3 snapshots and trend history persisted in:
  - `results/l3_trend_latest.json`
  - `results/l3_trend_history.json`
  - `results/self_healing_v4_latest.json`
- Dashboard now visualizes:
  - L3 relation flow
  - L3 causal insights (top rules/chains)
  - L3 trend panel (time-series)
  - research-driven completion/progress panel

## Remaining high-priority work

- Add explicit causal-rule confidence calibration using replayed incidents.
- Introduce HITL gating policy for high-risk recovery actions.
- Add recurrence-resolution KPI board (MTTR reduction by matched chains).
