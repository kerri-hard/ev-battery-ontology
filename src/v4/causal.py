"""
Causal Reasoning Layer (L3) — 인과 추론 계층
=============================================
경로 거리 기반 RCA → 인과관계 체인 기반 RCA로 전환.

학술 근거:
  - KG-Driven Fault Diagnosis (Sensors, 2025)
  - CausalTrace: Neurosymbolic Causal Analysis (arXiv, 2025)
  - Causal AI for Manufacturing RCA (Databricks, 2025)

핵심 개념:
  CausalRule: (원인)─[CAUSES]→(중간결과)─[CAUSES]→(최종증상)
  FailureChain: 과거 확인된 원인→증상 체인 (패턴 매칭용)
  AnomalyPattern: 시계열 특성 (drift, spike, oscillation)

개선 효과:
  - "장비 MTBF 초과" 같은 피상적 원인 → 진짜 근본 원인 추적
  - 과거 동일 장애 즉시 인식 → 복구 시간 단축
  - 인과관계 강도 학습 → 진단 정확도 향상
"""
import math
from collections import defaultdict
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
#  L3 SCHEMA EXTENSION
# ═══════════════════════════════════════════════════════════════

def extend_schema_l3(conn):
    """온톨로지에 L3(인과 추론) 계층을 추가한다.

    CausalRule.strength 는 단일 P(effect|cause) 점추정. 향후 Bayesian
    conditional 추론 (VISION §4.3 "다음 핵심") 을 위해 ConditionalStrength
    노드를 시작점으로 도입 — context_factor 별 조건부 확률 P(effect|cause, ctx).
    """
    node_tables = [
        ("CREATE NODE TABLE CausalRule ("
         "id STRING, name STRING, cause_type STRING, effect_type STRING, "
         "strength DOUBLE DEFAULT 0.5, confirmation_count INT64 DEFAULT 0, "
         "last_confirmed STRING, PRIMARY KEY(id))"),
        ("CREATE NODE TABLE AnomalyPattern ("
         "id STRING, name STRING, pattern_type STRING, "
         "sensor_type STRING, description STRING, "
         "occurrence_count INT64 DEFAULT 0, PRIMARY KEY(id))"),
        ("CREATE NODE TABLE FailureChain ("
         "id STRING, step_id STRING, pattern_id STRING, "
         "cause_sequence STRING, resolution STRING, "
         "success_count INT64 DEFAULT 0, fail_count INT64 DEFAULT 0, "
         "avg_recovery_sec DOUBLE DEFAULT 0.0, PRIMARY KEY(id))"),
        # Bayesian conditional strength — VISION §4.3 시작점
        # 같은 cause라도 context (예: time_of_day, batch, equipment_class)
        # 에 따라 P(effect|cause, context) 가 다를 수 있음
        ("CREATE NODE TABLE ConditionalStrength ("
         "id STRING, causal_rule_id STRING, "
         "context_factor STRING, context_value STRING, "
         "conditional_prob DOUBLE DEFAULT 0.5, "
         "sample_count INT64 DEFAULT 0, "
         "last_updated STRING, PRIMARY KEY(id))"),
    ]
    rel_tables = [
        "CREATE REL TABLE CAUSES (FROM CausalRule TO CausalRule, strength DOUBLE DEFAULT 0.5)",
        "CREATE REL TABLE HAS_CAUSE (FROM ProcessStep TO CausalRule)",
        "CREATE REL TABLE HAS_PATTERN (FROM CausalRule TO AnomalyPattern)",
        "CREATE REL TABLE MATCHED_BY (FROM Incident TO FailureChain)",
        "CREATE REL TABLE CHAIN_USES (FROM FailureChain TO CausalRule)",
        "CREATE REL TABLE PREDICTS (FROM AnomalyPattern TO DefectMode, confidence DOUBLE DEFAULT 0.5)",
        # ConditionalStrength → CausalRule
        "CREATE REL TABLE CONDITIONS_ON (FROM ConditionalStrength TO CausalRule)",
    ]
    for ddl in node_tables + rel_tables:
        try:
            conn.execute(ddl)
        except Exception:
            pass


