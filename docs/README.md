# 📁 docs/

본 저장소의 문서 디렉토리. 두 종류의 진입점이 있습니다.

| 디렉토리 | 용도 | 누가 보나 |
|---|---|---|
| [`handbook/`](./handbook/00-toc.md) | **저장소 내부 원본 핸드북** (10 챕터 + 표지, 코드 디테일 포함) | 신규 합류 개발자, 코드 기여자 |
| [`blog-essays/`](./blog-essays/README.md) | **자율 제조 사상 시리즈** (5편, 코드 디테일 없음) | 비전·용어·사상에 관심 있는 외부 독자 |

---

## 두 디렉토리의 차이

| 항목 | `handbook/` | `blog-essays/` |
|---|---|---|
| 무엇 | 코드 베이스 가이드 (구현 안내) | 자율 제조 사상 글 |
| 코드 디테일 | ✓ (파일/함수/API) | ✗ (사상만) |
| 대상 독자 | 저장소 안에서 읽는 개발자 | 네이버 블로그 등 외부 독자 |
| prev/next 네비 | ✓ (← / →) | 시리즈 헤더/푸터 박스 |
| 외부 링크 | 상대 경로 | 제거 (네이버 호환) |
| 분량 | 11 파일 | 5 파일 + README |

`handbook/` 는 저장소 내부에서 읽기 위한 *내부 문서*, `blog-essays/` 는 외부 블로그 게시를 위한 *공개 글* 입니다. 두 디렉토리는 *다른 독자*를 겨냥하므로 따로 작성·관리합니다.

---

## 산업 분석 자료

| 파일 | 내용 |
|---|---|
| [`industry_analysis.md`](./industry_analysis.md) | 제조업 AIOps / 다크 팩토리 시장 동향 |

---

## 진실 출처 (저장소 루트)

| 출처 | 역할 |
|---|---|
| [`VISION.md`](https://github.com/kerri-hard/ev-battery-ontology/blob/main/VISION.md) | 다크 팩토리 5단계 로드맵 + 9 설계 철학 |
| [`ARCHITECTURE.md`](https://github.com/kerri-hard/ev-battery-ontology/blob/main/ARCHITECTURE.md) | 시스템 동작/모듈 맵/7-페이즈 루프 |
| [`CLAUDE.md`](https://github.com/kerri-hard/ev-battery-ontology/blob/main/CLAUDE.md) | 개발 가이드 (에이전트 하네스용) |
| [`README.md`](https://github.com/kerri-hard/ev-battery-ontology/blob/main/README.md) | 빠른 시작 |

이 4 문서가 충돌의 진실. `docs/` 의 어떤 내용과 충돌해도 위 4 문서 + 코드가 우선합니다.
