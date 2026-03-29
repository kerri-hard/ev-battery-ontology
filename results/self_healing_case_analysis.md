# Self-Healing Case Analysis (2026-03-29T18:55:25.246247)

## Executive Summary
- Total incidents: **2**
- Auto-recovered: **2** (100.0%)
- L3 status: CausalRule=15, FailureChain=2, MATCHED_BY=2

## Case Analysis
### Case 1: INC-0001 / PS-103
- Issue: type=threshold_breach, severity=MEDIUM, cause=equipment_mtbf (conf=0.85)
- Recovery: action=ADJUST_PARAMETER, auto=True, improved=True
- Effect: pre=0.995, post=0.999, delta=0.004, delta_pct=0.40%

### Case 2: INC-0002 / PS-507
- Issue: type=threshold_breach, severity=CRITICAL, cause=equipment_mtbf (conf=0.6)
- Recovery: action=ADJUST_PARAMETER, auto=True, improved=True
- Effect: pre=0.998, post=0.999, delta=0.001, delta_pct=0.10%

## Aggregate Pattern
- Improved cases: **2/2**
- Top causes:
  - equipment_mtbf: 2
- Top recovery actions:
  - ADJUST_PARAMETER: 2

## Recommended Next Actions
- Enrich causal links where `MATCHED_BY` exists but `CHAIN_USES` is low.
- Increase diversity of recovery playbook to reduce single-action concentration.
- Track step-wise pre/post yield distributions for robust outlier control.