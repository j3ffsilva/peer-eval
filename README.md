# Contribution Factor Model v3.0

## ✨ Setup - Ambiente Virtual

### 1. Criar e Ativar o Ambiente Virtual

O projeto inclui um ambiente virtual pré-configurado chamado `venv`. Para começar:

**No Linux/macOS:**
```bash
source venv/bin/activate
```

**No Windows:**
```bash
venv\Scripts\activate
```

Você saberá que o ambiente está ativo quando vir `(venv)` no inicio do seu prompt.

### 2. Instalar Dependências (se necessário)

Se o venv foi recém-criado ou você precisa atualizar:

```bash
pip install -U pip setuptools wheel
pip install -r requirements.txt
```

### 3. Rodar o Projeto

```bash
python main.py --fixture fixtures/mr_artifacts.json \
               --members ana bruno carla diego \
               --deadline 2024-11-29T23:59:00Z \
               --output-dir output
```

### 4. Rodar os Testes

```bash
pytest tests/ -v
```

Com cobertura:
```bash
pytest tests/ -v --cov=. --cov-report=html
```

---

## 📁 Estrutura do Projeto

```
peer-eval/
├── venv/                       # Ambiente virtual (não committar no Git)
├── fixtures/
│   └── mr_artifacts.json       # Dados de teste com 8 MRs
├── output/                     # Relatórios gerados
│   ├── mr_llm_estimates.json   # Estimativas LLM
│   ├── group_report.json       # Análise de padrões
│   └── full_report.json        # Relatório completo
├── prompts/
│   └── avaliacao_llm.md        # System prompts para LLM
├── tests/
│   ├── test_model.py           # Testes do modelo
│   ├── test_loader.py          # Testes de I/O
│   └── test_scorer.py          # Testes de scoring
├── config.py                   # Configuração centralizada
├── exceptions.py               # Exceções customizadas
├── model.py                    # Cálculos puros
├── loader.py                   # Operações de arquivo
├── scorer.py                   # Agregação de scores
├── llm_stage2a.py              # Avaliação por MR
├── llm_stage2b.py              # Detecção de padrões
├── report.py                   # Formatação de saída
├── main.py                     # Orquestração principal
├── requirements.txt            # Dependências
└── README.md                   # Este arquivo
```

---

## 🚀 Uso do CLI

```bash
python main.py [OPTIONS]

OPTIONS:
  --fixture PATH                Caminho para mr_artifacts.json (obrigatório)
  --members NAMES               Lista de nomes dos membros (obrigatório)
  --deadline ISO8601            Data limite do projeto (obrigatório)
  --llm-estimates PATH          Caminho para estimativas pré-computadas (opcional)
  --overrides PATH              Caminho para overrides do professor (opcional)
  --output-dir DIR              Diretório de saída (padrão: output)
  --skip-stage2b                Pular detecção de padrões (opcional)
  --direct-committers NAMES     Membros com commits diretos (opcional)
```

---

## 📊 Exemplo de Saída

```
┌─────────────────────────────────────────────┐
│  RESULTADO — Modelo de Contribuição v3.0    │
├──────────┬───────┬───────┬───────┬──────────┤
│  Aluno   │  S(p) │  Abs  │  Rel  │  Nota    │
├──────────┼───────┼───────┼───────┼──────────┤
│ ana      │  1.07 │  1.00 │  1.00 │  100.0%  │
│ carla    │  0.90 │  1.00 │  0.84 │   97.6%  │
│ bruno    │  0.87 │  1.00 │  0.82 │   97.3%  │
│ diego    │  0.49 │  1.00 │  0.46 │   91.9%  │
└──────────┴───────┴───────┴───────┴──────────┘

⚠️  ALERTAS DETECTADOS:

🟡 BURST_DE_VESPERA - carla
   MRs: MR-5, MR-6
   Evidência: 2 of 2 MRs em últimos 3 dias
   Alternativa legítima: Planejamento pobre ou sprint final legítimo
```

---

## 📦 Dependências

### Principais
- **anthropic**: API Anthropic Claude (para ciclo 2+)
- **python-gitlab**: Cliente GitLab API (para ciclo 2+)

### Testes
- **pytest**: Framework de testes
- **pytest-cov**: Plugin de cobertura

### Desenvolvimento
- **black**: Formatador de código
- **flake8**: Linter
- **mypy**: Type checker

---

## 🛠️ Desenvolvimento com Black e Flake8

Formatar código:
```bash
black *.py tests/
```

Verificar linting:
```bash
flake8 *.py tests/
```

Type checking:
```bash
mypy *.py --ignore-missing-imports
```

---

## 📝 Notas

- **Ciclo 1**: Funciona com fixtures JSON
- **Ciclo 2+**: Integrará com APIs reais (Anthropic, GitLab)
- Porta Python: 3.8+
- Todos os valores numéricos estão centralizados em `config.py`
