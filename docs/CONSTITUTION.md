# NOC AI Chat — Project Constitution
**Versão:** 3.0 | **Data:** 2026-04-21 | **Anterior:** 2.0 (2026-04-09)

Documento não-negociável que governa todo o desenvolvimento do projeto.
Specs, planos e tasks não podem contradizer esta constituição sem revisão explícita.

---

## 1. Visão do Produto

Assistente de IA conversacional para NOC (Network Operations Center) com:
- **Multimodal**: texto, voz de entrada (Whisper), voz de saída (OpenAI TTS)
- **Hands-free**: wake word "Olá NOC", encerramento "NOC obrigado"
- **Multi-especialista**: 5 agentes com domínios distintos + roteamento automático
- **Multi-provedor**: Anthropic direto ou qualquer modelo via OpenRouter
- **Multi-ferramenta**: Zabbix, Datadog, Grafana, ThousandEyes
- **Idioma**: sempre Português Brasileiro (pt-BR) — premissa inegociável

---

## 2. Arquitetura

```
Browser (React 18 PWA)
  ├── Chat (texto + Markdown + Recharts)
  ├── Voz entrada: OpenAI Whisper → /stt/transcribe
  ├── Voz saída: OpenAI TTS (onyx/nova) → /tts/speak
  ├── Wake word: Web Speech API (standby) + Whisper (listening)
  └── Modal NDX: Canvas + Web Audio API (ondas em tempo real)
        ↓ WebSocket streaming
Backend (FastAPI + AsyncAnthropic/AsyncOpenAI)
  ├── AgentOrchestrator (loop agêntico, streaming real)
  ├── AIConfigStore (provedor/modelo/key em runtime via Redis)
  ├── SpecialistRouter (5 especialistas, ROUTE_TO automático)
  └── MCPDispatcher → MCP Servers
        ├── mcp-zabbix      (8 tools, multi-cliente, tag Organization)
        ├── mcp-datadog     (5 tools, health cacheado)
        ├── mcp-grafana     (2 tools)
        └── mcp-thousandeyes (6 tools, API v7)
              ↕ Redis (sessões, histórico 50 turnos, TTL 24h, ai_config)
```

---

## 3. Stack

### Frontend

| Categoria | Tecnologia |
|-----------|-----------|
| Framework | React 18 + TypeScript 5 strict |
| Build | Vite 5 |
| Estilo | Tailwind CSS 3 |
| Estado | Zustand 4 |
| Gráficos | Recharts 2 + react-is |
| Áudio entrada | Web Speech API (standby) + OpenAI Whisper via backend |
| Áudio saída | OpenAI TTS via backend (`/tts/speak`) + Web Speech fallback |
| Animação voz | Canvas 2D + Web Audio API (AnalyserNode) |
| PWA | vite-plugin-pwa |

**Proibido:** Redux, jQuery, Bootstrap, MUI, Ant Design.

### Backend

| Categoria | Tecnologia |
|-----------|-----------|
| Framework | FastAPI 0.115+ |
| IA Anthropic | anthropic.AsyncAnthropic |
| IA OpenRouter | openai.AsyncOpenAI (OpenAI-compatible) |
| Cache | Redis 7 (redis.asyncio) |
| Auth | python-jose + bcrypt |
| Upload | python-multipart (Form/File endpoints) |
| HTTP | httpx.AsyncClient |
| Logs | structlog JSON |

**Regra crítica:** sempre `AsyncAnthropic` — nunca `Anthropic` síncrono.
**Regra crítica:** OpenRouter usa `AsyncOpenAI` — Anthropic SDK rejeita o host.

---

## 4. Especialistas NOC

| ID | Nome | Ferramentas | Gatilho automático |
|----|------|-------------|-------------------|
| `generalista` | Generalista NOC | Todas | Entrada padrão, triagem |
| `apm` | APM & Logs | Datadog + Grafana | Erros HTTP, latência, traces |
| `infra` | Infraestrutura | Zabbix + Datadog | CPU, memória, disco, host down |
| `conectividade` | Conectividade | ThousandEyes | Latência de rede, BGP, DNS |
| `observabilidade` | Observabilidade | Grafana + Datadog | Dashboards, SLOs, correlação |

O Generalista emite `<ROUTE_TO specialist="X" reason="Y"/>` quando identifica o domínio. O backend detecta a tag, atualiza `session.active_specialist`, emite evento `specialist_change` via WS e continua com o especialista correto na próxima mensagem.

---

## 5. Modo Voz

