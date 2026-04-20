import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../hooks/useAuth'
import type { AIConfigInput, AIConfigOut, AdminStatus, ModelOption, TestResult } from '../types'

const API = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

function useAdminAPI() {
  const token = useAuthStore(s => s.token)
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
  const get  = (path: string) => fetch(`${API}${path}`, { headers }).then(r => r.json())
  const put  = (path: string, body: unknown) => fetch(`${API}${path}`, { method: 'PUT',  headers, body: JSON.stringify(body) }).then(r => r.json())
  const post = (path: string) => fetch(`${API}${path}`, { method: 'POST', headers }).then(r => r.json())
  return { get, put, post }
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionCard({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="bg-noc-surface border border-noc-border rounded-2xl overflow-hidden">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-noc-border/60">
        <span className="text-lg">{icon}</span>
        <h2 className="text-sm font-semibold text-noc-text font-mono tracking-wide">{title}</h2>
      </div>
      <div className="p-6">{children}</div>
    </div>
  )
}

function ProviderTab({ active, onClick, icon, label, badge }: {
  active: boolean; onClick: () => void; icon: string; label: string; badge?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        flex items-center gap-2.5 px-5 py-3 rounded-xl border text-sm font-mono transition-all duration-200 font-semibold
        ${active
          ? 'bg-noc-accent/10 border-noc-accent text-noc-accent shadow-lg shadow-noc-accent/10'
          : 'border-noc-border text-noc-muted hover:border-noc-border/80 hover:text-noc-text'
        }
      `}
    >
      <span className="text-base">{icon}</span>
      <span>{label}</span>
      {badge && (
        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${active ? 'bg-noc-accent/20 text-noc-accent' : 'bg-noc-border text-noc-muted'}`}>
          {badge}
        </span>
      )}
    </button>
  )
}

function ModelCard({ model, selected, onClick }: { model: ModelOption; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        w-full text-left p-4 rounded-xl border transition-all duration-150 group
        ${selected
          ? 'border-noc-accent bg-noc-accent/5 shadow-md shadow-noc-accent/10'
          : 'border-noc-border/60 hover:border-noc-border bg-noc-bg/30 hover:bg-noc-bg/60'
        }
      `}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-bold font-mono ${selected ? 'text-noc-accent' : 'text-noc-text'}`}>
              {model.name}
            </span>
            {selected && <span className="text-[9px] bg-noc-accent text-noc-bg px-1.5 py-0.5 rounded-full font-bold">ATIVO</span>}
          </div>
          <p className="text-[11px] text-noc-muted leading-relaxed">{model.description}</p>
        </div>
        <div className="flex-shrink-0 text-right">
          <span className="text-[10px] font-mono text-noc-muted">{model.context_k}K ctx</span>
        </div>
      </div>
      <div className="mt-2">
        <span className="text-[9px] font-mono text-noc-muted/60 bg-noc-border/30 px-2 py-0.5 rounded">
          {model.id}
        </span>
      </div>
    </button>
  )
}

