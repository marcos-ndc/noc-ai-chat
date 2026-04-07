import type { VoiceInputState } from '../../types'

interface VoiceInputButtonProps {
  state: VoiceInputState
  isSupported: boolean
  onStart: () => void
  onStop: () => void
}

const stateConfig = {
  idle: {
    label: 'Ativar microfone',
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm-2 17.93A8.001 8.001 0 0 1 4.07 13H6.1a6 6 0 0 0 11.8 0h2.03A8.001 8.001 0 0 1 14 18.93V21h2v2H8v-2h2v-2.07z"/>
      </svg>
    ),
    className: 'text-noc-muted hover:text-noc-accent hover:border-noc-accent/50',
  },
  listening: {
    label: 'Parar gravação',
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm-2 17.93A8.001 8.001 0 0 1 4.07 13H6.1a6 6 0 0 0 11.8 0h2.03A8.001 8.001 0 0 1 14 18.93V21h2v2H8v-2h2v-2.07z"/>
      </svg>
    ),
    className: 'text-noc-danger border-noc-danger/60 glow-danger animate-pulse',
  },
  processing: {
    label: 'Processando voz...',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5 animate-spin">
        <circle cx="12" cy="12" r="10" strokeOpacity="0.3" />
        <path d="M12 2a10 10 0 0 1 10 10" />
      </svg>
    ),
    className: 'text-noc-accent border-noc-accent/60',
  },
  error: {
    label: 'Microfone indisponível',
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M12 1a4 4 0 0 1 4 4v.172L5.172 16H5V5a4 4 0 0 1 7-2.828zM3.28 2.22 2 3.5l2 2V11a4 4 0 0 0 7.172 2.45L19.5 21.5l1.28-1.28L3.28 2.22zM10 18.93V21H8v2h8v-2h-2v-2.07A8.001 8.001 0 0 0 19.93 13h-2.03a6 6 0 0 1-11.8 0H4.07A8.001 8.001 0 0 0 10 18.93z"/>
      </svg>
    ),
    className: 'text-noc-warning border-noc-warning/60',
  },
}

export function VoiceInputButton({ state, isSupported, onStart, onStop }: VoiceInputButtonProps) {
  if (!isSupported) return null

  const config = stateConfig[state]
  const isListening = state === 'listening'

  return (
    <button
      type="button"
      aria-label={config.label}
      title={config.label}
      onClick={isListening ? onStop : onStart}
      disabled={state === 'processing'}
      className={`
        relative flex items-center justify-center
        w-9 h-9 rounded-full border transition-all duration-200
        ${config.className}
        disabled:opacity-40 disabled:cursor-not-allowed
      `}
    >
      {config.icon}

      {/* Ripple ring when listening */}
      {isListening && (
        <span className="absolute inset-0 rounded-full border border-noc-danger/40 animate-ping" />
      )}
    </button>
  )
}
