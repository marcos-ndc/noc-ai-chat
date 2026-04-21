/**
 * SpecialistToast — Notificação quando o agente redireciona para um especialista
 * Aparece brevemente no centro da tela com o nome e motivo do redirecionamento.
 */
import { useEffect, useState } from 'react'
import { SPECIALISTS } from '../../types'

interface SpecialistToastProps {
  specialist: string | null
  reason:     string | null
}

export function SpecialistToast({ specialist, reason }: SpecialistToastProps) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!specialist) return
    setVisible(true)
    const t = setTimeout(() => setVisible(false), 4000)
    return () => clearTimeout(t)
  }, [specialist])

  if (!visible || !specialist) return null

  const info = SPECIALISTS.find(s => s.id === specialist)
  if (!info) return null

  return (
    <div className="fixed top-20 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
      <div className={`
        flex items-center gap-3 px-5 py-3 rounded-2xl
        border border-noc-accent/40 bg-noc-surface/95 backdrop-blur-sm
        shadow-2xl shadow-noc-accent/10
        animate-in slide-in-from-top-4 duration-300
      `}>
        <span className="text-2xl">{info.icon}</span>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-noc-muted uppercase tracking-widest">
              🔀 Redirecionando para
            </span>
          </div>
          <p className={`text-sm font-bold font-mono ${info.color}`}>
            {info.label}
          </p>
          {reason && (
            <p className="text-[10px] text-noc-muted mt-0.5 max-w-xs truncate">
              {reason}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
