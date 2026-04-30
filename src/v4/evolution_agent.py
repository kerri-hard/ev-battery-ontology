"""
Evolution Agent — 자가 진화 메타 에이전트
==========================================
research_loop.py의 6개 개선 전략을 메인 SelfHealingEngine에 통합하여,
에이전트 전략이 스스로 최적화되고 진화하는 메커니즘을 제공한다.

학술 근거:
  - A Comprehensive Survey of Self-Evolving AI Agents (2025)
  - Self-organizing Machine Network (ASME MSEC, 2025)
  - Gartner: 2028까지 기업 앱의 33%가 자율 에이전트 포함

핵심 메커니즘:
  1. 6 + α 개선 전략을 StrategyRecord로 래핑하여 fitness 추적
  2. 매 N 이터레이션마다 전략 실행 → 메트릭 델타 기반 fitness 계산
  3. 파라미터 변형 (Gaussian perturbation) → 우수 변형 승격
  4. 저성과 전략은 쿨다운 (제거하지 않고 빈도 감소)

설계 원칙 (VISION.md 섹션 9.6):
  - 점진적 자율성: 검증된 변형만 승격
  - 실패에서 성장: 저성과 전략도 삭제하지 않고 학습 데이터로 보존
"""
import json
import math
import os
import random
import re
import copy
from datetime import datetime
from collections import defaultdict


class StrategyRecord:
    """개별 전략의 실행 이력과 성과를 추적한다."""

    def __init__(self, name: str, fn, description: str = "",
                 params: dict | None = None):
        self.name = name
        self.fn = fn
        self.description = description
        self.params = params or {}
        self.executions = 0
        self.improvements = 0
        self.fitness = 0.5  # 0.0 ~ 1.0
        self.active = True
        self.cooldown_counter = 0
        self.history: list[dict] = []  # execution history (last 20)
        self.best_params: dict | None = None
        self.best_fitness = 0.0

    def record_execution(self, success: bool, fitness_delta: float, detail: str = ""):
        """실행 결과를 기록한다."""
        self.executions += 1
        if success:
            self.improvements += 1
        self.history.append({
            "cycle": self.executions,
            "success": success,
            "fitness_delta": round(fitness_delta, 4),
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        })
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "fitness": round(self.fitness, 4),
            "executions": self.executions,
            "improvements": self.improvements,
            "success_rate": round(
                self.improvements / max(self.executions, 1), 3
            ),
            "active": self.active,
            "cooldown": self.cooldown_counter,
        }


