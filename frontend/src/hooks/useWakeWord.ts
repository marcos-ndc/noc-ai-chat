/**
 * useWakeWord — Modo hands-free estilo Alexa
 *
 * Uma única sessão continuous=true que fica aberta o tempo todo.
 * Analisa cada utterance e decide se é wake word, query ou stop word.
 *
 * Palavras de ativação:  "olá noc", "nokia", "hey noc" e variações pt-BR
 * Palavras de parada:    "noc obrigado", "tchau noc", "pare noc"
 */
import { useCallback, useEffect, useRef, useState } from 'react'

export type HandsFreeState =
  | 'off'       // desligado
  | 'standby'   // aguardando wake word
  | 'listening' // pronto para receber pergunta
  | 'waiting'   // aguardando resposta do agente
  | 'speaking'  // TTS reproduzindo

// Variações de como pt-BR transcreve "NOC"
const WAKE_WORDS = [
  'olá noc', 'ola noc', 'hey noc', 'ei noc', 'oi noc',
  'olá nokia', 'ola nokia', 'hey nokia', 'ei nokia',
  'olá nok',  'ola nok',
  'olá knock', 'ola knock',
  'olá nóc',  'ola nóc',
  'olá noque', 'ola noque',
]
const STOP_WORDS = [
  'noc obrigado', 'nokia obrigado',
  'tchau noc', 'tchau nokia',
  'pare noc',  'pare nokia',
  'obrigado noc', 'obrigado nokia',
]

interface Options {
  onQuery:    (text: string) => void
  agentState: 'idle' | 'typing'
  ttsState:   'idle' | 'speaking' | 'paused'
  disabled?:  boolean
}

export function useWakeWord({ onQuery, agentState, ttsState, disabled = false }: Options) {
  const [state, setState]     = useState<HandsFreeState>('off')
  const stateRef              = useRef<HandsFreeState>('off')
  const recRef                = useRef<SpeechRecognition | null>(null)
  const onQueryRef            = useRef(onQuery)
  const agentRef              = useRef(agentState)
  const ttsRef                = useRef(ttsState)
  const restartTimerRef       = useRef<ReturnType<typeof setTimeout> | null>(null)
  const activeRef             = useRef(false)   // true = hands-free is on

  useEffect(() => { onQueryRef.current = onQuery },    [onQuery])
  useEffect(() => { agentRef.current   = agentState }, [agentState])
  useEffect(() => { ttsRef.current     = ttsState },   [ttsState])

  const isSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const set = useCallback((s: HandsFreeState) => {
    stateRef.current = s
    setState(s)
  }, [])

  const clearTimer = useCallback(() => {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }
  }, [])

  // ── Start/restart continuous recognition ─────────────────────────────────
  const startRef = useRef<() => void>(() => {})

  startRef.current = () => {
    if (!isSupported || !activeRef.current) return

    // Don't start while TTS is speaking — Chrome will abort immediately
    if (ttsRef.current === 'speaking') {
      console.log('[WakeWord] TTS playing, will retry after it finishes')
      return
    }

    if (recRef.current) {
      try { recRef.current.abort() } catch { /* ignore */ }
      recRef.current = null
    }

    const SR  = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang           = 'pt-BR'
    rec.continuous     = true    // stay open across silences
    rec.interimResults = false   // final results only — fewer false positives
    recRef.current     = rec

    rec.addEventListener('result', (e: SpeechRecognitionEvent) => {
      // Process only the latest final result
      const last = e.results[e.results.length - 1]
      if (!last?.isFinal) return
      const raw = last[0].transcript.toLowerCase().trim()
      console.log('[WakeWord] heard:', raw, '| state:', stateRef.current)

      // Stop word — always wins
      if (STOP_WORDS.some(w => raw.includes(w))) {
        console.log('[WakeWord] stop word detected → off')
        activeRef.current = false
        if (recRef.current) { recRef.current.abort(); recRef.current = null }
        set('off')
        return
      }

      if (stateRef.current === 'standby') {
        const isWake = WAKE_WORDS.some(w => raw.includes(w))
        if (!isWake) return   // ignore non-wake words in standby

        // Strip wake word from query (in case both spoken together)
        let query = raw
        for (const w of [...WAKE_WORDS]) query = query.replace(w, '').trim()

        if (query.length > 2) {
          console.log('[WakeWord] wake + query:', query)
          set('waiting')
          onQueryRef.current(query)
        } else {
          console.log('[WakeWord] wake word → now listening')
          set('listening')
        }

      } else if (stateRef.current === 'listening') {
        // Any speech that's not a stop word is the question
        const cleaned = raw
          .replace(/(olá noc|ola noc|hey noc|oi noc|ei noc|olá nokia|ola nokia)/gi, '')
          .trim()
        if (cleaned.length > 1) {
          console.log('[WakeWord] query:', cleaned)
          set('waiting')
          onQueryRef.current(cleaned)
        }
      }
    })

    rec.addEventListener('error', (e: SpeechRecognitionErrorEvent) => {
      console.log('[WakeWord] error:', e.error, '| state:', stateRef.current)
      if (!activeRef.current) return
      if (e.error === 'not-allowed') { activeRef.current = false; set('off'); return }
      // aborted/network/no-speech → onend will restart
    })

    rec.addEventListener('end', () => {
      console.log('[WakeWord] session ended | active:', activeRef.current, '| state:', stateRef.current)
      if (!activeRef.current) return
      if (stateRef.current === 'waiting' || stateRef.current === 'speaking') return

      // Restart continuous session after short delay
      clearTimer()
      restartTimerRef.current = setTimeout(() => {
        if (activeRef.current) startRef.current()
      }, 500)
    })

    try {
      rec.start()
      console.log('[WakeWord] continuous session started, state:', stateRef.current)
    } catch (err) {
      console.warn('[WakeWord] failed to start:', err)
      restartTimerRef.current = setTimeout(() => {
        if (activeRef.current) startRef.current()
      }, 1000)
    }
  }

  // ── After agent responds + TTS finishes → go back to listening ───────────
  useEffect(() => {
    if (!activeRef.current) return
    if (stateRef.current !== 'waiting' && stateRef.current !== 'speaking') return

    if (ttsState === 'speaking') {
      set('speaking')
      return
    }

    if (agentState === 'idle' && ttsState === 'idle') {
      console.log('[WakeWord] agent done → back to listening')
      clearTimer()
      set('listening')
      // Restart recognition after TTS finishes (Chrome needs a moment)
      restartTimerRef.current = setTimeout(() => {
        if (activeRef.current) startRef.current()
      }, 1200)
    }
  }, [agentState, ttsState, set, clearTimer])

  // ── Public API ────────────────────────────────────────────────────────────
  const activate = useCallback(() => {
    if (!isSupported || disabled) return
    activeRef.current = true
    // Button click → go straight to listening (skip standby wake word requirement)
    set('listening')
    setTimeout(() => startRef.current(), 100)
  }, [isSupported, disabled, set])

  const deactivate = useCallback(() => {
    activeRef.current = false
    clearTimer()
    if (recRef.current) {
      try { recRef.current.abort() } catch { /* ignore */ }
      recRef.current = null
    }
    set('off')
  }, [clearTimer, set])

  useEffect(() => () => {
    activeRef.current = false
    clearTimer()
    if (recRef.current) { try { recRef.current.abort() } catch { /* ignore */ } }
  }, [clearTimer])

  return { state, activate, deactivate, isSupported }
}
