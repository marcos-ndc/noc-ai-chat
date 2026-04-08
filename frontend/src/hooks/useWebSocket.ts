import { useCallback, useEffect, useRef, useState } from 'react'
import type { WSEvent, WSOutboundMessage } from '../types'

interface UseWebSocketOptions {
  onMessage?: (event: WSEvent) => void
  onConnect?: () => void
  onDisconnect?: () => void
  autoReconnect?: boolean
  maxRetries?: number
}

interface UseWebSocketReturn {
  isConnected: boolean
  send: (message: WSOutboundMessage) => void
  disconnect: () => void
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const { autoReconnect = true, maxRetries = 3 } = options

  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalCloseRef = useRef(false)

  // ─── Stable refs for callbacks ─────────────────────────────────────────────
  // Storing callbacks in refs means the WebSocket connection is NEVER torn down
  // just because the parent component re-renders or updates its callbacks.
  const onMessageRef = useRef(options.onMessage)
  const onConnectRef  = useRef(options.onConnect)
  const onDisconnectRef = useRef(options.onDisconnect)

  // Keep refs up to date on every render without causing reconnection
  useEffect(() => { onMessageRef.current = options.onMessage })
  useEffect(() => { onConnectRef.current = options.onConnect })
  useEffect(() => { onDisconnectRef.current = options.onDisconnect })

  // ─── Connect (stable — never recreated) ────────────────────────────────────
  const connectRef = useRef<() => void>(() => {})

  connectRef.current = () => {
    if (!url) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      retriesRef.current = 0
      onConnectRef.current?.()
    }

    ws.onclose = () => {
      setIsConnected(false)
      onDisconnectRef.current?.()

      if (!intentionalCloseRef.current && autoReconnect && retriesRef.current < maxRetries) {
        const delay = Math.pow(2, retriesRef.current) * 1000
        retriesRef.current += 1
        retryTimerRef.current = setTimeout(() => connectRef.current(), delay)
      }
    }

    ws.onerror = () => {
      setIsConnected(false)
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const parsed: WSEvent = JSON.parse(event.data as string)
        onMessageRef.current?.(parsed)
      } catch {
        // Ignore malformed messages
      }
    }
  }

  // ─── Only reconnect when the URL changes ───────────────────────────────────
  useEffect(() => {
    if (!url) return

    intentionalCloseRef.current = false
    connectRef.current()

    return () => {
      intentionalCloseRef.current = true
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [url]) // <-- ONLY url, never callbacks

  const send = useCallback((message: WSOutboundMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  return { isConnected, send, disconnect }
}
