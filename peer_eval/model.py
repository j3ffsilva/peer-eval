"""
Core calculation functions for the Contribution Factor Model v4.0.
All functions are pure (no I/O, no side effects, 100% testable).

Novo modelo:
  X(k) = média(atomicity(c) × scope_clarity(c))  — de commits
  E(k) = média(message_quality(c))               — de commits
  A(k) ∈ [0,1]                                   — LLM por MR
  V(k) = 0.35·X + 0.35·A + 0.30·E
  S(k) ∈ {0.0, 0.3, 1.0}                        — sobrevivência
  Q(k) ∈ {0.0, 0.3, 0.7, 1.0}                   — CI
  R(k) = 0.60·S + 0.40·Q
  W(k) = V(k) × R(k)  [com gating por trivialidade]
"""

import math
import re
from typing import Optional, List, Dict
from . import config


# ═══════════════════════════════════════════════════════════════════════════
# Funções utilitárias (mantidas para compatibilidade)
# ═══════════════════════════════════════════════════════════════════════════


def sat(x: float, tau: float) -> float:
    """
    Saturation function: sat(x, τ) = 1 - exp(-x / τ)

    Mantida para compatibilidade e uso potencial em extensões.
    No modelo v4.0, X(k) vem de commits, não desta função.
    """
    if tau <= 0:
        raise ValueError("tau must be positive")
    return 1.0 - math.exp(-x / tau)


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2.2 — Métricas determinísticas de commit
# ═══════════════════════════════════════════════════════════════════════════

_VALID_PREFIXES = frozenset({
    "feat", "fix", "test", "chore", "refactor",
    "docs", "style", "perf", "ci", "build", "revert",
})

_DEGENERATE_MESSAGES = frozenset({
    "fix", "wip", "update", "commit", "temp", "ok", "done",
    "changes", "asdfgh", "test", "minor", "stuff", "misc",
    "a", ".", "-", "...",
})


def calc_message_syntax(message: str) -> float:
    """
    Avalia a sintaxe da mensagem de commit deterministicamente.

    Critérios (cada um é binário):
      +0.4  tem prefixo conventional commits válido
      +0.2  tem escopo definido (feat(payment): ...)
      +0.2  mensagem tem comprimento adequado (> 20 chars na primeira linha)
      +0.2  não é mensagem degenerada

    Exemplos:
      "feat(auth): add JWT expiration validation"   → 1.0
      "feat: add validation"                        → 0.6
      "fix"                                         → 0.0

    Args:
        message: Mensagem de commit completa

    Returns:
        Score de sintaxe em [0, 1]
    """
    first_line = message.strip().split("\n")[0].strip()

    if first_line.lower() in _DEGENERATE_MESSAGES:
        return 0.0

    score = 0.0

    # Verifica prefixo conventional commits
    prefix_match = re.match(r"^(\w+)(\([^)]+\))?!?:", first_line.lower())
    if prefix_match:
        prefix = prefix_match.group(1)
        has_scope = prefix_match.group(2) is not None

        if prefix in _VALID_PREFIXES:
            score += 0.4
            if has_scope:
                score += 0.2

    # Comprimento adequado (> 20 chars na primeira linha)
    if len(first_line) > 20:
        score += 0.2

    # Conteúdo não trivial após o prefixo
    if prefix_match and prefix_match.group(1) in _VALID_PREFIXES:
        description = first_line[prefix_match.end():].strip()
        if len(description) > 10:
            score += 0.2
    elif not prefix_match and len(first_line) > 10:
        score += 0.2

    return min(1.0, score)


# ═══════════════════════════════════════════════════════════════════════════
# Agregação de métricas de commit → nível de MR
# ═══════════════════════════════════════════════════════════════════════════


def calc_x_from_commits(commit_estimates: List[Dict]) -> float:
    """
    Calcula X(k) a partir das estimativas de commits do MR.

    X(k) = média( atomicity(c) × scope_clarity(c) )

    Semântica: "o trabalho foi bem executado e delimitado em nível de commits?"

    Args:
        commit_estimates: Lista de estimativas de commits (não filtrados)
                          Cada item deve ter "atomicity" e "scope_clarity" em [0,1]

    Returns:
        X(k) em [0, 1]; retorna 0.5 se lista vazia (neutro)
    """
    if not commit_estimates:
        return 0.5

    products = [
        c.get("atomicity", 0.5) * c.get("scope_clarity", 0.5)
        for c in commit_estimates
    ]
    return sum(products) / len(products)


