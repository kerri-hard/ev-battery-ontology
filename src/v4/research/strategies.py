"""연구 루프 6개 개선 전략 — 메트릭 history를 보고 시스템 파라미터 조정."""
from datetime import datetime

from v4.healing import AnomalyDetector, AutoRecoveryAgent
from v4.causal import CausalReasoner
from v4.correlation import CorrelationAnalyzer
from v4.scenarios import ScenarioEngine


def tune_anomaly_thresholds(detector: AnomalyDetector, metrics_history: list) -> str:
    """전략 1: 오탐률 기반 이상 감지 윈도우 크기 조정."""
    if not metrics_history:
        return "데이터 없음"
    fpr = metrics_history[-1].get("false_positive_rate", 0)
    if fpr > 0.3:
        detector.window_size = min(30, detector.window_size + 2)
        return f"윈도우 크기 증가: {detector.window_size - 2} → {detector.window_size} (오탐률 {fpr:.0%} 감소 목표)"
    if fpr < 0.1 and detector.window_size > 12:
        detector.window_size = max(10, detector.window_size - 1)
        return f"윈도우 크기 감소: {detector.window_size + 1} → {detector.window_size} (감도 향상)"
    return "임계값 유지 (적정 범위)"


def add_causal_rules(conn, causal_reasoner: CausalReasoner, metrics_history: list) -> str:
    """전략 2: 학습된 FailureChain에서 새로운 CausalRule을 도출."""
    added = 0
    try:
        r = conn.execute(
            "MATCH (fc:FailureChain) WHERE fc.success_count >= 2 "
            "RETURN fc.id, fc.cause_sequence, fc.step_id, fc.success_count"
        )
        while r.has_next():
            row = r.get_next()
            _fc_id, cause, step_id, count = row[0], row[1], row[2], int(row[3])
            new_id = f"CR-AUTO-{step_id}-{cause}"
            try:
                r2 = conn.execute(
                    "MATCH (cr:CausalRule) WHERE cr.id=$id RETURN count(cr)",
                    {"id": new_id},
                )
                if r2.get_next()[0] == 0:
                    conn.execute(
                        "CREATE (cr:CausalRule {id:$id, name:$name, cause_type:$cause, "
                        "effect_type:'yield_drop', strength:$str, confirmation_count:$cnt, "
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
    return f"새 인과규칙 {added}개 추가" if added else "추가할 규칙 없음"


def expand_correlation_coverage(corr_analyzer: CorrelationAnalyzer, metrics_history: list) -> str:
    """전략 3: 상관 임계값을 상관관계 수에 따라 가감."""
    if not metrics_history:
        return "데이터 없음"
    last_corrs = metrics_history[-1].get("correlations", 0)
    old_threshold = corr_analyzer.threshold
    if last_corrs < 10:
        corr_analyzer.threshold = max(0.4, corr_analyzer.threshold - 0.05)
        return f"상관 임계값 하향: {old_threshold:.2f} → {corr_analyzer.threshold:.2f}"
    if last_corrs > 80:
        corr_analyzer.threshold = min(0.8, corr_analyzer.threshold + 0.05)
        return f"상관 임계값 상향: {old_threshold:.2f} → {corr_analyzer.threshold:.2f} (노이즈 감소)"
    return "상관분석 설정 유지"


def optimize_recovery_playbook(auto_recovery: AutoRecoveryAgent, metrics_history: list) -> str:
    """전략 4: 복구 성공률 50% 미만인 (action, cause) 쌍을 식별."""
    if not hasattr(auto_recovery, "success_history"):
        return "학습 이력 없음"
    adjustments = []
    for (action, cause), stats in auto_recovery.success_history.items():
        total = stats.get("attempts", 0)
        success = stats.get("successes", 0)
        if total >= 3 and success / total < 0.5:
            adjustments.append(f"{action}/{cause}: 성공률 {success}/{total} — 대체 전략 필요")
    return f"플레이북 조정 {len(adjustments)}건" if adjustments else "플레이북 최적"


def enrich_scenarios(scenario_engine: ScenarioEngine, round_num: int) -> str:
    """전략 5: 라운드 5회 이후부터 시나리오 severity를 점진 상향."""
    lib = scenario_engine.get_scenario_library()
    if round_num >= 5:
        for scn in lib:
            for step in scn.get("affected_steps", []):
                step["severity"] = min(3, step.get("severity", 1) + 1)
    return f"시나리오 난이도 조정 (라운드 {round_num})"


def calibrate_causal_strength(conn, causal_reasoner: CausalReasoner) -> str:
    """전략 6: FailureChain 이력으로 CausalRule strength 재보정."""
    result = causal_reasoner.replay_calibration(conn)
    return f"인과규칙 재보정: {result.get('updates', 0)}개 업데이트"
