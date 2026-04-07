# NOC AI Chat — Project Constitution
**Versão:** 1.0 | **Data:** 2026-04-07

Documento não-negociável que governa todo o desenvolvimento do projeto.
Specs, planos e tasks não podem contradizer esta constituição sem revisão explícita.

---

## 1. Arquitetura

- **Estilo:** Frontend SPA desacoplado do backend via WebSocket + REST
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS (PWA)
- **Backend:** Python + FastAPI (especificado separadamente)
- **Containers:** Tudo dockerizado — `docker-compose up` deve subir 100% do stack
- **Cloud-agnostic:** Nenhuma dependência de provider específico no código; Azure é preferencial para deploy mas não obrigatório

## 2. Stack Permitido (Frontend)

| Categoria | Tecnologia | Versão |
|-----------|-----------|--------|
| Framework | React | 18.x |
| Linguagem | TypeScript | 5.x |
| Build | Vite | 5.x |
| Estilo | Tailwind CSS | 3.x |
| Estado global | Zustand | 4.x |
| WebSocket | nativo (browser API) | — |
| STT | Web Speech API + Whisper API | — |
| TTS | Web Speech API + OpenAI TTS | — |
| Markdown | react-markdown | 9.x |
| HTTP | fetch nativo | — |
| Testes | Vitest + Testing Library | — |

**Proibido:** Redux, jQuery, Bootstrap, MUI, Ant Design, CSS-in-JS (styled-components/emotion).

## 3. Git & Branching

- Branch principal: `main` (protegida — nunca commitar direto)
- Cada feature: `feature/<nome-descritivo>`
- Cada bug: `fix/<nome-descritivo>`
- Commits seguem Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`
- PRs requerem: testes passando + sem erros TypeScript
- Referência a task no commit: `feat: T005 implement chat message component`

## 4. Qualidade de Código

- TypeScript strict mode: `"strict": true` — zero `any` implícito
- ESLint + Prettier obrigatórios
- Componentes máximo 200 linhas — acima disso, decomponha
- Hooks máximo 100 linhas
- Sem comentários óbvios — código deve ser auto-documentado
- Nomes em inglês no código, comentários podem ser em português

## 5. Testes

- Cobertura mínima: 70% para lógica de negócio (hooks, utils)
- Todo componente crítico tem ao menos 1 smoke test
- Teste escrito ANTES da implementação (TDD) — validate RED before GREEN
- Testes de integração para fluxos principais (login, envio de mensagem, voz)

## 6. Segurança

- Zero secrets no frontend — variáveis de ambiente apenas para URLs públicas
- Inputs sanitizados antes de renderizar (XSS prevention)
- JWT armazenado apenas em memória (não localStorage)
- HTTPS obrigatório em produção

## 7. Acessibilidade

- WCAG 2.1 nível AA
- Todos os controles interativos acessíveis por teclado
- Labels em todos os inputs e botões de voz
- Contraste mínimo 4.5:1

## 8. Performance

- Lighthouse score ≥ 85 em Performance e Acessibilidade
- First Contentful Paint < 2s
- Bundle principal < 300KB gzipped
- Code splitting por rota

## 9. Internacionalização

- Interface em português (pt-BR) por padrão
- Estrutura preparada para i18n futuro (strings centralizadas em `src/i18n/`)

## 10. Docker

- Dockerfile multi-stage para frontend (build + nginx)
- Imagem final < 50MB
- Healthcheck definido em todos os containers
