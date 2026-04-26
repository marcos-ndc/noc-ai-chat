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
import { useAuthStore } from './useAuth'
import type { VoiceOutputState } from '../types'

// ── Per-specialist voice helpers ─────────────────────────────────────────────

export interface VoiceSettings {
  provider: string
  voice:    string
  model:    string
  speed:    number
}

export function saveSpecialistVoice(specialist: string, settings: VoiceSettings) {
  const map = JSON.parse(localStorage.getItem('tts_specialist_voices') ?? '{}')
  map[specialist] = settings
  localStorage.setItem('tts_specialist_voices', JSON.stringify(map))
}

export function getSpecialistVoice(specialist: string): VoiceSettings | null {
  const map = JSON.parse(localStorage.getItem('tts_specialist_voices') ?? '{}')
  return map[specialist] ?? null
}

const API_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export interface TTSVoiceOption {
  label:   string
  desc:    string
  gender:  string
}

interface ELVoice {
  name:   string
  desc:   string
  gender: string
  accent: string
  preset?: boolean
}

interface ProviderStatus {
  available:      boolean
  default_voice?:    string
  default_voice_id?: string
  default_model:  string
  voices:         Record<string, TTSVoiceOption | ELVoice>
  models:         Record<string, string>
  error?:         string
}

interface TTSStatus {
  openai:           ProviderStatus
  elevenlabs:       ProviderStatus
  available:        boolean
  default_provider: string
}

interface UseVoiceOutputReturn {
  state:        VoiceOutputState
  isSupported:  boolean
  isPremium:    boolean
  currentVoice: string
  ttsStatus:    TTSStatus | null
  speak:        (text: string, specialist?: string) => void
  stop:         () => void
  pause:        () => void
  resume:       () => void
  setVoice:     (voice: string) => void
  setModel:     (model: string) => void
  setSpeed:     (speed: number) => void
  setProvider:  (provider: string) => void
  provider:     string
}

export function useVoiceOutput(language = 'pt-BR'): UseVoiceOutputReturn {
  const token = useAuthStore(s => s.token)
  const [state, setState] = useState<VoiceOutputState>('idle')
  const [ttsStatus, setTtsStatus] = useState<TTSStatus | null>(null)
  // Persist voice settings in localStorage so admin panel changes apply across sessions
  const [selectedProvider, setSelectedProvider] = useState<string>(
    () => localStorage.getItem('tts_provider') || 'openai'
  )
  const [selectedVoice, setSelectedVoiceState] = useState<string>(
    () => localStorage.getItem('tts_voice') || 'onyx'
  )
  const [selectedModel, setSelectedModelState] = useState<string>(
    () => localStorage.getItem('tts_model') || 'tts-1-hd'
  )
  const [selectedSpeed, setSelectedSpeedState] = useState<number>(
    () => parseFloat(localStorage.getItem('tts_speed') || '0.92')
  )

  const setSelectedVoice = (v: string) => { setSelectedVoiceState(v); localStorage.setItem('tts_voice', v) }
  const setSelectedModel = (m: string) => { setSelectedModelState(m); localStorage.setItem('tts_model', m) }
  const setSelectedSpeed = (s: number) => { setSelectedSpeedState(s); localStorage.setItem('tts_speed', String(s)) }

  const utteranceRef  = useRef<SpeechSynthesisUtterance | null>(null)
  const audioRef      = useRef<HTMLAudioElement | null>(null)
  const abortRef      = useRef<AbortController | null>(null)

  const isBrowserTTSSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const isSupported = isBrowserTTSSupported || true // OpenAI TTS sempre disponível se configurado

  // ── Check OpenAI TTS availability on mount ────────────────────────────────
  useEffect(() => {
    const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}
    fetch(`${API_URL}/tts/voices`, { headers: authHeaders })
      .then(r => r.json())
      .then((rawData: any) => {
        // Ensure root-level available is computed from providers
        const data: TTSStatus = {
          ...rawData,
          available: rawData.available ?? (rawData.openai?.available || rawData.elevenlabs?.available) ?? false,
          default_provider: rawData.default_provider || (rawData.elevenlabs?.available ? 'elevenlabs' : 'openai'),
        }
        setTtsStatus(data)
        // Only apply server defaults when the user has no saved preferences
        if (!localStorage.getItem('tts_provider')) {
          const defaultProv = data.default_provider
          setSelectedProvider(defaultProv)
          localStorage.setItem('tts_provider', defaultProv)

          if (defaultProv === 'elevenlabs' && data.elevenlabs?.available) {
            const voiceId = data.elevenlabs.default_voice_id
              || Object.keys(data.elevenlabs.voices ?? {})[0]
              || ''
            setSelectedVoice(voiceId)
            setSelectedModel(data.elevenlabs.default_model || 'eleven_flash_v2_5')
          } else if (data.openai?.available) {
            setSelectedVoice(data.openai.default_voice || 'onyx')
            setSelectedModel(data.openai.default_model || 'tts-1-hd')
          }
        }
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
  const speakPremium = useCallback(async (text: string, settings?: VoiceSettings) => {
    stop()
    setState('speaking')

    abortRef.current = new AbortController()

    const provider = settings?.provider ?? selectedProvider
    const voice    = settings?.voice    ?? selectedVoice
    const model    = settings?.model    ?? selectedModel
    const speed    = settings?.speed    ?? selectedSpeed

    try {
      const resp = await fetch(`${API_URL}/tts/speak`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text, provider, voice, model, speed }),
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
  const speak = useCallback((text: string, specialist?: string) => {
    if (!text.trim()) return
    const voicesMap: Record<string, VoiceSettings> = JSON.parse(localStorage.getItem('tts_specialist_voices') ?? '{}')
    const settings: VoiceSettings | undefined = specialist && voicesMap[specialist]
      ? voicesMap[specialist]
      : undefined
    if (ttsStatus?.available) {
      speakPremium(text, settings)
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
    isPremium:    (ttsStatus?.available ?? false),
    provider:     selectedProvider,
    currentVoice: ttsStatus?.available ? selectedVoice : 'browser',
    ttsStatus,
    speak,
    stop,
    pause,
    resume,
    setVoice:    setSelectedVoice,
    setModel:    setSelectedModel,
    setSpeed:    setSelectedSpeed,
    setProvider: (p: string) => { setSelectedProvider(p); localStorage.setItem('tts_provider', p) },
  }
}
