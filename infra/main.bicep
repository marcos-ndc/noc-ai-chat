/*
  NOC AI Chat — Infraestrutura Azure
  ───────────────────────────────────
  Recursos criados:
  • Log Analytics Workspace
  • Azure Container Registry (Basic)
  • Azure Cache for Redis (Basic ou Standard)
  • Managed Identity + role assignments (AcrPull)
  • Container Apps Environment → módulo apps.bicep
  • Azure Static Web Apps (frontend)

  Segredos passados via pipeline (GitHub Actions) — nunca em código.
*/

targetScope = 'resourceGroup'

// ─── Parâmetros gerais ───────────────────────────────────────────────────────

@description('Prefixo dos recursos (ex: nocaichat). Sem hífens para ACR.')
param appName string = 'nocaichat'

@description('Região Azure (ex: brazilsouth, eastus2, westeurope).')
param location string = resourceGroup().location

@description('Ambiente: prod ou staging.')
@allowed(['prod', 'staging'])
param env string = 'prod'

@description('Tag da imagem Docker (ex: sha do commit).')
param imageTag string = 'latest'

@description('URL pública do frontend — preenchida após o 1º deploy.')
param frontendUrl string = ''

@description('Tier do Redis: Basic (sem HA, ~$55/mês) ou Standard (com HA, ~$110/mês).')
@allowed(['Basic', 'Standard'])
param redisSku string = 'Basic'

@description('Capacidade do Redis (1 = 1 GB).')
@minValue(1)
@maxValue(6)
param redisCapacity int = 1

// ─── Segredos obrigatórios (passados pelo pipeline, nunca commitados) ────────

@secure()
@description('Anthropic API Key (sk-ant-...).')
param anthropicApiKey string

@secure()
@description('Segredo JWT — mínimo 32 caracteres aleatórios.')
param jwtSecret string

// ─── Segredos opcionais ───────────────────────────────────────────────────────

@secure()
param openaiApiKey string = ''

@secure()
param elevenLabsApiKey string = ''

@secure()
param elevenLabsVoiceId string = ''

@secure()
param zabbixUrl string = ''

@secure()
param zabbixUser string = ''

@secure()
param zabbixPassword string = ''

@secure()
param datadogApiKey string = ''

@secure()
param datadogAppKey string = ''

@secure()
param grafanaUrl string = ''

@secure()
param grafanaToken string = ''

@secure()
param thousandEyesToken string = ''

// ─── Variáveis ───────────────────────────────────────────────────────────────

var prefix   = '${appName}-${env}'
var acrName  = '${replace(appName, '-', '')}${env}acr'   // alphanumeric ≤50 chars
var tags     = { application: 'noc-ai-chat', environment: env, managedBy: 'bicep' }

// ─── Log Analytics Workspace ──────────────────────────────────────────────────

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json('1') }   // teto de custo: ~$2/mês
  }
}

// ─── Azure Container Registry ─────────────────────────────────────────────────

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false   // usamos managed identity
    publicNetworkAccess: 'Enabled'
  }
}

// ─── Azure Cache for Redis ────────────────────────────────────────────────────

resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: '${prefix}-redis'
  location: location
  tags: tags
  properties: {
    sku: { name: redisSku, family: 'C', capacity: redisCapacity }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    redisConfiguration: { 'maxmemory-policy': 'allkeys-lru' }
  }
}

// Formato rediss:// para TLS (porta 6380) — suportado pelo redis-py
var redisUrl = 'rediss://:${redis.listKeys().primaryKey}@${redis.properties.hostName}:6380'

// ─── Managed Identity ─────────────────────────────────────────────────────────
// Uma identity única usada por todos os Container Apps para pull de imagens no ACR.

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-identity'
  location: location
  tags: tags
}

// Role: AcrPull — permite que os Container Apps façam pull de imagens
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, 'acrpull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'   // AcrPull built-in role
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Container Apps (backend + 4 MCP servers) ────────────────────────────────

module apps 'modules/container-apps.bicep' = {
  name: 'container-apps'
  params: {
    prefix: prefix
    location: location
    tags: tags
    logAnalyticsCustomerId: law.properties.customerId
    logAnalyticsKey: law.listKeys().primarySharedKey
    acrLoginServer: acr.properties.loginServer
    identityId: identity.id
    identityClientId: identity.properties.clientId
    imageTag: imageTag
    frontendUrl: frontendUrl
    // Segredos
    anthropicApiKey: anthropicApiKey
    jwtSecret: jwtSecret
    redisUrl: redisUrl
    openaiApiKey: openaiApiKey
    elevenLabsApiKey: elevenLabsApiKey
    elevenLabsVoiceId: elevenLabsVoiceId
    zabbixUrl: zabbixUrl
    zabbixUser: zabbixUser
    zabbixPassword: zabbixPassword
    datadogApiKey: datadogApiKey
    datadogAppKey: datadogAppKey
    grafanaUrl: grafanaUrl
    grafanaToken: grafanaToken
    thousandEyesToken: thousandEyesToken
  }
  dependsOn: [acrPullRole]
}

// ─── Static Web App (Frontend React) ─────────────────────────────────────────
// O deployment do código é feito via GitHub Actions (token de deploy).
// Regiões disponíveis para SWA: eastus2, westeurope, eastasia, westus2.

resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${prefix}-frontend'
  location: 'eastus2'
  tags: tags
  sku: { name: 'Standard', tier: 'Standard' }
  properties: {
    stagingEnvironmentPolicy: 'Disabled'
    allowConfigFileUpdates: true
    buildProperties: {
      skipGithubActionWorkflowGeneration: true   // gerenciamos nosso próprio workflow
    }
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

@description('FQDN público do backend (use como VITE_BACKEND_URL no frontend).')
output backendFqdn string = apps.outputs.backendFqdn

@description('FQDN padrão do Static Web App.')
output frontendHostname string = swa.properties.defaultHostname

@description('Login server do ACR — use nos comandos docker push.')
output acrLoginServer string = acr.properties.loginServer

@description('Nome do ACR — use para az acr login.')
output acrName string = acr.name

@description('Nome do Static Web App — use para obter o token de deploy.')
output staticWebAppName string = swa.name
