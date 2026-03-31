#!/usr/bin/env python3
"""
Research Improvement Loop — 연구→개선→테스트→검증 자동 사이클
=============================================================
비전(VISION.md)의 GAP 분석을 기반으로, 시스템을 자동으로 개선하는 루프.

각 반복마다:
  ① RESEARCH  — 현재 시스템을 분석하고 개선점을 식별
  ② IMPROVE   — 식별된 개선점을 코드/데이터로 적용
  ③ TEST      — 자율 복구 시뮬레이션 5회 실행
  ④ VERIFY    — 결과 메트릭을 이전과 비교
  ⑤ REPORT    — 개선 결과를 기록

사용법:
  python src/v4/research_loop.py
"""
import sys
import os
import json
import time
import math
import copy
import random
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import kuzu
from v3.skills import create_skill_registry
from v3.agents import create_agents, Moderator, Proposal
from v4.sensor_simulator import SensorSimulator, extend_schema_l2, store_readings, store_alarm
from v4.healing_agents import AnomalyDetector, RootCauseAnalyzer, AutoRecoveryAgent
from v4.causal import extend_schema_l3, seed_causal_knowledge, CausalReasoner
from v4.correlation import extend_schema_correlation, CorrelationAnalyzer, CrossProcessInvestigator
from v4.scenarios import ScenarioEngine


# ═══════════════════════════════════════════════════════════════
#  METRICS COLLECTOR
# ═══════════════════════════════════════════════════════════════

class MetricsCollector:
    """시뮬레이션 결과를 수집하고 비교한다."""

    def __init__(self):
        self.rounds = []

    def collect(self, label, incidents, auto_recovered, scenarios_run,
                causal_rules, failure_chains, correlations,
                avg_confidence, avg_recovery_time, yield_before, yield_after,
                false_positive_rate, missed_anomalies, details=None):
        self.rounds.append({
            "label": label,
            "timestamp": datetime.now().isoformat(),
            "incidents": incidents,
            "auto_recovered": auto_recovered,
            "recovery_rate": round(auto_recovered / max(incidents, 1), 3),
            "scenarios_run": scenarios_run,
            "causal_rules": causal_rules,
            "failure_chains": failure_chains,
            "correlations": correlations,
            "avg_confidence": round(avg_confidence, 3),
            "avg_recovery_time": round(avg_recovery_time, 3),
            "yield_before": round(yield_before, 5),
            "yield_after": round(yield_after, 5),
            "yield_improvement": round((yield_after - yield_before) * 100, 3),
            "false_positive_rate": round(false_positive_rate, 3),
            "missed_anomalies": missed_anomalies,
            "details": details or {},
        })

    def compare(self, round_a, round_b):
        a = self.rounds[round_a]
        b = self.rounds[round_b]
        improvements = {}
        for key in ["recovery_rate", "avg_confidence", "yield_improvement", "false_positive_rate"]:
            va, vb = a.get(key, 0), b.get(key, 0)
            if key == "false_positive_rate":
                improvements[key] = {"before": va, "after": vb, "improved": vb < va}
            else:
                improvements[key] = {"before": va, "after": vb, "improved": vb > va}
        return improvements

    def summary(self):
        if len(self.rounds) < 2:
            return "데이터 부족"
        first = self.rounds[0]
        last = self.rounds[-1]
        return {
            "total_rounds": len(self.rounds),
            "recovery_rate": f"{first['recovery_rate']:.0%} → {last['recovery_rate']:.0%}",
            "avg_confidence": f"{first['avg_confidence']:.3f} → {last['avg_confidence']:.3f}",
            "yield_improvement": f"{first['yield_improvement']:.3f}%p → {last['yield_improvement']:.3f}%p",
            "failure_chains": f"{first['failure_chains']} → {last['failure_chains']}",
            "correlations": f"{first['correlations']} → {last['correlations']}",
        }


# ═══════════════════════════════════════════════════════════════
#  IMPROVEMENT STRATEGIES
# ═══════════════════════════════════════════════════════════════

