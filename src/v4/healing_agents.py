"""Backward-compatibility shim — 실제 구현은 `v4.healing` 패키지로 이동했다.

기존 import path (`from v4.healing_agents import X`)를 깨지 않도록 재내보낸다.
신규 코드는 `from v4.healing import X`를 사용할 것.
"""
from v4.healing import (
    RECOVERY_PLAYBOOK,
    ACTION_DEFAULTS,
    RISK_NUMERIC,
    requires_hitl,
    AnomalyDetector,
    RootCauseAnalyzer,
    AutoRecoveryAgent,
    ResilienceOrchestrator,
)

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
