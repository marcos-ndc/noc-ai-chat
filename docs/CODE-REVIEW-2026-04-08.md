# Code Review — NOC AI Chat
**Data:** 2026-04-08 | **Revisor:** Claude | **Severidade:** 🔴 Crítico · 🟠 Alto · 🟡 Médio · 🟢 Baixo

---

## Resumo Executivo

O código tem uma arquitetura sólida mas acumula **8 bugs funcionais** introduzidos durante o desenvolvimento iterativo por correções que criaram novos problemas. Os problemas críticos impedem o funcionamento básico do chat. Abaixo cada issue com localização exata e correção.

---

## 🔴 CRÍTICO — Impedem funcionamento

### CR-1: Login redireciona mesmo quando falha
**Arquivo:** `frontend/src/pages/LoginPage.tsx:14-17`

```typescript
// PROBLEMA: navega para /chat independente de erro
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault()
  await login({ email, password })
  navigate('/chat')  // ← executa mesmo se login falhou
}

// CORREÇÃO:
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault()
  await login({ email, password })
  if (useAuthStore.getState().isAuthenticated) {
    navigate('/chat')
  }
}
```

---

### CR-2: Orchestrator usa `messages.create` síncrono — bloqueia o event loop
**Arquivo:** `backend/app/agent/orchestrator.py:258-264`

```python
# PROBLEMA: chamada síncrona dentro de async generator — bloqueia uvicorn
response = self._client.messages.create(...)

# CORREÇÃO: usar AsyncAnthropic
from anthropic import AsyncAnthropic
self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
response = await self._client.messages.create(...)
```
O cliente `anthropic.Anthropic` é **síncrono**. Dentro de um `async def` com `AsyncGenerator`, isso bloqueia o event loop do uvicorn enquanto a API responde (podendo demorar 10-30s). Nenhum outro request é atendido durante esse tempo.

---

### CR-3: "Fake streaming" — tokens chegam todos de uma vez
**Arquivo:** `backend/app/agent/orchestrator.py:280-289`

```python
# PROBLEMA: espera a resposta COMPLETA, depois simula chunks de 4 chars
chunk_size = 4
for i in range(0, len(combined), chunk_size):
    chunk = combined[i:i + chunk_size]
    yield WSOutbound(type=WSEventType.agent_token, content=chunk)
```
O usuário vê tudo aparecendo de uma vez após longa espera, não streaming real.

```python
# CORREÇÃO: usar stream=True da API Anthropic
async with self._client.messages.stream(
    model=settings.claude_model,
    max_tokens=4096,
    system=system_prompt,
    messages=claude_messages,
) as stream:
    async for text in stream.text_stream:
        yield WSOutbound(type=WSEventType.agent_token,
                        messageId=message_id, content=text)
```

---

### CR-4: Race condition — `currentAgentMsgId` definido DEPOIS do primeiro token
**Arquivo:** `frontend/src/pages/ChatPage.tsx:142-157` e `52-85`

```typescript
// handleSend (linha 151-152):
const agentId = generateId()
currentAgentMsgId.current = agentId  // ← definido aqui

// mas handleWSMessage case 'agent_token' (linha 64-83):
const msgId = currentAgentMsgId.current  // ← pode ser null se token chega rápido

// Se o primeiro agent_token chegar antes de handleSend retornar:
// msgId = null → cria mensagem com id aleatório
// currentAgentMsgId.current = newMsg.id (novo id)
// Resultado: dois slots de mensagem, conteúdo duplicado
```
**Correção:** Setar `currentAgentMsgId.current` antes de chamar `send()`.

---

### CR-5: Session role mapping quebrado para histórico
**Arquivo:** `backend/app/agent/session.py:63-65`

```python
# PROBLEMA: comparação com string literal em vez do enum
{"role": msg.role.value if msg.role != "agent" else "assistant"}
#                                    ^^^^^^^^^^
# msg.role é MessageRole enum, "agent" é string — nunca são iguais!
# Resultado: TODOS os roles viram "user" na API Claude → erro ou resposta errada

# CORREÇÃO:
{"role": "user" if msg.role == MessageRole.user else "assistant"}
```

---

## 🟠 ALTO — Causam bugs visíveis

### AL-1: LoginPage.tsx — `useAuth` instancia estado local por renderização
**Arquivo:** `frontend/src/hooks/useAuth.ts:34-38`

```typescript
// PROBLEMA: useState dentro de useAuth cria estado LOCAL por chamada
// LoginPage e ChatPage têm instâncias separadas de isLoading/error
export function useAuth(): UseAuthReturn {
  const [isLoading, setIsLoading] = useState(false)  // ← local, não compartilhado
  const [error, setError] = useState<string | null>(null)
```
O `error` e `isLoading` não persistem entre navegações. Mover para o Zustand store.

