# Guia: Ambientes com Proxy Corporativo / SSL Inspection

Se você está em uma rede corporativa com inspeção SSL (muito comum em NOCs),
pode encontrar erros como:

```
SSLError: certificate verify failed: unable to get local issuer certificate
```

## Causa

Firewalls corporativos (Zscaler, Palo Alto, Forcepoint etc.) interceptam o tráfego
HTTPS e substituem os certificados dos sites por certificados internos da empresa.
Os containers Docker não confiam nesses certificados por padrão.

## Soluções aplicadas nos Dockerfiles

Os Dockerfiles já estão configurados com:

**Python/pip:**
```dockerfile
ENV PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org ...
```

**Node/npm:**
```dockerfile
ENV NODE_TLS_REJECT_UNAUTHORIZED=0
ENV NPM_CONFIG_STRICT_SSL=false
```

## Se ainda falhar: injetar certificado corporativo

### 1. Exporte o certificado raiz da sua empresa
```bash
# No Windows (PowerShell):
$cert = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -like "*NomeDaEmpresa*" }
Export-Certificate -Cert $cert -FilePath C:\corp-ca.crt -Type CERT

# No Linux/Mac:
# Abra o browser → site externo → cadeado → Exportar certificado raiz → .pem/.crt
```

### 2. Coloque o certificado na pasta docker/
```bash
cp /caminho/para/corp-ca.crt ./docker/corp-ca.crt
```

### 3. Adicione ao Dockerfile (backend e MCP servers)
```dockerfile
FROM python:3.12-slim

# Injeta certificado corporativo
COPY docker/corp-ca.crt /usr/local/share/ca-certificates/corp-ca.crt
RUN update-ca-certificates

# ... resto do Dockerfile
```

### 4. Para o frontend
```dockerfile
FROM node:20-alpine

COPY docker/corp-ca.crt /usr/local/share/ca-certificates/corp-ca.crt
RUN update-ca-certificates

ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/corp-ca.crt
# ... resto do Dockerfile
```

## Variáveis de ambiente proxy (se necessário)

Se sua rede exige proxy explícito, adicione no `.env`:
```env
HTTP_PROXY=http://proxy.empresa.com:8080
HTTPS_PROXY=http://proxy.empresa.com:8080
NO_PROXY=localhost,127.0.0.1,redis,mcp-zabbix,mcp-datadog,mcp-grafana,mcp-thousandeyes
```

E no `docker-compose.yml`, passe para os containers:
```yaml
services:
  backend:
    environment:
      - HTTP_PROXY=${HTTP_PROXY}
      - HTTPS_PROXY=${HTTPS_PROXY}
      - NO_PROXY=${NO_PROXY}
```

## Verificar se o proxy é o problema

```bash
# Teste dentro de um container Python
docker run --rm python:3.12-slim python -c "import urllib.request; print(urllib.request.urlopen('https://pypi.org').status)"

# Se retornar SSL error → problema de certificado corporativo
# Se retornar 200 → outro problema
```
