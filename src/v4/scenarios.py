"""
ScenarioEngine --- EV 배터리팩 제조 특화 장애 시나리오 엔진
==========================================================
실제 제조 현장에서 발생하는 장애 패턴을 시뮬레이션한다.

기존 sensor_simulator 는 5% 확률의 단순 Gaussian 노이즈만 생성했으나,
실제 배터리팩 라인에서는 다음과 같은 패턴이 훨씬 흔하다:

  - 단일 장애(single): 한 공정의 한 센서에서만 이상 발생
  - 연쇄 장애(cascading): 상류 공정 문제가 하류로 전파
  - 자재 열화(degradation): 시간이 지남에 따라 점진적으로 악화
  - 환경 변동(environmental): 외부 요인(온도, 습도)에 의한 전체 영향

사용법:
    engine = ScenarioEngine(sensor_sim)
    engine.activate_scenario("SCN-001")
    # 매 healing iteration 시작 시:
    effects = engine.tick()
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from v4.sensor_simulator import SensorSimulator


# ═══════════════════════════════════════════════════════════════
#  Physical Distance Model for Cascading Timing
# ═══════════════════════════════════════════════════════════════

def _area_from_step(step_id: str) -> int:
    """PS-1xx -> 1, PS-2xx -> 2, etc. Returns the 100-series area number."""
    try:
        return int(step_id.split("-")[1][0])
    except (IndexError, ValueError):
        return 0


def physical_delay(src_step: str, tgt_step: str) -> int:
    """Compute delay_ticks based on physical distance between process areas.

    Same area = 1 tick, adjacent area = 2 ticks, far (2+ areas apart) = 3 ticks.
    """
    src_area = _area_from_step(src_step)
    tgt_area = _area_from_step(tgt_step)
    distance = abs(src_area - tgt_area)
    if distance == 0:
        return 1
    elif distance == 1:
        return 2
    else:
        return 3


# ═══════════════════════════════════════════════════════════════
#  Scenario Library
# ═══════════════════════════════════════════════════════════════

SCENARIO_LIBRARY: list[dict[str, Any]] = [
    # ──────────────────────────────────────────────────────────
    # SCN-001: 셀 스태킹 진동 → 용접 불량 전파 (cascading)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-001",
        "name": "셀 스태킹 진동 이상 -> 용접 불량 전파",
        "description": (
            "스태킹 머신 베어링 마모로 진동 증가, "
            "셀 정렬 불량이 후속 탭 레이저 용접의 전류 불안정과 "
            "용접부 온도 편차로 전파된다."
        ),
        "category": "cascading",
        "severity": "HIGH",
        "affected_steps": [
            {"step_id": "PS-103", "sensor": "vibration", "severity": 2, "delay_ticks": 0},
            {"step_id": "PS-104", "sensor": "current", "severity": 1, "delay_ticks": 2},
            {"step_id": "PS-105", "sensor": "temperature", "severity": 1, "delay_ticks": 3},
        ],
        "root_cause": "bearing_wear",
        "expected_yield_impact": -0.015,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-002: 코팅 부스 온도 이상 (single)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-002",
        "name": "코팅 부스 온도 이상 -> 표면 불량",
        "description": (
            "에폭시 코팅 부스의 냉각 장치 고장으로 부스 내 온도가 급등. "
            "코팅 점도가 변화하여 표면 불량(기포, 두께 편차) 발생."
        ),
        "category": "single",
        "severity": "MEDIUM",
        "affected_steps": [
            {"step_id": "PS-404", "sensor": "temperature", "severity": 3, "delay_ticks": 0},
        ],
        "root_cause": "cooling_failure",
        "expected_yield_impact": -0.008,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-003: 와이어 하네스 자재 로트 변경 (degradation)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-003",
        "name": "와이어 하네스 자재 로트 변경",
        "description": (
            "새 로트의 와이어 하네스 원재료 특성이 미세하게 상이하여 "
            "크림핑 프레스 토크 값이 서서히 드리프트하고, "
            "이후 통전 검사에서 전류 값이 약간 상승한다."
        ),
        "category": "degradation",
        "severity": "LOW",
        "affected_steps": [
            {"step_id": "PS-203", "sensor": "torque_force", "severity": 1, "delay_ticks": 0,
             "degradation_ticks": 10},
            {"step_id": "PS-204", "sensor": "current", "severity": 1, "delay_ticks": 5,
             "degradation_ticks": 10},
        ],
        "root_cause": "material_lot_change",
        "expected_yield_impact": -0.005,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-004: BMS 솔더링 온도 편차 → 기능 불량 (cascading)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-004",
        "name": "BMS 솔더링 온도 편차 -> 기능 불량",
        "description": (
            "SMT 리플로우 오븐의 히터 열화로 솔더링 온도가 상한 근처까지 상승. "
            "솔더 접합 품질 저하가 BMS 기능 테스트에서 전류 이상으로 나타난다."
        ),
        "category": "cascading",
        "severity": "HIGH",
        "affected_steps": [
            {"step_id": "PS-201", "sensor": "temperature", "severity": 2, "delay_ticks": 0},
            {"step_id": "PS-202", "sensor": "current", "severity": 1, "delay_ticks": 2},
        ],
        "root_cause": "temperature_rise",
        "expected_yield_impact": -0.012,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-005: CNC 가공 정밀도 저하 (degradation)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-005",
        "name": "CNC 가공 정밀도 저하",
        "description": (
            "5축 CNC 스핀들 베어링 열화로 절삭 진동이 점진적으로 증가. "
            "마찰열 증가로 쿨링 플레이트 가공면 온도도 미세 상승."
        ),
        "category": "degradation",
        "severity": "MEDIUM",
        "affected_steps": [
            {"step_id": "PS-301", "sensor": "vibration", "severity": 1, "delay_ticks": 0,
             "degradation_ticks": 8},
            {"step_id": "PS-304", "sensor": "temperature", "severity": 1, "delay_ticks": 3,
             "degradation_ticks": 8},
        ],
        "root_cause": "precision_loss",
        "expected_yield_impact": -0.010,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-006: 인클로저 용접 전류 이상 (single)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-006",
        "name": "인클로저 용접 전류 이상",
        "description": (
            "레이저 용접 로봇의 전원 공급 모듈 불안정으로 용접 전류 스파이크 발생. "
            "용접 비드 품질 불량으로 이어질 수 있다."
        ),
        "category": "single",
        "severity": "HIGH",
        "affected_steps": [
            {"step_id": "PS-402", "sensor": "current", "severity": 3, "delay_ticks": 0},
        ],
        "root_cause": "current_anomaly",
        "expected_yield_impact": -0.018,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-007: 최종 조립 토크 편차 + 기밀 불량 (cascading)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-007",
        "name": "최종 조립 토크 편차 + 기밀 불량",
        "description": (
            "토크 렌치 교정 편차로 고전압 버스바 체결 토크가 드리프트. "
            "조립 불균일이 BMS/하네스 연결 온도와 EOL 기밀 검사 진동에 전파."
        ),
        "category": "cascading",
        "severity": "HIGH",
        "affected_steps": [
            {"step_id": "PS-502", "sensor": "torque_force", "severity": 2, "delay_ticks": 0},
            {"step_id": "PS-503", "sensor": "temperature", "severity": 1, "delay_ticks": 2},
            {"step_id": "PS-506", "sensor": "vibration", "severity": 1, "delay_ticks": 4},
        ],
        "root_cause": "equipment_wear",
        "expected_yield_impact": -0.020,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-008: 전체 라인 환경 온도 상승 (environmental)
    # ──────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────
    # SCN-009: 검사기 캘리브레이션 드리프트 (degradation, defect_mode_match)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-009",
        "name": "최종 검사기 캘리브레이션 드리프트",
        "description": (
            "EOL 검사기의 광학 모듈 캘리브레이션이 점진 드리프트하여 "
            "두께/정렬 측정값이 미세하게 부정확해진다. INCREASE_INSPECTION 효과 큼."
        ),
        "category": "degradation",
        "severity": "MEDIUM",
        "affected_steps": [
            {"step_id": "PS-505", "sensor": "alignment", "severity": 1, "delay_ticks": 0,
             "degradation_ticks": 12},
            {"step_id": "PS-506", "sensor": "vibration", "severity": 1, "delay_ticks": 4,
             "degradation_ticks": 12},
        ],
        "root_cause": "defect_mode_match",
        "expected_yield_impact": -0.008,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-010: 셀 공급사 LOT 품질 편차 (single, material_anomaly)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-010",
        "name": "셀 공급사 LOT 품질 편차",
        "description": (
            "신규 입고 셀 LOT의 두께가 사양 상한 근처에 분포. "
            "스태킹 정렬과 셀 검사 단계에서 품질 변동. MATERIAL_SWITCH 효과 큼."
        ),
        "category": "single",
        "severity": "HIGH",
        "affected_steps": [
            {"step_id": "PS-101", "sensor": "thickness", "severity": 3, "delay_ticks": 0},
            {"step_id": "PS-102", "sensor": "alignment", "severity": 2, "delay_ticks": 1},
        ],
        "root_cause": "material_anomaly",
        "expected_yield_impact": -0.014,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-011: 클린룸 파티클 증가 (environmental, yield_drop)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-011",
        "name": "클린룸 파티클 카운트 증가",
        "description": (
            "HEPA 필터 노화로 클린룸 내 0.5μm 파티클 카운트 상한 초과. "
            "BMS 보드 솔더링과 코팅 표면 품질에 직접 영향."
        ),
        "category": "environmental",
        "severity": "MEDIUM",
        "affected_steps": [
            {"step_id": "PS-201", "sensor": "humidity", "severity": 2, "delay_ticks": 0},
            {"step_id": "PS-404", "sensor": "humidity", "severity": 2, "delay_ticks": 0},
        ],
        "root_cause": "yield_drop",
        "expected_yield_impact": -0.012,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-012: 컨베이어 속도 편차 (degradation, process_variation)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-012",
        "name": "공정 컨베이어 속도 편차",
        "description": (
            "메인 컨베이어 모터 인버터 노이즈로 이송 속도가 ±5% 변동. "
            "주요 가공 공정의 사이클 타임이 흔들리며 공정 변동 증가."
        ),
        "category": "degradation",
        "severity": "LOW",
        "affected_steps": [
            {"step_id": "PS-105", "sensor": "speed", "severity": 1, "delay_ticks": 0,
             "degradation_ticks": 8},
            {"step_id": "PS-204", "sensor": "speed", "severity": 1, "delay_ticks": 2,
             "degradation_ticks": 8},
        ],
        "root_cause": "process_variation",
        "expected_yield_impact": -0.006,
    },

    # ──────────────────────────────────────────────────────────
    # SCN-013: 공압 시스템 압력 누설 (cascading, pressure_drop)
    # ──────────────────────────────────────────────────────────
    {
        "id": "SCN-013",
        "name": "공압 시스템 압력 누설",
        "description": (
            "공장 메인 압축기 → 라인 분배기 사이 호스 누설로 공압 압력 강하. "
            "크림핑 프레스와 클램핑 토크가 동시 영향."
        ),
        "category": "cascading",
        "severity": "HIGH",
        "affected_steps": [
            {"step_id": "PS-203", "sensor": "pressure", "severity": 2, "delay_ticks": 0},
            {"step_id": "PS-502", "sensor": "pressure", "severity": 2, "delay_ticks": 1},
        ],
        "root_cause": "pressure_drop",
        "expected_yield_impact": -0.016,
    },

    {
        "id": "SCN-008",
        "name": "전체 라인 환경 온도 상승",
        "description": (
            "여름철 공조 용량 부족으로 공장 전체 온도가 3~5도C 상승. "
            "전 공정의 온도 센서에 영향을 미치며, 특히 코팅/용접/검사 "
            "공정에서 품질 편차가 발생한다."
        ),
        "category": "environmental",
        "severity": "LOW",
        "affected_steps": [
            # 모든 공정 영역에서 온도 센서에 영향
            # 100 계열: 모듈 조립
            {"step_id": "PS-101", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            {"step_id": "PS-103", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            {"step_id": "PS-104", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            {"step_id": "PS-106", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            # 200 계열: BMS/하네스
            {"step_id": "PS-201", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            {"step_id": "PS-203", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            # 300 계열: 냉각 시스템
            {"step_id": "PS-301", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            {"step_id": "PS-303", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            # 400 계열: 인클로저
            {"step_id": "PS-401", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            {"step_id": "PS-402", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            {"step_id": "PS-404", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            # 500 계열: 최종 조립
            {"step_id": "PS-501", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            {"step_id": "PS-503", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
            {"step_id": "PS-504", "sensor": "temperature", "severity": 1, "delay_ticks": 0},
        ],
        "root_cause": "environmental_temperature",
        "expected_yield_impact": -0.025,
    },
    # ─────────────────────────────────────────────────────────────────
    # 다양성 강화 시나리오 (severity 균형 + 외부 disruption + 시간대 변동)
    # ─────────────────────────────────────────────────────────────────
    {
        "id": "SCN-009",
        "name": "자재 LOT 변경 — 신규 셀 입고",
        "description": (
            "공급사 LOT 교체로 셀 두께/내부저항 분포가 미세하게 변경. "
            "초기 입고 검사부터 모듈 조립까지 부드러운 편차로 전파. "
            "외부(공급망)에서 유입되는 disruption."
        ),
        "category": "external",
        "severity": "MEDIUM",
        "affected_steps": [
            {"step_id": "PS-101", "sensor": "thickness", "severity": 2, "delay_ticks": 0},
            {"step_id": "PS-102", "sensor": "alignment", "severity": 1, "delay_ticks": 1,
             "drift_per_tick": 0.005},
            {"step_id": "PS-104", "sensor": "current", "severity": 1, "delay_ticks": 3,
             "drift_per_tick": 0.003},
        ],
        "root_cause": "material_lot_change",
        "expected_yield_impact": -0.012,
    },
    {
        "id": "SCN-010",
        "name": "야간 운영 저강도 변동",
        "description": (
            "야간 무인 운영 시 기온 하강으로 모든 센서가 약하게 drift. "
            "공정 영향은 미미하지만 검출 임계 근처에서 oscillate."
        ),
        "category": "environmental",
        "severity": "LOW",
        "affected_steps": [
            {"step_id": "PS-301", "sensor": "temperature", "severity": 1, "delay_ticks": 0,
             "drift_per_tick": 0.002},
            {"step_id": "PS-401", "sensor": "temperature", "severity": 1, "delay_ticks": 0,
             "drift_per_tick": 0.002},
            {"step_id": "PS-503", "sensor": "temperature", "severity": 1, "delay_ticks": 0,
             "drift_per_tick": 0.002},
        ],
        "root_cause": "environmental_temperature",
        "expected_yield_impact": -0.003,
    },
    {
        "id": "SCN-011",
        "name": "교대 인계 트랜지션",
        "description": (
            "교대 시점에 일부 라인이 일시적 idle → restart로 setpoint 재정렬. "
            "짧은 기간(2~3 tick) LOW severity 이상이 다중 영역에 동시 발생."
        ),
        "category": "transient",
        "severity": "LOW",
        "affected_steps": [
            {"step_id": "PS-105", "sensor": "speed", "severity": 1, "delay_ticks": 0},
            {"step_id": "PS-202", "sensor": "current", "severity": 1, "delay_ticks": 1},
            {"step_id": "PS-501", "sensor": "torque_force", "severity": 1, "delay_ticks": 1},
        ],
        "root_cause": "shift_transition",
        "expected_yield_impact": -0.005,
    },
    {
        "id": "SCN-012",
        "name": "다영역 동시 장애 — 자재+공조 복합",
        "description": (
            "자재 LOT 편차와 공조 출력 저하가 동시 발생하여 5개 공정 영역에 "
            "동시 영향. 단일 인과로 설명 불가능한 multi-root 시나리오."
        ),
        "category": "multi_root",
        "severity": "HIGH",
        "affected_steps": [
            {"step_id": "PS-101", "sensor": "thickness", "severity": 2, "delay_ticks": 0},
            {"step_id": "PS-203", "sensor": "torque_force", "severity": 2, "delay_ticks": 1},
            {"step_id": "PS-301", "sensor": "temperature", "severity": 2, "delay_ticks": 1},
            {"step_id": "PS-404", "sensor": "humidity", "severity": 2, "delay_ticks": 2},
            {"step_id": "PS-505", "sensor": "alignment", "severity": 1, "delay_ticks": 3},
        ],
        "root_cause": "multi_root_complex",
        "expected_yield_impact": -0.030,
    },
    {
        "id": "SCN-013",
        "name": "장비 누적 마모 — 베어링 drift",
        "description": (
            "고속 회전 장비의 베어링이 정비주기 후반 진입. "
            "vibration/torque 점진적 drift, MTBF 임계 접근 시그널."
        ),
        "category": "degradation",
        "severity": "LOW",
        "affected_steps": [
            {"step_id": "PS-204", "sensor": "vibration", "severity": 1, "delay_ticks": 0,
             "drift_per_tick": 0.004},
            {"step_id": "PS-204", "sensor": "torque_force", "severity": 1, "delay_ticks": 1,
             "drift_per_tick": 0.003},
        ],
        "root_cause": "bearing_wear",
        "expected_yield_impact": -0.006,
    },
    {
        "id": "SCN-014",
        "name": "품질 batch 편차 — 코팅 균질성",
        "description": (
            "코팅 화학 batch 교체 후 두께 균질성에 미세 편차. "
            "PS-404 표면처리에서 검사 데이터 산포 확대."
        ),
        "category": "external",
        "severity": "MEDIUM",
        "affected_steps": [
            {"step_id": "PS-404", "sensor": "thickness", "severity": 2, "delay_ticks": 0},
            {"step_id": "PS-405", "sensor": "alignment", "severity": 1, "delay_ticks": 2},
        ],
        "root_cause": "batch_variance",
        "expected_yield_impact": -0.014,
    },
    {
        "id": "SCN-015",
        "name": "전력 dip — 일시적 전류 변동",
        "description": (
            "외부 전력망에서 짧은 dip 발생, 용접/충전 공정의 전류 센서가 "
            "단발성 spike. 즉각 회복되지만 품질 영향 가능."
        ),
        "category": "external",
        "severity": "MEDIUM",
        "affected_steps": [
            {"step_id": "PS-202", "sensor": "current", "severity": 2, "delay_ticks": 0},
            {"step_id": "PS-503", "sensor": "current", "severity": 2, "delay_ticks": 0},
        ],
        "root_cause": "power_disturbance",
        "expected_yield_impact": -0.008,
    },
]


# ═══════════════════════════════════════════════════════════════
#  Active Scenario Tracker
# ═══════════════════════════════════════════════════════════════

@dataclass
class _ActiveScenario:
    """실행 중인 시나리오의 내부 상태를 추적한다."""

    scenario: dict[str, Any]
    elapsed_ticks: int = 0
    injected_steps: set = field(default_factory=set)
    degradation_progress: dict = field(default_factory=dict)
    completed: bool = False
    activated_at: str = ""


# ═══════════════════════════════════════════════════════════════
#  ScenarioEngine
# ═══════════════════════════════════════════════════════════════

class ScenarioEngine:
    """EV 배터리팩 제조 특화 장애 시나리오 엔진.

    실제 제조 현장에서 발생하는 장애 패턴을 시뮬레이션한다:
    - 단일 장애: 한 공정의 한 센서 이상
    - 연쇄 장애: 상류 공정 문제가 하류로 전파
    - 자재 열화: 시간이 지남에 따라 점진적 악화
    - 환경 변동: 외부 요인(온도, 습도)에 의한 전체 영향
    """

    # 같은 시나리오 재활성 차단 기간 (tick 단위). 다양성 강화 + 시각적 변화 유도.
    COOLDOWN_TICKS = 8

    def __init__(self, sensor_sim: "SensorSimulator") -> None:
        """
        Parameters
        ----------
        sensor_sim : SensorSimulator
            이상을 주입할 센서 시뮬레이터 인스턴스.
        """
        self.sensor_sim = sensor_sim

        # 활성화 카운트 — 다양성 가중 weighted random에 사용
        self._activate_count: dict[str, int] = {}
        # scenario_id -> _ActiveScenario
        self._active: dict[str, _ActiveScenario] = {}

        # 완료된 시나리오 이력
        self._history: list[dict[str, Any]] = []

        # id -> scenario dict 조회용 인덱스
        self._library_index: dict[str, dict[str, Any]] = {
            s["id"]: s for s in SCENARIO_LIBRARY
        }

        # scenario_id -> 마지막 종료/활성 tick 카운터 (cooldown용)
        self._last_seen_tick: dict[str, int] = {}
        self._tick_counter: int = 0

    # ── Public API ───────────────────────────────────────────

    def get_scenario_library(self) -> list[dict[str, Any]]:
        """전체 시나리오 라이브러리를 반환한다."""
        return copy.deepcopy(SCENARIO_LIBRARY)

    def activate_scenario(self, scenario_id: str) -> dict[str, Any] | None:
        """시나리오를 활성화하여 실행 큐에 등록한다.

        Parameters
        ----------
        scenario_id : str
            활성화할 시나리오 ID (예: ``"SCN-001"``).

        Returns
        -------
        dict or None
            활성화된 시나리오 정보. 이미 활성 중이거나 존재하지 않으면 None.
        """
        if scenario_id in self._active:
            return None  # 이미 실행 중

        scenario = self._library_index.get(scenario_id)
        if scenario is None:
            return None  # 알 수 없는 시나리오

        scenario_copy = copy.deepcopy(scenario)

        # cascading 시나리오: delay_ticks를 물리적 거리 기반으로 재계��
        if scenario_copy["category"] == "cascading" and len(scenario_copy["affected_steps"]) > 1:
            origin_step = scenario_copy["affected_steps"][0]["step_id"]
            for step_effect in scenario_copy["affected_steps"]:
                if step_effect["delay_ticks"] == 0:
                    continue  # 원점은 그대로
                step_effect["delay_ticks"] = physical_delay(origin_step, step_effect["step_id"])

        active = _ActiveScenario(
            scenario=scenario_copy,
            activated_at=datetime.now(timezone.utc).isoformat(),
        )

        # degradation 타입이면 진행 카운터 초기화
        if scenario["category"] == "degradation":
            for i, step_effect in enumerate(scenario["affected_steps"]):
                if step_effect.get("degradation_ticks"):
                    active.degradation_progress[i] = 0  # 현재 진행도

        self._active[scenario_id] = active
        # cooldown tracker 갱신 — 활성 시점 기록
        self._last_seen_tick[scenario_id] = self._tick_counter
        return {
            "scenario_id": scenario_id,
            "name": scenario["name"],
            "category": scenario["category"],
            "severity": scenario["severity"],
            "affected_steps_count": len(scenario["affected_steps"]),
        }

    def activate_random(self) -> dict[str, Any] | None:
        """가중 무작위 시나리오 활성화 — 다양성 보장.

        - 이미 활성 상태인 시나리오는 제외
        - cooldown(COOLDOWN_TICKS) 안에 종료/시작된 시나리오는 제외
        - **활성화 횟수 역수 가중** (적게 발화한 시나리오 우선) — sim 다양성 ↑
        - cooldown 통과 후보 없으면 cooldown 무시하고 가중 선택 (fallback)
        """
        in_cooldown = {
            sid for sid, last in self._last_seen_tick.items()
            if self._tick_counter - last < self.COOLDOWN_TICKS
        }
        available = [
            sid for sid in self._library_index
            if sid not in self._active and sid not in in_cooldown
        ]
        if not available:
            available = [sid for sid in self._library_index if sid not in self._active]
        if not available:
            return None

        # weighted random: weight = 1 / (1 + activate_count) — 적게 발화한 시나리오가 더 자주 뽑힘
        weights = [1.0 / (1 + self._activate_count.get(sid, 0)) for sid in available]
        total = sum(weights)
        if total <= 0:
            chosen = random.choice(available)
        else:
            r = random.random() * total
            acc = 0.0
            chosen = available[-1]
            for sid, w in zip(available, weights):
                acc += w
                if r <= acc:
                    chosen = sid
                    break

        self._activate_count[chosen] = self._activate_count.get(chosen, 0) + 1
        return self.activate_scenario(chosen)

    def tick(self) -> list[dict[str, Any]]:
        """시간을 1 tick 전진시키고, 활성 시나리오의 이상을 주입한다.

        각 활성 시나리오의 ``affected_steps`` 를 순회하며:

        1. ``delay_ticks`` 가 도래한 단계에 ``sensor_sim.inject_anomaly()`` 호출
        2. ``degradation`` 타입이면 tick 마다 severity 를 점진적으로 증가
        3. 모든 효과가 주입 완료되면 시나리오를 종료하고 이력에 기록

        Returns
        -------
        list[dict]
            이번 tick 에서 실제로 주입된 효과 목록.
        """
        effects_this_tick: list[dict[str, Any]] = []
        completed_ids: list[str] = []
        self._tick_counter += 1

        for scenario_id, active in self._active.items():
            scenario = active.scenario
            category = scenario["category"]
            active.elapsed_ticks += 1
            elapsed = active.elapsed_ticks

            all_done = True

            for i, step_effect in enumerate(scenario["affected_steps"]):
                step_id = step_effect["step_id"]
                sensor = step_effect["sensor"]
                base_severity = step_effect["severity"]
                delay = step_effect["delay_ticks"]
                degradation_ticks = step_effect.get("degradation_ticks")
                effect_key = f"{i}:{step_id}:{sensor}"

                # ── delay 가 아직 도래하지 않았으면 skip ──
                if elapsed <= delay:
                    all_done = False
                    continue

                ticks_since_start = elapsed - delay  # 이 효과가 시작된 이후 경과 tick

                # ── degradation 타입: 점진적 severity 증가 ──
                if category == "degradation" and degradation_ticks:
                    if i in active.degradation_progress:
                        progress = active.degradation_progress[i]
                        if progress < degradation_ticks:
                            # severity: 1 에서 시작하여 degradation_ticks 에 걸쳐
                            # base_severity 의 최대 3배까지 선형 증가
                            fraction = (progress + 1) / degradation_ticks
                            current_severity = max(1, min(3, round(
                                base_severity * (0.5 + 1.5 * fraction)
                            )))

                            self.sensor_sim.inject_anomaly(
                                step_id, sensor, current_severity,
                            )
                            effects_this_tick.append({
                                "scenario_id": scenario_id,
                                "scenario_name": scenario["name"],
                                "step_id": step_id,
                                "sensor": sensor,
                                "severity": current_severity,
                                "type": "degradation",
                                "progress": f"{progress + 1}/{degradation_ticks}",
                            })
                            active.degradation_progress[i] = progress + 1
                            all_done = False
                            continue
                        else:
                            # degradation 완료
                            active.injected_steps.add(effect_key)
                            continue
                    # degradation_progress 에 없으면 이미 완료
                    continue

                # ── single / cascading / environmental: 1회 주입 ──
                if effect_key not in active.injected_steps:
                    self.sensor_sim.inject_anomaly(
                        step_id, sensor, base_severity,
                    )
                    active.injected_steps.add(effect_key)

                    effects_this_tick.append({
                        "scenario_id": scenario_id,
                        "scenario_name": scenario["name"],
                        "step_id": step_id,
                        "sensor": sensor,
                        "severity": base_severity,
                        "type": category,
                        "progress": "injected",
                    })

            # ── 시나리오 완료 여부 판정 ──
            if all_done:
                # 모든 효과가 주입(또는 degradation 완료) 되었는가?
                total_effects = len(scenario["affected_steps"])
                injected_count = len(active.injected_steps)
                # degradation 진행 중인 것이 없으면 완료
                degradation_pending = any(
                    active.degradation_progress.get(i, degradation_ticks or 0)
                    < (step_effect.get("degradation_ticks") or 0)
                    for i, step_effect in enumerate(scenario["affected_steps"])
                    if step_effect.get("degradation_ticks")
                )
                if injected_count >= total_effects and not degradation_pending:
                    active.completed = True
                    completed_ids.append(scenario_id)

        # ── 완료된 시나리오를 이력으로 이동 ──
        for scenario_id in completed_ids:
            active = self._active.pop(scenario_id)
            # cooldown tracker 갱신 — 종료 시점부터 cooldown 시작
            self._last_seen_tick[scenario_id] = self._tick_counter
            self._history.append({
                "scenario_id": scenario_id,
                "name": active.scenario["name"],
                "category": active.scenario["category"],
                "severity": active.scenario["severity"],
                "root_cause": active.scenario["root_cause"],
                "expected_yield_impact": active.scenario["expected_yield_impact"],
                "total_ticks": active.elapsed_ticks,
                "effects_injected": len(active.injected_steps),
                "activated_at": active.activated_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })

        return effects_this_tick

    def get_active_scenarios(self) -> list[dict[str, Any]]:
        """현재 활성 상태인 시나리오 목록과 진행 상황을 반환한다.

        Returns
        -------
        list[dict]
            각 활성 시나리오의 상태 정보.
        """
        result = []
        for scenario_id, active in self._active.items():
            scenario = active.scenario
            total_effects = len(scenario["affected_steps"])
            injected_count = len(active.injected_steps)

            # degradation 진행 상황 요약
            degradation_info = {}
            for i, progress in active.degradation_progress.items():
                step_effect = scenario["affected_steps"][i]
                degradation_info[step_effect["step_id"]] = {
                    "sensor": step_effect["sensor"],
                    "progress": progress,
                    "total": step_effect.get("degradation_ticks", 0),
                }

            result.append({
                "scenario_id": scenario_id,
                "name": scenario["name"],
                "category": scenario["category"],
                "severity": scenario["severity"],
                "root_cause": scenario["root_cause"],
                "elapsed_ticks": active.elapsed_ticks,
                "effects_injected": injected_count,
                "total_effects": total_effects,
                "degradation": degradation_info if degradation_info else None,
                "activated_at": active.activated_at,
            })

        return result

    def get_scenario_history(self) -> list[dict[str, Any]]:
        """완료된 시나리오 이력을 반환한다.

        Returns
        -------
        list[dict]
            완료된 시나리오 기록. 최근 것이 마지막.
        """
        return list(self._history)

    def adapt_difficulty(self, metrics: dict) -> dict[str, Any]:
        """Adapt scenario difficulty based on current recovery performance.

        If recovery rate > 80%, increase severity to challenge the system.
        If recovery rate < 40%, decrease severity to let it stabilize.

        Parameters
        ----------
        metrics : dict
            Should contain 'recovery_rate' (0..1) or 'auto_recovered' and 'total_incidents'.

        Returns
        -------
        dict
            Summary of difficulty adjustments made.
        """
        recovery_rate = metrics.get("recovery_rate")
        if recovery_rate is None:
            total = metrics.get("total_incidents", 0)
            recovered = metrics.get("auto_recovered", 0)
            recovery_rate = recovered / max(total, 1)

        adjustments = []

        for scenario in SCENARIO_LIBRARY:
            for step_effect in scenario["affected_steps"]:
                old_severity = step_effect["severity"]
                if recovery_rate > 0.80:
                    # Increase difficulty: bump severity up (max 3)
                    step_effect["severity"] = min(3, old_severity + 1)
                elif recovery_rate < 0.40:
                    # Decrease difficulty: reduce severity (min 1)
                    step_effect["severity"] = max(1, old_severity - 1)
                else:
                    continue

                if step_effect["severity"] != old_severity:
                    adjustments.append({
                        "scenario_id": scenario["id"],
                        "step_id": step_effect["step_id"],
                        "old_severity": old_severity,
                        "new_severity": step_effect["severity"],
                    })

        # Rebuild library index
        self._library_index = {s["id"]: s for s in SCENARIO_LIBRARY}

        return {
            "recovery_rate": round(recovery_rate, 3),
            "direction": "harder" if recovery_rate > 0.80 else ("easier" if recovery_rate < 0.40 else "unchanged"),
            "adjustments": len(adjustments),
            "details": adjustments[:10],
        }
