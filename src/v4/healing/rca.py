"""온톨로지 경로 역추적 기반 RCA (Root Cause Analyzer).

이상이 감지된 공정에서 출발하여 장비/자재/결함모드/상류/검사 경로를 탐색한다.
과거 확인된 원인은 +confidence 보정.
"""
from collections import defaultdict
from datetime import datetime


class RootCauseAnalyzer:
    """온톨로지 경로 기반 원인 진단."""

    def __init__(self):
        self.cause_history = defaultdict(list)

    def analyze(self, conn, anomaly: dict) -> dict:
        """이상 → 후보 원인 리스트 (confidence 정렬)."""
        start_time = datetime.now()
        step_id = anomaly.get("step_id", "unknown")
        sensor_type = anomaly.get("sensor_type", "unknown")
        candidates = []
        paths_explored = 1

        if not self._query_step(conn, step_id):
            return {
                "step_id": step_id,
                "candidates": [],
                "analysis_time_ms": _elapsed_ms(start_time),
                "paths_explored": paths_explored,
            }

        for fn in (
            self._check_equipment_path,
            self._check_material_path,
            self._check_upstream_path,
            self._check_inspection_path,
        ):
            candidates.extend(fn(conn, step_id))
            paths_explored += 1

        candidates.extend(self._check_defect_path(conn, step_id, sensor_type))
        paths_explored += 1

        history_key = (step_id, sensor_type)
        if history_key in self.cause_history:
            candidates.extend(self._candidates_from_history(history_key, step_id))
            self._boost_history_match(candidates, history_key)
            paths_explored += 1

        candidates = _dedupe_keep_max_confidence(candidates)

        return {
            "step_id": step_id,
            "candidates": candidates,
            "analysis_time_ms": _elapsed_ms(start_time),
            "paths_explored": paths_explored,
        }

    def learn(self, step_id: str, sensor_type: str, confirmed_cause: str):
        """확인된 원인을 기록하여 미래 진단에 활용한다."""
        self.cause_history[(step_id, sensor_type)].append(confirmed_cause)

    # ── Path queries ────────────────────────────────────

    def _query_step(self, conn, step_id: str) -> dict:
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
                eq_id, eq_name = row[0], row[1]
                mtbf = float(row[2]) if row[2] is not None else 0.0
                cost = float(row[3]) if row[3] is not None else 0.0

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
                mat_id, mat_name = row[0], row[1]
                supplier = row[2] if row[2] is not None else "unknown"
                cost = float(row[3]) if row[3] is not None else 0.0
                category = row[4] if row[4] is not None else "unknown"

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
                dm_id, dm_name = row[0], row[1]
                dm_cat = row[2] if row[2] is not None else ""
                dm_sev = int(row[3]) if row[3] is not None else 5
                dm_occ = int(row[4]) if row[4] is not None else 5
                dm_det = int(row[5]) if row[5] is not None else 5
                rpn = dm_sev * dm_occ * dm_det

                type_match = _sensor_defect_match(sensor_type, dm_cat)
                base_confidence = 0.80 if type_match else 0.55
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
                prev_id, prev_name = row[0], row[1]
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

    def _candidates_from_history(self, history_key: tuple, step_id: str) -> list:
        cause_counts = defaultdict(int)
        for c in self.cause_history[history_key]:
            cause_counts[c] += 1
        return [
            {
                "cause_type": cause_type,
                "cause_id": f"HIST-{step_id}",
                "cause_name": f"과거 확인 원인: {cause_type}",
                "confidence": min(0.95, 0.90 + count * 0.01),
                "evidence": f"과거 {count}회 동일 원인 확인됨",
                "suggested_action": f"이전 복구 조치 재적용 ({cause_type})",
            }
            for cause_type, count in cause_counts.items()
        ]

    def _boost_history_match(self, candidates: list, history_key: tuple) -> None:
        """과거에 확인된 cause_type과 일치하는 후보 confidence 가중."""
        confirmed_types = set(self.cause_history[history_key])
        for c in candidates:
            if c["cause_type"] in confirmed_types and "HIST" not in c.get("cause_id", ""):
                c["confidence"] = min(0.95, c["confidence"] + 0.05)


def _dedupe_keep_max_confidence(candidates: list) -> list:
    seen = {}
    for c in candidates:
        cid = c["cause_id"]
        if cid not in seen or c["confidence"] > seen[cid]["confidence"]:
            seen[cid] = c
    return sorted(seen.values(), key=lambda x: -x["confidence"])


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
    return defect_category in mapping.get(sensor_type, ())


def _elapsed_ms(start_time: datetime) -> float:
    return round((datetime.now() - start_time).total_seconds() * 1000, 1)
