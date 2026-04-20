import { useNavigate } from 'react-router-dom'
import type { User } from '../../types'

interface HeaderProps {
  user: User | null
  isConnected: boolean
  onLogout: () => void
  voiceMode?: boolean
}

const profileLabel: Record<string, string> = {
  N1:       'Analista N1',
  N2:       'Analista N2',
  engineer: 'Engenheiro',
  manager:  'Gestor',
  admin:    'Administrador',
}

export function Header({ user, isConnected, onLogout, voiceMode = false }: HeaderProps) {
  const navigate = useNavigate()
  const isAdmin  = user?.profile === 'admin'

  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-noc-border bg-noc-surface/80 backdrop-blur-sm">

      {/* Left — brand */}
      <div className="flex items-center gap-3">
        <div className="relative w-8 h-8">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-noc-accent/20 to-noc-accent2/20 border border-noc-accent/30 flex items-center justify-center">
            <span className="text-noc-accent text-xs font-display font-bold tracking-tight">N</span>
          </div>
          <span
            className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-noc-surface transition-colors duration-500
              ${isConnected ? 'bg-noc-success' : 'bg-noc-danger animate-pulse'}`}
            title={isConnected ? 'Conectado' : 'Desconectado'}
          />
        </div>

        <div>
          <h1 className="text-sm font-display font-bold text-noc-text tracking-tight leading-none">
            NOC<span className="text-noc-accent"> AI</span>
          </h1>
          <p className="text-[10px] text-noc-muted font-mono leading-none mt-0.5 flex items-center gap-2">
            {isConnected
              ? <span className="text-noc-success">● online</span>
              : <span className="text-noc-danger">● reconectando...</span>}
            {voiceMode && <span className="text-noc-accent animate-pulse">🎙️ voz</span>}
          </p>
        </div>
      </div>

      {/* Center — tool badges */}
      <div className="hidden md:flex items-center gap-1.5">
        {(['zabbix', 'datadog', 'grafana', 'thousandeyes'] as const).map(tool => (
          <span
            key={tool}
            className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-noc-border/60 text-noc-muted"
          >
            {tool === 'thousandeyes' ? 'T.Eyes' : tool.charAt(0).toUpperCase() + tool.slice(1)}
          </span>
        ))}
      </div>

      {/* Right — user info + admin + logout */}
      {user && (
        <div className="flex items-center gap-2">
          <div className="text-right hidden sm:block">
            <p className="text-xs font-semibold text-noc-text leading-none">{user.name}</p>
            <p className="text-[10px] text-noc-muted font-mono mt-0.5">
              {profileLabel[user.profile] ?? user.profile}
            </p>
          </div>

          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-noc-accent/30 to-noc-accent2/30 border border-noc-accent/40 flex items-center justify-center">
            <span className="text-xs text-noc-accent font-bold">{user.avatarInitials}</span>
          </div>

          {/* Admin button — only shown for admin profile */}
          {isAdmin && (
            <button
              type="button"
              onClick={() => navigate('/admin')}
              aria-label="Painel de administração"
              title="Painel de Administração"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-noc-accent/50 bg-noc-accent/10 text-noc-accent hover:bg-noc-accent/20 transition-all duration-200 text-xs font-mono font-bold"
            >
              <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5 flex-shrink-0">
                <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
              </svg>
              <span>Admin</span>
            </button>
          )}

          <button
            type="button"
            onClick={onLogout}
            aria-label="Sair da conta"
            title="Sair"
            className="w-7 h-7 rounded-lg border border-noc-border/60 text-noc-muted hover:border-noc-danger/60 hover:text-noc-danger transition-all duration-200 flex items-center justify-center"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5">
              <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/>
            </svg>
          </button>
        </div>
      )}
    </header>
  )
}
