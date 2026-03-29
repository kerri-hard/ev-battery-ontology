"""
Correlation Analysis — 공정 간 상관분석 기반 장애 원인 추적
============================================================
단일 센서의 이상만 보는 것이 아니라, 공정 간 센서 값의
상관관계를 분석하여 "왜 이 장애가 발생했는지"를 추적한다.

학술 근거:
  - Multi-level RCA for Manufacturing (2025): 다변량 시계열 상관 분석
  - Causal AI for Manufacturing (Databricks, 2025): Granger causality

에이전트:
  - CorrelationAnalyzer: 센서 간 피어슨/시차 상관계수 계산
  - CrossProcessInvestigator: 상관관계 + 온톨로지 경로로 근본 원인 추적
"""
import math
from collections import defaultdict
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
#  SCHEMA EXTENSION
# ═══════════════════════════════════════════════════════════════

def extend_schema_correlation(conn):
    """상관관계 분석을 위한 스키마를 추가한다."""
    tables = [
        ("CREATE NODE TABLE Correlation ("
         "id STRING, source_step STRING, target_step STRING, "
         "source_sensor STRING, target_sensor STRING, "
         "coefficient DOUBLE, lag_seconds INT64 DEFAULT 0, "
         "direction STRING, discovery_time STRING, "
         "sample_count INT64 DEFAULT 0, "
         "PRIMARY KEY(id))"),
    ]
    rels = [
        "CREATE REL TABLE CORRELATES_WITH (FROM ProcessStep TO ProcessStep, "
        "coefficient DOUBLE DEFAULT 0.0, sensor_pair STRING DEFAULT '')",
    ]
    for ddl in tables + rels:
        try:
            conn.execute(ddl)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  CorrelationAnalyzer — 센서 간 상관계수 계산
# ═══════════════════════════════════════════════════════════════

class CorrelationAnalyzer:
    """센서 시계열 데이터의 상관관계를 분석한다.

    - Pearson 상관계수로 선형 관계 측정
    - 시차(lag) 상관으로 선행/후행 관계 감지
    - 공정 간 상관이 높으면 온톨로지에 CORRELATES_WITH 관계 추가
    """

    def __init__(self, min_samples=10, correlation_threshold=0.6):
        # step_id:sensor_type → list of (timestamp, value)
        self.series = defaultdict(list)
        self.max_history = 100
        self.min_samples = min_samples
        self.threshold = correlation_threshold
        self.known_correlations = {}  # (src_key, tgt_key) → coefficient
        self._counter = 0

    def ingest(self, readings: list):
        """센서 읽기값을 시계열 버퍼에 축적한다."""
        for r in readings:
            step_id = r.get("step_id", "")
            sensor_type = r.get("sensor_type", "")
            value = r.get("value")
            if not step_id or not sensor_type or value is None:
                continue
            key = f"{step_id}:{sensor_type}"
            buf = self.series[key]
            buf.append(float(value))
            if len(buf) > self.max_history:
                self.series[key] = buf[-self.max_history:]

    def analyze_all(self) -> list:
        """모든 센서 쌍의 상관계수를 계산하고, 유의미한 상관관계를 반환한다."""
        keys = [k for k, v in self.series.items() if len(v) >= self.min_samples]
        results = []

        for i, key_a in enumerate(keys):
            for key_b in keys[i + 1:]:
                step_a, sensor_a = key_a.split(":", 1)
                step_b, sensor_b = key_b.split(":", 1)

                # 같은 공정 내 상관은 스킵 (관심 대상은 공정 간 상관)
                if step_a == step_b:
                    continue

                series_a = self.series[key_a]
                series_b = self.series[key_b]
                n = min(len(series_a), len(series_b))
                if n < self.min_samples:
                    continue

                a = series_a[-n:]
                b = series_b[-n:]

                # Pearson 상관계수
                coeff = self._pearson(a, b)
                if abs(coeff) < self.threshold:
                    continue

                # 시차(lag) 상관 — 1단계 시차
                lag_coeff = 0.0
                if n > self.min_samples + 1:
                    lag_coeff = self._pearson(a[:-1], b[1:])

                direction = "동시"
                if abs(lag_coeff) > abs(coeff) + 0.05:
                    direction = f"{step_a}→{step_b}" if lag_coeff > 0 else f"{step_b}→{step_a}"

                pair_key = (key_a, key_b)
                old = self.known_correlations.get(pair_key, 0)

                self._counter += 1
                result = {
                    "id": f"CORR-{self._counter:04d}",
                    "source_step": step_a,
                    "target_step": step_b,
                    "source_sensor": sensor_a,
                    "target_sensor": sensor_b,
                    "coefficient": round(coeff, 4),
                    "lag_coefficient": round(lag_coeff, 4),
                    "direction": direction,
                    "sample_count": n,
                    "is_new": pair_key not in self.known_correlations,
                    "strength_change": round(abs(coeff) - abs(old), 4) if old else 0,
                }
                self.known_correlations[pair_key] = coeff
                results.append(result)

        results.sort(key=lambda x: -abs(x["coefficient"]))
        return results

    def get_correlations_for_step(self, step_id: str) -> list:
        """특정 공정과 상관관계가 높은 다른 공정을 반환한다."""
        results = []
        for (key_a, key_b), coeff in self.known_correlations.items():
            step_a = key_a.split(":")[0]
            step_b = key_b.split(":")[0]
            if step_a == step_id or step_b == step_id:
                other = step_b if step_a == step_id else step_a
                results.append({
                    "other_step": other,
                    "coefficient": round(coeff, 4),
                    "sensor_pair": f"{key_a} ↔ {key_b}",
                })
        results.sort(key=lambda x: -abs(x["coefficient"]))
        return results

    @staticmethod
    def _pearson(x: list, y: list) -> float:
        """피어슨 상관계수를 계산한다."""
        n = len(x)
        if n < 3:
            return 0.0
        mx = sum(x) / n
        my = sum(y) / n
        sx = math.sqrt(sum((xi - mx) ** 2 for xi in x) / n)
        sy = math.sqrt(sum((yi - my) ** 2 for yi in y) / n)
        if sx == 0 or sy == 0:
            return 0.0
        cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / n
        return cov / (sx * sy)


