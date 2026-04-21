/**
 * useWhisperInput — Gravação de áudio + transcrição via OpenAI Whisper
 *
 * Fluxo:
 * 1. start() → abre MediaRecorder com microfone
 * 2. Usuário fala
 * 3. stop() → envia áudio para /stt/transcribe → retorna texto
 *
 * Vantagens sobre Web Speech API:
 * - Muito mais preciso em pt-BR
 * - Resistente a ruído ambiente
 * - Reconhece termos técnicos (NOC, Zabbix, Datadog, etc.)
 * - Não depende de conexão contínua ao Google
 */
import { useCallback, useRef, useState } from 'react'

export type WhisperState = 'idle' | 'recording' | 'transcribing' | 'error'

const API_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

// Termos técnicos para ajudar o Whisper a reconhecer
const NOC_PROMPT = [
  'NOC, Zabbix, Datadog, Grafana, ThousandEyes, Anthropic, OpenRouter',
  'alerta, incidente, latência, disponibilidade, CPU, disco, memória',
  'P1, P2, P3, timeout, firewall, BGP, DNS, VPN, ping, traceroute',
  'ClienteA, ClienteB, servidor, host, interface, trigger, monitor',
].join(', ')

interface UseWhisperInputReturn {
  state:        WhisperState
  transcript:   string
  isSupported:  boolean
  isPremium:    boolean
  start:        () => Promise<void>
  stop:         () => Promise<void>
  reset:        () => void
}

export function useWhisperInput(
  onResult?: (text: string) => void
): UseWhisperInputReturn {
  const [state, setState]           = useState<WhisperState>('idle')
  const [transcript, setTranscript] = useState('')
  const [isPremium, setIsPremium]   = useState(false)

  const recorderRef   = useRef<MediaRecorder | null>(null)
  const chunksRef     = useRef<Blob[]>([])
  const streamRef     = useRef<MediaStream | null>(null)

  const isSupported = typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia

  // Check Whisper availability on first use
  const checkPremium = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/stt/status`)
      const d = await r.json()
      setIsPremium(d.available)
      return d.available as boolean
    } catch {
      setIsPremium(false)
      return false
    }
  }, [])

  const start = useCallback(async () => {
    if (state === 'recording') return
    chunksRef.current = []

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount:      1,
          sampleRate:        16000,   // Whisper prefers 16kHz
          echoCancellation:  true,
          noiseSuppression:  true,    // browser-level noise reduction
          autoGainControl:   true,
        }
      })
      streamRef.current = stream

      // Prefer webm/opus — best quality + compression for Whisper
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/ogg'

      const recorder = new MediaRecorder(stream, { mimeType })
      recorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.start(100)   // collect chunks every 100ms
      setState('recording')

    } catch (err) {
      console.error('[Whisper] microphone error:', err)
      setState('error')
    }
  }, [state])

  const stop = useCallback(async () => {
    if (state !== 'recording' || !recorderRef.current) return

    return new Promise<void>((resolve) => {
      const recorder = recorderRef.current!

      recorder.onstop = async () => {
        // Stop all tracks
        streamRef.current?.getTracks().forEach(t => t.stop())
        streamRef.current = null

        const audioBlob = new Blob(chunksRef.current, { type: recorder.mimeType })
        chunksRef.current = []

        if (audioBlob.size < 1000) {
          setState('idle')
          resolve()
          return
        }

        setState('transcribing')

        try {
          const premium = isPremium || await checkPremium()

          if (premium) {
            // ── Whisper transcription ──────────────────────────────────────
            const ext      = recorder.mimeType.includes('ogg') ? 'ogg' : 'webm'
            const formData = new FormData()
            formData.append('audio', audioBlob, `recording.${ext}`)
            formData.append('prompt', NOC_PROMPT)

            const resp = await fetch(`${API_URL}/stt/transcribe`, {
              method: 'POST',
              body:   formData,
            })

            if (resp.ok) {
              const data = await resp.json()
              const text = data.text?.trim() ?? ''
              console.log('[Whisper] transcribed:', `"${text}"`)
              if (text) {
                setTranscript(text)
                onResult?.(text)
              }
            } else {
              throw new Error(`HTTP ${resp.status}`)
            }
          } else {
            // ── Fallback: Web Speech API ───────────────────────────────────
            console.warn('[Whisper] not available, fallback to Web Speech API')
            setState('idle')
          }
        } catch (err) {
          console.error('[Whisper] transcription error:', err)
          setState('error')
          setTimeout(() => setState('idle'), 2000)
        } finally {
          setState('idle')
          resolve()
        }
      }

      recorder.stop()
    })
  }, [state, isPremium, checkPremium, onResult])

  const reset = useCallback(() => {
    setTranscript('')
    setState('idle')
  }, [])

  return { state, transcript, isSupported, isPremium, start, stop, reset }
}
