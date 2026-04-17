import type { User } from '../../types'

interface HeaderProps {
  user: User | null
  isConnected: boolean
  onLogout: () => void
  voiceMode?: boolean
}

const profileLabel: Record<string, string> = {
  N1: 'Analista N1',
  N2: 'Analista N2',
  engineer: 'Engenheiro',
  manager: 'Gestor',
}

export function Header({ user, isConnected, onLogout, voiceMode = false }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-noc-border bg-noc-surface/80 backdrop-blur-sm">
      {/* Left — brand */}
      <div className="flex items-center gap-3">
        <div className="relative w-8 h-8">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-noc-accent/20 to-noc-accent2/20 border border-noc-accent/30 flex items-center justify-center">
            <span className="text-noc-accent text-xs font-display font-bold tracking-tight">N</span>
          </div>
          {/* Connection dot */}
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
            {isConnected ? (
              <span className="text-noc-success">● online</span>
            ) : (
              <span className="text-noc-danger">● reconectando...</span>
            )}
            {voiceMode && (
              <span className="text-noc-accent animate-pulse">🎙️ voz</span>
            )}
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

      {/* Right — user info + logout */}
      {user && (
        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <p className="text-xs font-semibold text-noc-text leading-none">{user.name}</p>
            <p className="text-[10px] text-noc-muted font-mono mt-0.5">
              {profileLabel[user.profile] ?? user.profile}
            </p>
          </div>

          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-noc-accent/30 to-noc-accent2/30 border border-noc-accent/40 flex items-center justify-center">
            <span className="text-xs text-noc-accent font-bold">{user.avatarInitials}</span>
          </div>

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
