"""
Self-Healing Agents — Dark Factory 자율 복구 루프
==================================================
감지(Detect) → 진단(Diagnose) → 복구(Recover) → 검증(Verify) → 학습(Learn)

v3 에이전트는 온톨로지 구조를 개선하는 오프라인 시스템이었다면,
v4 에이전트는 실시간 센서 데이터를 기반으로 공장 이상을 자율적으로 복구한다.

에이전트:
  - AnomalyDetector: SPC 기반 실시간 이상 감지 (Western Electric rules)
  - RootCauseAnalyzer: 온톨로지 경로 역추적 원인 진단
  - AutoRecoveryAgent: 파라미터 자동 보정 + 플레이북 기반 복구
"""
import random
import math
from collections import defaultdict
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
#  RECOVERY PLAYBOOK — 원인 유형별 복구 전략
# ═══════════════════════════════════════════════════════════════

RECOVERY_PLAYBOOK = {
    "equipment_mtbf": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.003, "risk": "LOW"},
    ],
    "defect_mode_match": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.005, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    "material_anomaly": [
        {"action": "MATERIAL_SWITCH", "param": None, "adjustment": None, "risk": "HIGH"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    "upstream_degradation": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
    ],
    "no_inspection": [
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    # 인과 체인에서 도출되는 원인 유형들
    "precision_loss": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.003, "risk": "LOW"},
    ],
    "coating_defect": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.004, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    "contact_failure": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.005, "risk": "LOW"},
    ],
    "yield_drop": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.003, "risk": "LOW"},
    ],
    "temperature_rise": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.01, "risk": "LOW"},
    ],
    "pressure_drop": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.003, "risk": "LOW"},
    ],
    "vibration_increase": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.015, "risk": "MEDIUM"},
    ],
    "welding_defect": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.005, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    "joint_weakness": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.004, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    "bearing_wear": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.025, "risk": "MEDIUM"},
    ],
    "cooling_failure": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
    ],
    "current_anomaly": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.003, "risk": "LOW"},
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.015, "risk": "MEDIUM"},
    ],
    "process_variation": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
    ],
    "property_deviation": [
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
    ],
    "equipment_wear": [
        {"action": "EQUIPMENT_RESET", "param": "oee", "adjustment": 0.02, "risk": "MEDIUM"},
    ],
    "material_lot_change": [
        {"action": "INCREASE_INSPECTION", "param": None, "adjustment": None, "risk": "LOW"},
        {"action": "ADJUST_PARAMETER", "param": "yield_rate", "adjustment": 0.002, "risk": "LOW"},
    ],
    "unknown": [
        {"action": "ESCALATE", "param": None, "adjustment": None, "risk": "CRITICAL"},
    ],
}

ACTION_DEFAULTS = {
    "ADJUST_PARAMETER": {"param": "yield_rate", "adjustment": 0.003},
    "EQUIPMENT_RESET": {"param": "oee", "adjustment": 0.02},
    "MATERIAL_SWITCH": {"param": None, "adjustment": None},
    "INCREASE_INSPECTION": {"param": None, "adjustment": None},
    "ESCALATE": {"param": None, "adjustment": None},
}

RISK_NUMERIC = {"LOW": 0.1, "MEDIUM": 0.3, "HIGH": 0.6, "CRITICAL": 0.9}


def requires_hitl(action: dict, diagnosis: dict, min_confidence: float = 0.62,
                  high_risk_threshold: float = 0.6,
                  medium_requires_history: bool = True) -> tuple[bool, str]:
    """고위험/저신뢰 복구 액션에 대해 HITL 게이트를 판단한다."""
    risk_level = str(action.get("risk_level", "MEDIUM"))
    risk_num = RISK_NUMERIC.get(risk_level, 0.5)
    confidence = float(action.get("confidence", 0.0) or 0.0)
    history_matched = bool(diagnosis.get("failure_chain_matched", False))

    if confidence < min_confidence:
        return True, f"low_confidence<{min_confidence:.2f}"
    if risk_num >= high_risk_threshold:
        return True, f"high_risk={risk_level}"
    if medium_requires_history and risk_num >= 0.3 and not history_matched:
        return True, "no_history_match_for_medium_plus_risk"
    return False, ""


# ═══════════════════════════════════════════════════════════════
#  AGENT 1: AnomalyDetector — SPC 기반 실시간 이상 감지
# ═══════════════════════════════════════════════════════════════

