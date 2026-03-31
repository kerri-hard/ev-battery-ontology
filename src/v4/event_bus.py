"""
Event Bus — 이벤트 기반 에이전트 오케스트레이션
================================================
업계 사례:
  - SOMN (ASME MSEC 2025): 자율 재편성 기계 네트워크 — 이벤트 기반 통신
  - CrewAI / LangGraph: 에이전트 DAG 워크플로우
  - Apache Kafka (제조): 이벤트 스트림 기반 실시간 파이프라인

현재 engine.py는 에이전트를 순차적 if/for로 호출한다.
이 모듈은 이벤트 기반 pub/sub 패턴으로 전환하여:
  1. 에이전트 추가/제거 시 engine.py 수정 불필요
  2. 이벤트에 반응하는 에이전트만 실행 (효율성)
  3. 에이전트 실행 순서를 동적으로 변경 가능
  4. 이벤트 로그를 통한 감사 추적 (audit trail)

사용법:
    bus = EventBus()
    bus.subscribe("anomaly_detected", anomaly_handler)
    bus.subscribe("diagnosis_complete", recovery_handler)
    await bus.publish("anomaly_detected", {"step_id": "PS-103", ...})
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine


# ═══════════════════════════════════════════════════════════════
#  EVENT TYPES — 자율 복구 루프의 이벤트 정의
# ═══════════════════════════════════════════════════════════════

# Phase 1: 감지
EVENT_SENSOR_READING = "sensor_reading"          # 센서 읽기값 수신
EVENT_ANOMALY_DETECTED = "anomaly_detected"      # 이상 감지됨
EVENT_ALARM_TRIGGERED = "alarm_triggered"        # 알람 발생

# Phase 2: 진단
EVENT_DIAGNOSIS_STARTED = "diagnosis_started"    # 진단 시작
EVENT_DIAGNOSIS_COMPLETE = "diagnosis_complete"  # 진단 완료
EVENT_CAUSAL_CHAIN_FOUND = "causal_chain_found"  # 인과 체인 발견
EVENT_CORRELATION_FOUND = "correlation_found"    # 상관관계 발견

# Phase 3: 복구
EVENT_RECOVERY_PLANNED = "recovery_planned"      # 복구 계획 수립
EVENT_RECOVERY_EXECUTED = "recovery_executed"    # 복구 실행됨
EVENT_RECOVERY_SUCCESS = "recovery_success"      # 복구 성공
EVENT_RECOVERY_FAILED = "recovery_failed"        # 복구 실패
EVENT_HITL_REQUIRED = "hitl_required"            # HITL 에스컬레이션

# Phase 4: 학습
EVENT_LEARNING_COMPLETE = "learning_complete"    # 학습 완료
EVENT_PLAYBOOK_UPDATED = "playbook_updated"      # 플레이북 갱신

# Phase 5: 예측
EVENT_RUL_UPDATED = "rul_updated"                # RUL 갱신
EVENT_PREDICTIVE_ALERT = "predictive_alert"      # 선제적 경고

# 배치/추적
EVENT_BATCH_CREATED = "batch_created"            # 생산 배치 생성
EVENT_BATCH_COMPLETED = "batch_completed"        # 생산 배치 완료
EVENT_BATCH_DEFECT = "batch_defect"              # 배치 결함 발생


# ═══════════════════════════════════════════════════════════════
#  EVENT DATACLASS
# ═══════════════════════════════════════════════════════════════

@dataclass
class Event:
    """이벤트 객체."""
    event_type: str
    data: dict = field(default_factory=dict)
    source: str = "engine"          # 발행자 (에이전트 이름)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    event_id: str = ""              # 자동 생성

    _counter: int = field(default=0, init=False, repr=False)

    def __post_init__(self):
        if not self.event_id:
            Event._counter += 1
            self.event_id = f"EVT-{Event._counter:06d}"


# ═══════════════════════════════════════════════════════════════
#  EVENT HANDLER TYPE
# ═══════════════════════════════════════════════════════════════

# 동기 핸들러: (event: Event) -> None
# 비동기 핸들러: (event: Event) -> Coroutine
EventHandler = Callable[[Event], Any]


@dataclass
class Subscription:
    """이벤트 구독 정보."""
    event_type: str
    handler: EventHandler
    agent_name: str = "unknown"
    priority: int = 0       # 높을수록 먼저 실행
    is_async: bool = False


# ═══════════════════════════════════════════════════════════════
#  EVENT BUS
# ═══════════════════════════════════════════════════════════════

class EventBus:
    """이벤트 기반 에이전트 오케스트레이션 버스.

    업계 참조:
      - SOMN: 이벤트 기반 기계 에이전트 통신
      - ROS 2: 토픽 기반 pub/sub (로봇 제조)
      - Apache Kafka: 이벤트 스트림 (제조 데이터 파이프라인)
    """

    def __init__(self, max_log_size: int = 1000):
        self._subscriptions: dict[str, list[Subscription]] = defaultdict(list)
        self._event_log: list[dict] = []
        self._max_log_size = max_log_size
        self._paused = False
        self._filters: list[Callable[[Event], bool]] = []

    def subscribe(self, event_type: str, handler: EventHandler,
                  agent_name: str = "unknown", priority: int = 0):
        """이벤트를 구독한다.

        Args:
            event_type: 구독할 이벤트 타입
            handler: 이벤트 핸들러 (동기 또는 비동기)
            agent_name: 구독 에이전트 이름
            priority: 실행 우선순위 (높을수록 먼저)
        """
        is_async = asyncio.iscoroutinefunction(handler)
        sub = Subscription(
            event_type=event_type,
            handler=handler,
            agent_name=agent_name,
            priority=priority,
            is_async=is_async,
        )
        self._subscriptions[event_type].append(sub)
        # 우선순위 정렬 (높은 순)
        self._subscriptions[event_type].sort(key=lambda s: -s.priority)

    def unsubscribe(self, event_type: str, agent_name: str):
        """특정 에이전트의 구독을 해제한다."""
        self._subscriptions[event_type] = [
            s for s in self._subscriptions[event_type]
            if s.agent_name != agent_name
        ]

    async def publish(self, event_type: str, data: dict = None,
                      source: str = "engine") -> list[dict]:
        """이벤트를 발행하고 모든 구독자에게 전달한다.

        Args:
            event_type: 이벤트 타입
            data: 이벤트 데이터
            source: 발행자

        Returns:
            list of handler results
        """
        if self._paused:
            return []

        event = Event(event_type=event_type, data=data or {}, source=source)

        # 필터 체크
        for f in self._filters:
            if not f(event):
                return []

        # 이벤트 로그 기록
        self._log_event(event)

        # 구독자 실행
        results = []
        for sub in self._subscriptions.get(event_type, []):
            try:
                if sub.is_async:
                    result = await sub.handler(event)
                else:
                    result = sub.handler(event)
                results.append({
                    "agent": sub.agent_name,
                    "success": True,
                    "result": result,
                })
            except Exception as e:
                results.append({
                    "agent": sub.agent_name,
                    "success": False,
                    "error": str(e),
                })

        return results

    def publish_sync(self, event_type: str, data: dict = None,
                     source: str = "engine") -> list[dict]:
        """동기 버전의 이벤트 발행 (비동기 핸들러 미지원)."""
        if self._paused:
            return []

        event = Event(event_type=event_type, data=data or {}, source=source)
        self._log_event(event)

        results = []
        for sub in self._subscriptions.get(event_type, []):
            if sub.is_async:
                continue  # 동기 모드에서는 비동기 핸들러 건너뜀
            try:
                result = sub.handler(event)
                results.append({
                    "agent": sub.agent_name, "success": True, "result": result,
                })
            except Exception as e:
                results.append({
                    "agent": sub.agent_name, "success": False, "error": str(e),
                })
        return results

    def add_filter(self, filter_fn: Callable[[Event], bool]):
        """이벤트 필터를 추가한다 (False 반환 시 이벤트 차단)."""
        self._filters.append(filter_fn)

    def pause(self):
        """이벤트 발행을 일시 중단한다."""
        self._paused = True

    def resume(self):
        """이벤트 발행을 재개한다."""
        self._paused = False

    def get_subscriptions(self) -> dict[str, list[str]]:
        """이벤트별 구독 에이전트 목록을 반환한다."""
        return {
            event_type: [s.agent_name for s in subs]
            for event_type, subs in self._subscriptions.items()
        }

    def get_event_log(self, limit: int = 50,
                      event_type: str | None = None) -> list[dict]:
        """이벤트 로그를 반환한다."""
        log = self._event_log
        if event_type:
            log = [e for e in log if e["event_type"] == event_type]
        return log[-limit:]

    def get_stats(self) -> dict:
        """이벤트 버스 통계."""
        type_counts = defaultdict(int)
        for entry in self._event_log:
            type_counts[entry["event_type"]] += 1

        return {
            "total_events": len(self._event_log),
            "subscription_count": sum(len(s) for s in self._subscriptions.values()),
            "event_types": len(self._subscriptions),
            "paused": self._paused,
            "events_by_type": dict(type_counts),
        }

    def _log_event(self, event: Event):
        """이벤트를 로그에 기록한다."""
        self._event_log.append({
            "event_id": event.event_id,
            "event_type": event.event_type,
            "source": event.source,
            "timestamp": event.timestamp,
            "data_keys": list(event.data.keys()),
        })
        # 로그 크기 제한
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]


# ═══════════════════════════════════════════════════════════════
#  AGENT REGISTRATION HELPERS
# ═══════════════════════════════════════════════════════════════

def register_healing_agents(bus: EventBus, agents: dict):
    """자율 복구 에이전트들을 이벤트 버스에 등록한다.

    Args:
        bus: EventBus 인스턴스
        agents: 에이전트 딕셔너리 (예: {"anomaly_detector": detector, ...})

    이 함수는 engine.py에서 호출하여 에이전트 ↔ 이벤트 매핑을 설정한다.
    새 에이전트를 추가할 때 engine.py를 수정하지 않고 여기에 등록하면 된다.
    """
    # 이벤트 → 에이전트 매핑 (선언적 구성)
    AGENT_EVENT_MAP = [
        (EVENT_SENSOR_READING, "anomaly_detector", 10),
        (EVENT_ANOMALY_DETECTED, "root_cause_analyzer", 10),
        (EVENT_ANOMALY_DETECTED, "causal_reasoner", 8),
        (EVENT_ANOMALY_DETECTED, "correlation_analyzer", 6),
        (EVENT_DIAGNOSIS_COMPLETE, "auto_recovery", 10),
        (EVENT_RECOVERY_FAILED, "resilience_orchestrator", 10),
        (EVENT_RECOVERY_SUCCESS, "causal_learner", 5),
        (EVENT_RECOVERY_FAILED, "causal_learner", 5),
        (EVENT_BATCH_DEFECT, "traceability_manager", 10),
    ]

    for event_type, agent_name, priority in AGENT_EVENT_MAP:
        agent = agents.get(agent_name)
        if agent and hasattr(agent, "handle_event"):
            bus.subscribe(event_type, agent.handle_event, agent_name, priority)
