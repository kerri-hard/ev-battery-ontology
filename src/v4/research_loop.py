#!/usr/bin/env python3
"""
Research Improvement Loop — 연구→개선→테스트→검증 자동 사이클
=============================================================
비전(VISION.md)의 GAP 분석을 기반으로, 시스템을 자동으로 개선하는 루프.

각 라운드마다:
  ① RESEARCH  — 현재 시스템 분석
  ② IMPROVE   — 개선 전략 적용 (`v4.research.strategies`)
  ③ TEST      — 자율 복구 시뮬레이션 (`v4.research.simulation.run_simulation`)
  ④ VERIFY    — 메트릭 비교 (`v4.research.metrics.MetricsCollector`)
  ⑤ REPORT    — 결과 기록

사용법:
  python src/v4/research_loop.py
"""
import sys
import os
import json
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from v3.skills import create_skill_registry
from v3.agents import Proposal
from v4.sensor_simulator import SensorSimulator
from v4.healing import AnomalyDetector, RootCauseAnalyzer, AutoRecoveryAgent
from v4.causal import CausalReasoner
from v4.correlation import CorrelationAnalyzer, CrossProcessInvestigator
from v4.scenarios import ScenarioEngine
from v4.causal_discovery import CausalDiscoveryEngine
from v4.evolution_agent import EvolutionAgent
from v4.llm_orchestrator import LLMOrchestrator

from v4.research.metrics import (
    MetricsCollector,
    CONVERGENCE_DELTA,
    CONVERGENCE_WINDOW,
)
from v4.research import strategies
from v4.research.simulation import run_simulation
from v4.research.db_setup import setup_db


CAUSAL_DISCOVERY_EVERY = 2  # 라운드 간격


def run_research_loop(num_rounds: int = 10, sim_iterations: int = 5):
    """연구→개선→테스트→검증 루프를 N회 반복한다."""
    _print_header(num_rounds, sim_iterations)

    db_path = os.path.join(PROJECT_ROOT, "kuzu_research_loop")
    data_path = os.path.join(PROJECT_ROOT, "data", "graph_data.json")
    db, conn = setup_db(db_path, data_path)
    print("  DB 초기화 완료\n")

    ctx = _create_context(conn)

    for round_num in range(1, num_rounds + 1):
        _print_round_header(round_num, num_rounds)
        _research_phase(ctx)
        active_strategies = _improve_phase(ctx, round_num)
        _maybe_run_causal_discovery(ctx, round_num)

        sim_result = _test_phase(ctx, sim_iterations)
        _evolve_phase(ctx, sim_result)

        _verify_phase(ctx, round_num, sim_result, active_strategies)
        _report_phase(ctx)

        if ctx.metrics.has_converged():
            print(
                f"\n  [🏁 CONVERGED] 최근 {CONVERGENCE_WINDOW}라운드 변화폭 "
                f"< {CONVERGENCE_DELTA * 100:.1f}%p — 조기 종료"
            )
            break

    _print_summary(ctx, num_rounds)
    _persist_results(ctx, num_rounds, sim_iterations, db_path)
    _cleanup_db(db_path)
    return ctx.metrics


# ── Context + agent wiring ─────────────────────────────


class _LoopContext:
    """연구 루프의 모든 에이전트/메트릭/카운터를 묶는 단순 컨테이너."""

    def __init__(self, conn):
        self.conn = conn
        self.skill_registry = create_skill_registry()
        self.sensor_sim = SensorSimulator(conn)
        self.anomaly_detector = AnomalyDetector()
        self.rca = RootCauseAnalyzer()
        self.auto_recovery = AutoRecoveryAgent()
        self.causal_reasoner = CausalReasoner()
        self.corr_analyzer = CorrelationAnalyzer()
        self.cross_investigator = CrossProcessInvestigator()
        self.scenario_engine = ScenarioEngine(self.sensor_sim)
        self.healing_counters = {"reading": 0, "alarm": 0, "incident": 0, "recovery": 0}

        self.causal_discovery = CausalDiscoveryEngine()
        self.llm_orchestrator = LLMOrchestrator()
        self.evolution_agent = EvolutionAgent(evolution_interval=1)
        self.evolution_agent.register_strategies(
            conn, self.anomaly_detector, self.causal_reasoner, self.corr_analyzer,
            self.auto_recovery, self.scenario_engine,
            causal_discovery=self.causal_discovery,
        )
        self.metrics = MetricsCollector()


def _create_context(conn) -> _LoopContext:
    Proposal._counter = 0
    ctx = _LoopContext(conn)
    print(
        f"  L4 모듈 통합: CausalDiscovery + LLMOrchestrator({ctx.llm_orchestrator.provider}) "
        "+ EvolutionAgent"
    )
    return ctx