def record_conditional_strength(
    conn,
    causal_rule_id: str,
    context_factor: str,
    context_value: str,
    conditional_prob: float,
    sample_count: int = 1,
) -> str | None:
    """조건부 인과 강도 영속화 — P(effect|cause, context_factor=context_value).

    새 ConditionalStrength 노드 생성 또는 기존 (cause_id, factor, value) 조합 시
    sample_count 증가 + EMA 업데이트.

    Args:
        causal_rule_id: 부모 CausalRule.id
        context_factor: 예 "time_of_day", "batch_id", "equipment_class"
        context_value: 예 "night", "BATCH-2026-04", "EQ-WELDER-A"
        conditional_prob: P(effect|cause, context) 관측값 [0, 1]
        sample_count: 누적 샘플 수 (기본 1)

    Returns:
        ConditionalStrength 노드 ID 또는 None (실패).
    """
    from datetime import datetime as _dt
    cs_id = f"CS-{causal_rule_id}-{context_factor}-{context_value}"
    now = _dt.now().isoformat()
    p = max(0.0, min(1.0, float(conditional_prob)))
    try:
        # 기존 노드 lookup
        r = conn.execute(
            "MATCH (cs:ConditionalStrength {id: $id}) "
            "RETURN cs.conditional_prob, cs.sample_count LIMIT 1",
            {"id": cs_id},
        )
        if r.has_next():
            row = r.get_next()
            old_prob = float(row[0] or 0.5)
            old_n = int(row[1] or 0)
            # EMA update with sample-weighted alpha
            alpha = sample_count / max(old_n + sample_count, 1)
            new_prob = (1.0 - alpha) * old_prob + alpha * p
            try:
                conn.execute(
                    "MATCH (cs:ConditionalStrength {id: $id}) "
                    "SET cs.conditional_prob = $p, "
                    "    cs.sample_count = cs.sample_count + $n, "
                    "    cs.last_updated = $ts",
                    {"id": cs_id, "p": new_prob, "n": int(sample_count), "ts": now},
                )
                return cs_id
            except Exception:
                return None
        # 신규 노드 생성
        try:
            conn.execute(
                "CREATE (cs:ConditionalStrength {"
                "id: $id, causal_rule_id: $crid, "
                "context_factor: $cf, context_value: $cv, "
                "conditional_prob: $p, sample_count: $n, "
                "last_updated: $ts})",
                {
                    "id": cs_id, "crid": str(causal_rule_id),
                    "cf": str(context_factor), "cv": str(context_value),
                    "p": p, "n": int(sample_count), "ts": now,
                },
            )
            # CausalRule 과 연결
            try:
                conn.execute(
                    "MATCH (cs:ConditionalStrength {id: $id}), "
                    "      (cr:CausalRule {id: $crid}) "
                    "WHERE NOT EXISTS { MATCH (cs)-[:CONDITIONS_ON]->(cr) } "
                    "CREATE (cs)-[:CONDITIONS_ON]->(cr)",
                    {"id": cs_id, "crid": str(causal_rule_id)},
                )
            except Exception:
                pass
            return cs_id
        except Exception:
            return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
#  SEED CAUSAL KNOWLEDGE — 도메인 전문가 지식 시딩
# ═══════════════════════════════════════════════════════════════

# 제조 도메인의 알려진 인과관계 규칙
SEED_CAUSAL_RULES = [
    # 장비 마모 인과 체인
    {"id": "CR-001", "name": "실린더 마모 → 압력 부족", "cause": "equipment_wear", "effect": "pressure_drop", "strength": 0.85},
    {"id": "CR-002", "name": "압력 부족 → 접촉 불량", "cause": "pressure_drop", "effect": "contact_failure", "strength": 0.80},
    {"id": "CR-003", "name": "접촉 불량 → 수율 하락", "cause": "contact_failure", "effect": "yield_drop", "strength": 0.90},
    # 온도 인과 체인
    {"id": "CR-004", "name": "냉각 이상 → 온도 상승", "cause": "cooling_failure", "effect": "temperature_rise", "strength": 0.90},
    {"id": "CR-005", "name": "온도 상승 → 코팅 불량", "cause": "temperature_rise", "effect": "coating_defect", "strength": 0.75},
    {"id": "CR-006", "name": "코팅 불량 → 수율 하락", "cause": "coating_defect", "effect": "yield_drop", "strength": 0.85},
    # 자재 인과 체인
    {"id": "CR-007", "name": "자재 로트 변경 → 특성 편차", "cause": "material_lot_change", "effect": "property_deviation", "strength": 0.70},
    {"id": "CR-008", "name": "특성 편차 → 공정 변동", "cause": "property_deviation", "effect": "process_variation", "strength": 0.65},
    {"id": "CR-009", "name": "공정 변동 → 수율 하락", "cause": "process_variation", "effect": "yield_drop", "strength": 0.75},
    # 전기 인과 체인
    {"id": "CR-010", "name": "전류 이상 → 용접 불량", "cause": "current_anomaly", "effect": "welding_defect", "strength": 0.85},
    {"id": "CR-011", "name": "용접 불량 → 접합 강도 저하", "cause": "welding_defect", "effect": "joint_weakness", "strength": 0.90},
    {"id": "CR-012", "name": "접합 강도 저하 → 수율 하락", "cause": "joint_weakness", "effect": "yield_drop", "strength": 0.80},
    # 진동 인과 체인
    {"id": "CR-013", "name": "베어링 마모 → 진동 증가", "cause": "bearing_wear", "effect": "vibration_increase", "strength": 0.90},
    {"id": "CR-014", "name": "진동 증가 → 가공 정밀도 저하", "cause": "vibration_increase", "effect": "precision_loss", "strength": 0.80},
    {"id": "CR-015", "name": "가공 정밀도 저하 → 수율 하락", "cause": "precision_loss", "effect": "yield_drop", "strength": 0.75},
]