def strategy_tune_anomaly_thresholds(detector: AnomalyDetector, metrics_history: list):
    """전략 1: 오탐률 기반 이상 감지 임계값 조정."""
    if not metrics_history:
        return "데이터 없음"
    last = metrics_history[-1]
    fpr = last.get("false_positive_rate", 0)
    if fpr > 0.3:
        detector.window_size = min(30, detector.window_size + 2)
        return f"윈도우 크기 증가: {detector.window_size - 2} → {detector.window_size} (오탐률 {fpr:.0%} 감소 목표)"
    elif fpr < 0.1 and detector.window_size > 12:
        detector.window_size = max(10, detector.window_size - 1)
        return f"윈도우 크기 감소: {detector.window_size + 1} → {detector.window_size} (감도 향상)"
    return "임계값 유지 (적정 범위)"


def strategy_add_causal_rules(conn, causal_reasoner: CausalReasoner, metrics_history: list):
    """전략 2: 학습된 장애 패턴에서 새로운 인과관계 규칙을 도출."""
    added = 0
    try:
        # FailureChain에서 반복되는 원인을 CausalRule로 승격
        r = conn.execute(
            "MATCH (fc:FailureChain) WHERE fc.success_count >= 2 "
            "RETURN fc.id, fc.cause_sequence, fc.step_id, fc.success_count"
        )
        while r.has_next():
            row = r.get_next()
            fc_id, cause, step_id, count = row[0], row[1], row[2], int(row[3])
            # 해당 원인의 CausalRule이 이미 있는지 확인
            new_id = f"CR-AUTO-{step_id}-{cause}"
            try:
                r2 = conn.execute("MATCH (cr:CausalRule) WHERE cr.id=$id RETURN count(cr)", {"id": new_id})
                if r2.get_next()[0] == 0:
                    conn.execute(
                        "CREATE (cr:CausalRule {id:$id, name:$name, cause_type:$cause, "
                        "effect_type:'yield_drop', strength:$str, confirmation_count:$cnt, "
                        "last_confirmed:$ts})",
                        {"id": new_id, "name": f"학습된 규칙: {cause}→수율하락 ({step_id})",
                         "cause": cause, "str": min(0.9, 0.5 + count * 0.1),
                         "cnt": count, "ts": datetime.now().isoformat()})
                    added += 1
            except Exception:
                pass
    except Exception:
        pass
    return f"새 인과규칙 {added}개 추가" if added else "추가할 규칙 없음"


def strategy_expand_correlation_coverage(corr_analyzer: CorrelationAnalyzer, metrics_history: list):
    """전략 3: 상관분석 임계값/윈도우 조정으로 더 많은 상관관계 발견."""
    old_threshold = corr_analyzer.threshold
    old_min = corr_analyzer.min_samples
    # 상관관계가 적으면 임계값 낮추기
    if metrics_history and metrics_history[-1].get("correlations", 0) < 10:
        corr_analyzer.threshold = max(0.4, corr_analyzer.threshold - 0.05)
        return f"상관 임계값 하향: {old_threshold:.2f} → {corr_analyzer.threshold:.2f}"
    elif metrics_history and metrics_history[-1].get("correlations", 0) > 80:
        corr_analyzer.threshold = min(0.8, corr_analyzer.threshold + 0.05)
        return f"상관 임계값 상향: {old_threshold:.2f} → {corr_analyzer.threshold:.2f} (노이즈 감소)"
    return "상관분석 설정 유지"


def strategy_optimize_recovery_playbook(auto_recovery: AutoRecoveryAgent, metrics_history: list):
    """전략 4: 복구 성공률 기반 플레이북 우선순위 조정."""
    if not hasattr(auto_recovery, 'success_history'):
        return "학습 이력 없음"
    adjustments = []
    for (action, cause), stats in auto_recovery.success_history.items():
        total = stats.get("attempts", 0)
        success = stats.get("successes", 0)
        if total >= 3 and success / total < 0.5:
            adjustments.append(f"{action}/{cause}: 성공률 {success}/{total} — 대체 전략 필요")
    return f"플레이북 조정 {len(adjustments)}건" if adjustments else "플레이북 최적"


