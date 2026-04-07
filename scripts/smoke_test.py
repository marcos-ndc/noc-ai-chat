#!/usr/bin/env python3
"""
Script de smoke test pós-deploy.
Verifica se o stack completo está funcionando após docker-compose up.

Uso:
    python scripts/smoke_test.py
    python scripts/smoke_test.py --base-url http://my-server:8000
"""
import sys
import json
import time
import argparse
import httpx
import websockets.sync.client as ws_client

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD  = "\033[1m"

results: list[dict] = []


def check(name: str, passed: bool, detail: str = ""):
    status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
    print(f"  {status}  {name}" + (f"  — {detail}" if detail else ""))
    results.append({"name": name, "passed": passed})


def section(title: str):
    print(f"\n{BOLD}{title}{RESET}")
    print("─" * 50)


def run_smoke_test(base_url: str, frontend_url: str):
    print(f"\n{BOLD}🔍 NOC AI Chat — Smoke Test{RESET}")
    print(f"Backend:  {base_url}")
    print(f"Frontend: {frontend_url}")
    print("=" * 50)

    client = httpx.Client(base_url=base_url, timeout=10.0)

    # ── 1. Health check ──────────────────────────────────────────────────────
    section("1. Health Check")
    try:
        resp = client.get("/health")
        check("Backend responde em /health", resp.status_code == 200)
        body = resp.json()
        check("Status retornado", "status" in body, body.get("status"))

        for svc in body.get("services", []):
            check(
                f"Serviço: {svc['name']}",
                svc["status"] in ("ok", "degraded"),
                svc["status"]
            )
    except Exception as e:
        check("Backend acessível", False, str(e))

    # ── 2. Auth ──────────────────────────────────────────────────────────────
    section("2. Autenticação")
    token = None
    try:
        resp = client.post("/auth/login", json={"email": "admin@noc.local", "password": "admin123"})
        check("Login válido retorna 200", resp.status_code == 200)
        body = resp.json()
        token = body.get("token")
        check("Token presente na resposta", bool(token))
        check("User presente na resposta", "user" in body)
        if "user" in body:
            check("Email correto no user", body["user"]["email"] == "admin@noc.local")

        # Invalid credentials
        resp_bad = client.post("/auth/login", json={"email": "admin@noc.local", "password": "wrong"})
        check("Login inválido retorna 401", resp_bad.status_code == 401)
    except Exception as e:
        check("Auth endpoint acessível", False, str(e))

    # ── 3. WebSocket ──────────────────────────────────────────────────────────
    section("3. WebSocket Chat")
    if token:
        ws_url = base_url.replace("http", "ws") + f"/ws/chat?token={token}"
        try:
            with ws_client.connect(ws_url, open_timeout=5) as ws:
                check("WebSocket conecta com token válido", True)

                # Ping/pong
                ws.send(json.dumps({"type": "ping"}))
                pong = json.loads(ws.recv(timeout=3))
                check("Ping → Pong funciona", pong.get("type") == "pong")
        except Exception as e:
            check("WebSocket acessível", False, str(e))
    else:
        check("WebSocket (pulado — sem token)", False, "Login falhou")

    # ── 4. Frontend ───────────────────────────────────────────────────────────
    section("4. Frontend")
    try:
        resp = httpx.get(f"{frontend_url}/health", timeout=5)
        check("Frontend responde em /health", resp.status_code == 200)
    except Exception as e:
        check("Frontend acessível", False, str(e))

    # ── 5. MCP Servers ────────────────────────────────────────────────────────
    section("5. MCP Servers")
    mcp_ports = {
        "mcp-zabbix":       8001,
        "mcp-datadog":      8002,
        "mcp-grafana":      8003,
        "mcp-thousandeyes": 8004,
    }
    mcp_base = base_url.rsplit(":", 1)[0]
    for name, port in mcp_ports.items():
        try:
            resp = httpx.get(f"{mcp_base}:{port}/health", timeout=5)
            check(f"{name} /health", resp.status_code == 200, resp.json().get("status"))
        except Exception as e:
            check(f"{name} acessível", False, str(e))

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(1 for r in results if r["passed"])
    total  = len(results)
    failed = total - passed

    print(f"\n{'=' * 50}")
    print(f"{BOLD}Resultado: {passed}/{total} verificações{RESET}")
    if failed > 0:
        print(f"{RED}  ⚠️  {failed} verificações falharam{RESET}")
        failing = [r["name"] for r in results if not r["passed"]]
        for f in failing:
            print(f"     • {f}")
    else:
        print(f"{GREEN}  🎉 Todas as verificações passaram!{RESET}")
    print()

    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NOC AI Chat Smoke Test")
    parser.add_argument("--base-url",     default="http://localhost:8000")
    parser.add_argument("--frontend-url", default="http://localhost:3000")
    args = parser.parse_args()

    ok = run_smoke_test(args.base_url, args.frontend_url)
    sys.exit(0 if ok else 1)
