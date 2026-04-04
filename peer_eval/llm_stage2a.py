"""
Stage 2a: MR-level qualitative evaluation (E, A, T_review, P estimation).

Cycle 1: dry_run mode returns structured mock estimates derived heuristically.
Cycle 2+: Will call Anthropic Claude API for real evaluation with caching and fallback.
"""

import anthropic
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

from . import config
from . import model
from .exceptions import LLMParseError

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Prompt Loading
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# LLM Client & Response Parsing
# ═══════════════════════════════════════════════════════════════════════════


def _get_client(api_key: str) -> anthropic.Anthropic:
    """Create and return Anthropic client."""
    return anthropic.Anthropic(api_key=api_key)


def _parse_llm_response(raw: str, mr_id: str) -> Optional[dict]:
    """
    Extract JSON from LLM response, handling various formats.

    Tries in order:
      1. Direct JSON parse
      2. JSON in ```json ... ``` block
      3. JSON in ``` ... ``` block
      4. First {...} substring

    Returns None if no JSON found or invalid.
    """
    # Case 1: Direct JSON
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Case 2 & 3: Markdown code blocks
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    # Case 4: Extract first {...} object
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning(f"[{mr_id}] Could not parse LLM response: {raw[:200]}")
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Fallback Heuristics
# ═══════════════════════════════════════════════════════════════════════════


def _fallback_estimate(mr_artifact: dict, reason: str = "fallback") -> dict:
    """
    Return heuristic estimate when LLM fails or confidence is low.

    Uses model.py functions as base.
    """
    files = [f["file"] for f in mr_artifact.get("diff_summary", [])]
    type_declared = mr_artifact.get("type_declared", "unknown")
    has_reviewers = len(mr_artifact.get("reviewers", [])) > 0
    has_ci = mr_artifact.get("quantitative", {}).get("Q", 0.5) == 1.0
    has_issues = len(mr_artifact.get("linked_issues", [])) > 0

    e_value = model.calc_e_heuristic(type_declared, has_ci, has_issues)
    a_value = model.calc_a_heuristic(files)

    return {
        "mr_id": mr_artifact["mr_id"],
        "author": mr_artifact["author"],
        "E": {
            "value": e_value,
            "confidence": "low",
            "reasoning": f"Heuristic fallback ({reason})"
        },
        "A": {
            "value": a_value,
            "confidence": "low",
            "reasoning": f"Heuristic fallback ({reason})"
        },
        "T_review": {
            "value": config.T_REVIEWER_MAX if has_reviewers else 0.0,
            "level": "absent" if not has_reviewers else "superficial",
            "confidence": "low",
            "reasoning": f"Heuristic fallback ({reason})"
        },
        "P": {
            "value": 0.5,
            "confidence": "low",
            "reasoning": f"Heuristic fallback ({reason})"
        },
        "llm_model": "heuristic",
        "estimated_at": datetime.now(timezone.utc).isoformat() + "Z"
    }


# ═══════════════════════════════════════════════════════════════════════════
# Mock Estimate (for dry_run)
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# Caching
# ═══════════════════════════════════════════════════════════════════════════


def _cache_path(mr_id: str, cache_dir: str = "output/cache") -> Path:
    """Return Path to cached estimate file."""
    return Path(cache_dir) / f"{mr_id}.json"


def _load_from_cache(mr_id: str, cache_dir: str = "output/cache") -> Optional[dict]:
    """Load estimate from cache, return None if not found or invalid."""
    path = _cache_path(mr_id, cache_dir)
    if path.exists():
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            logger.debug(f"[{mr_id}] Loaded from cache")
            return result
        except Exception as e:
            logger.warning(f"[{mr_id}] Cache load error: {e}")
    return None


