"""
L5 Learning Layer — 자가 진화 학습 이력 온톨로지화
===================================================
VISION.md 섹션 4.2 Layer 5 자가 진화: LearningRecord, StrategyMutation 노드를
온톨로지에 저장하여 학습 이력을 그래프 쿼리로 감사 가능하게 한다.

설계 원칙 (VISION 9.5):
  - 모든 장애는 삭제하지 않고 구조화 → 학습 이력도 동일 적용
  - 각 진화 사이클마다 LearningRecord upsert
  - 전략별 fitness 변동은 StrategyMutation으로 누적 (삭제 없음)

관계:
  - LearningRecord -[:TESTED_MUTATION]-> StrategyMutation
  - LearningRecord -[:SUPERSEDES]-> LearningRecord (이전 사이클)
"""
from datetime import datetime

# 노드 ID 포맷 — LearningRecord, StrategyMutation은 cycle 기준 안정적 ID 부여
LEARNING_RECORD_PREFIX = "LR"
STRATEGY_MUTATION_PREFIX = "SM"
CYCLE_ID_DIGITS = 6  # LR-000001, LR-000042 형태로 정렬 가능


def _learning_record_id(cycle_num: int) -> str:
    return f"{LEARNING_RECORD_PREFIX}-{cycle_num:0{CYCLE_ID_DIGITS}d}"


def _strategy_mutation_id(cycle_num: int, strategy_name: str) -> str:
    return f"{STRATEGY_MUTATION_PREFIX}-{cycle_num:0{CYCLE_ID_DIGITS}d}-{strategy_name}"


def extend_schema_l5(conn) -> None:
    """L5 자가 진화 계층 노드와 관계를 스키마에 추가한다."""
    statements = [
        (
            "CREATE NODE TABLE IF NOT EXISTS LearningRecord ("
            "id STRING, cycle_number INT64, agent_type STRING, "
            "overall_fitness DOUBLE, strategies_run INT64, "
            "strategies_improved INT64, mutations_tested INT64, "
            "best_strategy STRING, best_fitness DOUBLE, "
            "improvement_delta DOUBLE, created_at STRING, "
            "PRIMARY KEY(id))"
        ),
        (
            "CREATE NODE TABLE IF NOT EXISTS StrategyMutation ("
            "id STRING, cycle_number INT64, strategy_name STRING, "
            "fitness_before DOUBLE, fitness_after DOUBLE, "
            "fitness_impact DOUBLE, applied BOOLEAN, "
            "created_at STRING, PRIMARY KEY(id))"
        ),
        (
            "CREATE REL TABLE IF NOT EXISTS TESTED_MUTATION ("
            "FROM LearningRecord TO StrategyMutation)"
        ),
        (
            "CREATE REL TABLE IF NOT EXISTS SUPERSEDES ("
            "FROM LearningRecord TO LearningRecord)"
        ),
    ]
    for stmt in statements:
        try:
            conn.execute(stmt)
        except Exception:
            # 이미 존재하거나 Kuzu 버전 차이 — 재시도하지 않음
            pass


