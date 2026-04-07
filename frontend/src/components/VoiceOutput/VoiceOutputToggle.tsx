import type { VoiceOutputState } from '../../types'

interface VoiceOutputToggleProps {
  enabled: boolean
  state: VoiceOutputState
  isSupported: boolean
  onToggle: () => void
  onStop: () => void
}

export function VoiceOutputToggle({ enabled, state, isSupported, onToggle, onStop }: VoiceOutputToggleProps) {
  if (!isSupported) return null

  const isSpeaking = state === 'speaking' || state === 'paused'

  return (
    <div className="flex items-center gap-2">
      {/* Stop speaking button — only when active */}
      {isSpeaking && (
        <button
          type="button"
          aria-label="Parar leitura"
          title="Parar leitura"
          onClick={onStop}
          className="flex items-center justify-center w-7 h-7 rounded-full border border-noc-warning/60 text-noc-warning hover:bg-noc-warning/10 transition-all"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5">
            <rect x="6" y="6" width="12" height="12" rx="1" />
          </svg>
        </button>
      )}

      {/* Toggle */}
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-label={enabled ? 'Desativar resposta por voz' : 'Ativar resposta por voz'}
        title={enabled ? 'Resposta por voz: ligada' : 'Resposta por voz: desligada'}
        onClick={onToggle}
        className={`
          relative flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono
          border transition-all duration-200
          ${enabled
            ? 'bg-noc-accent/10 border-noc-accent/50 text-noc-accent'
            : 'border-noc-border text-noc-muted hover:border-noc-border/80'
          }
        `}
      >
        <svg viewBox="0 0 24 24" fill="currentColor" className={`w-3.5 h-3.5 ${isSpeaking ? 'animate-pulse' : ''}`}>
          <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
        </svg>
        <span>{enabled ? 'Voz ON' : 'Voz'}</span>
      </button>
    </div>
  )
}
