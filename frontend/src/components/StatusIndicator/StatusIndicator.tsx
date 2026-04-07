import type { ToolName } from '../../types'
import { TOOL_METADATA } from '../../types'

interface StatusIndicatorProps {
  activeTools: ToolName[]
  isTyping: boolean
}

export function StatusIndicator({ activeTools, isTyping }: StatusIndicatorProps) {
  if (!isTyping && activeTools.length === 0) return null

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="flex items-center gap-1.5 bg-noc-surface border border-noc-border rounded-full px-3 py-1.5">
        {activeTools.length > 0 ? (
          <>
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-noc-accent opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-noc-accent" />
            </span>
            <span className="text-xs text-noc-muted font-mono">Consultando</span>
            {activeTools.map(tool => {
              const meta = TOOL_METADATA[tool]
              return (
                <span
                  key={tool}
                  className="text-xs font-semibold tool-active"
                  style={{ color: meta.color }}
                >
                  {meta.icon} {meta.label}
                </span>
              )
            })}
          </>
        ) : (
          <>
            <span className="flex gap-0.5 items-end h-3">
              {[0, 1, 2].map(i => (
                <span
                  key={i}
                  className="w-0.5 bg-noc-accent rounded-full"
                  style={{
                    height: `${8 + i * 3}px`,
                    animation: `tool-pulse 1s ease-in-out ${i * 0.15}s infinite`,
                  }}
                />
              ))}
            </span>
            <span className="text-xs text-noc-muted font-mono">Processando...</span>
          </>
        )}
      </div>
    </div>
  )
}
