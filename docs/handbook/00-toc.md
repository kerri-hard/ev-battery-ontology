# 개발자 핸드북 — EV Battery Pack 제조 AIOps 플랫폼

> "사람이 안 봐도 AI가 해결하는 다크 팩토리"를 만드는 개발자를 위한 책.

이 책은 본 저장소에 처음 합류한 개발자가 **무엇을 만들고 있는지(What)**, **왜 이렇게 설계했는지(Why)**, **어떻게 확장하는지(How)** 를 한 번에 이해하도록 정리한 핸드북입니다. 모든 챕터는 코드 진실(source of truth)에 직접 연결되어 있습니다.

---

## 누구를 위한 책인가

- **신규 합류 개발자** — 1주일 안에 새 컴포넌트/에이전트/스킬을 추가할 수 있을 정도의 이해를 목표
- **운영자/SRE 협업자** — SLI/SLO/HITL이 어떻게 흐르는지 알고 싶은 사람
- **아키텍트/연구자** — 인과 발견, 자가 진화, PRE-VERIFY 시뮬레이션의 설계 결정 배경이 궁금한 사람

원래 알고 있어야 하는 것: Python 기본, TypeScript/React 기본, 그래프 DB 개념, 제조/SRE 용어는 **Ch.10 용어집** 참고.

---

## 어떻게 읽는가

| 시나리오 | 권장 경로 |
|---|---|
| **30분 안에 큰 그림** | Ch.01 → Ch.02 → Ch.07 |
| **하루 안에 깊게** | Ch.01 → Ch.03 → Ch.05 → Ch.07 → Ch.10 |
| **코드 기여자** | Ch.04 (온톨로지) → Ch.06 (에이전트) → Ch.09 (개발법) |
| **운영/SLO 관심** | Ch.05 → Ch.07 → Ch.08 |
| **용어 사전이 필요할 때** | Ch.10 글로서리 |

---

## 목차

| # | 챕터 | 한 줄 요약 |
|---|---|---|
| 01 | [Introduction](./01-introduction.md) | 다크 팩토리 비전, EV 배터리 도메인, L1-L4 자율성 |
| 02 | [Quick Start](./02-quickstart.md) | 5분 만에 첫 incident 자동 복구 보기 |
| 03 | [Architecture](./03-architecture.md) | 백엔드 + 프론트 + 그래프DB 토폴로지와 데이터 흐름 |
| 04 | [Ontology](./04-ontology.md) | L1-L4 노드/관계 스키마 + Cypher 패턴 |
| 05 | [7-Phase Loop](./05-7phase-loop.md) | SENSE → DETECT → DIAGNOSE → PRE-VERIFY → RECOVER → VERIFY → LEARN |
| 06 | [Agents & Skills](./06-agents-skills.md) | 6 v3 에이전트 + 14 스킬 + 토론 프로토콜 |
| 07 | [Features](./07-features.md) | 6 페이지 × 컴포넌트 기능 카탈로그 |
| 08 | [SLO · Evolution · Recurrence](./08-slo-evolution-recurrence.md) | 5 SLI 측정, 8 진화 전략, 반복 방지 정책 |
| 09 | [Development](./09-development.md) | 새 에이전트/스킬/페이지/페이즈 추가 절차 + 백테스트 게이트 |
| 10 | [Glossary](./10-glossary.md) | 도메인/기술 용어 한↔영 사전 |

---

## 책의 출처와 갱신

이 핸드북은 다음 4 진실 출처(source of truth)를 정리한 것입니다:

| 출처 | 역할 | 본 책의 어떤 부분과 매핑 |
|---|---|---|
| [`VISION.md`](../../VISION.md) | 다크 팩토리 5단계 로드맵 + 9 설계 철학 | Ch.01, Ch.08 |
| [`ARCHITECTURE.md`](../../ARCHITECTURE.md) | 시스템 동작/모듈 맵/7-페이즈 루프 | Ch.03, Ch.05 |
| [`CLAUDE.md`](../../CLAUDE.md) | 개발 가이드 (에이전트 하네스용) | Ch.09 |
| [`README.md`](../../README.md) | 빠른 시작 | Ch.02 |

**갱신 정책**: 핵심 사실은 코드와 위 4 문서가 진실. 본 책은 *조망*과 *교육*이 목적. 두 곳이 충돌하면 코드 → 4 문서 → 본 책 순서로 신뢰합니다. 책 내용이 코드와 어긋나면 PR로 수정 부탁드립니다.

---

## 표기 규약

- **굵은 영문** = 약어 또는 핵심 용어 (Ch.10 글로서리에 정의됨)
- `monospace` = 코드 식별자, 파일 경로
- 🟢 = 권고/모범 사례, 🟡 = 주의, 🔴 = 절대 금지
- 한국어 주석 + 영문 식별자 = 본 프로젝트 표기 표준 (변경 금지)

---

다음 → [01. Introduction](./01-introduction.md)
