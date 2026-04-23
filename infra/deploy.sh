#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh — Deploy inicial da infraestrutura NOC AI Chat no Azure
#
# USO:
#   ./infra/deploy.sh [resource-group] [location] [app-name]
#
# EXEMPLO:
#   ./infra/deploy.sh noc-ai-chat-prod brazilsouth nocaichat
#
# PRÉ-REQUISITOS:
#   • az CLI instalado e autenticado (az login)
#   • Variáveis de ambiente com os secrets (veja .env.azure.example abaixo)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuração ─────────────────────────────────────────────────────────────

RESOURCE_GROUP=${1:-noc-ai-chat-prod}
LOCATION=${2:-brazilsouth}
APP_NAME=${3:-nocaichat}
ENV=prod

# Secrets — lidos de variáveis de ambiente (nunca hardcode aqui)
: "${ANTHROPIC_API_KEY:?Defina ANTHROPIC_API_KEY}"
: "${JWT_SECRET:?Defina JWT_SECRET}"

OPENAI_API_KEY=${OPENAI_API_KEY:-}
ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY:-}
ELEVENLABS_VOICE_ID=${ELEVENLABS_VOICE_ID:-}
ZABBIX_URL=${ZABBIX_URL:-}
ZABBIX_USER=${ZABBIX_USER:-}
ZABBIX_PASSWORD=${ZABBIX_PASSWORD:-}
DATADOG_API_KEY=${DATADOG_API_KEY:-}
DATADOG_APP_KEY=${DATADOG_APP_KEY:-}
GRAFANA_URL=${GRAFANA_URL:-}
GRAFANA_TOKEN=${GRAFANA_TOKEN:-}
THOUSANDEYES_TOKEN=${THOUSANDEYES_TOKEN:-}
FRONTEND_URL=${FRONTEND_URL:-}

# ── Funções ──────────────────────────────────────────────────────────────────

info()    { echo -e "\033[0;36m[INFO]\033[0m  $*"; }
success() { echo -e "\033[0;32m[OK]\033[0m    $*"; }
warn()    { echo -e "\033[0;33m[WARN]\033[0m  $*"; }
error()   { echo -e "\033[0;31m[ERR]\033[0m   $*"; exit 1; }

# ── 1. Resource Group ─────────────────────────────────────────────────────────

info "Criando resource group '$RESOURCE_GROUP' em '$LOCATION'..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --tags application=noc-ai-chat environment=$ENV managedBy=bicep \
  --output none
success "Resource group pronto."

# ── 2. Deploy da infraestrutura (Bicep) ───────────────────────────────────────

info "Executando Bicep — isso leva ~5-10 min na primeira vez..."

DEPLOYMENT_OUTPUT=$(az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$(dirname "$0")/main.bicep" \
  --parameters "$(dirname "$0")/prod.bicepparam" \
  --parameters \
    appName="$APP_NAME" \
    location="$LOCATION" \
    imageTag="initial" \
    frontendUrl="$FRONTEND_URL" \
    anthropicApiKey="$ANTHROPIC_API_KEY" \
    jwtSecret="$JWT_SECRET" \
    openaiApiKey="$OPENAI_API_KEY" \
    elevenLabsApiKey="$ELEVENLABS_API_KEY" \
    elevenLabsVoiceId="$ELEVENLABS_VOICE_ID" \
    zabbixUrl="$ZABBIX_URL" \
    zabbixUser="$ZABBIX_USER" \
    zabbixPassword="$ZABBIX_PASSWORD" \
    datadogApiKey="$DATADOG_API_KEY" \
    datadogAppKey="$DATADOG_APP_KEY" \
    grafanaUrl="$GRAFANA_URL" \
    grafanaToken="$GRAFANA_TOKEN" \
    thousandEyesToken="$THOUSANDEYES_TOKEN" \
  --output json)

success "Infraestrutura criada."

# ── 3. Extrair outputs ────────────────────────────────────────────────────────

get_output() {
  echo "$DEPLOYMENT_OUTPUT" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d['properties']['outputs']['$1']['value'])"
}

BACKEND_FQDN=$(get_output backendFqdn)
ACR_LOGIN_SERVER=$(get_output acrLoginServer)
ACR_NAME=$(get_output acrName)
SWA_NAME=$(get_output staticWebAppName)
FRONTEND_HOSTNAME=$(get_output frontendHostname)

# ── 4. Build e push das imagens Docker ───────────────────────────────────────

info "Fazendo login no ACR '$ACR_NAME'..."
az acr login --name "$ACR_NAME"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

push_image() {
  local context="$1"
  local image_name="$2"
  info "Build e push: $image_name..."
  docker build -t "$ACR_LOGIN_SERVER/$image_name:latest" "$context" --quiet
  docker push "$ACR_LOGIN_SERVER/$image_name:latest" --quiet
  success "$image_name enviado."
}

push_image "$PROJECT_ROOT/backend"                         "backend"
push_image "$PROJECT_ROOT/mcp-servers/zabbix"             "mcp-zabbix"
push_image "$PROJECT_ROOT/mcp-servers/datadog"            "mcp-datadog"
push_image "$PROJECT_ROOT/mcp-servers/grafana"            "mcp-grafana"
push_image "$PROJECT_ROOT/mcp-servers/thousandeyes"       "mcp-thousandeyes"

# ── 5. Atualizar Container Apps com a imagem real ────────────────────────────

info "Atualizando Container Apps com imagem 'latest'..."
for app in backend mcp-zabbix mcp-datadog mcp-grafana mcp-thousandeyes; do
  az containerapp update \
    --name "${APP_NAME}-${ENV}-${app}" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/$app:latest" \
    --output none
done
success "Container Apps atualizados."

# ── 6. Token do Static Web App para o frontend ───────────────────────────────

SWA_TOKEN=$(az staticwebapp secrets list \
  --name "$SWA_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.apiKey" \
  --output tsv)

# ── 7. Build e deploy do frontend ────────────────────────────────────────────

info "Build do frontend com VITE_BACKEND_URL=https://$BACKEND_FQDN..."
cd "$PROJECT_ROOT/frontend"
VITE_BACKEND_URL="https://$BACKEND_FQDN" npm run build

info "Deploy do frontend no Static Web App..."
npx @azure/static-web-apps-cli deploy ./dist \
  --deployment-token "$SWA_TOKEN" \
  --env production

# ── 8. Resumo ─────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════════════"
success "Deploy concluído!"
echo ""
echo "  Backend:   https://$BACKEND_FQDN"
echo "  Frontend:  https://$FRONTEND_HOSTNAME"
echo "  ACR:       $ACR_LOGIN_SERVER"
echo ""
warn "PRÓXIMO PASSO: Copie a URL do frontend e configure no prod.bicepparam:"
warn "  param frontendUrl = 'https://$FRONTEND_HOSTNAME'"
warn "Depois execute o pipeline novamente para ajustar o CORS."
echo "════════════════════════════════════════════════════════════"
