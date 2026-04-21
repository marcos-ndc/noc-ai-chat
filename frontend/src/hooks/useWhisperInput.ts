/**
 * useWhisperInput — Gravação de áudio + transcrição via OpenAI Whisper
 *
 * Usa Web Audio API (AnalyserNode) para detectar silêncio automaticamente.
 * Quando o usuário para de falar por SILENCE_DURATION ms → para de gravar → transcreve.
 */
import { useCallback, useRef, useState } from 'react'

export type WhisperState = 'idle' | 'recording' | 'transcribing' | 'error'

const API_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

const NOC_PROMPT = [
  'NOC, Zabbix, Datadog, Grafana, ThousandEyes',
  'alerta, incidente, latência, disponibilidade, CPU, disco, memória',
  'P1, P2, P3, timeout, firewall, BGP, DNS, VPN, ping',
  'obrigado, encerrar, tchau, pare',
].join(', ')

const SILENCE_THRESHOLD = 8      // amplitude below this = silence (0–255 scale)
const SILENCE_DURATION  = 1500   // ms of silence before auto-stop
const MAX_DURATION      = 10000  // ms max recording time

interface UseWhisperInputReturn {
  state:       WhisperState
  isSupported: boolean
  isPremium:   boolean
  start:       () => Promise<void>
  stop:        () => Promise<void>
  reset:       () => void
}

export function useWhisperInput(
  onResult?: (text: string) => void
): UseWhisperInputReturn {
  const [state, setState]     = useState<WhisperState>('idle')
  const [isPremium, setIsPremium] = useState(false)
  const [checkedPremium, setCheckedPremium] = useState(false)

  const recorderRef       = useRef<MediaRecorder | null>(null)
  const chunksRef         = useRef<Blob[]>([])
  const streamRef         = useRef<MediaStream | null>(null)
  const audioCtxRef       = useRef<AudioContext | null>(null)
  const analyserRef       = useRef<AnalyserNode | null>(null)
  const silenceTimerRef   = useRef<ReturnType<typeof setTimeout> | null>(null)
  const maxTimerRef       = useRef<ReturnType<typeof setTimeout> | null>(null)
  const speechStartedRef  = useRef(false)
  const stoppedRef        = useRef(false)
  const rafRef            = useRef<number>(0)

  const isSupported = typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia

  // Check Whisper availability once
  const checkPremium = useCallback(async () => {
    if (checkedPremium) return isPremium
    try {
      const r = await fetch(`${API_URL}/stt/status`)
      const d = await r.json()
      setIsPremium(d.available)
      setCheckedPremium(true)
      return d.available as boolean
    } catch {
      setCheckedPremium(true)
      return false
    }
  }, [checkedPremium, isPremium])

  const clearTimers = () => {
    if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null }
    if (maxTimerRef.current)     { clearTimeout(maxTimerRef.current);     maxTimerRef.current = null }
    cancelAnimationFrame(rafRef.current)
  }

  const cleanup = () => {
    clearTimers()
    audioCtxRef.current?.close()
    audioCtxRef.current  = null
    analyserRef.current  = null
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
  }

  // ── Silence detection via Web Audio API ──────────────────────────────────
  const startSilenceDetection = (onSilence: () => void) => {
    const analyser = analyserRef.current
    if (!analyser) return

    const data = new Uint8Array(analyser.frequencyBinCount)
    let   lastSpeechTime = Date.now()

    const check = () => {
      if (stoppedRef.current) return
      analyser.getByteFrequencyData(data)
      const avg = data.reduce((a, b) => a + b, 0) / data.length
      const now = Date.now()

      if (avg > SILENCE_THRESHOLD) {
        lastSpeechTime = now
        speechStartedRef.current = true
      }

      // Only trigger silence if we've heard some speech first
      if (speechStartedRef.current && (now - lastSpeechTime) > SILENCE_DURATION) {
        console.log('[Whisper] silence detected → auto-stop')
        onSilence()
        return
      }

      rafRef.current = requestAnimationFrame(check)
    }

    rafRef.current = requestAnimationFrame(check)
  }

  // ── Transcribe audio blob ─────────────────────────────────────────────────
  const transcribe = useCallback(async (blob: Blob, mimeType: string) => {
    if (blob.size < 1000) {
      console.log('[Whisper] audio too short, skipping')
      setState('idle')
      return
    }

    setState('transcribing')
    try {
      const ext      = mimeType.includes('ogg') ? 'ogg' : 'webm'
      const formData = new FormData()
      formData.append('audio', blob, `recording.${ext}`)
      formData.append('prompt', NOC_PROMPT)

      const resp = await fetch(`${API_URL}/stt/transcribe`, {
        method: 'POST',
        body:   formData,
      })

      if (resp.ok) {
        const data = await resp.json()
        const text = data.text?.trim() ?? ''
        console.log('[Whisper] transcribed:', `"${text}"`)
        if (text) onResult?.(text)
      }
    } catch (err) {
      console.error('[Whisper] transcription error:', err)
    } finally {
      setState('idle')
    }
  }, [onResult])

  // ── start() ───────────────────────────────────────────────────────────────
  const start = useCallback(async () => {
    if (state === 'recording' || state === 'transcribing') return

    const premium = await checkPremium()
    if (!premium) return   // caller should use Web Speech API instead

    stoppedRef.current    = false
    speechStartedRef.current = false
    chunksRef.current     = []

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount:     1,
          sampleRate:       16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl:  true,
        }
      })
      streamRef.current = stream

      // Set up Web Audio analyser for silence detection
      const ctx      = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize              = 256
      analyser.smoothingTimeConstant = 0.6
      ctx.createMediaStreamSource(stream).connect(analyser)
      audioCtxRef.current  = ctx
      analyserRef.current  = analyser

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'

      const recorder = new MediaRecorder(stream, { mimeType })
      recorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mimeType })
        chunksRef.current = []
        cleanup()
        await transcribe(blob, mimeType)
      }

      recorder.start(100)
      setState('recording')

      // Start silence detection
      startSilenceDetection(() => {
        if (!stoppedRef.current) stopRecording()
      })

      // Max duration safety valve
      maxTimerRef.current = setTimeout(() => {
        if (!stoppedRef.current) {
          console.log('[Whisper] max duration reached')
          stopRecording()
        }
      }, MAX_DURATION)

    } catch (err) {
      console.error('[Whisper] mic error:', err)
      setState('error')
      setTimeout(() => setState('idle'), 2000)
    }
  }, [state, checkPremium, transcribe])

  // ── Internal stop (called by silence detection) ───────────────────────────
  const stopRecording = () => {
    if (stoppedRef.current) return
    stoppedRef.current = true
    clearTimers()
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop()
    }
  }

  // ── stop() — public, called by user or external code ─────────────────────
  const stop = useCallback(async () => {
    stopRecording()
  }, [])

  const reset = useCallback(() => {
    stopRecording()
    cleanup()
    setState('idle')
  }, [])

  return { state, isSupported, isPremium, start, stop, reset }
}
