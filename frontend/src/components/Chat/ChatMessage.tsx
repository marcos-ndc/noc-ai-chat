import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '../../types'
import { TOOL_METADATA } from '../../types'
import { parseMessageWithCharts } from '../Charts/chartParser'
import {
  AvailabilityChart, ResponseTimeChart, PacketLossChart,
  MetricDashboard, AvailabilitySummaryChart, NetworkLatencyChart,
} from '../Charts/NocCharts'

// ─── AgentContent — renders markdown + inline charts ─────────────────────────

function AgentContent({ content, isStreaming }: { content: string; isStreaming: boolean }) {
  const { segments, textParts, charts } = parseMessageWithCharts(content)

  return (
    <div className={isStreaming ? 'typing-cursor' : ''}>
      {segments.map((seg, i) => {
        if (seg.kind === 'text') {
          const text = textParts[seg.index]
          if (!text?.trim()) return null
          return (
            <div key={i} className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
            </div>
          )
        }
        const chart = charts[seg.index]
        if (!chart) return null
        return (
          <div key={i} className="-mx-4">
            {chart.type === 'multi_metric' && <MetricDashboard data={chart.data} />}
            {chart.type === 'availability' && <AvailabilityChart data={chart.data} />}
            {chart.type === 'response_time' && <ResponseTimeChart data={chart.data} />}
            {chart.type === 'packet_loss' && <PacketLossChart data={chart.data} />}
            {chart.type === 'network_latency' && <NetworkLatencyChart data={chart.data} />}
            {chart.type === 'availability_summary' && (
              <AvailabilitySummaryChart tests={chart.data.tests} threshold={chart.data.threshold} />
            )}
          </div>
        )
      })}
    </div>
  )
}


// ─── ChatMessage ──────────────────────────────────────────────────────────────

interface ChatMessageProps {
  message: Message
}

function formatTime(date: Date | string): string {
  // AL-4: timestamps from WS arrive as ISO strings, not Date objects
  const d = date instanceof Date ? date : new Date(date)
  if (isNaN(d.getTime())) return '--:--'
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser  = message.role === 'user'
  const isError = message.status === 'error'
  const isStreaming = message.status === 'streaming'

  return (
    <div className={`flex w-full msg-appear ${isUser ? 'justify-end' : 'justify-start'} px-4 py-1`}>
      {/* Agent avatar */}
      {!isUser && (
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-noc-border border border-noc-accent/30 flex items-center justify-center mr-2 mt-1">
          <span className="text-xs text-noc-accent font-mono font-bold">AI</span>
        </div>
      )}

      <div className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Bubble */}
        <div
          className={`
            relative rounded-2xl px-4 py-3 text-sm leading-relaxed
            ${isUser
              ? 'bg-noc-user text-white rounded-tr-sm'
              : isError
                ? 'bg-red-900/30 border border-noc-danger/40 text-red-200 rounded-tl-sm'
                : 'bg-noc-agent border border-noc-border/60 text-noc-text rounded-tl-sm'
            }
          `}
        >
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <AgentContent content={message.content || ' '} isStreaming={isStreaming} />
          )}

          {/* Accent line for agent messages */}
          {!isUser && !isError && (
            <div className="absolute left-0 top-3 bottom-3 w-0.5 bg-noc-accent/40 rounded-full" />
          )}
        </div>

        {/* Footer: time + tools used */}
        <div className="flex items-center gap-2 mt-1 px-1">
          <span className="text-[10px] text-noc-muted font-mono">
            {formatTime(message.timestamp)}
          </span>

          {message.toolsUsed && message.toolsUsed.length > 0 && (
            <div className="flex items-center gap-1">
              {message.toolsUsed.map(tool => {
                const meta = TOOL_METADATA[tool]
                return (
                  <span
                    key={tool}
                    className="text-[10px] font-mono opacity-60"
                    title={`Consultou ${meta.label}`}
                  >
                    {meta.icon}
                  </span>
                )
              })}
            </div>
          )}

          {message.status === 'error' && (
            <span className="text-[10px] text-noc-danger font-mono">erro</span>
          )}
        </div>
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-noc-user border border-blue-500/40 flex items-center justify-center ml-2 mt-1">
          <span className="text-[10px] text-white font-bold">EU</span>
        </div>
      )}
    </div>
  )
}
