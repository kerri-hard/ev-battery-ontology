"""
Battery Traceability Layer (L5) — 배터리 추적성 계층
====================================================
업계 사례:
  - Tesla: 모든 셀에 고유 ID → 현장 불량 시 제조 시점까지 역추적
  - Samsung SDI: 셀 단위 추적성 (셀 → 모듈 → 팩)
  - CATL: 극편 결함 실시간 감지 + 배치별 추적
  - LG Energy ATLAAS: 배터리 전주기 데이터 분석

규제 배경:
  - EU Battery Regulation (2027 시행): 배터리 여권(Battery Passport) 의무화
  - 탄소 발자국, 재활용 원자재 비율, 공급망 실사 추적
  - 셀 → 모듈 → 팩 전 단계 디지털 추적 필수

온톨로지 확장:
  새 노드: ProductionBatch, LotTrace, BatteryPassport
  새 관계: PRODUCED_IN, USES_LOT, TRACED_TO, HAS_PASSPORT, BATCH_INCIDENT
"""
from __future__ import annotations

import random
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
#  L5 TRACEABILITY SCHEMA EXTENSION
# ═══════════════════════════════════════════════════════════════

def extend_schema_traceability(conn):
    """온톨로지에 L5(추적성) 계층을 추가한다."""
    node_tables = [
        # 생산 배치: 특정 공정에서 특정 시간에 생산된 단위
        ("CREATE NODE TABLE ProductionBatch ("
         "id STRING, step_id STRING, batch_size INT64, "
         "start_time STRING, end_time STRING, "
         "yield_rate DOUBLE, defect_count INT64 DEFAULT 0, "
         "energy_kwh DOUBLE DEFAULT 0.0, "
         "status STRING DEFAULT 'completed', "
         "PRIMARY KEY(id))"),

        # 로트 추적: 자재 로트와 생산 배치의 연결
        ("CREATE NODE TABLE LotTrace ("
         "id STRING, material_id STRING, lot_number STRING, "
         "supplier STRING, received_date STRING, "
         "quantity DOUBLE, unit STRING, "
         "inspection_result STRING DEFAULT 'PASS', "
         "certificate_id STRING, "
         "PRIMARY KEY(id))"),

        # 배터리 여권: EU Battery Regulation 대응
        ("CREATE NODE TABLE BatteryPassport ("
         "id STRING, pack_id STRING, "
         "cell_count INT64, module_count INT64, "
         "total_energy_kwh DOUBLE, "
         "carbon_footprint_kg DOUBLE, "
         "recycled_content_pct DOUBLE, "
         "manufacturing_date STRING, "
         "manufacturing_plant STRING, "
         "certification STRING, "
         "PRIMARY KEY(id))"),
    ]

    rel_tables = [
        # 공정 → 배치: 어떤 공정에서 생산되었는지
        "CREATE REL TABLE PRODUCED_IN (FROM ProductionBatch TO ProcessStep)",
        # 배치 → 자재 로트: 어떤 자재 로트를 사용했는지
        "CREATE REL TABLE USES_LOT (FROM ProductionBatch TO LotTrace, qty DOUBLE)",
        # 배치 → 배치: 셀 배치 → 모듈 배치 → 팩 배치 추적
        "CREATE REL TABLE TRACED_TO (FROM ProductionBatch TO ProductionBatch, trace_type STRING)",
        # 팩 → 배터리 여권
        "CREATE REL TABLE HAS_PASSPORT (FROM ProductionBatch TO BatteryPassport)",
        # 배치 → 인시던트: 배치별 품질 이슈 추적
        "CREATE REL TABLE BATCH_INCIDENT (FROM ProductionBatch TO Incident)",
    ]

    for ddl in node_tables + rel_tables:
        try:
            conn.execute(ddl)
        except Exception:
            pass  # 이미 존재하면 무시


# ═══════════════════════════════════════════════════════════════
#  TRACEABILITY MANAGER
# ═══════════════════════════════════════════════════════════════

