// Arquivo de parâmetros — apenas valores NÃO SENSÍVEIS.
// Segredos (API keys, senhas) são passados pelo pipeline via --parameters key=value.
// Nunca adicione secrets aqui. Este arquivo é versionado no Git.

using './main.bicep'

// ── Identificação ──────────────────────────────────────────────────────────────
param appName  = 'nocaichat'
param env      = 'prod'
param location = 'brazilsouth'   // Altere se preferir eastus2 ou westeurope

// ── Redis ──────────────────────────────────────────────────────────────────────
// Basic  = sem HA, 1 GB, ~$55/mês  → OK para NOC interno
// Standard = com HA (réplica), 1 GB, ~$110/mês → recomendado se downtime é crítico
param redisSku      = 'Basic'
param redisCapacity = 1

// ── Frontend URL ───────────────────────────────────────────────────────────────
// Deixe em branco no 1º deploy. Após obter o hostname do Static Web App,
// preencha e re-execute o pipeline para configurar CORS corretamente.
// Exemplo: 'https://blue-sand-0a1b2c3d4.azurestaticapps.net'
param frontendUrl = ''

// ── imageTag é passado dinamicamente pelo pipeline (github.sha) ──────────────
// Não defina aqui — o workflow injeta o valor correto.
