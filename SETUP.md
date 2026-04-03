# 🚀 Setup Completo - Ambiente Virtual

## ✅ Checklist de Configuração

- [x] **Ambiente virtual criado** (`venv/`)
- [x] **Dependências instaladas** (via `requirements.txt`)
- [x] **Todos os 61 testes passando** ✓
- [x] **Projeto funcionando end-to-end** ✓
- [x] **Documentação** (README.md, SETUP.md)

---

## 📋 Como Usar o VirtualEnv

### Ativar (Recomendado: Use o Script)

```bash
# Opção 1: Script rápido (Linux/macOS)
./activate.sh

# Opção 2: Ativação manual (Linux/macOS)
source venv/bin/activate

# Opção 3: Ativação manual (Windows)
venv\Scripts\activate
```

### Verificar que está ativo

Se viu `(venv)` no seu prompt, está ativado! ✓

```bash
(venv) $ which python
/home/jeff/Documentos/dev/peer-eval/venv/bin/python

(venv) $ python --version
Python 3.8.18
```

### Desativar

```bash
deactivate
```

---

## 🧪 Rodar Testes

```bash
# Todos os testes
pytest tests/ -v

# Com cobertura
pytest tests/ -v --cov=. --cov-report=html

# Teste específico
pytest tests/test_model.py::TestSat::test_sat_tau -v
```

**Resultado esperado:**
```
============================== 61 passed in 0.05s ==============================
```

---

## 🎯 Exemplo Completo

```bash
# 1. Ativar venv
source venv/bin/activate

# 2. Rodar projeto
python main.py \
  --fixture fixtures/mr_artifacts.json \
  --members ana bruno carla diego \
  --deadline 2024-11-29T23:59:00Z \
  --output-dir output

# 3. Saída esperada
# ┌─────────────────────────────────────────────┐
# │  RESULTADO — Modelo de Contribuição v3.0    │
# ├──────────┬───────┬───────┬───────┬──────────┤
# │  Aluno   │  S(p) │  Abs  │  Rel  │  Nota    │
# ├──────────┼───────┼───────┼───────┼──────────┤
# │ ana      │  1.07 │  1.00 │  1.00 │  100.0%  │
# │ carla    │  0.90 │  1.00 │  0.84 │   97.6%  │
# │ bruno    │  0.87 │  1.00 │  0.82 │   97.3%  │
# │ diego    │  0.49 │  1.00 │  0.46 │   91.9%  │
# └──────────┴───────┴───────┴───────┴──────────┘
```

---

## 📦 Dependências Instaladas

### Versões Principais

| Pacote | Versão | Uso |
|--------|--------|-----|
| **anthropic** | 0.72.0 | API Anthropic Claude |
| **python-gitlab** | 4.13.0 | Cliente GitLab API |
| **pytest** | 8.3.5 | Framework de testes |
| **pytest-cov** | 5.0.0 | Cobertura de testes |
| **black** | 24.8.0 | Formatador de código |
| **flake8** | 7.1.2 | Linter |
| **mypy** | 1.14.1 | Type checker |

---

## 🛠️ Ferramentas de Desenvolvimento

### Formatar Código

```bash
black *.py tests/
```

### Linting

```bash
flake8 *.py tests/
```

### Type Checking

```bash
mypy *.py --ignore-missing-imports
```

---

## 📁 Estrutura de Diretórios

```
peer-eval/
├── venv/                      ← Ambiente isolado (não fazer git add!)
├── fixtures/
│   └── mr_artifacts.json      ← Dados de teste
├── output/                    ← Relatórios gerados
├── prompts/
│   └── avaliacao_llm.md       ← System prompts
├── tests/
│   ├── test_model.py          ← 41 testes
│   ├── test_loader.py         ← 9 testes
│   └── test_scorer.py         ← 11 testes (total: 61 testes)
├── *.py                       ← Módulos principais
├── requirements.txt           ← Dependências
├── README.md                  ← Documentação
├── SETUP.md                   ← Este arquivo
├── activate.sh                ← Script de ativação rápida
└── .gitignore                 ← Configuração Git
```

---

## ⚠️ Dicas Importantes

1. **Sempre ative o venv antes de trabalhar**
   ```bash
   source venv/bin/activate  # ou: ./activate.sh
   ```

2. **Não committe o venv no Git** (`.gitignore` já está configurado)

3. **Se adicionar novas dependências**, atualize `requirements.txt`:
   ```bash
   pip freeze > requirements.txt
   ```

4. **Testes sempre passam?** 
   ```bash
   pytest tests/ -v  # 61 testes devem passar
   ```

---

## 🔄 Atualizar Dependências

Se precisar atualizar as dependências:

```bash
source venv/bin/activate
pip install -U pip setuptools wheel
pip install -r requirements.txt --upgrade
```

---

## ✨ Ready to Go!

O projeto está 100% configurado e pronto para uso. Basta ativar o venv e começar a trabalhar!

```bash
./activate.sh
python main.py --help
```

Boa sorte! 🎉
