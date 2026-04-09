import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell,
} from 'recharts'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface TimeSeriesPoint {
  time: string
  value: number
}

export interface AvailabilityData {
  testName: string
  window: string
  points: TimeSeriesPoint[]
  avg: number
}

export interface ResponseTimeData {
  testName: string
  window: string
  points: TimeSeriesPoint[]
  avg: number
  p95?: number
}

export interface PacketLossData {
  testName: string
  window: string
  points: TimeSeriesPoint[]
  avg: number
}

export interface MultiMetricData {
  testName: string
  window: string
  availability: TimeSeriesPoint[]
  responseTime: TimeSeriesPoint[]
  packetLoss: TimeSeriesPoint[]
  aggregated: {
    avg_availability?: number
    avg_response_time_ms?: number
    avg_packet_loss_pct?: number
  }
}

// ─── Custom Tooltip ───────────────────────────────────────────────────────────

const NocTooltip = ({ active, payload, label, unit }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-noc-surface border border-noc-border rounded-lg px-3 py-2 text-xs font-mono shadow-lg">
      <p className="text-noc-muted mb-1">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: <span className="text-white font-bold">{p.value?.toFixed(2)}{unit}</span>
        </p>
      ))}
    </div>
  )
}

// ─── Availability Chart ───────────────────────────────────────────────────────

