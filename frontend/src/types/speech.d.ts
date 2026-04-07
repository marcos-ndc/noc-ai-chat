// Speech Recognition API type declarations
interface SpeechRecognition extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  start(): void
  stop(): void
  abort(): void
  addEventListener(type: 'result', listener: (event: SpeechRecognitionEvent) => void): void
  addEventListener(type: 'error', listener: (event: SpeechRecognitionErrorEvent) => void): void
  addEventListener(type: 'end', listener: () => void): void
  addEventListener(type: string, listener: EventListenerOrEventListenerObject): void
}

interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number
  readonly results: SpeechRecognitionResultList
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string
  readonly message: string
}

declare var SpeechRecognition: {
  prototype: SpeechRecognition
  new(): SpeechRecognition
}

interface Window {
  SpeechRecognition: typeof SpeechRecognition
  webkitSpeechRecognition: typeof SpeechRecognition
}
