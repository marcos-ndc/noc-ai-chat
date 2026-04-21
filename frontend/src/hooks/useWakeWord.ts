/**
 * useWakeWord — Modo hands-free simplificado
 *
 * Fluxo único e claro:
 * 1. activate() → 'listening' → grava pergunta
 * 2. onQuery(text) → ChatPage envia ao agente → 'waiting'
 * 3. Agente responde (TTS) → 'speaking'
 * 4. TTS termina → volta para 'listening' → repete
 *
 * Standby (wake word) usa Web Speech API contínua.
 * Listening usa Whisper (se disponível) ou Web Speech.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useWhisperInput } from './useWhisperInput'

export type HandsFreeState = 'off' | 'standby' | 'listening' | 'waiting' | 'speaking'

const WAKE_WORDS = [
  'olá noc', 'ola noc', 'hey noc', 'ei noc', 'oi noc',
  'olá nokia', 'ola nokia', 'nokia', 'nok', 'olá nok',
]
const STOP_WORDS = [
  'noc obrigado', 'nokia obrigado', 'tchau noc', 'tchau nokia',
  'pare noc', 'pare nokia', 'obrigado noc', 'encerrar noc',
]
const isStopWord = (t: string) => STOP_WORDS.some(w => t.toLowerCase().includes(w))

interface Options {
  onQuery:    (text: string) => void
  agentState: 'idle' | 'typing'
  ttsState:   'idle' | 'speaking' | 'paused'
  disabled?:  boolean
}

export function useWakeWord({ onQuery, agentState, ttsState, disabled = false }: Options) {
  const [state, setState] = useState<HandsFreeState>('off')

  // All mutable state in refs to avoid stale closures
  const stateRef    = useRef<HandsFreeState>('off')
  const activeRef   = useRef(false)
  const recRef      = useRef<SpeechRecognition | null>(null)
  const timerRef    = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onQueryRef  = useRef(onQuery)
  const ttsRef      = useRef(ttsState)
  const agentRef    = useRef(agentState)

  useEffect(() => { onQueryRef.current = onQuery },    [onQuery])
  useEffect(() => { ttsRef.current     = ttsState },   [ttsState])
  useEffect(() => { agentRef.current   = agentState }, [agentState])

  const isSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  // Whisper for precise transcription
  const whisper = useWhisperInput((text) => {
    console.log('[WakeWord] Whisper result:', `"${text}"`)
    if (!activeRef.current) return
    if (isStopWord(text)) { doDeactivate(); return }
    if (stateRef.current !== 'listening') return
    const q = text.replace(/(olá|ola|hey|ei|oi)?\s*(noc|nokia|nok)\b/gi, '').trim()
    if (q.length > 1) {
      doSet('waiting')
      onQueryRef.current(q)
    } else {
      // Empty after stripping — was probably just the wake word, listen again
      scheduleResumeListening(200)
    }
  })

  // ── Helpers ───────────────────────────────────────────────────────────────

  const doSet = (s: HandsFreeState) => { stateRef.current = s; setState(s) }

  const clearTimer = () => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
  }

  const killRec = () => {
    if (recRef.current) {
      const r = recRef.current; recRef.current = null
      try { r.abort() } catch { /* ignore */ }
    }
  }

  const doDeactivate = () => {
    console.log('[WakeWord] deactivate')
    activeRef.current = false
    clearTimer()
    killRec()
    whisper.reset()
    doSet('off')
  }

  // ── Start listening for a question ────────────────────────────────────────

  const startListeningRef = useRef<() => void>(() => {})

  startListeningRef.current = () => {
    if (!activeRef.current) return
    if (ttsRef.current !== 'idle') {
      console.log('[WakeWord] TTS active, will resume when idle')
      return
    }
    console.log('[WakeWord] start listening, whisper:', whisper.isPremium)
    doSet('listening')

    if (whisper.isPremium) {
      // Whisper: records audio + auto-stops on silence
      whisper.start()
    } else {
      // Web Speech fallback
      startWebSpeechListening()
    }
  }

  const scheduleResumeListening = (delay = 600) => {
    clearTimer()
    timerRef.current = setTimeout(() => {
      if (activeRef.current) startListeningRef.current()
    }, delay)
  }

  // ── Web Speech API for listening (fallback) ───────────────────────────────

  const startWebSpeechListening = () => {
    killRec()
    const SR  = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang           = 'pt-BR'
    rec.continuous     = false
    rec.interimResults = false
    recRef.current     = rec

    rec.addEventListener('result', (e: SpeechRecognitionEvent) => {
      const last = e.results[e.results.length - 1]
      if (!last?.isFinal) return
      const raw = last[0].transcript.toLowerCase().trim()
      console.log('[WakeWord] WebSpeech heard:', `"${raw}"`)
      if (isStopWord(raw)) { doDeactivate(); return }
      if (stateRef.current !== 'listening') return
      const q = raw.replace(/(olá|ola|hey|ei|oi)?\s*(noc|nokia|nok)\b/gi, '').trim()
      if (q.length > 1) { doSet('waiting'); onQueryRef.current(q) }
    })
    rec.addEventListener('error', (e: SpeechRecognitionErrorEvent) => {
      if (e.error === 'not-allowed') { doDeactivate(); return }
    })
    rec.addEventListener('end', () => {
      if (!activeRef.current) return
      if (stateRef.current !== 'listening') return
      if (recRef.current !== rec) return
      recRef.current = null
      scheduleResumeListening(300)
    })
    try { rec.start() } catch { scheduleResumeListening(500) }
  }

  // ── Standby: Web Speech continuous for wake word ──────────────────────────

  const startStandbyRef = useRef<() => void>(() => {})

  startStandbyRef.current = () => {
    if (!activeRef.current) return
    killRec()
    const SR  = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang           = 'pt-BR'
    rec.continuous     = true
    rec.interimResults = false
    recRef.current     = rec

    rec.addEventListener('result', (e: SpeechRecognitionEvent) => {
      const last = e.results[e.results.length - 1]
      if (!last?.isFinal) return
      const raw = last[0].transcript.toLowerCase().trim()
      console.log('[WakeWord] standby heard:', `"${raw}"`)
      if (isStopWord(raw)) { doDeactivate(); return }
      const hit = WAKE_WORDS.some(w => raw.includes(w))
      if (!hit) return
      let q = raw
      for (const w of WAKE_WORDS) q = q.replace(w, '').trim()
      killRec()
      if (q.length > 2) { doSet('waiting'); onQueryRef.current(q) }
      else startListeningRef.current()
    })
    rec.addEventListener('error', (e: SpeechRecognitionErrorEvent) => {
      if (e.error === 'not-allowed') { doDeactivate(); return }
    })
    rec.addEventListener('end', () => {
      if (!activeRef.current || stateRef.current !== 'standby') return
      if (recRef.current !== rec) return
      recRef.current = null
      timerRef.current = setTimeout(() => {
        if (activeRef.current && stateRef.current === 'standby') startStandbyRef.current()
      }, 300)
    })
    try { rec.start(); doSet('standby') } catch { /* ignore */ }
  }

  // ── Resume after agent responds ───────────────────────────────────────────

  useEffect(() => {
    if (!activeRef.current) return
    const s = stateRef.current

    console.log('[WakeWord] check:', s, '| agent:', agentState, '| tts:', ttsState)

    // Mark speaking when TTS starts
    if (ttsState === 'speaking' && (s === 'waiting' || s === 'listening')) {
      doSet('speaking')
      killRec()  // stop mic while TTS plays
      whisper.reset()
      return
    }

    // Resume listening when both agent and TTS are done
    if (agentState === 'idle' && ttsState === 'idle') {
      if (s === 'waiting' || s === 'speaking') {
        console.log('[WakeWord] → resuming listening')
        scheduleResumeListening(800)
      }
    }
  }, [agentState, ttsState]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Public API ────────────────────────────────────────────────────────────

  const activate = useCallback(() => {
    if (!isSupported || disabled) return
    console.log('[WakeWord] activating')
    activeRef.current = true
    timerRef.current = setTimeout(() => startListeningRef.current(), 100)
  }, [isSupported, disabled])

  const deactivate = useCallback(() => doDeactivate(), []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => { activeRef.current = false; clearTimer(); killRec() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return { state, activate, deactivate, isSupported, isActive: activeRef }
}
