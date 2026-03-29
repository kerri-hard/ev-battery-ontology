# EV Battery Manufacturing — Self-Healing Factory

제조 공정 온톨로지 + AIOps로 문제를 자동 감지/진단/복구하는 다크 팩토리 플랫폼.

> 문제가 생기면 AI가 원인을 찾고, 스스로 복구하며, 같은 장애가 재발하지 않도록 학습한다. [VISION.md](VISION.md)

## 빠른 시작

```bash
pip install -r requirements.txt
cd web && npm install && cd ..

./run.sh dev    # 백엔드(:8080) + Next.js(:3000) 동시 시작
```

http://localhost:3000 에서 온톨로지 그래프 + 자율 복구 시뮬레이션 확인.

## 아키텍처

```
Browser (:3000)  ←── WebSocket ──→  FastAPI (:8080)
Next.js + TypeScript                 SelfHealingEngine
                                     ├─ v3: 6 에이전트 온톨로지 개선
                                     ├─ v4: 감지→진단→복구→학습
                                     ├─ 14 스킬 + 56 가상 센서
                                     └─ Kuzu 그래프 DB
```

## 프로젝트 구조

```
├── server.py              # FastAPI 백엔드 (REST + WebSocket)
├── src/
│   ├── v3/                # 멀티 에이전트 토론 시스템 (6 에이전트, 14 스킬)
│   └── v4/                # 자율 복구 시스템 (센서 시뮬레이터, 3 복구 에이전트)
├── web/                   # Next.js 14 + TypeScript + Tailwind CSS
│   └── src/
│       ├── components/
│       │   ├── graph/     # 온톨로지 그래프 시각화 (force-directed SVG)
│       │   ├── issues/    # 실시간 이슈 패널
│       │   ├── agents/    # 에이전트 신뢰도
│       │   ├── debate/    # 토론 패널
│       │   ├── metrics/   # 메트릭 카드
│       │   └── controls/  # 제어판
│       ├── hooks/         # useHarnessEngine (WebSocket)
│       └── context/       # EngineContext
└── data/graph_data.json   # 제조 데이터 (5 공정영역, 31 스텝)
```

## 자율 복구 루프

```
① SENSE    센서 데이터 수집 (56개 가상 센서)
② DETECT   SPC 기반 이상 감지 (3-sigma, Western Electric)
③ DIAGNOSE 온톨로지 경로 역추적 원인 진단
④ RECOVER  자동 파라미터 보정 (5종 플레이북)
⑤ VERIFY   복구 효과 검증
⑥ LEARN    장애 이력 축적, 에이전트 학습
```

## 실행 결과

| 지표 | 초기 | v3 온톨로지 개선 후 | v4 자율 복구 후 |
|------|------|-------------------|----------------|
| 노드 | 83 | 270 | 270+ |
| 엣지 | 118 | 467 | 467+ |
| 수율 | 87.15% | 91.47% | 93.14% |
| 장애 감지 | — | — | 24건 |
| 자동 복구 | — | — | 24건 (100%) |
