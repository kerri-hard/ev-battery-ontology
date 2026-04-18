"""Self-Healing 에이전트 패키지 (DETECT → DIAGNOSE → RECOVER).

각 책임을 단일 파일로 분리:
- detector.AnomalyDetector — SPC + Western Electric 룰 기반 이상 감지
- rca.RootCauseAnalyzer — 온톨로지 경로 역추적 진단
- recovery.AutoRecoveryAgent — 플레이북 기반 자동 복구
- orchestrator.ResilienceOrchestrator — PARALLEL_WITH 대체 경로 활성화
- playbook — 복구 플레이북 상수 + HITL 게이트 함수
"""
from v4.healing.playbook import (
    RECOVERY_PLAYBOOK,
    ACTION_DEFAULTS,
    RISK_NUMERIC,
    requires_hitl,
)
from v4.healing.detector import AnomalyDetector
from v4.healing.rca import RootCauseAnalyzer
from v4.healing.recovery import AutoRecoveryAgent
from v4.healing.orchestrator import ResilienceOrchestrator

__all__ = [
    "RECOVERY_PLAYBOOK",
    "ACTION_DEFAULTS",
    "RISK_NUMERIC",
    "requires_hitl",
    "AnomalyDetector",
    "RootCauseAnalyzer",
    "AutoRecoveryAgent",
    "ResilienceOrchestrator",
]
