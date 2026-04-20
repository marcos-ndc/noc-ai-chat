import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth, useAuthStore } from '../hooks/useAuth'

export function LoginPage() {
  const { login, isLoading, error } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await login({ email, password })
    // CR-1: only navigate if login actually succeeded
    if (useAuthStore.getState().isAuthenticated) {
      navigate('/chat')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center noc-grid px-4">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-noc-accent/5 rounded-full blur-3xl" />
        <div className="absolute top-1/3 left-1/3 w-[300px] h-[300px] bg-noc-accent2/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-noc-accent/20 to-noc-accent2/20 border border-noc-accent/30 mb-4 glow-accent">
            <span className="text-2xl font-display font-bold text-noc-accent text-glow">N</span>
          </div>
          <h1 className="text-2xl font-display font-bold text-noc-text">
            NOC<span className="text-noc-accent"> AI</span>
          </h1>
          <p className="text-xs text-noc-muted font-mono mt-1">
            Centro de Operações Inteligente
          </p>
        </div>

        {/* Form card */}
        <div className="bg-noc-surface border border-noc-border rounded-2xl p-6 shadow-2xl">
          <h2 className="text-sm font-semibold text-noc-text mb-5">Acesso ao sistema</h2>

          <form onSubmit={handleSubmit} noValidate>
            <div className="space-y-4">
              {/* Email */}
              <div>
                <label htmlFor="email" className="block text-xs text-noc-muted font-mono mb-1.5">
                  E-mail
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  placeholder="analista@empresa.com"
                  className="
                    w-full px-3 py-2.5 rounded-xl bg-noc-bg border border-noc-border
                    text-sm text-noc-text placeholder:text-noc-muted/50 font-mono
                    focus:outline-none focus:border-noc-accent/60 focus:ring-1 focus:ring-noc-accent/20
                    transition-all duration-200
                  "
                />
              </div>

              {/* Password */}
              <div>
                <label htmlFor="password" className="block text-xs text-noc-muted font-mono mb-1.5">
                  Senha
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className="
                    w-full px-3 py-2.5 rounded-xl bg-noc-bg border border-noc-border
                    text-sm text-noc-text placeholder:text-noc-muted/50 font-mono
                    focus:outline-none focus:border-noc-accent/60 focus:ring-1 focus:ring-noc-accent/20
                    transition-all duration-200
                  "
                />
              </div>

              {/* Error */}
              {error && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-noc-danger/10 border border-noc-danger/30">
                  <span className="text-noc-danger text-xs">⚠</span>
                  <p className="text-xs text-noc-danger font-mono">{error}</p>
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={isLoading || !email || !password}
                className="
                  w-full py-2.5 rounded-xl font-semibold text-sm
                  bg-noc-accent text-noc-bg
                  hover:bg-noc-accent/90 active:scale-[0.98]
                  disabled:opacity-40 disabled:cursor-not-allowed
                  transition-all duration-200 glow-accent
                  flex items-center justify-center gap-2
                "
              >
                {isLoading ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <circle cx="12" cy="12" r="10" strokeOpacity="0.3" strokeWidth="3"/>
                      <path d="M12 2a10 10 0 0 1 10 10" strokeWidth="3"/>
                    </svg>
                    Entrando...
                  </>
                ) : (
                  'Entrar'
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Quick login hints */}
        <div className="mt-4 space-y-1.5">
          {[
            { email: 'admin-sys@noc.local', pass: 'admin-noc-2024', label: 'Admin', badge: '⚙️' },
            { email: 'gestor@noc.local',    pass: 'mgr2024',         label: 'Gestor', badge: '👔' },
            { email: 'n1@noc.local',        pass: 'noc2024',         label: 'N1',     badge: '🟢' },
          ].map(u => (
            <button
              key={u.email}
              type="button"
              onClick={() => { setEmail(u.email); setPassword(u.pass) }}
              className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg border border-noc-border/40 text-noc-muted hover:border-noc-border hover:text-noc-text transition-all text-[10px] font-mono"
            >
              <span>{u.badge}</span>
              <span className="font-semibold">{u.label}</span>
              <span className="text-noc-muted/60">{u.email}</span>
            </button>
          ))}
        </div>

        {/* Footer */}
        <p className="text-center text-[10px] text-noc-muted font-mono mt-4">
          NOC AI Chat · Agente especializado em monitoramento
        </p>
      </div>
    </div>
  )
}
