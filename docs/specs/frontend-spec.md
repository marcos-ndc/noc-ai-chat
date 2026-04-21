# Spec: Frontend
**Versão:** 3.0 | **Data:** 2026-04-21 | **Status:** Implementado ✅

---

## Functional Requirements

| ID | Requisito | Status |
|----|-----------|--------|
| FR-1 | Login com email/senha, JWT em Zustand (memória) | ✅ |
| FR-2 | Redirect guard: não autenticado → `/login` | ✅ |
| FR-3 | Botões de acesso rápido na LoginPage (Admin, Gestor, N1) | ✅ |
| FR-4 | WebSocket com reconexão automática (backoff 3x) | ✅ |
| FR-5 | Streaming token a token sem aguardar resposta completa | ✅ |
| FR-6 | Markdown renderizado nas respostas | ✅ |
| FR-7 | Gráficos Recharts inline (6 tipos via blocos `chart`) | ✅ |
| FR-8 | StatusIndicator com nome da ferramenta sendo consultada | ✅ |
| FR-9 | Seletor de especialista (barra abaixo do header) | ✅ |
| FR-10 | SpecialistToast ao redirecionar automaticamente (4s) | ✅ |
| FR-11 | Botão microfone → Whisper STT (fallback Web Speech) | ✅ |
| FR-12 | Toggle TTS com indicador premium "AI" | ✅ |
| FR-13 | Auto-send após transcrição de voz | ✅ |
| FR-14 | Auto-TTS após agent_done em modo voz | ✅ |
| FR-15 | stripForVoice() — remove markdown/charts antes do TTS | ✅ |
| FR-16 | Botão "Olá NOC" → modo hands-free | ✅ |
| FR-17 | Banner animado com estado hands-free | ✅ |
| FR-18 | "NOC obrigado" encerra modo hands-free | ✅ |
| FR-19 | Modal NDX (VoiceModal) — Canvas + Web Audio API | ✅ |
| FR-20 | Ondas do modal reativas à amplitude do microfone | ✅ |
| FR-21 | Header: indicador voiceMode + handsFreeState | ✅ |
| FR-22 | Painel `/admin` com seletor de modelo, voz e TTS | ✅ |
| FR-23 | Resultado de teste com diagnóstico + hint em azul | ✅ |
| FR-24 | Responsivo: mobile ≥ 375px e desktop ≥ 1024px | ✅ |
| FR-25 | PWA instalável | ✅ |

---

## Hooks

| Hook | Tecnologia | Função |
|------|-----------|--------|
| `useWebSocket` | WebSocket nativo | Conexão WS com stable refs, backoff |
| `useAuth` | Zustand | JWT em memória, login/logout |
| `useWhisperInput` | MediaRecorder + POST /stt | Gravação + transcrição Whisper |
| `useVoiceInput` | Web Speech API | STT nativo (standby/fallback) |
| `useVoiceOutput` | Audio() + Web Speech | TTS premium (OpenAI) + fallback |
| `useWakeWord` | Web Speech (standby) + Whisper (listening) | Hands-free loop |

---

## Componentes

| Componente | Descrição |
|-----------|-----------|
| `ChatPage` | Orquestra tudo: WS, mensagens, especialista, voz |
| `ChatMessage / AgentContent` | Markdown + Recharts intercalados |
| `ChatInput` | Textarea, Whisper mic, "Olá NOC", voice toggle |
| `NocCharts` | 6 componentes Recharts com tema NOC |
| `chartParser` | Detecta blocos `chart JSON` nas mensagens |
| `SpecialistSelector` | Dropdown com 5 especialistas |
| `SpecialistToast` | Toast animado de roteamento automático |
| `VoiceModal` | Modal NDX: Canvas 320px + Web Audio API |
| `VoiceOutputToggle` | Toggle TTS com badge "AI" premium |
| `Header` | Perfil, status WS, voiceMode, handsFreeState, botão Admin |
| `AdminPage` | Painel completo: modelo, TTS, status |
| `StatusIndicator` | Ícone animado da tool sendo consultada |

---

## useWakeWord — Fluxo de Estados

```
off ──[click "Olá NOC"]──→ listening ──[fala]──→ waiting ──[agent responde]──→ speaking
 ↑                              ↑                                                   │
 └──["NOC obrigado"]────────────┘◄─────────────────────────────────────────────────┘
                                                                         (400ms delay)
```

- **standby**: Web Speech API contínua (wake word detection) — só ativo após wake word
- **listening**: Whisper grava e transcreve (ou Web Speech fallback)
- **waiting**: aguardando agent_done
- **speaking**: TTS ativo — mic pausado para evitar feedback

---

## Bugs Corrigidos Notáveis

| Fix | Problema |
|-----|----------|
| voiceMode React async | setState assíncrono — send() usava estado antigo |
| fromVoiceRef | onResult não disparava em `end` natural (só em `stop()`) |
| stopPropagation | Banner aparecia onde botão estava — click propagava |
| isActive ref | Closure stale no toggle — lia `wakeWord.state` antigo |
| continuous=true | Chrome abortava ao reiniciar — solução: sessão única longa |
| isStopWord | speechend e timer de silêncio não checavam stop words |
| Whisper | Web Speech API insensível a ruído → migrado para Whisper |
