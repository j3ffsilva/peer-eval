#!/bin/bash
# Script para coletar informações do GitLab e criar .env

echo "═══════════════════════════════════════════════════════════════"
echo "Configuração do Ciclo 2 — Coleta Real do GitLab"
echo "═══════════════════════════════════════════════════════════════"
echo ""

read -p "1. URL do GitLab self-hosted (ex: https://gitlab.seu-dominio.edu.br): " GITLAB_URL
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
# GitLab Self-Hosted Configuration
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
echo "Próximo passo: execute o comando"
echo ""
echo "python main.py \\"
echo "  --since 2026-03-16 \\"
echo "  --until 2026-03-27 \\"
echo "  --members catarina celso leonardo gabriel henrique rafael \\"
echo "  --deadline 2026-03-27T23:59:00Z \\"
echo "  --skip-llm \\"
echo "  --output-dir output/"
echo ""