class EvolutionAgent:
    """자가 진화 메타 에이전트.

    research_loop.py의 6개 개선 전략을 메인 SelfHealingEngine에 통합하고,
    전략별 fitness를 추적하며, 파라미터 변형 + 승격/쿨다운을 수행한다.

    토론 프로토콜(v3)에는 참여하지 않지만, trust_score 패턴을 따라
    다른 에이전트의 신뢰도와 유사한 방식으로 성과를 추적한다.
    """

    # Fitness 임계값 — 전략 승격/쿨다운/재활성화 판정 기준
    FITNESS_PROMOTE_THRESHOLD = 0.6       # fitness 이상이면 활성 유지
    FITNESS_DEPRECIATE_THRESHOLD = 0.3    # fitness 미만이면 쿨다운
    FITNESS_MUTATION_LOW = 0.3            # 변형 탐색 대상 범위 하한
    FITNESS_MUTATION_HIGH = 0.7           # 변형 탐색 대상 범위 상한
    FITNESS_REACTIVATION_RESET = 0.4      # 쿨다운 해제 시 재부여 fitness
    MIN_EXECUTIONS_FOR_MUTATION = 2       # 변형 시도 전 최소 실행 횟수
    REACTIVATION_COOLDOWN_CYCLES = 6      # 쿨다운 후 재시도까지 대기 사이클

    def __init__(self, evolution_interval: int = 5):
        self.evolution_interval = evolution_interval
        self.trust_score = 1.0  # BaseAgent 패턴 호환
        self.strategies: list[StrategyRecord] = []
        self.cycle_count = 0
        self.history: list[dict] = []  # cycle 결과 이력

        # 파라미터 변형 경계
        self._param_bounds = {
            "window_size": (8, 40),
            "correlation_threshold": (0.3, 0.85),
            "scenario_severity_max": (1, 5),
            "significance": (0.01, 0.10),
            "min_samples": (10, 40),
        }

        # Fitness 가중치
        self._fitness_weights = {
            "recovery_rate": 0.40,
            "avg_confidence": 0.30,
            "yield_improvement": 0.30,
        }

    # ── STRATEGY REGISTRATION ─────────────────────────────

    def register_strategies(self, conn, anomaly_detector, causal_reasoner,
                           correlation_analyzer, auto_recovery, scenario_engine,
                           causal_discovery=None, engine=None):
        """research_loop.py의 6 전략 + CausalDiscovery + PRE-VERIFY 임계값 자기 진화 등록.

        Args:
            engine: SelfHealingEngine 인스턴스. PRE-VERIFY threshold 튜닝 전략에서
                    preverify_accuracy_history와 preverify_thresholds 접근에 사용.
        """
        self.strategies = []

        # Strategy 1: 이상 감지 임계값 조정
        def _tune_thresholds(_conn, _metrics):
            if not _metrics:
                return {"applied": False, "detail": "메트릭 없음"}
            last = _metrics[-1] if isinstance(_metrics, list) else _metrics
            fpr = last.get("false_positive_rate", 0)
            old_ws = anomaly_detector.window_size
            if fpr > 0.3:
                anomaly_detector.window_size = min(30, anomaly_detector.window_size + 2)
            elif fpr < 0.1 and anomaly_detector.window_size > 12:
                anomaly_detector.window_size = max(10, anomaly_detector.window_size - 1)
            changed = old_ws != anomaly_detector.window_size
            return {
                "applied": changed,
                "detail": f"윈도우: {old_ws}→{anomaly_detector.window_size}" if changed else "유지",
            }

        self.strategies.append(StrategyRecord(
            "anomaly_threshold_tuning",
            _tune_thresholds,
            "오탐률 기반 이상 감지 윈도우 크기 조정",
            {"window_size": anomaly_detector.window_size},
        ))

        # Strategy 2: 인과규칙 자동 도출 (FailureChain→CausalRule 승격)
        def _add_causal_rules(_conn, _metrics):
            added = 0
            try:
                r = _conn.execute(
                    "MATCH (fc:FailureChain) WHERE fc.success_count >= 2 "
                    "RETURN fc.id, fc.cause_sequence, fc.step_id, fc.success_count"
                )
                while r.has_next():
                    row = r.get_next()
                    fc_id, cause, step_id, count = row[0], row[1], row[2], int(row[3])
                    new_id = f"CR-AUTO-{step_id}-{cause}"
                    try:
                        r2 = _conn.execute(
                            "MATCH (cr:CausalRule) WHERE cr.id=$id RETURN count(cr)",
                            {"id": new_id},
                        )
                        if r2.get_next()[0] == 0:
                            _conn.execute(
                                "CREATE (cr:CausalRule {id:$id, name:$name, "
                                "cause_type:$cause, effect_type:'yield_drop', "
                                "strength:$str, confirmation_count:$cnt, "
                                "last_confirmed:$ts})",
                                {
                                    "id": new_id,
                                    "name": f"학습된 규칙: {cause}→수율하락 ({step_id})",
                                    "cause": cause,
                                    "str": min(0.9, 0.5 + count * 0.1),
                                    "cnt": count,
                                    "ts": datetime.now().isoformat(),
                                },
                            )
                            added += 1
                    except Exception:
                        pass
            except Exception:
                pass
            return {"applied": added > 0, "detail": f"새 인과규칙 {added}개 추가"}

        self.strategies.append(StrategyRecord(
            "causal_rule_derivation",
            _add_causal_rules,
            "FailureChain 성공 이력에서 CausalRule 자동 도출",
        ))

        # Strategy 3: 상관분석 범위 확장
        def _expand_correlation(_conn, _metrics):
            old_threshold = correlation_analyzer.threshold
            if _metrics:
                last = _metrics[-1] if isinstance(_metrics, list) else _metrics
                corr_count = last.get("correlations", len(correlation_analyzer.known_correlations))
                if corr_count < 10:
                    correlation_analyzer.threshold = max(0.4, correlation_analyzer.threshold - 0.05)
                elif corr_count > 80:
                    correlation_analyzer.threshold = min(0.8, correlation_analyzer.threshold + 0.05)
            changed = old_threshold != correlation_analyzer.threshold
            return {
                "applied": changed,
                "detail": f"임계값: {old_threshold:.2f}→{correlation_analyzer.threshold:.2f}" if changed else "유지",
            }

        self.strategies.append(StrategyRecord(
            "correlation_expansion",
            _expand_correlation,
            "상관분석 임계값 조정으로 발견 범위 확장/축소",
            {"correlation_threshold": correlation_analyzer.threshold},
        ))

        # Strategy 4: 복구 플레이북 최적화
        def _optimize_playbook(_conn, _metrics):
            if not hasattr(auto_recovery, 'success_history'):
                return {"applied": False, "detail": "학습 이력 없음"}
            low_performers = []
            for (action, cause), stats in auto_recovery.success_history.items():
                total = stats.get("attempts", 0)
                success = stats.get("successes", 0)
                if total >= 3 and success / total < 0.5:
                    low_performers.append(f"{action}/{cause}")
            return {
                "applied": len(low_performers) > 0,
                "detail": f"저성과 액션 {len(low_performers)}건 식별",
                "low_performers": low_performers[:5],
            }

        self.strategies.append(StrategyRecord(
            "playbook_optimization",
            _optimize_playbook,
            "복구 성공률 기반 플레이북 우선순위 조정",
        ))

        # Strategy 5: 시나리오 난이도 적응
        def _enrich_scenarios(_conn, _metrics):
            if _metrics:
                last = _metrics[-1] if isinstance(_metrics, list) else _metrics
                total_inc = last.get("total_incidents", 0)
                auto_rec = last.get("auto_recovered", 0)
                result = scenario_engine.adapt_difficulty({
                    "total_incidents": total_inc,
                    "auto_recovered": auto_rec,
                })
                return {"applied": True, "detail": str(result)}
            return {"applied": False, "detail": "메트릭 없음"}

        self.strategies.append(StrategyRecord(
            "scenario_difficulty",
            _enrich_scenarios,
            "복구율 기반 시나리오 난이도 적응",
        ))

        # Strategy 6: 인과규칙 강도 재보정
        def _calibrate_causal(_conn, _metrics):
            result = causal_reasoner.replay_calibration(_conn)
            updates = result.get("updates", 0)
            return {
                "applied": updates > 0,
                "detail": f"인과규칙 {updates}개 재보정",
            }

        self.strategies.append(StrategyRecord(
            "causal_strength_calibration",
            _calibrate_causal,
            "FailureChain 이력으로 CausalRule strength Bayesian 재보정",
        ))

        # Strategy 7 (optional): 자동 인과 발견 트리거
        if causal_discovery:
            def _trigger_discovery(_conn, _metrics):
                candidates = causal_discovery.discover(correlation_analyzer)
                if not candidates:
                    return {"applied": False, "detail": "발견된 인과 없음"}
                pruned = causal_discovery.prune_conditional_independence(
                    candidates, correlation_analyzer,
                )
                promoted = causal_discovery.promote_to_ontology(
                    _conn, pruned, {},
                )
                return {
                    "applied": len(promoted) > 0,
                    "detail": f"테스트 {len(candidates)}쌍, 가지치기 후 {len(pruned)}, 승격 {len(promoted)}",
                    "promoted": [p["id"] for p in promoted],
                }

            self.strategies.append(StrategyRecord(
                "causal_discovery",
                _trigger_discovery,
                "Granger causality 기반 자동 인과 발견",
            ))

        # Strategy 8 (optional): PRE-VERIFY 임계값 자기 진화 — sign accuracy fitness signal
        if engine is not None:
            self.strategies.append(StrategyRecord(
                "preverify_threshold_tuning",
                _make_preverify_tuner(engine),
                "PRE-VERIFY 예측 정확도 기반 안전등급별 threshold 자기 진화",
                dict(engine.preverify_thresholds),
            ))

    # ── EVOLUTION CYCLE ───────────────────────────────────

    def should_run(self, healing_iteration: int) -> bool:
        """이번 이터레이션에서 진화 사이클을 실행해야 하는지 판단한다."""
        return healing_iteration > 0 and healing_iteration % self.evolution_interval == 0

    def run_evolution_cycle(self, conn, metrics_before: dict,
                            metrics_after: dict) -> dict:
        """진화 사이클 하나를 실행한다.

        1. 활성 전략 실행
        2. 전략별 fitness 계산
        3. 파라미터 변형 생성
        4. 승격/쿨다운 결정
        """
        self.cycle_count += 1
        strategies_run = 0
        strategies_improved = 0
        mutations_tested = 0
        strategy_details = []

        # 메트릭을 리스트로 래핑 (전략 함수의 기대 형식)
        metrics_list = [metrics_after] if metrics_after else []

        for strategy in self.strategies:
            if not strategy.active:
                # 쿨다운 중인 전략은 2 사이클마다 한 번만 실행
                strategy.cooldown_counter += 1
                if strategy.cooldown_counter % 2 != 0:
                    continue

            try:
                result = strategy.fn(conn, metrics_list)
                applied = result.get("applied", False)
                strategies_run += 1

                # Fitness 계산: 전략별 고유 impact + 글로벌 메트릭 델타의 일부
                # (모든 전략이 같은 fitness를 받던 버그 수정)
                global_delta = self._evaluate_fitness(metrics_before, metrics_after)
                strategy_impact = self._evaluate_strategy_impact(strategy, result)
                # 70% 전략 고유 impact, 30% 글로벌 분배 (전략이 applied=True일 때만)
                fitness_delta = 0.7 * strategy_impact + (0.3 * global_delta if applied else 0.0)
                old_fitness = strategy.fitness
                # Exponential moving average — α=0.5 (이전 0.3은 baseline 0.5에서 평형
                # 정체. 23 사이클 후 평균 fitness 0.52, 사실상 학습 0이라 α 상향).
                strategy.fitness = 0.5 * strategy.fitness + 0.5 * (0.5 + fitness_delta)
                strategy.fitness = max(0.0, min(1.0, strategy.fitness))

                success = applied and fitness_delta > 0
                strategy.record_execution(success, fitness_delta, result.get("detail", ""))

                if success:
                    strategies_improved += 1

                # 최고 성능 파라미터 기록
                if strategy.fitness > strategy.best_fitness:
                    strategy.best_fitness = strategy.fitness
                    strategy.best_params = copy.deepcopy(strategy.params)

                strategy_details.append({
                    "name": strategy.name,
                    "applied": applied,
                    "fitness_before": round(old_fitness, 4),
                    "fitness_after": round(strategy.fitness, 4),
                    "detail": result.get("detail", ""),
                })

            except Exception as exc:
                strategy.record_execution(False, 0.0, f"error: {exc}")
                strategy_details.append({
                    "name": strategy.name,
                    "applied": False,
                    "error": str(exc),
                })

        # 파라미터 변형 시도 (fitness가 중간 범위인 전략 대상)
        for strategy in self.strategies:
            if self._is_mutation_candidate(strategy):
                variant = self._mutate_strategy_params(strategy)
                if variant:
                    mutations_tested += 1

        # 승격/쿨다운 판정
        self._promote_or_depreciate()

        # 전체 fitness
        active_strategies = [s for s in self.strategies if s.active]
        overall_fitness = (
            sum(s.fitness for s in active_strategies) / len(active_strategies)
            if active_strategies else 0.5
        )

        best_strategy = max(self.strategies, key=lambda s: s.fitness) if self.strategies else None

        cycle_result = {
            "cycle": self.cycle_count,
            "strategies_run": strategies_run,
            "strategies_improved": strategies_improved,
            "mutations_tested": mutations_tested,
            "overall_fitness": round(overall_fitness, 4),
            "best_strategy": best_strategy.name if best_strategy else None,
            "best_fitness": round(best_strategy.fitness, 4) if best_strategy else 0,
            "details": strategy_details,
            "timestamp": datetime.now().isoformat(),
        }
        self.history.append(cycle_result)
        if len(self.history) > 50:
            self.history = self.history[-50:]

        return cycle_result

    # ── PARAMETER MUTATION ────────────────────────────────

    def _is_mutation_candidate(self, strategy: StrategyRecord) -> bool:
        """전략이 파라미터 변형 탐색의 대상인지 판단한다.

        중간 fitness 범위(탐색 가치 있음) + 변형 가능 파라미터 존재 +
        최소 실행 이력이 있어야 변형을 시도한다.
        """
        return (
            self.FITNESS_MUTATION_LOW < strategy.fitness < self.FITNESS_MUTATION_HIGH
            and bool(strategy.params)
            and strategy.executions >= self.MIN_EXECUTIONS_FOR_MUTATION
        )

    def _mutate_strategy_params(self, strategy: StrategyRecord) -> dict | None:
        """전략의 파라미터를 가우시안 교란으로 변형한다."""
        if not strategy.params:
            return None

        variant = {}
        for key, value in strategy.params.items():
            bounds = self._param_bounds.get(key)
            if bounds is None or not isinstance(value, (int, float)):
                variant[key] = value
                continue

            low, high = bounds
            # Gaussian perturbation: σ = (high - low) * 0.1
            sigma = (high - low) * 0.1
            new_val = value + random.gauss(0, sigma)
            new_val = max(low, min(high, new_val))

            if isinstance(value, int):
                new_val = int(round(new_val))

            variant[key] = new_val

        strategy.params = variant
        return variant

    # ── FITNESS EVALUATION ────────────────────────────────

    def _evaluate_strategy_impact(self, strategy: StrategyRecord, result: dict) -> float:
        """전략의 고유 실행 결과에서 impact 점수(-0.3~+0.3)를 산출한다.

        전략별 결과 시그니처(result dict)를 해석하여 global metric delta와는
        독립적인 직접 임팩트를 계산한다. 없으면 0을 반환한다.
        """
        if not result.get("applied", False):
            # 데이터 부족으로 적용되지 못한 전략은 중립(0). 이전 -0.02는 data-hungry
            # 전략(causal_discovery 등)을 계속 끌어내려 mean fitness plateau를 만들었음.
            # 실제 부진 전략은 쿨다운 로직이 별도로 처리하므로 여기서 페널티 불필요.
            return 0.0
        detail = str(result.get("detail", ""))
        name = strategy.name

        if name == "anomaly_threshold_tuning":
            # 실제 조정이 일어났으면 +0.08, 과한 조정은 감점
            return 0.08

        if name == "causal_rule_derivation":
            # detail에 "새 인과규칙 N개 추가" (접미사 섞임 허용) 형태로 N 추출
            m = re.search(r"(\d+)", detail)
            added = int(m.group(1)) if m else 0
            # 규칙 1개당 +0.025, 상한 +0.3
            return min(0.30, added * 0.025)

        if name == "correlation_expansion":
            return 0.05  # 임계값 조정은 탐색 행위 — 작은 긍정

        if name == "playbook_optimization":
            # 저성과 액션이 식별되었다는 것은 최적화 여지가 있다는 신호
            low_perf = result.get("low_performers", [])
            # 정보 가치: +0.06, 너무 많으면 시스템 문제로 감점 안 함 (식별 자체가 가치)
            return 0.06 if low_perf else 0.02

        if name == "scenario_difficulty":
            # 난이도 적응은 항상 가치 있는 탐색
            return 0.05

        if name == "causal_strength_calibration":
            m = re.search(r"(\d+)", detail)
            updates = int(m.group(1)) if m else 0
            return min(0.25, updates * 0.03)

        if name == "causal_discovery":
            promoted = result.get("promoted", [])
            # 새 인과 발견은 매우 가치 있음: 개당 +0.08, 상한 +0.3
            return min(0.30, len(promoted) * 0.08)

        return 0.03  # 알 수 없는 전략 — 실행 자체를 약한 긍정

    def _evaluate_fitness(self, metrics_before: dict, metrics_after: dict) -> float:
        """전략 실행 전후 메트릭 델타로 fitness를 계산한다.

        fitness = Σ w_i * normalized_delta_i
        범위: -0.5 ~ +0.5 (0.0 = 변화 없음)
        """
        if not metrics_before or not metrics_after:
            return 0.0

        total = 0.0

        # Recovery rate
        rr_before = metrics_before.get("recovery_rate", 0)
        rr_after = metrics_after.get("recovery_rate", 0)
        if rr_before == 0 and rr_after == 0:
            # healing history에서 계산
            inc = metrics_after.get("total_incidents", metrics_after.get("incidents", 0))
            rec = metrics_after.get("auto_recovered", 0)
            rr_after = rec / max(inc, 1) if inc else 0
        total += self._fitness_weights["recovery_rate"] * (rr_after - rr_before)

        # Confidence
        conf_before = metrics_before.get("avg_confidence", 0)
        conf_after = metrics_after.get("avg_confidence", 0)
        total += self._fitness_weights["avg_confidence"] * (conf_after - conf_before)

        # Yield improvement
        y_before = metrics_before.get("line_yield", metrics_before.get("avg_yield", 0))
        y_after = metrics_after.get("line_yield", metrics_after.get("avg_yield", 0))
        total += self._fitness_weights["yield_improvement"] * (y_after - y_before) * 10  # 수율은 미세한 차이도 중요

        return max(-0.5, min(0.5, total))

    # ── PROMOTE / DEPRECIATE ──────────────────────────────

    def _promote_or_depreciate(self):
        """전략의 활성/쿨다운 상태를 업데이트한다.

        - fitness > FITNESS_PROMOTE_THRESHOLD → 활성 유지/복원
        - fitness < FITNESS_DEPRECIATE_THRESHOLD (3회+ 실행) → 쿨다운
        - 쿨다운 후 REACTIVATION_COOLDOWN_CYCLES 경과 → 재활성화 시도
        """
        min_execs_for_cooldown = 3
        for strategy in self.strategies:
            if strategy.fitness > self.FITNESS_PROMOTE_THRESHOLD:
                if not strategy.active:
                    strategy.active = True
                    strategy.cooldown_counter = 0
            elif (strategy.fitness < self.FITNESS_DEPRECIATE_THRESHOLD
                    and strategy.executions >= min_execs_for_cooldown):
                if strategy.active:
                    strategy.active = False
                    strategy.cooldown_counter = 0
            elif (not strategy.active
                    and strategy.cooldown_counter >= self.REACTIVATION_COOLDOWN_CYCLES):
                # 재활성화 시도: fitness를 리셋하고 다시 기회 부여
                strategy.active = True
                strategy.fitness = self.FITNESS_REACTIVATION_RESET
                strategy.cooldown_counter = 0

    # ── STATUS / SUMMARY ──────────────────────────────────

    def get_status(self) -> dict:
        """EvolutionAgent의 현재 상태를 반환한다."""
        return {
            "cycle_count": self.cycle_count,
            "evolution_interval": self.evolution_interval,
            "trust_score": round(self.trust_score, 3),
            "strategy_count": len(self.strategies),
            "active_count": sum(1 for s in self.strategies if s.active),
            "strategies": self.get_strategy_summary(),
            "recent_cycles": self.history[-5:],
        }

    def get_strategy_summary(self) -> list[dict]:
        """전략별 요약 정보를 반환한다."""
        return [s.to_dict() for s in self.strategies]

    # ── PERSISTENCE (L5 LearningRecord 경량 구현) ─────────

    def save_state(self, path: str) -> bool:
        """fitness/executions/파라미터를 JSON으로 저장한다.

        VISION Layer 5 (자가 진화) 원칙: 학습 이력을 재시작 간 유지.
        """
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            payload = {
                "saved_at": datetime.now().isoformat(),
                "cycle_count": self.cycle_count,
                "evolution_interval": self.evolution_interval,
                "trust_score": self.trust_score,
                "strategies": [
                    {
                        "name": s.name,
                        "params": s.params,
                        "executions": s.executions,
                        "improvements": s.improvements,
                        "fitness": s.fitness,
                        "active": s.active,
                        "cooldown_counter": s.cooldown_counter,
                        "best_params": s.best_params,
                        "best_fitness": s.best_fitness,
                        "history": s.history[-10:],  # 최근 10건만
                    }
                    for s in self.strategies
                ],
                "recent_cycles": self.history[-10:],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def load_state(self, path: str) -> bool:
        """이전 저장 상태를 복원한다. register_strategies() 이후 호출."""
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            by_name = {s["name"]: s for s in payload.get("strategies", [])}
            for strategy in self.strategies:
                snap = by_name.get(strategy.name)
                if not snap:
                    continue
                # 함수 자체(fn)는 복원하지 않고 통계만 이어서 쌓는다
                strategy.executions = snap.get("executions", 0)
                strategy.improvements = snap.get("improvements", 0)
                strategy.fitness = snap.get("fitness", 0.5)
                strategy.active = snap.get("active", True)
                strategy.cooldown_counter = snap.get("cooldown_counter", 0)
                strategy.best_params = snap.get("best_params")
                strategy.best_fitness = snap.get("best_fitness", 0.0)
                strategy.history = snap.get("history", [])
                # 저장된 best_params가 있으면 현재 params로 복원 (학습된 최적 유지)
                if strategy.best_params:
                    strategy.params = copy.deepcopy(strategy.best_params)
            self.cycle_count = payload.get("cycle_count", 0)
            self.history = payload.get("recent_cycles", [])
            return True
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 8 factory — PRE-VERIFY 임계값 자기 진화
# ═══════════════════════════════════════════════════════════════════════════

# 안전등급별 임계값 범위 (mutation 안전대)
_PV_THRESHOLD_BOUNDS = {
    "A": (1e-5, 1e-3),
    "B": (-5e-5, 5e-4),
    "C": (-5e-3, 1e-4),
}

_PV_MIN_SAMPLES = 5         # 이 값 미만이면 튜닝 skip
_PV_LOW_ACCURACY = 0.6      # 이하면 tighten
_PV_HIGH_ACCURACY = 0.85    # 이상이고 reject rate > 0 이면 loosen
_PV_MIN_REJECT_RATE = 0.05  # loosen 조건


def _make_preverify_tuner(engine):
    """engine의 preverify_thresholds를 accuracy_history 기반으로 조정하는 전략 클로저.

    낮은 sign_accuracy → 시뮬레이션 신뢰도가 낮음 → 임계값 상향(엄격)으로 위험 액션 차단
    높은 sign_accuracy + 높은 reject rate → 임계값 하향(완화)으로 자율성 회복
    """

    def _tune_preverify(_conn, _metrics):
        history = list(getattr(engine, "preverify_accuracy_history", []) or [])
        recent = history[-20:]
        if len(recent) < _PV_MIN_SAMPLES:
            return {
                "applied": False,
                "detail": f"샘플 부족 ({len(recent)} < {_PV_MIN_SAMPLES})",
            }

        sign_matches = sum(1 for s in recent if s.get("sign_match"))
        sign_accuracy = sign_matches / len(recent)
        mae = sum(s.get("abs_error", 0) for s in recent) / len(recent)

        counters = getattr(engine, "preverify_counters", {})
        plans_total = counters.get("plans_total", 0) or 1
        reject_rate = counters.get("auto_rejected_total", 0) / plans_total

        thresholds = engine.preverify_thresholds
        before = dict(thresholds)

        direction = _decide_direction(sign_accuracy, reject_rate)
        if direction == "tighten":
            _tighten(thresholds)
        elif direction == "loosen":
            _loosen(thresholds)

        changed = any(before[k] != thresholds[k] for k in thresholds)
        return {
            "applied": changed,
            "detail": (
                f"sign_acc={sign_accuracy:.2f}, mae={mae:.5f}, "
                f"reject_rate={reject_rate:.2%} → {direction}"
            ),
            "direction": direction,
            "before": before,
            "after": dict(thresholds),
            "sign_accuracy": round(sign_accuracy, 3),
            "mae": round(mae, 6),
            "samples": len(recent),
        }

    return _tune_preverify


def _decide_direction(sign_accuracy: float, reject_rate: float) -> str:
    if sign_accuracy < _PV_LOW_ACCURACY:
        return "tighten"
    if sign_accuracy > _PV_HIGH_ACCURACY and reject_rate > _PV_MIN_REJECT_RATE:
        return "loosen"
    return "hold"


def _tighten(thresholds: dict) -> None:
    """임계값을 상향 (엄격). 더 많은 auto-reject → HITL 부담 증가지만 안전."""
    for level, (lo, hi) in _PV_THRESHOLD_BOUNDS.items():
        cur = thresholds.get(level, 0.0)
        # 양수 영역으로 10%씩 상향, 음수면 0에 가깝게
        step = max(abs(cur) * 0.2, 1e-5)
        thresholds[level] = min(cur + step, hi)


def _loosen(thresholds: dict) -> None:
    """임계값을 하향 (완화). 더 많은 자동 실행 → 자율성 회복."""
    for level, (lo, hi) in _PV_THRESHOLD_BOUNDS.items():
        cur = thresholds.get(level, 0.0)
        step = max(abs(cur) * 0.2, 1e-5)
        thresholds[level] = max(cur - step, lo)
