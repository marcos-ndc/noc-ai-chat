/**
 * useWakeWord — Modo hands-free estilo Alexa
 *
 * Escuta continuamente em background por palavras de ativação/desativação.
 * Quando ativado, fica em loop: ouve pergunta → envia → aguarda resposta → ouve novamente.
 *
 * Palavra de ativação:  "olá noc" / "ola noc" / "hey noc"
 * Palavra de parada:    "noc obrigado" / "tchau noc" / "pare noc"
 */
import { useCallback, useEffect, useRef, useState } from 'react'

export type HandsFreeState =
  | 'off'          // modo normal, não ouvindo
  | 'standby'      // ouvindo em background por wake word
  | 'listening'    // gravando pergunta do usuário
  | 'waiting'      // aguardando resposta do agente
  | 'speaking'     // agente falando — vai ouvir logo em seguida

const WAKE_WORDS    = ['olá noc', 'ola noc', 'hey noc', 'ei noc', 'olá noc']
const STOP_WORDS    = ['noc obrigado', 'tchau noc', 'pare noc', 'noc tchau', 'desligar noc']
const LISTEN_DELAY  = 800   // ms após o agente falar para começar a ouvir

interface UseWakeWordOptions {
  onQuery:    (text: string) => void   // called when user says something (not a command)
  agentState: 'idle' | 'typing'        // whether agent is currently responding
  ttsState:   'idle' | 'speaking' | 'paused'
  disabled?:  boolean
}

interface UseWakeWordReturn {
  state:        HandsFreeState
  activate:     () => void             // manual activation
  deactivate:   () => void             // manual deactivation
  isSupported:  boolean
}

export function useWakeWord({
  onQuery,
  agentState,
  ttsState,
  disabled = false,
}: UseWakeWordOptions): UseWakeWordReturn {
  const [state, setState] = useState<HandsFreeState>('off')

  const recognitionRef  = useRef<SpeechRecognition | null>(null)
  const stateRef        = useRef<HandsFreeState>('off')
  const agentStateRef   = useRef(agentState)
  const ttsStateRef     = useRef(ttsState)
  const listenTimerRef  = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  // Keep refs in sync
  useEffect(() => { agentStateRef.current = agentState }, [agentState])
  useEffect(() => { ttsStateRef.current   = ttsState   }, [ttsState])

  const setStateSync = (s: HandsFreeState) => {
    stateRef.current = s
    setState(s)
  }

  const stopRecognition = useCallback(() => {
    recognitionRef.current?.abort()
    recognitionRef.current = null
  }, [])

  const clearListenTimer = useCallback(() => {
    if (listenTimerRef.current) {
      clearTimeout(listenTimerRef.current)
      listenTimerRef.current = null
    }
  }, [])

  // ── Start one recognition session ──────────────────────────────────────────
  const startSession = useCallback((mode: 'standby' | 'listening') => {
    if (!isSupported || stateRef.current === 'off') return

    stopRecognition()

    const SR          = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SR()
    recognition.lang             = 'pt-BR'
    recognition.continuous       = false
    recognition.interimResults   = false
    recognitionRef.current       = recognition

    setStateSync(mode)

    recognition.addEventListener('result', (event: SpeechRecognitionEvent) => {
      const transcript = Array.from(event.results)
        .map(r => r[0].transcript.toLowerCase().trim())
        .join(' ')

      // Always check for stop word first
      if (STOP_WORDS.some(w => transcript.includes(w))) {
        setStateSync('off')
        stopRecognition()
        return
      }

      if (mode === 'standby') {
        // In standby, only react to wake word
        if (WAKE_WORDS.some(w => transcript.includes(w))) {
          // Extract query after wake word if spoken together
          let query = transcript
          for (const w of WAKE_WORDS) {
            query = query.replace(w, '').trim()
          }
          if (query.length > 2) {
            // Wake word + question in one sentence: "Olá NOC, como está o ambiente?"
            setStateSync('waiting')
            onQuery(query)
          } else {
            // Just the wake word — start listening for the question
            setStateSync('listening')
            startSession('listening')
          }
        }
        // else: ignore — not a wake word, keep standby
      } else if (mode === 'listening') {
        // In listening mode, any speech is a query
        const cleaned = transcript
          .replace(/(olá noc|ola noc|hey noc|ei noc)/gi, '')
          .replace(/(noc obrigado|tchau noc|pare noc)/gi, '')
          .trim()

        if (cleaned.length > 1) {
          setStateSync('waiting')
          onQuery(cleaned)
        } else {
          // Empty/command — restart listening
          startSession('listening')
        }
      }
    })

    recognition.addEventListener('end', () => {
      // If we're still active and not waiting for agent, restart
      if (stateRef.current === 'standby') {
        startSession('standby')
      } else if (stateRef.current === 'listening') {
        // Silence — restart listening
        startSession('listening')
      }
    })

    recognition.addEventListener('error', (e: SpeechRecognitionErrorEvent) => {
      if (stateRef.current === 'off') return
      if (e.error === 'no-speech' || e.error === 'aborted') {
        // Expected — restart session
        if (stateRef.current === 'standby') startSession('standby')
        else if (stateRef.current === 'listening') startSession('listening')
      } else {
        // Real error — go back to standby
        startSession('standby')
      }
    })

    recognition.start()
  }, [isSupported, stopRecognition, onQuery]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── When agent finishes speaking → restart listening ───────────────────────
  useEffect(() => {
    if (stateRef.current === 'off') return
    if (stateRef.current === 'waiting' && agentState === 'idle' && ttsState === 'idle') {
      // Agent done typing AND TTS done speaking → listen for next question
      clearListenTimer()
      listenTimerRef.current = setTimeout(() => {
        if (stateRef.current !== 'off') {
          startSession('listening')
        }
      }, LISTEN_DELAY)
    }
  }, [agentState, ttsState, clearListenTimer, startSession])

  // ── When TTS starts speaking, mark state as speaking ───────────────────────
  useEffect(() => {
    if (stateRef.current === 'off') return
    if (ttsState === 'speaking' && stateRef.current === 'waiting') {
      setStateSync('speaking')
    }
  }, [ttsState])

  // ── When TTS stops, go back to listening ───────────────────────────────────
  useEffect(() => {
    if (stateRef.current === 'off') return
    if (stateRef.current === 'speaking' && ttsState === 'idle' && agentState === 'idle') {
      clearListenTimer()
      listenTimerRef.current = setTimeout(() => {
        if (stateRef.current !== 'off') startSession('listening')
      }, LISTEN_DELAY)
    }
  }, [ttsState, agentState, clearListenTimer, startSession])

  // ── Public controls ────────────────────────────────────────────────────────
  const activate = useCallback(() => {
    if (!isSupported || disabled) return
    setStateSync('standby')
    startSession('standby')
  }, [isSupported, disabled, startSession])

  const deactivate = useCallback(() => {
    clearListenTimer()
    stopRecognition()
    setStateSync('off')
  }, [clearListenTimer, stopRecognition])

  // Cleanup on unmount
  useEffect(() => () => {
    clearListenTimer()
    stopRecognition()
  }, [clearListenTimer, stopRecognition])

  return { state, activate, deactivate, isSupported }
}
