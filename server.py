#!/usr/bin/env python3
"""
EV Battery Manufacturing Ontology — Live Server
FastAPI + WebSocket 기반 실시간 하네스 시뮬레이션 서버.

사용법:
    python server.py              # localhost:8080
    python server.py --port 3000  # 포트 지정

API:
    GET  /                  → 대시보드
    GET  /api/state         → 현재 엔진 상태
    POST /api/init          → 엔진 초기화
    POST /api/run           → 자동 루프 실행
    POST /api/step          → 1회 반복 실행
    POST /api/pause         → 일시정지
    POST /api/resume        → 재개
    POST /api/speed         → 속도 변경
    POST /api/reset         → 리셋
    WS   /ws                → 실시간 이벤트 스트림
"""
import asyncio
import json
import os
import sys
import argparse

# 프로젝트 루트 설정
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from v4.engine import SelfHealingEngine

# ── App ───────────────────────────────────────────────────
app = FastAPI(title="EV Battery Ontology — Self-Healing Factory")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
engine = SelfHealingEngine(
    data_path=os.path.join(PROJECT_ROOT, "data", "graph_data.json"),
    db_path=os.path.join(PROJECT_ROOT, "kuzu_v4_live"),
)
SUPERVISOR_TOKEN = os.getenv("HITL_SUPERVISOR_TOKEN", "").strip()
ALLOW_INSECURE_SUPERVISOR = os.getenv("HITL_ALLOW_INSECURE_SUPERVISOR", "0").strip() == "1"

# WebSocket 클라이언트 관리
ws_clients: list[WebSocket] = []


async def broadcast(event_type: str, data: dict):
    """모든 WebSocket 클라이언트에게 이벤트를 전송한다."""
    message = json.dumps({"event": event_type, "data": data, "ts": asyncio.get_event_loop().time()}, ensure_ascii=False, default=str)
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)


def resolve_operator_role(requested_role: str, provided_token: str) -> str:
    role = (requested_role or "operator").strip().lower()
    if role != "supervisor":
        return "operator"
    # Secure-by-default: if token is not configured, supervisor is denied
    # unless explicitly allowed for local demo compatibility.
    if not SUPERVISOR_TOKEN:
        return "supervisor" if ALLOW_INSECURE_SUPERVISOR else "operator"
    return "supervisor" if (provided_token or "").strip() == SUPERVISOR_TOKEN else "operator"


# 엔진 이벤트를 WebSocket으로 중계
engine.add_listener(broadcast)


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse('<html><body style="background:#0a0a1a;color:#e0e0f0;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><h1>EV Battery — Self-Healing Factory API</h1><p>Frontend: <a href="http://localhost:3000" style="color:#00d2ff">http://localhost:3000</a></p><p>API: <a href="/api/state" style="color:#06d6a0">/api/state</a> | WebSocket: <code>ws://localhost:8080/ws</code></p></div></body></html>')


# ── REST API ──────────────────────────────────────────────

@app.get("/api/state")
async def get_state():
    return JSONResponse(engine.get_state())


