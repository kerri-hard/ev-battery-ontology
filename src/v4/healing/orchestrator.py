"""ResilienceOrchestrator — 장비 고장 시 PARALLEL_WITH 대체 경로 활성화."""


class ResilienceOrchestrator:
    """대체 경로 탐색/활성화."""

    def find_alternate_path(self, conn, failed_step_id):
        """실패한 공정의 대체 경로 후보 (병렬 + 동일 area 고yield)."""
        alternates = []
        alternates.extend(self._find_parallel(conn, failed_step_id))
        alternates.extend(self._find_same_area_high_yield(conn, failed_step_id))
        alternates.sort(key=lambda x: -x["yield_rate"])
        return alternates

    def activate_alternate(self, conn, failed_step_id, alternate):
        """대체 경로를 활성화한다 (FEEDS_INTO 우회 관계 추가)."""
        try:
            conn.execute(
                "MATCH (a:ProcessStep),(b:ProcessStep) WHERE a.id=$s AND b.id=$t "
                "AND NOT (a)-[:FEEDS_INTO]->(b) "
                "CREATE (a)-[:FEEDS_INTO]->(b)",
                {"s": failed_step_id, "t": alternate["step_id"]},
            )
            return {"success": True, "alternate": alternate["step_id"], "type": alternate["type"]}
        except Exception:
            return {"success": False}

    @staticmethod
    def _find_parallel(conn, failed_step_id):
        out = []
        try:
            r = conn.execute(
                "MATCH (a:ProcessStep)-[:PARALLEL_WITH]-(b:ProcessStep) "
                "WHERE a.id = $id RETURN b.id, b.name, b.yield_rate, b.oee",
                {"id": failed_step_id},
            )
            while r.has_next():
                row = r.get_next()
                out.append({
                    "step_id": row[0], "name": row[1],
                    "yield_rate": float(row[2]) if row[2] else 0,
                    "oee": float(row[3]) if row[3] else 0,
                    "type": "parallel",
                })
        except Exception:
            pass
        return out

    @staticmethod
    def _find_same_area_high_yield(conn, failed_step_id):
        out = []
        try:
            r = conn.execute(
                "MATCH (a:ProcessStep) WHERE a.id = $id "
                "MATCH (b:ProcessStep) WHERE b.area_id = a.area_id AND b.id <> a.id AND b.yield_rate > 0.99 "
                "RETURN b.id, b.name, b.yield_rate, b.oee LIMIT 2",
                {"id": failed_step_id},
            )
            while r.has_next():
                row = r.get_next()
                out.append({
                    "step_id": row[0], "name": row[1],
                    "yield_rate": float(row[2]) if row[2] else 0,
                    "oee": float(row[3]) if row[3] else 0,
                    "type": "same_area",
                })
        except Exception:
            pass
        return out
