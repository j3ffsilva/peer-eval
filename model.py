"""
Core calculation functions for the Contribution Factor Model v3.0.
All functions are pure (no I/O, no side effects, 100% testable).
"""

import math
from typing import Optional, List
import config


def sat(x: float, tau: float) -> float:
    """
    Saturation function: sat(x, τ) = 1 - exp(-x / τ)

    Args:
        x: Input value (lines, files, or modules count)
        tau: Time constant for saturation

    Returns:
        Saturation score in [0, 1]
    """
    if tau <= 0:
        raise ValueError("tau must be positive")
    return 1.0 - math.exp(-x / tau)


def calc_x(lines: int, files: int, n_modules: int) -> float:
    """
    Calculate quantitative component X(k).

    X(k) = 0.5·sat(lines, 100) + 0.3·sat(files, 10) + 0.2·sat(modules, 5)

    Args:
        lines: Total lines added/modified
        files: Number of files affected
        n_modules: Number of distinct modules/directories affected

    Returns:
        Quantitative score in [0, 1]
    """
    sat_lines = sat(lines, config.TAU_LINES)
    sat_files = sat(files, config.TAU_FILES)
    sat_modules = sat(n_modules, config.TAU_MODULES)

    return 0.5 * sat_lines + 0.3 * sat_files + 0.2 * sat_modules


def calc_a_heuristic(module_paths: List[str]) -> float:
    """
    Calculate architectural weight A(k) heuristically.

    Extracts the root module name from each file path (e.g., "domain/payment.py" → "domain")
    and takes the average of MODULE_WEIGHTS.
    For unmapped modules, defaults to 0.5.

    Args:
        module_paths: List of file paths (e.g., ["domain/payment.py", "api/routes.py"])

    Returns:
        Architectural weight in [0, 1]
    """
    if not module_paths:
        return 0.5

    weights = []
    for path in module_paths:
        # Extract root module name (first directory or filename if no directory)
        parts = path.split("/")
        root_module = parts[0].split(".")[0]  # remove extension if no directory

        # Look up weight, default to 0.5
        weight = config.MODULE_WEIGHTS.get(root_module, 0.5)
        weights.append(weight)

    return sum(weights) / len(weights) if weights else 0.5


def calc_e_heuristic(
    type_declared: str,
    ci_green: bool,
    closes_issue: bool
) -> float:
    """
    Calculate effort/authenticity component E(k) heuristically.

    Sums COMMIT_SIGNALS[type] + CI bonus + issue bonus. Clamped to [0, 1].

    Args:
        type_declared: Declared commit type (feat, fix, refactor, test, ci, docs)
        ci_green: True if CI passed, False if failed, None if unknown
        closes_issue: True if MR closes an issue

    Returns:
        Effort/authenticity score in [0, 1]
    """
    # Base signal from commit type
    base = config.COMMIT_SIGNALS.get(type_declared.lower(), 0.2)

    # Add CI bonus
    ci_bonus = config.E_BONUS_CI if ci_green else 0.0

    # Add issue bonus
    issue_bonus = config.E_BONUS_ISSUE if closes_issue else 0.0

    total = base + ci_bonus + issue_bonus
    return min(1.0, total)


def calc_v(X: float, A: float, E: float) -> float:
    """
    Calculate value component V(k).

    V(k) = 0.35·X(k) + 0.35·A(k) + 0.30·E(k)

    Args:
        X: Quantitative component
        A: Architectural component
        E: Effort/authenticity component

    Returns:
        Value score in [0, 1]
    """
    return config.W_X * X + config.W_A * A + config.W_E * E


def calc_r(S: float, P: float, Q: float) -> float:
    """
    Calculate review/risk component R(k).

    R(k) = 0.50·S(k) + 0.30·P(k) + 0.20·Q(k)

    Args:
        S: Survival score (survival rate from git blame; always 1.0 in cycle 1)
        P: Potential/impact score
        Q: Quality score (CI status)

    Returns:
        Review/risk score in [0, 1]
    """
    return config.W_S * S + config.W_P * P + config.W_Q * Q


def calc_w(V: float, R: float, A: float, X: float) -> float:
    """
    Calculate MR weight W(k) with triviality gating.

    Base: W(k) = V(k) × R(k)
    Gating: if A(k) < GATE_A and X(k) < GATE_X, then W(k) *= GATE_PENALTY

    Args:
        V: Value component
        R: Review/risk component
        A: Architectural component
        X: Quantitative component

    Returns:
        MR weight in [0, 1]
    """
    W = V * R

    # Apply triviality gating: both A and X must be below threshold
    if A < config.GATE_A and X < config.GATE_X:
        W *= config.GATE_PENALTY

    return W


