.PHONY: help dev prod test test-backend test-frontend logs clean setup smoke

# ─── Cores ────────────────────────────────────────────────────────────────────
CYAN  := \033[36m
GREEN := \033[32m
RESET := \033[0m

help: ## Mostra este menu de ajuda
	@echo ""
	@echo "$(CYAN)NOC AI Chat — Comandos disponíveis$(RESET)"
	@echo "════════════════════════════════════"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ─── Setup ────────────────────────────────────────────────────────────────────
setup: ## Configura ambiente de desenvolvimento (cria .env, instala deps)
	@echo "$(CYAN)→ Configurando ambiente...$(RESET)"
	@[ -f .env ] || cp .env.example .env && echo "  ✅ .env criado (configure suas API keys)"
	@cd frontend && npm ci --legacy-peer-deps --silent && echo "  ✅ Frontend deps instalados"
	@cd backend && pip install -r requirements.txt -q && echo "  ✅ Backend deps instalados"
	@echo "$(GREEN)✅ Setup concluído! Edite o .env com suas API keys antes de rodar.$(RESET)"

# ─── Desenvolvimento ──────────────────────────────────────────────────────────
dev: ## Sobe stack completo em modo desenvolvimento (hot-reload)
	@echo "$(CYAN)→ Parando containers anteriores...$(RESET)"
	-docker compose -f docker-compose.yml -f docker-compose.dev.yml down --remove-orphans 2>/dev/null
	@echo "$(CYAN)→ Verificando portas disponíveis...$(RESET)"
	@bash scripts/check-ports.sh || (echo "$(YELLOW)  Dica: mude FRONTEND_PORT ou BACKEND_PORT no .env$(RESET)" && exit 1)
	@echo "$(CYAN)→ Iniciando stack de desenvolvimento...$(RESET)"
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

rebuild: ## Rebuild completo sem cache (use quando mudar requirements ou Dockerfiles)
	@echo "$(CYAN)→ Rebuild completo sem cache...$(RESET)"
	docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache
	@echo "$(GREEN)✅ Build completo — rode 'make dev' para subir$(RESET)"

dev-bg: ## Sobe stack em background
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
	@echo "$(GREEN)✅ Stack rodando em background$(RESET)"
	@echo "   Frontend: http://localhost:3000"
	@echo "   Backend:  http://localhost:8000"
	@echo "   API Docs: http://localhost:8000/docs"

# ─── Produção ─────────────────────────────────────────────────────────────────
prod: ## Sobe stack de produção
	docker compose up --build -d
	@echo "$(GREEN)✅ Stack de produção rodando$(RESET)"

# ─── Testes ───────────────────────────────────────────────────────────────────
test: test-backend test-frontend ## Roda todos os testes

test-backend: ## Roda testes do backend
	@echo "$(CYAN)→ Testes do backend...$(RESET)"
	cd backend && python -m pytest tests/ -v --tb=short

test-backend-cov: ## Testes backend com cobertura
	cd backend && python -m pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

test-frontend: ## Roda testes do frontend
	@echo "$(CYAN)→ Testes do frontend...$(RESET)"
	cd frontend && npm test

test-mcp: ## Testa os MCP servers (modo mock)
	cd backend && python -m pytest tests/test_mcp_servers.py -v

# ─── Qualidade ────────────────────────────────────────────────────────────────
lint: ## Roda linters (Python + TypeScript)
	@echo "$(CYAN)→ TypeScript check...$(RESET)"
	cd frontend && npx tsc --noEmit
	@echo "$(GREEN)✅ TypeScript OK$(RESET)"

typecheck: ## TypeScript strict mode check
	cd frontend && npx tsc --noEmit

# ─── Smoke test ───────────────────────────────────────────────────────────────
smoke: ## Roda smoke test contra stack rodando
	@echo "$(CYAN)→ Smoke test...$(RESET)"
	python scripts/smoke_test.py

smoke-url: ## Smoke test contra URL customizada (URL=http://...)
	python scripts/smoke_test.py --base-url $(URL)

# ─── Utilitários ──────────────────────────────────────────────────────────────
logs: ## Mostra logs dos containers
	docker compose logs -f

logs-backend: ## Logs apenas do backend
	docker compose logs -f backend

logs-frontend: ## Logs apenas do frontend
	docker compose logs -f frontend

ps: ## Status dos containers
	docker compose ps

stop: ## Para os containers
	docker compose down

clean: ## Para containers e remove volumes
	docker compose down -v
	@echo "$(GREEN)✅ Containers e volumes removidos$(RESET)"

clean-all: clean ## Limpa containers, volumes e imagens
	docker compose down --rmi all -v
	@echo "$(GREEN)✅ Tudo limpo$(RESET)"

# ─── Git helpers ──────────────────────────────────────────────────────────────
branch-feature: ## Cria branch de feature (NAME=nome-da-feature)
	git checkout main && git pull origin main
	git checkout -b feature/$(NAME)
	@echo "$(GREEN)✅ Branch feature/$(NAME) criada$(RESET)"

fix-docker: ## Corrige erro 'error getting credentials' do Docker
	bash scripts/fix-docker-credentials.sh

pull-images: ## Pré-baixa todas as imagens Docker necessárias
	docker pull python:3.12-slim
	docker pull node:20-alpine
	docker pull nginx:1.27-alpine
	docker pull redis:7-alpine
	@echo "$(GREEN)✅ Todas as imagens baixadas$(RESET)"

branch-fix: ## Cria branch de fix (NAME=nome-do-fix)
	git checkout main && git pull origin main
	git checkout -b fix/$(NAME)
	@echo "$(GREEN)✅ Branch fix/$(NAME) criada$(RESET)"