function SliderField({ label, value, min, max, step, onChange, format }: {
  label: string; value: number; min: number; max: number; step: number
  onChange: (v: number) => void; format?: (v: number) => string
}) {
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-xs font-mono text-noc-muted">{label}</label>
        <span className="text-xs font-mono font-bold text-noc-accent">
          {format ? format(value) : value}
        </span>
      </div>
      <div className="relative">
        <input
          type="range"
          min={min} max={max} step={step} value={value}
          onChange={e => onChange(parseFloat(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
          style={{
            background: `linear-gradient(to right, #00d4ff ${pct}%, #1e2d4a ${pct}%)`,
          }}
        />
      </div>
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  const ok = status === 'ok'
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] font-mono ${ok ? 'text-noc-success' : 'text-noc-danger'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-noc-success' : 'bg-noc-danger animate-pulse'}`} />
      {ok ? 'online' : status}
    </span>
  )
}

// ─── Main AdminPage ───────────────────────────────────────────────────────────

export function AdminPage() {
  const navigate  = useNavigate()
  const user      = useAuthStore(s => s.user)
  const api       = useAdminAPI()

  const [config,    setConfig]    = useState<AIConfigOut | null>(null)
  const [models,    setModels]    = useState<ModelOption[]>([])
  const [status,    setStatus]    = useState<AdminStatus | null>(null)
  const [loading,   setLoading]   = useState(true)
  const [saving,    setSaving]    = useState(false)
  const [testing,   setTesting]   = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [saveMsg,   setSaveMsg]   = useState('')

  // Form state
  const [provider,    setProvider]    = useState<'anthropic' | 'openrouter'>('anthropic')
  const [model,       setModel]       = useState('claude-sonnet-4-20250514')
  const [apiKey,      setApiKey]      = useState('')
  const [temperature, setTemperature] = useState(1.0)
  const [maxTokens,   setMaxTokens]   = useState(4096)
  const [orBaseUrl,   setOrBaseUrl]   = useState('https://openrouter.ai/api/v1')
  const [siteName,    setSiteName]    = useState('NOC AI Chat')
  const [siteUrl,     setSiteUrl]     = useState('')
  const [showKey,     setShowKey]     = useState(false)

  // Redirect if not admin
  useEffect(() => {
    if (user && user.profile !== 'admin') {
      navigate('/chat')
    }
  }, [user, navigate])

  // Load data
  useEffect(() => {
    Promise.all([
      api.get('/admin/ai-config'),
      api.get('/admin/models'),
      api.get('/admin/status'),
    ]).then(([cfg, mdls, st]) => {
      setConfig(cfg)
      setModels(mdls)
      setStatus(st)
      // Populate form
      setProvider(cfg.provider)
      setModel(cfg.model)
      setTemperature(cfg.temperature)
      setMaxTokens(cfg.max_tokens)
      setOrBaseUrl(cfg.openrouter_base_url)
      setSiteName(cfg.site_name)
    }).finally(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const filteredModels = models.filter(m => m.provider === provider)

  const handleSave = useCallback(async () => {
    setSaving(true)
    setSaveMsg('')
    const body: AIConfigInput = {
      provider, model, api_key: apiKey,
      temperature, max_tokens: maxTokens,
      openrouter_base_url: orBaseUrl,
      site_url: siteUrl, site_name: siteName,
    }
    try {
      const updated = await api.put('/admin/ai-config', body)
      setConfig(updated)
      setApiKey('')
      setSaveMsg('✅ Configuração salva com sucesso')
      setTimeout(() => setSaveMsg(''), 4000)
    } catch {
      setSaveMsg('❌ Erro ao salvar configuração')
    } finally {
      setSaving(false)
    }
  }, [provider, model, apiKey, temperature, maxTokens, orBaseUrl, siteUrl, siteName, api])

  const handleTest = useCallback(async () => {
    setTesting(true)
    setTestResult(null)
    const result = await api.post('/admin/ai-config/test')
    setTestResult(result)
    setTesting(false)
  }, [api])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen noc-grid">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-noc-accent/30 border-t-noc-accent rounded-full animate-spin" />
          <span className="text-xs font-mono text-noc-muted">carregando painel...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen noc-grid text-noc-text">

      {/* Header */}
      <header className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-noc-border bg-noc-surface/90 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => navigate('/chat')}
            className="flex items-center gap-2 text-noc-muted hover:text-noc-text transition-colors text-sm font-mono"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
              <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
            </svg>
            Chat
          </button>
          <span className="text-noc-border">|</span>
          <div className="flex items-center gap-2">
            <span className="text-noc-accent text-lg">⚙️</span>
            <h1 className="text-sm font-bold font-mono text-noc-text tracking-wider">PAINEL DE ADMINISTRAÇÃO</h1>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-mono text-noc-muted">{user?.email}</span>
          <span className="text-[9px] px-2 py-0.5 rounded-full bg-noc-accent/10 border border-noc-accent/30 text-noc-accent font-mono font-bold">ADMIN</span>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* Status row */}
        {status && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            {/* Current model badge */}
            <div className="col-span-2 bg-noc-surface border border-noc-border rounded-xl px-4 py-3 flex items-center gap-3">
              <span className="text-2xl">🤖</span>
              <div>
                <p className="text-[10px] text-noc-muted font-mono">MODELO ATIVO</p>
                <p className="text-xs font-bold text-noc-accent font-mono truncate max-w-[200px]">{status.ai.model}</p>
                <p className="text-[10px] text-noc-muted font-mono capitalize">{status.ai.provider}</p>
              </div>
            </div>
            {/* Redis */}
            <div className="bg-noc-surface border border-noc-border rounded-xl px-4 py-3">
              <p className="text-[10px] text-noc-muted font-mono mb-1">REDIS</p>
              <StatusDot status={status.redis} />
            </div>
            {/* MCP servers */}
            {Object.entries(status.mcp_servers).map(([svc, s]) => (
              <div key={svc} className="bg-noc-surface border border-noc-border rounded-xl px-4 py-3">
                <p className="text-[10px] text-noc-muted font-mono mb-1 capitalize">{svc.toUpperCase().slice(0, 6)}</p>
                <StatusDot status={s.status} />
              </div>
            ))}
          </div>
        )}

        {/* Provider selection */}
        <SectionCard title="PROVEDOR DE IA" icon="🔌">
          <div className="flex flex-wrap gap-3">
            <ProviderTab
              active={provider === 'anthropic'}
              onClick={() => { setProvider('anthropic'); setModel('claude-sonnet-4-20250514') }}
              icon="🟣"
              label="Anthropic"
              badge="DIRETO"
            />
            <ProviderTab
              active={provider === 'openrouter'}
              onClick={() => { setProvider('openrouter'); setModel('anthropic/claude-sonnet-4-5') }}
              icon="🔀"
              label="OpenRouter"
              badge="MULTI-MODEL"
            />
          </div>
          {provider === 'openrouter' && (
            <div className="mt-4 p-4 rounded-xl bg-noc-bg border border-noc-border/60 text-[11px] text-noc-muted font-mono leading-relaxed">
              OpenRouter permite usar múltiplos modelos com uma única API key.
              Obtenha sua chave em{' '}
              <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer"
                 className="text-noc-accent hover:underline">openrouter.ai/keys</a>
            </div>
          )}
        </SectionCard>

        {/* Model selection */}
        <SectionCard title="MODELO" icon="🧠">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filteredModels.map(m => (
              <ModelCard
                key={m.id}
                model={m}
                selected={model === m.id}
                onClick={() => setModel(m.id)}
              />
            ))}
          </div>
          {/* Custom model input */}
          <div className="mt-4">
            <label className="text-[10px] font-mono text-noc-muted mb-1.5 block">
              ID PERSONALIZADO (opcional — sobrescreve seleção acima)
            </label>
            <input
              type="text"
              value={filteredModels.find(m => m.id === model) ? '' : model}
              onChange={e => e.target.value && setModel(e.target.value)}
              placeholder={model}
              className="w-full px-3 py-2 bg-noc-bg border border-noc-border rounded-lg text-xs font-mono text-noc-text placeholder:text-noc-muted/50 focus:outline-none focus:border-noc-accent/60"
            />
          </div>
        </SectionCard>

        {/* API Key */}
        <SectionCard title="CHAVE DE API" icon="🔑">
          <div className="space-y-4">
            {config?.api_key_set && (
              <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-noc-success/10 border border-noc-success/30">
                <span className="text-noc-success text-sm">✓</span>
                <span className="text-xs font-mono text-noc-success">
                  Chave configurada: {config.api_key_preview}
                </span>
              </div>
            )}
            <div>
              <label className="text-[10px] font-mono text-noc-muted mb-1.5 block">
                {provider === 'anthropic' ? 'ANTHROPIC API KEY' : 'OPENROUTER API KEY'}
                {config?.api_key_set && ' (deixe em branco para manter a atual)'}
              </label>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  placeholder={provider === 'anthropic' ? 'sk-ant-api03-...' : 'sk-or-v1-...'}
                  className="w-full pl-4 pr-12 py-3 bg-noc-bg border border-noc-border rounded-xl text-sm font-mono text-noc-text placeholder:text-noc-muted/40 focus:outline-none focus:border-noc-accent/60 focus:ring-1 focus:ring-noc-accent/20"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-noc-muted hover:text-noc-text transition-colors"
                >
                  <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
                    {showKey
                      ? <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
                      : <path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/>
                    }
                  </svg>
                </button>
              </div>
            </div>

            {provider === 'openrouter' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-[10px] font-mono text-noc-muted mb-1.5 block">SITE URL (opcional)</label>
                  <input type="text" value={siteUrl} onChange={e => setSiteUrl(e.target.value)}
                    placeholder="https://noc.suaempresa.com"
                    className="w-full px-3 py-2 bg-noc-bg border border-noc-border rounded-lg text-xs font-mono text-noc-text placeholder:text-noc-muted/40 focus:outline-none focus:border-noc-accent/60" />
                </div>
                <div>
                  <label className="text-[10px] font-mono text-noc-muted mb-1.5 block">NOME DO SITE</label>
                  <input type="text" value={siteName} onChange={e => setSiteName(e.target.value)}
                    className="w-full px-3 py-2 bg-noc-bg border border-noc-border rounded-lg text-xs font-mono text-noc-text focus:outline-none focus:border-noc-accent/60" />
                </div>
              </div>
            )}
          </div>
        </SectionCard>

        {/* Parameters */}
        <SectionCard title="PARÂMETROS DO MODELO" icon="🎛️">
          <div className="space-y-6">
            <SliderField
              label="TEMPERATURA"
              value={temperature}
              min={0} max={1} step={0.05}
              onChange={setTemperature}
              format={v => v.toFixed(2)}
            />
            <div className="text-[10px] font-mono text-noc-muted -mt-4">
              {temperature < 0.3 ? '❄️ Determinístico — respostas consistentes e previsíveis' :
               temperature < 0.7 ? '⚖️ Balanceado — boa variação mantendo coerência' :
               '🔥 Criativo — maior variedade e respostas mais elaboradas'}
            </div>
            <SliderField
              label="MAX TOKENS"
              value={maxTokens}
              min={512} max={8192} step={256}
              onChange={setMaxTokens}
              format={v => v.toLocaleString()}
            />
          </div>
        </SectionCard>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Test */}
          <button
            type="button"
            onClick={handleTest}
            disabled={testing}
            className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl border border-noc-border text-noc-muted hover:border-noc-accent/40 hover:text-noc-accent font-mono text-sm transition-all disabled:opacity-40"
          >
            {testing ? (
              <><div className="w-4 h-4 border border-noc-accent/30 border-t-noc-accent rounded-full animate-spin" /> Testando...</>
            ) : (
              <><span>🔬</span> Testar Conexão</>
            )}
          </button>

          {/* Save */}
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-noc-accent text-noc-bg font-bold font-mono text-sm hover:bg-noc-accent/90 transition-all disabled:opacity-40 shadow-lg shadow-noc-accent/20"
          >
            {saving ? (
              <><div className="w-4 h-4 border-2 border-noc-bg/30 border-t-noc-bg rounded-full animate-spin" /> Salvando...</>
            ) : (
              <><span>💾</span> Salvar Configuração</>
            )}
          </button>
        </div>

        {/* Save message */}
        {saveMsg && (
          <div className={`px-4 py-3 rounded-xl text-sm font-mono border ${
            saveMsg.startsWith('✅')
              ? 'bg-noc-success/10 border-noc-success/30 text-noc-success'
              : 'bg-noc-danger/10 border-noc-danger/30 text-noc-danger'
          }`}>
            {saveMsg}
          </div>
        )}

        {/* Test result */}
        {testResult && (
          <div className={`p-5 rounded-xl border font-mono text-xs ${
            testResult.success
              ? 'bg-noc-success/5 border-noc-success/30'
              : 'bg-noc-danger/5 border-noc-danger/30'
          }`}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-base">{testResult.success ? '✅' : '❌'}</span>
              <span className={`font-bold ${testResult.success ? 'text-noc-success' : 'text-noc-danger'}`}>
                {testResult.success ? 'Conexão bem-sucedida' : 'Falha na conexão'}
              </span>
            </div>
            {testResult.success ? (
              <div className="space-y-1.5 text-noc-muted">
                <div><span className="text-noc-text">Provedor:</span> {testResult.provider}</div>
                <div><span className="text-noc-text">Modelo:</span> {testResult.model}</div>
                <div><span className="text-noc-text">Resposta:</span> <span className="text-noc-accent">"{testResult.response}"</span></div>
                <div><span className="text-noc-text">Tokens:</span> {testResult.input_tokens} entrada / {testResult.output_tokens} saída</div>
              </div>
            ) : (
              <div className="text-noc-danger space-y-2">
                <div><span className="text-noc-text">Tipo:</span> {testResult.error_type}</div>
                <div className="text-noc-muted break-all text-[10px]">{testResult.error}</div>
                {testResult.hint && (
                  <div className="mt-2 px-3 py-2 rounded-lg bg-noc-accent/10 border border-noc-accent/20 text-noc-accent text-[11px]">
                    💡 {testResult.hint}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Spacer */}
        <div className="h-8" />
      </div>
    </div>
  )
}