def strategy_enrich_scenarios(scenario_engine: ScenarioEngine, round_num: int):
    """전략 5: 라운드별로 새로운 시나리오 변형을 추가."""
    # 기존 시나리오의 severity를 점진적으로 높여 더 어려운 테스트
    lib = scenario_engine.get_scenario_library()
    for scn in lib:
        for step in scn.get("affected_steps", []):
            if round_num >= 5:
                step["severity"] = min(3, step.get("severity", 1) + 1)
    return f"시나리오 난이도 조정 (라운드 {round_num})"


def strategy_calibrate_causal_strength(conn, causal_reasoner: CausalReasoner):
    """전략 6: FailureChain 이력으로 CausalRule strength 재보정."""
    result = causal_reasoner.replay_calibration(conn)
    return f"인과규칙 재보정: {result.get('updates', 0)}개 업데이트"


# ═══════════════════════════════════════════════════════════════
#  SIMULATION RUNNER
# ═══════════════════════════════════════════════════════════════

def run_simulation(conn, sensor_sim, anomaly_detector, rca, auto_recovery,
                   causal_reasoner, corr_analyzer, cross_investigator,
                   scenario_engine, skill_registry, healing_counters,
                   num_iterations=5):
    """자율 복구 시뮬레이션을 N회 실행하고 결과를 반환한다."""
    incidents = []
    total_anomalies = 0
    total_false_positives = 0
    total_missed = 0
    scenarios_activated = 0

    # 초기 수율 측정
    gm = skill_registry.execute("graph_metrics", conn, {}, "system")
    yield_before = gm["metrics"]["line_yield"]

    for it in range(num_iterations):
        # 시나리오 주입
        scenario_engine.tick()
        if it % 2 == 0 and not scenario_engine.get_active_scenarios():
            activated = scenario_engine.activate_random()
            if activated:
                scenarios_activated += 1

        # SENSE
        readings = sensor_sim.generate_readings()
        store_readings(conn, readings, healing_counters)
        corr_analyzer.ingest(readings)

        # DETECT
        anomaly_detector.update(readings)
        detected = anomaly_detector.detect(readings)
        alarms = sensor_sim.check_alarms(readings)
        for alarm in alarms:
            store_alarm(conn, alarm, healing_counters)

        # 오탐 추정 (시나리오에 의한 것이 아닌 감지)
        active_scn = scenario_engine.get_active_scenarios()
        scenario_steps = set()
        for scn in active_scn:
            for step in scn.get("affected_steps", []):
                scenario_steps.add(step.get("step_id", ""))

        for d in detected:
            if d.get("step_id") not in scenario_steps and not d.get("is_anomaly"):
                total_false_positives += 1
        total_anomalies += len(detected)

        if not detected:
            continue

        # DIAGNOSE
        for anomaly in detected:
            try:
                basic_diag = rca.analyze(conn, anomaly)
                causal_diag = causal_reasoner.analyze(conn, anomaly, basic_diag)

                # RECOVER
                actions = auto_recovery.plan_recovery(conn, causal_diag, anomaly)
                if actions:
                    best = actions[0]
                    result = auto_recovery.execute_recovery(conn, best, healing_counters)
                    success = result.get("success", False)

                    # LEARN
                    top_cause = causal_diag["candidates"][0]["cause_type"] if causal_diag.get("candidates") else "unknown"
                    causal_reasoner.learn_from_recovery(
                        conn, anomaly.get("step_id", ""),
                        anomaly.get("sensor_type", ""),
                        anomaly.get("anomaly_type", ""),
                        top_cause, success, 0.5, healing_counters)

                    incidents.append({
                        "step_id": anomaly.get("step_id"),
                        "cause": top_cause,
                        "confidence": causal_diag["candidates"][0]["confidence"] if causal_diag.get("candidates") else 0,
                        "action": best.get("action_type", ""),
                        "success": success,
                        "causal_chains": causal_diag.get("causal_chains_found", 0),
                        "history_matched": causal_diag.get("failure_chain_matched", False),
                    })
            except Exception:
                pass

        # 상관분석 (2회마다)
        if it % 2 == 0:
            corr_analyzer.analyze_all()

    # 최종 수율 측정
    gm = skill_registry.execute("graph_metrics", conn, {}, "system")
    yield_after = gm["metrics"]["line_yield"]

    # FailureChain, CausalRule 수 세기
    causal_count, fc_count, corr_count = 0, 0, 0
    try:
        r = conn.execute("MATCH (cr:CausalRule) RETURN count(cr)")
        causal_count = r.get_next()[0]
    except Exception:
        pass
    try:
        r = conn.execute("MATCH (fc:FailureChain) RETURN count(fc)")
        fc_count = r.get_next()[0]
    except Exception:
        pass
    corr_count = len(corr_analyzer.known_correlations)

    auto_recovered = sum(1 for i in incidents if i["success"])
    avg_conf = sum(i["confidence"] for i in incidents) / max(len(incidents), 1)
    fpr = total_false_positives / max(total_anomalies, 1)

    return {
        "incidents": len(incidents),
        "auto_recovered": auto_recovered,
        "scenarios_run": scenarios_activated,
        "causal_rules": causal_count,
        "failure_chains": fc_count,
        "correlations": corr_count,
        "avg_confidence": avg_conf,
        "avg_recovery_time": 0.5,
        "yield_before": yield_before,
        "yield_after": yield_after,
        "false_positive_rate": fpr,
        "missed_anomalies": total_missed,
        "incident_details": incidents,
    }


