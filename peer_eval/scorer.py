"""
Stage 3 — Cálculo do fator de contribuição por membro.
"""

import logging
from typing import Optional, List, Dict
from . import config
from . import model

logger = logging.getLogger(__name__)


def compute_scores(
    mr_artifacts: List[Dict],
    llm_estimates: Optional[List[Dict]],
    overrides: Optional[Dict],
    members: List[str],
    direct_committers: Optional[List[str]] = None,
    commit_estimates: Optional[List[Dict]] = None,
) -> Dict[str, Dict]:
    """
    Calcula o fator de contribuição para cada membro do grupo.

    Por MR:
      - autor recebe T_AUTHOR × W(k)_efetivo
      - cada revisor recebe (T_review / n_revisores) × W(k)_efetivo

    Penalidade de direct commit (Stage 2.1):
      W(k)_efetivo = W(k) × DIRECT_COMMIT_PENALTY_MULTIPLIER (0.40)
      Aplicada sobre MRs cuja autoria pertence a um direct_committer.
      NÃO resulta em nota zero — o aluno mantém contribuições via review.

    Args:
        mr_artifacts: Lista de MR artifacts
        llm_estimates: Optional lista de estimativas LLM (Stage 2.3 — A, T_review)
        overrides: Optional dict de overrides do professor por mr_id
        members: Lista de usernames dos membros do grupo
        direct_committers: Optional lista de membros que fizeram commits diretos
        commit_estimates: Optional lista de estimativas de commits (Stage 2.2)

    Returns:
        Dict por username:
        {
            "ana": {
                "S": 1.435,
                "Abs": 1.000,
                "Rel": 0.733,
                "fc":  0.960,
                "nota": 0.960,        # alias de fc
                "mr_contributions": [...]
            }
        }
    """
    if direct_committers is None:
        direct_committers = []

    # Lookup de estimativas LLM por mr_id
    llm_lookup: Dict[str, Dict] = {}
    if llm_estimates:
        for est in llm_estimates:
            llm_lookup[est.get("mr_id")] = est

    # Lookup de overrides por mr_id
    overrides_lookup: Dict[str, Dict] = {}
    if overrides:
        for mr_id, mr_overrides in overrides.items():
            overrides_lookup[mr_id] = mr_overrides

    # Inicializa scores para todos os membros
    scores = {member: {"mr_contributions": []} for member in members}

    logger.info(
        f"Stage 3: {len(mr_artifacts)} MRs × {len(members)} membros"
        + (f", {len(commit_estimates)} commit estimates" if commit_estimates else "")
    )

    for mr_artifact in mr_artifacts:
        mr_id    = mr_artifact.get("mr_id")
        author   = mr_artifact.get("author")
        reviewers = mr_artifact.get("reviewers", [])

        llm_est    = llm_lookup.get(mr_id)
        mr_overrides = overrides_lookup.get(mr_id)

        # Resolve todos os componentes (X, E de commits; A, T_review de LLM/heurístico)
        components = model.compute_mr_weight(
            mr_artifact,
            llm_est,
            mr_overrides,
            commit_estimates,
        )
        W = components["W"]

        # Penalidade por direct commit: W × 0.40
        is_direct = author and author in direct_committers
        if is_direct:
            W = W * config.DIRECT_COMMIT_PENALTY_MULTIPLIER
            logger.info(
                f"{mr_id}: direct committer ({author}), "
                f"W={components['W']:.3f} → W_efetivo={W:.3f}"
            )

        logger.debug(
            f"{mr_id}: W_efetivo={W:.3f}, "
            f"X={components['X']:.3f}({components['X_source']}) "
            f"A={components['A']:.3f}({components['A_source']}) "
            f"E={components['E']:.3f}({components['E_source']})"
        )

        # Contribuição do autor
        if author and author in scores:
            author_contribution = config.T_AUTHOR * W
            scores[author]["mr_contributions"].append({
                "mr_id":        mr_id,
                "role":         "author",
                "W":            W,
                "T":            config.T_AUTHOR,
                "contribution": author_contribution,
                "direct_commit_penalty": is_direct,
            })

        # Contribuição dos revisores
        if reviewers:
            T_review = components.get("T_review", config.T_REVIEWER_MAX)
            per_reviewer = T_review / len(reviewers)

            for reviewer in reviewers:
                if reviewer in scores:
                    reviewer_contribution = per_reviewer * W
                    scores[reviewer]["mr_contributions"].append({
                        "mr_id":        mr_id,
                        "role":         "reviewer",
                        "W":            W,
                        "T":            per_reviewer,
                        "contribution": reviewer_contribution,
                        "direct_commit_penalty": False,
                    })

    # Agrega S(m) para todos os membros
    all_S = []
    for member in members:
        contributions = scores[member]["mr_contributions"]
        S = sum(c["contribution"] for c in contributions)
        scores[member]["S"] = S
        all_S.append(S)

    # Calcula Abs, Rel e fc
    max_S = max(all_S) if all_S else 1.0
    if max_S == 0:
        max_S = 1.0

    for member in members:
        S   = scores[member]["S"]
        Abs = min(1.0, S / config.L)
        Rel = S / max_S if max_S > 0 else 0.0
        fc  = config.ALPHA * Abs + config.BETA * Rel

        scores[member]["Abs"]  = Abs
        scores[member]["Rel"]  = Rel
        scores[member]["fc"]   = fc
        scores[member]["nota"] = fc  # alias para compatibilidade com relatórios existentes

    logger.info("Stage 3 completo")
    return scores
