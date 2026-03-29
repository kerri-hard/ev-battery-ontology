# EV Battery AIOps 발표 대본

발표자료: `EV_Battery_AIOps_Research_Brief_2026-03-29.pptx`
발표일: 2026-03-29

## Slide 1. 타이틀
안녕하세요. 오늘은 EV 배터리 제조 공정을 대상으로, 인과추론과 LLM을 결합한 자율복구형 AIOps 플랫폼을 소개드리겠습니다. 핵심은 사람이 항상 모니터링하지 않아도 시스템이 감지, 진단, 복구, 학습을 반복하는 Dark Factory 방향입니다.

## Slide 2. 문제 정의
기존 제조 현장은 이상 발생 시 원인 분석과 대응이 사람에게 집중됩니다. 그 결과 대응 속도와 품질 편차가 크고, 동일 장애가 재발해도 조직적 학습이 어렵습니다. 저희는 장애 이력을 그래프 지식으로 구조화해 재발 대응력을 높이는 방식으로 접근했습니다.

## Slide 3. 연구 근거
설계는 2024~2026 최신 연구를 직접 반영했습니다. KG+DT 융합, KG 기반 고장 진단, Hybrid Agentic AI, FD-LLM, Self-Evolving Agent까지 각 논문의 핵심 인사이트를 시스템 구조에 매핑했습니다.

## Slide 4. 아키텍처
구조는 Physical Twin, Knowledge Graph, Cognitive Agents의 3축입니다. 센서 데이터가 들어오면 온톨로지가 문맥과 인과 관계를 제공하고, 에이전트가 자율복구 루프를 실행합니다. 이 루프가 시스템의 핵심 실행 엔진입니다.

## Slide 5. 현재 구현
Phase1~2는 완료했고, L3 인과추론 계층을 실제 운영 루프에 연결했습니다. Incident/RecoveryAction과 L3 트렌드 데이터를 영속화했고, 대시보드에는 인과 흐름과 케이스 상세를 실시간으로 표시합니다. 즉, 연구 방향이 화면에서 바로 검증되도록 만들었습니다.

## Slide 6. 인과추론 핵심
RCA는 단순 거리 기반이 아니라 인과 체인과 과거 FailureChain 매칭으로 confidence를 보정합니다. 복구 결과는 다시 confirmation_count와 관계 업데이트로 반영되어, 시간이 갈수록 진단 정확도가 좋아지는 구조입니다.

## Slide 7. LLM 하이브리드
Phase4에서는 LLM을 전략 질의 해석에 사용하고, 실행은 여전히 빠른 edge agent가 담당합니다. NaturalLanguageDiagnoser는 JSON Schema 기반으로 안전하게 결과를 생성하고, LLM 호출 실패 시에도 symbolic 분석으로 즉시 폴백합니다.

## Slide 8. 데모 플로우
이상 발생 후 감지-진단-복구-검증-학습까지 한 사이클을 실행하고, 운영자는 자연어 질의로 근거와 권고를 확인할 수 있습니다. 즉 자동화와 설명가능성을 동시에 제공합니다.

## Slide 9. KPI
운영 KPI는 복구율, MTTR, 재발률, 수율 개선입니다. 지식 KPI는 L3 링크 증가량, FailureChain 적중률, CausalRule 확인횟수입니다. AI KPI는 질의 신뢰도, HITL 전환율, 비용 대비 효과입니다.

## Slide 10. 남은 과제
남은 핵심은 RUL 고도화(LSTM/Transformer), HITL 정책 엔진, MQTT/OPC-UA 연계, 라인 재편성 오케스트레이터, 그리고 EvolutionAgent 구현입니다. 이 부분이 L4 Dark Factory로 가는 필수 단계입니다.

## Slide 11. 결론
결론적으로 저희는 데이터 수집 중심이 아니라 인과 학습 중심의 제조 AIOps로 전환하고 있습니다. 인과추론과 LLM 하이브리드 구조를 기반으로, 자율성 레벨을 단계적으로 높여 실무에서 검증 가능한 Dark Factory를 구현하겠습니다.
