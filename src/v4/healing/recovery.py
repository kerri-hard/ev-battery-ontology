"""AutoRecoveryAgent — 진단 결과 기반 자동 복구.

L4 ResponsePlaybook 그래프 노드를 우선 사용, 없으면 하드코딩 RECOVERY_PLAYBOOK 폴백.
"""
from collections import defaultdict
from datetime import datetime

from v4.healing.playbook import RECOVERY_PLAYBOOK, ACTION_DEFAULTS, RISK_NUMERIC


_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class AutoRecoveryAgent:
    """진단 결과로부터 복구 액션을 계획/실행/검증/학습한다."""

    _recovery_counter = 0

    def __init__(self):
        self.recovery_playbook = dict(RECOVERY_PLAYBOOK)
        self.success_history = defaultdict(lambda: {"attempts": 0, "successes": 0})

    # ── PLAN ────────────────────────────────────────────

    def plan_recovery(self, conn, diagnosis: dict, anomaly: dict) -> list:
        """후보 원인 상위 3개에 대해 복구 액션을 생성하고 risk/confidence 정렬."""
        actions = []
        candidates = diagnosis.get("candidates", [])
        step_id = diagnosis.get("step_id", anomaly.get("step_id", "unknown"))

        for candidate in candidates[:3]:
            cause_type = candidate.get("cause_type", "unknown")
            cause_confidence = candidate.get("confidence", 0.0)
            playbook_entries = self._resolve_playbook_entries(conn, cause_type)
            if not playbook_entries:
                playbook_entries = self._resolve_playbook_entries(conn, "unknown")

            for entry in playbook_entries:
                actions.append(self._build_action(
                    conn, step_id, entry, cause_type, cause_confidence, candidate,
                ))

        actions.sort(key=lambda a: (
            _RISK_ORDER.get(a["risk_level"], 2),
            -a["confidence"],
        ))
        return actions

    def _build_action(self, conn, step_id, entry, cause_type, cause_confidence, candidate):
        action_type = entry["action"]
        param = entry["param"]
        adjustment = entry["adjustment"]
        risk_str = entry["risk"]

        history_key = (action_type, cause_type)
        hist = self.success_history[history_key]
        if hist["attempts"] > 0:
            success_rate = hist["successes"] / hist["attempts"]
            adjusted_confidence = cause_confidence * (0.7 + 0.3 * success_rate)
        else:
            adjusted_confidence = cause_confidence

        old_value = self._get_current_value(conn, step_id, param)
        new_value = self._compute_new_value(old_value, adjustment, param)

        return {
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
        }

    def _resolve_playbook_entries(self, conn, cause_type: str) -> list:
        """L4 그래프 playbook 우선, 없으면 하드코딩 폴백."""
        graph_entries = self._load_graph_playbook(conn, cause_type)
        if graph_entries:
            return graph_entries
        hardcoded = self.recovery_playbook.get(cause_type, [])
        return [
            {
                "id": f"HC-{cause_type}-{idx + 1}",
                "action": e["action"],
                "param": e["param"],
                "adjustment": e["adjustment"],
                "risk": e["risk"],
                "source": "hardcoded",
            }
            for idx, e in enumerate(hardcoded)
        ]

    def _load_graph_playbook(self, conn, cause_type: str) -> list:
        out = self._query_graph_playbook(
            conn,
            "MATCH (cr:CausalRule)-[:TRIGGERS_ACTION]->(pb:ResponsePlaybook) "
            "WHERE (cr.cause_type=$cause OR cr.effect_type=$cause) AND pb.active=true "
            "RETURN pb.id, pb.action_type, pb.risk_level, pb.priority "
            "ORDER BY pb.priority ASC",
            cause_type, source="graph_rule",
        )
        if out:
            return out
        return self._query_graph_playbook(
            conn,
            "MATCH (pb:ResponsePlaybook) "
            "WHERE pb.cause_type=$cause AND pb.active=true "
            "RETURN pb.id, pb.action_type, pb.risk_level, pb.priority "
            "ORDER BY pb.priority ASC",
            cause_type, source="graph_direct",
        )

    @staticmethod
    def _query_graph_playbook(conn, query: str, cause_type: str, source: str) -> list:
        out = []
        try:
            r = conn.execute(query, {"cause": cause_type})
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
                    "source": source,
                })
        except Exception:
            pass
        return out

    # ── EXECUTE ─────────────────────────────────────────

    def execute_recovery(self, conn, action: dict, counters: dict) -> dict:
        """복구 액션을 실행(시뮬레이션)한다."""
        AutoRecoveryAgent._recovery_counter += 1
        recovery_id = f"REC-{AutoRecoveryAgent._recovery_counter:04d}"
        action_type = action.get("action_type", "ESCALATE")
        step_id = action.get("target_step", "unknown")
        param = action.get("parameter")
        confidence = action.get("confidence", 0.0)

        try:
            handler = _ACTION_HANDLERS.get(action_type)
            if handler is None:
                return _failure(action_type, step_id, recovery_id,
                                f"지원되지 않는 복구 유형: {action_type}")
            return handler(self, conn, recovery_id, step_id, param, confidence, counters)
        except Exception as e:
            return _failure(action_type, step_id, recovery_id,
                            f"복구 실행 오류: {str(e)[:200]}")

    def _do_adjust_parameter(self, conn, recovery_id, step_id, param, confidence, counters):
        if param != "yield_rate":
            return _failure("ADJUST_PARAMETER", step_id, recovery_id,
                            f"지원되지 않는 파라미터: {param}")
        adjustment = 0.005 if confidence >= 0.7 else 0.002
        r = conn.execute(
            "MATCH (ps:ProcessStep) WHERE ps.id = $step_id RETURN ps.yield_rate",
            {"step_id": step_id},
        )
        if not r.has_next():
            return _failure("ADJUST_PARAMETER", step_id, recovery_id, "step not found")

        current = float(r.get_next()[0])
        new_val = min(current + adjustment, 0.999)
        conn.execute(
            "MATCH (ps:ProcessStep) WHERE ps.id = $step_id SET ps.yield_rate = $val",
            {"step_id": step_id, "val": new_val},
        )
        self._store_recovery_action(
            conn, recovery_id, "ADJUST_PARAMETER", counters,
            parameter=param, old_value=current, new_value=new_val, success=True,
        )
        return {
            "success": True,
            "action_type": "ADJUST_PARAMETER",
            "step_id": step_id,
            "detail": f"yield_rate {current:.4f} → {new_val:.4f} (+{adjustment})",
            "recovery_id": recovery_id,
        }

    def _do_equipment_reset(self, conn, recovery_id, step_id, param, confidence, counters):
        oee_boost = 0.02
        r = conn.execute(
            "MATCH (ps:ProcessStep) WHERE ps.id = $step_id RETURN ps.oee",
            {"step_id": step_id},
        )
        if not r.has_next():
            return _failure("EQUIPMENT_RESET", step_id, recovery_id, "step not found")

        current_oee = float(r.get_next()[0])
        new_oee = min(current_oee + oee_boost, 0.999)
        conn.execute(
            "MATCH (ps:ProcessStep) WHERE ps.id = $step_id SET ps.oee = $val",
            {"step_id": step_id, "val": new_oee},
        )
        self._store_recovery_action(
            conn, recovery_id, "EQUIPMENT_RESET", counters,
            parameter="oee", old_value=current_oee, new_value=new_oee, success=True,
        )
        return {
            "success": True,
            "action_type": "EQUIPMENT_RESET",
            "step_id": step_id,
            "detail": f"OEE {current_oee:.4f} → {new_oee:.4f} (+{oee_boost})",
            "recovery_id": recovery_id,
        }

    def _do_increase_inspection(self, conn, recovery_id, step_id, param, confidence, counters):
        added = self._add_inspection_link(conn, step_id)
        self._store_recovery_action(
            conn, recovery_id, "INCREASE_INSPECTION", counters,
            parameter=None, old_value=None, new_value=None, success=True,
        )
        return {
            "success": True,
            "action_type": "INCREASE_INSPECTION",
            "step_id": step_id,
            "detail": f"검사 연결 {'추가됨' if added else '이미 존재 — 확인 완료'}",
            "recovery_id": recovery_id,
        }

    def _do_material_switch(self, conn, recovery_id, step_id, param, confidence, counters):
        self._store_recovery_action(
            conn, recovery_id, "MATERIAL_SWITCH", counters,
            parameter=None, old_value=None, new_value=None, success=True,
        )
        return {
            "success": True,
            "action_type": "MATERIAL_SWITCH",
            "step_id": step_id,
            "detail": "자재 LOT 변경 플래그 설정 — 공급망 담당자 알림 발송",
            "recovery_id": recovery_id,
        }

    def _do_escalate(self, conn, recovery_id, step_id, param, confidence, counters):
        self._store_recovery_action(
            conn, recovery_id, "ESCALATE", counters,
            parameter=None, old_value=None, new_value=None, success=False,
        )
        return {
            "success": False,
            "action_type": "ESCALATE",
            "step_id": step_id,
            "detail": "자동 복구 불가 — 운영자 에스컬레이션 발행",
            "recovery_id": recovery_id,
            "escalated": True,
        }

    # ── VERIFY / LEARN / MUTATE ─────────────────────────

    def verify_recovery(self, conn, step_id: str, pre_yield: float) -> dict:
        """복구 후 yield_rate를 측정하여 개선 여부를 판정한다."""
        try:
            r = conn.execute(
                "MATCH (ps:ProcessStep) WHERE ps.id = $step_id RETURN ps.yield_rate",
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
        key = (action_type, cause_type)
        self.success_history[key]["attempts"] += 1
        if success:
            self.success_history[key]["successes"] += 1

    def mutate_playbook(self) -> dict:
        """성공률 < 50% 인 (action_type, cause_type) 쌍의 우선순위를 swap한다."""
        mutations = []
        for (action_type, cause_type), hist in list(self.success_history.items()):
            attempts = hist["attempts"]
            if attempts < 3:
                continue
            success_rate = hist["successes"] / attempts
            if success_rate >= 0.50:
                continue

            playbook_entries = self.recovery_playbook.get(cause_type, [])
            if len(playbook_entries) < 2:
                continue

            current_idx = next(
                (i for i, e in enumerate(playbook_entries) if e["action"] == action_type),
                None,
            )
            if current_idx is None:
                continue

            next_idx = (current_idx + 1) % len(playbook_entries)
            new_action = playbook_entries[next_idx]["action"]
            if action_type == new_action:
                continue

            playbook_entries[current_idx], playbook_entries[next_idx] = (
                playbook_entries[next_idx],
                playbook_entries[current_idx],
            )
            mutations.append({
                "cause_type": cause_type,
                "old_action": action_type,
                "new_action": new_action,
                "old_success_rate": round(success_rate, 3),
                "attempts": attempts,
            })

        return {"mutations_applied": len(mutations), "details": mutations[:10]}

    # ── Internal ────────────────────────────────────────

    def _get_current_value(self, conn, step_id: str, param: str):
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
        if old_value is None or adjustment is None or param is None:
            return None
        new_val = old_value + adjustment
        if param in ("yield_rate", "oee"):
            new_val = min(new_val, 0.999)
        return round(new_val, 6)

    def _add_inspection_link(self, conn, step_id: str) -> bool:
        """누락된 검사 연결을 추가한다."""
        try:
            r = conn.execute(
                "MATCH (insp:ProcessStep)-[:INSPECTS]->(ps:ProcessStep) "
                "WHERE ps.id = $step_id RETURN count(insp)",
                {"step_id": step_id},
            )
            if r.has_next() and int(r.get_next()[0]) > 0:
                return False

            r = conn.execute(
                "MATCH (ps:ProcessStep) WHERE ps.id = $step_id RETURN ps.area_id",
                {"step_id": step_id},
            )
            if not r.has_next():
                return False
            area_id = r.get_next()[0]

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
        self, conn, recovery_id: str, action_type: str, counters: dict,
        parameter=None, old_value=None, new_value=None, success: bool = True,
    ):
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
            pass


def _failure(action_type: str, step_id: str, recovery_id: str, detail: str) -> dict:
    return {
        "success": False,
        "action_type": action_type,
        "step_id": step_id,
        "detail": detail,
        "recovery_id": recovery_id,
    }


_ACTION_HANDLERS = {
    "ADJUST_PARAMETER": AutoRecoveryAgent._do_adjust_parameter,
    "EQUIPMENT_RESET": AutoRecoveryAgent._do_equipment_reset,
    "INCREASE_INSPECTION": AutoRecoveryAgent._do_increase_inspection,
    "MATERIAL_SWITCH": AutoRecoveryAgent._do_material_switch,
    "ESCALATE": AutoRecoveryAgent._do_escalate,
}
