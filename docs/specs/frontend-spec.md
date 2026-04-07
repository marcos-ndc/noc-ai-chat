# Spec: Frontend — NOC AI Chat (v1 MVP)
**Feature:** `feature/frontend-base`  
**Data:** 2026-04-07  
**Status:** Aprovado

---

## Overview

Interface web responsiva (PWA) para interação com o agente de IA NOC. O usuário pode conversar com o agente via texto ou voz. O agente responde em streaming, indicando em tempo real quais ferramentas está consultando. A interface se adapta ao perfil do usuário logado.

---

## User Journeys

### J1 — Login
1. Usuário acessa a URL da aplicação
2. Vê tela de login com campo de email/senha
3. Autentica com sucesso → redireciona para o chat
4. Token JWT armazenado em memória

### J2 — Conversa por texto
1. Usuário digita uma pergunta no campo de input
2. Pressiona Enter ou clica em Enviar
3. Mensagem aparece no histórico (lado direito, balão azul)
4. Indicador mostra "Consultando Zabbix..." enquanto o agente trabalha
5. Resposta aparece em streaming (lado esquerdo, balão escuro) com Markdown renderizado
6. Histórico é mantido durante a sessão

### J3 — Conversa por voz (STT → texto)
1. Usuário clica no botão de microfone
2. Indicador visual mostra que está gravando
3. Usuário fala a pergunta
4. Clica novamente (ou pausa automática) para encerrar gravação
5. Texto transcrito aparece no campo de input
6. Fluxo segue igual ao J2

### J4 — Resposta em voz bidirecional
1. Usuário ativa o toggle "Modo Voz"
2. Após cada resposta do agente, TTS lê o texto automaticamente
3. Usuário pode interromper o áudio clicando em "Parar"
4. Toggle pode ser desativado a qualquer momento

### J5 — Indicador de ferramentas
1. Durante o processamento, o agente envia eventos de status
2. Interface exibe qual ferramenta está sendo consultada: "🔍 Zabbix", "📊 Datadog", etc.
3. Ao finalizar, indicador desaparece e a resposta começa a aparecer

---

## Functional Requirements

- **FR-1:** O sistema SHALL exibir uma tela de login com campos email e senha
- **FR-2:** O sistema SHALL autenticar via POST `/auth/login` e armazenar o JWT em memória
- **FR-3:** O sistema SHALL redirecionar usuários não autenticados para `/login`
- **FR-4:** O sistema SHALL manter conexão WebSocket com o backend durante a sessão de chat
- **FR-5:** O sistema SHALL exibir mensagens do usuário e do agente em formato de chat (bolhas)
- **FR-6:** O sistema SHALL renderizar Markdown nas respostas do agente (bold, code blocks, tabelas, listas)
- **FR-7:** O sistema SHALL exibir respostas em streaming (token por token) sem aguardar a resposta completa
- **FR-8:** O sistema SHALL exibir indicador animado com o nome da ferramenta sendo consultada
- **FR-9:** O sistema SHALL permitir entrada de voz via Web Speech API (STT)
- **FR-10:** O sistema SHALL transcrever voz para texto no campo de input antes de enviar
- **FR-11:** O sistema SHALL oferecer toggle para ativar/desativar resposta em áudio (TTS)
- **FR-12:** O sistema SHALL ler a resposta do agente em voz via Web Speech API (TTS) quando o modo estiver ativo
- **FR-13:** O sistema SHALL ser responsivo e funcionar em mobile (≥ 375px) e desktop (≥ 1024px)
- **FR-14:** O sistema SHALL ser instalável como PWA (manifest + service worker)
- **FR-15:** O sistema SHALL exibir o nome e perfil do usuário logado no header
- **FR-16:** O sistema SHALL permitir logout, invalidando o token em memória

---

## Non-Functional Requirements

- **NFR-1:** First Contentful Paint < 2s em conexão 4G simulada
- **NFR-2:** Bundle principal < 300KB gzipped
- **NFR-3:** A interface deve responder a interações em < 100ms (feedback visual imediato)
- **NFR-4:** WebSocket deve reconectar automaticamente em até 3 tentativas com backoff exponencial
- **NFR-5:** WCAG 2.1 AA — todos os controles acessíveis por teclado, contraste ≥ 4.5:1
- **NFR-6:** Funcional nos browsers: Chrome 120+, Firefox 120+, Safari 17+, Edge 120+

---

## Acceptance Criteria

**FR-1/FR-2:**
- Given: usuário acessa `/login`
- When: preenche email/senha corretos e submete
- Then: é redirecionado para `/chat` e vê seu nome no header

**FR-7:**
- Given: usuário enviou uma pergunta
- When: o agente está processando
- Then: cada token aparece individualmente na tela com delay < 50ms entre tokens

**FR-9/FR-10:**
- Given: usuário clica no botão de microfone
- When: fala por 3 segundos e para
- Then: o texto transcrito aparece no input em até 500ms

**FR-11/FR-12:**
- Given: modo voz bidirecional ativado
- When: agente termina de responder
- Then: TTS inicia leitura automaticamente em até 1s após o fim do streaming

---

## Out of Scope (v1)

- Histórico persistente entre sessões (Redis apenas durante sessão ativa)
- Upload de arquivos/screenshots para o agente
- Notificações push
- Múltiplas conversas/tabs simultâneas
- Tema claro/escuro toggle (apenas tema escuro no MVP)
- i18n / múltiplos idiomas (estrutura preparada, não implementada)
- Integração com SSO/AD

---

## Dependencies

- Backend FastAPI rodando em `VITE_BACKEND_URL` (WebSocket + REST)
- Para desenvolvimento: mock server que simula respostas do agente

---

## Open Questions

- [ ] O backend vai suportar reconexão de WebSocket com retomada de contexto? (Assumido: sim, via session ID no Redis)
- [ ] Qual o tamanho máximo do histórico exibido no chat? (Assumido: últimas 100 mensagens, scroll infinito futuro)
