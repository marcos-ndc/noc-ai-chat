import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useWebSocket } from '../useWebSocket'

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('deve iniciar desconectado', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))
    expect(result.current.isConnected).toBe(false)
  })

  it('deve conectar ao WebSocket ao montar', () => {
    renderHook(() => useWebSocket('ws://localhost:8000/ws'))
    expect(window.WebSocket).toHaveBeenCalledWith('ws://localhost:8000/ws')
  })

  it('deve atualizar isConnected para true ao abrir conexão', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))
    const ws = vi.mocked(window.WebSocket).mock.results[0].value

    act(() => { ws.onopen?.() })
    expect(result.current.isConnected).toBe(true)
  })

  it('deve atualizar isConnected para false ao fechar conexão', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))
    const ws = vi.mocked(window.WebSocket).mock.results[0].value

    act(() => { ws.onopen?.() })
    act(() => { ws.onclose?.() })
    expect(result.current.isConnected).toBe(false)
  })

  it('deve chamar onMessage ao receber mensagem', () => {
    const onMessage = vi.fn()
    renderHook(() => useWebSocket('ws://localhost:8000/ws', { onMessage }))
    const ws = vi.mocked(window.WebSocket).mock.results[0].value

    const event = { data: JSON.stringify({ type: 'agent_token', content: 'Olá' }) }
    act(() => { ws.onmessage?.(event as MessageEvent) })

    expect(onMessage).toHaveBeenCalledWith({ type: 'agent_token', content: 'Olá' })
  })

  it('deve enviar mensagem quando conectado', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))
    const ws = vi.mocked(window.WebSocket).mock.results[0].value

    act(() => { ws.onopen?.() })
    act(() => { result.current.send({ type: 'user_message', content: 'teste', sessionId: '123' }) })

    expect(ws.send).toHaveBeenCalledWith(JSON.stringify({ type: 'user_message', content: 'teste', sessionId: '123' }))
  })

  it('não deve enviar mensagem quando desconectado', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws'))
    const ws = vi.mocked(window.WebSocket).mock.results[0].value

    act(() => { result.current.send({ type: 'user_message', content: 'teste', sessionId: '123' }) })
    expect(ws.send).not.toHaveBeenCalled()
  })

  it('deve tentar reconectar após desconexão (backoff exponencial)', () => {
    renderHook(() => useWebSocket('ws://localhost:8000/ws', { autoReconnect: true }))
    const ws = vi.mocked(window.WebSocket).mock.results[0].value

    act(() => { ws.onclose?.() })

    // 1ª tentativa após 1s
    act(() => { vi.advanceTimersByTime(1000) })
    expect(window.WebSocket).toHaveBeenCalledTimes(2)

    // 2ª tentativa após 2s
    const ws2 = vi.mocked(window.WebSocket).mock.results[1].value
    act(() => { ws2.onclose?.() })
    act(() => { vi.advanceTimersByTime(2000) })
    expect(window.WebSocket).toHaveBeenCalledTimes(3)
  })

  it('deve parar de reconectar após 3 tentativas', () => {
    renderHook(() => useWebSocket('ws://localhost:8000/ws', { autoReconnect: true }))

    for (let i = 0; i < 4; i++) {
      const ws = vi.mocked(window.WebSocket).mock.results[i]?.value
      if (ws) act(() => { ws.onclose?.() })
      act(() => { vi.advanceTimersByTime(10000) })
    }

    expect(window.WebSocket).toHaveBeenCalledTimes(4) // inicial + 3 tentativas
  })
})
