"""
Score aggregation and grade computation for individual contributors.
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
    direct_committers: Optional[List[str]] = None
) -> Dict[str, Dict]:
    """
    Compute contribution scores for each team member.

    For each MR:
      - author receives T_AUTHOR × W(k)
      - each reviewer receives (T_review_total / n_reviewers) × W(k)

    Args:
        mr_artifacts: List of MR artifacts
        llm_estimates: Optional list of LLM estimates
        overrides: Optional professor overrides dict
        members: List of all team member usernames
        direct_committers: Optional list of members to zero out (direct commits broke workflow)

    Returns:
        Dict keyed by username:
        {
            "ana": {
                "S": 1.24,          # Sum of contributions
                "Abs": 1.0,         # Absolute score (min(S/L, 1.0))
                "Rel": 1.0,         # Relative score (S / max)
                "nota": 1.0,        # Final grade (0.85*Abs + 0.15*Rel)
                "mr_contributions": [
                    {
                        "mr_id": "MR-1",
                        "role": "author",
                        "W": 0.495,
                        "T": 0.7,
                        "contribution": 0.347
                    }
                ]
            }
        }

    Members in direct_committers have nota = 0.0.
    Members without any MR contribution have nota = 0.0 (but S, Abs, Rel are 0.0).
    """
    if direct_committers is None:
        direct_committers = []

    # Build LLM estimates lookup by MR ID
    llm_lookup = {}
    if llm_estimates:
        for est in llm_estimates:
            llm_lookup[est.get("mr_id")] = est

    # Build overrides lookup by MR ID
    overrides_lookup = {}
    if overrides:
        for mr_id, mr_overrides in overrides.items():
            overrides_lookup[mr_id] = mr_overrides

    # Initialize scores dict for all members
    scores = {member: {"mr_contributions": []} for member in members}

    # Process each MR
    logger.info(f"Computing scores for {len(mr_artifacts)} MRs and {len(members)} members")

    for mr_artifact in mr_artifacts:
        mr_id = mr_artifact.get("mr_id")
        author = mr_artifact.get("author")
        reviewers = mr_artifact.get("reviewers", [])

        # Get LLM estimate if available
        llm_est = llm_lookup.get(mr_id)

        # Get overrides if available
        mr_overrides = overrides_lookup.get(mr_id)

        # Compute MR weight and components
        components = model.compute_mr_weight(mr_artifact, llm_est, mr_overrides)
        W = components["W"]

        logger.debug(f"{mr_id}: W={W:.3f}, X={components['X']:.3f}, A={components['A']:.3f}")

        # Author contribution
        if author and author in scores:
            author_contribution = config.T_AUTHOR * W
            scores[author]["mr_contributions"].append({
                "mr_id": mr_id,
                "role": "author",
                "W": W,
                "T": config.T_AUTHOR,
                "contribution": author_contribution
            })

        # Reviewer contributions
        if reviewers:
            T_review = components.get("T_review", config.T_REVIEWER_MAX)
            per_reviewer = T_review / len(reviewers)

            for reviewer in reviewers:
                if reviewer in scores:
                    reviewer_contribution = per_reviewer * W
                    scores[reviewer]["mr_contributions"].append({
                        "mr_id": mr_id,
                        "role": "reviewer",
                        "W": W,
                        "T": per_reviewer,
                        "contribution": reviewer_contribution
                    })

    # Compute aggregated scores
    all_S = []
    for member in members:
        contributions = scores[member]["mr_contributions"]
        S = sum(c["contribution"] for c in contributions)
        scores[member]["S"] = S
        all_S.append(S)

    # Compute Abs and Rel for each member
    max_S = max(all_S) if all_S else 1.0
    if max_S == 0:
        max_S = 1.0

    for member in members:
        S = scores[member]["S"]
        Abs = min(1.0, S / config.L)
        Rel = S / max_S if max_S > 0 else 0.0

        scores[member]["Abs"] = Abs
        scores[member]["Rel"] = Rel

        # Compute final grade
        if member in direct_committers:
            nota = 0.0
            logger.info(f"{member}: direct committer, nota = 0.0")
        else:
            nota = config.ALPHA * Abs + config.BETA * Rel

        scores[member]["nota"] = nota

    logger.info(f"Score computation complete")

    return scores