def calc_e_from_commits(commit_estimates: List[Dict]) -> float:
    """
    Calcula E(k) a partir das estimativas de commits do MR.

    E(k) = média( message_quality(c) )
    onde message_quality(c) = 0.5·message_syntax(c) + 0.5·message_semantic(c)

    Semântica: "os commits comunicam com clareza o que foi feito e por quê?"

    Args:
        commit_estimates: Lista de estimativas de commits (não filtrados)
                          Cada item deve ter "message_quality" em [0,1]

    Returns:
        E(k) em [0, 1]; retorna 0.5 se lista vazia (neutro)
    """
    if not commit_estimates:
        return 0.5

    qualities = [c.get("message_quality", 0.5) for c in commit_estimates]
    return sum(qualities) / len(qualities)


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2.3 — Métricas determinísticas de MR
# ═══════════════════════════════════════════════════════════════════════════


def calc_s(reverted: bool = False, overwritten_ratio: float = 0.0) -> float:
    """
    Calcula S(k) — sobrevivência da contribuição.

    S(k) = 0.0  MR foi revertido explicitamente
    S(k) = 0.3  arquivos do MR foram reescritos em >80% por outro autor
    S(k) = 1.0  caso contrário (padrão)

    Args:
        reverted: True se o MR foi revertido
        overwritten_ratio: Fração dos arquivos do MR reescritos por outro autor

    Returns:
        S(k) ∈ {0.0, 0.3, 1.0}
    """
    if reverted:
        return config.S_REVERTED
    if overwritten_ratio > config.OVERWRITE_THRESHOLD:
        return config.S_OVERWRITTEN
    return config.S_NORMAL


def calc_q(
    ci_configured: bool = False,
    ci_passed: bool = True,
    ci_attempts: int = 1
) -> float:
    """
    Calcula Q(k) — qualidade CI.

    Q(k) = 1.0  sem pipeline configurado (sem penalidade)
    Q(k) = 1.0  CI verde na primeira tentativa
    Q(k) = 0.7  CI verde após correções no mesmo MR
    Q(k) = 0.3  CI falhou, MR mergeado mesmo assim
    Q(k) = 0.0  MR ignorou falhas sistematicamente

    Args:
        ci_configured: True se o projeto tem CI configurado
        ci_passed: True se o CI passou
        ci_attempts: Número de tentativas até passar (1 = primeira tentativa)

    Returns:
        Q(k) ∈ {0.0, 0.3, 0.7, 1.0}
    """
    if not ci_configured:
        return config.Q_NO_CI
    if ci_passed and ci_attempts == 1:
        return config.Q_GREEN_FIRST
    if ci_passed and ci_attempts > 1:
        return config.Q_GREEN_AFTER_FIX
    if not ci_passed:
        return config.Q_FAILED_MERGED
    return config.Q_NO_CI


# ═══════════════════════════════════════════════════════════════════════════
# Cálculo de componentes V, R, W
# ═══════════════════════════════════════════════════════════════════════════


def calc_v(X: float, A: float, E: float) -> float:
    """
    Calcula V(k) — valor técnico.

    V(k) = 0.35·X(k) + 0.35·A(k) + 0.30·E(k)

    Args:
        X: Qualidade de execução (de commits)
        A: Importância arquitetural (LLM)
        E: Clareza técnica da autoria (de commits)

    Returns:
        V(k) em [0, 1]
    """
    return config.W_X * X + config.W_A * A + config.W_E * E


def calc_r(S: float, Q: float) -> float:
    """
    Calcula R(k) — qualidade da entrega.

    R(k) = 0.60·S(k) + 0.40·Q(k)

    Args:
        S: Sobrevivência da contribuição
        Q: Qualidade CI

    Returns:
        R(k) em [0, 1]
    """
    return config.W_S * S + config.W_Q * Q


def calc_w(V: float, R: float, A: float, X: float) -> float:
    """
    Calcula W(k) — peso final do MR, com gating por trivialidade.

    Base:   W(k) = V(k) × R(k)
    Gating: se A(k) < GATE_A E X(k) < GATE_X → W(k) *= GATE_PENALTY

    Args:
        V: Valor técnico
        R: Qualidade da entrega
        A: Importância arquitetural
        X: Qualidade de execução

    Returns:
        W(k) em [0, 1]
    """
    W = V * R
    if A < config.GATE_A and X < config.GATE_X:
        W *= config.GATE_PENALTY
    return W


