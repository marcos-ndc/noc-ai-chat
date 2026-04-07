#!/usr/bin/env bash
# =============================================================================
# fix-docker-credentials.sh
# Corrige erro "error getting credentials" no Docker em ambientes corporativos
# =============================================================================
set -e

CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RESET='\033[0m'

echo -e "${CYAN}Corrigindo configuração de credenciais do Docker...${RESET}"
echo ""

# Localizar docker config
DOCKER_CONFIG="${HOME}/.docker/config.json"

if [ ! -f "$DOCKER_CONFIG" ]; then
    mkdir -p "${HOME}/.docker"
    echo '{}' > "$DOCKER_CONFIG"
fi

# Verificar se o problema é credHelper inválido
if grep -q '"credsStore"' "$DOCKER_CONFIG" 2>/dev/null; then
    echo -e "${YELLOW}Problema detectado: credsStore configurado mas helper não disponível${RESET}"
    echo ""
    echo "Opção 1 (recomendada) — remover o credsStore problemático:"
    echo "  python3 -c \""
    echo "    import json; c=json.load(open('$DOCKER_CONFIG'));"
    echo "    c.pop('credsStore',None); c.pop('credHelpers',None);"
    echo "    json.dump(c,open('$DOCKER_CONFIG','w'))\""
    echo ""
    echo "Opção 2 — fazer login no Docker Hub:"
    echo "  docker login"
    echo ""
    read -p "Aplicar Opção 1 automaticamente? (s/N) " choice
    if [[ "$choice" == "s" || "$choice" == "S" ]]; then
        python3 -c "
import json
with open('$DOCKER_CONFIG') as f:
    c = json.load(f)
c.pop('credsStore', None)
c.pop('credHelpers', None)
with open('$DOCKER_CONFIG', 'w') as f:
    json.dump(c, f, indent=2)
print('credsStore removido com sucesso')
"
        echo -e "${GREEN}✅ Configuração corrigida!${RESET}"
    fi
else
    echo -e "${YELLOW}credsStore não encontrado no config.json${RESET}"
    echo ""
    echo "Tente fazer login no Docker Hub:"
    echo "  docker login"
    echo ""
    echo "Ou puxe a imagem node manualmente:"
    echo "  docker pull node:20-alpine"
fi

echo ""
echo "Após corrigir, rode novamente:"
echo "  make dev"
