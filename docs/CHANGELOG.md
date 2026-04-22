# Changelog — NOC AI Chat

## v3.2 — 2026-04-22 (atual)

### Segurança
- **Row Level Security**: `session.user_id` verificado em toda reconexão — acesso negado se usuário ≠ dono da sessão
- **CORS restrito em produção**: `CORS_ALLOW_ALL=false` + lista explícita de origens
- **Security Headers** em todas as respostas: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, CSP (prod), HSTS (prod)
- **Auth obrigatória em TTS/STT**: `/tts/speak`, `/tts/voices`, `/stt/transcribe` exigem JWT válido
- **auth/dependencies.py**: `get_current_user` e `require_admin` centralizados como `Depends` reutilizáveis
- **Debug endpoints** desabilitados em produção (`/debug/config` → 404)
- **167 testes** (19 novos de segurança)

### Features
- **ElevenLabs TTS**: suporte nativo pt-BR com fallback automático para OpenAI quando indisponível (proxy)
- **Cumprimentos e despedidas**: TTS fala ao ativar ("Olá! Como posso ajudar?") e ao encerrar o modo voz
- **Handoff de contexto entre especialistas**: ao redirecionar, o novo especialista recebe resumo dos últimos 10 turnos e inicia investigação imediatamente

### Correções críticas
- `specialist_change` ausente do `WSEventType` — especialista nunca assumia a conversa
- `_build_handoff_context` chamado com parâmetro inexistente — handoff nunca enviado
- `_cfg()`: env vars de TTS/STT lidas a cada request (não no import) — chaves reconhecidas sem rebuild
- `useWakeWord` reescrito com fluxo único e determinista — eliminado travamento após segunda pergunta
- `useWhisperInput`: silêncio detectado via Web Audio API (1.5s) — Whisper auto-para quando usuário cala
- Modal NDX desaparecia durante cumprimento — `doSet('speaking')` chamado imediatamente ao ativar

---

## v3.1 — 2026-04-21 (atual)

### Novas features
- **Premissa pt-BR**: `_LANGUAGE_PREMISE` no topo de todos os system prompts — agente sempre responde em Português Brasileiro, independente do modelo

### Correções
- `_enrich_triggers` não definida no MCP Zabbix causava NameError ao consultar alertas reais
- `python-multipart` adicionado ao `requirements.txt` — obrigatório para `UploadFile`/`Form` no FastAPI

---

## v3.0 — 2026-04-21

### Novas features
- **OpenAI Whisper STT**: transcrição de áudio precisa em pt-BR via `/stt/transcribe`
  - MediaRecorder com `echoCancellation + noiseSuppression`
  - Prompt NOC para reconhecer termos técnicos (Zabbix, Datadog, BGP, etc.)
  - Fallback automático para Web Speech API
- **Detecção de fim de fala**: evento `speechend` + timer de silêncio (1.2s) reduz delay de 3-5s para 300-800ms
- **5 Especialistas NOC com roteamento automático**:
  - Generalista, APM & Logs, Infraestrutura, Conectividade, Observabilidade
  - Tag `<ROUTE_TO specialist="X" reason="Y"/>` detectada no streaming
  - Toast de notificação ao redirecionar
  - `SpecialistSelector` dropdown na interface
- **Modal NDX**: overlay Canvas animado com ondas sonoras em tempo real (Web Audio API AnalyserNode)
- **Fix stop words**: `isStopWord()` centralizada — "NOC obrigado" agora encerra corretamente em todos os caminhos de submissão
- **Fix wake word pt-BR**: reconhece "nokia", "nok", "noque" como variações de "NOC"

### Correções
- Wake word não ativava — reescrito com `startRef` (evita stale closures)
- `deactivate()` chamado logo após `activate()` — click propagation fix + `isActive.current` ref
- Loop infinito `aborted` — `continuous=true` + `killRec()` nula ref antes de `abort()`
- Stop words não funcionavam no modo hands-free — `speechend` e silence timer bypassavam a verificação

---

## v2.0 — 2026-04-09

### Novas features
- **Painel Admin** (`/admin`): seletor de modelo de IA, provedor, API key, TTS
- **OpenRouter**: integração com `AsyncOpenAI` SDK (Anthropic SDK rejeita o host)
- **Catálogo de 19 modelos**: Claude, GPT-4o, Gemini, Llama, Mistral, DeepSeek, NVIDIA, Qwen
- **OpenAI TTS**: voz premium `onyx` (Jarvis) via `/tts/speak`, modelo `tts-1-hd`
- **Modo voz adaptativo**: `voiceMode=true` injeta `_VOICE_ADDENDUM` — sem tabelas/gráficos na resposta
- **Wake word hands-free**: "Olá NOC" / "NOC obrigado" com loop automático
- **Admin user**: `admin-sys@noc.local` / `admin-noc-2024`

### Correções
- `uvicorn` not found in PATH — `COPY /usr/local/bin` no Dockerfile multi-stage
- `voiceMode` não chegava ao backend — stale closure corrigida com `fromVoice` direto
- Erros HTML do OpenRouter — strip de tags regex + diagnóstico por `isinstance()`
- `NotFoundError` mostrava mensagem de timeout — `isinstance()` com classes do SDK

---

## v1.0 — 2026-04-07

### Features iniciais
- Chat WebSocket com streaming real token-a-token
- 4 MCP Servers: Zabbix (8 tools), Datadog (5 tools), Grafana (2 tools), ThousandEyes (6 tools)
- Multi-cliente via tag Organization no Zabbix
- Gráficos interativos Recharts inline (7 chartTypes)
- Autenticação JWT + 5 perfis (N1, N2, engineer, manager, admin)
- PWA instalável
- STT/TTS via Web Speech API
- Docker Compose completo com hot-reload
