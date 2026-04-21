/**
 * SpecialistSelector — Seletor de especialista NOC
 * Exibe o especialista ativo e permite troca manual.
 */
import { useState } from 'react'
import { SPECIALISTS } from '../../types'
import type { SpecialistId } from '../../types'

interface SpecialistSelectorProps {
  active:   SpecialistId
  onChange: (id: SpecialistId) => void
  disabled?: boolean
}

export function SpecialistSelector({ active, onChange, disabled = false }: SpecialistSelectorProps) {
  const [open, setOpen] = useState(false)
  const current = SPECIALISTS.find(s => s.id === active) ?? SPECIALISTS[0]

  return (
    <div className="relative">
      {/* Current specialist button */}
      <button
        type="button"
        onClick={() => !disabled && setOpen(o => !o)}
        disabled={disabled}
        className={`
          flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-mono
          transition-all duration-200
          ${disabled
            ? 'opacity-40 cursor-not-allowed border-noc-border text-noc-muted'
            : 'border-noc-border hover:border-noc-accent/40 text-noc-text cursor-pointer'
          }
        `}
        title="Selecionar especialista"
      >
        <span>{current.icon}</span>
        <span className={`font-semibold ${current.color}`}>{current.label}</span>
        <svg
          viewBox="0 0 24 24" fill="currentColor"
          className={`w-3 h-3 text-noc-muted transition-transform ${open ? 'rotate-180' : ''}`}
        >
          <path d="M7 10l5 5 5-5z"/>
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />

          <div className="absolute bottom-full left-0 mb-2 z-50 w-72 rounded-2xl border border-noc-border bg-noc-surface shadow-2xl shadow-black/50 overflow-hidden">
            <div className="px-3 py-2 border-b border-noc-border/60">
              <p className="text-[10px] font-mono text-noc-muted uppercase tracking-widest">
                Selecionar Especialista
              </p>
            </div>

            <div className="p-2 space-y-1">
              {SPECIALISTS.map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => { onChange(s.id); setOpen(false) }}
                  className={`
                    w-full flex items-start gap-3 px-3 py-2.5 rounded-xl text-left
                    transition-all duration-150
                    ${s.id === active
                      ? 'bg-noc-accent/10 border border-noc-accent/30'
                      : 'hover:bg-noc-bg/60 border border-transparent'
                    }
                  `}
                >
                  <span className="text-lg leading-none mt-0.5">{s.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className={`text-xs font-bold font-mono ${s.color} flex items-center gap-2`}>
                      {s.label}
                      {s.id === active && (
                        <span className="text-[9px] bg-noc-accent text-noc-bg px-1.5 py-0.5 rounded-full">
                          ATIVO
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-noc-muted mt-0.5 leading-relaxed">{s.desc}</p>
                  </div>
                </button>
              ))}
            </div>

            <div className="px-3 py-2 border-t border-noc-border/60">
              <p className="text-[9px] text-noc-muted font-mono">
                O agente também redireciona automaticamente quando identifica o domínio
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
