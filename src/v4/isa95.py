"""ISA-95 (IEC 62264) 4-level 스키마 시작점 — 표준 호환 기반층.

ISA-95는 제조 운영 통합 모델의 국제 표준. 4-level 위계:
    Enterprise > Site > Area > WorkUnit/WorkCenter

본 저장소는 현재 ProcessArea > ProcessStep 의 2-level 만 표현. 다공장 확장,
IATF 16949 감사, MES/ERP 외부 통합의 *선결 조건* 으로 ISA-95 위계와 호환되는
시작점을 제공한다.

본 모듈 범위 (작은 시작):
- Enterprise 노드 — 회사 단위 (예: "EV Battery Mfg Co")
- Site 노드 — 공장/사이트 단위 (예: "Cheonan Plant")
- EquipmentClass 노드 — 동종 설비의 클래스 (현 Equipment는 인스턴스)
- 관계: HAS_SITE, CONTAINS_AREA, INSTANCE_OF
- 기본 시드: 1 Enterprise + 1 Site + 기존 5 ProcessArea와 CONTAINS_AREA 연결

다음 사이클 범위 (보류):
- ProcessArea/ProcessStep 에 plant_id/site_id 속성 추가 (다공장 쿼리 필터)
- Personnel + Qualification (운영자 + 자격)
- Regulation/Audit/Compliance (UN R150, IATF 16949 거버넌스)
- ProcessSegment (ISA-95 OperationsDefinition)

설계 원칙: 모든 스키마 확장은 idempotent (재실행 안전).
"""

from __future__ import annotations

# ── 기본 시드 상수 ───────────────────────────────────────────────────────────

DEFAULT_ENTERPRISE_ID = "ENT-001"
DEFAULT_ENTERPRISE_NAME = "EV Battery Mfg Co"
DEFAULT_SITE_ID = "SITE-001"
DEFAULT_SITE_NAME = "Cheonan Plant"
DEFAULT_SITE_LOCATION = "충남 천안"


def extend_schema_isa95(conn) -> None:
    """ISA-95 노드 + 관계 idempotent 추가.

    이미 존재하면 silent skip (try/except). 한 번이라도 호출되면 모든 후속
    호출이 안전하게 No-op.
    """
    # ── Nodes ──
    _try(conn, """
        CREATE NODE TABLE Enterprise (
            id STRING,
            name STRING,
            country STRING,
            PRIMARY KEY(id)
        )
    """)
    _try(conn, """
        CREATE NODE TABLE Site (
            id STRING,
            name STRING,
            location STRING,
            timezone STRING,
            PRIMARY KEY(id)
        )
    """)
    _try(conn, """
        CREATE NODE TABLE EquipmentClass (
            id STRING,
            name STRING,
            category STRING,
            description STRING,
            PRIMARY KEY(id)
        )
    """)

    # ── Relationships ──
    _try(conn, "CREATE REL TABLE HAS_SITE (FROM Enterprise TO Site)")
    _try(conn, "CREATE REL TABLE CONTAINS_AREA (FROM Site TO ProcessArea)")
    _try(conn, "CREATE REL TABLE INSTANCE_OF (FROM Equipment TO EquipmentClass)")


def seed_default_isa95(conn) -> dict:
    """기본 1 Enterprise + 1 Site + 기존 ProcessArea 5개 연결.

    이미 시드된 경우 skip. ProcessArea 변경 없음 (Site → ProcessArea 관계만 추가).

    Returns:
        시드 결과 카운터 dict (생성 vs skip).
    """
    counters = {"enterprise_created": 0, "site_created": 0, "area_linked": 0}

    # Enterprise
    if not _exists(conn, "MATCH (e:Enterprise {id: $id}) RETURN e.id LIMIT 1",
                   {"id": DEFAULT_ENTERPRISE_ID}):
        _try(conn, f"""
            CREATE (e:Enterprise {{
                id: '{DEFAULT_ENTERPRISE_ID}',
                name: '{DEFAULT_ENTERPRISE_NAME}',
                country: 'KR'
            }})
        """)
        counters["enterprise_created"] = 1

    # Site
    if not _exists(conn, "MATCH (s:Site {id: $id}) RETURN s.id LIMIT 1",
                   {"id": DEFAULT_SITE_ID}):
        _try(conn, f"""
            CREATE (s:Site {{
                id: '{DEFAULT_SITE_ID}',
                name: '{DEFAULT_SITE_NAME}',
                location: '{DEFAULT_SITE_LOCATION}',
                timezone: 'Asia/Seoul'
            }})
        """)
        counters["site_created"] = 1

    # Enterprise → Site (HAS_SITE)
    _try(conn, f"""
        MATCH (e:Enterprise {{id: '{DEFAULT_ENTERPRISE_ID}'}}),
              (s:Site {{id: '{DEFAULT_SITE_ID}'}})
        WHERE NOT EXISTS {{ MATCH (e)-[:HAS_SITE]->(s) }}
        CREATE (e)-[:HAS_SITE]->(s)
    """)

    # Site → ProcessArea (CONTAINS_AREA) — 기존 5개 ProcessArea 모두 연결
    try:
        r = conn.execute("MATCH (pa:ProcessArea) RETURN pa.id")
        area_ids: list[str] = []
        while r.has_next():
            area_ids.append(r.get_next()[0])
    except Exception:
        area_ids = []

    for area_id in area_ids:
        if not _exists(
            conn,
            "MATCH (s:Site {id: $sid})-[:CONTAINS_AREA]->(pa:ProcessArea {id: $aid}) "
            "RETURN s.id LIMIT 1",
            {"sid": DEFAULT_SITE_ID, "aid": area_id},
        ):
            _try(conn, f"""
                MATCH (s:Site {{id: '{DEFAULT_SITE_ID}'}}),
                      (pa:ProcessArea {{id: '{area_id}'}})
                CREATE (s)-[:CONTAINS_AREA]->(pa)
            """)
            counters["area_linked"] += 1

    return counters


def get_default_site() -> dict:
    """기본 site 정보 — 현재는 단일 plant라 hardcoded.

    다공장 확장 시 이 함수가 동적 lookup으로 변경됨.
    """
    return {
        "enterprise_id": DEFAULT_ENTERPRISE_ID,
        "site_id": DEFAULT_SITE_ID,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _try(conn, query: str, params: dict | None = None) -> None:
    """Idempotent execute — 기존 객체 충돌은 silent skip."""
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
