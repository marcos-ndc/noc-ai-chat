#!/usr/bin/env bash
# =============================================================================
# check-ports.sh — verifica se as portas necessárias estão livres
# =============================================================================

CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'

# Carrega variáveis do .env se existir
[ -f .env ] && export $(grep -v '^#' .env | grep -E '^(FRONTEND_PORT|BACKEND_PORT|REDIS_PORT)=' | xargs) 2>/dev/null

FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
REDIS_PORT="${REDIS_PORT:-6379}"

FAILED=0

check_port() {
    local port=$1
    local name=$2

    # Tenta com lsof primeiro, depois ss, depois netstat
    if command -v lsof >/dev/null 2>&1; then
        PROCESS=$(lsof -ti :$port 2>/dev/null | head -1)
        if [ -n "$PROCESS" ]; then
            PNAME=$(ps -p $PROCESS -o comm= 2>/dev/null || echo "desconhecido")
            echo -e "  ${RED}✗ Porta $port ($name) em uso pelo processo: $PNAME (PID $PROCESS)${RESET}"
            echo -e "    Para liberar: ${YELLOW}kill -9 $PROCESS${RESET}"
            echo -e "    Ou mude a porta no .env: ${YELLOW}${name//-/_}_PORT=<outra porta>${RESET}"
            return 1
        fi
    elif command -v ss >/dev/null 2>&1; then
        if ss -tlnp 2>/dev/null | grep -q ":$port "; then
            echo -e "  ${RED}✗ Porta $port ($name) já está em uso${RESET}"
            echo -e "    Para ver quem usa: ${YELLOW}ss -tlnp | grep :$port${RESET}"
            echo -e "    Ou mude no .env: ${YELLOW}${name//-/_}_PORT=<outra porta>${RESET}"
            return 1
        fi
    fi

    echo -e "  ${GREEN}✓ Porta $port ($name) disponível${RESET}"
    return 0
}

echo -e "${CYAN}Verificando portas...${RESET}"

check_port "$FRONTEND_PORT" "frontend" || FAILED=1
check_port "$BACKEND_PORT"  "backend"  || FAILED=1
check_port "$REDIS_PORT"    "redis"    || FAILED=1

if [ $FAILED -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}┌─────────────────────────────────────────────────────────┐${RESET}"
    echo -e "${YELLOW}│  Opções para resolver conflito de porta:                │${RESET}"
    echo -e "${YELLOW}│                                                         │${RESET}"
    echo -e "${YELLOW}│  1. Parar containers antigos:                           │${RESET}"
    echo -e "${YELLOW}│     docker stop \$(docker ps -q)                         │${RESET}"
    echo -e "${YELLOW}│                                                         │${RESET}"
    echo -e "${YELLOW}│  2. Usar portas alternativas (edite o .env):            │${RESET}"
    echo -e "${YELLOW}│     FRONTEND_PORT=3001                                  │${RESET}"
    echo -e "${YELLOW}│     BACKEND_PORT=8001                                   │${RESET}"
    echo -e "${YELLOW}│                                                         │${RESET}"
    echo -e "${YELLOW}│  3. Parar processo específico:                          │${RESET}"
    echo -e "${YELLOW}│     kill -9 <PID>  (PID listado acima)                  │${RESET}"
    echo -e "${YELLOW}└─────────────────────────────────────────────────────────┘${RESET}"
    exit 1
fi

echo -e "${GREEN}✅ Todas as portas disponíveis!${RESET}"
exit 0
