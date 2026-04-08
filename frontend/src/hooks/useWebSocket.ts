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
  const { onMessage, onConnect, onDisconnect, autoReconnect = true, maxRetries = 3 } = options

  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalCloseRef = useRef(false)

  const connect = useCallback(() => {
    if (!url) return                                          // sem URL/token, não conecta
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      retriesRef.current = 0
      onConnect?.()
    }

    ws.onclose = () => {
      setIsConnected(false)
      onDisconnect?.()

      if (!intentionalCloseRef.current && autoReconnect && retriesRef.current < maxRetries) {
        const delay = Math.pow(2, retriesRef.current) * 1000
        retriesRef.current += 1
        retryTimerRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {
      setIsConnected(false)
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const parsed: WSEvent = JSON.parse(event.data as string)
        onMessage?.(parsed)
      } catch {
        // Ignore malformed messages
      }
    }
  }, [url, onMessage, onConnect, onDisconnect, autoReconnect, maxRetries])

  useEffect(() => {
    intentionalCloseRef.current = false
    connect()

    return () => {
      intentionalCloseRef.current = true
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((message: WSOutboundMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    wsRef.current?.close()
  }, [])

  return { isConnected, send, disconnect }
}
