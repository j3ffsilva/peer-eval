#!/bin/bash
# Interactive script to configure .env for peer-eval

echo "═══════════════════════════════════════════════════════════════"
echo "peer-eval: Configuração do GitLab"
echo "═══════════════════════════════════════════════════════════════"
echo ""

read -p "1. URL do GitLab (ex: https://git.inteli.edu.br): " GITLAB_URL
read -p "2. Project ID ou namespace/projeto (ex: 123 ou grupo/projeto): " GITLAB_PROJECT
read -p "3. Caminho absoluto do repositório clonado: " REPO_PATH
read -sp "4. Personal Access Token (será oculto): " GITLAB_TOKEN
echo ""

# Validar se o repositório existe
if [ ! -d "$REPO_PATH" ]; then
    echo "❌ Erro: Diretório $REPO_PATH não encontrado!"
    exit 1
fi

# Criar .env
cat > .env << EOF
# GitLab Configuration
GITLAB_URL=$GITLAB_URL
GITLAB_TOKEN=$GITLAB_TOKEN
GITLAB_PROJECT=$GITLAB_PROJECT
REPO_PATH=$REPO_PATH
GITLAB_SSL_VERIFY=true
EOF

echo ""
echo "✅ Arquivo .env criado com sucesso!"
echo "   Localização: $(pwd)/.env"
echo ""
echo "Próximos passos:"
echo ""
echo "1. Instale o package (se ainda não instalou):"
echo "   pip install -e ."
echo ""
echo "2. Execute a avaliação:"
echo "   peer-eval --since 2026-03-16 \\"
echo "             --until 2026-03-27 \\"
echo "             --deadline 2026-03-27T23:59:00Z"
echo ""
echo "3. Consulte --help para mais opções:"
echo "   peer-eval --help"
echo ""
