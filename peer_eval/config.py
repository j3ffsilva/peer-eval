"""
Configuration parameters for the Contribution Factor Model v4.0.
All numerical values are centralized here — no hardcoding elsewhere.
"""

# ===== Pesos de V(k) =====
W_X = 0.35  # qualidade de execução (de commits)
W_A = 0.35  # importância arquitetural (LLM por MR)
W_E = 0.30  # clareza técnica da autoria (de commits)

# ===== Pesos de R(k) — P removido =====
W_S = 0.60  # sobrevivência da contribuição
W_Q = 0.40  # qualidade CI

# ===== Fator de contribuição =====
ALPHA = 0.85  # peso do score absoluto na nota final
BETA  = 0.15  # peso do score relativo na nota final
L     = 1.225 # ponto de saturação calibrado para aluno pleno → Abs ≈ 0.775

# ===== T(k) — atribuição de contribuição =====
T_AUTHOR       = 0.70   # peso fixo para o autor do MR
T_REVIEWER_MAX = 0.30   # máximo para revisores; LLM estima dentro desse teto

# ===== Triviality gating =====
GATE_A       = 0.3   # limiar de importância arquitetural
GATE_X       = 0.2   # limiar de qualidade de execução
GATE_PENALTY = 0.1   # multiplicador quando ambos os limiares são violados

# ===== S(k) — sobrevivência da contribuição =====
S_REVERTED    = 0.0   # MR foi revertido explicitamente
S_OVERWRITTEN = 0.3   # >80% dos arquivos reescritos por outro autor em 2 semanas
S_NORMAL      = 1.0   # caso padrão

# Parâmetros calibráveis pelo professor no setup
OVERWRITE_THRESHOLD   = 0.80  # limiar de reescrita (padrão: 80%)
OVERWRITE_WINDOW_DAYS = 14    # janela de tempo (padrão: 2 semanas)

# ===== Q(k) — CI =====
Q_NO_CI             = 1.0   # sem pipeline configurado → sem penalidade
Q_GREEN_FIRST       = 1.0   # CI verde na primeira tentativa
Q_GREEN_AFTER_FIX   = 0.7   # CI verde após correções no mesmo MR
Q_FAILED_MERGED     = 0.3   # CI falhou, MR mergeado mesmo assim
Q_IGNORED_FAILURES  = 0.0   # MR ignorou falhas sistematicamente

# ===== Penalidade por direct commit =====
DIRECT_COMMIT_PENALTY_MULTIPLIER = 0.40  # W(k)_efetivo = W(k) × 0.40

# ===== LLM =====
LLM_MODEL       = "claude-sonnet-4-20250514"
LLM_TEMPERATURE = 0
LLM_MAX_TOKENS  = 1500
LLM_MAX_TOKENS_COMMIT = 800   # commits têm output menor
PROMPT_FILE     = "prompts/avaliacao_llm.md"

# ===== Filtro de commits (Stage 2.2) =====
BOT_AUTHORS = {
    "dependabot[bot]", "dependabot", "renovate[bot]", "renovate",
    "github-actions[bot]", "github-actions", "gitlab-bot",
    "semantic-release-bot",
}
MERGE_COMMIT_PATTERN = r"^merge (branch|remote|pull request|tag)"  # usar com re.IGNORECASE

# Tamanho máximo do diff enviado ao LLM por commit (caracteres)
COMMIT_DIFF_MAX_CHARS = 3000

# ===== Padrões de arquivos ignorados em diffs =====
IGNORE_PATTERNS = [
    "*.lock",
    "*.min.js",
    "*.min.css",
    "dist/*",
    "build/*",
    "*.generated.*",
    "__pycache__/*",
    "*.pyc",
]
