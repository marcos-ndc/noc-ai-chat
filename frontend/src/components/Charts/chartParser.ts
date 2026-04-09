/**
 * Detects chart-renderable data blocks in agent messages.
 * The agent wraps chart data in ```chart ... ``` code blocks.
 * Also detects ThousandEyes metric patterns from tool results.
 */

import type {
  MultiMetricData, AvailabilityData,
  ResponseTimeData, PacketLossData,
  TestSummaryItem, TimeSeriesPoint,
} from './NocCharts'

export type ChartBlock =
  | { type: 'multi_metric';   data: MultiMetricData }
  | { type: 'availability';   data: AvailabilityData }
  | { type: 'response_time';  data: ResponseTimeData }
  | { type: 'packet_loss';    data: PacketLossData }
  | { type: 'availability_summary'; data: { tests: TestSummaryItem[]; threshold: number } }

export interface ParsedMessage {
  textParts: string[]    // markdown text segments between charts
  charts: ChartBlock[]   // chart blocks in order
  segments: Array<{ kind: 'text' | 'chart'; index: number }>
}

// ─── Fenced code block parser ─────────────────────────────────────────────────

const CHART_FENCE = /```chart\s*\n([\s\S]*?)```/g

export function parseMessageWithCharts(content: string): ParsedMessage {
  const segments: ParsedMessage['segments'] = []
  const textParts: string[] = []
  const charts: ChartBlock[] = []

  let lastIndex = 0
  let match: RegExpExecArray | null

  CHART_FENCE.lastIndex = 0
  while ((match = CHART_FENCE.exec(content)) !== null) {
    // Text before this chart block
    const textBefore = content.slice(lastIndex, match.index)
    if (textBefore.trim()) {
      const ti = textParts.push(textBefore) - 1
      segments.push({ kind: 'text', index: ti })
    }

    // Parse the chart JSON
    try {
      const parsed = JSON.parse(match[1].trim())
      const chart = parseChartBlock(parsed)
      if (chart) {
        const ci = charts.push(chart) - 1
        segments.push({ kind: 'chart', index: ci })
      }
    } catch {
      // Invalid JSON — treat as text
      const ti = textParts.push(match[0]) - 1
      segments.push({ kind: 'text', index: ti })
    }

    lastIndex = match.index + match[0].length
  }

  // Remaining text
  const remaining = content.slice(lastIndex)
  if (remaining.trim()) {
    const ti = textParts.push(remaining) - 1
    segments.push({ kind: 'text', index: ti })
  }

  // If no chart blocks found, return original content as single text part
  if (segments.length === 0) {
    textParts.push(content)
    segments.push({ kind: 'text', index: 0 })
  }

  return { textParts, charts, segments }
}

function parseChartBlock(data: any): ChartBlock | null {
  if (!data?.chartType) return null

  switch (data.chartType) {
    case 'multi_metric':
      return { type: 'multi_metric', data: buildMultiMetric(data) }
    case 'availability':
      return { type: 'availability', data: buildAvailability(data) }
    case 'response_time':
      return { type: 'response_time', data: buildResponseTime(data) }
    case 'packet_loss':
      return { type: 'packet_loss', data: buildPacketLoss(data) }
    case 'availability_summary':
      return {
        type: 'availability_summary',
        data: {
          tests: (data.tests || []) as TestSummaryItem[],
          threshold: data.threshold ?? 99,
        },
      }
    default:
      return null
  }
}

// ─── Builders ─────────────────────────────────────────────────────────────────

function toPoints(arr: any[]): TimeSeriesPoint[] {
  if (!Array.isArray(arr)) return []
  return arr.map((item: any, i: number) => ({
    time: item.time ?? item.dateStart ?? item.clock_iso ?? formatIndex(i),
    value: Number(item.value ?? item.availability ?? item.responseTime ?? item.loss ?? 0),
  }))
}

function formatIndex(i: number): string {
  const h = i * 5
  return `${String(Math.floor(h / 60)).padStart(2, '0')}:${String(h % 60).padStart(2, '0')}`
}

function buildMultiMetric(d: any): MultiMetricData {
  return {
    testName: d.testName ?? 'Teste',
    window: d.window ?? '1h',
    availability: toPoints(d.availability ?? []),
    responseTime: toPoints(d.responseTime ?? []),
    packetLoss: toPoints(d.packetLoss ?? []),
    aggregated: {
      avg_availability: d.aggregated?.avg_availability,
      avg_response_time_ms: d.aggregated?.avg_response_time_ms,
      avg_packet_loss_pct: d.aggregated?.avg_packet_loss_pct,
    },
  }
}

function buildAvailability(d: any): AvailabilityData {
  return {
    testName: d.testName ?? '',
    window: d.window ?? '1h',
    points: toPoints(d.points ?? d.results ?? []),
    avg: d.avg ?? d.aggregated?.avg_availability ?? 0,
  }
}

function buildResponseTime(d: any): ResponseTimeData {
  return {
    testName: d.testName ?? '',
    window: d.window ?? '1h',
    points: toPoints(d.points ?? d.results ?? []),
    avg: d.avg ?? d.aggregated?.avg_response_time_ms ?? 0,
    p95: d.p95,
  }
}

function buildPacketLoss(d: any): PacketLossData {
  return {
    testName: d.testName ?? '',
    window: d.window ?? '1h',
    points: toPoints(d.points ?? d.results ?? []),
    avg: d.avg ?? d.aggregated?.avg_packet_loss_pct ?? 0,
  }
}