@app.get("/api/graph")
async def get_graph():
    """온톨로지 그래프 데이터 (노드 + 엣지) — 프론트엔드 시각화용."""
    if not engine.conn:
        return JSONResponse({"nodes": [], "edges": []})
    try:
        nodes = []
        # ProcessSteps with current state
        r = engine.conn.execute("MATCH (ps:ProcessStep) RETURN ps.id, ps.name, ps.area_id, ps.yield_rate, ps.automation, ps.oee, ps.cycle_time, ps.safety_level, ps.equipment, ps.sigma_level")
        while r.has_next():
            row = r.get_next()
            nodes.append({"id": row[0], "type": "ProcessStep", "name": row[1], "area": row[2], "yield": round(float(row[3]), 4), "auto": row[3 + 1], "oee": round(float(row[5]), 3), "cycle": int(row[6]), "safety": row[7], "equipment": row[8], "sigma": round(float(row[9]), 2)})
        # Equipment
        r = engine.conn.execute("MATCH (eq:Equipment) RETURN eq.id, eq.name, eq.cost, eq.mtbf_hours, eq.mttr_hours")
        while r.has_next():
            row = r.get_next()
            nodes.append({"id": row[0], "type": "Equipment", "name": row[1], "cost": int(row[2]), "mtbf": float(row[3]), "mttr": float(row[4])})
        # DefectModes
        r = engine.conn.execute("MATCH (dm:DefectMode) RETURN dm.id, dm.name, dm.category, dm.rpn")
        while r.has_next():
            row = r.get_next()
            nodes.append({"id": row[0], "type": "DefectMode", "name": row[1], "category": row[2], "rpn": int(row[3])})
        # Alarms
        try:
            r = engine.conn.execute("MATCH (a:Alarm) WHERE a.resolved = false RETURN a.id, a.step_id, a.severity, a.sensor_type, a.message, a.timestamp")
            while r.has_next():
                row = r.get_next()
                nodes.append({"id": row[0], "type": "Alarm", "step_id": row[1], "severity": row[2], "sensor_type": row[3], "message": row[4], "timestamp": row[5]})
        except Exception:
            pass
        # CausalRules (L3)
        try:
            r = engine.conn.execute("MATCH (cr:CausalRule) RETURN cr.id, cr.name, cr.cause_type, cr.effect_type, cr.strength, cr.confirmation_count")
            while r.has_next():
                row = r.get_next()
                nodes.append({"id": row[0], "type": "CausalRule", "name": row[1], "cause_type": row[2], "effect_type": row[3], "strength": float(row[4]), "confirmations": int(row[5])})
        except Exception:
            pass
        # FailureChains (L3)
        try:
            r = engine.conn.execute("MATCH (fc:FailureChain) RETURN fc.id, fc.step_id, fc.cause_sequence, fc.success_count, fc.fail_count, fc.avg_recovery_sec")
            while r.has_next():
                row = r.get_next()
                nodes.append({"id": row[0], "type": "FailureChain", "step_id": row[1], "cause": row[2], "successes": int(row[3]), "failures": int(row[4]), "avg_sec": float(row[5])})
        except Exception:
            pass
        # Incidents (L2)
        try:
            r = engine.conn.execute("MATCH (inc:Incident) RETURN inc.id, inc.step_id, inc.root_cause, inc.recovery_action, inc.auto_recovered, inc.timestamp")
            while r.has_next():
                row = r.get_next()
                nodes.append({
                    "id": row[0],
                    "type": "Incident",
                    "step_id": row[1],
                    "root_cause": row[2],
                    "recovery_action": row[3],
                    "auto_recovered": bool(row[4]),
                    "timestamp": row[5],
                })
        except Exception:
            pass
        # RecoveryActions (L2)
        try:
            r = engine.conn.execute("MATCH (ra:RecoveryAction) RETURN ra.id, ra.action_type, ra.parameter, ra.success, ra.timestamp")
            while r.has_next():
                row = r.get_next()
                nodes.append({
                    "id": row[0],
                    "type": "RecoveryAction",
                    "action_type": row[1],
                    "parameter": row[2],
                    "success": bool(row[3]) if row[3] is not None else None,
                    "timestamp": row[4],
                })
        except Exception:
            pass
        # Edges
        edges = []
        for rel_type in [
            "NEXT_STEP",
            "FEEDS_INTO",
            "PARALLEL_WITH",
            "TRIGGERS_REWORK",
            "HAS_DEFECT",
            "INSPECTS",
            "DEPENDS_ON",
            "CAUSES",
            "MATCHED_BY",
            "CHAIN_USES",
            "HAS_CAUSE",
            "HAS_PATTERN",
            "CORRELATES_WITH",
        ]:
            try:
                r = engine.conn.execute(f"MATCH (a)-[r:{rel_type}]->(b) RETURN a.id, b.id")
                while r.has_next():
                    row = r.get_next()
                    edges.append({"source": row[0], "target": row[1], "type": rel_type})
            except Exception:
                pass
        return JSONResponse({"nodes": nodes, "edges": edges})
    except Exception as e:
        return JSONResponse({"nodes": [], "edges": [], "error": str(e)})


@app.get("/api/correlations")
async def get_correlations():
    """공정 간 상관관계 분석 결과."""
    if not hasattr(engine, 'correlation_analyzer') or not engine.correlation_analyzer:
        return JSONResponse({"correlations": [], "total": 0})
    all_corr = engine.correlation_analyzer.analyze_all()
    return JSONResponse({
        "correlations": all_corr[:20],
        "total": len(all_corr),
        "known_pairs": len(engine.correlation_analyzer.known_correlations),
    })


