"""SPC + Western Electric 룰 기반 실시간 이상 감지."""
import math
from collections import defaultdict


class AnomalyDetector:
    """센서 읽기값의 통계적 이상을 감지한다.

    3가지 룰:
      1) Threshold breach: normal_min/max 이탈
      2) Statistical outlier: 3σ 룰 (window=20)
      3) Trend shift: 연속 7점 한쪽 편향 (Western Electric)
    """

    def __init__(self):
        self.history = defaultdict(list)
        self.window_size = 20
        self.recovery_feedback = defaultdict(lambda: {"attempts": 0, "successes": 0})

    def update(self, readings: list):
        """센서 읽기값을 히스토리에 추가한다."""
        for r in readings:
            try:
                sid = r.get("sensor_id")
                val = r.get("value")
                if sid is not None and val is not None:
                    self.history[sid].append(float(val))
            except (TypeError, ValueError):
                continue

    def detect(self, readings: list) -> list:
        """이번 사이클의 이상 목록을 반환한다."""
        anomalies = []
        for r in readings:
            anomaly = self._check_one(r)
            if anomaly:
                anomalies.append(anomaly)
        return anomalies

    def learn(self, anomaly: dict, diagnosis: dict, recovery_result: dict):
        """복구 결과를 누적해 향후 감지 파라미터 조정의 근거로 사용한다."""
        key = (
            anomaly.get("step_id", "unknown"),
            anomaly.get("sensor_type", "unknown"),
            anomaly.get("anomaly_type", "unknown"),
        )
        self.recovery_feedback[key]["attempts"] += 1
        if recovery_result.get("success", False):
            self.recovery_feedback[key]["successes"] += 1

    # ── Internal ────────────────────────────────────────

    def _check_one(self, r: dict) -> dict | None:
        try:
            sensor_id = r.get("sensor_id")
            step_id = r.get("step_id", "unknown")
            equip_id = r.get("equip_id", "unknown")
            sensor_type = r.get("sensor_type", "unknown")
            value = float(r.get("value", 0))
            normal_min = r.get("normal_min")
            normal_max = r.get("normal_max")
        except (TypeError, ValueError):
            return None

        # Check 1: Threshold breach (즉시 이상, 더 이상 검사 불필요)
        breach = self._check_threshold_breach(
            step_id, equip_id, sensor_type, value, normal_min, normal_max,
        )
        if breach:
            return breach

        # Check 2 & 3 require sufficient history
        if sensor_id is None:
            return None
        hist = self.history.get(sensor_id, [])
        if len(hist) < self.window_size:
            return None

        window = hist[-self.window_size:]
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std = math.sqrt(variance) if variance > 0 else 0.0

        outlier = self._check_statistical_outlier(
            step_id, equip_id, sensor_type, value, mean, std,
        )
        if outlier:
            return outlier

        return self._check_trend_shift(
            step_id, equip_id, sensor_type, value, mean, hist,
        )

    @staticmethod
    def _check_threshold_breach(step_id, equip_id, sensor_type, value, nmin, nmax):
        if nmin is None or nmax is None:
            return None
        try:
            nmin_f = float(nmin)
            nmax_f = float(nmax)
        except (TypeError, ValueError):
            return None
        if value >= nmin_f and value <= nmax_f:
            return None

        span = nmax_f - nmin_f if nmax_f > nmin_f else 1.0
        deviation = max(nmin_f - value, value - nmax_f, 0) / span
        confidence = min(0.95, 0.7 + deviation * 0.3)
        return {
            "step_id": step_id,
            "equip_id": equip_id,
            "sensor_type": sensor_type,
            "value": value,
            "anomaly_type": "threshold_breach",
            "severity": _severity_from_deviation(deviation),
            "confidence": round(confidence, 3),
            "message": (
                f"{sensor_type} 값 {value:.3f}이(가) 정상 범위 "
                f"[{nmin_f:.3f}, {nmax_f:.3f}]을 벗어남"
            ),
        }

    @staticmethod
    def _check_statistical_outlier(step_id, equip_id, sensor_type, value, mean, std):
        if std <= 0:
            return None
        z_score = abs(value - mean) / std
        if z_score <= 3.0:
            return None
        confidence = min(0.95, 0.6 + (z_score - 3.0) * 0.1)
        return {
            "step_id": step_id,
            "equip_id": equip_id,
            "sensor_type": sensor_type,
            "value": value,
            "anomaly_type": "statistical_outlier",
            "severity": _severity_from_zscore(z_score),
            "confidence": round(confidence, 3),
            "message": (
                f"{sensor_type} 값 {value:.3f} — "
                f"3σ 규칙 위반 (μ={mean:.3f}, σ={std:.3f}, z={z_score:.1f})"
            ),
        }

    @staticmethod
    def _check_trend_shift(step_id, equip_id, sensor_type, value, mean, hist):
        if len(hist) < 7:
            return None
        last_7 = hist[-7:]
        above = all(v > mean for v in last_7)
        below = all(v < mean for v in last_7)
        if not (above or below):
            return None
        direction = "상방" if above else "하방"
        return {
            "step_id": step_id,
            "equip_id": equip_id,
            "sensor_type": sensor_type,
            "value": value,
            "anomaly_type": "trend_shift",
            "severity": "MEDIUM",
            "confidence": 0.75,
            "message": (
                f"{sensor_type} — 연속 7개 읽기값이 평균 {direction} 편향 "
                f"(μ={mean:.3f}, 최근값={value:.3f})"
            ),
        }


def _severity_from_deviation(deviation: float) -> str:
    """정상 범위 이탈 비율로 심각도 결정."""
    if deviation > 0.5:
        return "CRITICAL"
    if deviation > 0.2:
        return "HIGH"
    return "MEDIUM"


def _severity_from_zscore(z: float) -> str:
    if z > 5.0:
        return "CRITICAL"
    if z > 4.0:
        return "HIGH"
    return "MEDIUM"
