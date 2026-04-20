/**
 * useVoiceOutput — TTS com dois modos:
 *
 * 1. PREMIUM (padrão quando disponível): OpenAI TTS via backend /tts/speak
 *    Voz "onyx" — grave, autoritativa, similar ao Jarvis (Homem de Ferro)
 *
 * 2. FALLBACK: Web Speech API nativa do browser
 *    Ativa automaticamente se OPENAI_API_KEY não configurada no servidor
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { VoiceOutputState } from '../types'

const API_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export interface TTSVoiceOption {
  label:   string
  desc:    string
  gender:  string
}

interface TTSStatus {
  available: boolean
  voice:     string
  model:     string
  speed:     number
  voices:    Record<string, TTSVoiceOption>
  models:    Record<string, string>
}

interface UseVoiceOutputReturn {
  state:        VoiceOutputState
  isSupported:  boolean
  isPremium:    boolean
  currentVoice: string
  ttsStatus:    TTSStatus | null
  speak:        (text: string) => void
  stop:         () => void
  pause:        () => void
  resume:       () => void
  setVoice:     (voice: string) => void
  setModel:     (model: string) => void
  setSpeed:     (speed: number) => void
}

export function useVoiceOutput(language = 'pt-BR'): UseVoiceOutputReturn {
  const [state, setState] = useState<VoiceOutputState>('idle')
  const [ttsStatus, setTtsStatus] = useState<TTSStatus | null>(null)
  // Persist voice settings in sessionStorage so admin panel changes apply to chat
  const [selectedVoice, setSelectedVoiceState] = useState<string>(
    () => sessionStorage.getItem('tts_voice') || 'onyx'
  )
  const [selectedModel, setSelectedModelState] = useState<string>(
    () => sessionStorage.getItem('tts_model') || 'tts-1-hd'
  )
  const [selectedSpeed, setSelectedSpeedState] = useState<number>(
    () => parseFloat(sessionStorage.getItem('tts_speed') || '0.92')
  )

  const setSelectedVoice = (v: string) => { setSelectedVoiceState(v); sessionStorage.setItem('tts_voice', v) }
  const setSelectedModel = (m: string) => { setSelectedModelState(m); sessionStorage.setItem('tts_model', m) }
  const setSelectedSpeed = (s: number) => { setSelectedSpeedState(s); sessionStorage.setItem('tts_speed', String(s)) }

  const utteranceRef  = useRef<SpeechSynthesisUtterance | null>(null)
  const audioRef      = useRef<HTMLAudioElement | null>(null)
  const abortRef      = useRef<AbortController | null>(null)

  const isBrowserTTSSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const isSupported = isBrowserTTSSupported || true // OpenAI TTS sempre disponível se configurado

  // ── Check OpenAI TTS availability on mount ────────────────────────────────
  useEffect(() => {
    fetch(`${API_URL}/tts/status`)
      .then(r => r.json())
      .then((data: TTSStatus) => {
        setTtsStatus(data)
        setSelectedVoice(data.voice)
        setSelectedModel(data.model)
        setSelectedSpeed(data.speed)
      })
      .catch(() => {/* silently fallback to browser TTS */})
  }, [])

  // ── Stop any active audio ─────────────────────────────────────────────────
  const stop = useCallback(() => {
    // Stop OpenAI audio
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ''
      audioRef.current = null
    }
    // Abort in-flight fetch
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    // Stop browser TTS
    if (isBrowserTTSSupported) {
      window.speechSynthesis.cancel()
    }
    setState('idle')
  }, [isBrowserTTSSupported])

  // ── OpenAI TTS (premium) ──────────────────────────────────────────────────
  const speakPremium = useCallback(async (text: string) => {
    stop()
    setState('speaking')

    abortRef.current = new AbortController()

    try {
      const resp = await fetch(`${API_URL}/tts/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice: selectedVoice, model: selectedModel, speed: selectedSpeed }),
        signal: abortRef.current.signal,
      })

      if (!resp.ok) {
        // Server returned error — fallback to browser TTS
        console.warn('OpenAI TTS failed, falling back to browser TTS')
        speakBrowser(text)
        return
      }

      const blob  = await resp.blob()
      const url   = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audioRef.current = audio

      audio.onended  = () => { setState('idle'); URL.revokeObjectURL(url) }
      audio.onerror  = () => { setState('idle'); URL.revokeObjectURL(url) }
      audio.onpause  = () => setState('paused')
      audio.onplay   = () => setState('speaking')

      await audio.play()

    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return // intentional stop
      console.warn('OpenAI TTS error:', err)
      speakBrowser(text) // fallback
    }
  }, [stop]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Browser TTS (fallback) ────────────────────────────────────────────────
  const speakBrowser = useCallback((text: string) => {
    if (!isBrowserTTSSupported || !text.trim()) return

    window.speechSynthesis.cancel()

    const utterance  = new SpeechSynthesisUtterance(text)
    utterance.lang   = language
    utterance.rate   = 0.95
    utterance.pitch  = 0.85   // ligeiramente mais grave
    utterance.volume = 1.0
    utteranceRef.current = utterance

    // Try to pick a deep, clear voice if available
    const voices = window.speechSynthesis.getVoices()
    const preferred = voices.find(v =>
      v.lang.startsWith('pt') && (
        v.name.toLowerCase().includes('male') ||
        v.name.toLowerCase().includes('daniel') ||
        v.name.toLowerCase().includes('reed') ||
        v.name.toLowerCase().includes('thomas')
      )
    ) ?? voices.find(v => v.lang.startsWith('pt'))

    if (preferred) utterance.voice = preferred

    utterance.onstart  = () => setState('speaking')
    utterance.onend    = () => setState('idle')
    utterance.onerror  = () => setState('idle')
    utterance.onpause  = () => setState('paused')
    utterance.onresume = () => setState('speaking')

    window.speechSynthesis.speak(utterance)
  }, [isBrowserTTSSupported, language])

  // ── Public speak() — picks premium or fallback ────────────────────────────
  const speak = useCallback((text: string) => {
    if (!text.trim()) return
    if (ttsStatus?.available) {
      speakPremium(text)
    } else {
      speakBrowser(text)
    }
  }, [ttsStatus?.available, speakPremium, speakBrowser])

  const pause = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
    } else if (isBrowserTTSSupported) {
      window.speechSynthesis.pause()
    }
  }, [isBrowserTTSSupported])

  const resume = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.play()
    } else if (isBrowserTTSSupported) {
      window.speechSynthesis.resume()
    }
  }, [isBrowserTTSSupported])

  return {
    state,
    isSupported,
    isPremium:    ttsStatus?.available ?? false,
    currentVoice: ttsStatus?.available ? selectedVoice : 'browser',
    ttsStatus,
    speak,
    stop,
    pause,
    resume,
    setVoice: setSelectedVoice,
    setModel: setSelectedModel,
    setSpeed: setSelectedSpeed,
  }
}