class AnomalyDetector:
    """SPC 기반 실시간 이상 감지 에이전트.
    센서 읽기값의 통계적 이상을 감지한다."""

    def __init__(self):
        self.history = defaultdict(list)   # sensor_id → list of values
        self.window_size = 20
        self.recovery_feedback = defaultdict(lambda: {"attempts": 0, "successes": 0})

    def update(self, readings: list):
        """센서 읽기값을 히스토리에 추가한다.

        Args:
            readings: list of dicts, each with at least
                      {sensor_id, step_id, equip_id, sensor_type, value,
                       normal_min, normal_max}
        """
        for r in readings:
            try:
                sid = r.get("sensor_id")
                val = r.get("value")
                if sid is not None and val is not None:
                    self.history[sid].append(float(val))
            except (TypeError, ValueError):
                continue

    def detect(self, readings: list) -> list:
        """센서 읽기값에서 이상을 감지한다.

        Args:
            readings: list of dicts with sensor reading data.

        Returns:
            list of anomaly dicts.
        """
        anomalies = []

        for r in readings:
            try:
                sensor_id = r.get("sensor_id")
                step_id = r.get("step_id", "unknown")
                equip_id = r.get("equip_id", "unknown")
                sensor_type = r.get("sensor_type", "unknown")
                value = float(r.get("value", 0))
                normal_min = r.get("normal_min")
                normal_max = r.get("normal_max")
            except (TypeError, ValueError):
                continue

            # ── Check 1: Threshold breach (즉시 이상) ──
            if normal_min is not None and normal_max is not None:
                try:
                    nmin = float(normal_min)
                    nmax = float(normal_max)
                    if value < nmin or value > nmax:
                        span = nmax - nmin if nmax > nmin else 1.0
                        deviation = max(nmin - value, value - nmax, 0) / span
                        severity = self._severity_from_deviation(deviation)
                        confidence = min(0.95, 0.7 + deviation * 0.3)
                        anomalies.append({
                            "step_id": step_id,
                            "equip_id": equip_id,
                            "sensor_type": sensor_type,
                            "value": value,
                            "anomaly_type": "threshold_breach",
                            "severity": severity,
                            "confidence": round(confidence, 3),
                            "message": (
                                f"{sensor_type} 값 {value:.3f}이(가) 정상 범위 "
                                f"[{nmin:.3f}, {nmax:.3f}]을 벗어남"
                            ),
                        })
                        continue  # threshold breach가 발견되면 추가 검사 불필요
                except (TypeError, ValueError):
                    pass

            # ── Check 2 & 3: Statistical outlier / Trend shift ──
            if sensor_id is None:
                continue

            hist = self.history.get(sensor_id, [])
            if len(hist) < self.window_size:
                continue

            window = hist[-self.window_size:]
            mean = sum(window) / len(window)
            variance = sum((x - mean) ** 2 for x in window) / len(window)
            std = math.sqrt(variance) if variance > 0 else 0.0

            # ── Check 2: 3-sigma rule (통계적 이상치) ──
            if std > 0:
                z_score = abs(value - mean) / std
                if z_score > 3.0:
                    severity = self._severity_from_zscore(z_score)
                    confidence = min(0.95, 0.6 + (z_score - 3.0) * 0.1)
                    anomalies.append({
                        "step_id": step_id,
                        "equip_id": equip_id,
                        "sensor_type": sensor_type,
                        "value": value,
                        "anomaly_type": "statistical_outlier",
                        "severity": severity,
                        "confidence": round(confidence, 3),
                        "message": (
                            f"{sensor_type} 값 {value:.3f} — "
                            f"3σ 규칙 위반 (μ={mean:.3f}, σ={std:.3f}, z={z_score:.1f})"
                        ),
                    })
                    continue

            # ── Check 3: Western Electric rule — 연속 7점 한쪽 편향 ──
            if len(hist) >= 7:
                last_7 = hist[-7:]
                above = all(v > mean for v in last_7)
                below = all(v < mean for v in last_7)
                if above or below:
                    direction = "상방" if above else "하방"
                    confidence = 0.75
                    anomalies.append({
                        "step_id": step_id,
                        "equip_id": equip_id,
                        "sensor_type": sensor_type,
                        "value": value,
                        "anomaly_type": "trend_shift",
                        "severity": "MEDIUM",
                        "confidence": round(confidence, 3),
                        "message": (
                            f"{sensor_type} — 연속 7개 읽기값이 평균 {direction} 편향 "
                            f"(μ={mean:.3f}, 최근값={value:.3f})"
                        ),
                    })

        return anomalies

    # ── Internal helpers ──

    @staticmethod
    def _severity_from_deviation(deviation: float) -> str:
        """정상 범위 이탈 비율로 심각도 결정."""
        if deviation > 0.5:
            return "CRITICAL"
        elif deviation > 0.2:
            return "HIGH"
        else:
            return "MEDIUM"

    @staticmethod
    def _severity_from_zscore(z: float) -> str:
        """Z-score로 심각도 결정."""
        if z > 5.0:
            return "CRITICAL"
        elif z > 4.0:
            return "HIGH"
        else:
            return "MEDIUM"

    def learn(self, anomaly: dict, diagnosis: dict, recovery_result: dict):
        """복구 결과를 단순 누적해 추후 감지 파라미터 조정의 근거로 사용한다."""
        key = (
            anomaly.get("step_id", "unknown"),
            anomaly.get("sensor_type", "unknown"),
            anomaly.get("anomaly_type", "unknown"),
        )
        self.recovery_feedback[key]["attempts"] += 1
        if recovery_result.get("success", False):
            self.recovery_feedback[key]["successes"] += 1


# ═══════════════════════════════════════════════════════════════
#  AGENT 2: RootCauseAnalyzer — 온톨로지 경로 역추적 원인 진단
# ═══════════════════════════════════════════════════════════════