# ═══════════════════════════════════════════════════════════════════════════
# Heurísticas de fallback (mantidas para degradação graciosa)
# ═══════════════════════════════════════════════════════════════════════════


def calc_a_heuristic(module_paths: List[str]) -> float:
    """
    Fallback heurístico para A(k) quando LLM não está disponível.

    Extrai o módulo raiz de cada caminho e calcula a média dos pesos.
    Para módulos não mapeados, usa 0.5 como neutro.

    Args:
        module_paths: Lista de caminhos de arquivos

    Returns:
        A(k) em [0, 1]
    """
    _MODULE_WEIGHTS = {
        "core": 1.0, "domain": 1.0, "auth": 0.9, "api": 0.8,
        "services": 0.7, "tests": 0.7, "infra": 0.6,
        "config": 0.4, "docs": 0.2,
    }
    if not module_paths:
        return 0.5
    weights = []
    for path in module_paths:
        parts = path.split("/")
        root_module = parts[0].split(".")[0]
        weights.append(_MODULE_WEIGHTS.get(root_module, 0.5))
    return sum(weights) / len(weights)


def calc_e_heuristic(
    type_declared: str,
    ci_green: bool,
    closes_issue: bool
) -> float:
    """
    Fallback heurístico para E(k) quando commits não estão disponíveis.

    Usa o tipo do commit, CI e fechamento de issue como proxy.
    No modelo v4.0 E vem de commits; este fallback é usado em modo legado.

    Args:
        type_declared: Tipo declarado do commit (feat, fix, ...)
        ci_green: CI passou
        closes_issue: MR fecha uma issue

    Returns:
        E(k) em [0, 1]
    """
    _COMMIT_SIGNALS = {
        "feat": 0.3, "fix": 0.4, "refactor": 0.3, "test": 0.2,
        "ci": 0.2, "docs": 0.1, "unknown": 0.25,
    }
    base = _COMMIT_SIGNALS.get(type_declared.lower(), 0.25)
    ci_bonus    = 0.2 if ci_green else 0.0
    issue_bonus = 0.4 if closes_issue else 0.0
    return min(1.0, base + ci_bonus + issue_bonus)


# ═══════════════════════════════════════════════════════════════════════════
# Resolução de componentes (prioridade: professor > commits > LLM > heurístico)
# ═══════════════════════════════════════════════════════════════════════════


