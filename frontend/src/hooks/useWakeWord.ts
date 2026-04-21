/**
 * useWakeWord — Modo hands-free
 * 
 * Clica "Olá NOC" → ouve pergunta → agente responde em voz → ouve novamente.
 * Diz "NOC obrigado" para encerrar.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useWhisperInput } from './useWhisperInput'

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
  // variações que o pt-BR pode transcrever
  'nok obrigado', 'obrigado nok', 'tchau nok',
  'encerrar noc', 'encerrar nokia', 'finalizar noc',
]

const isStopWord = (text: string): boolean =>
  STOP_WORDS.some(w => text.toLowerCase().includes(w))

interface Options {
  onQuery:    (text: string) => void
  agentState: 'idle' | 'typing'
  ttsState:   'idle' | 'speaking' | 'paused'
  disabled?:  boolean
}

export function useWakeWord({ onQuery, agentState, ttsState, disabled = false }: Options) {
  // Whisper for precise transcription in listening mode
  const whisper = useWhisperInput((text) => {
    // Called when Whisper returns transcription
    clearTimer()
    console.log('[WakeWord] Whisper result:', `"${text}"`)
    if (!activeRef.current) return
    if (isStopWord(text)) {
      console.log('[WakeWord] Whisper → stop word')
      activeRef.current = false; stopRec(); set('off'); return
    }
    if (stateRef.current === 'listening' && text.length > 1) {
      const q = text.replace(/(olá|ola|hey|ei|oi)?\s*(noc|nokia|nok)/gi, '').trim()
      if (q.length > 1) {
        set('waiting')
        onQueryRef.current(q)
      }
    }
  })
  const [state, setState]   = useState<HandsFreeState>('off')
  const stateRef            = useRef<HandsFreeState>('off')
  const recRef              = useRef<SpeechRecognition | null>(null)
  const onQueryRef          = useRef(onQuery)
  const ttsRef              = useRef(ttsState)
  const activeRef           = useRef(false)
  const timerRef            = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryCountRef       = useRef(0)
  const silenceTimerRef     = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hasInterimRef       = useRef(false)   // tracks if we received any speech
  const transcriptRef        = useRef('')

  useEffect(() => { onQueryRef.current = onQuery }, [onQuery])
  useEffect(() => { ttsRef.current = ttsState },    [ttsState])

  const isSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const set = (s: HandsFreeState) => { stateRef.current = s; setState(s) }

  const clearTimer = () => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
  }

  const stopRec = () => {
    if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null }
    hasInterimRef.current = false
    transcriptRef.current = ''
    if (recRef.current) {
      const r = recRef.current
      recRef.current = null
      try { r.abort() } catch { /* ignore */ }
    }
  }

  // ── Whisper listening session ────────────────────────────────────────────
  // Called when we need to capture a question (not wake word detection)
  const whisperListenRef = useRef<() => void>(() => {})

  whisperListenRef.current = () => {
    if (!activeRef.current || !whisper.isSupported) return
    console.log('[WakeWord] Whisper listening started')
    // Silence detection is now built into useWhisperInput via Web Audio API
    // It auto-stops and calls onResult when user pauses for 1.5s
    whisper.start()
  }

  // ── Core recognition loop ─────────────────────────────────────────────────
  const startRec = useCallback(() => {
    if (!isSupported || !activeRef.current) return
    if (ttsRef.current === 'speaking') return

    stopRec()
    clearTimer()

    const SR   = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec  = new SR()
    const mode = stateRef.current  // capture mode at session start

    rec.lang = 'pt-BR'

    ;(rec as unknown as {maxAlternatives: number}).maxAlternatives = mode === 'standby' ? 3 : 1

    if (mode === 'standby') {
      // Standby: Web Speech API (continuous, low CPU, wake word detection)
      rec.continuous     = true
      rec.interimResults = false
    } else {
      // Listening: if Whisper available, use it instead of Web Speech API
      // Whisper is called separately via whisperListenRef.current()
      rec.continuous     = false
      rec.interimResults = true
    }

    recRef.current = rec

    // speechend fires when Chrome detects the user STOPPED speaking
    // Use it to immediately submit the last interim transcript
    rec.addEventListener('speechend', () => {
      if (mode !== 'listening') return
      // Clear existing silence timer — submit immediately
      if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null }
      const pending = transcriptRef.current.trim()
      if (pending.length > 2 && stateRef.current === 'listening' && activeRef.current) {
        console.log('[WakeWord] speechend → submit:', pending)
        // Short delay to allow final result to arrive first
        silenceTimerRef.current = setTimeout(() => {
          // Only submit if still in listening (no final result arrived)
          if (stateRef.current === 'listening' && transcriptRef.current.length > 2) {
            const text = transcriptRef.current
            transcriptRef.current = ''
            hasInterimRef.current = false
            // Check stop word BEFORE submitting
            if (isStopWord(text)) {
              console.log('[WakeWord] speechend → stop word detected')
              activeRef.current = false; stopRec(); set('off'); return
            }
            const q = text.replace(/(olá|ola|hey|ei|oi)?\s*(noc|nokia|nok)/gi, '').trim()
            if (q.length > 1) {
              set('waiting')
              onQueryRef.current(q)
              stopRec()
            }
          }
        }, 300)
      }
    })

    rec.addEventListener('result', (e: SpeechRecognitionEvent) => {
      const last = e.results[e.results.length - 1]

      // In listening mode: update transcript preview with interim results
      if (mode === 'listening' && !last?.isFinal) {
        const interim = last[0].transcript
        if (interim.length > 2) {
          transcriptRef.current = interim
          hasInterimRef.current = true
          // Reset silence timer — user is still speaking
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
          // If user pauses for 1.2s after speaking, force-submit interim as final
          silenceTimerRef.current = setTimeout(() => {
            const pending = transcriptRef.current.trim()
            if (pending.length > 2 && stateRef.current === 'listening' && activeRef.current) {
              console.log('[WakeWord] silence detected → auto-submit:', pending)
              // Check stop word BEFORE submitting
              if (isStopWord(pending)) {
                console.log('[WakeWord] silence timer → stop word detected')
                transcriptRef.current = ''
                hasInterimRef.current = false
                activeRef.current = false; stopRec(); set('off'); return
              }
              const q = pending.replace(/(olá|ola|hey|ei|oi)?\s*(noc|nokia|nok)/gi, '').trim()
              if (q.length > 1) {
                transcriptRef.current = ''
                hasInterimRef.current = false
                set('waiting')
                onQueryRef.current(q)
                stopRec()
              }
            }
          }, 1200)
        }
        return
      }

      if (!last?.isFinal) return

      // Clear silence detection timer — final result arrived
      if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null }
      hasInterimRef.current = false

      // Use best alternative or check all for wake word (standby mode)
      let raw = last[0].transcript.toLowerCase().trim()
      const confidence = last[0].confidence

      // In standby: check all alternatives for wake word
      if (mode === 'standby') {
        for (let a = 0; a < e.results[e.results.length - 1].length; a++) {
          const alt = e.results[e.results.length - 1][a].transcript.toLowerCase()
          if (WAKE_WORDS.some(w => alt.includes(w))) { raw = alt; break }
        }
      }

      // Reject low-confidence results in listening mode (likely noise)
      if (mode === 'listening' && confidence > 0 && confidence < 0.3) {
        console.log('[WakeWord] low confidence:', confidence, '— ignoring noise')
        return
      }

      console.log('[WakeWord] heard:', `"${raw}"`, '| mode:', mode, '| conf:', confidence?.toFixed(2))
      retryCountRef.current = 0

      if (isStopWord(raw)) {
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
        if (q.length > 1) {
          transcriptRef.current = ''
          set('waiting')
          onQueryRef.current(q)
          // continuous=false: session will end naturally after this result
        }
        // if q is empty (noise only): session ends → onend restarts listening
      }
    })

    rec.addEventListener('error', (e: SpeechRecognitionErrorEvent) => {
      console.log('[WakeWord] error:', e.error, '| active:', activeRef.current)
      if (!activeRef.current) return
      if (e.error === 'not-allowed') { activeRef.current = false; set('off'); return }
      if (e.error === 'aborted') return  // onend will handle restart
    })

    rec.addEventListener('end', () => {
      console.log('[WakeWord] ended | active:', activeRef.current, '| state:', stateRef.current, '| mode:', mode)
      if (!activeRef.current) return
      if (stateRef.current === 'waiting' || stateRef.current === 'speaking') return
      if (recRef.current !== null && recRef.current !== rec) return

      if (mode === 'listening') {
        // continuous=false: session ended after user stopped speaking
        // The result handler already processed the query — nothing to do here
        // UNLESS no result was received (silence / noise only) → restart listening
        if (stateRef.current === 'listening') {
          // Still in listening state means no result → user was silent → retry
          retryCountRef.current += 1
          const delay = Math.min(200 + (retryCountRef.current > 5 ? 600 : 0), 1200)
          timerRef.current = setTimeout(() => {
            if (activeRef.current && stateRef.current === 'listening') startRec()
          }, delay)
        }
        return
      }

      // Standby mode: always restart continuous session
      retryCountRef.current += 1
      const delay = Math.min(150 + (retryCountRef.current > 3 ? 400 : 0), 1000)
      timerRef.current = setTimeout(() => {
        if (activeRef.current) startRec()
      }, delay)
    })

    try {
      rec.start()
      console.log('[WakeWord] started | state:', stateRef.current)
    } catch (err) {
      console.warn('[WakeWord] start failed:', err)
      timerRef.current = setTimeout(() => { if (activeRef.current) startRec() }, 400)
    }
  }, [isSupported])   // stable - no changing deps

  // ── After agent + TTS finish → resume listening ───────────────────────────
  const ttsWasActiveRef = useRef(false)
  useEffect(() => {
    if (ttsState === 'speaking') ttsWasActiveRef.current = true
    if (ttsState === 'idle')     ttsWasActiveRef.current = false
  }, [ttsState])

  useEffect(() => {
    console.log('[WakeWord] state check:', stateRef.current, 'agent:', agentState, 'tts:', ttsState, 'active:', activeRef.current)
    if (!activeRef.current) return
    if (stateRef.current !== 'waiting' && stateRef.current !== 'speaking') return
    if (ttsState === 'speaking') { if (stateRef.current !== 'speaking') set('speaking'); return }
    if (agentState === 'idle' && ttsState === 'idle') {
      console.log('[WakeWord] → resume listening after response, whisper:', whisper.isPremium)
      set('listening')
      clearTimer()
      const delay = ttsWasActiveRef.current ? 600 : 150
      timerRef.current = setTimeout(() => {
        if (!activeRef.current) return
        if (whisper.isPremium) {
          whisperListenRef.current()
        } else {
          startRec()
        }
      }, delay)
    }
  }, [agentState, ttsState, startRec, whisper.isPremium])

  // ── Public API ────────────────────────────────────────────────────────────
  const activate = useCallback(() => {
    if (!isSupported || disabled) return
    console.log('[WakeWord] activating... whisper:', whisper.isPremium)
    retryCountRef.current = 0
    activeRef.current = true
    set('listening')
    timerRef.current = setTimeout(() => {
      if (whisper.isPremium) {
        whisperListenRef.current()
      } else {
        startRec()
      }
    }, 80)
  }, [isSupported, disabled, startRec, whisper.isPremium])

  const deactivate = useCallback(() => {
    console.log('[WakeWord] deactivating', new Error().stack?.split('\n').slice(1,4).join(' | '))
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

  return { state, activate, deactivate, isSupported, isActive: activeRef }
}
