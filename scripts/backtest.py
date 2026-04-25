#!/usr/bin/env python3
"""Backtest CLI — 저장된 incident snapshot을 현재 SelfHealingEngine으로 replay.

사용:
  python scripts/backtest.py
  python scripts/backtest.py --snapshot results/self_healing_v4_latest.json
  python scripts/backtest.py --snapshot X.json --output results/backtest_report.json
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from v4.backtest import run_backtest


def _default_output_path() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(PROJECT_ROOT, "results", f"backtest_report_{ts}.json")


def _print_summary(report: dict) -> None:
    print("=" * 70)
    print(f"  Backtest Report — {report['snapshot']}")
    print("=" * 70)
    print(f"  N incidents:           {report['n_total']} (usable: {report['n_usable']})")
    print(f"  Decision match rate:   {report['decision_match_rate']:.1%}")
    print(f"  Pre-verify reject:     {report['preverify_reject_rate']:.1%}")
    print(f"  Anti-recur switches:   {report.get('policy_switch_rate', 0):.1%}"
          f"  (force_escalate: {report.get('force_escalate_rate', 0):.1%}, "
          f"hist_demoted: {report.get('historical_demoted_rate', 0):.1%})")
    print(f"  Confidence Brier:      {report['confidence_brier']:.4f} (lower=better)")
    print(f"  Calibration ECE:       {report['confidence_ece']:.4f} (lower=better)")
    print()
    print("  Per-action breakdown:")
    for action, stats in sorted(report["per_action_breakdown"].items()):
        print(
            f"    {action:>20s}: n={stats['count']:>3d}, "
            f"match={stats['match_rate']:.1%}, "
            f"pv_reject={stats['preverify_reject_rate']:.1%}"
        )

    drifts = report.get("drift_warnings", [])
    if drifts:
        print(f"\n  ⚠️  Drift warnings ({len(drifts)}):")
        for w in drifts[:10]:
            print(f"    - {w}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        default=os.path.join(PROJECT_ROOT, "results", "self_healing_v4_latest.json"),
        help="Path to incident snapshot JSON",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Where to write report JSON (default: results/backtest_report_<ts>.json)",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Override Kuzu DB path for replay (default: tmp dir)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.snapshot):
        print(f"ERROR: snapshot not found: {args.snapshot}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or _default_output_path()

    report = asyncio.run(run_backtest(
        args.snapshot, output_path=output_path, db_path=args.db_path,
    ))
    _print_summary(report)
    print(f"\n  Full report: {output_path}")


if __name__ == "__main__":
    main()