class RootCauseAnalyzer:
    """온톨로지 경로 역추적 기반 원인 진단 에이전트.
    이상이 감지된 공정에서 출발하여 관련 장비, 자재, 결함모드를 탐색한다."""

    def __init__(self):
        self.cause_history = defaultdict(list)  # (step_id, sensor_type) → [cause_type, ...]

    def analyze(self, conn, anomaly: dict) -> dict:
        """이상 원인을 온톨로지 그래프에서 추적한다.

        Args:
            conn: Kuzu connection object.
            anomaly: anomaly dict from AnomalyDetector.

        Returns:
            diagnosis dict with ranked cause candidates.
        """
        start_time = datetime.now()
        step_id = anomaly.get("step_id", "unknown")
        sensor_type = anomaly.get("sensor_type", "unknown")
        severity = anomaly.get("severity", "MEDIUM")
        candidates = []
        paths_explored = 0

        # ── Path 1: 공정 기본 정보 확인 ──
        step_info = self._query_step(conn, step_id)
        paths_explored += 1
        if not step_info:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "step_id": step_id,
                "candidates": [],
                "analysis_time_ms": round(elapsed, 1),
                "paths_explored": paths_explored,
            }

        # ── Path 2: 장비 경로 — MTBF 초과 여부 ──
        equip_candidates = self._check_equipment_path(conn, step_id)
        candidates.extend(equip_candidates)
        paths_explored += 1

        # ── Path 3: 자재 경로 — 공급 이상 여부 ──
        material_candidates = self._check_material_path(conn, step_id)
        candidates.extend(material_candidates)
        paths_explored += 1

        # ── Path 4: 결함 모드 경로 — 센서 유형별 매칭 ──
        defect_candidates = self._check_defect_path(conn, step_id, sensor_type)
        candidates.extend(defect_candidates)
        paths_explored += 1

        # ── Path 5: 상류 공정 경로 — 수율 저하 전파 ──
        upstream_candidates = self._check_upstream_path(conn, step_id)
        candidates.extend(upstream_candidates)
        paths_explored += 1

        # ── Path 6: 검사 커버리지 — 누락 여부 ──
        inspection_candidates = self._check_inspection_path(conn, step_id)
        candidates.extend(inspection_candidates)
        paths_explored += 1

        # ── Path 7: 과거 사례 기반 학습 ──
        history_key = (step_id, sensor_type)
        if history_key in self.cause_history:
            past_causes = self.cause_history[history_key]
            # 과거에 확인된 원인은 높은 신뢰도 부여
            cause_counts = defaultdict(int)
            for c in past_causes:
                cause_counts[c] += 1
            for cause_type, count in cause_counts.items():
                candidates.append({
                    "cause_type": cause_type,
                    "cause_id": f"HIST-{step_id}",
                    "cause_name": f"과거 확인 원인: {cause_type}",
                    "confidence": min(0.95, 0.90 + count * 0.01),
                    "evidence": f"과거 {count}회 동일 원인 확인됨",
                    "suggested_action": f"이전 복구 조치 재적용 ({cause_type})",
                })
            paths_explored += 1

        # ── Confidence boost: 과거 이력이 있는 candidate에 가중 ──
        if history_key in self.cause_history:
            confirmed_types = set(self.cause_history[history_key])
            for c in candidates:
                if c["cause_type"] in confirmed_types and "HIST" not in c.get("cause_id", ""):
                    c["confidence"] = min(0.95, c["confidence"] + 0.05)

        # 중복 제거: 같은 cause_id가 여러 번 나올 수 있으므로 가장 높은 confidence만 유지
        seen = {}
        for c in candidates:
            cid = c["cause_id"]
            if cid not in seen or c["confidence"] > seen[cid]["confidence"]:
                seen[cid] = c
        candidates = sorted(seen.values(), key=lambda x: -x["confidence"])

        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        return {
            "step_id": step_id,
            "candidates": candidates,
            "analysis_time_ms": round(elapsed, 1),
            "paths_explored": paths_explored,
        }

    def learn(self, step_id: str, sensor_type: str, confirmed_cause: str):
        """확인된 원인을 기록하여 미래 진단에 활용한다.

        Args:
            step_id: 공정 단계 ID.
            sensor_type: 센서 유형.
            confirmed_cause: 확인된 원인 유형 (e.g. 'equipment_mtbf').
        """
        self.cause_history[(step_id, sensor_type)].append(confirmed_cause)

    # ── Internal query helpers ──

    def _query_step(self, conn, step_id: str) -> dict:
        """공정 단계 기본 정보를 조회한다."""
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep) WHERE ps.id = $step_id "
                "RETURN ps.id, ps.name, ps.yield_rate, ps.oee, ps.automation, ps.cycle_time",
                {"step_id": step_id},
            )
            if r.has_next():
                row = r.get_next()
                return {
                    "id": row[0], "name": row[1],
                    "yield_rate": float(row[2]) if row[2] is not None else 0.0,
                    "oee": float(row[3]) if row[3] is not None else 0.0,
                    "automation": row[4], "cycle_time": row[5],
                }
        except Exception:
            pass
        return {}

    def _check_equipment_path(self, conn, step_id: str) -> list:
        """장비 경로: MTBF 초과, 고비용, 노후화 여부를 확인한다."""
        candidates = []
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep)-[:USES_EQUIPMENT]->(eq:Equipment) "
                "WHERE ps.id = $step_id "
                "RETURN eq.id, eq.name, eq.mtbf_hours, eq.cost",
                {"step_id": step_id},
            )
            while r.has_next():
                row = r.get_next()
                eq_id = row[0]
                eq_name = row[1]
                mtbf = float(row[2]) if row[2] is not None else 0.0
                cost = float(row[3]) if row[3] is not None else 0.0

                # MTBF가 낮은 장비는 고장 가능성 높음
                if mtbf < 5000:
                    candidates.append({
                        "cause_type": "equipment_mtbf",
                        "cause_id": eq_id,
                        "cause_name": f"장비 MTBF 위험: {eq_name}",
                        "confidence": 0.85,
                        "evidence": f"MTBF {mtbf:.0f}h (기준 5000h 미만), 투자액 {cost:,.0f}",
                        "suggested_action": f"장비 '{eq_name}' 재보정 또는 예방정비 실시",
                    })
                elif cost > 200000:
                    # 고가 장비는 중간 수준의 의심
                    candidates.append({
                        "cause_type": "equipment_mtbf",
                        "cause_id": eq_id,
                        "cause_name": f"고가 장비 점검 필요: {eq_name}",
                        "confidence": 0.60,
                        "evidence": f"고가 장비 (투자 {cost:,.0f}), MTBF {mtbf:.0f}h",
                        "suggested_action": f"장비 '{eq_name}' 상태 점검 권고",
                    })
        except Exception:
            pass
        return candidates

    def _check_material_path(self, conn, step_id: str) -> list:
        """자재 경로: 공급 이상, 비용 변동 여부를 확인한다."""
        candidates = []
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep)-[:CONSUMES]->(mat:Material) "
                "WHERE ps.id = $step_id "
                "RETURN mat.id, mat.name, mat.supplier, mat.cost_per_unit, mat.category",
                {"step_id": step_id},
            )
            while r.has_next():
                row = r.get_next()
                mat_id = row[0]
                mat_name = row[1]
                supplier = row[2] if row[2] is not None else "unknown"
                cost = float(row[3]) if row[3] is not None else 0.0
                category = row[4] if row[4] is not None else "unknown"

                # 고비용 자재 또는 외부 공급업체는 변동 리스크가 높음
                if cost > 10.0 and supplier not in ("자체제작",):
                    candidates.append({
                        "cause_type": "material_anomaly",
                        "cause_id": mat_id,
                        "cause_name": f"자재 공급 이상 의심: {mat_name}",
                        "confidence": 0.70,
                        "evidence": (
                            f"외부 공급 자재 (공급사: {supplier}, "
                            f"단가: {cost:,.1f}, 분류: {category})"
                        ),
                        "suggested_action": f"자재 '{mat_name}' 입고 검사 강화 및 LOT 변경 검토",
                    })
        except Exception:
            pass
        return candidates

    def _check_defect_path(self, conn, step_id: str, sensor_type: str) -> list:
        """결함 모드 경로: 센서 유형과 매칭되는 결함 모드를 찾는다."""
        candidates = []
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep)-[:HAS_DEFECT]->(dm:DefectMode) "
                "WHERE ps.id = $step_id "
                "RETURN dm.id, dm.name, dm.category, dm.severity, dm.occurrence, dm.detection",
                {"step_id": step_id},
            )
            while r.has_next():
                row = r.get_next()
                dm_id = row[0]
                dm_name = row[1]
                dm_cat = row[2] if row[2] is not None else ""
                dm_sev = int(row[3]) if row[3] is not None else 5
                dm_occ = int(row[4]) if row[4] is not None else 5
                dm_det = int(row[5]) if row[5] is not None else 5
                rpn = dm_sev * dm_occ * dm_det

                # 센서 유형과 결함 카테고리 매칭 (계측, 제어, 공정변동 등)
                type_match = self._sensor_defect_match(sensor_type, dm_cat)
                base_confidence = 0.80 if type_match else 0.55

                # RPN이 높을수록 더 의심
                if rpn > 100:
                    base_confidence = min(0.90, base_confidence + 0.05)

                candidates.append({
                    "cause_type": "defect_mode_match",
                    "cause_id": dm_id,
                    "cause_name": f"결함 모드 매칭: {dm_name}",
                    "confidence": round(base_confidence, 3),
                    "evidence": (
                        f"결함 '{dm_name}' (분류: {dm_cat}, RPN={rpn}, "
                        f"센서 매칭={'예' if type_match else '아니오'})"
                    ),
                    "suggested_action": f"결함 모드 '{dm_name}' 대응 절차 실행",
                })
        except Exception:
            pass
        return candidates

    def _check_upstream_path(self, conn, step_id: str) -> list:
        """상류 공정 경로: 이전 공정의 수율 저하가 전파되었는지 확인한다."""
        candidates = []
        try:
            r = conn.execute(
                "MATCH (prev:ProcessStep)-[:NEXT_STEP]->(ps:ProcessStep) "
                "WHERE ps.id = $step_id "
                "RETURN prev.id, prev.name, prev.yield_rate, prev.oee",
                {"step_id": step_id},
            )
            while r.has_next():
                row = r.get_next()
                prev_id = row[0]
                prev_name = row[1]
                prev_yield = float(row[2]) if row[2] is not None else 1.0
                prev_oee = float(row[3]) if row[3] is not None else 1.0

                if prev_yield < 0.995 or prev_oee < 0.80:
                    candidates.append({
                        "cause_type": "upstream_degradation",
                        "cause_id": prev_id,
                        "cause_name": f"상류 공정 수율 저하: {prev_name}",
                        "confidence": 0.65,
                        "evidence": (
                            f"상류 공정 '{prev_name}' 수율 {prev_yield:.3f}, "
                            f"OEE {prev_oee:.3f}"
                        ),
                        "suggested_action": f"상류 공정 '{prev_name}' 우선 점검 후 순차 복구",
                    })
        except Exception:
            pass
        return candidates

    def _check_inspection_path(self, conn, step_id: str) -> list:
        """검사 커버리지 경로: 검사 연결이 누락되었는지 확인한다."""
        candidates = []
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep) WHERE ps.id = $step_id "
                "OPTIONAL MATCH (insp:ProcessStep)-[:INSPECTS]->(ps) "
                "RETURN ps.id, insp.id",
                {"step_id": step_id},
            )
            has_inspection = False
            while r.has_next():
                row = r.get_next()
                if row[1] is not None:
                    has_inspection = True
                    break

            if not has_inspection:
                candidates.append({
                    "cause_type": "no_inspection",
                    "cause_id": f"INSP-GAP-{step_id}",
                    "cause_name": f"검사 연결 누락: {step_id}",
                    "confidence": 0.50,
                    "evidence": f"공정 '{step_id}'에 연결된 검사 공정이 없음",
                    "suggested_action": f"공정 '{step_id}'에 인라인 검사 추가 권고",
                })
        except Exception:
            pass
        return candidates

    @staticmethod
    def _sensor_defect_match(sensor_type: str, defect_category: str) -> bool:
        """센서 유형과 결함 카테고리 간 연관성을 판단한다."""
        mapping = {
            "temperature": ("공정변동", "마모", "오염"),
            "pressure": ("공정변동", "품질"),
            "vibration": ("마모", "정밀도"),
            "current": ("제어", "계측"),
            "voltage": ("제어", "계측"),
            "flow_rate": ("공정변동", "오염"),
            "humidity": ("오염", "품질"),
            "force": ("정밀도", "체결"),
            "torque": ("정밀도", "체결", "품질"),
            "speed": ("제어", "공정변동"),
        }
        related_categories = mapping.get(sensor_type, ())
        return defect_category in related_categories


