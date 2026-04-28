# Ch.02 Quick Start — 5분 만에 첫 자동 복구 보기

← [01. Introduction](./01-introduction.md) | [목차](./00-toc.md) | 다음 → [03. Architecture](./03-architecture.md)

---

## 2.1 사전 준비물

| 항목 | 버전 | 비고 |
|---|---|---|
| Python | 3.11+ | 3.13 권장 |
| Node.js | 18+ | Next.js 14 빌드용 |
| OS | macOS / Linux | Windows는 WSL 권장 |
| Anthropic/OpenAI API key | 선택 | 없어도 오프라인 폴백 동작 |

> 그래프 DB는 **Kuzu (임베디드)** 라 별도 설치 불필요. 파이썬 패키지로 자동 다운로드.

---

## 2.2 첫 실행 (3단계)

### 단계 1 — 의존성 설치

```bash
git clone <repo>
cd ev-battery-ontology

# Python
pip install -r requirements.txt

# Frontend
cd web && npm install && cd ..
```

### 단계 2 — 개발 모드 시작

```bash
./run.sh dev
```

이 한 줄이 다음을 동시에 띄웁니다:
- 백엔드 (`server.py`) → http://localhost:8080
- 프론트엔드 (Next.js) → http://localhost:3000
- WebSocket (`ws://localhost:8080/ws`) → 실시간 이벤트 스트림

### 단계 3 — 브라우저 열기

http://localhost:3000

기본 진입 페이지는 **Healing**입니다. 좌측 사이드바에 6 페이지(Overview/Healing/SLO/Learning/Console/Settings)가 보이면 정상.

---

## 2.3 첫 incident 보기

자동 시뮬레이터가 5초마다 한 사이클을 돌리며 가상 센서 데이터를 생성합니다.

처음 30초 동안 **DETECT** 페이즈가 SPC 3-sigma 위반을 감지하면 우상단 토스트 알림이 뜹니다:

```
🔴 HIGH · PS-203 와이어 하네스 — drift detected
```

토스트 클릭 → Healing 페이지에서 해당 incident 카드가 강조됩니다. 5 섹션 워크벤치:

1. **Detect** — 어떤 센서가 어떤 임계를 위반했는가
2. **Diagnose** — 인과 그래프 역추적 + RCA top-3 후보
3. **PRE-VERIFY** — 액션 시뮬레이션 결과 (success_prob, expected_delta)
4. **Recover** — 적용된 액션 + HITL 게이트 (필요 시 Approve/Reject inline)
5. **Verify + Learn** — 사후 yield 측정, FailureChain 매칭

대부분 1분 안에 5 섹션이 채워지면서 **자동 복구 완료** 표시.

---

## 2.4 키보드 단축키

브라우저 안에서:

| 키 | 동작 |
|---|---|
| `?` | 도움말 모달 |
| `g o` | Overview |
| `g h` | Healing |
| `g s` | SLO |
| `g l` | Learning |
| `g c` | Console |
| `Esc` | 선택 해제 |

`g`는 leader 키. 누른 후 1초 안에 두 번째 키 입력.

---

## 2.5 시나리오 강제 트리거 (Sim Control)

좌측 사이드바 아래 **Sim Control** 패널:

1. severity 필터 (HIGH/MEDIUM/LOW/ALL)
2. 20 시나리오 dropdown — 예: `SCN-001 cooling degradation`
3. **Trigger** 버튼

3-5초 안에 해당 시나리오가 활성화되며 관련 step에서 incident가 발생.

**활성화 카운트(×N)** 가 시나리오 옆에 표시됩니다 — 가중 랜덤이 적게 본 시나리오를 우선 활성화하므로 다양성 확보.

---

## 2.6 다른 모드들

| 명령 | 용도 |
|---|---|
| `./run.sh dev` | 개발 표준 (백엔드+프론트엔드) |
| `./run.sh live` | 백엔드만 (HTML 대시보드 포함) |
| `./run.sh v3` | v3 멀티 에이전트 토론 배치 (CLI 출력) |

---

## 2.7 백테스트 (회귀 가드)

코드를 변경했다면 PR 전 다음을 실행:

```bash
python scripts/backtest.py --snapshot results/self_healing_v4_latest.json
```

출력에서 다음 4 메트릭이 임계 안에 있어야 통과:

| 메트릭 | 임계 | 의미 |
|---|---|---|
| `decision_match_rate` | ≥ 0.55 | 재실행 시 같은 결정 |
| `brier_score` | ≤ 0.10 | 확률 예측 오차 |
| `ECE` | ≤ 0.30 | 캘리브레이션 오차 |
| `drift_warnings` | ≤ 5 | 분포 변화 경고 |

GitHub Actions의 [`.github/workflows/backtest.yml`](../../.github/workflows/backtest.yml)이 PR마다 자동으로 위 게이트를 실행합니다.

---

## 2.8 자주 만나는 첫 문제

| 증상 | 원인 | 해결 |
|---|---|---|
| 8080 포트 충돌 | 백엔드 이미 실행 | `lsof -i :8080` 후 kill |
| 프론트 화면 빈 채로 멈춤 | WebSocket 연결 실패 | 우상단 ConnectionDot 확인. 백엔드 재시작 |
| 토스트 안 뜸 | Sim 사이클 시작 전 | 30초 대기 또는 Sim Control로 강제 trigger |
| LLM 호출 에러 | API key 없음 | `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY` 환경변수 설정. 없으면 자동 오프라인 폴백 |

---

## 2.9 다음에 무엇을 읽을 것인가

이제 시스템을 *움직여 봤으니*, 다음 챕터는 *왜 이렇게 움직이는지* 입니다.

- 시스템 토폴로지 — [Ch.03 Architecture](./03-architecture.md)
- 7-페이즈 루프 자세히 — [Ch.05](./05-7phase-loop.md)
- 페이지/컴포넌트 카탈로그 — [Ch.07](./07-features.md)

---

← [01. Introduction](./01-introduction.md) | [목차](./00-toc.md) | 다음 → [03. Architecture](./03-architecture.md)