# 센서 유형 → 관련 인과관계 매핑
SENSOR_TO_CAUSES = {
    "temperature": ["cooling_failure", "temperature_rise", "coating_defect"],
    "current": ["current_anomaly", "welding_defect"],
    "vibration": ["bearing_wear", "vibration_increase", "precision_loss"],
    "torque_force": ["equipment_wear", "pressure_drop", "contact_failure"],
    "humidity": ["cooling_failure"],
}

ANOMALY_TO_PATTERN = {
    "trend_shift": "drift",
    "statistical_outlier": "spike",
    "threshold_breach": "level_shift",
}

# 이상 패턴 유형
ANOMALY_PATTERNS = [
    {"id": "AP-001", "name": "급격한 스파이크", "type": "spike", "desc": "정상 범위 내에서 갑자기 2σ 이상 급등/급락"},
    {"id": "AP-002", "name": "점진적 드리프트", "type": "drift", "desc": "평균이 서서히 한쪽으로 이동 (7점 규칙 위반)"},
    {"id": "AP-003", "name": "주기적 진동", "type": "oscillation", "desc": "값이 규칙적으로 오르내림 (베어링 마모 등)"},
    {"id": "AP-004", "name": "레벨 시프트", "type": "level_shift", "desc": "갑자기 새로운 평균으로 이동 후 유지"},
    {"id": "AP-005", "name": "분산 증가", "type": "variance_increase", "desc": "값의 변동폭이 점점 커짐"},
]


def seed_causal_knowledge(conn, counters):
    """도메인 전문가의 인과관계 지식을 온톨로지에 시딩한다."""
    for rule in SEED_CAUSAL_RULES:
        try:
            r = conn.execute("MATCH (n:CausalRule) WHERE n.id=$id RETURN count(n)", {"id": rule["id"]})
            if r.get_next()[0] == 0:
                conn.execute(
                    "CREATE (cr:CausalRule {id:$id, name:$name, cause_type:$cause, "
                    "effect_type:$effect, strength:$str, confirmation_count:0, last_confirmed:''})",
                    {"id": rule["id"], "name": rule["name"], "cause": rule["cause"],
                     "effect": rule["effect"], "str": rule["strength"]})
        except Exception:
            pass

    # 인과관계 체인 연결 (CAUSES 관계)
    chain_pairs = [
        ("CR-001", "CR-002"), ("CR-002", "CR-003"),  # 마모→압력→접촉→수율
        ("CR-004", "CR-005"), ("CR-005", "CR-006"),  # 냉각→온도→코팅→수율
        ("CR-007", "CR-008"), ("CR-008", "CR-009"),  # 자재→편차→변동→수율
        ("CR-010", "CR-011"), ("CR-011", "CR-012"),  # 전류→용접→접합→수율
        ("CR-013", "CR-014"), ("CR-014", "CR-015"),  # 베어링→진동→정밀도→수율
    ]
    for src, tgt in chain_pairs:
        try:
            conn.execute(
                "MATCH (a:CausalRule),(b:CausalRule) WHERE a.id=$s AND b.id=$t "
                "AND NOT (a)-[:CAUSES]->(b) "
                "CREATE (a)-[:CAUSES {strength: 0.8}]->(b)",
                {"s": src, "t": tgt})
        except Exception:
            pass

    # 이상 패턴 시딩
    for pat in ANOMALY_PATTERNS:
        try:
            r = conn.execute("MATCH (n:AnomalyPattern) WHERE n.id=$id RETURN count(n)", {"id": pat["id"]})
            if r.get_next()[0] == 0:
                conn.execute(
                    "CREATE (ap:AnomalyPattern {id:$id, name:$name, pattern_type:$type, "
                    "sensor_type:'', description:$desc, occurrence_count:0})",
                    {"id": pat["id"], "name": pat["name"], "type": pat["type"], "desc": pat["desc"]})
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  EXPLAINABLE RCA — 배제 후보의 *왜* 답
# ═══════════════════════════════════════════════════════════════