def _save_to_cache(estimate: dict, cache_dir: str = "output/cache") -> None:
    """Save estimate to cache file."""
    path = _cache_path(estimate["mr_id"], cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(estimate, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.debug(f"[{estimate['mr_id']}] Saved to cache")


# ═══════════════════════════════════════════════════════════════════════════
# Core Estimation Logic
# ═══════════════════════════════════════════════════════════════════════════


def estimate_mr(
    mr_artifact: dict,
    system_prompt: str = "",
    api_key: Optional[str] = None,
    dry_run: bool = True,
    cache_dir: str = "output/cache"
) -> dict:
    """
    Estimate E, A, T_review, P for a single MR.

    Args:
        mr_artifact: MR artifact dict
        system_prompt: System prompt for API
        api_key: Anthropic API key (required if dry_run=False)
        dry_run: If True, return mock estimate; if False, call API (cycle 2+)
        cache_dir: Directory for caching estimates

    Returns:
        Estimate dict with E, A, T_review, P values

    Raises:
        ValueError: If dry_run=False and api_key is None
    """
    mr_id = mr_artifact["mr_id"]

    # Dry run: return mock
    if dry_run:
        return _mock_estimate(mr_artifact)

    # Real LLM path
    if not api_key:
        raise ValueError("api_key required when dry_run=False")

    # Check cache first
    cached = _load_from_cache(mr_id, cache_dir)
    if cached:
        return cached

    # Build message
    user_message = (
        "Avalie o Merge Request abaixo e retorne apenas o JSON de saída "
        "conforme especificado no system prompt. Nenhum texto fora do JSON.\n\n"
        + json.dumps(mr_artifact, ensure_ascii=False, indent=2)
    )

    try:
        client = _get_client(api_key)
        logger.info(f"[{mr_id}] Calling LLM...")

        response = client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=config.LLM_MAX_TOKENS,
            temperature=config.LLM_TEMPERATURE,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        raw = response.content[0].text
        parsed = _parse_llm_response(raw, mr_id)

        if parsed is None:
            logger.warning(f"[{mr_id}] Parse failed — using fallback heuristic")
            result = _fallback_estimate(mr_artifact, reason="parse error")
        else:
            # Ensure required fields
            result = {
                "mr_id": mr_id,
                "author": mr_artifact["author"],
                **parsed,
                "llm_model": config.LLM_MODEL,
                "estimated_at": datetime.now(timezone.utc).isoformat() + "Z"
            }
            logger.info(
                f"[{mr_id}] OK — "
                f"E={result['E']['value']:.2f}({result['E']['confidence']}) "
                f"A={result['A']['value']:.2f}({result['A']['confidence']}) "
                f"T={result['T_review']['value']:.2f}({result['T_review']['level']}) "
                f"P={result['P']['value']:.2f}({result['P']['confidence']})"
            )

    except anthropic.APIStatusError as e:
        logger.error(f"[{mr_id}] API error ({e.status_code}): {e.message}")
        if e.status_code in (401, 403):
            raise  # Invalid key — stop immediately
        result = _fallback_estimate(mr_artifact, reason=f"API error {e.status_code}")

    except anthropic.APIConnectionError as e:
        logger.error(f"[{mr_id}] Connection error: {e}")
        result = _fallback_estimate(mr_artifact, reason="connection error")

    except Exception as e:
        logger.error(f"[{mr_id}] Unexpected error: {e}")
        result = _fallback_estimate(mr_artifact, reason=f"unexpected error: {type(e).__name__}")

    # Save to cache regardless of source
    _save_to_cache(result, cache_dir)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2a Orchestration
# ═══════════════════════════════════════════════════════════════════════════


def run_stage2a(
    mr_artifacts: List[Dict],
    api_key: Optional[str] = None,
    prompt_path: str = config.PROMPT_FILE,
    dry_run: bool = True,
    cache_dir: str = "output/cache",
    output_path: str = "output/mr_llm_estimates.json"
) -> List[Dict]:
    """
    Run Stage 2a: estimate qualitative components for all MRs.

    Args:
        mr_artifacts: List of MR artifacts
        api_key: Anthropic API key (required if dry_run=False)
        prompt_path: Path to prompts markdown file
        dry_run: If True, return mock estimates
        cache_dir: Directory for caching estimates
        output_path: Where to save estimates JSON

    Returns:
        List of estimate dicts
    """
    logger.info(f"Stage 2a: Processing {len(mr_artifacts)} MRs (dry_run={dry_run})")

    # Load system prompt
    system_prompt = ""
    if not dry_run:
        try:
            system_prompt = load_prompt("Stage 2a", prompt_path)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Could not load prompt: {e}")
            raise

    estimates = []
    for i, mr_artifact in enumerate(mr_artifacts, 1):
        logger.info(f"Stage 2a [{i}/{len(mr_artifacts)}] {mr_artifact['mr_id']} — {mr_artifact['title'][:60]}")
        estimate = estimate_mr(
            mr_artifact=mr_artifact,
            system_prompt=system_prompt,
            api_key=api_key,
            dry_run=dry_run,
            cache_dir=cache_dir
        )
        estimates.append(estimate)

    # Save to disk
    from . import loader
    loader.save_json(estimates, output_path)

    logger.info(f"Stage 2a complete: saved {len(estimates)} estimates to {output_path}")
    return estimates