# ═══════════════════════════════════════════════════════════════
#  CrossProcessInvestigator — 상관관계 + 온톨로지로 원인 추적
# ═══════════════════════════════════════════════════════════════

class CrossProcessInvestigator:
    """장애 발생 시 상관관계를 바탕으로 다른 공정의 영향을 추적한다.

    단일 공정 분석만으로는 "왜?"를 알 수 없는 경우:
    1. 상관관계 분석으로 관련 공정을 찾고
    2. 온톨로지 경로(FEEDS_INTO, DEPENDS_ON 등)로 인과 경로를 확인하고
    3. 두 근거가 일치하면 높은 확신도로 교차 원인을 보고한다.
    """

    def investigate(self, conn, anomaly: dict, correlation_analyzer: CorrelationAnalyzer) -> dict:
        """장애가 발생한 공정의 교차 원인을 분석한다."""
        step_id = anomaly.get("step_id", "")
        sensor_type = anomaly.get("sensor_type", "")

        # 1. 상관관계 기반: 이 공정과 높은 상관인 다른 공정
        correlated = correlation_analyzer.get_correlations_for_step(step_id)

        # 2. 온톨로지 경로 기반: 이 공정에 영향을 주는 상류 공정
        upstream = self._get_upstream_steps(conn, step_id)
        downstream = self._get_downstream_steps(conn, step_id)

        # 3. 교차 검증: 상관관계 + 온톨로지 경로가 모두 지목하는 공정
        cross_causes = []
        upstream_ids = {s["id"] for s in upstream}
        downstream_ids = {s["id"] for s in downstream}

        for c in correlated:
            other = c["other_step"]
            coeff = c["coefficient"]

            in_upstream = other in upstream_ids
            in_downstream = other in downstream_ids
            ontology_connected = in_upstream or in_downstream

            # 상관관계 + 온톨로지 연결 → 높은 확신
            if ontology_connected:
                confidence = min(0.95, abs(coeff) * 0.7 + 0.3)
                relationship = "상류 공정" if in_upstream else "하류 공정"
            else:
                # 상관은 있지만 온톨로지에 경로 없음 → 숨겨진 의존성 발견
                confidence = min(0.75, abs(coeff) * 0.5)
                relationship = "숨겨진 연관"

            # 다른 공정의 현재 상태 조회
            other_info = self._query_step(conn, other)

            cross_causes.append({
                "step_id": other,
                "step_name": other_info.get("name", other),
                "relationship": relationship,
                "correlation": round(coeff, 4),
                "confidence": round(confidence, 3),
                "sensor_pair": c["sensor_pair"],
                "other_yield": other_info.get("yield_rate", 0),
                "other_oee": other_info.get("oee", 0),
                "evidence": self._build_evidence(
                    step_id, other, relationship, coeff, other_info
                ),
                "recommended_action": self._suggest_action(
                    relationship, coeff, other_info
                ),
            })

        cross_causes.sort(key=lambda x: -x["confidence"])

        # 숨겨진 의존성이 발견되면 온톨로지에 기록
        hidden = [c for c in cross_causes if c["relationship"] == "숨겨진 연관" and c["confidence"] > 0.5]

        return {
            "step_id": step_id,
            "sensor_type": sensor_type,
            "cross_causes": cross_causes[:5],
            "total_correlated": len(correlated),
            "ontology_confirmed": sum(1 for c in cross_causes if c["relationship"] != "숨겨진 연관"),
            "hidden_dependencies": len(hidden),
            "hidden_dependency_details": hidden[:3],
        }

    def store_discovered_correlations(self, conn, correlations: list, counters: dict):
        """발견된 상관관계를 온톨로지에 CORRELATES_WITH로 저장한다."""
        stored = 0
        for c in correlations:
            if abs(c["coefficient"]) < 0.4:
                continue
            src = c["source_step"]
            tgt = c["target_step"]
            pair = f"{c['source_sensor']}↔{c['target_sensor']}"
            try:
                # 이미 존재하는지 확인
                r = conn.execute(
                    "MATCH (a:ProcessStep)-[r:CORRELATES_WITH]->(b:ProcessStep) "
                    "WHERE a.id=$s AND b.id=$t RETURN count(r)",
                    {"s": src, "t": tgt})
                if r.get_next()[0] == 0:
                    conn.execute(
                        "MATCH (a:ProcessStep),(b:ProcessStep) WHERE a.id=$s AND b.id=$t "
                        "CREATE (a)-[:CORRELATES_WITH {coefficient:$c, sensor_pair:$p}]->(b)",
                        {"s": src, "t": tgt, "c": c["coefficient"], "p": pair})
                    stored += 1
            except Exception:
                pass
        return stored

    # ── Internal ──

    def _get_upstream_steps(self, conn, step_id: str) -> list:
        """이 공정에 영향을 주는 상류 공정을 온톨로지에서 찾는다."""
        results = []
        for rel in ["NEXT_STEP", "FEEDS_INTO"]:
            try:
                r = conn.execute(
                    f"MATCH (prev:ProcessStep)-[:{rel}]->(ps:ProcessStep) "
                    f"WHERE ps.id=$id RETURN prev.id, prev.name, prev.yield_rate, prev.oee",
                    {"id": step_id})
                while r.has_next():
                    row = r.get_next()
                    results.append({
                        "id": row[0], "name": row[1],
                        "yield_rate": float(row[2]) if row[2] else 0,
                        "oee": float(row[3]) if row[3] else 0,
                    })
            except Exception:
                pass
        return results

    def _get_downstream_steps(self, conn, step_id: str) -> list:
        results = []
        for rel in ["NEXT_STEP", "FEEDS_INTO"]:
            try:
                r = conn.execute(
                    f"MATCH (ps:ProcessStep)-[:{rel}]->(nxt:ProcessStep) "
                    f"WHERE ps.id=$id RETURN nxt.id, nxt.name, nxt.yield_rate, nxt.oee",
                    {"id": step_id})
                while r.has_next():
                    row = r.get_next()
                    results.append({
                        "id": row[0], "name": row[1],
                        "yield_rate": float(row[2]) if row[2] else 0,
                        "oee": float(row[3]) if row[3] else 0,
                    })
            except Exception:
                pass
        return results

    def _query_step(self, conn, step_id: str) -> dict:
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep) WHERE ps.id=$id "
                "RETURN ps.name, ps.yield_rate, ps.oee, ps.automation",
                {"id": step_id})
            if r.has_next():
                row = r.get_next()
                return {
                    "name": row[0],
                    "yield_rate": float(row[1]) if row[1] else 0,
                    "oee": float(row[2]) if row[2] else 0,
                    "automation": row[3],
                }
        except Exception:
            pass
        return {}

    @staticmethod
    def _build_evidence(step_id, other, relationship, coeff, other_info) -> str:
        direction = "양의" if coeff > 0 else "음의"
        strength = "강한" if abs(coeff) > 0.8 else "보통" if abs(coeff) > 0.6 else "약한"
        yield_str = f"수율 {other_info.get('yield_rate', 0) * 100:.1f}%" if other_info else ""
        return (
            f"{other}({other_info.get('name', '')})과 {strength} {direction} 상관 "
            f"(r={coeff:.3f}), {relationship}, {yield_str}"
        )

    @staticmethod
    def _suggest_action(relationship, coeff, other_info) -> str:
        if relationship == "상류 공정":
            if other_info.get("yield_rate", 1) < 0.99:
                return f"상류 공정({other_info.get('name', '')}) 수율 개선 우선 — 현재 공정에 전파되고 있음"
            return "상류 공정 안정성 모니터링 강화"
        elif relationship == "하류 공정":
            return "현재 공정 품질 관리 강화 — 하류 공정에 영향 전파 중"
        else:
            return f"숨겨진 의존성 발견 — 온톨로지에 CORRELATES_WITH 관계 추가 검토"