# ═══════════════════════════════════════════════════════════════
#  AGENT 3: AutoRecoveryAgent — 자동 복구
# ═══════════════════════════════════════════════════════════════

class AutoRecoveryAgent:
    """자동 복구 에이전트. 진단 결과를 바탕으로 파라미터를 자동 보정한다."""

    _recovery_counter = 0

    def __init__(self):
        self.recovery_playbook = dict(RECOVERY_PLAYBOOK)
        self.success_history = defaultdict(lambda: {"attempts": 0, "successes": 0})

    def plan_recovery(self, conn, diagnosis: dict, anomaly: dict) -> list:
        """진단 결과로부터 복구 계획을 수립한다.

        Args:
            conn: Kuzu connection object.
            diagnosis: diagnosis dict from RootCauseAnalyzer.
            anomaly: original anomaly dict from AnomalyDetector.

        Returns:
            sorted list of recovery action dicts.
        """
        actions = []
        candidates = diagnosis.get("candidates", [])
        step_id = diagnosis.get("step_id", anomaly.get("step_id", "unknown"))

        # 상위 3개 원인 후보에 대해 복구 계획 수립
        for candidate in candidates[:3]:
            cause_type = candidate.get("cause_type", "unknown")
            cause_confidence = candidate.get("confidence", 0.0)
            playbook_entries = self._resolve_playbook_entries(conn, cause_type)

            if not playbook_entries:
                playbook_entries = self._resolve_playbook_entries(conn, "unknown")

            for entry in playbook_entries:
                action_type = entry["action"]
                param = entry["param"]
                adjustment = entry["adjustment"]
                risk_str = entry["risk"]
                risk_numeric = RISK_NUMERIC.get(risk_str, 0.5)

                # 과거 성공률 반영
                history_key = (action_type, cause_type)
                hist = self.success_history[history_key]
                if hist["attempts"] > 0:
                    success_rate = hist["successes"] / hist["attempts"]
                    # 과거 성공률이 높으면 신뢰도 보정
                    adjusted_confidence = cause_confidence * (0.7 + 0.3 * success_rate)
                else:
                    adjusted_confidence = cause_confidence

                # 현재 파라미터 값 조회
                old_value = self._get_current_value(conn, step_id, param)
                new_value = self._compute_new_value(old_value, adjustment, param)

                actions.append({
                    "action_type": action_type,
                    "target_step": step_id,
                    "parameter": param,
                    "old_value": old_value,
                    "new_value": new_value,
                    "confidence": round(adjusted_confidence, 3),
                    "risk_level": risk_str,
                    "cause_type": cause_type,
                    "cause_name": candidate.get("cause_name", ""),
                    "playbook_source": entry.get("source", "hardcoded"),
                    "playbook_id": entry.get("id"),
                })

        # 리스크 레벨 순 정렬: LOW → MEDIUM → HIGH → CRITICAL
        # 같은 리스크 레벨 내에서는 confidence 높은 순
        _RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        actions.sort(
            key=lambda a: (
                _RISK_ORDER.get(a["risk_level"], 2),
                -a["confidence"],
            ),
        )
        return actions

    def _resolve_playbook_entries(self, conn, cause_type: str) -> list:
        """L4 ResponsePlaybook를 우선 사용하고, 없으면 하드코딩 playbook 폴백."""
        graph_entries = self._load_graph_playbook(conn, cause_type)
        if graph_entries:
            return graph_entries
        hardcoded = self.recovery_playbook.get(cause_type, [])
        out = []
        for idx, e in enumerate(hardcoded):
            out.append({
                "id": f"HC-{cause_type}-{idx+1}",
                "action": e["action"],
                "param": e["param"],
                "adjustment": e["adjustment"],
                "risk": e["risk"],
                "source": "hardcoded",
            })
        return out

    def _load_graph_playbook(self, conn, cause_type: str) -> list:
        out = []
        # 1) 인과규칙과 연결된 playbook 우선
        try:
            r = conn.execute(
                "MATCH (cr:CausalRule)-[:TRIGGERS_ACTION]->(pb:ResponsePlaybook) "
                "WHERE (cr.cause_type=$cause OR cr.effect_type=$cause) AND pb.active=true "
                "RETURN pb.id, pb.action_type, pb.risk_level, pb.priority "
                "ORDER BY pb.priority ASC",
                {"cause": cause_type},
            )
            while r.has_next():
                row = r.get_next()
                action_type = row[1]
                defaults = ACTION_DEFAULTS.get(action_type, {"param": None, "adjustment": None})
                out.append({
                    "id": row[0],
                    "action": action_type,
                    "risk": row[2] or "MEDIUM",
                    "param": defaults["param"],
                    "adjustment": defaults["adjustment"],
                    "priority": int(row[3]) if row[3] is not None else 50,
                    "source": "graph_rule",
                })
        except Exception:
            pass
        if out:
            return out

        # 2) cause_type 직접 매칭 playbook 폴백
        try:
            r = conn.execute(
                "MATCH (pb:ResponsePlaybook) "
                "WHERE pb.cause_type=$cause AND pb.active=true "
                "RETURN pb.id, pb.action_type, pb.risk_level, pb.priority "
                "ORDER BY pb.priority ASC",
                {"cause": cause_type},
            )
            while r.has_next():
                row = r.get_next()
                action_type = row[1]
                defaults = ACTION_DEFAULTS.get(action_type, {"param": None, "adjustment": None})
                out.append({
                    "id": row[0],
                    "action": action_type,
                    "risk": row[2] or "MEDIUM",
                    "param": defaults["param"],
                    "adjustment": defaults["adjustment"],
                    "priority": int(row[3]) if row[3] is not None else 50,
                    "source": "graph_direct",
                })
        except Exception:
            pass
        return out

    def execute_recovery(self, conn, action: dict, counters: dict) -> dict:
        """복구 조치를 실행(시뮬레이션)한다.

        Args:
            conn: Kuzu connection object.
            action: recovery action dict from plan_recovery.
            counters: shared counter dict for ID generation.

        Returns:
            execution result dict.
        """
        AutoRecoveryAgent._recovery_counter += 1
        recovery_id = f"REC-{AutoRecoveryAgent._recovery_counter:04d}"
        action_type = action.get("action_type", "ESCALATE")
        step_id = action.get("target_step", "unknown")
        param = action.get("parameter")
        confidence = action.get("confidence", 0.0)

        try:
            # ── ADJUST_PARAMETER: 수율 보정 ──
            if action_type == "ADJUST_PARAMETER" and param == "yield_rate":
                adjustment = 0.005 if confidence >= 0.7 else 0.002
                r = conn.execute(
                    "MATCH (ps:ProcessStep) WHERE ps.id = $step_id "
                    "RETURN ps.yield_rate",
                    {"step_id": step_id},
                )
                if r.has_next():
                    current = float(r.get_next()[0])
                    new_val = min(current + adjustment, 0.999)
                    conn.execute(
                        "MATCH (ps:ProcessStep) WHERE ps.id = $step_id "
                        "SET ps.yield_rate = $val",
                        {"step_id": step_id, "val": new_val},
                    )
                    self._store_recovery_action(
                        conn, recovery_id, action_type, counters,
                        parameter=param, old_value=current, new_value=new_val, success=True,
                    )
                    return {
                        "success": True,
                        "action_type": action_type,
                        "step_id": step_id,
                        "detail": f"yield_rate {current:.4f} → {new_val:.4f} (+{adjustment})",
                        "recovery_id": recovery_id,
                    }

            # ── EQUIPMENT_RESET: OEE 보정 ──
            elif action_type == "EQUIPMENT_RESET":
                oee_boost = 0.02
                r = conn.execute(
                    "MATCH (ps:ProcessStep) WHERE ps.id = $step_id "
                    "RETURN ps.oee",
                    {"step_id": step_id},
                )
                if r.has_next():
                    current_oee = float(r.get_next()[0])
                    new_oee = min(current_oee + oee_boost, 0.999)
                    conn.execute(
                        "MATCH (ps:ProcessStep) WHERE ps.id = $step_id "
                        "SET ps.oee = $val",
                        {"step_id": step_id, "val": new_oee},
                    )
                    self._store_recovery_action(
                        conn, recovery_id, action_type, counters,
                        parameter="oee", old_value=current_oee, new_value=new_oee, success=True,
                    )
                    return {
                        "success": True,
                        "action_type": action_type,
                        "step_id": step_id,
                        "detail": f"OEE {current_oee:.4f} → {new_oee:.4f} (+{oee_boost})",
                        "recovery_id": recovery_id,
                    }

            # ── INCREASE_INSPECTION: 검사 관계 추가 ──
            elif action_type == "INCREASE_INSPECTION":
                # 가장 가까운 검사 공정을 찾아 연결
                added = self._add_inspection_link(conn, step_id)
                self._store_recovery_action(
                    conn, recovery_id, action_type, counters,
                    parameter=None, old_value=None, new_value=None, success=True,
                )
                return {
                    "success": True,
                    "action_type": action_type,
                    "step_id": step_id,
                    "detail": f"검사 연결 {'추가됨' if added else '이미 존재 — 확인 완료'}",
                    "recovery_id": recovery_id,
                }

            # ── MATERIAL_SWITCH: 자재 LOT 변경 플래그 ──
            elif action_type == "MATERIAL_SWITCH":
                self._store_recovery_action(
                    conn, recovery_id, action_type, counters,
                    parameter=None, old_value=None, new_value=None, success=True,
                )
                return {
                    "success": True,
                    "action_type": action_type,
                    "step_id": step_id,
                    "detail": "자재 LOT 변경 플래그 설정 — 공급망 담당자 알림 발송",
                    "recovery_id": recovery_id,
                }

            # ── ESCALATE: 사람에게 에스컬레이션 ──
            elif action_type == "ESCALATE":
                self._store_recovery_action(
                    conn, recovery_id, action_type, counters,
                    parameter=None, old_value=None, new_value=None, success=False,
                )
                return {
                    "success": False,
                    "action_type": action_type,
                    "step_id": step_id,
                    "detail": "자동 복구 불가 — 운영자 에스컬레이션 발행",
                    "recovery_id": recovery_id,
                    "escalated": True,
                }

            # ── Unknown action type ──
            return {
                "success": False,
                "action_type": action_type,
                "step_id": step_id,
                "detail": f"지원되지 않는 복구 유형: {action_type}",
                "recovery_id": recovery_id,
            }

        except Exception as e:
            return {
                "success": False,
                "action_type": action_type,
                "step_id": step_id,
                "detail": f"복구 실행 오류: {str(e)[:200]}",
                "recovery_id": recovery_id,
            }

    def verify_recovery(self, conn, step_id: str, pre_yield: float) -> dict:
        """복구 후 수율 변화를 검증한다.

        Args:
            conn: Kuzu connection object.
            step_id: 복구 대상 공정 ID.
            pre_yield: 복구 전 수율.

        Returns:
            verification result dict.
        """
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep) WHERE ps.id = $step_id "
                "RETURN ps.yield_rate",
                {"step_id": step_id},
            )
            if r.has_next():
                post_yield = float(r.get_next()[0])
                improvement = post_yield - pre_yield
                return {
                    "verified": improvement > 0,
                    "improved": improvement > 0,
                    "pre_yield": round(pre_yield, 6),
                    "post_yield": round(post_yield, 6),
                    "improvement": round(improvement, 6),
                    "step_id": step_id,
                }
        except Exception:
            pass

        return {
            "verified": False,
            "improved": False,
            "pre_yield": round(pre_yield, 6),
            "post_yield": round(pre_yield, 6),
            "improvement": 0.0,
            "step_id": step_id,
        }

    def learn(self, action_type: str, cause_type: str, success: bool):
        """복구 결과를 기록하여 미래 의사결정을 개선한다.

        Args:
            action_type: 실행한 복구 유형.
            cause_type: 원인 유형.
            success: 복구 성공 여부.
        """
        key = (action_type, cause_type)
        self.success_history[key]["attempts"] += 1
        if success:
            self.success_history[key]["successes"] += 1

    def mutate_playbook(self) -> dict:
        """Self-evolution: mutate playbook entries with < 50% success rate.

        For poorly performing (action_type, cause_type) pairs, try the NEXT
        action in the playbook list. Track which mutations improved outcomes.

        Returns:
            Summary of mutations applied.
        """
        mutations = []
        for (action_type, cause_type), hist in list(self.success_history.items()):
            attempts = hist["attempts"]
            successes = hist["successes"]
            if attempts < 3:
                continue  # not enough data
            success_rate = successes / attempts
            if success_rate >= 0.50:
                continue  # performing OK

            # Find current position in playbook for this cause_type
            playbook_entries = self.recovery_playbook.get(cause_type, [])
            if len(playbook_entries) < 2:
                continue  # no alternative to try

            current_idx = None
            for i, entry in enumerate(playbook_entries):
                if entry["action"] == action_type:
                    current_idx = i
                    break

            if current_idx is None:
                continue

            # Try the next action in the list (wrap around)
            next_idx = (current_idx + 1) % len(playbook_entries)
            next_entry = playbook_entries[next_idx]
            old_action = action_type
            new_action = next_entry["action"]

            if old_action == new_action:
                continue

            # Promote the next entry to the front by swapping
            playbook_entries[current_idx], playbook_entries[next_idx] = (
                playbook_entries[next_idx],
                playbook_entries[current_idx],
            )

            mutations.append({
                "cause_type": cause_type,
                "old_action": old_action,
                "new_action": new_action,
                "old_success_rate": round(success_rate, 3),
                "attempts": attempts,
            })

        return {
            "mutations_applied": len(mutations),
            "details": mutations[:10],
        }

    # ── Internal helpers ──

    def _get_current_value(self, conn, step_id: str, param: str):
        """현재 파라미터 값을 DB에서 조회한다."""
        if param is None:
            return None
        try:
            field_map = {"yield_rate": "ps.yield_rate", "oee": "ps.oee"}
            field = field_map.get(param)
            if field is None:
                return None
            r = conn.execute(
                f"MATCH (ps:ProcessStep) WHERE ps.id = $step_id RETURN {field}",
                {"step_id": step_id},
            )
            if r.has_next():
                val = r.get_next()[0]
                return float(val) if val is not None else None
        except Exception:
            pass
        return None

    @staticmethod
    def _compute_new_value(old_value, adjustment, param: str):
        """새 파라미터 값을 계산한다."""
        if old_value is None or adjustment is None or param is None:
            return None
        new_val = old_value + adjustment
        # 비율 파라미터는 0.999를 초과할 수 없음
        if param in ("yield_rate", "oee"):
            new_val = min(new_val, 0.999)
        return round(new_val, 6)

    def _add_inspection_link(self, conn, step_id: str) -> bool:
        """누락된 검사 연결을 추가한다."""
        try:
            # 이미 검사가 있는지 확인
            r = conn.execute(
                "MATCH (insp:ProcessStep)-[:INSPECTS]->(ps:ProcessStep) "
                "WHERE ps.id = $step_id RETURN count(insp)",
                {"step_id": step_id},
            )
            if r.has_next() and int(r.get_next()[0]) > 0:
                return False  # 이미 존재

            # 동일 area의 검사 공정 찾기
            r = conn.execute(
                "MATCH (ps:ProcessStep) WHERE ps.id = $step_id "
                "RETURN ps.area_id",
                {"step_id": step_id},
            )
            if not r.has_next():
                return False
            area_id = r.get_next()[0]

            # 같은 area에서 '검사' 키워드가 포함된 공정을 찾아 연결
            r = conn.execute(
                "MATCH (insp:ProcessStep) "
                "WHERE insp.area_id = $area_id AND insp.name CONTAINS '검사' "
                "AND insp.id <> $step_id "
                "RETURN insp.id LIMIT 1",
                {"area_id": area_id, "step_id": step_id},
            )
            if r.has_next():
                insp_id = r.get_next()[0]
                conn.execute(
                    "MATCH (a:ProcessStep), (b:ProcessStep) "
                    "WHERE a.id = $insp_id AND b.id = $step_id "
                    "CREATE (a)-[:INSPECTS]->(b)",
                    {"insp_id": insp_id, "step_id": step_id},
                )
                return True
        except Exception:
            pass
        return False

    def _store_recovery_action(
        self,
        conn,
        recovery_id: str,
        action_type: str,
        counters: dict,
        parameter=None,
        old_value=None,
        new_value=None,
        success: bool = True,
    ):
        """RecoveryAction 노드를 DB에 저장한다."""
        try:
            timestamp = datetime.now().isoformat()
            conn.execute(
                "CREATE (ra:RecoveryAction {"
                "  id: $rid, incident_id: '', action_type: $atype, "
                "  parameter: $param, old_value: $old, new_value: $new, "
                "  success: $ok, timestamp: $ts"
                "})",
                {
                    "rid": recovery_id,
                    "atype": action_type,
                    "param": parameter,
                    "old": old_value,
                    "new": new_value,
                    "ok": success,
                    "ts": timestamp,
                },
            )
            counters["recovery"] = counters.get("recovery", 0) + 1
        except Exception:
            # RecoveryAction 테이블이 아직 없을 수 있음 — 무시
            pass