@app.get("/api/correlations/{step_id}")
async def get_step_correlations(step_id: str):
    """특정 공정의 상관관계."""
    if not hasattr(engine, 'correlation_analyzer') or not engine.correlation_analyzer:
        return JSONResponse({"step_id": step_id, "correlations": []})
    related = engine.correlation_analyzer.get_correlations_for_step(step_id)
    return JSONResponse({"step_id": step_id, "correlations": related})


@app.get("/api/l3-trend")
async def get_l3_trend():
    """L3 트렌드 히스토리 조회 (메모리 우선, 파일 폴백)."""
    if getattr(engine, "l3_trend_history", None):
        return JSONResponse({
            "history": engine.l3_trend_history[-120:],
            "latest": getattr(engine, "latest_l3_snapshot", {}),
        })

    history_path = os.path.join(PROJECT_ROOT, "results", "l3_trend_history.json")
    latest_path = os.path.join(PROJECT_ROOT, "results", "l3_trend_latest.json")
    history = []
    latest = {}
    try:
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
    except Exception:
        history = []
    try:
        if os.path.exists(latest_path):
            with open(latest_path, "r", encoding="utf-8") as f:
                latest = json.load(f)
    except Exception:
        latest = {}
    return JSONResponse({"history": history[-120:], "latest": latest})


@app.get("/api/predictive-rul")
async def get_predictive_rul(limit: int = 5):
    """PredictiveAgent 기반 RUL/리스크 랭킹 조회."""
    if not engine.conn:
        await engine.initialize()
    try:
        rows = engine.predictive_agent.rank_rul_risks_v1(engine.conn, limit=max(1, min(20, limit)))
        return JSONResponse({"items": rows})
    except Exception as e:
        return JSONResponse({"items": [], "error": str(e)})


@app.post("/api/nl-diagnose")
async def nl_diagnose(body: dict):
    """NaturalLanguageDiagnoser 기반 자연어 진단."""
    if not engine.conn:
        await engine.initialize()
    query = (body or {}).get("query", "")
    if not query:
        return JSONResponse({"error": "query is required"}, status_code=400)
    try:
        result = engine.nl_diagnoser.analyze(engine.conn, str(query))
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/phase4-status")
async def phase4_status():
    """Phase4 LLM/Predictive runtime status."""
    s = engine.get_state().get("phase4", {})
    return JSONResponse(s)


@app.post("/api/hitl/approve")
async def hitl_approve(body: dict):
    hitl_id = (body or {}).get("id")
    operator = (body or {}).get("operator", "operator")
    role = resolve_operator_role((body or {}).get("role", "operator"), (body or {}).get("supervisor_token", ""))
    if not hitl_id:
        return JSONResponse({"error": "id is required"}, status_code=400)
    res = await engine.resolve_hitl(str(hitl_id), True, str(operator), str(role))
    return JSONResponse(res)


@app.post("/api/hitl/reject")
async def hitl_reject(body: dict):
    hitl_id = (body or {}).get("id")
    operator = (body or {}).get("operator", "operator")
    role = resolve_operator_role((body or {}).get("role", "operator"), (body or {}).get("supervisor_token", ""))
    if not hitl_id:
        return JSONResponse({"error": "id is required"}, status_code=400)
    res = await engine.resolve_hitl(str(hitl_id), False, str(operator), str(role))
    return JSONResponse(res)


@app.get("/api/hitl/policy")
async def get_hitl_policy():
    return JSONResponse(engine.get_state().get("healing", {}).get("hitl_policy", {}))


@app.post("/api/hitl/policy")
async def set_hitl_policy(body: dict):
    req = body or {}
    operator = str(req.get("operator", "operator"))
    role = resolve_operator_role(str(req.get("role", "operator")), str(req.get("supervisor_token", "")))
    policy_patch = {
        "min_confidence": req.get("min_confidence"),
        "high_risk_threshold": req.get("high_risk_threshold"),
        "medium_requires_history": req.get("medium_requires_history"),
    }
    policy = await engine.update_hitl_policy(policy_patch, operator=operator, role=role)
    return JSONResponse({"policy": policy})


@app.get("/api/hitl/audit")
async def get_hitl_audit(limit: int = 50):
    healing = engine.get_state().get("healing", {})
    audit = healing.get("hitl_audit", [])
    lim = max(1, min(500, int(limit)))
    return JSONResponse({"items": audit[-lim:]})


