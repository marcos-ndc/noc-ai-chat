import { useCallback, useEffect, useRef, useState } from 'react'
import { Header } from '../components/Layout/Header'
import { ChatMessage } from '../components/Chat/ChatMessage'
import { ChatInput } from '../components/Chat/ChatInput'
import { StatusIndicator } from '../components/StatusIndicator/StatusIndicator'
import { useWebSocket } from '../hooks/useWebSocket'
import { useVoiceOutput } from '../hooks/useVoiceOutput'
import { useWakeWord } from '../hooks/useWakeWord'
import { VoiceModal } from '../components/Voice/VoiceModal'
import { SpecialistSelector } from '../components/Specialist/SpecialistSelector'
import { SpecialistToast } from '../components/Specialist/SpecialistToast'
import type { SpecialistId } from '../types'
import { useAuth, useAuthStore } from '../hooks/useAuth'
import type { Message, ToolName, WSEvent } from '../types'

/** Remove markdown e blocos chart do texto antes de enviar para TTS */
function stripForVoice(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, '')   // remove code blocks e chart blocks
    .replace(/#{1,6}\s/g, '')          // remove headings
    .replace(/[*_~`|]/g, '')           // remove emphasis, code inline, pipe
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // links → só o texto
    .replace(/^\s*[-•]\s/gm, '')       // remove bullets
    .replace(/\n{2,}/g, '. ')          // parágrafos duplos viram pausa
    .replace(/\n/g, ' ')               // quebras simples viram espaço
    .replace(/\s{2,}/g, ' ')           // múltiplos espaços
    .trim()
}

const BACKEND_WS_BASE = (import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000')
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
  const token = useAuthStore(s => s.token)
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [activeTools, setActiveTools] = useState<ToolName[]>([])
  const [isAgentTyping, setIsAgentTyping] = useState(false)
  const [voiceOutputEnabled, setVoiceOutputEnabled] = useState(false)
  const [voiceMode, setVoiceMode] = useState(false) // true = última mensagem foi por voz
  const [activeSpecialist, setActiveSpecialist] = useState<SpecialistId>('generalista')
  const [routeToast, setRouteToast] = useState<{specialist:string,reason:string}|null>(null)
  const [sessionId] = useState(() => generateId())
  const bottomRef = useRef<HTMLDivElement>(null)
  const currentAgentMsgId = useRef<string | null>(null)

  const voiceOutput = useVoiceOutput()

  // WS URL com token JWT no query param (requerido pelo backend)
  const wsUrl = token ? `${BACKEND_WS_BASE}?token=${token}` : null

  // Handle incoming WS events
  const handleWSMessage = useCallback((event: WSEvent) => {
    switch (event.type) {
      case 'specialist_change':
        if (event.specialist) {
          setActiveSpecialist(event.specialist as SpecialistId)
          setRouteToast({ specialist: event.specialist, reason: event.reason ?? '' })
        }
        break

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

        setMessages(prev => {
          const updated = prev.map(m =>
            m.id === msgId ? { ...m, status: 'done' as const } : m
          )
          // TTS automático: fala se voiceOutput ativo OU se veio de interação por voz
          if ((voiceOutputEnabled || voiceMode || wakeWord.state !== 'off') && msgId) {
            const doneMsg = updated.find(m => m.id === msgId)
            if (doneMsg) {
              const plainText = stripForVoice(doneMsg.content)
              if (plainText) voiceOutput.speak(plainText, activeSpecialist)
            }
          }
          return updated
        })

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
  }, [voiceOutputEnabled, voiceOutput, voiceMode])

  const { isConnected, send } = useWebSocket(wsUrl ?? '', {
    onMessage: handleWSMessage,
    autoReconnect: !!wsUrl,
  })

  // Hands-free: wake word loop (needs isConnected)
  const wakeWord = useWakeWord({
    onQuery:    (text) => handleSend(text, true),
    agentState: isAgentTyping ? 'typing' : 'idle',
    ttsState:   voiceOutput.state === 'speaking' ? 'speaking'
              : voiceOutput.state === 'paused'   ? 'paused'
              : 'idle',
    disabled: !isConnected,
    speak:    voiceOutput.speak,   // for greetings and farewells
  })

  // TTS ativado automaticamente via wakeWord.state check no agent_done handler

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isAgentTyping])

  const handleSend = useCallback((content: string, fromVoice = false) => {
    // Fix: usar fromVoice diretamente (não voiceMode state — setState é async!)
    setVoiceMode(fromVoice)
    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content,
      status: 'done',
      timestamp: new Date(),
    }

    // CR-4: set agentId BEFORE send() to avoid race with first token
    const agentId = generateId()
    currentAgentMsgId.current = agentId
    setIsAgentTyping(true)
    setMessages(prev => [...prev, userMsg])

    // Usa fromVoice diretamente — voiceMode state ainda não atualizou (React async)
    send({ type: 'user_message', content, sessionId, voiceMode: fromVoice, specialist: activeSpecialist })
  }, [send, sessionId])

  return (
    <div className="flex flex-col h-screen noc-grid scanlines">
      <Header user={user} isConnected={isConnected} onLogout={logout} voiceMode={voiceMode} handsFreeState={wakeWord.state} />
      <div className="flex items-center justify-between px-4 py-1.5 border-b border-noc-border/40 bg-noc-bg/40">
        <SpecialistSelector
          active={activeSpecialist}
          onChange={id => {
            setActiveSpecialist(id)
            setRouteToast(null)
          }}
          disabled={isAgentTyping}
        />
        <p className="text-[10px] font-mono text-noc-muted">
          {activeSpecialist !== 'generalista' && '🔀 especialista ativo'}
        </p>
      </div>

      {/* Messages area */}
      <main className="flex-1 overflow-y-auto py-4 space-y-1">
        {messages.map(msg => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        <StatusIndicator activeTools={activeTools} isTyping={isAgentTyping} />

        <div ref={bottomRef} />
      </main>

      {/* Hands-free banner */}
      {wakeWord.state !== 'off' && (
        <div className="flex items-center justify-between px-4 py-2 bg-noc-accent/10 border-t border-noc-accent/20"
          onClick={e => e.stopPropagation()}>
          <div className="flex items-center gap-2 text-xs font-mono text-noc-accent">
            <span className={`w-2 h-2 rounded-full bg-noc-accent ${wakeWord.state === 'listening' ? 'animate-ping' : 'animate-pulse'}`} />
            {wakeWord.state === 'standby'  && <>👂 Aguardando... diga &ldquo;Olá NOC&rdquo;</>}
            {wakeWord.state === 'listening' && <>🎙️ Ouvindo sua pergunta...</>}
            {wakeWord.state === 'waiting'  && <>⏳ Processando...</>}
            {wakeWord.state === 'speaking' && <>🔊 Respondendo...</>}
          </div>
          <button type="button" onClick={e => { e.stopPropagation(); wakeWord.deactivate() }}
            className="text-[10px] font-mono text-noc-muted hover:text-noc-danger transition-colors px-2 py-1 rounded border border-noc-border/40">
            Encerrar modo voz
          </button>
        </div>
      )}

      {/* Input area */}
      <ChatInput
        onSend={handleSend}
        onVoiceSend={(content) => handleSend(content, true)}
        disabled={!isConnected || isAgentTyping}
        voiceOutputState={voiceOutput.state}
        voiceOutputIsPremium={voiceOutput.isPremium}
        voiceOutputEnabled={voiceOutputEnabled}
        onVoiceOutputToggle={() => {
          if (voiceOutputEnabled) voiceOutput.stop()
          setVoiceOutputEnabled(v => !v)
        }}
        onVoiceOutputStop={voiceOutput.stop}
        handsFreeActive={wakeWord.state !== 'off'}
        handsFreeSupported={wakeWord.isSupported}
        onHandsFreeToggle={() => {
          // Use isActive ref — always reads LIVE value, avoids stale closure bug
          // wakeWord.state is captured at render time and can be stale
          if (wakeWord.isActive.current) {
            wakeWord.deactivate()
          } else {
            wakeWord.activate()
          }
        }}
        placeholder={
          !isConnected
            ? 'Aguardando conexão...'
            : isAgentTyping
              ? 'Agente processando...'
              : 'Pergunte sobre incidentes, alertas, métricas...'
        }
      />
      {/* Voice modal overlay */}
      <SpecialistToast
        specialist={routeToast?.specialist ?? null}
        reason={routeToast?.reason ?? null}
      />
      <VoiceModal
        state={wakeWord.state}
        onClose={wakeWord.deactivate}
      />
    </div>
  )
}