---

### AL-2: `datetime.utcnow()` depreciado causa warnings constantes
**Arquivo:** `backend/app/models.py:65,72,104`

```python
# PROBLEMA: Python 3.12 deprecation warning em cada request
timestamp: datetime = Field(default_factory=datetime.utcnow)

# CORREÇÃO:
from datetime import datetime, timezone
timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

---

### AL-3: MCP server ports inconsistentes no docker-compose
**Arquivo:** `docker-compose.yml`

```yaml
# PROBLEMA: backend espera mcp-datadog na :8002 mas internamente é :8001
mcp-datadog:
  ports: ["8002:8001"]  # host:container
# settings.py: mcp_datadog_url = "http://mcp-datadog:8002"  # ERRADO! container usa 8001

# CORREÇÃO: comunicação interna usa porta do container (8001), não do host
# settings.py: mcp_datadog_url = "http://mcp-datadog:8001"  # correto
```
Dentro da rede Docker, containers se comunicam pela porta **interna** (8001), não pela porta mapeada no host. O backend nunca consegue chamar Datadog, Grafana ou ThousandEyes.

---

### AL-4: `ChatMessage.timestamp` desserializado como string, não Date
**Arquivo:** `frontend/src/pages/ChatPage.tsx` e `ChatMessage.tsx:10`

```typescript
// Mensagens vindas do WS têm timestamp como string ISO
// formatTime() chama date.toLocaleTimeString() que falha em strings
// Correção em ChatMessage.tsx:
const ts = message.timestamp instanceof Date
  ? message.timestamp
  : new Date(message.timestamp)
return ts.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
```

---

## 🟡 MÉDIO — Afetam qualidade / manutenibilidade

### ME-1: `EmailStr` importado mas não usado em models.py
**Arquivo:** `backend/app/models.py:4`
```python
from pydantic import BaseModel, EmailStr, Field  # EmailStr não usado
```

### ME-2: `UserOut` e `ChatMessage` importados 2x no orchestrator
**Arquivo:** `backend/app/agent/orchestrator.py:7-14` e linha 222
```python
# Topo do arquivo: from app.models import ChatMessage, MessageRole, ...
# Dentro de process_message():
from app.models import ChatMessage, MessageRole  # duplicado
```

### ME-3: `voiceOutput` instanciado tanto em `ChatInput` quanto em `ChatPage`
**Arquivo:** `frontend/src/components/Chat/ChatInput.tsx:20` e `ChatPage.tsx:46`
Dois contextos de TTS separados — podem conflitar ao falar ao mesmo tempo.

### ME-4: `build_claude_messages` em session.py nunca é chamado
**Arquivo:** `backend/app/agent/session.py:58-65`
O orchestrator reimplementa a mesma lógica inline. Código morto.

### ME-5: `tools_used: set[ToolName]` no orchestrator nunca salvo na sessão
**Arquivo:** `backend/app/agent/orchestrator.py:250`
Coletado mas nunca anexado às mensagens — o frontend nunca recebe `toolsUsed`.

---

## 🟢 BAIXO — Melhorias

### BA-1: JWT exposto na URL do WebSocket
O token aparece em logs do servidor e no histórico do browser.
**Alternativa:** header `Authorization` via subprotocol ou handshake HTTP → upgrade.

### BA-2: Seed users com senhas em texto claro no código
**Arquivo:** `backend/app/auth/service.py:28-60`
Para produção: mover para banco de dados com migrações.

### BA-3: `import json` dentro de método `to_json()`
**Arquivo:** `backend/app/models.py:92`
```python
def to_json(self) -> str:
    import json  # ← mover para topo do arquivo
```

---

## Prioridade de Correção

| # | Issue | Impacto | Esforço |
|---|-------|---------|---------|
| 1 | CR-2: AsyncAnthropic | Bloqueia event loop | 15 min |
| 2 | CR-3: Streaming real | UX degradado | 30 min |
| 3 | CR-5: Role mapping | Histórico quebrado | 5 min |
| 4 | AL-3: MCP ports | Ferramentas não chamadas | 5 min |
| 5 | CR-1: Login redirect | Auth quebrado | 5 min |
| 6 | CR-4: Race condition | Mensagens duplicadas | 15 min |
| 7 | AL-2: utcnow | Warnings constantes | 5 min |
| 8 | AL-4: timestamp Date | UI quebra | 10 min |
