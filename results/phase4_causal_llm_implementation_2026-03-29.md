# Phase4 Causal+LLM Implementation Note (2026-03-29)

## Research-to-implementation mapping

## 1) KG-driven RCA (Sensors 2025)
- Paper direction: structured fault knowledge graph + causal relation reasoning.
- Implemented:
  - `src/v4/causal.py`: CausalRule / FailureChain / CAUSES / MATCHED_BY / CHAIN_USES
  - Causal chain boosting + history matching in RCA.

## 2) Hybrid Agentic AI + MAS (NAMRC 2026)
- Paper direction: strategic planner + fast domain agents.
- Implemented:
  - v4 healing loop keeps deterministic edge agents.
  - Added Phase4-style analysis agents:
    - `PredictiveAgent` for RUL/risk ranking
    - `NaturalLanguageDiagnoser` for text query diagnosis

## 3) FD-LLM / Natural-language diagnosis (AEI 2025)
- Paper direction: textual query + sensor/fault context reasoning.
- Implemented (LLM-ready, no external key required):
  - `src/v4/llm_agents.py` / `NaturalLanguageDiagnoser.analyze()`
  - Uses ontology + incident history + causal rules to produce hypotheses and recommendations.

## Implemented APIs

- `GET /api/predictive-rul?limit=5`
  - Returns step/equipment risk and estimated RUL.
- `POST /api/nl-diagnose`
  - Body: `{ "query": "PS-203 온도 이상 원인 뭐야?" }`
  - Returns hypotheses, related causal rules, recommendations.
- `GET /api/phase4-status`
  - Returns runtime status (`llm_orchestrator`, `model`, predictive cache).

## Runtime config (optional)

- `OPENAI_API_KEY` : OpenAI API key
- `OPENAI_MODEL` : model name (default `gpt-4.1-mini`)
- `LLM_USE_OPENAI` : `1` (default) or `0`

If key is missing or API call fails, system automatically falls back to symbolic diagnosis.

## Dashboard visibility

- Research progress panel now reflects Phase4 from runtime state.
- Predictive RUL card shows top risk items from `verify_done`.

## Remaining work for full paper parity

- Real LLM backend wiring (model inference API) with guardrails.
- RUL model upgrade from heuristic to sequence model (LSTM/Transformer).
- HITL policy and cost-aware scheduler integration for prescriptive maintenance.