def sync_learning_to_ontology(conn, cycle_result: dict,
                              prev_fitness: float = 0.5,
                              prev_record_id: str | None = None) -> dict:
    """진화 사이클 결과를 LearningRecord + StrategyMutation 노드로 영속화한다.

    LearningRecord는 cycle_number 기준 upsert (최신만 유지할 수도, 역사도 가능).
    여기서는 완전 이력을 위해 **삭제 없음** — 각 사이클마다 새 레코드 생성.
    StrategyMutation은 cycle + strategy 단위로 새로 생성.

    Args:
        conn: Kuzu Connection
        cycle_result: EvolutionAgent.run_evolution_cycle() 반환값
        prev_fitness: 직전 사이클 overall_fitness (개선 델타 계산용)
        prev_record_id: 직전 LearningRecord ID (SUPERSEDES 관계 연결용)

    Returns:
        {"record_id": str, "mutations_created": int, "supersedes_linked": bool}
    """
    cycle_num = int(cycle_result.get("cycle", 0))
    if cycle_num <= 0:
        return {"record_id": "", "mutations_created": 0, "supersedes_linked": False}

    record_id = _learning_record_id(cycle_num)
    now_iso = datetime.now().isoformat()
    overall_fitness = float(cycle_result.get("overall_fitness", 0.5))
    improvement_delta = overall_fitness - prev_fitness

    # LearningRecord upsert: 기존 동일 cycle 레코드는 제거 후 재생성
    try:
        conn.execute(
            "MATCH (lr:LearningRecord)-[r:TESTED_MUTATION]->() "
            "WHERE lr.id=$id DELETE r",
            {"id": record_id},
        )
        conn.execute(
            "MATCH (lr:LearningRecord) WHERE lr.id=$id DELETE lr",
            {"id": record_id},
        )
    except Exception:
        pass

    try:
        conn.execute(
            "CREATE (lr:LearningRecord {"
            "id:$id, cycle_number:$cn, agent_type:'EvolutionAgent', "
            "overall_fitness:$of, strategies_run:$sr, "
            "strategies_improved:$si, mutations_tested:$mt, "
            "best_strategy:$bs, best_fitness:$bf, "
            "improvement_delta:$idelta, created_at:$ts})",
            {
                "id": record_id,
                "cn": cycle_num,
                "of": overall_fitness,
                "sr": int(cycle_result.get("strategies_run", 0)),
                "si": int(cycle_result.get("strategies_improved", 0)),
                "mt": int(cycle_result.get("mutations_tested", 0)),
                "bs": str(cycle_result.get("best_strategy") or "none"),
                "bf": float(cycle_result.get("best_fitness", 0.0)),
                "idelta": improvement_delta,
                "ts": now_iso,
            },
        )
    except Exception:
        return {"record_id": "", "mutations_created": 0, "supersedes_linked": False}

    # 각 전략에 대한 StrategyMutation 생성 + TESTED_MUTATION 관계
    mutations_created = 0
    details = cycle_result.get("details", []) or []
    for detail in details:
        strat_name = str(detail.get("name", "unknown"))
        fb = float(detail.get("fitness_before", 0.0))
        fa = float(detail.get("fitness_after", 0.0))
        applied = bool(detail.get("applied", False))
        mut_id = _strategy_mutation_id(cycle_num, strat_name)
        try:
            conn.execute(
                "CREATE (sm:StrategyMutation {"
                "id:$id, cycle_number:$cn, strategy_name:$sn, "
                "fitness_before:$fb, fitness_after:$fa, "
                "fitness_impact:$fi, applied:$ap, created_at:$ts})",
                {
                    "id": mut_id, "cn": cycle_num, "sn": strat_name,
                    "fb": fb, "fa": fa, "fi": fa - fb,
                    "ap": applied, "ts": now_iso,
                },
            )
            conn.execute(
                "MATCH (lr:LearningRecord), (sm:StrategyMutation) "
                "WHERE lr.id=$lr AND sm.id=$sm "
                "CREATE (lr)-[:TESTED_MUTATION]->(sm)",
                {"lr": record_id, "sm": mut_id},
            )
            mutations_created += 1
        except Exception:
            continue

    # 직전 사이클과 SUPERSEDES 관계 연결
    supersedes_linked = False
    if prev_record_id and prev_record_id != record_id:
        try:
            conn.execute(
                "MATCH (curr:LearningRecord), (prev:LearningRecord) "
                "WHERE curr.id=$curr AND prev.id=$prev "
                "CREATE (curr)-[:SUPERSEDES]->(prev)",
                {"curr": record_id, "prev": prev_record_id},
            )
            supersedes_linked = True
        except Exception:
            pass

    return {
        "record_id": record_id,
        "mutations_created": mutations_created,
        "supersedes_linked": supersedes_linked,
        "improvement_delta": improvement_delta,
    }
