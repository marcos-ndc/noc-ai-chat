import { useCallback, useRef, useState } from 'react'
import type { VoiceInputState } from '../types'

interface UseVoiceInputOptions {
  onResult?: (transcript: string) => void
  language?: string
  continuous?: boolean
}

interface UseVoiceInputReturn {
  state: VoiceInputState
  transcript: string
  isSupported: boolean
  start: () => void
  stop: () => void
  reset: () => void
}

export function useVoiceInput(options: UseVoiceInputOptions = {}): UseVoiceInputReturn {
  const { onResult, language = 'pt-BR', continuous = false } = options

  const [state, setState] = useState<VoiceInputState>('idle')
  const [transcript, setTranscript] = useState('')
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const transcriptRef = useRef('')

  const isSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const start = useCallback(() => {
    if (!isSupported) { setState('error'); return }

    const SR = (window.SpeechRecognition || window.webkitSpeechRecognition)
    const recognition = new SR()
    recognition.lang = language
    recognition.continuous = continuous
    recognition.interimResults = true
    recognitionRef.current = recognition

    recognition.addEventListener('result', (event: SpeechRecognitionEvent) => {
      const current = Array.from(event.results)
        .map((r: SpeechRecognitionResult) => r[0].transcript)
        .join('')
      transcriptRef.current = current
      setTranscript(current)
    })

    recognition.addEventListener('error', (_event: SpeechRecognitionErrorEvent) => {
      setState('error')
    })

    recognition.addEventListener('end', () => {
      setState('idle')
      // Also fire onResult on natural end (not just manual stop)
      if (transcriptRef.current) onResult?.(transcriptRef.current)
    })

    recognition.start()
    setState('listening')
  }, [isSupported, language, continuous])

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
    setState('idle')
    if (transcriptRef.current) onResult?.(transcriptRef.current)
  }, [onResult])

  const reset = useCallback(() => {
    recognitionRef.current?.abort()
    recognitionRef.current = null
    transcriptRef.current = ''
    setTranscript('')
    setState('idle')
  }, [])

  return { state, transcript, isSupported, start, stop, reset }
}