@app.post("/api/agent/route")
async def agent_route(body: dict):
    """Hybrid orchestrator intent router."""
    if not engine.conn:
        await engine.initialize()
    intent = (body or {}).get("intent", "")
    payload = (body or {}).get("payload", {})
    if not intent:
        return JSONResponse({"error": "intent is required"}, status_code=400)
    try:
        out = await engine.route_intent(str(intent), payload if isinstance(payload, dict) else {})
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/causal-discovery")
async def get_causal_discovery():
    """Auto-discovered causal relationships."""
    if not engine.conn:
        await engine.initialize()
    if not hasattr(engine, 'causal_discovery') or not engine.causal_discovery:
        return JSONResponse({"discovered": [], "total": 0})
    return JSONResponse(engine.causal_discovery.get_status())


@app.get("/api/evolution-status")
async def get_evolution_status():
    """EvolutionAgent strategy fitness and history."""
    if not engine.conn:
        await engine.initialize()
    if not hasattr(engine, 'evolution_agent') or not engine.evolution_agent:
        return JSONResponse({"strategies": [], "cycles": 0})
    return JSONResponse(engine.evolution_agent.get_status())


@app.get("/api/orchestrator/status")
async def orchestrator_status():
    """LLM Orchestrator status and config."""
    if not hasattr(engine, 'llm_orchestrator') or not engine.llm_orchestrator:
        return JSONResponse({"enabled": False, "provider": "none"})
    return JSONResponse(engine.llm_orchestrator.get_status())


@app.get("/api/orchestrator/audit")
async def orchestrator_audit(limit: int = 50):
    """LLM Orchestrator decision audit log."""
    if not hasattr(engine, 'llm_orchestrator') or not engine.llm_orchestrator:
        return JSONResponse({"items": []})
    items = engine.llm_orchestrator.get_audit_log(limit=max(1, min(200, limit)))
    return JSONResponse({"items": items})


@app.get("/api/replay-eval")
async def replay_eval():
    """Offline replay-style policy sweep."""
    if not engine.conn:
        await engine.initialize()
    try:
        return JSONResponse(engine.evaluate_policy_variants())
    except Exception as e:
        return JSONResponse({"variants": [], "error": str(e)})


@app.post("/api/init")
async def init_engine():
    if engine.running:
        return JSONResponse({"error": "이미 실행 중"}, status_code=400)
    await engine.initialize()
    return JSONResponse({"status": "initialized", "metrics": engine.current_metrics})


@app.post("/api/run")
async def run_loop():
    if engine.running:
        return JSONResponse({"error": "이미 실행 중"}, status_code=400)
    if not engine.conn:
        await engine.initialize()
    asyncio.create_task(engine.run_loop())
    return JSONResponse({"status": "running"})


@app.post("/api/step")
async def run_step():
    if engine.running and not engine.paused:
        return JSONResponse({"error": "자동 실행 중에는 step 불가. pause 먼저."}, status_code=400)
    if not engine.conn:
        await engine.initialize()
    asyncio.create_task(engine.run_single_iteration())
    return JSONResponse({"status": "stepping", "iteration": engine.iteration + 1})


@app.post("/api/pause")
async def pause():
    engine.paused = True
    await broadcast("paused", {"iteration": engine.iteration})
    return JSONResponse({"status": "paused"})


@app.post("/api/resume")
async def resume():
    engine.paused = False
    await broadcast("resumed", {"iteration": engine.iteration})
    return JSONResponse({"status": "resumed"})


@app.post("/api/speed")
async def set_speed(body: dict):
    engine.speed = max(0.1, min(5.0, body.get("speed", 1.0)))
    await broadcast("speed_changed", {"speed": engine.speed})
    return JSONResponse({"speed": engine.speed})


@app.post("/api/reset")
async def reset():
    engine.running = False
    engine.healing_running = False
    await asyncio.sleep(0.5)
    await engine.initialize()
    return JSONResponse({"status": "reset", "metrics": engine.current_metrics})


@app.post("/api/heal")
async def run_healing():
    """자율 복구 루프 시작 (v4)."""
    if engine.healing_running:
        return JSONResponse({"error": "이미 실행 중"}, status_code=400)
    if not engine.conn:
        await engine.initialize()
    asyncio.create_task(engine.run_healing_loop())
    return JSONResponse({"status": "healing"})


