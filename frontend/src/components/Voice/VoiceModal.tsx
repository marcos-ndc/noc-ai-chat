/**
 * VoiceModal — Modal de voz com ondas sonoras em tempo real
 *
 * Usa Web Audio API para capturar amplitude do microfone e animar
 * múltiplos anéis SVG que pulsam conforme as ondas sonoras.
 * Estética: orb de IA azul/roxo com glow, similar à imagem de referência.
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import type { HandsFreeState } from '../../hooks/useWakeWord'

interface VoiceModalProps {
  state:      HandsFreeState
  onClose:    () => void
  transcript?: string   // texto parcial sendo ouvido
}

// Quantidade de anéis orbitais
const RING_COUNT = 6

export function VoiceModal({ state, onClose, transcript }: VoiceModalProps) {
  const canvasRef       = useRef<HTMLCanvasElement>(null)
  const analyserRef     = useRef<AnalyserNode | null>(null)
  const audioCtxRef     = useRef<AudioContext | null>(null)
  const streamRef       = useRef<MediaStream | null>(null)
  const rafRef          = useRef<number>(0)
  const [amplitude, setAmplitude] = useState(0)
  const amplitudeRef    = useRef(0)

  const isListening = state === 'listening'
  const isWaiting   = state === 'waiting'
  const isSpeaking  = state === 'speaking'
  const isActive    = state !== 'off'

  // ── Connect microphone to analyser ────────────────────────────────────────
  const connectMic = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const ctx      = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.8

      const source = ctx.createMediaStreamSource(stream)
      source.connect(analyser)

      audioCtxRef.current  = ctx
      analyserRef.current  = analyser
    } catch {
      // mic permission denied — still show modal with synthetic animation
    }
  }, [])

  const disconnectMic = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    audioCtxRef.current?.close()
    audioCtxRef.current  = null
    analyserRef.current  = null
  }, [])

  useEffect(() => {
    if (isListening) {
      connectMic()
    } else {
      disconnectMic()
    }
    return disconnectMic
  }, [isListening, connectMic, disconnectMic])

  // ── Canvas animation loop ─────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !isActive) return
    const ctx = canvas.getContext('2d')!

    let tick = 0

    const draw = () => {
      rafRef.current = requestAnimationFrame(draw)
      tick++

      const W = canvas.width
      const H = canvas.height
      const cx = W / 2
      const cy = H / 2

      ctx.clearRect(0, 0, W, H)

      // Read mic amplitude
      let amp = 0
      if (analyserRef.current) {
        const data = new Uint8Array(analyserRef.current.frequencyBinCount)
        analyserRef.current.getByteFrequencyData(data)
        const avg = data.reduce((a, b) => a + b, 0) / data.length
        amp = avg / 128   // 0..2 range
      } else if (isWaiting || isSpeaking) {
        // Synthetic breathing animation when no mic
        amp = 0.3 + Math.sin(tick * 0.04) * 0.25
      }

      // Smooth amplitude
      amplitudeRef.current = amplitudeRef.current * 0.85 + amp * 0.15
      const a = amplitudeRef.current
      setAmplitude(a)

      // Background deep glow
      const bgGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, W * 0.6)
      bgGrad.addColorStop(0, `rgba(30, 20, 80, ${0.4 + a * 0.3})`)
      bgGrad.addColorStop(0.5, 'rgba(10, 5, 40, 0.2)')
      bgGrad.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = bgGrad
      ctx.fillRect(0, 0, W, H)

      // Draw orbital rings
      for (let i = 0; i < RING_COUNT; i++) {
        const t = tick * 0.008 + (i * Math.PI * 2) / RING_COUNT
        const phase = (i / RING_COUNT) * Math.PI * 2

        // Base radius + amplitude perturbation per ring
        const baseR  = W * (0.12 + i * 0.055)
        const waver  = a * W * (0.04 + i * 0.015)
        const rotate = t * (i % 2 === 0 ? 1 : -1) * (0.3 + i * 0.1)

        // Ring path with sinusoidal distortion
        ctx.beginPath()
        const pts = 120
        for (let p = 0; p <= pts; p++) {
          const angle   = (p / pts) * Math.PI * 2
          const distort = Math.sin(angle * (3 + i) + t * 2 + phase) * waver
                        + Math.sin(angle * (2 + i) - t * 1.5) * waver * 0.5
          const r       = baseR + distort

          const rx = cx + Math.cos(angle + rotate) * r
          const ry = cy + Math.sin(angle + rotate) * r * 0.85   // slight ellipse

          p === 0 ? ctx.moveTo(rx, ry) : ctx.lineTo(rx, ry)
        }
        ctx.closePath()

        // Color: deep blue → violet → cyan gradient per ring
        const hue     = 220 + i * 20 + a * 30
        const bright  = 0.15 + (RING_COUNT - i) / RING_COUNT * 0.35 + a * 0.2
        const alpha   = (0.4 + a * 0.4) * (1 - i * 0.1)

        ctx.strokeStyle = `hsla(${hue}, 85%, ${bright * 100}%, ${alpha})`
        ctx.lineWidth   = 1.5 - i * 0.15
        ctx.shadowBlur  = 8 + a * 20
        ctx.shadowColor = `hsla(${hue}, 90%, 70%, 0.6)`
        ctx.stroke()
        ctx.shadowBlur  = 0
      }

      // Inner orb glow
      const orbR    = W * 0.18 + a * W * 0.04
      const orbGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, orbR)
      orbGrad.addColorStop(0, `rgba(140, 120, 255, ${0.6 + a * 0.3})`)
      orbGrad.addColorStop(0.4, `rgba(80, 60, 200, ${0.3 + a * 0.2})`)
      orbGrad.addColorStop(1, 'rgba(40, 20, 120, 0)')
      ctx.fillStyle = orbGrad
      ctx.beginPath()
      ctx.arc(cx, cy, orbR, 0, Math.PI * 2)
      ctx.fill()

      // Outer halo
      const haloGrad = ctx.createRadialGradient(cx, cy, orbR * 0.8, cx, cy, orbR * 2.5)
      haloGrad.addColorStop(0, `rgba(100, 80, 255, ${0.08 + a * 0.12})`)
      haloGrad.addColorStop(1, 'rgba(60, 40, 180, 0)')
      ctx.fillStyle = haloGrad
      ctx.beginPath()
      ctx.arc(cx, cy, orbR * 2.5, 0, Math.PI * 2)
      ctx.fill()
    }

    draw()
    return () => { cancelAnimationFrame(rafRef.current) }
  }, [isActive, isWaiting, isSpeaking])

  if (!isActive) return null

  const stateLabel = {
    standby:   'Aguardando...',
    listening: 'Ouvindo',
    waiting:   'Processando...',
    speaking:  'Respondendo...',
    off:       '',
  }[state]

  const stateColor = {
    standby:   'text-blue-300',
    listening: 'text-cyan-300',
    waiting:   'text-violet-300',
    speaking:  'text-indigo-300',
    off:       '',
  }[state]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(2, 1, 20, 0.85)', backdropFilter: 'blur(12px)' }}
      onClick={onClose}
    >
      <div
        className="relative flex flex-col items-center gap-6"
        onClick={e => e.stopPropagation()}
      >
        {/* Canvas orb */}
        <div className="relative">
          <canvas
            ref={canvasRef}
            width={320}
            height={320}
            className="rounded-full"
            style={{ filter: 'contrast(1.1) saturate(1.3)' }}
          />

          {/* Center AI label */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <span
              className="font-bold tracking-widest select-none"
              style={{
                fontSize: '2rem',
                background: 'linear-gradient(135deg, #a5b4fc 0%, #818cf8 40%, #c4b5fd 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                textShadow: 'none',
                filter: `drop-shadow(0 0 ${8 + amplitude * 16}px rgba(139,92,246,0.9))`,
              }}
            >
              NDX
            </span>
          </div>

          {/* Listening pulse ring */}
          {isListening && (
            <div
              className="absolute inset-0 rounded-full animate-ping"
              style={{
                border: '2px solid rgba(99, 179, 237, 0.4)',
                animationDuration: '1.5s',
              }}
            />
          )}
        </div>

        {/* State label */}
        <div className="text-center space-y-2">
          <p className={`text-lg font-mono font-semibold tracking-widest uppercase ${stateColor}`}
             style={{ textShadow: '0 0 20px currentColor' }}>
            {stateLabel}
          </p>

          {/* Transcript preview */}
          {transcript && isListening && (
            <p className="text-sm text-white/60 font-mono max-w-xs text-center px-4 animate-pulse">
              "{transcript}"
            </p>
          )}

          {/* Audio level bars */}
          {isListening && (
            <div className="flex items-end justify-center gap-1 h-8">
              {Array.from({ length: 9 }).map((_, i) => {
                const barAmp = Math.max(0.05, amplitude * (0.4 + Math.sin(Date.now() * 0.005 + i) * 0.3))
                return (
                  <div
                    key={i}
                    className="w-1 rounded-full transition-all duration-75"
                    style={{
                      height: `${Math.max(4, barAmp * 28 + (i === 4 ? 6 : 0))}px`,
                      background: `hsla(${200 + i * 15}, 85%, 65%, 0.8)`,
                      boxShadow: `0 0 6px hsla(${200 + i * 15}, 85%, 65%, 0.6)`,
                    }}
                  />
                )
              })}
            </div>
          )}
        </div>

        {/* Close hint */}
        <p className="text-xs text-white/30 font-mono">
          Diga <span className="text-white/50">"NOC obrigado"</span> para encerrar · clique fora para fechar
        </p>
      </div>
    </div>
  )
}