def resolve_components(
    mr_artifact: dict,
    llm_estimate: Optional[dict] = None,
    overrides: Optional[dict] = None,
    commit_estimates: Optional[List[Dict]] = None,
) -> dict:
    """
    Resolve os valores finais de X, E, A, T_review, S, Q com prioridade:

    X: commits → legacy quantitative["X"] → 0.0
    E: professor → commits → LLM MR (legado) → heurístico
    A: professor → LLM → heurístico
    T_review: professor → LLM → heurístico
    S: artifact[reverted/overwritten_ratio] → legacy quantitative["S"] → 1.0
    Q: artifact[ci_configured/ci_passed/ci_attempts] → legacy quantitative["Q"] → 1.0

    Args:
        mr_artifact: MR artifact dict
        llm_estimate: Optional LLM estimate dict (Stage 2.3 — somente A e T_review)
        overrides: Optional dict com valores do professor para este MR
        commit_estimates: Optional lista de estimativas de commits (Stage 2.2)

    Returns:
        Dict com todos os componentes resolvidos e W calculado
    """
    result = {}
    mr_id = mr_artifact.get("mr_id", "unknown")

    # ===== X — qualidade de execução =====
    mr_commits = []
    if commit_estimates:
        mr_commits = [
            c for c in commit_estimates
            if c.get("mr_id") == mr_id and not c.get("is_filtered", False)
        ]

    if mr_commits:
        result["X"] = calc_x_from_commits(mr_commits)
        result["X_source"] = "commits"
    else:
        # Fallback legado: quantitative.X pré-computado
        result["X"] = mr_artifact.get("quantitative", {}).get("X", 0.0)
        result["X_source"] = "legacy"

    # ===== S — sobrevivência =====
    if "reverted" in mr_artifact or "overwritten_ratio" in mr_artifact:
        result["S"] = calc_s(
            reverted=mr_artifact.get("reverted", False),
            overwritten_ratio=mr_artifact.get("overwritten_ratio", 0.0),
        )
        result["S_source"] = "script"
    else:
        result["S"] = mr_artifact.get("quantitative", {}).get("S", 1.0)
        result["S_source"] = "legacy"

    # ===== Q — qualidade CI =====
    if "ci_configured" in mr_artifact or "ci_passed" in mr_artifact:
        result["Q"] = calc_q(
            ci_configured=mr_artifact.get("ci_configured", False),
            ci_passed=mr_artifact.get("ci_passed", True),
            ci_attempts=mr_artifact.get("ci_attempts", 1),
        )
        result["Q_source"] = "script"
    else:
        result["Q"] = mr_artifact.get("quantitative", {}).get("Q", 1.0)
        result["Q_source"] = "legacy"

    # ===== E — clareza técnica da autoria =====
    E = None
    E_source = None

    if overrides and "E" in overrides:
        E = overrides["E"]
        E_source = "professor"
    elif mr_commits:
        E = calc_e_from_commits(mr_commits)
        E_source = "commits"
    elif llm_estimate and "E" in llm_estimate:
        # Caminho legado: LLM retornava E antes do modelo v4.0
        e_info = llm_estimate["E"]
        if e_info.get("confidence", "low") != "low":
            E = e_info["value"]
            E_source = "llm"
    if E is None:
        # Fallback heurístico (legado)
        type_declared = mr_artifact.get("type_declared", "fix").lower()
        ci_green      = result["Q"] == 1.0
        closes_issue  = len(mr_artifact.get("linked_issues", [])) > 0
        E = calc_e_heuristic(type_declared, ci_green, closes_issue)
        E_source = "heuristic"

    result["E"] = E
    result["E_source"] = E_source

    # ===== A — importância arquitetural =====
    A = None
    A_source = None

    if overrides and "A" in overrides:
        A = overrides["A"]
        A_source = "professor"
    elif llm_estimate and "A" in llm_estimate:
        a_info = llm_estimate["A"]
        if a_info.get("confidence", "low") != "low":
            A = a_info["value"]
            A_source = "llm"

    if A is None:
        module_paths = [f["file"] for f in mr_artifact.get("diff_summary", [])]
        A = calc_a_heuristic(module_paths)
        A_source = "heuristic"

    result["A"] = A
    result["A_source"] = A_source

    # ===== T_review — qualidade do review =====
    T_review = None
    T_review_source = None

    if overrides and "T_review" in overrides:
        T_review = overrides["T_review"]
        T_review_source = "professor"
    elif llm_estimate and "T_review" in llm_estimate:
        tr_info = llm_estimate["T_review"]
        if tr_info.get("confidence", "low") != "low":
            T_review = tr_info["value"]
            T_review_source = "llm"

    if T_review is None:
        reviewers = mr_artifact.get("reviewers", [])
        T_review = config.T_REVIEWER_MAX if reviewers else 0.0
        T_review_source = "heuristic"

    result["T_review"] = T_review
    result["T_review_source"] = T_review_source

    # ===== V, R, W =====
    result["V"] = calc_v(result["X"], result["A"], result["E"])
    result["R"] = calc_r(result["S"], result["Q"])
    result["W"] = calc_w(result["V"], result["R"], result["A"], result["X"])

    # Qualidade da estimação: "degraded" se algum componente qualitativo usou heurística
    result["estimation_quality"] = "degraded" if any(
        src == "heuristic"
        for src in [E_source, A_source, T_review_source]
    ) else "full"

    return result


def compute_mr_weight(
    mr_artifact: dict,
    llm_estimate: Optional[dict] = None,
    overrides: Optional[dict] = None,
    commit_estimates: Optional[List[Dict]] = None,
) -> dict:
    """
    Wrapper principal: resolve todos os componentes e retorna o peso completo.

    Args:
        mr_artifact: MR artifact dict completo
        llm_estimate: Optional LLM estimate (Stage 2.3 — A e T_review)
        overrides: Optional overrides do professor
        commit_estimates: Optional estimativas de commits (Stage 2.2)

    Returns:
        Dict com todos os componentes resolvidos e W calculado
    """
    return resolve_components(mr_artifact, llm_estimate, overrides, commit_estimates)
