"""연구→개선→테스트→검증 자동 사이클 패키지.

CLI 진입점은 `v4.research_loop:run_research_loop`. 본 패키지는 구성 요소만 제공.

- metrics.MetricsCollector — 라운드별 메트릭 수집/비교/수렴 판정
- strategies — 6개 개선 전략 (임계값/인과/상관/플레이북/시나리오/재보정)
- simulation.run_simulation — 자율 복구 N회 실행 + 결과 집계
- db_setup.setup_db — Kuzu DB 초기화 + 시드 적재
"""
from v4.research.metrics import MetricsCollector, CONVERGENCE_DELTA, CONVERGENCE_WINDOW, REGRESSION_THRESHOLD
from v4.research import strategies
from v4.research.simulation import run_simulation
from v4.research.db_setup import setup_db

__all__ = [
    "MetricsCollector",
    "CONVERGENCE_DELTA",
    "CONVERGENCE_WINDOW",
    "REGRESSION_THRESHOLD",
    "strategies",
    "run_simulation",
    "setup_db",
]
