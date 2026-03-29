#!/usr/bin/env python3
"""
EV Battery Pack Manufacturing Ontology — Harness Loop v3
=========================================================
Multi-Agent Debate System: 6종 전문 에이전트가 토론/투표로 온톨로지를 자율 개선

v2 → v3 핵심 변경점:
  ✅ 단일 전략 → 6종 전문 에이전트 (공정/품질/보전/자동화/공급망/안전)
  ✅ 고정 규칙 → 토론 프로토콜 (PROPOSE → CRITIQUE → VOTE)
  ✅ 단순 반복 → 신뢰도 가중 투표 (에이전트 신뢰도 동적 조정)
  ✅ 일회성 전략 → 14개 재사용 스킬 시스템
  ✅ 수동 평가 → 자가 학습 (성과 기반 신뢰도 업데이트)

사용법:
  python src/harness_v3.py
"""
import sys
import os

# 프로젝트 루트를 기준으로 실행
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from v3.harness import run_harness_loop

if __name__ == "__main__":
    run_harness_loop()
