# Tasks: Frontend MVP
**Branch:** `feature/frontend-base`  
**Data:** 2026-04-07

---

## Phase 0 — Setup & Contratos

- [x] **T001** [S] Inicializar repo Git com `main` branch e estrutura de pastas
  - Critério: `git log` mostra commit inicial; estrutura de dirs conforme spec
  - Links: CONSTITUTION.md

- [ ] **T002** [S] Configurar projeto React + TypeScript + Vite + Tailwind
  - Critério: `npm run dev` sobe sem erros; TypeScript strict mode ativo
  - Deps: T001

- [ ] **T003** [S] Definir tipos TypeScript centrais (`src/types/`)
  - Critério: interfaces `Message`, `User`, `ToolStatus`, `WSEvent` definidas e exportadas
  - Deps: T002

- [ ] **T004** [S] Configurar mock WebSocket server para desenvolvimento
  - Critério: frontend conecta ao mock e recebe mensagens simuladas do agente
  - Deps: T002

---

## Phase 1 — Testes (escritos antes da implementação)

- [ ] **T005** [P] Escrever testes para `useWebSocket` hook
  - Critério: testes RED para conexão, reconexão, envio e recebimento de mensagens
  - Deps: T003

- [ ] **T006** [P] Escrever testes para `useVoiceInput` hook
  - Critério: testes RED para start/stop gravação, transcrição, tratamento de erro
  - Deps: T003

- [ ] **T007** [P] Escrever testes para `ChatMessage` component
  - Critério: testes RED para renderização de Markdown, balões user/agent, streaming
  - Deps: T003

- [ ] **T008** [P] Escrever testes para `LoginPage`
  - Critério: testes RED para validação de form, submit, redirect após login
  - Deps: T003

---

## Phase 2 — Implementação Core

- [ ] **T009** [S] Implementar `useWebSocket` hook
  - Critério: T005 passa GREEN; reconexão com backoff exponencial (3 tentativas)
  - Links: FR-4, NFR-4 | Deps: T005

- [ ] **T010** [S] Implementar `useAuth` hook + `LoginPage`
  - Critério: T008 passa GREEN; JWT em memória; redirect guard funcionando
  - Links: FR-1, FR-2, FR-3, FR-16 | Deps: T005

- [ ] **T011** [S] Implementar `ChatMessage` component
  - Critério: T007 passa GREEN; Markdown renderizado; balões distintos user/agent
  - Links: FR-5, FR-6 | Deps: T009

- [ ] **T012** [S] Implementar `ChatInput` component
  - Critério: Enter envia mensagem; botão enviar; campo limpa após envio
  - Links: FR-5 | Deps: T011

- [ ] **T013** [S] Implementar streaming de respostas
  - Critério: tokens aparecem individualmente; T007 streaming test GREEN
  - Links: FR-7 | Deps: T011

- [ ] **T014** [S] Implementar `StatusIndicator` component
  - Critério: exibe nome da ferramenta com ícone animado; desaparece após resposta
  - Links: FR-8 | Deps: T011

- [ ] **T015** [S] Implementar `useVoiceInput` hook
  - Critério: T006 passa GREEN; texto aparece no input após fala
  - Links: FR-9, FR-10 | Deps: T006, T012

- [ ] **T016** [S] Implementar `useVoiceOutput` hook + toggle
  - Critério: TTS lê resposta quando modo ativo; toggle funcional
  - Links: FR-11, FR-12 | Deps: T013

- [ ] **T017** [S] Implementar `Layout` + `Header` component
  - Critério: nome/perfil do usuário no header; botão logout funcional; responsivo
  - Links: FR-13, FR-15, FR-16 | Deps: T010

---

## Phase 3 — PWA & Design

- [ ] **T018** [S] Aplicar design system (cores, tipografia, tema escuro NOC)
  - Critério: interface com identidade visual NOC; sem estética genérica
  - Deps: T017

- [ ] **T019** [S] Configurar PWA (manifest + service worker)
  - Critério: instalável no Chrome desktop e Safari mobile; ícones configurados
  - Links: FR-14 | Deps: T018

- [ ] **T020** [S] Configurar Dockerfile do frontend (multi-stage + nginx)
  - Critério: `docker build` sem erros; imagem < 50MB; healthcheck funcionando
  - Deps: T018

---

## Phase 4 — Validação

- [ ] **T021** [S] Rodar suite completa de testes — todos GREEN
  - Critério: `npm test` 100% passando; cobertura ≥ 70% em hooks e utils

- [ ] **T022** [S] Lighthouse audit
  - Critério: Performance ≥ 85, Accessibility ≥ 85, PWA ≥ 85

- [ ] **T023** [S] Revisão humana contra acceptance criteria do spec
  - Critério: todos os FR-1 a FR-16 verificados manualmente
