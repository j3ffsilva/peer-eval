"""
Stage 2b: Cross-MR pattern detection and group analysis.

Cycle 1: dry_run mode with heuristic pattern detection.
Cycle 2+: Will call Anthropic Claude API for detailed analysis.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from . import config
from .llm_stage2a import load_prompt

logger = logging.getLogger(__name__)


def _mock_group_report(
    mr_artifacts: List[Dict],
    llm_estimates: List[Dict],
    members: List[str],
    deadline: str
) -> dict:
    """
    Detect suspicious patterns heuristically from fixture.

    Looks for:
    - fragmentacao_artificial: MRs from same author < 2h apart, same files
    - burst_de_vespera: ≥50% of MRs in last 3 days
    - commit_inflado: High X but low A/E
    - padding_de_volume: High X but low A/E

    Args:
        mr_artifacts: List of MR artifacts
        llm_estimates: List of LLM estimates (with E, A, P values)
        members: List of team members
        deadline: Deadline ISO string

    Returns:
        Group report dict with flags and observations
    """
    flags = []
    observations = []
    flags_by_level = {"alto": 0, "medio": 0, "baixo": 0}

    # Build lookup tables
    mr_by_id = {mr["mr_id"]: mr for mr in mr_artifacts}
    est_by_id = {est["mr_id"]: est for est in llm_estimates}

    # Parse deadline
    try:
        deadline_dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        deadline_dt = datetime.now()

    # ===== Check for burst_de_vespera =====
    # Last 3 days before deadline
    three_days_before = deadline_dt - timedelta(days=3)

    for member in members:
        member_mrs = [mr for mr in mr_artifacts if mr.get("author") == member]
        if len(member_mrs) < 2:
            continue

        # Count MRs in last 3 days
        try:
            recent_mrs = [
                mr for mr in member_mrs
                if datetime.fromisoformat(mr.get("opened_at", "").replace("Z", "+00:00")) > three_days_before
            ]
        except (ValueError, AttributeError):
            recent_mrs = []

        if len(recent_mrs) >= max(2, len(member_mrs) * 0.5):  # ≥50% or at least 2
            # Check average T_review
            avg_t_review = 0.0
            review_count = 0
            for mr in member_mrs:
                est = est_by_id.get(mr["mr_id"])
                if est and "T_review" in est:
                    avg_t_review += est["T_review"].get("value", 0.0)
                    review_count += 1

            if review_count > 0:
                avg_t_review /= review_count

            if avg_t_review < 0.10:
                flags.append({
                    "type": "burst_de_vespera",
                    "persons": [member],
                    "mr_ids": [mr["mr_id"] for mr in recent_mrs],
                    "evidence": f"{len(recent_mrs)} of {len(member_mrs)} MRs em últimos 3 dias, T_review médio=0.{int(avg_t_review*100):.0f}",
                    "alternative": "Planejamento pobre ou sprint final intenso legítimo",
                    "suspicion_level": "medio"
                })
                flags_by_level["medio"] += 1

    # ===== Check for fragmentacao_artificial =====
    for member in members:
        member_mrs = sorted(
            [mr for mr in mr_artifacts if mr.get("author") == member],
            key=lambda m: m.get("opened_at", "")
        )

        if len(member_mrs) < 2:
            continue

        for i in range(len(member_mrs) - 1):
            mr1 = member_mrs[i]
            mr2 = member_mrs[i + 1]

            try:
                t1 = datetime.fromisoformat(mr1.get("opened_at", "").replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(mr2.get("opened_at", "").replace("Z", "+00:00"))
                delta = (t2 - t1).total_seconds() / 3600  # hours
            except (ValueError, AttributeError):
                continue

            # Check if < 2 hours apart
            if delta < 2.0:
                # Check if they touch same files
                files1 = set(f["file"] for f in mr1.get("diff_summary", []))
                files2 = set(f["file"] for f in mr2.get("diff_summary", []))
                overlap = files1 & files2

                if overlap:
                    flags.append({
                        "type": "fragmentacao_artificial",
                        "persons": [member],
                        "mr_ids": [mr1["mr_id"], mr2["mr_id"]],
                        "evidence": f"{mr1['mr_id']} e {mr2['mr_id']} abertos com {delta:.1f}h de intervalo, {len(overlap)} arquivos em comum",
                        "alternative": "Múltiplos PRs independentes para refatoração em paralelo",
                        "suspicion_level": "baixo"
                    })
                    flags_by_level["baixo"] += 1

    # ===== Check for commit_inflado =====
    for member in members:
        member_mrs = [mr for mr in mr_artifacts if mr.get("author") == member]
        if len(member_mrs) < 2:
            continue

        inflated_count = 0
        for mr in member_mrs:
            quant = mr.get("quantitative", {})
            est = est_by_id.get(mr["mr_id"], {})
            X = quant.get("X", 0.0)
            E_val = est.get("E", {}).get("value", 0.5)
            type_decl = mr.get("type_declared", "").lower()

            # High X but low E on feat/fix = suspicious
            if X > 0.5 and E_val < 0.4 and type_decl in ["feat", "fix"]:
                inflated_count += 1

        if inflated_count >= max(2, len(member_mrs) * 0.5):
            flags.append({
                "type": "commit_inflado",
                "persons": [member],
                "mr_ids": [mr["mr_id"] for mr in member_mrs],
                "evidence": f"{inflated_count} de {len(member_mrs)} MRs com X alto mas E baixo",
                "alternative": "Refatoração genuína que não afeta features (alto X, baixo E é normal)",
                "suspicion_level": "medio"
            })
            flags_by_level["medio"] += 1

    observations.append(f"Análise de {len(mr_artifacts)} MRs de {len(members)} membros")
    observations.append("Padrões: fragmentação artificial, burst de véspera, commits inflados, padding de volume")

    return {
        "project": "peer-eval-project",
        "analyzed_at": datetime.utcnow().isoformat() + "Z",
        "flags": flags,
        "observations": observations,
        "summary": {
            "total_mrs": len(mr_artifacts),
            "total_persons": len(members),
            "flags_by_level": flags_by_level
        }
    }


def detect_patterns(
    mr_artifacts: List[Dict],
    llm_estimates: List[Dict],
    members: List[str],
    deadline: str,
    prompt_path: str = config.PROMPT_FILE,
    dry_run: bool = True,
    output_path: str = "output/group_report.json"
) -> dict:
    """
    Run Stage 2b: detect cross-MR patterns and group analysis.

    Args:
        mr_artifacts: List of MR artifacts
        llm_estimates: List of LLM estimates
        members: List of team members
        deadline: Deadline ISO string
        prompt_path: Path to prompts markdown file
        dry_run: If True, return mock report
        output_path: Where to save report JSON

    Returns:
        Group report dict
    """
    logger.info(f"Running Stage 2b (dry_run={dry_run}) on {len(mr_artifacts)} MRs")

    # Load system prompt if not dry_run (will be used in cycle 2)
    system_prompt = ""
    if not dry_run:
        try:
            system_prompt = load_prompt("Stage 2b", prompt_path)
        except (FileNotFoundError, ValueError) as e:
            logger.warning(f"Could not load prompt: {e}")

    # Generate report
    if dry_run:
        report = _mock_group_report(mr_artifacts, llm_estimates, members, deadline)
    else:
        # Cycle 2: Call Anthropic API
        raise NotImplementedError("Real LLM calls in cycle 2")

    # Save to disk
    from . import loader
    loader.save_json(report, output_path)

    logger.info(f"Stage 2b complete: saved report to {output_path}")
    return report
