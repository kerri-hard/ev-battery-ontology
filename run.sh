#!/bin/bash
# EV Battery Manufacturing — Self-Healing Factory
#
# 사용법:
#   ./run.sh dev      → 개발 서버 (백엔드:8080 + Next.js:3000)
#   ./run.sh live     → 백엔드만 (http://localhost:8080)
#   ./run.sh v3       → 배치 하네스 v3 실행
#   ./run.sh install  → 의존성 설치

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

install_deps() {
    echo -e "${YELLOW}의존성 설치 중...${NC}"
    pip install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt --break-system-packages --quiet
    cd web && npm install
    echo -e "${GREEN}설치 완료${NC}"
}

run_v3() {
    echo -e "${YELLOW}Harness Loop v3 (Multi-Agent Debate) 실행 중...${NC}"
    rm -f kuzu_v3_db kuzu_v3_db.wal
    python src/harness_v3.py
    echo -e "${GREEN}v3 완료! 결과: results/harness_v3_results.json${NC}"
}

live() {
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Self-Healing Factory Server${NC}"
    echo -e "${GREEN}  http://localhost:${1:-8080}${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    rm -f kuzu_v4_live kuzu_v4_live.wal
    python server.py --port "${1:-8080}"
}

dev() {
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    echo -e "${GREEN}  개발 서버 시작 (백엔드 + 프론트엔드)${NC}"
    echo -e "${GREEN}  Backend  : http://localhost:8080${NC}"
    echo -e "${GREEN}  Frontend : http://localhost:3000${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    rm -f kuzu_v4_live kuzu_v4_live.wal
    python server.py --port 8080 &
    BACKEND_PID=$!
    cd web && npm run dev &
    FRONTEND_PID=$!
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
    wait
}

case "${1:-}" in
    install)
        install_deps
        ;;
    v3)
        run_v3
        ;;
    live)
        shift
        live "$@"
        ;;
    dev)
        dev
        ;;
    "")
        echo -e "${YELLOW}═══════════════════════════════════════════${NC}"
        echo -e "${YELLOW}  EV Battery — Self-Healing Factory${NC}"
        echo -e "${YELLOW}═══════════════════════════════════════════${NC}"
        echo ""
        echo "사용법:"
        echo "  ./run.sh dev      - 개발 서버 (백엔드:8080 + Next.js:3000)"
        echo "  ./run.sh live     - 백엔드 서버 (http://localhost:8080)"
        echo "  ./run.sh v3       - 배치 하네스 v3 실행"
        echo "  ./run.sh install  - 의존성 설치"
        echo ""
        ;;
    *)
        echo -e "${RED}알 수 없는 명령: $1${NC}"
        echo "사용법: ./run.sh [dev|live|v3|install]"
        exit 1
        ;;
esac