# ═══════════════════════════════════════════════════════════════
#  DB SETUP (reuse from engine)
# ═══════════════════════════════════════════════════════════════

def setup_db(db_path, data_path):
    """DB를 초기화하고 모든 스키마를 생성한다."""
    import shutil
    for p in [db_path, db_path + ".wal", db_path + ".lock"]:
        if os.path.exists(p):
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # L1 스키마
    conn.execute("CREATE NODE TABLE ProcessArea (id STRING, name STRING, color STRING, cycle_time INT64, step_count INT64, takt_time DOUBLE DEFAULT 0.0, PRIMARY KEY(id))")
    conn.execute("CREATE NODE TABLE ProcessStep (id STRING, name STRING, area_id STRING, cycle_time INT64, yield_rate DOUBLE, automation STRING, equipment STRING, equip_cost INT64, operators INT64, safety_level STRING, oee DOUBLE DEFAULT 0.85, sigma_level DOUBLE DEFAULT 3.0, PRIMARY KEY(id))")
    conn.execute("CREATE NODE TABLE Equipment (id STRING, name STRING, cost INT64, mtbf_hours DOUBLE DEFAULT 2000.0, mttr_hours DOUBLE DEFAULT 4.0, PRIMARY KEY(id))")
    conn.execute("CREATE NODE TABLE Material (id STRING, name STRING, category STRING, cost DOUBLE, supplier STRING, lead_time_days INT64 DEFAULT 7, PRIMARY KEY(id))")
    conn.execute("CREATE NODE TABLE QualitySpec (id STRING, name STRING, type STRING, unit STRING, min_val DOUBLE, max_val DOUBLE, PRIMARY KEY(id))")
    conn.execute("CREATE NODE TABLE DefectMode (id STRING, name STRING, category STRING, severity INT64, occurrence INT64, detection INT64, rpn INT64, PRIMARY KEY(id))")
    conn.execute("CREATE NODE TABLE AutomationPlan (id STRING, name STRING, from_level STRING, to_level STRING, investment INT64, expected_yield_gain DOUBLE, expected_cycle_reduction INT64, PRIMARY KEY(id))")
    conn.execute("CREATE NODE TABLE MaintenancePlan (id STRING, name STRING, strategy STRING, interval_hours INT64, cost_per_event INT64, PRIMARY KEY(id))")

    for rel in [
        "CREATE REL TABLE NEXT_STEP (FROM ProcessStep TO ProcessStep)",
        "CREATE REL TABLE FEEDS_INTO (FROM ProcessStep TO ProcessStep)",
        "CREATE REL TABLE PARALLEL_WITH (FROM ProcessStep TO ProcessStep)",
        "CREATE REL TABLE TRIGGERS_REWORK (FROM ProcessStep TO ProcessStep)",
        "CREATE REL TABLE BELONGS_TO (FROM ProcessStep TO ProcessArea)",
        "CREATE REL TABLE USES_EQUIPMENT (FROM ProcessStep TO Equipment)",
        "CREATE REL TABLE CONSUMES (FROM ProcessStep TO Material, qty DOUBLE)",
        "CREATE REL TABLE REQUIRES_SPEC (FROM ProcessStep TO QualitySpec)",
        "CREATE REL TABLE HAS_DEFECT (FROM ProcessStep TO DefectMode)",
        "CREATE REL TABLE PREVENTS (FROM QualitySpec TO DefectMode)",
        "CREATE REL TABLE PLANNED_UPGRADE (FROM ProcessStep TO AutomationPlan)",
        "CREATE REL TABLE HAS_MAINTENANCE (FROM Equipment TO MaintenancePlan)",
        "CREATE REL TABLE DEPENDS_ON (FROM ProcessStep TO ProcessStep, dependency_type STRING)",
        "CREATE REL TABLE INSPECTS (FROM ProcessStep TO ProcessStep)",
    ]:
        conn.execute(rel)

    # 데이터 적재
    with open(data_path) as f:
        raw = json.load(f)

    equip_map = {}
    for a in raw["areas"]:
        conn.execute("CREATE (pa:ProcessArea {id:$id,name:$name,color:$color,cycle_time:$ct,step_count:$sc,takt_time:$tt})",
                     {"id":a["id"],"name":a["name"],"color":a["color"],"ct":a["cycle"],"sc":a["steps"],"tt":round(a["cycle"]/a["steps"],2)})
    for s in raw["steps"]:
        sigma = 3.0 + (s["yield_rate"] - 0.98) * 100
        conn.execute("CREATE (ps:ProcessStep {id:$id,name:$name,area_id:$area,cycle_time:$ct,yield_rate:$yr,automation:$auto,equipment:$eq,equip_cost:$ec,operators:$op,safety_level:$sl,oee:$oee,sigma_level:$sig})",
                     {"id":s["id"],"name":s["name"],"area":s["area"],"ct":s["cycle"],"yr":s["yield_rate"],"auto":s["auto"],"eq":s["equipment"],"ec":s["equip_cost"],"op":s["operators"],"sl":s["safety"],"oee":round(0.75+s["yield_rate"]*0.1,3),"sig":round(sigma,2)})
    for i, s in enumerate(raw["steps"]):
        eid = f"EQ-{i+1:03d}"
        if s["equipment"] not in equip_map:
            equip_map[s["equipment"]] = eid
            conn.execute("CREATE (e:Equipment {id:$id,name:$name,cost:$cost,mtbf_hours:$mtbf,mttr_hours:$mttr})",
                         {"id":eid,"name":s["equipment"],"cost":s["equip_cost"],"mtbf":round(1500+s["equip_cost"]/100),"mttr":round(4+s["equip_cost"]/200000,1)})
    mat_seen = set()
    for m in raw["materials"]:
        if m["mat_id"] not in mat_seen:
            mat_seen.add(m["mat_id"])
            conn.execute("CREATE (m:Material {id:$id,name:$name,category:$cat,cost:$cost,supplier:$sup,lead_time_days:7})",
                         {"id":m["mat_id"],"name":m["mat_name"],"cat":m["category"],"cost":m["cost"],"sup":m["supplier"]})
    qs_seen = set()
    for q in raw["quality"]:
        if q["spec_id"] not in qs_seen:
            qs_seen.add(q["spec_id"])
            conn.execute("CREATE (q:QualitySpec {id:$id,name:$name,type:$type,unit:$unit,min_val:$mn,max_val:$mx})",
                         {"id":q["spec_id"],"name":q["spec_name"],"type":q["type"],"unit":q["unit"],"mn":q["min"],"mx":q["max"]})
    for e in raw["edges"]:
        conn.execute(f"MATCH (a:ProcessStep),(b:ProcessStep) WHERE a.id=$s AND b.id=$t CREATE (a)-[:{e['type']}]->(b)", {"s":e["source"],"t":e["target"]})
    for s in raw["steps"]:
        conn.execute("MATCH (ps:ProcessStep),(pa:ProcessArea) WHERE ps.id=$sid AND pa.id=$aid CREATE (ps)-[:BELONGS_TO]->(pa)", {"sid":s["id"],"aid":s["area"]})
    for s in raw["steps"]:
        eid = equip_map[s["equipment"]]
        conn.execute("MATCH (ps:ProcessStep),(eq:Equipment) WHERE ps.id=$sid AND eq.id=$eid CREATE (ps)-[:USES_EQUIPMENT]->(eq)", {"sid":s["id"],"eid":eid})
    for m in raw["materials"]:
        conn.execute("MATCH (ps:ProcessStep),(mat:Material) WHERE ps.id=$sid AND mat.id=$mid CREATE (ps)-[:CONSUMES {qty:$qty}]->(mat)", {"sid":m["step_id"],"mid":m["mat_id"],"qty":m["qty"]})
    for q in raw["quality"]:
        conn.execute("MATCH (ps:ProcessStep),(qs:QualitySpec) WHERE ps.id=$sid AND qs.id=$qid CREATE (ps)-[:REQUIRES_SPEC]->(qs)", {"sid":q["step_id"],"qid":q["spec_id"]})

    # L2, L3, 상관 스키마
    extend_schema_l2(conn)
    extend_schema_l3(conn)
    seed_causal_knowledge(conn, {})
    extend_schema_correlation(conn)

    return db, conn


