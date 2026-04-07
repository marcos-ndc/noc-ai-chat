import { useCallback, useRef, useState } from 'react'
import type { VoiceOutputState } from '../types'

interface UseVoiceOutputReturn {
  state: VoiceOutputState
  isSupported: boolean
  speak: (text: string) => void
  stop: () => void
  pause: () => void
  resume: () => void
}

export function useVoiceOutput(language = 'pt-BR'): UseVoiceOutputReturn {
  const [state, setState] = useState<VoiceOutputState>('idle')
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)

  const isSupported = typeof window !== 'undefined' && 'speechSynthesis' in window

  const speak = useCallback((text: string) => {
    if (!isSupported || !text.trim()) return

    window.speechSynthesis.cancel()

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = language
    utterance.rate = 1.0
    utterance.pitch = 1.0
    utteranceRef.current = utterance

    utterance.onstart = () => setState('speaking')
    utterance.onend = () => setState('idle')
    utterance.onerror = () => setState('idle')
    utterance.onpause = () => setState('paused')
    utterance.onresume = () => setState('speaking')

    window.speechSynthesis.speak(utterance)
  }, [isSupported, language])

  const stop = useCallback(() => {
    window.speechSynthesis.cancel()
    setState('idle')
  }, [])

  const pause = useCallback(() => {
    window.speechSynthesis.pause()
  }, [])

  const resume = useCallback(() => {
    window.speechSynthesis.resume()
  }, [])

  return { state, isSupported, speak, stop, pause, resume }
}
