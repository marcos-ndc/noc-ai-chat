# Tasks: Frontend
**Versão:** 2.0 | **Data:** 2026-04-09 | **Branch:** `main` (mergeado)

---

## Phase 0 — Setup ✅

- [x] **T001** Inicializar projeto React + TypeScript + Vite + Tailwind
- [x] **T002** Configurar TypeScript strict mode + paths aliases
- [x] **T003** Definir tipos TypeScript centrais em `src/types/index.ts`
  - `Message`, `User`, `WSEvent`, `WSOutboundMessage`, `ToolName`, `TOOL_METADATA`, etc.
- [x] **T004** Configurar Zustand store (useAuthStore)

## Phase 1 — Testes ✅

- [x] **T005** Testes para `useWebSocket` hook
- [x] **T006** Testes para `useVoiceInput` hook
- [x] **T007** Smoke tests para `ChatMessage` component
- [x] **T008** Smoke tests para `LoginPage`

## Phase 2 — Core ✅

- [x] **T009** `useWebSocket` — stable refs, backoff exponencial (3x), reconexão
- [x] **T010** `useAuth` + `LoginPage` — Zustand, JWT em memória, redirect guard
- [x] **T011** `ChatMessage` — Markdown, balões user/agent, timestamps
- [x] **T012** `ChatInput` — Enter para enviar, Shift+Enter nova linha, auto-resize
- [x] **T013** Streaming de respostas token-a-token
- [x] **T014** `StatusIndicator` — ícone animado da tool em uso
- [x] **T015** `useVoiceInput` — STT Web Speech API, preview transcript
- [x] **T016** `useVoiceOutput` — TTS Web Speech API, toggle, stop
- [x] **T017** `Header` — perfil, status WS, logout

## Phase 3 — Design e PWA ✅

- [x] **T018** Design system NOC: cores, tipografia, grid, scanlines, glow
- [x] **T019** PWA: manifest, service worker, ícones
- [x] **T020** Dockerfile frontend (multi-stage + nginx) + Dockerfile.dev

## Phase 4 — Gráficos Interativos ✅

- [x] **T021** Instalar Recharts + react-is (peer dependency obrigatória)
- [x] **T022** `NocCharts.tsx` — 6 componentes Recharts com tema NOC:
  - `AvailabilityChart` — área com gradiente, linha SLA
  - `ResponseTimeChart` — linha com referências 200ms/500ms
  - `PacketLossChart` — barras coloridas por severidade
  - `NetworkLatencyChart` — avg/min/max com jitter
  - `MetricDashboard` — painel completo com 3 gráficos
  - `AvailabilitySummaryChart` — barras horizontais multi-teste
- [x] **T023** `chartParser.ts` — parser de blocos chart JSON nas mensagens
  - Detecta ` ```chart {...} ``` ` no conteúdo
  - Suporta: `availability`, `response_time`, `packet_loss`, `network_latency`,
    `multi_metric`, `availability_summary`, `latency_simulation` (alias)
- [x] **T024** `AgentContent` em `ChatMessage.tsx` — intercala markdown e gráficos

## Phase 5 — Bugfixes (Code Review) ✅

- [x] **T025** CR-1: Login só redireciona quando `isAuthenticated = true`
- [x] **T026** CR-4: `currentAgentMsgId` definido antes de `send()` (race condition)
- [x] **T027** AL-1: `isLoading`/`error` movidos para Zustand store
- [x] **T028** AL-4: `formatTime()` aceita `string | Date`, converte com `new Date()`
- [x] **T029** ME-3: `useVoiceOutput` removido do `ChatInput` (instância duplicada)
- [x] **T030** Fix: `StrictMode` desabilitado (causava dupla conexão WS em dev)
- [x] **T031** Fix: build script = `vite build` (sem `tsc -b` que causava erros de node_modules)
- [x] **T032** Fix: `@types/node` adicionado para `vite.config.ts`
- [x] **T033** Fix: `vite.config.ts` refatorado com `loadEnv()` (sem `process.env` inline)
- [x] **T034** Fix: `react-is` adicionado ao `package.json` (peer dep do Recharts)

## Próximas Tasks (Backlog)

- [ ] **T035** Histórico persistente entre sessões (localStorage opt-in)
- [ ] **T036** Upload de screenshots para análise pelo agente
- [ ] **T037** Notificações push para alertas P1/P2
- [ ] **T038** Tema claro (toggle dark/light)
- [ ] **T039** Exportar conversa como PDF
- [ ] **T040** Lighthouse audit completo (meta: ≥ 85 em todas as categorias)
- [ ] **T041** Cobertura de testes ≥ 70% em hooks e utils
