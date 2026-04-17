// ─── Core Domain Types ───────────────────────────────────────────────────────

export type UserProfile = 'N1' | 'N2' | 'engineer' | 'manager'

export interface User {
  id: string
  name: string
  email: string
  profile: UserProfile
  avatarInitials: string
}

export type MessageRole = 'user' | 'agent'
export type MessageStatus = 'sending' | 'streaming' | 'done' | 'error'

export interface Message {
  id: string
  role: MessageRole
  content: string
  status: MessageStatus
  timestamp: Date
  toolsUsed?: ToolName[]
}

// ─── NOC Tools ───────────────────────────────────────────────────────────────

export type ToolName = 'zabbix' | 'datadog' | 'grafana' | 'thousandeyes'

export interface ToolStatus {
  tool: ToolName
  label: string
  icon: string
  active: boolean
}

export const TOOL_METADATA: Record<ToolName, { label: string; icon: string; color: string }> = {
  zabbix:       { label: 'Zabbix',       icon: '🔴', color: '#d40000' },
  datadog:      { label: 'Datadog',      icon: '🐕', color: '#632ca6' },
  grafana:      { label: 'Grafana',      icon: '📊', color: '#f46800' },
  thousandeyes: { label: 'ThousandEyes', icon: '👁️', color: '#00bceb' },
}

// ─── WebSocket Events ─────────────────────────────────────────────────────────

export type WSEventType =
  | 'user_message'
  | 'agent_token'        // streaming token
  | 'agent_done'         // response complete
  | 'tool_start'         // agent started consulting a tool
  | 'tool_end'           // tool consultation done
  | 'error'
  | 'ping'
  | 'pong'

export interface WSEvent {
  type: WSEventType
  messageId?: string
  content?: string
  tool?: ToolName
  error?: string
}

export interface WSOutboundMessage {
  type: 'user_message'
  content: string
  sessionId: string
  voiceMode?: boolean   // true quando mensagem veio de voz → agente responde em texto oral
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface AuthCredentials {
  email: string
  password: string
}

export interface AuthResponse {
  token: string
  user: User
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
}

// ─── Chat State ───────────────────────────────────────────────────────────────

export interface ChatState {
  messages: Message[]
  activeTools: ToolName[]
  isConnected: boolean
  isAgentTyping: boolean
  sessionId: string
}

// ─── Voice ────────────────────────────────────────────────────────────────────

export type VoiceInputState = 'idle' | 'listening' | 'processing' | 'error'
export type VoiceOutputState = 'idle' | 'speaking' | 'paused'

export interface VoiceSettings {
  inputEnabled: boolean
  outputEnabled: boolean
  language: string
  rate: number
  pitch: number
}
