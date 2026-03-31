"""
Advanced Anomaly Detection — Matrix Profile + Isolation Forest
==============================================================
업계 사례:
  - Sight Machine: 다변량 이상탐지 (Isolation Forest) 기반 품질 예측
  - Google TFT: Temporal Fusion Transformer로 시계열 예측 + 이상 감지
  - Matrix Profile (UCR/UNM): 비지도 시계열 패턴 매칭, discord 탐지

기존 SPC(3-sigma, Western Electric) 위에 다음을 보강:
  1. Matrix Profile: 시계열 패턴의 "이상 구간(discord)" 자동 발견
  2. Isolation Forest: 다변량 공간에서의 아웃라이어 탐지
  3. CUSUM (Cumulative Sum): 미세한 평균 이동 감지

사용법:
    detector = AdvancedAnomalyDetector()
    detector.update(readings)
    anomalies = detector.detect(readings)
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime

# 선택적 의존성
try:
    import stumpy
    HAS_STUMPY = True
except ImportError:
    HAS_STUMPY = False

try:
    from sklearn.ensemble import IsolationForest
    import numpy as np
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


# ═══════════════════════════════════════════════════════════════
#  CUSUM — 미세한 평균 이동 감지 (순수 Python)
# ═══════════════════════════════════════════════════════════════

class CUSUMDetector:
    """CUSUM (Cumulative Sum) 제어 차트.

    업계 참조: 반도체/배터리 제조에서 SPC 보완용으로 널리 사용.
    SPC 3-sigma가 놓치는 작은 평균 이동(0.5~1.5σ)을 감지한다.
    """

    def __init__(self, threshold: float = 5.0, drift: float = 0.5):
        self.threshold = threshold   # 알람 임계값 (σ 단위)
        self.drift = drift           # 허용 드리프트 (σ 단위)
        self.cum_pos = defaultdict(float)   # sensor_id → 양 방향 누적합
        self.cum_neg = defaultdict(float)   # sensor_id → 음 방향 누적합
        self.stats = defaultdict(lambda: {"mean": 0.0, "std": 1.0, "n": 0})

    def update_stats(self, sensor_id: str, value: float):
        """온라인 평균/표준편차 업데이트 (Welford 알고리즘)."""
        s = self.stats[sensor_id]
        s["n"] += 1
        n = s["n"]
        old_mean = s["mean"]
        s["mean"] = old_mean + (value - old_mean) / n
        if n > 1:
            # 온라인 분산 업데이트
            old_var = s["std"] ** 2 * (n - 2) / (n - 1) if n > 2 else 0
            new_var = old_var + (value - old_mean) * (value - s["mean"]) / (n - 1)
            s["std"] = max(1e-6, math.sqrt(new_var))

    def check(self, sensor_id: str, value: float) -> dict | None:
        """CUSUM 검정. 이상 발견 시 dict 반환, 아니면 None."""
        self.update_stats(sensor_id, value)
        s = self.stats[sensor_id]
        if s["n"] < 20:
            return None  # 충분한 데이터 축적 전

        z = (value - s["mean"]) / s["std"]

        self.cum_pos[sensor_id] = max(0, self.cum_pos[sensor_id] + z - self.drift)
        self.cum_neg[sensor_id] = max(0, self.cum_neg[sensor_id] - z - self.drift)

        if self.cum_pos[sensor_id] > self.threshold:
            self.cum_pos[sensor_id] = 0  # 리셋
            return {"direction": "upward", "cusum": round(self.cum_pos[sensor_id], 2)}

        if self.cum_neg[sensor_id] > self.threshold:
            self.cum_neg[sensor_id] = 0  # 리셋
            return {"direction": "downward", "cusum": round(self.cum_neg[sensor_id], 2)}

        return None


# ═══════════════════════════════════════════════════════════════
#  MATRIX PROFILE — 시계열 패턴 이상 구간 탐지
# ═══════════════════════════════════════════════════════════════

class MatrixProfileDetector:
    """Matrix Profile 기반 시계열 이상 감지.

    업계 참조:
      - UCR Matrix Profile: 비지도 시계열 이상 감지의 표준
      - STUMPY 라이브러리: O(n log n) 구현
      - 실제 사용: 전력 소비 이상, 기계 진동 이상 감지

    원리: 서브시퀀스 간 최소 거리(Matrix Profile)를 계산하여
          다른 구간과 가장 다른 구간(discord)을 이상으로 판단한다.
    """

    def __init__(self, window_size: int = 10, top_k: int = 3):
        self.window_size = window_size
        self.top_k = top_k
        self.series = defaultdict(list)  # sensor_id → time series
        self.max_history = 200

    def update(self, sensor_id: str, value: float):
        """시계열 데이터 추가."""
        self.series[sensor_id].append(value)
        if len(self.series[sensor_id]) > self.max_history:
            self.series[sensor_id] = self.series[sensor_id][-self.max_history:]

    def detect_discords(self, sensor_id: str) -> list[dict]:
        """Discord(이상 구간)을 탐지한다."""
        ts = self.series.get(sensor_id, [])
        min_length = self.window_size * 3

        if len(ts) < min_length:
            return []

        if HAS_STUMPY:
            return self._detect_with_stumpy(sensor_id, ts)
        else:
            return self._detect_fallback(sensor_id, ts)

    def _detect_with_stumpy(self, sensor_id: str, ts: list) -> list[dict]:
        """STUMPY를 사용한 Matrix Profile Discord 탐지."""
        try:
            import numpy as np
            arr = np.array(ts, dtype=np.float64)
            mp = stumpy.stump(arr, m=self.window_size)
            profile = mp[:, 0].astype(float)

            # Discord: Profile 값이 가장 큰 구간
            mean_p = float(np.mean(profile))
            std_p = float(np.std(profile))
            if std_p < 1e-6:
                return []

            discords = []
            for idx in range(len(profile)):
                z = (profile[idx] - mean_p) / std_p
                if z > 2.5:  # 2.5σ 이상 = discord
                    discords.append({
                        "sensor_id": sensor_id,
                        "position": idx,
                        "profile_value": round(float(profile[idx]), 3),
                        "z_score": round(z, 2),
                        "method": "matrix_profile_stumpy",
                    })

            discords.sort(key=lambda d: -d["z_score"])
            return discords[:self.top_k]
        except Exception:
            return self._detect_fallback(sensor_id, ts)

    def _detect_fallback(self, sensor_id: str, ts: list) -> list[dict]:
        """순수 Python 폴백: 슬라이딩 윈도우 기반 간이 Matrix Profile."""
        n = len(ts)
        w = self.window_size
        if n < w * 2:
            return []

        # 각 서브시퀀스의 최소 거리 계산 (brute-force, O(n²))
        profile = []
        for i in range(n - w + 1):
            sub_i = ts[i:i + w]
            min_dist = float("inf")
            for j in range(n - w + 1):
                if abs(i - j) < w:  # 자기 자신 및 겹치는 구간 제외
                    continue
                sub_j = ts[j:j + w]
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(sub_i, sub_j)))
                min_dist = min(min_dist, dist)
            profile.append(min_dist)

        if not profile:
            return []

        mean_p = sum(profile) / len(profile)
        var_p = sum((x - mean_p) ** 2 for x in profile) / len(profile)
        std_p = math.sqrt(var_p) if var_p > 0 else 1e-6

        discords = []
        for idx, val in enumerate(profile):
            z = (val - mean_p) / std_p
            if z > 2.5:
                discords.append({
                    "sensor_id": sensor_id,
                    "position": idx,
                    "profile_value": round(val, 3),
                    "z_score": round(z, 2),
                    "method": "matrix_profile_fallback",
                })

        discords.sort(key=lambda d: -d["z_score"])
        return discords[:self.top_k]


# ═══════════════════════════════════════════════════════════════
#  ISOLATION FOREST — 다변량 이상탐지
# ═══════════════════════════════════════════════════════════════

class MultivariatAnomalyDetector:
    """Isolation Forest 기반 다변량 이상탐지.

    업계 참조:
      - Sight Machine: 공정별 다변량 Isolation Forest
      - Samsung SDI 스마트팩토리 2.0: 다차원 품질 예측

    단일 센서의 SPC는 각 센서를 독립적으로 보지만,
    다변량 탐지는 센서 조합에서의 이상을 포착한다.
    예: 온도는 정상, 전류도 정상이지만, 온도-전류 조합이 비정상.
    """

    def __init__(self, contamination: float = 0.05, min_samples: int = 30):
        self.contamination = contamination
        self.min_samples = min_samples
        self.step_data = defaultdict(list)  # step_id → list of feature vectors
        self.step_features = defaultdict(list)  # step_id → feature names
        self.models = {}  # step_id → fitted IsolationForest
        self.max_history = 200

    def update(self, step_id: str, features: dict[str, float]):
        """공정별 다변량 데이터 추가.

        Args:
            step_id: 공정 ID (예: "PS-103")
            features: 센서 값 딕셔너리 (예: {"temperature": 35.2, "vibration": 1.5})
        """
        if not features:
            return

        # 피처 이름 정렬 (일관된 순서 보장)
        sorted_keys = sorted(features.keys())
        if not self.step_features[step_id]:
            self.step_features[step_id] = sorted_keys

        vector = [features.get(k, 0.0) for k in self.step_features[step_id]]
        self.step_data[step_id].append(vector)

        if len(self.step_data[step_id]) > self.max_history:
            self.step_data[step_id] = self.step_data[step_id][-self.max_history:]

    def fit(self, step_id: str) -> bool:
        """공정별 Isolation Forest 모델을 학습한다."""
        if not HAS_SKLEARN:
            return False

        data = self.step_data.get(step_id, [])
        if len(data) < self.min_samples:
            return False

        try:
            X = np.array(data)
            model = IsolationForest(
                contamination=self.contamination,
                n_estimators=100,
                random_state=42,
            )
            model.fit(X)
            self.models[step_id] = model
            return True
        except Exception:
            return False

    def predict(self, step_id: str, features: dict[str, float]) -> dict | None:
        """다변량 이상 여부를 판정한다.

        Returns:
            이상이면 {"anomaly": True, "score": float}, 정상이면 None
        """
        model = self.models.get(step_id)
        if model is None:
            # 모델 없으면 자동 피팅 시도
            if not self.fit(step_id):
                return None
            model = self.models.get(step_id)
            if model is None:
                return None

        try:
            sorted_keys = self.step_features[step_id]
            vector = np.array([[features.get(k, 0.0) for k in sorted_keys]])
            prediction = model.predict(vector)[0]
            score = model.decision_function(vector)[0]

            if prediction == -1:  # 이상
                return {
                    "anomaly": True,
                    "score": round(float(score), 3),
                    "features": {k: features.get(k, 0.0) for k in sorted_keys},
                    "method": "isolation_forest",
                }
        except Exception:
            pass
        return None


# ═══════════════════════════════════════════════════════════════
#  COMPOSITE DETECTOR — 모든 방법을 통합
# ═══════════════════════════════════════════════════════════════

class AdvancedAnomalyDetector:
    """SPC + CUSUM + Matrix Profile + Isolation Forest 통합 이상 감지.

    기존 AnomalyDetector(SPC)를 보강하며, 대체하지 않는다.
    """

    def __init__(self):
        self.cusum = CUSUMDetector(threshold=5.0, drift=0.5)
        self.matrix_profile = MatrixProfileDetector(window_size=10, top_k=3)
        self.multivariate = MultivariatAnomalyDetector(contamination=0.05)
        self._iteration = 0

    def update(self, readings: list[dict]):
        """센서 읽기값을 모든 검출기에 전달한다."""
        step_features = defaultdict(dict)

        for r in readings:
            sensor_id = r.get("sensor_id")
            step_id = r.get("step_id", "unknown")
            sensor_type = r.get("sensor_type", "unknown")
            value = r.get("value")

            if sensor_id is None or value is None:
                continue

            try:
                val = float(value)
            except (TypeError, ValueError):
                continue

            # CUSUM 업데이트
            self.cusum.update_stats(sensor_id, val)

            # Matrix Profile 업데이트
            self.matrix_profile.update(sensor_id, val)

            # 다변량 데이터 수집
            step_features[step_id][sensor_type] = val

        # 다변량 업데이트
        for step_id, features in step_features.items():
            self.multivariate.update(step_id, features)

        self._iteration += 1

    def detect(self, readings: list[dict]) -> list[dict]:
        """고급 이상 감지를 실행한다.

        Returns:
            anomaly dicts: 기존 AnomalyDetector와 동일한 형식으로 반환
        """
        anomalies = []
        step_features = defaultdict(dict)

        for r in readings:
            sensor_id = r.get("sensor_id")
            step_id = r.get("step_id", "unknown")
            equip_id = r.get("equip_id", "unknown")
            sensor_type = r.get("sensor_type", "unknown")
            value = r.get("value")

            if sensor_id is None or value is None:
                continue

            try:
                val = float(value)
            except (TypeError, ValueError):
                continue

            step_features[step_id][sensor_type] = val

            # CUSUM 검정
            cusum_result = self.cusum.check(sensor_id, val)
            if cusum_result:
                anomalies.append({
                    "step_id": step_id,
                    "equip_id": equip_id,
                    "sensor_type": sensor_type,
                    "value": val,
                    "anomaly_type": "cusum_shift",
                    "severity": "MEDIUM",
                    "confidence": 0.72,
                    "message": (
                        f"{sensor_type} CUSUM {cusum_result['direction']} shift 감지 — "
                        f"미세한 평균 이동 포착"
                    ),
                    "detection_method": "cusum",
                })

        # Matrix Profile discord 탐지 (5 이터레이션마다)
        if self._iteration % 5 == 0:
            for sensor_id, ts in self.matrix_profile.series.items():
                discords = self.matrix_profile.detect_discords(sensor_id)
                for d in discords:
                    # sensor_id에서 step_id 추출
                    matched = [r for r in readings if r.get("sensor_id") == sensor_id]
                    if matched:
                        r = matched[0]
                        anomalies.append({
                            "step_id": r.get("step_id", "unknown"),
                            "equip_id": r.get("equip_id", "unknown"),
                            "sensor_type": r.get("sensor_type", "unknown"),
                            "value": r.get("value", 0),
                            "anomaly_type": "matrix_profile_discord",
                            "severity": "HIGH" if d["z_score"] > 3.5 else "MEDIUM",
                            "confidence": round(min(0.95, 0.6 + d["z_score"] * 0.08), 3),
                            "message": (
                                f"시계열 패턴 이상 구간 감지 (z={d['z_score']:.1f}, "
                                f"method={d['method']})"
                            ),
                            "detection_method": d["method"],
                        })

        # Isolation Forest 다변량 탐지 (10 이터레이션마다 모델 재학습)
        if self._iteration % 10 == 0:
            for step_id in step_features:
                self.multivariate.fit(step_id)

        for step_id, features in step_features.items():
            result = self.multivariate.predict(step_id, features)
            if result and result.get("anomaly"):
                anomalies.append({
                    "step_id": step_id,
                    "equip_id": "multi",
                    "sensor_type": "multivariate",
                    "value": result["score"],
                    "anomaly_type": "multivariate_outlier",
                    "severity": "HIGH" if result["score"] < -0.3 else "MEDIUM",
                    "confidence": round(min(0.9, 0.65 + abs(result["score"]) * 0.2), 3),
                    "message": (
                        f"다변량 이상 감지 (score={result['score']:.3f}) — "
                        f"센서 조합에서 비정상 패턴"
                    ),
                    "detection_method": "isolation_forest",
                })

        return anomalies

    def get_status(self) -> dict:
        """현재 검출기 상태 요약."""
        return {
            "iteration": self._iteration,
            "cusum_tracked_sensors": len(self.cusum.stats),
            "matrix_profile_series": len(self.matrix_profile.series),
            "isolation_forest_models": len(self.multivariate.models),
            "has_stumpy": HAS_STUMPY,
            "has_sklearn": HAS_SKLEARN,
        }
