# Ciclo 2 — Configuração para Coleta Real do GitLab

## 📋 Pré-requisitos

- ✅ GitLab self-hosted configurado (URL conhecida)
- ✅ Repositório clonado localmente
- ✅ Personal Access Token criado no GitLab

---

## 🔑 Criar Personal Access Token no GitLab

1. Acesse: `{SUA_URL_GITLAB}/-/user_settings/personal_access_tokens`
2. Clique em **"Add new token"**
3. Preencha:
   - **Token name**: `peer-eval-collector` (ou qualquer nome)
   - **Expiration date**: Escolha uma data futura
   - **Scopes**: Marque apenas `api`
4. Clique em **"Create personal access token"**
5. **Copie o token** (só aparece uma vez!)

---

## ⚙️ Configurar `.env`

### Opção A: Script automático (recomendado)

```bash
bash setup_env.sh
```

O script perguntará:
1. URL do GitLab
2. Project ID
3. Caminho do repositório
4. Token (input oculto)

Depois cria o `.env` automaticamente.

### Opção B: Editar manualmente

```bash
# Copiar template
cp .env.example .env

# Editar com seu editor favorito
nano .env
# ou
vim .env
```

Preencha com seus valores:
```dotenv
GITLAB_URL=https://seu-gitlab.seu-dominio.edu.br
GITLAB_TOKEN=glpat-sua-token-aqui
GITLAB_PROJECT=seu-namespace/seu-projeto
REPO_PATH=/caminho/absoluto/local/do/repo
GITLAB_SSL_VERIFY=true
```

---

## 🧪 Testar a Conexão

```bash
# Verificar se o .env está correto
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

print('GITLAB_URL:', os.getenv('GITLAB_URL'))
print('GITLAB_PROJECT:', os.getenv('GITLAB_PROJECT'))
print('REPO_PATH:', os.getenv('REPO_PATH'))
print('Token:', '***' if os.getenv('GITLAB_TOKEN') else 'AUSENTE')
"
```

---

## 🚀 Executar a Coleta

```bash
python main.py \
  --since 2026-03-16 \
  --until 2026-03-27 \
  --members catarina celso leonardo gabriel henrique rafael \
  --deadline 2026-03-27T23:59:00Z \
  --skip-llm \
  --output-dir output/
```

Isso vai:
1. ✅ Carregar credenciais do `.env`
2. ✅ Conectar ao GitLab
3. ✅ Buscar MRs merged no período
4. ✅ Enriched com git blame, reviews, etc
5. ✅ Salvar em `output/mr_artifacts.json`
6. ✅ Gerar relatório de scores

---

## 🔍 Saída Esperada

```
======================================================================
Stage 0: Collecting artifacts from GitLab
======================================================================
Collecting from https://seu-gitlab.seu-dominio.edu.br/seu-namespace/seu-projeto
  Period: 2026-03-16 to 2026-03-27
  Repo: /caminho/local/repo
======================================================================
✓ GitLab authentication successful
✓ Project loaded: seu-namespace / seu-projeto
Found 5 merged MRs in period
  Processing MR-42: feat: add payment flow
    X=0.521 S=0.950 Q=1.0
  Processing MR-43: fix: correct tax calculation
    X=0.312 S=0.900 Q=1.0
  ...
Saved 5 artifacts to output/mr_artifacts.json
```

---

## ⚠️ Troubleshooting

| Erro | Solução |
|------|---------|
| `SSL: CERTIFICATE_VERIFY_FAILED` | Use `GITLAB_SSL_VERIFY=false` no `.env` ou `--no-ssl-verify` |
| `401 Unauthorized` | Token inválido ou expirado — crie novo |
| `404 Project not found` | Project ID incorreto — use formato `namespace/projeto` |
| `Repository not found` | REPO_PATH incorreto ou repositório não clonado |

---

## 📝 Próximos Passos

Após gerar os artefatos com sucesso:

1. **Ciclo 3**: Chamar LLM para estimar E, A, T_review, P
2. **Stage 3**: Calcular scores finais por membro
3. **Stage 4**: Gerar relatórios (HTML, JSON, texto)

Você quer ajuda com isso?
