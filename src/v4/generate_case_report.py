"""
Generate detailed incident-recovery case analysis report.

Usage:
  python src/v4/generate_case_report.py
"""

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
LATEST = RESULTS / "self_healing_v4_latest.json"
OUT_MD = RESULTS / "self_healing_case_analysis.md"


def load_latest():
    if not LATEST.exists():
        return None
    with open(LATEST, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt(v, nd=3):
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def build_report(data):
    incidents = data.get("recent_incidents", [])
    analyses = data.get("case_analyses", [])
    total = data.get("total_incidents", 0)
    auto = data.get("auto_recovered", 0)
    recovery_rate = (auto / total * 100) if total else 0
    l3 = data.get("latest_l3_snapshot", {}).get("counts", {})

    lines = []
    lines.append(f"# Self-Healing Case Analysis ({datetime.now().isoformat()})")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(f"- Total incidents: **{total}**")
    lines.append(f"- Auto-recovered: **{auto}** ({recovery_rate:.1f}%)")
    lines.append(f"- L3 status: CausalRule={l3.get('causal_rules',0)}, FailureChain={l3.get('failure_chains',0)}, MATCHED_BY={l3.get('matched_by',0)}")
    lines.append("")

    if not analyses:
        lines.append("## Case Analysis")
        lines.append("No case analysis data available.")
        return "\n".join(lines)

    lines.append("## Case Analysis")
    for idx, c in enumerate(analyses, start=1):
        issue = c.get("issue", {})
        rec = c.get("recovery", {})
        eff = c.get("effect", {})
        lines.append(f"### Case {idx}: {c.get('incident_id')} / {c.get('step_id')}")
        lines.append(f"- Issue: type={issue.get('anomaly_type')}, severity={issue.get('severity')}, cause={issue.get('top_cause')} (conf={issue.get('confidence')})")
        lines.append(f"- Recovery: action={rec.get('action_type')}, auto={rec.get('auto_recovered')}, improved={rec.get('improved')}")
        lines.append(f"- Effect: pre={fmt(eff.get('pre_yield'))}, post={fmt(eff.get('post_yield'))}, delta={fmt(eff.get('delta'))}, delta_pct={fmt(eff.get('delta_pct'),2)}%")
        if c.get("quality_flag"):
            lines.append(f"- Data quality flag: `{c.get('quality_flag')}`")
        lines.append("")

    # Top patterns
    by_cause = {}
    by_action = {}
    improved_count = 0
    for i in incidents:
        cause = i.get("top_cause", "unknown")
        action = i.get("action_type", "unknown")
        by_cause[cause] = by_cause.get(cause, 0) + 1
        by_action[action] = by_action.get(action, 0) + 1
        if i.get("improved"):
            improved_count += 1

    lines.append("## Aggregate Pattern")
    lines.append(f"- Improved cases: **{improved_count}/{len(incidents)}**")
    if by_cause:
        lines.append("- Top causes:")
        for k, v in sorted(by_cause.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"  - {k}: {v}")
    if by_action:
        lines.append("- Top recovery actions:")
        for k, v in sorted(by_action.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"  - {k}: {v}")

    lines.append("")
    lines.append("## Recommended Next Actions")
    lines.append("- Enrich causal links where `MATCHED_BY` exists but `CHAIN_USES` is low.")
    lines.append("- Increase diversity of recovery playbook to reduce single-action concentration.")
    lines.append("- Track step-wise pre/post yield distributions for robust outlier control.")
    return "\n".join(lines)


def main():
    data = load_latest()
    if not data:
        print("No latest self-healing result found.")
        return
    md = build_report(data)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Report generated: {OUT_MD}")


if __name__ == "__main__":
    main()