def _explain_exclusion(candidate: dict, top_candidate: dict | None) -> str:
    """배제된 candidate에 대한 *왜 선택되지 않았는가* 답.

    rca_score_breakdown을 분석해 어느 신호가 약했는지 자연어로 설명.
    운영자 신뢰 + HITL 검토 보조 (CausalTrace 학술 근거 §9.2).

    Returns:
        세미콜론 구분 사유 문자열 (예: "신뢰도 격차 큼 (Δ0.18); 과거 매칭 부족").
    """
    reasons: list[str] = []
    breakdown = candidate.get("rca_score_breakdown", {}) or {}

    if top_candidate is not None:
        gap = float(top_candidate.get("confidence", 0.0)) - float(candidate.get("confidence", 0.0))
        if gap >= 0.15:
            reasons.append(f"신뢰도 격차 큼 (Δ{gap:.2f})")
        elif gap >= 0.05:
            reasons.append(f"신뢰도 차이 (Δ{gap:.2f})")

    if float(breakdown.get("history_match", 0.0)) < 0.1:
        reasons.append("과거 매칭 부족")
    if float(breakdown.get("pattern_similarity", 0.0)) < 0.1:
        reasons.append("패턴 유사도 낮음")
    if float(breakdown.get("causal_strength", 0.0)) < 0.1:
        reasons.append("인과 사슬 약함")

    return "; ".join(reasons) if reasons else "전반적 신뢰도 부족"


# ═══════════════════════════════════════════════════════════════
#  CAUSAL REASONER — 인과관계 기반 RCA 에이전트
# ═══════════════════════════════════════════════════════════════

