"""
Stage 2a: MR-level qualitative evaluation (E, A, T_review, P estimation).

Cycle 1: dry_run mode returns structured mock estimates derived heuristically.
Cycle 2+: Will call Anthropic Claude API for real evaluation.
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict
import config
import model
from exceptions import LLMParseError

logger = logging.getLogger(__name__)


def load_prompt(section: str, prompt_path: str = config.PROMPT_FILE) -> str:
    """
    Load and extract system prompt from markdown file.

    Searches for a heading matching '#### System Prompt — {section}'
    and extracts the code block immediately following it.

    Args:
        section: Section name (e.g., "Stage 2a")
        prompt_path: Path to prompts markdown file

    Returns:
        System prompt content

    Raises:
        FileNotFoundError: If prompt file not found
        ValueError: If section not found
    """
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    # Search for the section heading
    pattern = rf"#### System Prompt — {section}\s*\n\s*```\s*\n(.*?)\n```"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        raise ValueError(f"Section 'System Prompt — {section}' not found in {prompt_path}")

    return match.group(1).strip()


def _mock_estimate(mr_artifact: dict) -> dict:
    """
    Generate mock LLM estimate based on heuristics from the artifact.

    Returns structured estimate with plausible values derived from:
    - Commit type and description for E(k)
    - Module paths for A(k)
    - Review comments for T_review(k)
    - Diff size/complexity for P(k)

    Args:
        mr_artifact: MR artifact dict

    Returns:
        Mock estimate dict with E, A, T_review, P values and confidence
    """
    mr_id = mr_artifact.get("mr_id", "UNKNOWN")
    author = mr_artifact.get("author", "unknown")
    type_declared = mr_artifact.get("type_declared", "fix").lower()
    reviewers = mr_artifact.get("reviewers", [])
    diff_summary = mr_artifact.get("diff_summary", [])
    review_comments = mr_artifact.get("review_comments", [])
    linked_issues = mr_artifact.get("linked_issues", [])
    quantitative = mr_artifact.get("quantitative", {})

    # ===== E(k) — effort/authenticity =====
    # Use heuristic calculation
    ci_green = quantitative.get("Q", 1.0) == 1.0
    closes_issue = len(linked_issues) > 0
    E_value = model.calc_e_heuristic(type_declared, ci_green, closes_issue)

    # ===== A(k) — architectural importance =====
    # Use heuristic calculation
    module_paths = [f["file"] for f in diff_summary]
    A_value = model.calc_a_heuristic(module_paths)

    # ===== T_review(k) — reviewer quality =====
    # Assess review comments
    T_review_value = 0.0
    T_review_level = "ausente"

    if reviewers and review_comments:
        # Count substantive vs cosmetic comments
        substantive_count = 0
        superficial_count = 0
        cosmetic_count = 0

        for comment in review_comments:
            body = comment.get("body", "").lower()
            comment_type = comment.get("type", "comment")

            if comment_type == "approval":
                # Approval without prior comments = cosmetic
                if not [c for c in review_comments if c.get("type") == "comment"]:
                    cosmetic_count += 1
                else:
                    # Had technical comments before approval
                    substantive_count += 1
            elif len(body) > 30 and any(w in body for w in ["add", "remove", "fix", "improve", "refactor"]):
                substantive_count += 1
            elif len(body) < 10:
                cosmetic_count += 1
            else:
                superficial_count += 1

        if substantive_count > superficial_count + cosmetic_count:
            T_review_value = 0.26  # substantivo
            T_review_level = "substantivo"
        elif superficial_count > cosmetic_count:
            T_review_value = 0.12  # superficial
            T_review_level = "superficial"
        else:
            T_review_value = 0.03  # cosmetic
            T_review_level = "cosmetico"
    elif reviewers:
        # Reviewers exist but we're in this branch = no comments analyzed
        T_review_value = 0.15
        T_review_level = "superficial"

    # ===== P(k) — potential/impact =====
    # Estimate based on diff characteristics
    total_additions = sum(f.get("additions", 0) for f in diff_summary)
    n_files = len(diff_summary)

    if n_files > 5 and total_additions > 100:
        # Large, multi-file change likely to have impact
        P_value = 0.7
    elif n_files > 2 and any("core" in f["file"] or "domain" in f["file"] for f in diff_summary):
        # Core/domain logic = high impact
        P_value = 0.75
    elif n_files >= 1 and total_additions >= 50:
        # Medium-sized meaningful change
        P_value = 0.5
    elif "test" in " ".join(f["file"] for f in diff_summary):
        # Test-only = lower impact
        P_value = 0.2
    else:
        # Default for unknown
        P_value = 0.5

    return {
        "mr_id": mr_id,
        "author": author,
        "E": {
            "value": min(1.0, max(0.0, E_value)),
            "confidence": "medium",
            "reasoning": "mock"
        },
        "A": {
            "value": min(1.0, max(0.0, A_value)),
            "confidence": "medium",
            "reasoning": "mock"
        },
        "T_review": {
            "value": min(0.30, max(0.0, T_review_value)),
            "level": T_review_level,
            "confidence": "medium",
            "reasoning": "mock"
        },
        "P": {
            "value": min(1.0, max(0.0, P_value)),
            "confidence": "medium",
            "reasoning": "mock"
        },
        "llm_model": "dry_run",
        "estimated_at": datetime.utcnow().isoformat() + "Z"
    }


def estimate_mr(
    mr_artifact: dict,
    system_prompt: str = "",
    dry_run: bool = True
) -> dict:
    """
    Estimate E, A, T_review, P for a single MR.

    Args:
        mr_artifact: MR artifact dict
        system_prompt: System prompt (unused in cycle 1)
        dry_run: If True, return mock estimate; if False, call API (cycle 2+)

    Returns:
        Estimate dict with E, A, T_review, P values

    Raises:
        LLMParseError: If response cannot be parsed
    """
    if dry_run:
        return _mock_estimate(mr_artifact)

    # Cycle 2: Call Anthropic API
    # Placeholder for future implementation
    raise NotImplementedError("Real LLM calls in cycle 2")


def run_stage2a(
    mr_artifacts: List[Dict],
    prompt_path: str = config.PROMPT_FILE,
    dry_run: bool = True,
    output_path: str = "output/mr_llm_estimates.json"
) -> List[Dict]:
    """
    Run Stage 2a: estimate qualitative components for all MRs.

    Args:
        mr_artifacts: List of MR artifacts
        prompt_path: Path to prompts markdown file
        dry_run: If True, return mock estimates
        output_path: Where to save estimates JSON

    Returns:
        List of estimate dicts
    """
    logger.info(f"Running Stage 2a (dry_run={dry_run}) on {len(mr_artifacts)} MRs")

    # Load system prompt if not dry_run (will be used in cycle 2)
    system_prompt = ""
    if not dry_run:
        try:
            system_prompt = load_prompt("Stage 2a", prompt_path)
        except (FileNotFoundError, ValueError) as e:
            logger.warning(f"Could not load prompt: {e}")

    estimates = []
    for mr_artifact in mr_artifacts:
        estimate = estimate_mr(mr_artifact, system_prompt, dry_run=dry_run)
        estimates.append(estimate)

    # Save to disk
    import loader
    loader.save_json(estimates, output_path)

    logger.info(f"Stage 2a complete: saved {len(estimates)} estimates to {output_path}")
    return estimates
