"""
Shared evaluation pipeline (Stages 1-4).

Extracted from main.py to be reusable across all subcommands.
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Optional, Literal

from ... import loader
from ... import llm_stage2a
from ... import llm_stage2b
from ... import scorer
from ... import report

logger = logging.getLogger(__name__)


def _extract_members_from_artifacts(mr_artifacts: List[Dict]) -> List[str]:
    """
    Extract unique member usernames from MR artifacts.

    Args:
        mr_artifacts: List of MR artifact dicts

    Returns:
        Sorted list of unique member usernames
    """
    members = set()

    for mr in mr_artifacts:
        # Add author
        if mr.get("author"):
            members.add(mr["author"])

        # Add reviewers
        for reviewer in mr.get("reviewers", []):
            members.add(reviewer)

        # Add reviewers from comments
        for comment in mr.get("review_comments", []):
            if comment.get("author"):
                members.add(comment["author"])

    return sorted(list(members))


def run_evaluation(
    artifacts: List[Dict],
    deadline: str,
    llm_mode: Literal["live", "dry-run", "skip"] = "dry-run",
    anthropic_key: Optional[str] = None,
    members: Optional[List[str]] = None,
    output_dir: str = "output",
    overrides: Optional[str] = None,
    skip_stage2b: bool = False,
    direct_committers: Optional[List[str]] = None,
) -> Dict:
    """
    Run Stages 1-4 of the evaluation pipeline.

    This function:
    1. Ensures quantitative metrics are present
    2. Runs LLM component estimation (Stage 2a)
    3. Detects group patterns (Stage 2b, optional)
    4. Computes per-member scores (Stage 3)
    5. Generates reports (Stage 4)

    Args:
        artifacts: List of MR/PR artifact dicts
        deadline: Project deadline (ISO 8601 format)
        llm_mode: "live" (Anthropic API), "dry-run" (mock), "skip" (none)
        anthropic_key: Anthropic API key (required if llm_mode="live")
        members: List of team member usernames (auto-extracted if None)
        output_dir: Directory for output reports (default: output)
        overrides: Path to professor overrides JSON file (optional)
        skip_stage2b: Skip Stage 2b (group pattern detection)
        direct_committers: List of members to zero out (direct commits)

    Returns:
        Dictionary with final scores and metadata

    Raises:
        ValueError: If llm_mode="live" but anthropic_key is missing
        Exception: If any stage fails
    """

    # ===== STAGE 1: Extract quantitative (ensure present) =====
    logger.info("=" * 60)
    logger.info("Stage 1: Quantitative metrics")
    logger.info("=" * 60)

    for mr in artifacts:
        if "quantitative" not in mr:
            logger.warning(f"{mr.get('mr_id', 'UNKNOWN')}: missing quantitative — using defaults")
            mr["quantitative"] = {"X": 0.0, "S": 1.0, "Q": 1.0}

    logger.info("Quantitative metrics verified")

    # ===== Auto-extract members if not provided =====
    if not members:
        members = _extract_members_from_artifacts(artifacts)
        logger.info(f"Auto-extracted {len(members)} unique members from artifacts:")
        logger.info(f"  {', '.join(members)}")
    else:
        logger.info(f"Using {len(members)} provided members:")
        logger.info(f"  {', '.join(members)}")

    # ===== STAGE 2a: LLM evaluation of components =====
    logger.info("=" * 60)
    logger.info("Stage 2a: LLM component estimation (E, A, T_review, P)")
    logger.info("=" * 60)

    llm_estimates = []
    if llm_mode == "skip":
        logger.info("Skipping Stage 2a (--llm-mode skip)")
    else:
        # Determine if dry_run
        dry_run = (llm_mode == "dry-run")

        # Validate live mode
        if llm_mode == "live" and not anthropic_key:
            raise ValueError(
                "LLM mode is 'live' but anthropic_key not provided. "
                "Set ANTHROPIC_API_KEY env var or pass --anthropic-key"
            )

        logger.info(f"Running Stage 2a (mode={llm_mode})...")
        output_path = os.path.join(output_dir, "mr_llm_estimates.json")
        cache_dir = os.path.join(output_dir, "cache")

        # Get prompt path (relative to this module)
        prompt_path = os.path.join(
            Path(__file__).parent.parent.parent,  # package root
            "prompts",
            "avaliacao_llm.md"
        )

        llm_estimates = llm_stage2a.run_stage2a(
            artifacts,
            api_key=anthropic_key if llm_mode == "live" else None,
            prompt_path=prompt_path,
            dry_run=dry_run,
            cache_dir=cache_dir,
            output_path=output_path,
        )

    # ===== Load overrides =====
    logger.info("=" * 60)
    logger.info("Loading professor overrides (if any)")
    logger.info("=" * 60)

    overrides_dict = None
    if overrides:
        try:
            overrides_dict = loader.load_overrides(overrides)
            if overrides_dict:
                logger.info(f"Loaded overrides for {len(overrides_dict)} MRs")
            else:
                logger.info("No overrides found")
        except Exception as e:
            logger.warning(f"Failed to load overrides: {e}")

    # ===== STAGE 2b: Cross-MR pattern detection =====
    group_report = None
    if not skip_stage2b:
        logger.info("=" * 60)
        logger.info("Stage 2b: Cross-MR pattern detection")
        logger.info("=" * 60)

        output_path = os.path.join(output_dir, "group_report.json")

        # Get prompt path
        prompt_path = os.path.join(
            Path(__file__).parent.parent.parent,
            "prompts",
            "avaliacao_llm.md"
        )

        group_report = llm_stage2b.detect_patterns(
            artifacts,
            llm_estimates if llm_estimates else [],
            members,
            deadline,
            prompt_path=prompt_path,
            api_key=anthropic_key if llm_mode == "live" else None,
            dry_run=(llm_mode == "dry-run"),
            output_path=output_path,
        )

    # ===== STAGE 3: Compute per-member scores =====
    logger.info("=" * 60)
    logger.info("Stage 3: Aggregate scores per member")
    logger.info("=" * 60)

    scores = scorer.compute_scores(
        artifacts,
        llm_estimates,
        overrides_dict,
        members,
        direct_committers=direct_committers,
    )

    logger.info(f"Computed scores for {len(scores)} members")

    # ===== STAGE 4: Generate reports =====
    logger.info("=" * 60)
    logger.info("Stage 4: Generate reports")
    logger.info("=" * 60)

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Print summary
    report.print_summary(scores, group_report)

    # Export full report
    full_report_path = os.path.join(output_dir, "full_report.json")
    report.export_full_report(
        artifacts,
        llm_estimates,
        scores,
        group_report,
        output_path=full_report_path,
    )

    logger.info("=" * 60)
    logger.info("Pipeline completed successfully")
    logger.info("=" * 60)
    logger.info(f"Reports generated in {output_dir}/")

    return scores
