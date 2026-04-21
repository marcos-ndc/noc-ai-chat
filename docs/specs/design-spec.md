# NOC AI Chat — Design Spec
**Versão:** 3.0 | **Data:** 2026-04-21 | **Status:** Implementado ✅

---

## 1. Visão Geral

Assistente de IA para NOC com interface conversacional multimodal (texto + voz), 5 especialistas com roteamento automático, suporte a múltiplos provedores de IA e integração com Zabbix, Datadog, Grafana e ThousandEyes.

---

## 2. Fluxo de Dados Completo

```
┌─────────────────────────────────────────────────────────────────────┐
│                      FRONTEND (React 18 PWA)                         │
│                                                                       │
│  LoginPage → ChatPage                                                 │
│    ├── SpecialistSelector (barra abaixo do header)                   │
│    ├── ChatMessages (streaming token a token)                        │
│    ├── NocCharts (Recharts inline nos blocos ```chart)              │
│    ├── ChatInput                                                      │
│    │     ├── Mic button → useWhisperInput → /stt/transcribe         │
│    │     ├── Botão "Olá NOC" → useWakeWord (hands-free)             │
│    │     └── VoiceOutputToggle → useVoiceOutput → /tts/speak        │
│    ├── VoiceModal (NDX canvas + Web Audio API)                      │
│    └── SpecialistToast (notificação de redirecionamento)            │
│                          ↕ WebSocket                                  │
├──────────────────────────────────────────────────────────────────────┤
│                     BACKEND (FastAPI)                                 │
│                                                                       │
│  /auth/login          POST  → JWT + UserOut                         │
│  /ws/chat?token=      WS    → streaming agêntico                    │
│  /tts/speak           POST  → OpenAI TTS → MP3                      │
│  /tts/status          GET   → vozes disponíveis                     │
│  /stt/transcribe      POST  → OpenAI Whisper → texto                │
│  /stt/status          GET   → disponibilidade                       │
│  /admin/*             GET/PUT/POST → painel admin (perfil admin)    │
│  /health              GET   → status de todos os serviços           │
│                                                                       │
│  AgentOrchestrator                                                    │
│    ├── AIConfigStore (Redis) → provedor/modelo em runtime           │
│    ├── get_system_prompt(profile, specialist, voice_mode)           │
│    │     └── _LANGUAGE_PREMISE + specialist prompt + profile addendum│
│    ├── ROUTE_TO detection → specialist_change WS event              │
│    └── llm_client.py                                                 │
│          ├── build_anthropic_client() → AsyncAnthropic              │
│          └── build_openrouter_client() → AsyncOpenAI                │
│                          ↕ HTTP                                       │
├──────────────────────────────────────────────────────────────────────┤
│                     MCP SERVERS                                       │
│  mcp-zabbix:8001  mcp-datadog:8001  mcp-grafana:8001  mcp-te:8001   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Eventos WebSocket

### Frontend → Backend
```json
{ "type": "user_message", "content": "...", "sessionId": "abc",
  "voiceMode": true, "specialist": "apm" }
```

### Backend → Frontend
```json
{ "type": "specialist_change", "specialist": "apm",
  "content": "Especialista APM & Logs", "reason": "latência HTTP 502" }
{ "type": "tool_start", "tool": "datadog" }
{ "type": "tool_end",   "tool": "datadog" }
{ "type": "agent_token", "messageId": "x", "content": "texto..." }
{ "type": "agent_done",  "messageId": "x" }
{ "type": "error", "error": "mensagem limpa (sem HTML)" }
```

---

## 4. Gráficos Interativos (Recharts)

O agente emite blocos ` ```chart {...} ``` ` com JSON estruturado.

| chartType | Componente | Caso de uso |
|-----------|------------|-------------|
| `availability` | AvailabilityChart | Disponibilidade % com linha SLA |
| `response_time` | ResponseTimeChart | Latência HTTP em ms |
| `packet_loss` | PacketLossChart | % perda de pacotes |
| `network_latency` / `latency_simulation` | NetworkLatencyChart | avg/min/max/jitter |
| `multi_metric` | MetricDashboard | Painel com 3 gráficos |
| `availability_summary` | AvailabilitySummaryChart | Barras horizontais |

**Proibido em modo voz:** agente não emite blocos `chart` quando `voiceMode=true`.

---

## 5. Especialistas NOC

### Roteamento automático
O Generalista analisa e emite `<ROUTE_TO specialist="X" reason="Y"/>`.
O backend detecta via regex, atualiza `session.active_specialist` e emite `specialist_change`.
O frontend exibe o `SpecialistToast` por 4 segundos e atualiza o `SpecialistSelector`.

### Redirecionamento em cadeia
Cada especialista pode redirecionar para outro:
- APM identifica causa em infra → redireciona para Infraestrutura
- Infra identifica problema de rede → redireciona para Conectividade
- Todo o histórico é preservado na troca

---

## 6. Modo Voz — Fluxo Detalhado

### Entrada (STT)
```
Botão mic pressionado
  ↓
useWhisperInput.start()
  → MediaRecorder(echoCancellation, noiseSuppression, sampleRate:16kHz)
  → Grava audio/webm;codecs=opus
Botão mic solto (ou 8s timeout)
  ↓
useWhisperInput.stop()
  → POST /stt/transcribe (multipart/form-data)
  → Backend → OpenAI Whisper API
    (language=pt, prompt="NOC, Zabbix, Datadog...")
  → Retorna { text, language, duration }
  → onResult(text) → ChatInput auto-submits com voiceMode=true
```

### Saída (TTS)
```
agent_done recebido + (voiceOutputEnabled OR voiceMode OR handsFreeActive)
  ↓
stripForVoice(content)
  → remove code blocks, chart blocks, markdown
  ↓
useVoiceOutput.speak(plainText)
  → if isPremium: POST /tts/speak { text, voice, model, speed }
    → Backend → OpenAI TTS API → MP3
    → Audio().play()
  → else: SpeechSynthesisUtterance
```

### Hands-free
```
Clique "Olá NOC"
  ↓ activate() → state: listening
Web Speech API standby (wake word detection, continuous=true, baixo CPU)
  → ouve wake words: "olá noc", "nokia", "nok", etc.
    ↓ detectado
useWhisperInput.start() (recording)
  → usuário fala a pergunta
  → speechend → Whisper → texto → onQuery(texto) → handleSend(texto, true)
    ↓
Agent responde → TTS fala → 400ms delay
  ↓
useWhisperInput.start() novamente → loop contínuo
  ↓
"NOC obrigado" → isStopWord() → deactivate() → state: off
```

---

## 7. Painel Admin

### Endpoints
| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/admin/models` | 19 modelos em 2 provedores |
| GET | `/admin/ai-config` | Config atual (key mascarada) |
| PUT | `/admin/ai-config` | Atualiza em runtime sem reiniciar |
| POST | `/admin/ai-config/test` | Testa com diagnóstico detalhado |
| GET | `/admin/status` | IA + Redis + 4 MCP servers |

### Diagnóstico de erros (test endpoint)
| Erro | Mensagem |
|------|---------|
| 401/403 | "API key inválida" |
| 404/NotFoundError | "Modelo não encontrado — verifique o ID" |
| Timeout | "Proxy SSL corporativo bloqueando" |
| SSL | "Adicione ANTHROPIC_SSL_VERIFY=false" |
| 402 | "Sem saldo — adicione créditos" |
| 429 | "Rate limit — aguarde" |

---

## 8. Estrutura de Arquivos (resumo)

```
backend/app/
├── routers/
│   ├── admin.py      ← painel admin + catálogo de modelos
│   ├── tts.py        ← OpenAI TTS proxy
│   └── stt.py        ← OpenAI Whisper proxy (python-multipart)
├── agent/
│   ├── orchestrator.py ← ROUTE_TO detection, llm_client dispatch
│   ├── prompt.py     ← _LANGUAGE_PREMISE + 5 specialist prompts
│   ├── ai_config.py  ← AIConfigStore (Redis + in-memory cache)
│   └── llm_client.py ← AsyncAnthropic | AsyncOpenAI por provedor

frontend/src/
├── components/
│   ├── Specialist/
│   │   ├── SpecialistSelector.tsx ← dropdown com 5 especialistas
│   │   └── SpecialistToast.tsx    ← notificação de roteamento
│   └── Voice/
│       └── VoiceModal.tsx         ← modal NDX canvas + Web Audio API
├── hooks/
│   ├── useWhisperInput.ts  ← MediaRecorder + POST /stt/transcribe
│   ├── useVoiceOutput.ts   ← POST /tts/speak + fallback Web Speech
│   ├── useWakeWord.ts      ← hands-free com Whisper listening
│   └── useVoiceInput.ts    ← Web Speech API (fallback/standby)
└── types/index.ts ← SPECIALISTS catalog, SpecialistId, WSEventType
```

---

## 9. Premissa de Idioma

O `_LANGUAGE_PREMISE` é a PRIMEIRA instrução de todos os system prompts:

```
PREMISSA FUNDAMENTAL
Você SEMPRE responde em Português Brasileiro (pt-BR), sem exceção.
Isso se aplica a todas as respostas, análises, resumos, erros e mensagens de sistema.
Nunca responda em inglês ou qualquer outro idioma, mesmo que a pergunta seja feita em outro idioma.
```

Aplicado a: todos os 5 especialistas × todos os 4 perfis de usuário × modo voz.
