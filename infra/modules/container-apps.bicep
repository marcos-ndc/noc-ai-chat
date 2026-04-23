/*
  Container Apps — backend + 4 MCP servers (interno).

  Backend:
  • Ingress externo (HTTPS público)
  • Sticky sessions para WebSocket
  • Min 1 réplica (NOC é 24/7)
  • Scale até 5 com base em requisições HTTP

  MCP Servers (×4):
  • Ingress interno (sem exposição pública)
  • Scale to zero (min=0) — só ativa quando chamado pelo backend
  • 0.25 vCPU / 0.5 GB cada
*/

// ─── Parâmetros ───────────────────────────────────────────────────────────────

param prefix string
param location string
param tags object
param logAnalyticsCustomerId string
@secure()
param logAnalyticsKey string
param acrLoginServer string
param identityId string
param identityClientId string
param imageTag string
param frontendUrl string

// Segredos
@secure() param anthropicApiKey string
@secure() param jwtSecret string
@secure() param redisUrl string
@secure() param openaiApiKey string
@secure() param elevenLabsApiKey string
@secure() param elevenLabsVoiceId string
@secure() param zabbixUrl string
@secure() param zabbixUser string
@secure() param zabbixPassword string
@secure() param datadogApiKey string
@secure() param datadogAppKey string
@secure() param grafanaUrl string
@secure() param grafanaToken string
@secure() param thousandEyesToken string

// ─── Container Apps Environment ───────────────────────────────────────────────

resource caEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-env'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsKey
      }
    }
    // Workload profile Consumption — serverless, paga pelo uso
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
  }
}

// ─── Managed Identity config (reutilizado em todos os apps) ───────────────────

var identityBlock = {
  type: 'UserAssigned'
  userAssignedIdentities: { '${identityId}': {} }
}

var registryBlock = [
  { server: acrLoginServer, identity: identityId }
]

// ─── Backend Container App ────────────────────────────────────────────────────

var corsOrigins = empty(frontendUrl) ? ['*'] : [frontendUrl]

resource backend 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-backend'
  location: location
  tags: tags
  identity: identityBlock
  properties: {
    environmentId: caEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        // Sticky sessions — essencial para WebSocket persistente
        stickySessions: { affinity: 'sticky' }
        corsPolicy: {
          allowedOrigins: corsOrigins
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['Authorization', 'Content-Type', 'Accept', 'X-Requested-With']
          allowCredentials: !empty(frontendUrl)
        }
      }
      registries: registryBlock
      secrets: [
        { name: 'anthropic-api-key',   value: anthropicApiKey }
        { name: 'jwt-secret',          value: jwtSecret }
        { name: 'redis-url',           value: redisUrl }
        { name: 'openai-api-key',      value: openaiApiKey }
        { name: 'elevenlabs-api-key',  value: elevenLabsApiKey }
        { name: 'elevenlabs-voice-id', value: elevenLabsVoiceId }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: '${acrLoginServer}/backend:${imageTag}'
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: [
            // Segredos via secretRef (não aparecem em plain text no portal)
            { name: 'ANTHROPIC_API_KEY',    secretRef: 'anthropic-api-key' }
            { name: 'JWT_SECRET',           secretRef: 'jwt-secret' }
            { name: 'REDIS_URL',            secretRef: 'redis-url' }
            { name: 'OPENAI_API_KEY',       secretRef: 'openai-api-key' }
            { name: 'ELEVENLABS_API_KEY',   secretRef: 'elevenlabs-api-key' }
            { name: 'ELEVENLABS_VOICE_ID',  secretRef: 'elevenlabs-voice-id' }
            // Configuração não-sensível
            { name: 'CORS_ALLOW_ALL',       value: 'false' }
            { name: 'CORS_ORIGINS',         value: empty(frontendUrl) ? '["*"]' : '["${frontendUrl}"]' }
            // URLs internas dos MCP servers (DNS do Container Apps Environment)
            { name: 'MCP_ZABBIX_URL',       value: 'http://${prefix}-mcp-zabbix' }
            { name: 'MCP_DATADOG_URL',      value: 'http://${prefix}-mcp-datadog' }
            { name: 'MCP_GRAFANA_URL',      value: 'http://${prefix}-mcp-grafana' }
            { name: 'MCP_THOUSANDEYES_URL', value: 'http://${prefix}-mcp-thousandeyes' }
            { name: 'LOG_LEVEL',            value: 'INFO' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
              initialDelaySeconds: 15
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
              initialDelaySeconds: 10
              periodSeconds: 15
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1    // Sempre 1 — NOC não pode ter downtime
        maxReplicas: 5
        rules: [
          {
            name: 'http-scaling'
            http: { metadata: { concurrentRequests: '20' } }
          }
        ]
      }
    }
  }
}