class CausalReasoner:
    """인과관계 그래프 기반 근본 원인 추론 에이전트.

    기존 RootCauseAnalyzer(경로 거리 기반)를 보완하여,
    인과관계 체인을 역추적해 진짜 근본 원인을 찾는다.

    학술 근거:
      - CausalTrace (2025): neurosymbolic 인과 분석
      - Causal AI for RCA (Databricks, 2025): 인과 AI > 상관관계
    """

    def __init__(self):
        self.chain_cache = {}  # (step_id, sensor_type) → FailureChain ID

    def analyze(self, conn, anomaly: dict, basic_diagnosis: dict) -> dict:
        """인과관계 체인을 역추적하여 근본 원인을 진단한다.

        Args:
            conn: Kuzu connection
            anomaly: AnomalyDetector의 출력
            basic_diagnosis: RootCauseAnalyzer의 기본 진단 결과

        Returns:
            강화된 진단 결과 (근본 원인 + 인과 체인 + 신뢰도)
        """
        step_id = anomaly.get("step_id", "")
        sensor_type = anomaly.get("sensor_type", "")
        anomaly_type = anomaly.get("anomaly_type", "threshold_breach")
        pattern_ctx = self._resolve_anomaly_pattern(conn, sensor_type, anomaly_type)
        pattern_type = pattern_ctx.get("pattern_type", "")

        # 1. 센서 유형 → 관련 인과관계 매핑
        related_causes = SENSOR_TO_CAUSES.get(sensor_type, [])

        # 2. 인과관계 체인 역추적
        causal_chains = []
        for cause_type in related_causes:
            chain = self._trace_causal_chain(conn, cause_type)
            if chain:
                causal_chains.append(chain)

        # 3. FailureChain 패턴 매칭 (과거 동일 장애)
        matched_chain = self._match_failure_chain(conn, step_id, sensor_type, anomaly_type)

        # 4. 기본 진단 후보에 인과관계 신뢰도 보강
        enhanced_candidates = []
        basic_candidates = basic_diagnosis.get("candidates", [])

        for candidate in basic_candidates:
            cause_type = candidate.get("cause_type", "")
            base_confidence = candidate.get("confidence", 0.5)

            # 논문/비전 기준 RCA 점수:
            # final = base + w_causal*chain_strength + w_history*success_rate + w_pattern*pattern_link
            causal_score, causal_evidence = self._causal_chain_score(causal_chains, cause_type)
            history_score = self._history_match_score(matched_chain, cause_type)
            pattern_score, pattern_evidence = self._pattern_link_score(
                conn, cause_type, pattern_type, sensor_type
            )

            final_confidence = min(
                0.98,
                max(
                    0.05,
                    (base_confidence * 0.55)
                    + (causal_score * 0.25)
                    + (history_score * 0.20)
                    + (pattern_score * 0.12),
                ),
            )
            evidence_refs = []
            if matched_chain:
                evidence_refs.append(f"FailureChain:{matched_chain.get('id')}")
            if pattern_ctx.get("id"):
                evidence_refs.append(f"AnomalyPattern:{pattern_ctx.get('id')}")
            if causal_evidence:
                evidence_refs.append("CausalChain:trace")
            if pattern_evidence:
                evidence_refs.append("PatternLink:HAS_PATTERN")

            enhanced_candidates.append({
                **candidate,
                "confidence": round(final_confidence, 3),
                "causal_chain": causal_evidence or None,
                "causal_boost": round(causal_score * 0.25, 3),
                "history_boost": round(history_score * 0.20, 3),
                "pattern_boost": round(pattern_score * 0.12, 3),
                "root_cause_depth": len(causal_evidence.split(" → ")) if causal_evidence else 0,
                "rca_score_breakdown": {
                    "base": round(base_confidence, 3),
                    "causal_strength": round(causal_score, 3),
                    "history_match": round(history_score, 3),
                    "pattern_similarity": round(pattern_score, 3),
                },
                "pattern_type": pattern_type or None,
                "evidence_refs": evidence_refs[:6],
                "pattern_evidence": pattern_evidence or None,
            })

        # 인과관계에서만 발견된 새로운 후보 추가
        for chain in causal_chains:
            root = chain[0]
            existing_types = {c["cause_type"] for c in enhanced_candidates}
            if root["cause_type"] not in existing_types:
                enhanced_candidates.append({
                    "cause_type": root["cause_type"],
                    "cause_id": f"CAUSAL-{root['cause_type']}",
                    "cause_name": f"인과 추론: {root['name']}",
                    "confidence": round(min(0.9, self._chain_strength(chain) * 0.72 + 0.18), 3),
                    "evidence": f"인과 체인: {' → '.join(s['name'] for s in chain)}",
                    "suggested_action": f"근본 원인({root['name']}) 해결",
                    "causal_chain": " → ".join(s["name"] for s in chain),
                    "causal_boost": round(self._chain_strength(chain) * 0.15, 3),
                    "history_boost": 0.0,
                    "pattern_boost": 0.0,
                    "root_cause_depth": len(chain),
                    "pattern_type": pattern_type or None,
                    "evidence_refs": [f"AnomalyPattern:{pattern_ctx.get('id')}"] if pattern_ctx.get("id") else [],
                })

        enhanced_candidates.sort(key=lambda x: -x["confidence"])

        # Explainable RCA — 배제된 후보 + 배제 근거 (운영자 신뢰 + HITL 검토 보조).
        # 선택된 top-5 외 다음 top-5 까지를 *왜 배제됐는지* 근거와 함께 노출.
        selected = enhanced_candidates[:5]
        excluded_pool = enhanced_candidates[5:10]
        top_candidate = selected[0] if selected else None
        excluded_candidates = [
            {
                "cause_type": c.get("cause_type"),
                "cause_name": c.get("cause_name", ""),
                "confidence": c.get("confidence"),
                "rca_score_breakdown": c.get("rca_score_breakdown"),
                "exclusion_reason": _explain_exclusion(c, top_candidate),
            }
            for c in excluded_pool
        ]

        return {
            "step_id": step_id,
            "candidates": selected,
            "excluded_candidates": excluded_candidates,
            "causal_chains_found": len(causal_chains),
            "failure_chain_matched": matched_chain is not None,
            "matched_chain_id": matched_chain.get("id") if matched_chain else None,
            "matched_pattern_id": pattern_ctx.get("id"),
            "matched_pattern_type": pattern_type or None,
            "analysis_method": "causal_reasoning",
        }

    def learn_from_recovery(self, conn, step_id, sensor_type, anomaly_type,
                            confirmed_cause, recovery_success, recovery_time_sec, counters):
        """복구 결과로부터 인과관계를 학습한다."""
        # 1. CausalRule 확인 횟수 증가
        for rule in SEED_CAUSAL_RULES:
            if rule["cause"] == confirmed_cause or rule["effect"] == confirmed_cause:
                try:
                    conn.execute(
                        "MATCH (cr:CausalRule) WHERE cr.id=$id "
                        "SET cr.confirmation_count = cr.confirmation_count + 1, "
                        "cr.last_confirmed = $ts",
                        {"id": rule["id"], "ts": datetime.now().isoformat()})
                except Exception:
                    pass

        # 2. FailureChain 업데이트 또는 생성
        chain_key = f"FC-{step_id}-{sensor_type}-{anomaly_type}"
        try:
            r = conn.execute("MATCH (fc:FailureChain) WHERE fc.id=$id RETURN fc.success_count, fc.fail_count",
                             {"id": chain_key})
            if r.has_next():
                row = r.get_next()
                if recovery_success:
                    conn.execute(
                        "MATCH (fc:FailureChain) WHERE fc.id=$id "
                        "SET fc.success_count = fc.success_count + 1, "
                        "fc.avg_recovery_sec = (fc.avg_recovery_sec * fc.success_count + $sec) / (fc.success_count + 1)",
                        {"id": chain_key, "sec": recovery_time_sec})
                else:
                    conn.execute(
                        "MATCH (fc:FailureChain) WHERE fc.id=$id SET fc.fail_count = fc.fail_count + 1",
                        {"id": chain_key})
            else:
                conn.execute(
                    "CREATE (fc:FailureChain {id:$id, step_id:$step, pattern_id:$pat, "
                    "cause_sequence:$cause, resolution:$res, "
                    "success_count:$sc, fail_count:$fc, avg_recovery_sec:$sec})",
                    {"id": chain_key, "step": step_id,
                     "pat": anomaly_type, "cause": confirmed_cause,
                     "res": "auto_recovery" if recovery_success else "escalated",
                     "sc": 1 if recovery_success else 0,
                     "fc": 0 if recovery_success else 1,
                     "sec": recovery_time_sec})
        except Exception:
            pass

        # 3. FailureChain -> CausalRule 연결(그래프 이력 추적 강화)
        if confirmed_cause:
            try:
                conn.execute(
                    "MATCH (fc:FailureChain), (cr:CausalRule) "
                    "WHERE fc.id=$cid AND (cr.cause_type=$cause OR cr.effect_type=$cause) "
                    "AND NOT (fc)-[:CHAIN_USES]->(cr) "
                    "CREATE (fc)-[:CHAIN_USES]->(cr)",
                    {"cid": chain_key, "cause": confirmed_cause},
                )
            except Exception:
                pass

        self.chain_cache[(step_id, sensor_type)] = chain_key

    def replay_calibration(self, conn) -> dict:
        """FailureChain 성공/실패 이력을 재생해 CausalRule strength를 보정한다.

        High success_rate causes get boosted, low success_rate causes get dampened.
        Uses a Bayesian-style update: strength = old * (1 - lr) + target * lr
        where target depends on success_rate and trial count (more trials = more weight).
        """
        updates = 0
        scanned = 0
        # Aggregate success/fail across all chains per cause_type
        cause_stats: dict[str, dict] = {}
        try:
            r = conn.execute(
                "MATCH (fc:FailureChain) "
                "RETURN fc.cause_sequence, fc.success_count, fc.fail_count"
            )
            while r.has_next():
                row = r.get_next()
                cause = row[0]
                succ = int(row[1]) if row[1] is not None else 0
                fail = int(row[2]) if row[2] is not None else 0
                if not cause:
                    continue
                if cause not in cause_stats:
                    cause_stats[cause] = {"succ": 0, "fail": 0}
                cause_stats[cause]["succ"] += succ
                cause_stats[cause]["fail"] += fail
        except Exception:
            pass

        for cause, stats in cause_stats.items():
            succ = stats["succ"]
            fail = stats["fail"]
            trials = succ + fail
            if trials < 1:
                continue
            scanned += 1
            success_rate = succ / max(trials, 1)

            # Learning rate increases with more trials (more evidence = stronger update)
            lr = min(0.5, 0.15 + trials * 0.03)

            # Target strength: high success -> boost toward 0.9, low success -> dampen toward 0.3
            target = 0.3 + success_rate * 0.65  # range [0.3, 0.95]

            try:
                rr = conn.execute(
                    "MATCH (cr:CausalRule) "
                    "WHERE cr.cause_type=$cause OR cr.effect_type=$cause "
                    "RETURN cr.id, cr.strength",
                    {"cause": cause},
                )
                while rr.has_next():
                    cr = rr.get_next()
                    rule_id = cr[0]
                    old_strength = float(cr[1]) if cr[1] is not None else 0.5
                    new_strength = max(0.15, min(0.98, old_strength * (1 - lr) + target * lr))
                    conn.execute(
                        "MATCH (cr:CausalRule) WHERE cr.id=$id "
                        "SET cr.strength=$s, cr.last_confirmed=$ts",
                        {"id": rule_id, "s": round(new_strength, 3), "ts": datetime.now().isoformat()},
                    )
                    updates += 1
            except Exception:
                pass
        return {"scanned_chains": scanned, "updated_rules": updates}

    # ── Internal ──

    def _trace_causal_chain(self, conn, cause_type: str) -> list:
        """인과관계 체인을 추적한다. DB의 CAUSES 관계를 우선 사용한다."""
        chain = []
        visited = set()
        current = cause_type

        for _ in range(5):  # 최대 5단계 깊이
            if current in visited:
                break
            visited.add(current)

            graph_step = self._next_chain_step_from_graph(conn, current)
            if not graph_step:
                graph_step = self._next_chain_step_from_seed(current)
            if not graph_step:
                break

            chain.append(graph_step)
            current = graph_step["effect_type"]

        return chain

    @staticmethod
    def _next_chain_step_from_seed(cause_type: str) -> dict | None:
        """DB 쿼리가 어려울 때를 대비한 시드 기반 폴백."""
        matched_rule = None
        for rule in SEED_CAUSAL_RULES:
            if rule["cause"] == cause_type:
                matched_rule = rule
                break
        if not matched_rule:
            return None
        return {
            "rule_id": matched_rule["id"],
            "cause_type": matched_rule["cause"],
            "effect_type": matched_rule["effect"],
            "name": matched_rule["name"],
            "strength": matched_rule["strength"],
            "source": "seed_fallback",
        }

    @staticmethod
    def _next_chain_step_from_graph(conn, cause_type: str) -> dict | None:
        """CAUSES 관계를 따라 다음 인과 단계를 조회한다."""
        try:
            r = conn.execute(
                "MATCH (src:CausalRule)-[rel:CAUSES]->(dst:CausalRule) "
                "WHERE src.cause_type=$cause "
                "RETURN src.id, src.name, src.cause_type, src.effect_type, "
                "src.strength, src.confirmation_count, rel.strength, dst.cause_type "
                "ORDER BY src.confirmation_count DESC, rel.strength DESC "
                "LIMIT 1",
                {"cause": cause_type},
            )
            if r.has_next():
                row = r.get_next()
                src_strength = float(row[4]) if row[4] is not None else 0.5
                confirmations = int(row[5]) if row[5] is not None else 0
                rel_strength = float(row[6]) if row[6] is not None else 0.5
                learned_boost = min(0.2, confirmations * 0.01)
                step_strength = min(0.98, (src_strength * 0.7 + rel_strength * 0.3) + learned_boost)
                return {
                    "rule_id": row[0],
                    "name": row[1],
                    "cause_type": row[2],
                    "effect_type": row[3],
                    "strength": round(step_strength, 3),
                    "source": "graph",
                }
        except Exception:
            pass
        return None

    def _match_failure_chain(self, conn, step_id, sensor_type, anomaly_type) -> dict | None:
        """과거 FailureChain에서 동일 패턴을 매칭한다."""
        chain_key = f"FC-{step_id}-{sensor_type}-{anomaly_type}"
        try:
            r = conn.execute(
                "MATCH (fc:FailureChain) WHERE fc.id=$id "
                "RETURN fc.id, fc.cause_sequence, fc.resolution, fc.success_count, fc.fail_count, fc.avg_recovery_sec",
                {"id": chain_key})
            if r.has_next():
                row = r.get_next()
                return {
                    "id": row[0], "root_cause_type": row[1], "resolution": row[2],
                    "success_count": int(row[3]), "fail_count": int(row[4]),
                    "avg_recovery_sec": float(row[5]),
                }
        except Exception:
            pass

        # exact key가 없으면 step + anomaly 단위로 가장 성공률 높은 체인을 사용
        try:
            r = conn.execute(
                "MATCH (fc:FailureChain) "
                "WHERE fc.step_id=$step AND fc.pattern_id=$pat "
                "RETURN fc.id, fc.cause_sequence, fc.resolution, "
                "fc.success_count, fc.fail_count, fc.avg_recovery_sec "
                "ORDER BY fc.success_count DESC, fc.fail_count ASC "
                "LIMIT 1",
                {"step": step_id, "pat": anomaly_type},
            )
            if r.has_next():
                row = r.get_next()
                return {
                    "id": row[0], "root_cause_type": row[1], "resolution": row[2],
                    "success_count": int(row[3]), "fail_count": int(row[4]),
                    "avg_recovery_sec": float(row[5]),
                }
        except Exception:
            pass
        # 마지막 폴백: step 단위에서 성공률 상위 체인
        try:
            r = conn.execute(
                "MATCH (fc:FailureChain) "
                "WHERE fc.step_id=$step "
                "RETURN fc.id, fc.cause_sequence, fc.resolution, "
                "fc.success_count, fc.fail_count, fc.avg_recovery_sec "
                "ORDER BY fc.success_count DESC, fc.fail_count ASC "
                "LIMIT 1",
                {"step": step_id},
            )
            if r.has_next():
                row = r.get_next()
                return {
                    "id": row[0], "root_cause_type": row[1], "resolution": row[2],
                    "success_count": int(row[3]), "fail_count": int(row[4]),
                    "avg_recovery_sec": float(row[5]),
                }
        except Exception:
            pass
        return None

    @staticmethod
    def _chain_strength(chain: list) -> float:
        """인과관계 체인의 총 강도를 계산한다 (각 단계 강도의 곱)."""
        if not chain:
            return 0.0
        strength = 1.0
        for step in chain:
            strength *= step.get("strength", 0.5)
        return round(strength, 4)

    @staticmethod
    def _causal_chain_score(causal_chains: list, cause_type: str) -> tuple[float, str]:
        """원인 후보가 인과 체인에 얼마나 강하게 지지되는지 계산."""
        best_score = 0.0
        best_chain = ""
        for chain in causal_chains:
            chain_causes = [step.get("cause_type") for step in chain]
            chain_effects = [step.get("effect_type") for step in chain]
            if cause_type in chain_causes or cause_type in chain_effects:
                score = CausalReasoner._chain_strength(chain)
                if score > best_score:
                    best_score = score
                    best_chain = " → ".join(step.get("name", "") for step in chain)
        return min(0.98, best_score), best_chain

    @staticmethod
    def _history_match_score(matched_chain: dict | None, cause_type: str) -> float:
        """FailureChain 매칭 성공률 기반 점수."""
        if not matched_chain:
            return 0.0
        succ = int(matched_chain.get("success_count", 0) or 0)
        fail = int(matched_chain.get("fail_count", 0) or 0)
        trials = max(1, succ + fail)
        success_rate = succ / trials
        root = str(matched_chain.get("root_cause_type", "") or "")
        if root == cause_type:
            return min(0.98, success_rate)
        if root and cause_type in root:
            return min(0.85, success_rate * 0.75)
        return min(0.55, success_rate * 0.45)

    def _resolve_anomaly_pattern(self, conn, sensor_type: str, anomaly_type: str) -> dict:
        """이상 유형과 센서에 맞는 AnomalyPattern을 찾는다."""
        pattern_type = ANOMALY_TO_PATTERN.get(anomaly_type, "spike")
        try:
            r = conn.execute(
                "MATCH (ap:AnomalyPattern) "
                "WHERE ap.pattern_type=$ptype AND (ap.sensor_type='' OR ap.sensor_type=$stype) "
                "RETURN ap.id, ap.pattern_type, ap.sensor_type, ap.occurrence_count "
                "ORDER BY ap.occurrence_count DESC "
                "LIMIT 1",
                {"ptype": pattern_type, "stype": sensor_type},
            )
            if r.has_next():
                row = r.get_next()
                return {
                    "id": row[0],
                    "pattern_type": row[1],
                    "sensor_type": row[2] or sensor_type,
                    "occurrence_count": int(row[3]) if row[3] is not None else 0,
                }
        except Exception:
            pass
        return {"id": None, "pattern_type": pattern_type, "sensor_type": sensor_type, "occurrence_count": 0}

    def _pattern_link_score(self, conn, cause_type: str, pattern_type: str, sensor_type: str) -> tuple[float, str]:
        """원인-패턴 연결 강도(HAS_PATTERN)를 점수화."""
        if not pattern_type:
            return 0.0, ""
        try:
            r = conn.execute(
                "MATCH (cr:CausalRule)-[:HAS_PATTERN]->(ap:AnomalyPattern) "
                "WHERE (cr.cause_type=$cause OR cr.effect_type=$cause) "
                "AND ap.pattern_type=$ptype "
                "AND (ap.sensor_type='' OR ap.sensor_type=$stype) "
                "RETURN count(ap), max(cr.confirmation_count), max(cr.strength)",
                {"cause": cause_type, "ptype": pattern_type, "stype": sensor_type},
            )
            if r.has_next():
                row = r.get_next()
                links = int(row[0]) if row[0] is not None else 0
                confirmations = int(row[1]) if row[1] is not None else 0
                strength = float(row[2]) if row[2] is not None else 0.5
                if links <= 0:
                    return 0.0, ""
                score = min(0.98, strength * 0.7 + min(0.28, confirmations * 0.01))
                return score, f"HAS_PATTERN links={links}, conf={confirmations}, str={strength:.2f}"
        except Exception:
            pass
        return 0.0, ""
