"""
Configuration parameters for the Contribution Factor Model v3.0.
All numerical values are centralized here — no hardcoding elsewhere.
"""

import math

# ===== Saturation parameters =====
TAU_LINES = 100
TAU_FILES = 10
TAU_MODULES = 5

# ===== Weights for V(k) =====
W_X = 0.35  # quantitative component weight
W_A = 0.35  # architectural weight
W_E = 0.30  # effort/authenticity weight

# ===== Weights for R(k) =====
W_S = 0.50  # survival weight
W_P = 0.30  # potential weight
W_Q = 0.20  # quality (CI) weight

# ===== Final grade calculation =====
ALPHA = 0.85  # weight for absolute score in final grade
BETA = 0.15   # weight for relative score in final grade
L = 0.360     # normalization factor for absolute score

# ===== Triviality gating =====
GATE_A = 0.3      # threshold for architecture weight
GATE_X = 0.2      # threshold for quantitative score
GATE_PENALTY = 0.1  # penalty multiplier when gating is triggered

# ===== T(k) attribution weights =====
T_AUTHOR = 0.7         # weight for author contribution
T_REVIEWER_MAX = 0.30  # maximum weight for reviewer; LLM adjusts; fallback uses fixed value

# ===== LLM configuration (for future cycles) =====
LLM_MODEL = "claude-sonnet-4-20250514"
LLM_TEMPERATURE = 0
LLM_MAX_TOKENS = 1500
PROMPT_FILE = "prompts/avaliacao_llm.md"

# ===== File patterns to ignore in diffs =====
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

# ===== Module weight mapping =====
# Hint for LLM; fallback heuristic for A(k)
MODULE_WEIGHTS = {
    "core": 1.0,
    "domain": 1.0,
    "auth": 0.9,
    "api": 0.8,
    "services": 0.7,
    "tests": 0.7,
    "infra": 0.6,
    "config": 0.4,
    "docs": 0.2,
}

# ===== Conventional commit type signals =====
# Hint for LLM; fallback heuristic for E(k)
COMMIT_SIGNALS = {
    "feat": 0.3,
    "fix": 0.4,
    "refactor": 0.3,
    "test": 0.2,
    "ci": 0.2,
    "docs": 0.1,
    "unknown": 0.25,  # neutral — absent data, not a mistake by the student
}

E_BONUS_CI = 0.2      # bonus for passing CI
E_BONUS_ISSUE = 0.4   # bonus for closing an issue
