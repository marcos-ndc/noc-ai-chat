import { useCallback, useEffect, useRef, useState } from 'react'
import { Header } from '../components/Layout/Header'
import { ChatMessage } from '../components/Chat/ChatMessage'
import { ChatInput } from '../components/Chat/ChatInput'
import { StatusIndicator } from '../components/StatusIndicator/StatusIndicator'
import { useWebSocket } from '../hooks/useWebSocket'
import { useVoiceOutput } from '../hooks/useVoiceOutput'
import { useAuth } from '../hooks/useAuth'
import type { Message, ToolName, WSEvent } from '../types'

const BACKEND_WS = (import.meta.env.VITE_BACKEND_URL ?? 'ws://localhost:8000')
  .replace(/^http/, 'ws') + '/ws/chat'

function generateId(): string {
  return Math.random().toString(36).slice(2, 9)
}

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  role: 'agent',
  content: `## Olá! Sou o agente de IA da NOC 👋

Estou conectado às suas ferramentas de monitoramento e pronto para ajudar com:

- 🔴 **Incidentes ativos** — Zabbix, Datadog, ThousandEyes
- 📊 **Métricas e dashboards** — Grafana, Datadog
- 🔍 **Análise de causa raiz** — correlação entre ferramentas
- 📋 **Orientação de runbooks** — procedimentos e próximos passos

Como posso ajudar você agora?`,
  status: 'done',
  timestamp: new Date(),
}

export function ChatPage() {
  const { user, logout } = useAuth()
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [activeTools, setActiveTools] = useState<ToolName[]>([])
  const [isAgentTyping, setIsAgentTyping] = useState(false)
  const [voiceOutputEnabled, setVoiceOutputEnabled] = useState(false)
  const [sessionId] = useState(() => generateId())
  const bottomRef = useRef<HTMLDivElement>(null)
  const currentAgentMsgId = useRef<string | null>(null)

  const voiceOutput = useVoiceOutput()

  // Handle incoming WS events
  const handleWSMessage = useCallback((event: WSEvent) => {
    switch (event.type) {
      case 'tool_start':
        if (event.tool) setActiveTools(prev => [...new Set([...prev, event.tool!])])
        break

      case 'tool_end':
        if (event.tool) setActiveTools(prev => prev.filter(t => t !== event.tool))
        break

      case 'agent_token': {
        setIsAgentTyping(true)
        const msgId = currentAgentMsgId.current

        setMessages(prev => {
          const existing = prev.find(m => m.id === msgId)
          if (existing) {
            return prev.map(m =>
              m.id === msgId
                ? { ...m, content: m.content + (event.content ?? ''), status: 'streaming' as const }
                : m
            )
          }
          // Create new agent message
          const newMsg: Message = {
            id: msgId ?? generateId(),
            role: 'agent',
            content: event.content ?? '',
            status: 'streaming',
            timestamp: new Date(),
          }
          currentAgentMsgId.current = newMsg.id
          return [...prev, newMsg]
        })
        break
      }

      case 'agent_done': {
        setIsAgentTyping(false)
        setActiveTools([])
        const msgId = currentAgentMsgId.current

        setMessages(prev =>
          prev.map(m =>
            m.id === msgId
              ? { ...m, status: 'done' as const }
              : m
          )
        )

        // TTS
        if (voiceOutputEnabled) {
          const doneMsg = messages.find(m => m.id === msgId)
          if (doneMsg) {
            // Strip markdown for TTS
            const plainText = doneMsg.content.replace(/[#*`_~\[\]]/g, '').trim()
            voiceOutput.speak(plainText)
          }
        }

        currentAgentMsgId.current = null
        break
      }

      case 'error': {
        setIsAgentTyping(false)
        setActiveTools([])
        setMessages(prev => [...prev, {
          id: generateId(),
          role: 'agent',
          content: `Erro ao processar sua solicitação: ${event.error ?? 'erro desconhecido'}`,
          status: 'error',
          timestamp: new Date(),
        }])
        currentAgentMsgId.current = null
        break
      }
    }
  }, [voiceOutputEnabled, voiceOutput, messages])

  const { isConnected, send } = useWebSocket(BACKEND_WS, {
    onMessage: handleWSMessage,
    autoReconnect: true,
  })

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isAgentTyping])

  const handleSend = useCallback((content: string) => {
    // Add user message
    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content,
      status: 'done',
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])

    // Prepare agent message slot
    const agentId = generateId()
    currentAgentMsgId.current = agentId
    setIsAgentTyping(true)

    // Send via WS
    send({ type: 'user_message', content, sessionId })
  }, [send, sessionId])

  return (
    <div className="flex flex-col h-screen noc-grid scanlines">
      <Header user={user} isConnected={isConnected} onLogout={logout} />

      {/* Messages area */}
      <main className="flex-1 overflow-y-auto py-4 space-y-1">
        {messages.map(msg => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        <StatusIndicator activeTools={activeTools} isTyping={isAgentTyping} />

        <div ref={bottomRef} />
      </main>

      {/* Input area */}
      <ChatInput
        onSend={handleSend}
        disabled={!isConnected || isAgentTyping}
        voiceOutputState={voiceOutput.state}
        voiceOutputEnabled={voiceOutputEnabled}
        onVoiceOutputToggle={() => {
          if (voiceOutputEnabled) voiceOutput.stop()
          setVoiceOutputEnabled(v => !v)
        }}
        onVoiceOutputStop={voiceOutput.stop}
        placeholder={
          !isConnected
            ? 'Aguardando conexão...'
            : isAgentTyping
              ? 'Agente processando...'
              : 'Pergunte sobre incidentes, alertas, métricas...'
        }
      />
    </div>
  )
}
