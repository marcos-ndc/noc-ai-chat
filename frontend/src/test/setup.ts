import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock Web Speech API
Object.defineProperty(window, 'SpeechRecognition', {
  writable: true,
  value: vi.fn().mockImplementation(() => ({
    start: vi.fn(),
    stop: vi.fn(),
    abort: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
})

Object.defineProperty(window, 'webkitSpeechRecognition', {
  writable: true,
  value: window.SpeechRecognition
})

Object.defineProperty(window, 'speechSynthesis', {
  writable: true,
  value: {
    speak: vi.fn(),
    cancel: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    getVoices: vi.fn().mockReturnValue([]),
    speaking: false,
    paused: false,
  }
})

// Mock WebSocket
const MockWebSocket = vi.fn().mockImplementation((url: string) => ({
  url,
  readyState: 1,
  send: vi.fn(),
  close: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  onopen: null,
  onclose: null,
  onerror: null,
  onmessage: null,
}))
Object.defineProperty(window, 'WebSocket', { writable: true, value: MockWebSocket })