# ── Phases ─────────────────────────────────────────────


def _research_phase(ctx: _LoopContext) -> None:
    print("\n  [①] RESEARCH — 현재 시스템 분석...")
    if ctx.metrics.rounds:
        last = ctx.metrics.rounds[-1]
        print(
            f"      이전 라운드: 복구율 {last['recovery_rate']:.0%}, "
            f"신뢰도 {last['avg_confidence']:.3f}, "
            f"오탐률 {last['false_positive_rate']:.0%}"
        )
        print(
            f"      인과규칙: {last['causal_rules']}, "
            f"장애체인: {last['failure_chains']}, "
            f"상관관계: {last['correlations']}"
        )
    else:
        print("      첫 라운드 — 베이스라인 측정")


def _improve_phase(ctx: _LoopContext, round_num: int) -> list:
    print("\n  [②] IMPROVE — 개선 전략 적용...")
    history = ctx.metrics.rounds
    active = [
        ("이상감지 임계값 조정", lambda: strategies.tune_anomaly_thresholds(ctx.anomaly_detector, history)),
        ("인과규칙 강도 재보정", lambda: strategies.calibrate_causal_strength(ctx.conn, ctx.causal_reasoner)),
    ]
    if round_num % 2 == 0:
        active.append(("인과규칙 자동 도출",
                       lambda: strategies.add_causal_rules(ctx.conn, ctx.causal_reasoner, history)))
    if round_num % 3 == 0:
        active.append(("상관분석 범위 확장",
                       lambda: strategies.expand_correlation_coverage(ctx.corr_analyzer, history)))
    if round_num >= 3:
        active.append(("복구 플레이북 최적화",
                       lambda: strategies.optimize_recovery_playbook(ctx.auto_recovery, history)))
    if round_num >= 5:
        active.append(("시나리오 난이도 조정",
                       lambda: strategies.enrich_scenarios(ctx.scenario_engine, round_num)))

    for name, strategy_fn in active:
        result = strategy_fn()
        print(f"      [{name}] {result}")
    return active


def _maybe_run_causal_discovery(ctx: _LoopContext, round_num: int) -> None:
    if round_num % CAUSAL_DISCOVERY_EVERY != 0 or not ctx.corr_analyzer.known_correlations:
        return
    try:
        cands = ctx.causal_discovery.discover(ctx.corr_analyzer)
        pruned = ctx.causal_discovery.prune_conditional_independence(cands, ctx.corr_analyzer)
        promoted = ctx.causal_discovery.promote_to_ontology(ctx.conn, pruned, ctx.healing_counters)
        print(f"      [자동 인과 발견] 후보 {len(cands)} → 가지치기 {len(pruned)} → 승격 {len(promoted)}")
    except Exception as exc:
        print(f"      [자동 인과 발견] 실패: {exc}")


def _test_phase(ctx: _LoopContext, sim_iterations: int) -> dict:
    print(f"\n  [③] TEST — 시뮬레이션 {sim_iterations}회 실행...")
    sim_result = run_simulation(
        ctx.conn, ctx.sensor_sim, ctx.anomaly_detector, ctx.rca, ctx.auto_recovery,
        ctx.causal_reasoner, ctx.corr_analyzer, ctx.cross_investigator,
        ctx.scenario_engine, ctx.skill_registry, ctx.healing_counters,
        num_iterations=sim_iterations,
    )
    print(
        f"      인시던트: {sim_result['incidents']}, "
        f"자동복구: {sim_result['auto_recovered']}, "
        f"시나리오: {sim_result['scenarios_run']}"
    )
    print(
        f"      수율: {sim_result['yield_before'] * 100:.2f}% → "
        f"{sim_result['yield_after'] * 100:.2f}%"
    )
    return sim_result


def _evolve_phase(ctx: _LoopContext, sim_result: dict) -> None:
    try:
        evo_metrics_before = ctx.metrics.rounds[-1] if ctx.metrics.rounds else {}
        evo_metrics_after = {
            "recovery_rate": sim_result["auto_recovered"] / max(sim_result["incidents"], 1),
            "avg_confidence": sim_result["avg_confidence"],
            "line_yield": sim_result["yield_after"],
            "total_incidents": sim_result["incidents"],
            "auto_recovered": sim_result["auto_recovered"],
            "correlations": sim_result["correlations"],
            "false_positive_rate": sim_result["false_positive_rate"],
        }
        evo_result = ctx.evolution_agent.run_evolution_cycle(
            ctx.conn, evo_metrics_before, evo_metrics_after,
        )
        best = evo_result.get("best_strategy")
        print(
            f"      [EvolutionAgent] cycle {evo_result['cycle']}: "
            f"{evo_result['strategies_improved']}/{evo_result['strategies_run']} 개선, "
            f"overall_fitness={evo_result['overall_fitness']:.3f}, best={best}"
        )
    except Exception as exc:
        print(f"      [EvolutionAgent] 실패: {exc}")


