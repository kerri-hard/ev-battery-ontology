"""Regulation / Audit / Compliance 거버넌스 노드 — UN R150 / IATF 16949 / EU Battery.

ISA-95 기반층 (isa95.py) 의 자연 후속. 외부 감사·인증·규제 추적 시작점.

본 모듈 범위 (작은 시작):
- Regulation 노드 — 규제/표준 (UN R150, IATF 16949, EU Battery Regulation 등)
- ComplianceItem 노드 — 인증/감사 항목 (FMEA / MSA / PPAP / APQP / Cell-Pack 안전 시퀀스)
- AuditTrail 노드 — 감사 이벤트 이력 (HITL audit 와 별개, 외부 감사용)
- 관계: REQUIRES, AUDITS, COMPLIES_WITH

기본 시드:
- REG-001 UN R150 (배터리 안전)
- REG-002 IATF 16949 (자동차 품질)
- REG-003 EU Battery Regulation 2027 (BatteryPassport 강화)
- 각 Regulation에 핵심 ComplianceItem 1-2개

다음 사이클 범위 (보류):
- Incident/RecoveryAction에 COMPLIES_WITH 자동 연결 (모든 액션이 어떤 규제를 충족하는가)
- AuditTrail 자동 영속 (HITL audit + Personnel 식별 결합)
- 규제 만료/갱신 자동 알림

설계 원칙: 모든 스키마 확장 idempotent (CLAUDE.md §9.9).
"""

from __future__ import annotations

# ── 기본 시드 상수 ───────────────────────────────────────────────────────────

DEFAULT_REGULATIONS = [
    {
        "id": "REG-001",
        "name": "UN R150",
        "description": "EV 배터리 안전 기준 (UNECE)",
        "category": "safety",
        "country": "International",
        "effective_date": "2022-09-01",
    },
    {
        "id": "REG-002",
        "name": "IATF 16949",
        "description": "자동차 품질 관리 표준 (FMEA / MSA / PPAP / APQP / SPC)",
        "category": "quality",
        "country": "International",
        "effective_date": "2016-10-01",
    },
    {
        "id": "REG-003",
        "name": "EU Battery Regulation 2023/1542",
        "description": "EU 배터리 규제 — BatteryPassport / 재활용율 / 탄소 발자국",
        "category": "compliance",
        "country": "EU",
        "effective_date": "2027-02-18",
    },
]

DEFAULT_COMPLIANCE_ITEMS = [
    # UN R150
    {"id": "COMP-001", "name": "셀-팩 안전 입증 시퀀스", "regulation_id": "REG-001", "kind": "test_sequence"},
    {"id": "COMP-002", "name": "고전압 절연 검사", "regulation_id": "REG-001", "kind": "test"},
    # IATF 16949
    {"id": "COMP-003", "name": "FMEA RPN 검토", "regulation_id": "REG-002", "kind": "review"},
    {"id": "COMP-004", "name": "MSA Gage R&R", "regulation_id": "REG-002", "kind": "measurement"},
    {"id": "COMP-005", "name": "PPAP 제출", "regulation_id": "REG-002", "kind": "submission"},
    # EU Battery
    {"id": "COMP-006", "name": "BatteryPassport 데이터 충족", "regulation_id": "REG-003", "kind": "data_compliance"},
    {"id": "COMP-007", "name": "재활용율 추적", "regulation_id": "REG-003", "kind": "traceability"},
]


def extend_schema_regulation(conn) -> None:
    """Regulation / ComplianceItem / AuditTrail 노드 + 관계 idempotent 추가."""
    _try(conn, """
        CREATE NODE TABLE Regulation (
            id STRING,
            name STRING,
            description STRING,
            category STRING,
            country STRING,
            effective_date STRING,
            PRIMARY KEY(id)
        )
    """)
    _try(conn, """
        CREATE NODE TABLE ComplianceItem (
            id STRING,
            name STRING,
            regulation_id STRING,
            kind STRING,
            PRIMARY KEY(id)
        )
    """)
    _try(conn, """
        CREATE NODE TABLE AuditTrail (
            id STRING,
            event_type STRING,
            target_id STRING,
            personnel_id STRING,
            timestamp STRING,
            details STRING,
            PRIMARY KEY(id))
    """)
    # 관계
    _try(conn, "CREATE REL TABLE REQUIRES (FROM Regulation TO ComplianceItem)")
    _try(conn, "CREATE REL TABLE AUDITS (FROM AuditTrail TO ComplianceItem)")
    _try(conn, "CREATE REL TABLE COMPLIES_WITH (FROM RecoveryAction TO ComplianceItem)")


