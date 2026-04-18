"""Backtest 하네스 — 과거 incident snapshot을 현재 모델로 replay.

목적: 모델/플레이북 변경이 과거 결정과 어떻게 다른지 측정해 회귀를 차단.

산출 메트릭:
  - decision_match_rate    — 현재 모델 top-action vs 기록된 action 일치율
  - confidence_brier       — Brier score (낮을수록 calibrated)
  - confidence_ece         — Expected Calibration Error (10-bin)
  - preverify_reject_rate  — pre-verify가 거절했을 incident 비율
  - per_action_breakdown   — action_type별 incident 개수 + 일치율

사용:
  from v4.backtest import BacktestRunner, run_backtest
  report = await run_backtest("results/self_healing_v4_latest.json")
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections import defaultdict
from datetime import datetime

from v4.engine import SelfHealingEngine
from v4.phases.preverify import simulate_action


_NUM_BINS = 10  # confidence calibration bins


class BacktestRunner:
    """과거 incident를 현재 SelfHealingEngine으로 replay하고 결과를 비교한다."""

    def __init__(self, snapshot_path: str, db_path: str | None = None,
                 results_dir: str | None = None):
        self.snapshot_path = snapshot_path
        self.db_path = db_path or f"/tmp/kuzu_backtest_{int(time.time())}"
        self.results_dir = results_dir or f"/tmp/results_backtest_{int(time.time())}"
        self.engine: SelfHealingEngine | None = None
        self.incidents: list = []
        self.replay_log: list = []

    # ── PUBLIC ────────────────────────────────────────────

    async def setup(self) -> None:
        with open(self.snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        self.incidents = list(snapshot.get("recent_incidents", []))
        if not self.incidents:
            raise ValueError(f"snapshot has no incidents: {self.snapshot_path}")

        self.engine = SelfHealingEngine(db_path=self.db_path, results_dir=self.results_dir)
        await self.engine.initialize()

    async def replay(self) -> list:
        """각 incident에 대해 현재 모델의 결정을 기록한다."""
        if self.engine is None:
            await self.setup()

        for inc in self.incidents:
            self.replay_log.append(self._replay_one(inc))
        return self.replay_log

    def evaluate(self) -> dict:
        """집계 메트릭 산출."""
        if not self.replay_log:
            raise RuntimeError("replay() must be called first")

        usable = [r for r in self.replay_log if r.get("error") is None]
        decision_match = sum(1 for r in usable if r["decision_match"])
        preverify_rejects = sum(1 for r in usable if r["preverify_rejected"])

        return {
            "snapshot": self.snapshot_path,
            "evaluated_at": datetime.now().isoformat(),
            "n_total": len(self.replay_log),
            "n_usable": len(usable),
            "decision_match_rate": _safe_div(decision_match, len(usable), 4),
            "preverify_reject_rate": _safe_div(preverify_rejects, len(usable), 4),
            "confidence_brier": _brier_score(usable),
            "confidence_ece": _expected_calibration_error(usable),
            "per_action_breakdown": _per_action_breakdown(usable),
            "drift_warnings": _drift_warnings(usable),
        }

    def cleanup(self) -> None:
        """테스트 DB 디렉토리 제거."""
        import shutil
        for p in (self.db_path, self.db_path + ".wal", self.db_path + ".lock"):
            if not os.path.exists(p):
                continue
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
            except Exception:
                pass

    # ── INTERNAL ──────────────────────────────────────────

    def _replay_one(self, inc: dict) -> dict:
        anomaly = _reconstruct_anomaly(inc)
        diagnosis = _reconstruct_diagnosis(inc)
        try:
            candidates = self.engine.auto_recovery.plan_recovery(
                self.engine.conn, diagnosis, anomaly,
            )
        except Exception as exc:
            return {
                "incident_id": inc.get("id"),
                "step_id": inc.get("step_id"),
                "error": f"plan_recovery_failed: {exc}",
            }

        if not candidates:
            return {
                "incident_id": inc.get("id"),
                "step_id": inc.get("step_id"),
                "historical_action": inc.get("action_type"),
                "current_action": None,
                "decision_match": False,
                "preverify_rejected": False,
                "current_confidence": 0.0,
                "historical_success": bool(inc.get("auto_recovered", False)),
                "best_score": None,
                "error": None,
            }

        # Simulate top candidate (preverify-style scoring)
        top_action = candidates[0]
        sim = simulate_action(self.engine, top_action)
        rejected = self._would_preverify_reject(sim, inc.get("step_id", ""))

        return {
            "incident_id": inc.get("id"),
            "step_id": inc.get("step_id"),
            "historical_action": inc.get("action_type"),
            "current_action": top_action.get("action_type"),
            "decision_match": top_action.get("action_type") == inc.get("action_type"),
            "preverify_rejected": rejected,
            "current_confidence": top_action.get("confidence", 0.0),
            "historical_success": bool(inc.get("auto_recovered", False)),
            "best_score": sim["score"],
            "expected_delta": sim["expected_delta"],
            "success_prob": sim["success_prob"],
            "candidate_count": len(candidates),
            "error": None,
        }

    def _would_preverify_reject(self, sim: dict, step_id: str) -> bool:
        """preverify의 안전등급별 score 임계 적용."""
        from v4.phases.preverify import _SCORE_THRESHOLD_BY_SAFETY
        safety = self.engine._get_step_safety_level(step_id) if step_id else "C"
        threshold = _SCORE_THRESHOLD_BY_SAFETY.get(safety, 0.0)
        return sim["score"] < threshold


# ── reconstruction helpers ────────────────────────────────


def _reconstruct_anomaly(inc: dict) -> dict:
    return {
        "step_id": inc.get("step_id", ""),
        "anomaly_type": inc.get("anomaly_type", "threshold_breach"),
        "severity": inc.get("severity", "MEDIUM"),
        "sensor_type": inc.get("sensor_type", "unknown"),
        "value": inc.get("value"),
    }


def _reconstruct_diagnosis(inc: dict) -> dict:
    cause = inc.get("top_cause", "unknown")
    return {
        "step_id": inc.get("step_id", ""),
        "candidates": [{
            "cause_type": cause,
            "confidence": float(inc.get("confidence", 0.5) or 0.5),
            "cause_id": f"REPLAY-{inc.get('id', 'X')}",
            "cause_name": f"replay: {cause}",
            "evidence": "backtest replay",
        }],
        "failure_chain_matched": bool(inc.get("history_matched", False)),
        "matched_chain_id": inc.get("matched_chain_id"),
    }


# ── metric helpers ────────────────────────────────────────


def _safe_div(num, den, ndigits: int = 4) -> float:
    if den == 0:
        return 0.0
    return round(num / den, ndigits)


def _brier_score(replays: list) -> float:
    """mean((current_confidence − historical_success)^2). 낮을수록 좋음."""
    pairs = [
        (float(r.get("current_confidence", 0) or 0), 1 if r["historical_success"] else 0)
        for r in replays
    ]
    if not pairs:
        return 0.0
    return round(sum((p - y) ** 2 for p, y in pairs) / len(pairs), 4)


def _expected_calibration_error(replays: list, num_bins: int = _NUM_BINS) -> float:
    """ECE — 신뢰도 bin별 |평균 신뢰도 − 실제 성공률| 가중평균."""
    pairs = [
        (float(r.get("current_confidence", 0) or 0), 1 if r["historical_success"] else 0)
        for r in replays
    ]
    if not pairs:
        return 0.0

    bins: dict[int, list] = defaultdict(list)
    for conf, succ in pairs:
        idx = min(int(conf * num_bins), num_bins - 1)
        bins[idx].append((conf, succ))

    total = len(pairs)
    ece = 0.0
    for samples in bins.values():
        n = len(samples)
        if n == 0:
            continue
        avg_conf = sum(c for c, _ in samples) / n
        avg_succ = sum(s for _, s in samples) / n
        ece += (n / total) * abs(avg_conf - avg_succ)
    return round(ece, 4)


def _per_action_breakdown(replays: list) -> dict:
    """action_type별 (count, decision_match_rate)."""
    grouped: dict[str, list] = defaultdict(list)
    for r in replays:
        grouped[r.get("historical_action", "unknown")].append(r)

    return {
        action: {
            "count": len(rows),
            "match_rate": _safe_div(sum(1 for r in rows if r["decision_match"]), len(rows)),
            "preverify_reject_rate": _safe_div(sum(1 for r in rows if r["preverify_rejected"]), len(rows)),
        }
        for action, rows in grouped.items()
    }


def _drift_warnings(replays: list) -> list:
    """Notable regressions: action mismatch + previously successful incidents."""
    warnings = []
    for r in replays:
        if not r["decision_match"] and r["historical_success"]:
            warnings.append(
                f"INCIDENT {r.get('incident_id')} (step {r.get('step_id')}): "
                f"historical {r.get('historical_action')} succeeded, "
                f"current model would pick {r.get('current_action')}"
            )
    return warnings[:20]  # cap


# ── one-shot entry ────────────────────────────────────────


async def run_backtest(snapshot_path: str, output_path: str | None = None,
                       db_path: str | None = None) -> dict:
    """Snapshot → replay → 메트릭 산출 → JSON 저장 → report dict 반환."""
    runner = BacktestRunner(snapshot_path, db_path=db_path)
    try:
        await runner.setup()
        await runner.replay()
        report = runner.evaluate()
        report["replay_log"] = runner.replay_log
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        return report
    finally:
        runner.cleanup()
