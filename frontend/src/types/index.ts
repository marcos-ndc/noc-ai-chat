// ─── Core Domain Types ───────────────────────────────────────────────────────

export type UserProfile = 'N1' | 'N2' | 'engineer' | 'manager' | 'admin'

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
  | 'specialist_change'  // agent routed to a specialist
  | 'error'
  | 'ping'
  | 'pong'

export interface WSEvent {
  type:       WSEventType
  messageId?: string
  content?:   string
  tool?:      ToolName
  error?:     string
  specialist?: string
  reason?:    string
}

export interface WSOutboundMessage {
  type:       'user_message'
  content:    string
  sessionId:  string
  voiceMode?: boolean
  specialist?: string   // manual specialist selection
}

export type SpecialistId =
  | 'generalista'
  | 'apm'
  | 'infra'
  | 'conectividade'
  | 'observabilidade'

export interface SpecialistInfo {
  id:    SpecialistId
  label: string
  icon:  string
  desc:  string
  color: string
}

export const SPECIALISTS: SpecialistInfo[] = [
  { id: 'generalista',     label: 'Generalista',     icon: '🤖', desc: 'Triagem geral e diagnóstico inicial',           color: 'text-noc-text' },
  { id: 'apm',             label: 'APM & Logs',      icon: '📊', desc: 'Erros de app, latência HTTP, traces, logs',    color: 'text-noc-warning' },
  { id: 'infra',           label: 'Infraestrutura',  icon: '🖥️', desc: 'CPU, memória, disco, disponibilidade de host', color: 'text-noc-success' },
  { id: 'conectividade',   label: 'Conectividade',   icon: '🌐', desc: 'Latência de rede, BGP, DNS, VPN',              color: 'text-noc-accent' },
  { id: 'observabilidade', label: 'Observabilidade', icon: '📈', desc: 'Dashboards, SLOs, correlação de métricas',     color: 'text-noc-accent2' },
]

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

// ─── Admin / AI Config ────────────────────────────────────────────────────────

export type AIProvider = 'anthropic' | 'openrouter'

export interface AIConfigOut {
  provider:            AIProvider
  model:               string
  api_key_set:         boolean
  api_key_preview:     string
  temperature:         number
  max_tokens:          number
  openrouter_base_url: string
  site_name:           string
}

export interface AIConfigInput {
  provider:            AIProvider
  model:               string
  api_key:             string
  temperature:         number
  max_tokens:          number
  openrouter_base_url: string
  site_url:            string
  site_name:           string
}

export interface ModelOption {
  id:          string
  name:        string
  provider:    AIProvider
  description: string
  context_k:   number
}

export interface AdminStatus {
  ai: {
    provider:    AIProvider
    model:       string
    api_key_set: boolean
  }
  redis: 'ok' | 'down'
  mcp_servers: Record<string, { status: string }>
}

export interface PromptEntry {
  key:          string
  label:        string
  category:     'specialist' | 'profile'
  default_text: string
  current_text: string
  is_overridden: boolean
}

export interface TestResult {
  success:        boolean
  provider?:      AIProvider
  model?:         string
  response?:      string
  input_tokens?:  number
  output_tokens?: number
  error?:         string
  error_type?:    string
  hint?:          string
}