def seed_default_regulations(conn) -> dict:
    """기본 3 Regulation + 7 ComplianceItem + REQUIRES 관계 자동 시드."""
    counters = {"regulations_created": 0, "compliance_items_created": 0, "requires_linked": 0}

    for reg in DEFAULT_REGULATIONS:
        if not _exists(conn, "MATCH (r:Regulation {id: $id}) RETURN r.id LIMIT 1",
                       {"id": reg["id"]}):
            _try(conn, f"""
                CREATE (r:Regulation {{
                    id: '{reg["id"]}',
                    name: '{reg["name"]}',
                    description: '{reg["description"]}',
                    category: '{reg["category"]}',
                    country: '{reg["country"]}',
                    effective_date: '{reg["effective_date"]}'
                }})
            """)
            counters["regulations_created"] += 1

    for item in DEFAULT_COMPLIANCE_ITEMS:
        if not _exists(conn, "MATCH (c:ComplianceItem {id: $id}) RETURN c.id LIMIT 1",
                       {"id": item["id"]}):
            _try(conn, f"""
                CREATE (c:ComplianceItem {{
                    id: '{item["id"]}',
                    name: '{item["name"]}',
                    regulation_id: '{item["regulation_id"]}',
                    kind: '{item["kind"]}'
                }})
            """)
            counters["compliance_items_created"] += 1
        # REQUIRES 관계
        _try(conn, f"""
            MATCH (r:Regulation {{id: '{item["regulation_id"]}'}}),
                  (c:ComplianceItem {{id: '{item["id"]}'}})
            WHERE NOT EXISTS {{ MATCH (r)-[:REQUIRES]->(c) }}
            CREATE (r)-[:REQUIRES]->(c)
        """)

    return counters


# action_type → ComplianceItem 매핑 (정적 — 도메인 지식).
# 향후 그래프 기반 학습으로 동적화 가능.
ACTION_COMPLIANCE_MAP: dict[str, list[str]] = {
    "ADJUST_PARAMETER": ["COMP-003", "COMP-004"],   # FMEA 검토 + MSA Gage R&R
    "INCREASE_INSPECTION": ["COMP-002", "COMP-004"], # 고전압 절연 + MSA
    "EQUIPMENT_RESET": ["COMP-001", "COMP-003"],     # 셀-팩 안전 + FMEA
    "MATERIAL_SWITCH": ["COMP-005", "COMP-006"],     # PPAP + BatteryPassport
    "ESCALATE": ["COMP-001"],                        # 안전 시퀀스 강제
}


def link_action_to_compliance(conn, recovery_action_id: str, action_type: str) -> int:
    """RecoveryAction → ComplianceItem COMPLIES_WITH 관계 자동 생성.

    action_type 에 매핑된 ComplianceItem들과 idempotent 연결.

    Returns:
        생성된 관계 수 (이미 존재하면 0).
    """
    if not recovery_action_id or not action_type:
        return 0
    items = ACTION_COMPLIANCE_MAP.get(action_type, [])
    if not items:
        return 0
    created = 0
    for comp_id in items:
        try:
            r = conn.execute(
                "MATCH (ra:RecoveryAction {id: $rid})-[:COMPLIES_WITH]->"
                "(c:ComplianceItem {id: $cid}) RETURN ra.id LIMIT 1",
                {"rid": recovery_action_id, "cid": comp_id},
            )
            if r.has_next():
                continue
        except Exception:
            pass
        try:
            conn.execute(
                "MATCH (ra:RecoveryAction {id: $rid}), "
                "      (c:ComplianceItem {id: $cid}) "
                "CREATE (ra)-[:COMPLIES_WITH]->(c)",
                {"rid": recovery_action_id, "cid": comp_id},
            )
            created += 1
        except Exception:
            pass
    return created


def _try(conn, query: str, params: dict | None = None) -> None:
    try:
        if params:
            conn.execute(query, params)
        else:
            conn.execute(query)
    except Exception:
        pass


def _exists(conn, query: str, params: dict | None = None) -> bool:
    try:
        r = conn.execute(query, params or {})
        return r.has_next()
    except Exception:
        return False
