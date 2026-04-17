import { useCallback, useEffect, useRef, useState } from 'react'
import { VoiceInputButton } from '../VoiceInput/VoiceInputButton'
import { VoiceOutputToggle } from '../VoiceOutput/VoiceOutputToggle'
import { useVoiceInput } from '../../hooks/useVoiceInput'
import type { VoiceOutputState } from '../../types'

interface ChatInputProps {
  onSend: (content: string) => void
  onVoiceSend?: (content: string) => void  // called when text comes from voice input
  disabled?: boolean
  voiceOutputState?: VoiceOutputState
  voiceOutputEnabled?: boolean
  onVoiceOutputToggle?: () => void
  onVoiceOutputStop?: () => void
  placeholder?: string
}

export function ChatInput({
  onSend,
  onVoiceSend,
  disabled = false,
  voiceOutputState = 'idle',
  voiceOutputEnabled = false,
  onVoiceOutputToggle,
  onVoiceOutputStop,
  placeholder = 'Pergunte sobre incidentes, alertas, métricas...',
}: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const fromVoiceRef = useRef(false)

  const voiceInput = useVoiceInput({
    onResult: (transcript) => {
      fromVoiceRef.current = true
      setValue(transcript)
      textareaRef.current?.focus()
    },
  })

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`
  }, [value])

  // Fill input from voice transcript while speaking
  useEffect(() => {
    if (voiceInput.state === 'listening' && voiceInput.transcript) {
      setValue(voiceInput.transcript)
    }
  }, [voiceInput.transcript, voiceInput.state])

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    if (fromVoiceRef.current && onVoiceSend) {
      onVoiceSend(trimmed)
    } else {
      onSend(trimmed)
    }
    fromVoiceRef.current = false
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [value, disabled, onSend, onVoiceSend])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const canSend = value.trim().length > 0 && !disabled

  return (
    <div className="border-t border-noc-border bg-noc-bg px-4 py-3">
      {/* Voice transcript preview */}
      {voiceInput.state === 'listening' && voiceInput.transcript && (
        <div className="mb-2 px-3 py-1.5 rounded-lg bg-noc-danger/10 border border-noc-danger/20 text-xs text-noc-muted font-mono">
          <span className="text-noc-danger mr-1">●</span>
          {voiceInput.transcript}
        </div>
      )}

      <div className="flex items-end gap-2">
        {/* Textarea */}
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            aria-label="Campo de mensagem"
            className={`
              w-full resize-none rounded-xl px-4 py-3 pr-12
              bg-noc-surface border text-sm text-noc-text
              placeholder:text-noc-muted font-sans
              focus:outline-none focus:border-noc-accent/60 focus:ring-1 focus:ring-noc-accent/30
              transition-all duration-200 leading-relaxed
              disabled:opacity-50 disabled:cursor-not-allowed
              ${value ? 'border-noc-border/80' : 'border-noc-border/40'}
            `}
          />

          {/* Send button inside textarea */}
          <button
            type="button"
            onClick={handleSend}
            disabled={!canSend}
            aria-label="Enviar mensagem"
            className={`
              absolute right-2 bottom-2 w-8 h-8 rounded-lg
              flex items-center justify-center transition-all duration-200
              ${canSend
                ? 'bg-noc-accent text-noc-bg hover:bg-noc-accent/80 glow-accent'
                : 'bg-noc-border/40 text-noc-muted cursor-not-allowed'
              }
            `}
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>

        {/* Voice input button */}
        <VoiceInputButton
          state={voiceInput.state}
          isSupported={voiceInput.isSupported}
          onStart={voiceInput.start}
          onStop={voiceInput.stop}
        />
      </div>

      {/* Bottom bar: shortcuts + voice output toggle */}
      <div className="flex items-center justify-between mt-2">
        <span className="text-[10px] text-noc-muted font-mono">
          Enter para enviar · Shift+Enter nova linha
        </span>

        <VoiceOutputToggle
          enabled={voiceOutputEnabled}
          state={voiceOutputState}
          isSupported={'speechSynthesis' in window}
          onToggle={onVoiceOutputToggle ?? (() => {})}
          onStop={onVoiceOutputStop ?? (() => {})}
        />
      </div>
    </div>
  )
}
