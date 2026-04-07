#!/usr/bin/env bash
# =============================================================================
# smoke-test.sh — Valida que todos os serviços estão saudáveis após docker-compose up
# Uso: ./scripts/smoke-test.sh
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
  local name="$1"
  local url="$2"
  local expected="${3:-200}"

  printf "  %-40s" "$name"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")

  if [ "$status" = "$expected" ]; then
    echo -e "${GREEN}✓ $status${NC}"
    ((PASS++))
  else
    echo -e "${RED}✗ $status (esperado $expected)${NC}"
    ((FAIL++))
  fi
}

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     NOC AI Chat — Smoke Test             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

echo -e "${YELLOW}▶ Frontend${NC}"
check "App React (root)"     "http://localhost:3000"         "200"
check "App React (health)"   "http://localhost:3000/health"  "200"

echo ""
echo -e "${YELLOW}▶ Backend${NC}"
check "Health endpoint"      "http://localhost:8000/health"  "200"
check "Auth endpoint (POST)" "http://localhost:8000/auth/login" "405"  # GET returns 405, POST returns 200/401

echo ""
echo -e "${YELLOW}▶ MCP Servers${NC}"
check "MCP Zabbix health"        "http://localhost:8001/health" "200"
check "MCP Datadog health"       "http://localhost:8002/health" "200"
check "MCP Grafana health"       "http://localhost:8003/health" "200"
check "MCP ThousandEyes health"  "http://localhost:8004/health" "200"

echo ""
echo -e "${YELLOW}▶ Auth Flow${NC}"
printf "  %-40s" "Login admin@noc.local"
RESP=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@noc.local","password":"admin123"}' 2>/dev/null)

if echo "$RESP" | grep -q '"token"'; then
  echo -e "${GREEN}✓ Token recebido${NC}"
  ((PASS++))
  TOKEN=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null || echo "")
else
  echo -e "${RED}✗ Login falhou${NC}"
  ((FAIL++))
  TOKEN=""
fi

echo ""
echo "══════════════════════════════════════════════"
echo -e "  Total: ${GREEN}$PASS passaram${NC} / ${RED}$FAIL falharam${NC}"
echo "══════════════════════════════════════════════"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo -e "${RED}⚠ Smoke test falhou. Verifique os logs: docker-compose logs${NC}"
  exit 1
else
  echo -e "${GREEN}✅ Todos os serviços estão saudáveis!${NC}"
  echo ""
  echo "Acesse: http://localhost:3000"
  exit 0
fi
