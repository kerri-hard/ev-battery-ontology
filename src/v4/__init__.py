"""
EV Battery Manufacturing Ontology — Harness Loop v4
=====================================================
Self-Healing Factory: 감지 → 진단 → 복구 → 검증 → 학습

v3 → v4 핵심 변경:
  v3: 에이전트가 온톨로지 자체를 개선 (오프라인)
  v4: 에이전트가 실시간 공장 이상을 감지/진단/복구 (온라인)

새 에이전트:
  - AnomalyDetector: SPC 기반 실시간 이상 감지
  - RootCauseAnalyzer: 온톨로지 경로 역추적 원인 진단
  - AutoRecoveryAgent: 파라미터 자동 보정

새 온톨로지 노드:
  - SensorReading: 실시간 센서값
  - Alarm: 이상 감지 알람
  - Incident: 장애 이력
  - RecoveryAction: 복구 조치 이력
"""