### STT (entrada)
- **Premium (Whisper)**: grava com MediaRecorder → POST `/stt/transcribe` → Whisper API
  - Requer `OPENAI_API_KEY`
  - Prompt NOC: termos técnicos para melhor reconhecimento
  - `language=pt` forçado, `echoCancellation + noiseSuppression` no microfone
- **Fallback**: Web Speech API do Chrome

### TTS (saída)
- **Premium (OpenAI TTS)**: GET `/tts/speak` → MP3 → Audio()
  - Voz padrão: `onyx` (grave, autoritativa)
  - Modelo padrão: `tts-1-hd` (mais natural)
  - Configurável pelo painel `/admin`
- **Fallback**: Web Speech API (SpeechSynthesisUtterance)

### Hands-free
- **Standby**: Web Speech API contínua ouvindo wake words
- **Wake words**: "olá noc", "ola noc", "hey noc", "nokia", "nok" e variações pt-BR
- **Stop words**: "noc obrigado", "tchau noc", "pare noc" e variações
- **Listening**: Whisper (se disponível) ou Web Speech API
- **Loop automático**: após TTS terminar, volta a ouvir automaticamente
- **Modal NDX**: overlay com Canvas animado, ondas reativas ao microfone (Web Audio API)

### System prompt em modo voz
O `_VOICE_ADDENDUM` vai no TOPO do system prompt (prioridade máxima):
- PROIBIDO: tabelas, gráficos (`chart`), headings, bullets, code blocks
- OBRIGATÓRIO: texto corrido, máximo 5 frases
- Tags `<ROUTE_TO>` substituídas por texto natural

---

## 6. Premissa de Idioma

**Inegociável:** o agente SEMPRE responde em Português Brasileiro.
A `_LANGUAGE_PREMISE` é inserida no topo de todos os system prompts,
antes de qualquer instrução específica de especialista ou perfil.

---

## 7. Painel de Administração

Rota `/admin`, acesso restrito ao perfil `admin`.

| Seção | Funcionalidade |
|-------|---------------|
| Modelo de IA | Seletor de provedor (Anthropic/OpenRouter) + modelo + API key |
| Testar conexão | POST `/admin/ai-config/test` com diagnóstico por tipo de erro |
| Status | IA, Redis, 4 MCP servers |
| Voz TTS | Seletor de voz (6 opções) + modelo (tts-1/tts-1-hd) + velocidade |

**Catálogo:** 19 modelos — 4 Anthropic + 15 OpenRouter (Claude, GPT-4o, Gemini, Llama, Mistral, DeepSeek, NVIDIA Nemotron, Qwen).

**Importante:** OpenRouter usa `AsyncOpenAI`, não `AsyncAnthropic`. IDs sem sufixo `:free`.

---

## 8. Usuários Seed

| Email | Senha | Perfil |
|-------|-------|--------|
| `admin@noc.local` | `admin123` | N2 |
| `n1@noc.local` | `noc2024` | N1 |
| `eng@noc.local` | `eng2024` | Engineer |
| `gestor@noc.local` | `mgr2024` | Manager |
| `admin-sys@noc.local` | `admin-noc-2024` | **Admin** |

---

## 9. Variáveis de Ambiente

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `ANTHROPIC_API_KEY` | ✅ | Sem ela o agente não responde |
| `JWT_SECRET` | ✅ | `openssl rand -hex 32` |
| `OPENAI_API_KEY` | Opcional | TTS (voz Jarvis) + Whisper STT |
| `TTS_VOICE` | Opcional | Padrão: `onyx` |
| `TTS_MODEL` | Opcional | Padrão: `tts-1-hd` |
| `TTS_SPEED` | Opcional | Padrão: `0.92` |
| `WHISPER_MODEL` | Opcional | Padrão: `whisper-1` |
| `WHISPER_LANG` | Opcional | Padrão: `pt` |
| `ANTHROPIC_SSL_VERIFY` | Opcional | `false` para proxy corporativo |
| `OPENROUTER_SSL_VERIFY` | Opcional | `false` para proxy (padrão já false) |
| `ZABBIX_URL` | Opcional | Mock se ausente |
| `DATADOG_API_KEY` | Opcional | Mock se ausente |
| `THOUSANDEYES_TOKEN` | Opcional | Mock se ausente |
| `GRAFANA_URL` | Opcional | Mock se ausente |

---

## 10. Git & Qualidade

- Branches: `feature/`, `fix/`, `docs/`, `chore/`
- Commits: Conventional Commits
- TypeScript: strict, zero `any`, `tsc --noEmit` = 0 erros antes de merge
- Python: `py_compile` em todos os arquivos antes de commit
- Testes: `make test` deve passar (baseline: 105 testes)