def resolve_components(
    mr_artifact: dict,
    llm_estimate: Optional[dict] = None,
    overrides: Optional[dict] = None
) -> dict:
    """
    Resolve final values for E, A, T_review, P with priority:
      1. overrides (professor) → source = "professor"
      2. llm_estimate with confidence != "low" → source = "llm"
      3. fallback heuristic → source = "heuristic"

    Also extracts X, S, Q from quantitative (already calculated in fixture).

    Args:
        mr_artifact: MR artifact dict with diff_summary, review_comments, etc.
        llm_estimate: Optional LLM estimate dict with E, A, T_review, P
        overrides: Optional dict with professor-provided values for this MR

    Returns:
        Dict with all components and their sources:
        {
            "X": 0.103, "X_source": "script",
            "S": 1.0, "S_source": "script",
            "Q": 1.0, "Q_source": "script",
            "E": 0.82, "E_source": "llm",
            "A": 0.85, "A_source": "heuristic",
            "T_review": 0.26, "T_review_source": "llm",
            "P": 0.5, "P_source": "heuristic",
            "V": ..., "R": ..., "W": ...
        }
    """
    result = {}

    # ===== X, S, Q from artifact quantitative =====
    quant = mr_artifact.get("quantitative", {})
    result["X"] = quant.get("X", 0.0)
    result["X_source"] = "script"
    result["S"] = quant.get("S", 1.0)
    result["S_source"] = "script"
    result["Q"] = quant.get("Q", 1.0)
    result["Q_source"] = "script"

    # ===== E (effort/authenticity) =====
    E = None
    E_source = None

    # Check professor override first
    if overrides and "E" in overrides:
        E = overrides["E"]
        E_source = "professor"
    # Check LLM estimate
    elif llm_estimate and "E" in llm_estimate:
        e_info = llm_estimate["E"]
        confidence = e_info.get("confidence", "low")
        if confidence != "low":
            E = e_info["value"]
            E_source = "llm"

    # Fallback to heuristic
    if E is None:
        type_declared = mr_artifact.get("type_declared", "fix").lower()
        ci_green = result["Q"] == 1.0
        closes_issue = len(mr_artifact.get("linked_issues", [])) > 0
        E = calc_e_heuristic(type_declared, ci_green, closes_issue)
        E_source = "heuristic"

    result["E"] = E
    result["E_source"] = E_source

    # ===== A (architectural) =====
    A = None
    A_source = None

    if overrides and "A" in overrides:
        A = overrides["A"]
        A_source = "professor"
    elif llm_estimate and "A" in llm_estimate:
        a_info = llm_estimate["A"]
        confidence = a_info.get("confidence", "low")
        if confidence != "low":
            A = a_info["value"]
            A_source = "llm"

    if A is None:
        module_paths = [f["file"] for f in mr_artifact.get("diff_summary", [])]
        A = calc_a_heuristic(module_paths)
        A_source = "heuristic"

    result["A"] = A
    result["A_source"] = A_source

    # ===== T_review (reviewer contribution weight) =====
    T_review = None
    T_review_source = None

    if overrides and "T_review" in overrides:
        T_review = overrides["T_review"]
        T_review_source = "professor"
    elif llm_estimate and "T_review" in llm_estimate:
        tr_info = llm_estimate["T_review"]
        confidence = tr_info.get("confidence", "low")
        if confidence != "low":
            T_review = tr_info["value"]
            T_review_source = "llm"

    # Fallback: check if there are reviewers
    if T_review is None:
        reviewers = mr_artifact.get("reviewers", [])
        if reviewers:
            T_review = config.T_REVIEWER_MAX
        else:
            T_review = 0.0
        T_review_source = "heuristic"

    result["T_review"] = T_review
    result["T_review_source"] = T_review_source

    # ===== P (potential/impact) =====
    P = None
    P_source = None

    if overrides and "P" in overrides:
        P = overrides["P"]
        P_source = "professor"
    elif llm_estimate and "P" in llm_estimate:
        p_info = llm_estimate["P"]
        confidence = p_info.get("confidence", "low")
        if confidence != "low":
            P = p_info["value"]
            P_source = "llm"

    # Fallback: default to 0.5 for unknown
    if P is None:
        P = 0.5
        P_source = "heuristic"

    result["P"] = P
    result["P_source"] = P_source

    # ===== Calculate V, R, W =====
    result["V"] = calc_v(result["X"], result["A"], result["E"])
    result["R"] = calc_r(result["S"], result["P"], result["Q"])
    result["W"] = calc_w(result["V"], result["R"], result["A"], result["X"])

    return result


def compute_mr_weight(
    mr_artifact: dict,
    llm_estimate: Optional[dict] = None,
    overrides: Optional[dict] = None
) -> dict:
    """
    Main wrapper: resolve all components and return complete computed weight.

    Args:
        mr_artifact: Full MR artifact dict
        llm_estimate: Optional LLM estimate dict
        overrides: Optional professor overrides dict

    Returns:
        Dict with all components resolved and W computed
    """
    return resolve_components(mr_artifact, llm_estimate, overrides)
