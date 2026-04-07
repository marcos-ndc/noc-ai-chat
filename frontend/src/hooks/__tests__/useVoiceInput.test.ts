import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useVoiceInput } from '../useVoiceInput'

describe('useVoiceInput', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('deve iniciar em estado idle', () => {
    const { result } = renderHook(() => useVoiceInput())
    expect(result.current.state).toBe('idle')
    expect(result.current.transcript).toBe('')
  })

  it('deve verificar suporte do browser', () => {
    const { result } = renderHook(() => useVoiceInput())
    expect(result.current.isSupported).toBe(true)
  })

  it('deve mudar estado para listening ao iniciar', () => {
    const { result } = renderHook(() => useVoiceInput())

    act(() => { result.current.start() })
    expect(result.current.state).toBe('listening')
  })

  it('deve instanciar SpeechRecognition ao iniciar', () => {
    const { result } = renderHook(() => useVoiceInput())

    act(() => { result.current.start() })
    expect(window.SpeechRecognition).toHaveBeenCalled()
  })

  it('deve atualizar transcript ao receber resultado', () => {
    const { result } = renderHook(() => useVoiceInput())

    act(() => { result.current.start() })

    const recognition = vi.mocked(window.SpeechRecognition).mock.results[0].value
    const onResult = recognition.addEventListener.mock.calls.find(
      (call: unknown[]) => call[0] === 'result'
    )?.[1]

    act(() => {
      onResult?.({
        results: [[{ transcript: 'incidentes críticos agora' }]],
        resultIndex: 0
      } as unknown as SpeechRecognitionEvent)
    })

    expect(result.current.transcript).toBe('incidentes críticos agora')
  })

  it('deve mudar estado para idle ao parar', () => {
    const { result } = renderHook(() => useVoiceInput())

    act(() => { result.current.start() })
    act(() => { result.current.stop() })

    expect(result.current.state).toBe('idle')
  })

  it('deve chamar onResult com transcript ao parar', () => {
    const onResult = vi.fn()
    const { result } = renderHook(() => useVoiceInput({ onResult }))

    act(() => { result.current.start() })

    const recognition = vi.mocked(window.SpeechRecognition).mock.results[0].value
    const onResultHandler = recognition.addEventListener.mock.calls.find(
      (call: unknown[]) => call[0] === 'result'
    )?.[1]

    act(() => {
      onResultHandler?.({
        results: [[{ transcript: 'status do ambiente' }]],
        resultIndex: 0
      } as unknown as SpeechRecognitionEvent)
    })

    act(() => { result.current.stop() })
    expect(onResult).toHaveBeenCalledWith('status do ambiente')
  })

  it('deve limpar transcript ao chamar reset', () => {
    const { result } = renderHook(() => useVoiceInput())

    act(() => { result.current.start() })
    act(() => { result.current.reset() })

    expect(result.current.transcript).toBe('')
    expect(result.current.state).toBe('idle')
  })

  it('deve mudar para estado error em caso de falha', () => {
    const { result } = renderHook(() => useVoiceInput())

    act(() => { result.current.start() })

    const recognition = vi.mocked(window.SpeechRecognition).mock.results[0].value
    const onError = recognition.addEventListener.mock.calls.find(
      (call: unknown[]) => call[0] === 'error'
    )?.[1]

    act(() => { onError?.({ error: 'not-allowed' } as SpeechRecognitionErrorEvent) })
    expect(result.current.state).toBe('error')
  })
})
