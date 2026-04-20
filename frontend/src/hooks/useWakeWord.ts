/**
 * useWakeWord — Modo hands-free
 * 
 * Clica "Olá NOC" → ouve pergunta → agente responde em voz → ouve novamente.
 * Diz "NOC obrigado" para encerrar.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

export type HandsFreeState =
  | 'off'
  | 'standby'
  | 'listening'
  | 'waiting'
  | 'speaking'

const WAKE_WORDS = [
  'olá noc', 'ola noc', 'hey noc', 'ei noc', 'oi noc',
  'olá nokia', 'ola nokia', 'hey nokia',
  'olá nok', 'ola nok',
  'olá noque', 'ola noque',
]
const STOP_WORDS = [
  'noc obrigado', 'nokia obrigado', 'tchau noc', 'tchau nokia',
  'pare noc', 'pare nokia', 'obrigado noc',
]

interface Options {
  onQuery:    (text: string) => void
  agentState: 'idle' | 'typing'
  ttsState:   'idle' | 'speaking' | 'paused'
  disabled?:  boolean
}

export function useWakeWord({ onQuery, agentState, ttsState, disabled = false }: Options) {
  const [state, setState]   = useState<HandsFreeState>('off')
  const stateRef            = useRef<HandsFreeState>('off')
  const recRef              = useRef<SpeechRecognition | null>(null)
  const onQueryRef          = useRef(onQuery)
  const ttsRef              = useRef(ttsState)
  const activeRef           = useRef(false)
  const timerRef            = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryCountRef       = useRef(0)

  useEffect(() => { onQueryRef.current = onQuery }, [onQuery])
  useEffect(() => { ttsRef.current = ttsState },    [ttsState])

  const isSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const set = (s: HandsFreeState) => { stateRef.current = s; setState(s) }

  const clearTimer = () => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
  }

  const stopRec = () => {
    if (recRef.current) {
      const r = recRef.current
      recRef.current = null
      try { r.abort() } catch { /* ignore */ }
    }
  }

  // ── Core recognition loop ─────────────────────────────────────────────────
  const startRec = useCallback(() => {
    if (!isSupported || !activeRef.current) return
    if (ttsRef.current === 'speaking') return   // don't start while TTS is playing

    stopRec()
    clearTimer()

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
      console.log('[WakeWord] heard:', `"${raw}"`, '| mode:', stateRef.current)
      retryCountRef.current = 0  // reset on successful result

      if (STOP_WORDS.some(w => raw.includes(w))) {
        console.log('[WakeWord] → stop')
        activeRef.current = false
        stopRec()
        set('off')
        return
      }

      if (stateRef.current === 'standby') {
        if (!WAKE_WORDS.some(w => raw.includes(w))) return
        let q = raw
        for (const w of WAKE_WORDS) q = q.replace(w, '').trim()
        if (q.length > 2) { set('waiting'); onQueryRef.current(q) }
        else { console.log('[WakeWord] → listening'); set('listening') }

      } else if (stateRef.current === 'listening') {
        const q = raw.replace(/(olá|ola|hey|ei|oi)?\s*(noc|nokia|nok)/gi, '').trim()
        if (q.length > 1) { set('waiting'); onQueryRef.current(q) }
      }
    })

    rec.addEventListener('error', (e: SpeechRecognitionErrorEvent) => {
      console.log('[WakeWord] error:', e.error, '| active:', activeRef.current)
      if (!activeRef.current) return
      if (e.error === 'not-allowed') { activeRef.current = false; set('off'); return }
      if (e.error === 'aborted') return  // onend will handle restart
    })

    rec.addEventListener('end', () => {
      console.log('[WakeWord] ended | active:', activeRef.current, '| state:', stateRef.current)
      if (!activeRef.current) return
      if (stateRef.current === 'waiting' || stateRef.current === 'speaking') return
      if (recRef.current !== null) return  // new session already started

      retryCountRef.current += 1
      // Backoff: 300ms normally, longer after repeated failures
      const delay = Math.min(300 + (retryCountRef.current > 3 ? 500 : 0), 1500)
      timerRef.current = setTimeout(() => {
        if (activeRef.current) startRec()
      }, delay)
    })

    try {
      rec.start()
      console.log('[WakeWord] started | state:', stateRef.current)
    } catch (err) {
      console.warn('[WakeWord] start failed:', err)
      timerRef.current = setTimeout(() => { if (activeRef.current) startRec() }, 800)
    }
  }, [isSupported])   // stable - no changing deps

  // ── After agent + TTS finish → resume listening ───────────────────────────
  useEffect(() => {
    if (!activeRef.current) return
    if (stateRef.current !== 'waiting' && stateRef.current !== 'speaking') return
    if (ttsState === 'speaking') { if (stateRef.current !== 'speaking') set('speaking'); return }
    if (agentState === 'idle' && ttsState === 'idle') {
      console.log('[WakeWord] → resume listening after response')
      set('listening')
      clearTimer()
      timerRef.current = setTimeout(startRec, 1200)
    }
  }, [agentState, ttsState, startRec])

  // ── Public API ────────────────────────────────────────────────────────────
  const activate = useCallback(() => {
    if (!isSupported || disabled) return
    console.log('[WakeWord] activating...')
    retryCountRef.current = 0
    activeRef.current = true
    set('listening')
    // Small delay ensures browser has processed the click event
    timerRef.current = setTimeout(startRec, 200)
  }, [isSupported, disabled, startRec])

  const deactivate = useCallback(() => {
    console.log('[WakeWord] deactivating')
    activeRef.current = false
    clearTimer()
    stopRec()
    set('off')
  }, [])

  useEffect(() => () => {
    activeRef.current = false
    clearTimer()
    stopRec()
  }, [])

  return { state, activate, deactivate, isSupported }
}