// ─── MCP Servers (ingresso interno, scale to zero) ────────────────────────────
// DNS interno do Container Apps: http://{app-name} (porta 80 → targetPort)
// O backend usa MCP_*_URL=http://{prefix}-mcp-{nome}

resource mcpZabbix 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-mcp-zabbix'
  location: location
  tags: tags
  identity: identityBlock
  properties: {
    environmentId: caEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: { external: false, targetPort: 8001, transport: 'http' }
      registries: registryBlock
      secrets: [
        { name: 'zabbix-url',      value: zabbixUrl }
        { name: 'zabbix-user',     value: zabbixUser }
        { name: 'zabbix-password', value: zabbixPassword }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp-zabbix'
          image: '${acrLoginServer}/mcp-zabbix:${imageTag}'
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: [
            { name: 'ZABBIX_URL',      secretRef: 'zabbix-url' }
            { name: 'ZABBIX_USER',     secretRef: 'zabbix-user' }
            { name: 'ZABBIX_PASSWORD', secretRef: 'zabbix-password' }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 2 }
    }
  }
}

resource mcpDatadog 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-mcp-datadog'
  location: location
  tags: tags
  identity: identityBlock
  properties: {
    environmentId: caEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: { external: false, targetPort: 8001, transport: 'http' }
      registries: registryBlock
      secrets: [
        { name: 'datadog-api-key', value: datadogApiKey }
        { name: 'datadog-app-key', value: datadogAppKey }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp-datadog'
          image: '${acrLoginServer}/mcp-datadog:${imageTag}'
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: [
            { name: 'DATADOG_API_KEY', secretRef: 'datadog-api-key' }
            { name: 'DATADOG_APP_KEY', secretRef: 'datadog-app-key' }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 2 }
    }
  }
}

resource mcpGrafana 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-mcp-grafana'
  location: location
  tags: tags
  identity: identityBlock
  properties: {
    environmentId: caEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: { external: false, targetPort: 8001, transport: 'http' }
      registries: registryBlock
      secrets: [
        { name: 'grafana-url',   value: grafanaUrl }
        { name: 'grafana-token', value: grafanaToken }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp-grafana'
          image: '${acrLoginServer}/mcp-grafana:${imageTag}'
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: [
            { name: 'GRAFANA_URL',   secretRef: 'grafana-url' }
            { name: 'GRAFANA_TOKEN', secretRef: 'grafana-token' }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 2 }
    }
  }
}

resource mcpThousandEyes 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-mcp-thousandeyes'
  location: location
  tags: tags
  identity: identityBlock
  properties: {
    environmentId: caEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: { external: false, targetPort: 8001, transport: 'http' }
      registries: registryBlock
      secrets: [
        { name: 'thousandeyes-token', value: thousandEyesToken }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp-thousandeyes'
          image: '${acrLoginServer}/mcp-thousandeyes:${imageTag}'
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: [
            { name: 'THOUSANDEYES_TOKEN', secretRef: 'thousandeyes-token' }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 2 }
    }
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

output backendFqdn string = backend.properties.configuration.ingress.fqdn
output caEnvId string = caEnv.id
