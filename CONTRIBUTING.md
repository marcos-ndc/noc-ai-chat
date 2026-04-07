# Guia de Contribuição — NOC AI Chat

## Fluxo de Desenvolvimento

Este projeto segue **Spec-Driven Development (SDD)** — especificação antes de código.

### 1. Abrir uma Issue
Descreva a feature ou bug antes de começar a codar.

### 2. Criar branch a partir de `main`
```bash
git checkout main && git pull
git checkout -b feature/nome-descritivo   # nova feature
git checkout -b fix/nome-do-bug           # correção
```

### 3. Escrever spec e tasks (features novas)
```
docs/specs/<nome>.md   # O QUÊ e POR QUÊ
docs/tasks/<nome>.md   # COMO (lista de tasks TDD-first)
```

### 4. TDD — testes antes da implementação
- Escreva testes que falham (RED)
- Implemente até passar (GREEN)
- Refatore mantendo testes verdes

### 5. Commits com Conventional Commits
```
feat: T005 implement chat message component
fix: T012 correct WebSocket reconnection backoff
docs: update backend spec with new endpoint
test: T104 add auth service tests
chore: update dependencies
```

### 6. Abrir Pull Request para `main`
- Descreva o que foi feito
- Referencie a Issue
- Certifique-se que CI está verde

---

## Padrões de Código

### Backend (Python)
- Type hints obrigatórios em todas as funções
- Pydantic models para todos os dados de entrada/saída
- `async/await` para I/O
- Sem `print()` — use `structlog`

### Frontend (TypeScript)
- `strict: true` — sem `any` implícito
- Componentes com no máximo 200 linhas
- Hooks com no máximo 100 linhas
- Props tipadas com interfaces

---

## Executar localmente sem Docker

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev   # http://localhost:3000
```

### Redis (necessário para o backend)
```bash
docker run -d -p 6379:6379 redis:7-alpine
```
