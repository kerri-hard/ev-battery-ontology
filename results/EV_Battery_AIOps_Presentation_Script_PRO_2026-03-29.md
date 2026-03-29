# EV Battery AIOps 발표 대본 (PRO)

발표자료: `EV_Battery_AIOps_Research_Brief_PRO_2026-03-29.pptx`
발표일: 2026-03-29
권장 발표시간: 12~15분

## Slide 1. Cover (40초)
오늘 발표는 EV 배터리 제조 공정을 대상으로, 인과추론과 LLM을 결합한 자율복구 AIOps 플랫폼의 연구-구현 결과를 공유드립니다. 목적은 대시보드 관제가 아니라, 사람 개입을 최소화한 Dark Factory 운영입니다.

## Slide 2. Executive Summary (60초)
핵심 메시지는 세 가지입니다. 첫째, 연구 논문 인사이트를 시스템 컴포넌트로 전환했습니다. 둘째, L3 인과추론과 자율복구 루프를 실제 동작시켰습니다. 셋째, Phase4에서 LLM을 안전하게 통합해 자연어 진단까지 확장했습니다.

## Slide 3. Research Map (70초)
Sensors 계열 연구는 KG+DT와 fault diagnosis의 타당성을 제공합니다. NAMRC 2026은 LLM 전략 계층과 edge 실행 계층 분리를 제안하고, FD-LLM은 자연어 진단 가능성을 확인해줍니다. 저희는 이 세 흐름을 하나의 운영 아키텍처로 통합했습니다.

## Slide 4. Architecture (70초)
Physical Twin에서 수집된 이벤트가 Knowledge Graph로 들어오고, Cognitive Agents가 의사결정을 수행합니다. 이때 그래프는 단순 저장소가 아니라 추론의 근거를 제공하는 실행 지식 베이스 역할을 합니다.

## Slide 5. Self-Healing Loop (80초)
루프는 SENSE, DETECT, DIAGNOSE, RECOVER, VERIFY, LEARN 순서입니다. 중요한 점은 LEARN이 마지막 단계가 아니라 다음 루프의 정확도를 끌어올리는 시작점이라는 점입니다.

## Slide 6. Causal Deep-Dive (80초)
이전에는 거리 기반 후보순위가 중심이었다면, 현재는 CausalRule과 FailureChain을 이용한 인과 기반 RCA를 수행합니다. 그래서 원인 설명성이 좋아지고, 반복 장애 대응 속도가 빨라집니다.

## Slide 7. Runtime Evidence (70초)
실행 결과에서 자동 복구율, 수율, 완성도, L3 지식 축적량을 함께 확인할 수 있습니다. Incident별 수율 개선 영향도도 시각화해 복구 조치의 실효성을 빠르게 점검합니다.

## Slide 8. LLM Hybrid (80초)
NaturalLanguageDiagnoser는 JSON schema 강제와 sanitize를 통해 안전한 응답을 반환합니다. 호출 실패 시 symbolic 모드로 즉시 폴백하므로, 운영 안정성을 해치지 않습니다. PredictiveAgent는 RUL 우선순위를 제공해 예지정비 의사결정을 보조합니다.

## Slide 9. Demo Storyboard (60초)
실제 시나리오는 이상 감지, 원인 진단, 복구 실행, 검증, 이력 학습 순서로 진행됩니다. 운영자는 마지막에 자연어 질의만으로 근거와 권고를 확인할 수 있습니다.

## Slide 10. Roadmap (70초)
다음 90일은 RUL 고도화, HITL 정책, 실설비 브리지, 재편성 오케스트레이터가 핵심입니다. 즉 기능 확장이 아니라, 운영 신뢰성을 높이는 단계입니다.

## Slide 11. Risk/Governance (60초)
자동화 성능만큼 중요한 것이 리스크 거버넌스입니다. 모델 리스크, 운영 리스크, 데이터 리스크를 분리해 관리하고, 고위험 조치에는 반드시 HITL 정책을 적용합니다.

## Slide 12. Closing (40초)
결론적으로, 이 시스템은 모니터링 도구를 넘어 인과 기반 자율복구 플랫폼으로 진화하고 있습니다. 연구와 현업 실행을 동시에 만족하는 아키텍처로 Dark Factory 전환을 가속하겠습니다.
