"""HITL(Human-In-The-Loop) 관리 믹스인 — 승인/거절/정책/감사."""
import json
import os
from datetime import datetime

from v4.decision_layer import update_active_policy
from v4.isa95 import lookup_personnel, personnel_can_approve_safety
from v4.regulation import record_audit_trail


class HITLMixin:
    """HITL 큐 관리, 정책 업데이트, 감사 로그, 영속화."""

    async def resolve_hitl(
        self,
        hitl_id: str,
        approve: bool,
        operator: str = "operator",
        role: str = "operator",
        personnel_id: str | None = None,
    ):
        """HITL 대기 액션을 승인/거절한다.

        personnel_id (선택): Personnel 노드 식별자. 제공 시:
        - operator audit log에 personnel 정보 영속화
        - safety_level 검증 (Personnel.safety_level_max < action.safety_level → deny)

        personnel_id 미제공 시 기존 anonymous 동작 (하위 호환).
        """
        item = self._find_pending_hitl(hitl_id)
        if not item:
            return {"ok": False, "reason": "not_found_or_already_resolved", "id": hitl_id}

        # Personnel 식별 (선택)
        personnel = lookup_personnel(self.conn, personnel_id) if personnel_id else None

        if not approve:
            return await self._reject_hitl(item, hitl_id, operator, role, personnel=personnel)

        # 고위험/저신뢰 액션은 supervisor 이상만 승인 가능
        reason = str(item.get("reason", "") or "")
        if role != "supervisor" and ("high_risk" in reason or "low_confidence" in reason):
            return await self._deny_hitl(item, hitl_id, operator, role, personnel=personnel)

        # Personnel 안전등급 검증 (식별 시에만 — 미식별은 기존 동작 유지)
        action_safety = (item.get("action", {}) or {}).get("safety_level")
        if personnel and not personnel_can_approve_safety(personnel, action_safety):
            return await self._deny_hitl(
                item, hitl_id, operator, role, personnel=personnel,
                deny_reason="personnel_safety_insufficient",
            )

        return await self._approve_hitl(item, hitl_id, operator, role, personnel=personnel)

    def _find_pending_hitl(self, hitl_id: str):
        for h in self.hitl_pending:
            if h.get("id") == hitl_id and h.get("status") == "pending":
                return h
        return None

    async def _reject_hitl(self, item, hitl_id, operator, role, *, personnel: dict | None = None):
        item["status"] = "rejected"
        item["resolved_at"] = datetime.now().isoformat()
        item["operator"] = operator
        item["operator_role"] = role
        if personnel:
            item["personnel_id"] = personnel["id"]
            item["personnel_name"] = personnel["name"]
        audit_extra = {"hitl_id": hitl_id}
        if personnel:
            audit_extra["personnel_id"] = personnel["id"]
        self._append_hitl_audit("rejected", operator, audit_extra, role=role)
        self._persist_hitl_runtime_state()
        await self._emit("hitl_resolved", {
            "id": hitl_id, "status": "rejected", "operator": operator,
            "personnel_id": personnel["id"] if personnel else None,
        })
        return {"ok": True, "status": "rejected", "id": hitl_id}

    async def _deny_hitl(self, item, hitl_id, operator, role, *,
                         personnel: dict | None = None, deny_reason: str = "supervisor_required"):
        item["status"] = "denied"
        item["resolved_at"] = datetime.now().isoformat()
        item["operator"] = operator
        item["operator_role"] = role
        if personnel:
            item["personnel_id"] = personnel["id"]
        audit_extra = {"hitl_id": hitl_id, "reason": deny_reason}
        if personnel:
            audit_extra["personnel_id"] = personnel["id"]
            audit_extra["personnel_safety_max"] = personnel.get("safety_level_max")
        self._append_hitl_audit("approve_denied", operator, audit_extra, role=role)
        self._persist_hitl_runtime_state()
        await self._emit("hitl_resolved", {
            "id": hitl_id, "status": "denied", "operator": operator,
            "reason": deny_reason,
            "personnel_id": personnel["id"] if personnel else None,
        })
        return {"ok": False, "status": "denied", "id": hitl_id, "reason": deny_reason}

    async def _approve_hitl(self, item, hitl_id, operator, role, *, personnel: dict | None = None):
        action = item.get("action", {})
        item["status"] = "approved"
        item["resolved_at"] = datetime.now().isoformat()
        item["operator"] = operator
        item["operator_role"] = role
        if personnel:
            item["personnel_id"] = personnel["id"]
            item["personnel_name"] = personnel["name"]
            item["personnel_safety_max"] = personnel.get("safety_level_max")
        try:
            result = self.auto_recovery.execute_recovery(self.conn, action, self.healing_counters)
            payload = {
                "id": hitl_id,
                "status": "approved",
                "operator": operator,
                "action_type": action.get("action_type"),
                "step_id": action.get("target_step"),
                "result": result,
                "personnel_id": personnel["id"] if personnel else None,
            }
            audit_extra = {"hitl_id": hitl_id, "action_type": action.get("action_type")}
            if personnel:
                audit_extra["personnel_id"] = personnel["id"]
            self._append_hitl_audit("approved", operator, audit_extra, role=role)
            # AuditTrail 그래프 영속 — 외부 감사 (Regulation/Compliance) 추적
            try:
                record_audit_trail(
                    self.conn,
                    audit_id=f"AT-{hitl_id}",
                    event_type="hitl_approved",
                    target_id=str(action.get("target_step", "")),
                    personnel_id=personnel["id"] if personnel else None,
                    details=f"action={action.get('action_type', '?')}, operator={operator}",
                )
            except Exception:
                pass
            self._persist_hitl_runtime_state()
            await self._emit("hitl_resolved", payload)
            return {"ok": True, **payload}
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
            self._append_hitl_audit(
                "approve_failed", operator,
                {"hitl_id": hitl_id, "error": str(exc)}, role=role,
            )
            self._persist_hitl_runtime_state()
            await self._emit("hitl_resolved", {
                "id": hitl_id, "status": "failed", "operator": operator, "error": str(exc),
            })
            return {"ok": False, "status": "failed", "id": hitl_id, "error": str(exc)}

    async def update_hitl_policy(self, patch: dict, operator: str = "operator", role: str = "operator"):
        """HITL 정책을 런타임에서 업데이트한다."""
        prev_policy = dict(self.hitl_policy)
        if role != "supervisor":
            self._append_hitl_audit(
                "policy_update_denied", operator,
                {"reason": "supervisor_required", "patch": patch or {}}, role=role,
            )
            await self._emit("hitl_policy_update_denied", {
                "reason": "supervisor_required", "operator": operator, "role": role,
            })
            return dict(self.hitl_policy)

        if "min_confidence" in patch:
            self.hitl_policy["min_confidence"] = _clip(patch.get("min_confidence"), 0.3, 0.95)
        if "high_risk_threshold" in patch:
            self.hitl_policy["high_risk_threshold"] = _clip(patch.get("high_risk_threshold"), 0.3, 0.95)
        if "medium_requires_history" in patch:
            self.hitl_policy["medium_requires_history"] = bool(patch.get("medium_requires_history"))

        self._append_hitl_audit(
            "policy_updated", operator,
            {
                "prev": prev_policy,
                "next": dict(self.hitl_policy),
                "diff": self._policy_diff(prev_policy, self.hitl_policy),
            },
            role=role,
        )
        update_active_policy(self.conn, self.hitl_policy)
        self._persist_hitl_runtime_state()
        await self._emit("hitl_policy_updated", {
            "policy": dict(self.hitl_policy),
            "prev_policy": prev_policy,
            "diff": self._policy_diff(prev_policy, self.hitl_policy),
            "operator": operator,
            "role": role,
        })
        return dict(self.hitl_policy)

    def _append_hitl_audit(self, action: str, operator: str,
                            detail: dict | None = None, role: str = "operator"):
        self.hitl_audit.append({
            "ts": datetime.now().isoformat(),
            "action": action,
            "operator": operator,
            "role": role,
            "detail": detail or {},
        })
        self.hitl_audit = self.hitl_audit[-200:]

    @staticmethod
    def _policy_diff(prev: dict, nxt: dict):
        keys = ("min_confidence", "high_risk_threshold", "medium_requires_history")
        out = {}
        for k in keys:
            pv = prev.get(k)
            nv = nxt.get(k)
            if pv != nv:
                out[k] = {"from": pv, "to": nv}
        return out

    def _persist_hitl_runtime_state(self):
        try:
            os.makedirs(self.results_dir, exist_ok=True)
            path = os.path.join(self.results_dir, "hitl_runtime_state.json")
            payload = {
                "policy": dict(self.hitl_policy),
                "pending": self.hitl_pending[-200:],
                "audit": self.hitl_audit[-500:],
                "updated_at": datetime.now().isoformat(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_hitl_runtime_state(self):
        try:
            path = os.path.join(self.results_dir, "hitl_runtime_state.json")
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            policy = payload.get("policy", {})
            if isinstance(policy, dict):
                self.hitl_policy.update({
                    "min_confidence": float(policy.get("min_confidence", self.hitl_policy["min_confidence"])),
                    "high_risk_threshold": float(policy.get("high_risk_threshold", self.hitl_policy["high_risk_threshold"])),
                    "medium_requires_history": bool(policy.get("medium_requires_history", self.hitl_policy["medium_requires_history"])),
                })
            pending = payload.get("pending", [])
            audit = payload.get("audit", [])
            if isinstance(pending, list):
                self.hitl_pending = pending[-200:]
            if isinstance(audit, list):
                self.hitl_audit = audit[-500:]
        except Exception:
            pass


def _clip(v, lo: float, hi: float) -> float:
    try:
        f = float(v)
    except Exception:
        f = lo
    return max(lo, min(hi, f))