export function AvailabilityChart({ data }: { data: AvailabilityData }) {
  const color = data.avg >= 99.9 ? '#10b981' : data.avg >= 99 ? '#f59e0b' : '#ef4444'

  return (
    <div className="bg-noc-surface border border-noc-border rounded-xl p-4 my-2">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">🟢</span>
          <span className="text-sm font-semibold text-noc-text">Disponibilidade</span>
          {data.testName && (
            <span className="text-xs text-noc-muted font-mono">— {data.testName}</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-noc-muted font-mono">{data.window}</span>
          <span className="text-lg font-bold font-mono" style={{ color }}>
            {data.avg?.toFixed(2)}%
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={data.points} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id="availGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,45,74,0.5)" />
          <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 10, fontFamily: 'JetBrains Mono' }} />
          <YAxis domain={[80, 100]} tick={{ fill: '#6b7280', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            tickFormatter={(v) => `${v}%`} />
          <Tooltip content={<NocTooltip unit="%" />} />
          <ReferenceLine y={99} stroke="#f59e0b" strokeDasharray="3 3" strokeWidth={1} />
          <Area type="monotone" dataKey="value" name="Availability"
            stroke={color} strokeWidth={2} fill="url(#availGrad)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 mt-2 text-[10px] font-mono text-noc-muted">
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-yellow-500 inline-block" /> SLA 99%</span>
        <span className="flex items-center gap-1" style={{ color }}>● Média: {data.avg?.toFixed(2)}%</span>
      </div>
    </div>
  )
}

// ─── Response Time Chart ──────────────────────────────────────────────────────

export function ResponseTimeChart({ data }: { data: ResponseTimeData }) {
  const color = data.avg < 200 ? '#10b981' : data.avg < 500 ? '#f59e0b' : '#ef4444'

  return (
    <div className="bg-noc-surface border border-noc-border rounded-xl p-4 my-2">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">⏱️</span>
          <span className="text-sm font-semibold text-noc-text">Tempo de Resposta</span>
          {data.testName && (
            <span className="text-xs text-noc-muted font-mono">— {data.testName}</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-noc-muted font-mono">{data.window}</span>
          <span className="text-lg font-bold font-mono" style={{ color }}>
            {data.avg?.toFixed(0)}ms
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={data.points} margin={{ top: 5, right: 5, bottom: 0, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,45,74,0.5)" />
          <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 10, fontFamily: 'JetBrains Mono' }} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            tickFormatter={(v) => `${v}ms`} />
          <Tooltip content={<NocTooltip unit="ms" />} />
          <ReferenceLine y={500} stroke="#ef4444" strokeDasharray="3 3" strokeWidth={1} />
          <ReferenceLine y={200} stroke="#f59e0b" strokeDasharray="3 3" strokeWidth={1} />
          <Line type="monotone" dataKey="value" name="Response Time"
            stroke={color} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: color }} />
          {data.p95 && (
            <ReferenceLine y={data.p95} stroke="#00d4ff" strokeDasharray="2 2" strokeWidth={1} />
          )}
        </LineChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 mt-2 text-[10px] font-mono text-noc-muted">
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-yellow-500 inline-block" /> 200ms</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-red-500 inline-block" /> 500ms</span>
        {data.p95 && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-noc-accent inline-block" /> p95: {data.p95}ms</span>}
      </div>
    </div>
  )
}

// ─── Packet Loss Chart ────────────────────────────────────────────────────────

export function PacketLossChart({ data }: { data: PacketLossData }) {
  const color = data.avg === 0 ? '#10b981' : data.avg < 1 ? '#f59e0b' : '#ef4444'

  return (
    <div className="bg-noc-surface border border-noc-border rounded-xl p-4 my-2">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">📦</span>
          <span className="text-sm font-semibold text-noc-text">Perda de Pacotes</span>
          {data.testName && (
            <span className="text-xs text-noc-muted font-mono">— {data.testName}</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-noc-muted font-mono">{data.window}</span>
          <span className="text-lg font-bold font-mono" style={{ color }}>
            {data.avg?.toFixed(2)}%
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={data.points} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,45,74,0.5)" />
          <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 10, fontFamily: 'JetBrains Mono' }} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            tickFormatter={(v) => `${v}%`} />
          <Tooltip content={<NocTooltip unit="%" />} />
          <ReferenceLine y={1} stroke="#f59e0b" strokeDasharray="3 3" strokeWidth={1} />
          <Bar dataKey="value" name="Packet Loss" radius={[2, 2, 0, 0]}>
            {data.points.map((p, i) => (
              <Cell key={i} fill={p.value === 0 ? '#10b981' : p.value < 1 ? '#f59e0b' : '#ef4444'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── Multi-Metric Dashboard ───────────────────────────────────────────────────

export function MetricDashboard({ data }: { data: MultiMetricData }) {
  const agg = data.aggregated
  const healthColor = !agg.avg_availability ? '#6b7280'
    : agg.avg_availability >= 99.9 ? '#10b981'
    : agg.avg_availability >= 99 ? '#f59e0b' : '#ef4444'

  return (
    <div className="my-2">
      {/* Header */}
      <div className="bg-noc-surface border border-noc-border rounded-xl px-4 py-3 mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: healthColor }} />
          <span className="text-sm font-semibold text-noc-text">{data.testName}</span>
          <span className="text-xs text-noc-muted font-mono">· {data.window}</span>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          {agg.avg_availability !== undefined && (
            <span style={{ color: healthColor }}>{agg.avg_availability?.toFixed(2)}% avail</span>
          )}
          {agg.avg_response_time_ms !== undefined && (
            <span className="text-noc-accent">{agg.avg_response_time_ms?.toFixed(0)}ms</span>
          )}
          {agg.avg_packet_loss_pct !== undefined && (
            <span className={agg.avg_packet_loss_pct > 0 ? 'text-noc-danger' : 'text-noc-success'}>
              {agg.avg_packet_loss_pct?.toFixed(2)}% loss
            </span>
          )}
        </div>
      </div>

      {/* Charts */}
      {data.availability?.length > 0 && (
        <AvailabilityChart data={{
          testName: '', window: data.window,
          points: data.availability,
          avg: agg.avg_availability ?? 0,
        }} />
      )}
      {data.responseTime?.length > 0 && (
        <ResponseTimeChart data={{
          testName: '', window: data.window,
          points: data.responseTime,
          avg: agg.avg_response_time_ms ?? 0,
        }} />
      )}
      {data.packetLoss?.length > 0 && (
        <PacketLossChart data={{
          testName: '', window: data.window,
          points: data.packetLoss,
          avg: agg.avg_packet_loss_pct ?? 0,
        }} />
      )}
    </div>
  )
}

// ─── Availability Summary Bar Chart ──────────────────────────────────────────

export interface TestSummaryItem {
  name: string
  availability: number
  degraded: boolean
}

export function AvailabilitySummaryChart({ tests, threshold }: {
  tests: TestSummaryItem[]
  threshold: number
}) {
  const data = tests.map(t => ({
    name: t.name.length > 20 ? t.name.slice(0, 18) + '…' : t.name,
    fullName: t.name,
    value: t.availability,
    degraded: t.degraded,
  }))

  return (
    <div className="bg-noc-surface border border-noc-border rounded-xl p-4 my-2">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">📊</span>
          <span className="text-sm font-semibold text-noc-text">Disponibilidade por Teste</span>
        </div>
        <span className="text-xs text-noc-muted font-mono">SLA {threshold}%</span>
      </div>
      <ResponsiveContainer width="100%" height={Math.max(120, tests.length * 28)}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,45,74,0.5)" horizontal={false} />
          <XAxis type="number" domain={[80, 100]}
            tick={{ fill: '#6b7280', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            tickFormatter={(v) => `${v}%`} />
          <YAxis type="category" dataKey="name" width={120}
            tick={{ fill: '#e2e8f0', fontSize: 10, fontFamily: 'JetBrains Mono' }} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload
              return (
                <div className="bg-noc-surface border border-noc-border rounded-lg px-3 py-2 text-xs font-mono">
                  <p className="text-noc-text mb-1">{d.fullName}</p>
                  <p style={{ color: d.degraded ? '#ef4444' : '#10b981' }}>
                    {d.value?.toFixed(2)}%
                  </p>
                </div>
              )
            }}
          />
          <ReferenceLine x={threshold} stroke="#f59e0b" strokeDasharray="3 3" strokeWidth={1.5} />
          <Bar dataKey="value" radius={[0, 3, 3, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.degraded ? '#ef4444' : '#10b981'} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 mt-2 text-[10px] font-mono text-noc-muted">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-noc-success inline-block" /> OK</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-noc-danger inline-block" /> Degradado</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-yellow-500 inline-block" /> SLA {threshold}%</span>
      </div>
    </div>
  )
}
