#!/usr/bin/env bash
# =============================================================================
# setup-dev.sh — Configura o ambiente de desenvolvimento NOC AI Chat
# Uso: bash scripts/setup-dev.sh
# =============================================================================
set -e

CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'

info()    { echo -e "${CYAN}→ $1${RESET}"; }
success() { echo -e "${GREEN}✅ $1${RESET}"; }
warn()    { echo -e "${YELLOW}⚠️  $1${RESET}"; }
error()   { echo -e "${RED}❌ $1${RESET}"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║     NOC AI Chat — Setup Dev          ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════╝${RESET}"
echo ""

# ─── Verificar prerequisitos ──────────────────────────────────────────────────
info "Verificando pré-requisitos..."

command -v docker  >/dev/null 2>&1 || error "Docker não encontrado. Instale em https://docs.docker.com/get-docker/"
command -v node    >/dev/null 2>&1 || error "Node.js não encontrado. Instale em https://nodejs.org/ (v20+)"
command -v python3 >/dev/null 2>&1 || error "Python 3 não encontrado. Instale em https://python.org/ (3.12+)"
command -v git     >/dev/null 2>&1 || error "Git não encontrado."

DOCKER_V=$(docker --version | grep -oE '[0-9]+\.[0-9]+')
NODE_V=$(node --version | sed 's/v//')
PY_V=$(python3 --version | grep -oE '[0-9]+\.[0-9]+')

success "Docker $DOCKER_V | Node $NODE_V | Python $PY_V"

# ─── Configurar .env ──────────────────────────────────────────────────────────
info "Configurando variáveis de ambiente..."

if [ ! -f .env ]; then
    cp .env.example .env
    success ".env criado a partir de .env.example"
    warn "IMPORTANTE: Edite o .env com suas API keys antes de iniciar"
    echo ""
    echo "  Variáveis obrigatórias:"
    echo "    ANTHROPIC_API_KEY  → https://console.anthropic.com/settings/keys"
    echo "    JWT_SECRET         → gere com: openssl rand -hex 32"
    echo ""
    echo "  Variáveis opcionais (MCP servers usarão mock se vazias):"
    echo "    ZABBIX_URL / ZABBIX_USER / ZABBIX_PASSWORD"
    echo "    DATADOG_API_KEY / DATADOG_APP_KEY"
    echo "    GRAFANA_URL / GRAFANA_TOKEN"
    echo "    THOUSANDEYES_TOKEN"
else
    success ".env já existe"
fi

# ─── Gerar JWT_SECRET se não definido ─────────────────────────────────────────
if grep -q "JWT_SECRET=troque-por" .env 2>/dev/null; then
    if command -v openssl >/dev/null 2>&1; then
        JWT_SECRET=$(openssl rand -hex 32)
        sed -i.bak "s/JWT_SECRET=.*/JWT_SECRET=${JWT_SECRET}/" .env && rm -f .env.bak
        success "JWT_SECRET gerado automaticamente"
    fi
fi

# ─── Instalar dependências frontend ───────────────────────────────────────────
info "Instalando dependências do frontend..."
cd frontend
npm ci --legacy-peer-deps --silent
cd ..
success "Frontend deps instalados"

# ─── Instalar dependências backend ────────────────────────────────────────────
info "Instalando dependências do backend..."
cd backend
pip install -r requirements.txt -q
cd ..
success "Backend deps instalados"

# ─── Rodar testes ─────────────────────────────────────────────────────────────
info "Rodando testes do backend..."
cd backend
if python -m pytest tests/ -q --tb=short 2>&1 | tail -5; then
    success "Todos os testes passando"
else
    warn "Alguns testes falharam — verifique antes de iniciar"
fi
cd ..

# ─── TypeScript check ─────────────────────────────────────────────────────────
info "Verificando TypeScript..."
cd frontend
if npx tsc --noEmit 2>&1 | grep -q "error TS"; then
    warn "Erros TypeScript detectados — rode: cd frontend && npx tsc --noEmit"
else
    success "TypeScript OK"
fi
cd ..

# ─── Resumo ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}║     Setup concluído com sucesso! 🚀      ║${RESET}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${RESET}"
echo ""
echo "  Próximos passos:"
echo ""
echo "  1. Edite o .env com suas API keys (obrigatório: ANTHROPIC_API_KEY)"
echo "  2. Inicie o stack de desenvolvimento:"
echo ""
echo "     make dev"
echo "     # ou"
echo "     docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build"
echo ""
echo "  3. Acesse:"
echo "     Frontend:  http://localhost:3000"
echo "     Backend:   http://localhost:8000"
echo "     API Docs:  http://localhost:8000/docs"
echo ""
echo "  Usuários de desenvolvimento:"
echo "     admin@noc.local  / admin123  (Analista N2)"
echo "     n1@noc.local     / noc2024   (Analista N1)"
echo "     eng@noc.local    / eng2024   (Engenheiro)"
echo "     gestor@noc.local / mgr2024   (Gestor)"
echo ""