class ResilienceOrchestrator:
    """장비 고장 시 대체 경로를 활성화한다.

    온톨로지의 PARALLEL_WITH 관계를 활용하여,
    한 경로가 실패하면 병렬 경로로 자동 전환한다.
    """

    def find_alternate_path(self, conn, failed_step_id):
        """실패한 공정의 대체 경로를 찾는다."""
        alternates = []
        # PARALLEL_WITH 관계로 연결된 공정
        try:
            r = conn.execute(
                "MATCH (a:ProcessStep)-[:PARALLEL_WITH]-(b:ProcessStep) "
                "WHERE a.id = $id RETURN b.id, b.name, b.yield_rate, b.oee",
                {"id": failed_step_id})
            while r.has_next():
                row = r.get_next()
                alternates.append({
                    "step_id": row[0], "name": row[1],
                    "yield_rate": float(row[2]) if row[2] else 0,
                    "oee": float(row[3]) if row[3] else 0,
                    "type": "parallel",
                })
        except Exception:
            pass

        # 같은 영역의 다른 공정 (유사 장비)
        try:
            r = conn.execute(
                "MATCH (a:ProcessStep) WHERE a.id = $id "
                "MATCH (b:ProcessStep) WHERE b.area_id = a.area_id AND b.id <> a.id AND b.yield_rate > 0.99 "
                "RETURN b.id, b.name, b.yield_rate, b.oee LIMIT 2",
                {"id": failed_step_id})
            while r.has_next():
                row = r.get_next()
                alternates.append({
                    "step_id": row[0], "name": row[1],
                    "yield_rate": float(row[2]) if row[2] else 0,
                    "oee": float(row[3]) if row[3] else 0,
                    "type": "same_area",
                })
        except Exception:
            pass

        alternates.sort(key=lambda x: -x["yield_rate"])
        return alternates

    def activate_alternate(self, conn, failed_step_id, alternate):
        """대체 경로를 활성화한다 (온톨로지에 우회 관계 추가)."""
        try:
            conn.execute(
                "MATCH (a:ProcessStep),(b:ProcessStep) WHERE a.id=$s AND b.id=$t "
                "AND NOT (a)-[:FEEDS_INTO]->(b) "
                "CREATE (a)-[:FEEDS_INTO]->(b)",
                {"s": failed_step_id, "t": alternate["step_id"]})
            return {"success": True, "alternate": alternate["step_id"], "type": alternate["type"]}
        except Exception:
            return {"success": False}