# ═══════════════════════════════════════════════════════════════
#  MAIN LOOP
# ═══════════════════════════════════════════════════════════════

def run_research_loop(num_rounds=10, sim_iterations=5):
    """연구→개선→테스트→검증 루프를 N회 반복한다."""
    print("=" * 70)
    print("  Research Improvement Loop")
    print("  연구→개선→테스트→검증 자동 사이클")
    print(f"  라운드: {num_rounds}회, 시뮬레이션: {sim_iterations}회/라운드")
    print("=" * 70)

    db_path = os.path.join(PROJECT_ROOT, "kuzu_research_loop")
    data_path = os.path.join(PROJECT_ROOT, "data", "graph_data.json")

    db, conn = setup_db(db_path, data_path)
    print("  DB 초기화 완료\n")

    # 에이전트 초기화
    skill_registry = create_skill_registry()
    sensor_sim = SensorSimulator(conn)
    anomaly_detector = AnomalyDetector()
    rca = RootCauseAnalyzer()
    auto_recovery = AutoRecoveryAgent()
    causal_reasoner = CausalReasoner()
    corr_analyzer = CorrelationAnalyzer()
    cross_investigator = CrossProcessInvestigator()
    scenario_engine = ScenarioEngine(sensor_sim)
    healing_counters = {"reading": 0, "alarm": 0, "incident": 0, "recovery": 0}

    Proposal._counter = 0
    metrics_collector = MetricsCollector()

    # 전략 목록
    strategies = [
        ("이상감지 임계값 조정", lambda: strategy_tune_anomaly_thresholds(anomaly_detector, metrics_collector.rounds)),
        ("인과규칙 자동 도출", lambda: strategy_add_causal_rules(conn, causal_reasoner, metrics_collector.rounds)),
        ("상관분석 범위 확장", lambda: strategy_expand_correlation_coverage(corr_analyzer, metrics_collector.rounds)),
        ("복구 플레이북 최적화", lambda: strategy_optimize_recovery_playbook(auto_recovery, metrics_collector.rounds)),
        ("시나리오 난이도 조정", lambda: strategy_enrich_scenarios(scenario_engine, 0)),
        ("인과규칙 강도 재보정", lambda: strategy_calibrate_causal_strength(conn, causal_reasoner)),
    ]

    for round_num in range(1, num_rounds + 1):
        print(f"\n{'━' * 70}")
        print(f"  ROUND {round_num}/{num_rounds}")
        print(f"{'━' * 70}")

        # ① RESEARCH — 현재 시스템 분석
        print(f"\n  [①] RESEARCH — 현재 시스템 분석...")
        if metrics_collector.rounds:
            last = metrics_collector.rounds[-1]
            print(f"      이전 라운드: 복구율 {last['recovery_rate']:.0%}, "
                  f"신뢰도 {last['avg_confidence']:.3f}, "
                  f"오탐률 {last['false_positive_rate']:.0%}")
            print(f"      인과규칙: {last['causal_rules']}, "
                  f"장애체인: {last['failure_chains']}, "
                  f"상관관계: {last['correlations']}")
        else:
            print(f"      첫 라운드 — 베이스라인 측정")

        # ② IMPROVE — 개선 전략 적용
        print(f"\n  [②] IMPROVE — 개선 전략 적용...")
        # 라운드별로 다른 전략 조합 적용
        active_strategies = []
        # 매 라운드 기본 전략
        active_strategies.append(strategies[0])  # 임계값 조정
        active_strategies.append(strategies[5])  # 인과규칙 재보정

        # 라운드별 추가 전략
        if round_num % 2 == 0:
            active_strategies.append(strategies[1])  # 인과규칙 도출
        if round_num % 3 == 0:
            active_strategies.append(strategies[2])  # 상관분석 확장
        if round_num >= 3:
            active_strategies.append(strategies[3])  # 플레이북 최적화
        if round_num >= 5:
            strategies[4] = ("시나리오 난이도 조정", lambda r=round_num: strategy_enrich_scenarios(scenario_engine, r))
            active_strategies.append(strategies[4])

        for name, strategy_fn in active_strategies:
            result = strategy_fn()
            print(f"      [{name}] {result}")

        # ③ TEST — 시뮬레이션 실행
        print(f"\n  [③] TEST — 시뮬레이션 {sim_iterations}회 실행...")
        sim_result = run_simulation(
            conn, sensor_sim, anomaly_detector, rca, auto_recovery,
            causal_reasoner, corr_analyzer, cross_investigator,
            scenario_engine, skill_registry, healing_counters,
            num_iterations=sim_iterations,
        )
        print(f"      인시던트: {sim_result['incidents']}, "
              f"자동복구: {sim_result['auto_recovered']}, "
              f"시나리오: {sim_result['scenarios_run']}")
        print(f"      수율: {sim_result['yield_before']*100:.2f}% → {sim_result['yield_after']*100:.2f}%")

        # ④ VERIFY — 결과 검증
        print(f"\n  [④] VERIFY — 결과 검증...")
        metrics_collector.collect(
            label=f"Round {round_num}",
            **{k: sim_result[k] for k in [
                "incidents", "auto_recovered", "scenarios_run",
                "causal_rules", "failure_chains", "correlations",
                "avg_confidence", "avg_recovery_time",
                "yield_before", "yield_after",
                "false_positive_rate", "missed_anomalies",
            ]},
            details={"strategies_applied": [s[0] for s in active_strategies]},
        )

        if len(metrics_collector.rounds) >= 2:
            comparison = metrics_collector.compare(-2, -1)
            for key, comp in comparison.items():
                arrow = "▲" if comp["improved"] else "▼" if comp["before"] != comp["after"] else "─"
                color = "" if not comp["improved"] else ""
                print(f"      {key}: {comp['before']:.3f} → {comp['after']:.3f} {arrow}")
        else:
            print(f"      베이스라인 기록됨")

        # ⑤ REPORT
        print(f"\n  [⑤] REPORT")
        r = metrics_collector.rounds[-1]
        print(f"      복구율: {r['recovery_rate']:.0%}")
        print(f"      평균 신뢰도: {r['avg_confidence']:.3f}")
        print(f"      수율 개선: {r['yield_improvement']:.3f}%p")
        print(f"      인과규칙: {r['causal_rules']}개, 장애체인: {r['failure_chains']}개")
        print(f"      상관관계: {r['correlations']}개")

    # 최종 요약
    print(f"\n{'=' * 70}")
    print(f"  연구 루프 완료 — {num_rounds}회 반복")
    print(f"{'─' * 70}")
    summary = metrics_collector.summary()
    if isinstance(summary, dict):
        for k, v in summary.items():
            print(f"  {k}: {v}")
    print(f"{'=' * 70}")

    # 결과 저장
    output_path = os.path.join(PROJECT_ROOT, "results", "research_loop_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_rounds": num_rounds,
            "sim_iterations_per_round": sim_iterations,
            "rounds": metrics_collector.rounds,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {output_path}")

    # DB 정리
    for p in [db_path, db_path + ".wal", db_path + ".lock"]:
        if os.path.exists(p):
            try:
                if os.path.isdir(p):
                    import shutil
                    shutil.rmtree(p)
                else:
                    os.remove(p)
            except Exception:
                pass

    return metrics_collector


if __name__ == "__main__":
    run_research_loop(num_rounds=10, sim_iterations=5)
