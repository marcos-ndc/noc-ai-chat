# Spec: Frontend — NOC AI Chat
**Versão:** 2.0 | **Data:** 2026-04-09 | **Status:** Implementado ✅

---

## Overview

Interface web responsiva (PWA) para interação com o agente de IA NOC. Tema escuro com estética de terminal NOC (grid, scanlines, glow). Suporte a voz bidirecional (STT + TTS), renderização de Markdown e gráficos interativos inline com Recharts.

---

## Estrutura Implementada

```
frontend/src/
├── App.tsx                          # Rotas + ProtectedRoute + PublicRoute
├── main.tsx                         # Entry point (StrictMode desabilitado)
├── pages/
│   ├── LoginPage.tsx                # Form de login com validação
│   └── ChatPage.tsx                 # Página principal do chat
├── components/
│   ├── Chat/
│   │   ├── ChatMessage.tsx          # Mensagem com AgentContent (markdown + charts)
│   │   └── ChatInput.tsx            # Input com voz e envio
│   ├── Charts/
│   │   ├── NocCharts.tsx            # 6 componentes Recharts com tema NOC
│   │   └── chartParser.ts           # Parser de blocos chart JSON nas mensagens
│   ├── Layout/
│   │   └── Header.tsx               # Header com usuário, perfil, logout, status WS
│   ├── StatusIndicator/
│   │   └── StatusIndicator.tsx      # Indicador animado de tools em uso
│   └── VoiceInput/ VoiceOutput/     # Botões de voz
├── hooks/
│   ├── useWebSocket.ts              # WS com stable refs, backoff, reconexão
│   ├── useAuth.ts                   # Zustand store + login/logout
│   ├── useVoiceInput.ts             # Web Speech API STT
│   └── useVoiceOutput.ts            # Web Speech API TTS
└── types/
    └── index.ts                     # Message, User, WSEvent, ToolName, etc.
```

---

## User Journeys

### J1 — Login
1. Usuário acessa `/` → redireciona para `/login`
2. Preenche email/senha, clica Entrar
3. Se credenciais erradas: mensagem de erro exibida, **sem redirecionar** (CR-1 corrigido)
4. Se sucesso: redireciona para `/chat`

### J2 — Conversa por texto
1. Usuário digita no input e pressiona Enter (ou clica enviar)
2. Mensagem aparece imediatamente no histórico (lado direito)
3. Agente prepara slot de resposta (sem race condition — CR-4 corrigido)
4. StatusIndicator mostra tool em uso: `● zabbix`, `● datadog`, etc.
5. Resposta aparece em streaming real token-a-token
6. Gráficos Recharts renderizados inline quando agente emite blocos `chart`

### J3 — Voz bidirecional
1. Clique no microfone → gravação ativa (indicador vermelho)
2. Fala é transcrita via Web Speech API e aparece no input
3. Toggle de saída em voz: TTS lê resposta automaticamente após `agent_done`

### J4 — Gráficos interativos
1. Agente retorna bloco ` ```chart {...} ``` ` na resposta
2. `chartParser` detecta e extrai o JSON
3. Componente Recharts renderizado inline na mesma mensagem
4. Tipos suportados: `availability`, `response_time`, `packet_loss`, `network_latency`, `multi_metric`, `availability_summary`, `latency_simulation` (alias de `network_latency`)

---

## Functional Requirements

| ID | Requisito | Status |
|----|-----------|--------|
| FR-1 | Tela de login com email/senha | ✅ |
| FR-2 | Autenticação via POST `/auth/login`, JWT em Zustand | ✅ |
| FR-3 | Redirect guard: não autenticado → `/login` | ✅ |
| FR-4 | Conexão WebSocket persistente com reconexão (backoff 3x) | ✅ |
| FR-5 | Mensagens em bolhas distintas (usuário direita, agente esquerda) | ✅ |
| FR-6 | Markdown renderizado nas respostas (bold, code, tabelas, listas) | ✅ |
| FR-7 | Streaming token-a-token sem aguardar resposta completa | ✅ |
| FR-8 | StatusIndicator com nome e ícone da ferramenta consultada | ✅ |
| FR-9 | STT via Web Speech API | ✅ |
| FR-10 | Texto transcrito aparece no input antes de enviar | ✅ |
| FR-11 | Toggle TTS para resposta em voz | ✅ |
| FR-12 | TTS lê resposta do agente quando modo ativo | ✅ |
| FR-13 | Responsivo: mobile (≥ 375px) e desktop (≥ 1024px) | ✅ |
| FR-14 | PWA instalável (manifest + service worker via vite-plugin-pwa) | ✅ |
| FR-15 | Header com nome, perfil e botão de logout | ✅ |
| FR-16 | Logout invalida JWT em memória | ✅ |
| FR-17 | Gráficos Recharts interativos inline (6 tipos) | ✅ |
| FR-18 | Login não redireciona em caso de erro | ✅ (CR-1) |

---

## Componentes de Gráfico (NocCharts.tsx)

| Componente | chartType | Métricas exibidas |
|------------|-----------|-------------------|
| `AvailabilityChart` | `availability` | % disponibilidade, linha SLA 99% |
| `ResponseTimeChart` | `response_time` | Latência ms, refs 200ms/500ms |
| `PacketLossChart` | `packet_loss` | % perda, barras por severidade |
| `NetworkLatencyChart` | `network_latency` / `latency_simulation` | avg/min/max, jitter |
| `MetricDashboard` | `multi_metric` | Painel com os 3 gráficos + header |
| `AvailabilitySummaryChart` | `availability_summary` | Barras horizontais multi-teste |

---

## Bugs Corrigidos (Code Review 2026-04-08)

| ID | Bug | Correção |
|----|-----|----------|
| CR-1 | Login redirecionava mesmo com erro | Verifica `isAuthenticated` antes de navegar |
| CR-4 | Race condition: `currentAgentMsgId` null no primeiro token | Definido antes de `send()` |
| AL-1 | `isLoading`/`error` perdidos entre navegações | Movidos para Zustand store |
| AL-4 | `timestamp` do WS como string quebrava `formatTime()` | `new Date()` + `isNaN()` guard |
| ME-3 | `useVoiceOutput` instanciado em duplicata | Removido do `ChatInput` |

---

## Non-Functional Requirements

| ID | Requisito | Meta | Status |
|----|-----------|------|--------|
| NFR-1 | First Contentful Paint | < 2s | ✅ |
| NFR-2 | Bundle principal gzipped | < 300KB | ✅ (~109KB) |
| NFR-3 | Feedback visual imediato | < 100ms | ✅ |
| NFR-4 | Reconexão WebSocket com backoff | 3 tentativas | ✅ |
| NFR-5 | Build Docker sem erros (`vite build`) | 0 erros | ✅ |
| NFR-6 | Zero erros TypeScript | `tsc --noEmit` = 0 | ✅ |

---

## Out of Scope (v1)

- Histórico persistente entre sessões do browser
- Upload de arquivos/screenshots
- Notificações push
- Tema claro
- i18n / múltiplos idiomas
- SSO/AD corporativo → v2
