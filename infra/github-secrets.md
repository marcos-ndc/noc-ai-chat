# Secrets e variáveis necessários no GitHub

Configure em: **Settings → Secrets and variables → Actions**

---

## Secrets (Settings → Secrets)

| Nome | Descrição | Obrigatório |
|------|-----------|-------------|
| `AZURE_CLIENT_ID` | Client ID do Service Principal (OIDC) | ✅ |
| `AZURE_TENANT_ID` | Tenant ID do Azure AD | ✅ |
| `AZURE_SUBSCRIPTION_ID` | ID da subscription Azure | ✅ |
| `ANTHROPIC_API_KEY` | Chave da API Anthropic (`sk-ant-...`) | ✅ |
| `JWT_SECRET` | String aleatória ≥32 chars para assinar JWTs | ✅ |
| `OPENAI_API_KEY` | Chave OpenAI — para TTS e Whisper STT | ⭕ |
| `ELEVENLABS_API_KEY` | Chave ElevenLabs — voz pt-BR nativa | ⭕ |
| `ELEVENLABS_VOICE_ID` | Voice ID da voz ElevenLabs selecionada | ⭕ |
| `ZABBIX_URL` | URL da API Zabbix (`https://zabbix.empresa.com/api_jsonrpc.php`) | ⭕ |
| `ZABBIX_USER` | Usuário da API Zabbix | ⭕ |
| `ZABBIX_PASSWORD` | Senha da API Zabbix | ⭕ |
| `DATADOG_API_KEY` | Datadog API Key | ⭕ |
| `DATADOG_APP_KEY` | Datadog Application Key | ⭕ |
| `GRAFANA_URL` | URL do Grafana (`https://grafana.empresa.com`) | ⭕ |
| `GRAFANA_TOKEN` | Token de API do Grafana | ⭕ |
| `THOUSANDEYES_TOKEN` | Bearer Token do ThousandEyes | ⭕ |

---

## Variables (Settings → Variables)

| Nome | Descrição | Exemplo |
|------|-----------|---------|
| `AZURE_RESOURCE_GROUP` | Nome do resource group no Azure | `noc-ai-chat-prod` |
| `APP_NAME` | Prefixo dos recursos (sem hífens para ACR) | `nocaichat` |
| `FRONTEND_URL` | URL do SWA após 1º deploy (para CORS) | `https://blue-sand-0a1b2c3d4.azurestaticapps.net` |

> **FRONTEND_URL** fica vazio no 1º deploy. Após obter o hostname do Static Web App,
> configure aqui e o pipeline seguinte ajustará o CORS automaticamente.

---

## Configurar Service Principal com OIDC (sem senha de longa duração)

```bash
# 1. Criar Service Principal
az ad app create --display-name "noc-ai-chat-github"

# 2. Anotar o appId (CLIENT_ID)
APP_ID=$(az ad app list --display-name "noc-ai-chat-github" --query "[0].appId" -o tsv)

# 3. Criar Service Principal
az ad sp create --id "$APP_ID"
SP_ID=$(az ad sp show --id "$APP_ID" --query "id" -o tsv)

# 4. Atribuir permissão de Contributor no resource group
az role assignment create \
  --assignee "$APP_ID" \
  --role Contributor \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/noc-ai-chat-prod"

# 5. Configurar OIDC federated credential para o GitHub
az ad app federated-credential create \
  --id "$APP_ID" \
  --parameters '{
    "name": "github-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:SUA_ORG/noc-ai-chat:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# 6. Adicionar os secrets no GitHub:
#   AZURE_CLIENT_ID      = $APP_ID
#   AZURE_TENANT_ID      = $(az account show --query tenantId -o tsv)
#   AZURE_SUBSCRIPTION_ID = $(az account show --query id -o tsv)
```
