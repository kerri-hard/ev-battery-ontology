"""연구 루프 메트릭 수집기 — 라운드별 결과 누적, 수렴 판정, 회귀 경고."""
from datetime import datetime


# 수렴 감지: 연속 2라운드 동안 핵심 메트릭 변화폭이 이 값 이하이면 조기 종료
CONVERGENCE_DELTA = 0.003  # 0.3%p (CLAUDE.md 하네스 루프 규약)
CONVERGENCE_WINDOW = 2

# 회귀 감지: 핵심 메트릭이 이 비율 이상 악화되면 경고
REGRESSION_THRESHOLD = 0.05  # 5%


class MetricsCollector:
    """시뮬레이션 결과를 수집하고 비교한다."""

    def __init__(self):
        self.rounds = []
        self.baseline_yield = None

    def collect(self, label, incidents, auto_recovered, scenarios_run,
                causal_rules, failure_chains, correlations,
                avg_confidence, avg_recovery_time, yield_before, yield_after,
                false_positive_rate, missed_anomalies, details=None):
        if self.baseline_yield is None:
            self.baseline_yield = yield_before
        self.rounds.append({
            "label": label,
            "timestamp": datetime.now().isoformat(),
            "incidents": incidents,
            "auto_recovered": auto_recovered,
            "recovery_rate": round(auto_recovered / max(incidents, 1), 3),
            "scenarios_run": scenarios_run,
            "causal_rules": causal_rules,
            "failure_chains": failure_chains,
            "correlations": correlations,
            "avg_confidence": round(avg_confidence, 3),
            "avg_recovery_time": round(avg_recovery_time, 3),
            "yield_before": round(yield_before, 5),
            "yield_after": round(yield_after, 5),
            "yield_improvement": round((yield_after - yield_before) * 100, 3),
            "yield_vs_baseline": round((yield_after - self.baseline_yield) * 100, 3),
            "false_positive_rate": round(false_positive_rate, 3),
            "missed_anomalies": missed_anomalies,
            "details": details or {},
        })

    def has_converged(self, window: int = CONVERGENCE_WINDOW, delta: float = CONVERGENCE_DELTA) -> bool:
        """연속 ``window`` 라운드 동안 핵심 메트릭 변화가 ``delta`` 이하이면 True."""
        if len(self.rounds) < window + 1:
            return False
        recent = self.rounds[-(window + 1):]
        for i in range(1, len(recent)):
            rr_delta = abs(recent[i]["recovery_rate"] - recent[i - 1]["recovery_rate"])
            y_delta = abs(recent[i]["yield_vs_baseline"] - recent[i - 1]["yield_vs_baseline"]) / 100
            if rr_delta > delta or y_delta > delta:
                return False
        return True

    def regression_warnings(self, threshold: float = REGRESSION_THRESHOLD) -> list[str]:
        """직전 라운드 대비 악화된 메트릭을 사람이 읽을 수 있는 경고로 반환한다."""
        if len(self.rounds) < 2:
            return []
        prev, curr = self.rounds[-2], self.rounds[-1]
        warnings = []

        rr_drop = prev["recovery_rate"] - curr["recovery_rate"]
        if rr_drop > threshold:
            warnings.append(
                f"복구율 {prev['recovery_rate']:.0%} → {curr['recovery_rate']:.0%} "
                f"({rr_drop * 100:.1f}%p 하락)"
            )

        conf_drop = prev["avg_confidence"] - curr["avg_confidence"]
        if conf_drop > threshold:
            warnings.append(
                f"신뢰도 {prev['avg_confidence']:.3f} → {curr['avg_confidence']:.3f} "
                f"({conf_drop:.3f} 하락)"
            )

        fpr_increase = curr["false_positive_rate"] - prev["false_positive_rate"]
        if fpr_increase > threshold:
            warnings.append(
                f"오탐률 {prev['false_positive_rate']:.0%} → {curr['false_positive_rate']:.0%} "
                f"({fpr_increase * 100:.1f}%p 증가)"
            )

        y_drop = prev["yield_vs_baseline"] - curr["yield_vs_baseline"]
        if y_drop > threshold * 100:
            warnings.append(
                f"수율 베이스라인 대비 {prev['yield_vs_baseline']:.2f}%p → "
                f"{curr['yield_vs_baseline']:.2f}%p ({y_drop:.2f}%p 악화)"
            )
        return warnings

    def compare(self, round_a: int, round_b: int) -> dict:
        a = self.rounds[round_a]
        b = self.rounds[round_b]
        improvements = {}
        for key in ("recovery_rate", "avg_confidence", "yield_improvement", "false_positive_rate"):
            va, vb = a.get(key, 0), b.get(key, 0)
            improved = vb < va if key == "false_positive_rate" else vb > va
            improvements[key] = {"before": va, "after": vb, "improved": improved}
        return improvements

    def summary(self):
        if len(self.rounds) < 2:
            return "데이터 부족"
        first = self.rounds[0]
        last = self.rounds[-1]
        baseline = self.baseline_yield if self.baseline_yield is not None else first["yield_before"]
        return {
            "total_rounds": len(self.rounds),
            "recovery_rate": f"{first['recovery_rate']:.0%} → {last['recovery_rate']:.0%}",
            "avg_confidence": f"{first['avg_confidence']:.3f} → {last['avg_confidence']:.3f}",
            "yield_improvement": f"{first['yield_improvement']:.3f}%p → {last['yield_improvement']:.3f}%p",
            "yield_vs_baseline": f"{baseline * 100:.2f}% → {last['yield_after'] * 100:.2f}% (누적 {last['yield_vs_baseline']:+.3f}%p)",
            "failure_chains": f"{first['failure_chains']} → {last['failure_chains']}",
            "correlations": f"{first['correlations']} → {last['correlations']}",
        }
