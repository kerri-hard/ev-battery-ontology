#!/usr/bin/env python3
"""Backtest CI guard — backtest 결과가 임계 기준 위반 시 exit code 1.

사용:
  python scripts/backtest_ci_guard.py --report results/backtest_report_*.json

기본 임계값 (CLAUDE.md / VISION 기반):
  - decision_match_rate >= 0.55  (anti-recurrence false positive 고려)
  - confidence_brier <= 0.10
  - drift_warnings <= 5  (genuine drift만)
  - ECE <= 0.30  (calibration 정체 허용)

env로 override 가능: BACKTEST_MIN_DECISION_MATCH 등.
"""
import argparse
import json
import os
import sys


def _f(env_key: str, default: float) -> float:
    return float(os.environ.get(env_key, default))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, help="backtest_report_*.json 경로")
    args = parser.parse_args()

    if not os.path.exists(args.report):
        print(f"ERROR: report not found: {args.report}", file=sys.stderr)
        return 2

    with open(args.report, "r", encoding="utf-8") as f:
        report = json.load(f)

    decision_match = float(report.get("decision_match_rate", 0))
    brier = float(report.get("confidence_brier", 1))
    ece = float(report.get("confidence_ece", 1))
    drifts = len(report.get("drift_warnings", []))
    n = report.get("n_usable", 0)

    thresholds = {
        "decision_match_rate >= ?": _f("BACKTEST_MIN_DECISION_MATCH", 0.55),
        "confidence_brier <= ?": _f("BACKTEST_MAX_BRIER", 0.10),
        "confidence_ece <= ?": _f("BACKTEST_MAX_ECE", 0.30),
        "drift_warnings <= ?": int(_f("BACKTEST_MAX_DRIFT", 5)),
    }

    actual = {
        "decision_match_rate >= ?": decision_match,
        "confidence_brier <= ?": brier,
        "confidence_ece <= ?": ece,
        "drift_warnings <= ?": drifts,
    }

    print(f"=== Backtest CI Guard ===")
    print(f"Report: {args.report}")
    print(f"N incidents: {n}")
    print()

    failures = []
    for label, target in thresholds.items():
        cur = actual[label]
        op = ">=" if ">=" in label else "<="
        ok = (cur >= target) if op == ">=" else (cur <= target)
        status = "✅" if ok else "❌"
        print(f"  {status} {label.replace('?', str(target)):40s}  현재: {cur}")
        if not ok:
            failures.append((label, target, cur))

    print()
    if failures:
        print(f"🔴 {len(failures)}건 임계 위반 — CI gate 차단")
        for label, target, cur in failures:
            print(f"   · {label.replace('?', str(target))} (현재: {cur})")
        return 1
    print("✅ 모든 임계 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