def _verify_phase(ctx: _LoopContext, round_num: int, sim_result: dict, active_strategies: list) -> None:
    print("\n  [④] VERIFY — 결과 검증...")
    ctx.metrics.collect(
        label=f"Round {round_num}",
        **{k: sim_result[k] for k in (
            "incidents", "auto_recovered", "scenarios_run",
            "causal_rules", "failure_chains", "correlations",
            "avg_confidence", "avg_recovery_time",
            "yield_before", "yield_after",
            "false_positive_rate", "missed_anomalies",
        )},
        details={"strategies_applied": [s[0] for s in active_strategies]},
    )

    if len(ctx.metrics.rounds) < 2:
        print(f"      베이스라인 기록됨 (초기 수율 {ctx.metrics.baseline_yield * 100:.2f}%)")
        return

    for key, comp in ctx.metrics.compare(-2, -1).items():
        if comp["before"] == comp["after"]:
            arrow = "─"
        else:
            arrow = "▲" if comp["improved"] else "▼"
        print(f"      {key}: {comp['before']:.3f} → {comp['after']:.3f} {arrow}")

    warnings = ctx.metrics.regression_warnings()
    if warnings:
        print(f"      [⚠️  REGRESSION] {len(warnings)}건 감지")
        for w in warnings:
            print(f"         - {w}")


def _report_phase(ctx: _LoopContext) -> None:
    print("\n  [⑤] REPORT")
    r = ctx.metrics.rounds[-1]
    print(f"      복구율: {r['recovery_rate']:.0%}")
    print(f"      평균 신뢰도: {r['avg_confidence']:.3f}")
    print(f"      수율 개선 (이번 라운드): {r['yield_improvement']:.3f}%p")
    print(f"      수율 누적 (베이스라인 대비): {r['yield_vs_baseline']:+.3f}%p")
    print(f"      인과규칙: {r['causal_rules']}개, 장애체인: {r['failure_chains']}개")
    print(f"      상관관계: {r['correlations']}개")
    print(
        f"      자동발견 인과: {len(ctx.causal_discovery.discovered_pairs)}쌍 "
        f"(승격 {len(ctx.causal_discovery._promotion_log)}건)"
    )


# ── IO helpers ─────────────────────────────────────────


def _print_header(num_rounds: int, sim_iterations: int) -> None:
    print("=" * 70)
    print("  Research Improvement Loop")
    print("  연구→개선→테스트→검증 자동 사이클")
    print(f"  라운드: {num_rounds}회, 시뮬레이션: {sim_iterations}회/라운드")
    print("=" * 70)


def _print_round_header(round_num: int, num_rounds: int) -> None:
    print(f"\n{'━' * 70}")
    print(f"  ROUND {round_num}/{num_rounds}")
    print(f"{'━' * 70}")


def _print_summary(ctx: _LoopContext, num_rounds: int) -> None:
    print(f"\n{'=' * 70}")
    print(f"  연구 루프 완료 — {num_rounds}회 반복")
    print(f"{'─' * 70}")
    summary = ctx.metrics.summary()
    if isinstance(summary, dict):
        for k, v in summary.items():
            print(f"  {k}: {v}")
    print(f"{'=' * 70}")


def _persist_results(ctx: _LoopContext, num_rounds: int, sim_iterations: int, db_path: str) -> None:
    output_path = os.path.join(PROJECT_ROOT, "results", "research_loop_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_rounds": num_rounds,
            "actual_rounds_run": len(ctx.metrics.rounds),
            "sim_iterations_per_round": sim_iterations,
            "baseline_yield": ctx.metrics.baseline_yield,
            "converged": ctx.metrics.has_converged(),
            "rounds": ctx.metrics.rounds,
            "summary": ctx.metrics.summary(),
            "evolution_agent": ctx.evolution_agent.get_status(),
            "causal_discovery": {
                "discovered_pairs": len(ctx.causal_discovery.discovered_pairs),
                "promotion_log": ctx.causal_discovery._promotion_log,
            },
            "llm_orchestrator_stats": ctx.llm_orchestrator._stats,
            "timestamp": datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {output_path}")


def _cleanup_db(db_path: str) -> None:
    import shutil
    for p in (db_path, db_path + ".wal", db_path + ".lock"):
        if not os.path.exists(p):
            continue
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
        except Exception:
            pass


if __name__ == "__main__":
    run_research_loop(num_rounds=10, sim_iterations=5)