@app.post("/api/heal-step")
async def heal_step():
    """자율 복구 1회 실행."""
    if not engine.conn:
        await engine.initialize()
    asyncio.create_task(engine.run_healing_iteration())
    return JSONResponse({"status": "healing_step", "iteration": engine.healing_iteration + 1})


@app.post("/api/full-cycle")
async def full_cycle():
    """v3 온톨로지 개선 + v4 자율 복구 전체 사이클."""
    if engine.running or engine.healing_running:
        return JSONResponse({"error": "이미 실행 중"}, status_code=400)
    if not engine.conn:
        await engine.initialize()
    asyncio.create_task(engine.run_full_cycle())
    return JSONResponse({"status": "full_cycle"})


# ── WebSocket ─────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    # 연결 시 현재 상태 전송
    try:
        await ws.send_text(json.dumps({
            "event": "connected",
            "data": engine.get_state(),
        }, ensure_ascii=False, default=str))
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            cmd = msg.get("cmd")
            if cmd == "init":
                await engine.initialize()
            elif cmd == "run":
                if not engine.running:
                    if not engine.conn:
                        await engine.initialize()
                    asyncio.create_task(engine.run_loop())
            elif cmd == "step":
                if not engine.conn:
                    await engine.initialize()
                asyncio.create_task(engine.run_single_iteration())
            elif cmd == "pause":
                engine.paused = True
                await broadcast("paused", {"iteration": engine.iteration})
            elif cmd == "resume":
                engine.paused = False
                await broadcast("resumed", {"iteration": engine.iteration})
            elif cmd == "speed":
                engine.speed = max(0.1, min(5.0, msg.get("speed", 1.0)))
                await broadcast("speed_changed", {"speed": engine.speed})
            elif cmd == "reset":
                engine.running = False
                engine.healing_running = False
                await asyncio.sleep(0.3)
                await engine.initialize()
            elif cmd == "heal":
                if not engine.healing_running:
                    if not engine.conn:
                        await engine.initialize()
                    asyncio.create_task(engine.run_healing_loop())
            elif cmd == "heal_step":
                if not engine.conn:
                    await engine.initialize()
                asyncio.create_task(engine.run_healing_iteration())
            elif cmd == "full_cycle":
                if not engine.running and not engine.healing_running:
                    if not engine.conn:
                        await engine.initialize()
                    asyncio.create_task(engine.run_full_cycle())
            elif cmd == "state":
                await ws.send_text(json.dumps({"event": "state", "data": engine.get_state()}, ensure_ascii=False, default=str))
            elif cmd == "hitl_approve":
                hitl_id = msg.get("id", "")
                operator = msg.get("operator", "operator")
                role = resolve_operator_role(msg.get("role", "operator"), msg.get("supervisor_token", ""))
                await engine.resolve_hitl(str(hitl_id), True, str(operator), str(role))
            elif cmd == "hitl_reject":
                hitl_id = msg.get("id", "")
                operator = msg.get("operator", "operator")
                role = resolve_operator_role(msg.get("role", "operator"), msg.get("supervisor_token", ""))
                await engine.resolve_hitl(str(hitl_id), False, str(operator), str(role))
            elif cmd == "hitl_policy_update":
                await engine.update_hitl_policy({
                    "min_confidence": msg.get("min_confidence"),
                    "high_risk_threshold": msg.get("high_risk_threshold"),
                    "medium_requires_history": msg.get("medium_requires_history"),
                }, operator=str(msg.get("operator", "operator")), role=resolve_operator_role(str(msg.get("role", "operator")), str(msg.get("supervisor_token", ""))))
    except WebSocketDisconnect:
        pass
    finally:
        if ws in ws_clients:
            ws_clients.remove(ws)


# ── Main ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="EV Battery Ontology Live Server")
    parser.add_argument("--port", "-p", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  EV Battery Manufacturing — Self-Healing Factory")
    print("  AIOps: DETECT → DIAGNOSE → RECOVER → VERIFY → LEARN")
    print("=" * 60)
    print(f"  Dashboard : http://localhost:{args.port}")
    print(f"  API       : http://localhost:{args.port}/api/state")
    print(f"  WebSocket : ws://localhost:{args.port}/ws")
    print("=" * 60)
    print()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
