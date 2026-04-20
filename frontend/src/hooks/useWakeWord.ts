/**
 * useWakeWord — Modo hands-free estilo Alexa
 *
 * Clica em "Olá NOC" para entrar em standby.
 * Diz "Olá NOC" → ouve a pergunta → envia → aguarda resposta → ouve de novo.
 * Diz "NOC obrigado" (ou "tchau NOC", "pare NOC") para encerrar.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

export type HandsFreeState =
  | 'off'       // desligado
  | 'standby'   // ouvindo em background por wake word
  | 'listening' // gravando pergunta
  | 'waiting'   // aguardando resposta do agente
  | 'speaking'  // TTS reproduzindo — logo vai ouvir de novo

const WAKE_WORDS = [
  // Pronúncias corretas
  'olá noc', 'ola noc', 'hey noc', 'ei noc', 'oi noc',
  // Como o pt-BR reconhece "NOC" falado
  'olá nokia', 'ola nokia', 'hey nokia',
  'olá knock', 'ola knock',
  'olá nok', 'ola nok', 'hey nok',
  'olá nóc', 'ola nóc',
  'olá noque', 'ola noque',
  'olá norte', 'ola norte',  // às vezes reconhece "noc" como "norte"
  // Só "noc" em qualquer posição (captura "ei, noc!", "noc!" etc)
  ' noc ', 'nokia', 'nok ',
]
const STOP_WORDS = [
  'noc obrigado', 'tchau noc', 'pare noc', 'noc tchau', 'desligar',
  'nokia obrigado', 'tchau nokia', 'pare nokia',
  'nok obrigado', 'tchau nok',
]

interface Options {
  onQuery:    (text: string) => void
  agentState: 'idle' | 'typing'
  ttsState:   'idle' | 'speaking' | 'paused'
  disabled?:  boolean
}

export function useWakeWord({ onQuery, agentState, ttsState, disabled = false }: Options) {
  const [state, setState] = useState<HandsFreeState>('off')

  // All mutable state lives in refs so event listeners always see current values
  const stateRef      = useRef<HandsFreeState>('off')
  const recRef        = useRef<SpeechRecognition | null>(null)
  const onQueryRef    = useRef(onQuery)
  const timerRef      = useRef<ReturnType<typeof setTimeout> | null>(null)
  const agentRef      = useRef(agentState)
  const ttsRef        = useRef(ttsState)

  useEffect(() => { onQueryRef.current = onQuery },    [onQuery])
  useEffect(() => { agentRef.current   = agentState }, [agentState])
  useEffect(() => { ttsRef.current     = ttsState },   [ttsState])

  const isSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const set = useCallback((s: HandsFreeState) => {
    stateRef.current = s
    setState(s)
  }, [])

  const killRec = useCallback(() => {
    if (recRef.current) {
      const rec = recRef.current
      recRef.current = null          // null FIRST so onend/onerror don't restart
      try { rec.abort() } catch { /* ignore */ }
    }
  }, [])

  const killTimer = useCallback(() => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
  }, [])

  // ── Core: start one recognition session ─────────────────────────────────
  // Uses a ref so recursive restarts always call the latest version
  const startRef = useRef<(mode: 'standby' | 'listening') => void>(() => {})

  startRef.current = (mode: 'standby' | 'listening') => {
    if (!isSupported) return
    if (stateRef.current === 'off') return   // deactivated — stop recursion

    killRec()

    const SR  = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang           = 'pt-BR'
    rec.continuous     = false       // one utterance at a time — more reliable
    rec.interimResults = false       // final results only
    recRef.current     = rec

    stateRef.current = mode
    setState(mode)

    rec.addEventListener("result", (e: SpeechRecognitionEvent) => {
      const raw = Array.from(e.results)
        .map(r => r[0].transcript.toLowerCase().trim())
        .join(' ')

      console.log('[WakeWord] heard:', raw, '| mode:', mode)

      // Stop word always wins
      if (STOP_WORDS.some(w => raw.includes(w))) {
        killRec()
        set('off')
        return
      }

      if (mode === 'standby') {
        const hit = WAKE_WORDS.some(w => raw.includes(w))
        if (!hit) {
          // Not a wake word — restart standby
          setTimeout(() => startRef.current('standby'), 100)
          return
        }

        // Strip wake word to get optional inline question
        let query = raw
        for (const w of WAKE_WORDS) query = query.replace(w, '').trim()

        if (query.length > 2) {
          set('waiting')
          onQueryRef.current(query)
        } else {
          // Just the wake word — now listen for the question
          setTimeout(() => startRef.current('listening'), 200)
        }
      } else {
        // listening mode — any speech is the question
        const cleaned = raw
          .replace(/(olá noc|ola noc|hey noc|oi noc|ei noc)/gi, '')
          .trim()

        if (cleaned.length > 1) {
          set('waiting')
          onQueryRef.current(cleaned)
        } else {
          setTimeout(() => startRef.current('listening'), 100)
        }
      }
    })

    rec.addEventListener("error", (e: SpeechRecognitionErrorEvent) => {
      console.log('[WakeWord] error:', e.error)
      if (stateRef.current === 'off') return
      // no-speech and aborted are normal — just restart
      setTimeout(() => {
        if (stateRef.current !== 'off' && stateRef.current !== 'waiting') {
          startRef.current(stateRef.current as 'standby' | 'listening')
        }
      }, 300)
    })

    rec.addEventListener("end", () => {
      console.log('[WakeWord] session ended, state:', stateRef.current)
      if (stateRef.current === 'off' || stateRef.current === 'waiting') return
      if (stateRef.current === 'standby' || stateRef.current === 'listening') {
        setTimeout(() => {
          if (stateRef.current !== 'off' && stateRef.current !== 'waiting') {
            startRef.current(stateRef.current as 'standby' | 'listening')
          }
        }, 150)
      }
    })

    try {
      rec.start()
      console.log('[WakeWord] session started, mode:', mode)
    } catch (err) {
      console.warn('[WakeWord] failed to start:', err)
    }
  }

  // ── After agent + TTS finish → restart listening ─────────────────────────
  useEffect(() => {
    if (stateRef.current !== 'waiting' && stateRef.current !== 'speaking') return
    if (agentState !== 'idle') return
    if (ttsState !== 'idle') {
      // TTS started — mark as speaking
      if (ttsState === 'speaking') set('speaking')
      return
    }
    // Both done → listen again after short delay
    killTimer()
    timerRef.current = setTimeout(() => {
      if (stateRef.current !== 'off') startRef.current('listening')
    }, 900)
  }, [agentState, ttsState, set, killTimer])

  // ── Public API ────────────────────────────────────────────────────────────
  const activate = useCallback(() => {
    if (!isSupported || disabled) return
    set('standby')
    setTimeout(() => startRef.current('standby'), 50)
  }, [isSupported, disabled, set])

  const deactivate = useCallback(() => {
    killTimer()
    killRec()
    set('off')
  }, [killTimer, killRec, set])

  useEffect(() => () => { killTimer(); killRec() }, [killTimer, killRec])

  return { state, activate, deactivate, isSupported }
}