class TraceabilityManager:
    """배터리 생산 추적성을 관리한다.

    업계 참조:
      - Tesla: 셀별 고유 ID + QR 코드 → 전 공정 역추적
      - Samsung SDI: MES 연동 실시간 배치 추적
    """

    def __init__(self):
        self.batch_counter = 0
        self.lot_counter = 0
        self.passport_counter = 0

    def create_batch(self, conn, step_id: str, batch_size: int = 96,
                     energy_kwh: float = 0.0) -> dict:
        """생산 배치를 생성하고 온톨로지에 기록한다."""
        self.batch_counter += 1
        batch_id = f"BATCH-{self.batch_counter:06d}"
        now = datetime.now().isoformat()

        try:
            conn.execute(
                "CREATE (b:ProductionBatch {"
                "id:$id, step_id:$sid, batch_size:$bs, "
                "start_time:$st, end_time:$et, "
                "yield_rate:1.0, defect_count:0, "
                "energy_kwh:$energy, status:'in_progress'"
                "})",
                {"id": batch_id, "sid": step_id, "bs": batch_size,
                 "st": now, "et": "", "energy": energy_kwh},
            )
            # 공정과 연결
            conn.execute(
                "MATCH (b:ProductionBatch), (ps:ProcessStep) "
                "WHERE b.id=$bid AND ps.id=$sid "
                "CREATE (b)-[:PRODUCED_IN]->(ps)",
                {"bid": batch_id, "sid": step_id},
            )
        except Exception:
            pass

        return {"batch_id": batch_id, "step_id": step_id, "status": "in_progress"}

    def complete_batch(self, conn, batch_id: str, yield_rate: float,
                       defect_count: int = 0, energy_kwh: float = 0.0) -> dict:
        """배치를 완료하고 결과를 기록한다."""
        now = datetime.now().isoformat()
        try:
            conn.execute(
                "MATCH (b:ProductionBatch) WHERE b.id=$id "
                "SET b.end_time=$et, b.yield_rate=$yr, "
                "b.defect_count=$dc, b.energy_kwh=$energy, "
                "b.status='completed'",
                {"id": batch_id, "et": now, "yr": yield_rate,
                 "dc": defect_count, "energy": energy_kwh},
            )
        except Exception:
            pass
        return {"batch_id": batch_id, "status": "completed", "yield_rate": yield_rate}

    def register_lot(self, conn, material_id: str, lot_number: str,
                     supplier: str, quantity: float, unit: str = "ea") -> dict:
        """자재 로트를 등록한다."""
        self.lot_counter += 1
        lot_id = f"LOT-{self.lot_counter:06d}"
        now = datetime.now().isoformat()

        try:
            conn.execute(
                "CREATE (l:LotTrace {"
                "id:$id, material_id:$mid, lot_number:$ln, "
                "supplier:$sup, received_date:$rd, "
                "quantity:$qty, unit:$unit, "
                "inspection_result:'PASS', certificate_id:''"
                "})",
                {"id": lot_id, "mid": material_id, "ln": lot_number,
                 "sup": supplier, "rd": now, "qty": quantity, "unit": unit},
            )
        except Exception:
            pass
        return {"lot_id": lot_id, "material_id": material_id, "lot_number": lot_number}

    def link_batch_to_lot(self, conn, batch_id: str, lot_id: str,
                          qty: float) -> bool:
        """배치와 자재 로트를 연결한다."""
        try:
            conn.execute(
                "MATCH (b:ProductionBatch), (l:LotTrace) "
                "WHERE b.id=$bid AND l.id=$lid "
                "CREATE (b)-[:USES_LOT {qty:$qty}]->(l)",
                {"bid": batch_id, "lid": lot_id, "qty": qty},
            )
            return True
        except Exception:
            return False

    def trace_batch_to_batch(self, conn, from_batch: str, to_batch: str,
                             trace_type: str = "cell_to_module") -> bool:
        """배치 간 추적 관계를 생성한다 (셀→모듈→팩)."""
        try:
            conn.execute(
                "MATCH (a:ProductionBatch), (b:ProductionBatch) "
                "WHERE a.id=$fid AND b.id=$tid "
                "CREATE (a)-[:TRACED_TO {trace_type:$tt}]->(b)",
                {"fid": from_batch, "tid": to_batch, "tt": trace_type},
            )
            return True
        except Exception:
            return False

    def create_battery_passport(self, conn, pack_batch_id: str,
                                cell_count: int = 96, module_count: int = 8,
                                total_energy_kwh: float = 72.0,
                                carbon_footprint_kg: float = 0.0,
                                recycled_content_pct: float = 0.0) -> dict:
        """EU Battery Passport를 생성한다."""
        self.passport_counter += 1
        passport_id = f"BP-{self.passport_counter:06d}"
        now = datetime.now().isoformat()

        try:
            conn.execute(
                "CREATE (bp:BatteryPassport {"
                "id:$id, pack_id:$pid, "
                "cell_count:$cc, module_count:$mc, "
                "total_energy_kwh:$energy, "
                "carbon_footprint_kg:$cf, "
                "recycled_content_pct:$rc, "
                "manufacturing_date:$md, "
                "manufacturing_plant:'EV-FACTORY-01', "
                "certification:'EU-BR-2027'"
                "})",
                {"id": passport_id, "pid": pack_batch_id,
                 "cc": cell_count, "mc": module_count,
                 "energy": total_energy_kwh, "cf": carbon_footprint_kg,
                 "rc": recycled_content_pct, "md": now},
            )
            # 팩 배치와 연결
            conn.execute(
                "MATCH (b:ProductionBatch), (bp:BatteryPassport) "
                "WHERE b.id=$bid AND bp.id=$bpid "
                "CREATE (b)-[:HAS_PASSPORT]->(bp)",
                {"bid": pack_batch_id, "bpid": passport_id},
            )
        except Exception:
            pass

        return {"passport_id": passport_id, "pack_batch_id": pack_batch_id}

    def trace_incident_to_batch(self, conn, batch_id: str,
                                incident_id: str) -> bool:
        """인시던트를 배치에 연결한다 (품질 이슈 추적)."""
        try:
            conn.execute(
                "MATCH (b:ProductionBatch), (inc:Incident) "
                "WHERE b.id=$bid AND inc.id=$iid "
                "CREATE (b)-[:BATCH_INCIDENT]->(inc)",
                {"bid": batch_id, "iid": incident_id},
            )
            return True
        except Exception:
            return False

    def reverse_trace(self, conn, batch_id: str) -> dict:
        """배치에서 역추적하여 사용된 자재 로트와 상위 배치를 찾는다.

        Tesla 방식: 불량 팩 → 모듈 배치 → 셀 배치 → 자재 로트 → 공급업체
        """
        result = {"batch_id": batch_id, "lots": [], "parent_batches": [],
                  "incidents": []}

        # 사용된 자재 로트
        try:
            r = conn.execute(
                "MATCH (b:ProductionBatch)-[:USES_LOT]->(l:LotTrace) "
                "WHERE b.id=$bid RETURN l.id, l.material_id, l.lot_number, "
                "l.supplier, l.inspection_result",
                {"bid": batch_id},
            )
            while r.has_next():
                row = r.get_next()
                result["lots"].append({
                    "lot_id": row[0], "material_id": row[1],
                    "lot_number": row[2], "supplier": row[3],
                    "inspection": row[4],
                })
        except Exception:
            pass

        # 상위 배치 (셀→모듈→팩 역추적)
        try:
            r = conn.execute(
                "MATCH (parent:ProductionBatch)-[:TRACED_TO]->(b:ProductionBatch) "
                "WHERE b.id=$bid RETURN parent.id, parent.step_id, parent.yield_rate",
                {"bid": batch_id},
            )
            while r.has_next():
                row = r.get_next()
                result["parent_batches"].append({
                    "batch_id": row[0], "step_id": row[1],
                    "yield_rate": float(row[2]) if row[2] else 0,
                })
        except Exception:
            pass

        # 관련 인시던트
        try:
            r = conn.execute(
                "MATCH (b:ProductionBatch)-[:BATCH_INCIDENT]->(inc:Incident) "
                "WHERE b.id=$bid RETURN inc.id, inc.root_cause, inc.auto_recovered",
                {"bid": batch_id},
            )
            while r.has_next():
                row = r.get_next()
                result["incidents"].append({
                    "incident_id": row[0], "root_cause": row[1],
                    "auto_recovered": bool(row[2]),
                })
        except Exception:
            pass

        return result

    def get_batch_stats(self, conn) -> dict:
        """전체 배치 통계를 반환한다."""
        stats = {"total_batches": 0, "total_lots": 0, "total_passports": 0,
                 "avg_yield": 0.0, "total_defects": 0}
        try:
            r = conn.execute("MATCH (b:ProductionBatch) RETURN count(b), avg(b.yield_rate), sum(b.defect_count)")
            if r.has_next():
                row = r.get_next()
                stats["total_batches"] = int(row[0] or 0)
                stats["avg_yield"] = round(float(row[1] or 0), 4)
                stats["total_defects"] = int(row[2] or 0)
        except Exception:
            pass
        try:
            r = conn.execute("MATCH (l:LotTrace) RETURN count(l)")
            if r.has_next():
                stats["total_lots"] = int(r.get_next()[0] or 0)
        except Exception:
            pass
        try:
            r = conn.execute("MATCH (bp:BatteryPassport) RETURN count(bp)")
            if r.has_next():
                stats["total_passports"] = int(r.get_next()[0] or 0)
        except Exception:
            pass
        return stats
