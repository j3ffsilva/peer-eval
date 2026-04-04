"""
Main entry point: orchestrates the entire contribution factor model pipeline.

Usage:
    python main.py --fixture fixtures/mr_artifacts.json \
                   --members ana bruno carla diego \
                   --deadline 2024-11-29T23:59:00Z \
                   [--llm-estimates output/mr_llm_estimates.json] \
                   [--overrides final_values.json] \
                   [--output-dir output] \
                   [--skip-stage2b] \
                   [--direct-committers <usernames>]

For real gitlab data (cycle 2), configure .env or use:
    python main.py --since 2024-09-01 \
                   --until 2024-12-01 \
                   --members usuario1 usuario2 usuario3 usuario4 \
                   --deadline 2024-12-01T23:59:00Z
    # Credentials loaded from .env automatically
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional

from dotenv import load_dotenv

from . import loader
from . import llm_stage2a
from . import llm_stage2b
from . import model
from . import scorer
from . import report

# Load environment variables from .env file (if it exists)
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================
# Helper functions for auto-extraction and path handling
# ============================================================


def _extract_members_from_artifacts(mr_artifacts: List[Dict]) -> List[str]:
    """
    Extract unique member usernames from MR artifacts.

    Collects all authors and reviewers from the artifacts.
    Returns sorted list of unique usernames.

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


def _infer_project_id_from_cwd(gitlab_project_template: Optional[str] = None) -> Optional[str]:
    """
    Infer GitLab project ID from current working directory name.

    If cwd is "G02", tries to construct project ID by replacing the last segment
    of the template project ID with the lowercased directory name.

    Examples:
        - cwd="/path/G02", template="graduacao/2026-1a/t17/g03"
          → "graduacao/2026-1a/t17/g02"
        - cwd="/path/G02", template=None
          → None (can't infer without template)

    Args:
        gitlab_project_template: Template project ID to use as base (e.g., from .env)

    Returns:
        Inferred project ID, or None if impossible to infer
    """
    if not gitlab_project_template:
        return None

    # Get current directory name (e.g., "G02")
    cwd_name = os.path.basename(os.getcwd()).lower()

    if not cwd_name:
        return gitlab_project_template

    # Split template and replace last segment with cwd name
    parts = gitlab_project_template.split("/")
    if len(parts) > 0:
        parts[-1] = cwd_name
        return "/".join(parts)

    return gitlab_project_template


def _extract_repo_name(project_id: Optional[str]) -> str:
    """
    Extract repository name from project_id or use current directory name.

    Examples:
        "graduacao/2026-1a/t17/g03" → "g03"
        "group/project" → "project"
        "123" → "project_123"
        None → basename of current working directory

    Args:
        project_id: GitLab project ID or namespace/repo (optional)

    Returns:
        Repository name (last segment if path, directory name, or the ID)
    """
    # If no project_id, use current directory name
    if not project_id:
        return os.path.basename(os.getcwd())

    if project_id.isdigit():
        return f"project_{project_id}"

    # Split by / and return last segment
    parts = project_id.split("/")
    return parts[-1] if parts else os.path.basename(os.getcwd())


def _prepare_output_dir(base_dir: str, project_id: Optional[str]) -> str:
    """
    Prepare output directory, creating repo-specific subdirectory if using GitLab.

    Args:
        base_dir: Base output directory
        project_id: GitLab project ID (optional)

    Returns:
        Final output directory path
    """
    # Always extract repo name for organization, using cwd if project_id is None
    repo_name = _extract_repo_name(project_id)
    output_dir = os.path.join(base_dir, repo_name)

    os.makedirs(output_dir, exist_ok=True)
    return output_dir



def main():
    """Main execution flow."""
    parser = argparse.ArgumentParser(
        description="Contribution Factor Model v3.0 - Evaluate student contributions"
    )

    parser.add_argument(
        "--fixture",
        required=False,
        default=None,
        help="Path to MR artifacts fixture (JSON) — optional if using GitLab (cycle 2)"
    )

    parser.add_argument(
        "--members",
        required=False,
        nargs="*",
        default=None,
        help="List of team member usernames (optional — auto-extracted from MRs if omitted)"
    )

    parser.add_argument(
        "--deadline",
        required=True,
        help="Project deadline (ISO 8601)"
    )

    parser.add_argument(
        "--llm-estimates",
        default=None,
        help="Path to pre-computed LLM estimates (optional)"
    )

    parser.add_argument(
        "--overrides",
        default=None,
        help="Path to professor overrides (optional)"
    )

    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory for reports (default: output)"
    )

    parser.add_argument(
        "--skip-stage2b",
        action="store_true",
        help="Skip Stage 2b (group pattern detection)"
    )

    parser.add_argument(
        "--direct-committers",
        nargs="*",
        default=None,
        help="List of members who made direct commits (zero out their scores)"
    )

    # ===== Cycle 2: Real GitLab integration =====
    parser.add_argument(
        "--gitlab-url",
        default=os.getenv("GITLAB_URL"),
        help="GitLab instance URL (e.g., https://gitlab.com) — can read from GITLAB_URL env var"
    )

    parser.add_argument(
        "--project-id",
        default=os.getenv("GITLAB_PROJECT"),
        help="GitLab project ID or namespace/repo — can read from GITLAB_PROJECT env var"
    )

    parser.add_argument(
        "--token",
        default=os.getenv("GITLAB_TOKEN"),
        help="GitLab Personal Access Token — can read from GITLAB_TOKEN env var (NEVER in CLI!)"
    )

    parser.add_argument(
        "--repo-path",
        default=os.getenv("REPO_PATH"),
        help="Absolute path to cloned repository — can read from REPO_PATH env var, defaults to current directory"
    )

    parser.add_argument(
        "--use-cwd",
        action="store_true",
        help="Use current working directory as repository path (ignores REPO_PATH env var)"
    )

    parser.add_argument(
        "--no-ssl-verify",
        action="store_true",
        default=os.getenv("GITLAB_SSL_VERIFY", "true").lower() == "false",
        help="Disable SSL verification (for self-signed certificates)"
    )

    parser.add_argument(
        "--since",
        default=None,
        help="ISO 8601 start date (e.g., 2024-09-01T00:00:00Z)"
    )

    parser.add_argument(
        "--until",
        default=None,
        help="ISO 8601 end date (e.g., 2024-12-01T23:59:59Z)"
    )

    args = parser.parse_args()

    # Use current working directory if --use-cwd is specified or REPO_PATH not in .env
    if args.use_cwd or not args.repo_path:
        args.repo_path = os.getcwd()
        logger.info(f"Using current working directory as repository path: {args.repo_path}")

    # If using --use-cwd, infer project-id from directory name (replaces template from .env)
    if args.use_cwd:
        original_project_id = args.project_id
        args.project_id = _infer_project_id_from_cwd(args.project_id)
        if args.project_id != original_project_id:
            logger.info(f"Inferred project ID from directory: {original_project_id} → {args.project_id}")

    # Validate required GitLab parameters if not using fixture
    use_gitlab = all([
        args.gitlab_url,
        args.project_id,
        args.token,
        args.repo_path,
        args.since,
        args.until,
    ])

    if not use_gitlab and not args.fixture:
        parser.error(
            "Either --fixture must be provided (cycle 1) or all GitLab "
            "parameters must be set (gitlab-url, project-id, token, repo-path, since, until). "
            "Configure .env or pass as arguments. See .env.example for details."
        )

    # ===== STAGE 0: Load or collect artifacts =====
    logger.info("=" * 60)

    # Determine if using fixture or collecting from GitLab
    use_gitlab = all([
        args.gitlab_url,
        args.project_id,
        args.token,
        args.repo_path,
        args.since,
        args.until,
    ])

    if use_gitlab:
        logger.info("Stage 0: Collecting artifacts from GitLab")
        logger.info("=" * 60)

        try:
            from .collector import collect
            mr_artifacts = collect(
                gitlab_url=args.gitlab_url,
                project_id=args.project_id,
                token=args.token,
                repo_path=args.repo_path,
                since=args.since,
                until=args.until,
                output_path=os.path.join(args.output_dir, "mr_artifacts.json"),
                ssl_verify=not args.no_ssl_verify
            )
            logger.info(f"Collected {len(mr_artifacts)} MR artifacts")

            # Prepare output directory with repo name
            args.output_dir = _prepare_output_dir(args.output_dir, args.project_id)
            logger.info(f"Output directory: {args.output_dir}")

        except Exception as e:
            logger.error(f"Failed to collect artifacts from GitLab: {e}")
            sys.exit(1)
    else:
        logger.info("Stage 0: Loading artifacts from fixture")
        logger.info("=" * 60)

        try:
            mr_artifacts = loader.load_artifacts(args.fixture)
            logger.info(f"Loaded {len(mr_artifacts)} MR artifacts")
        except Exception as e:
            logger.error(f"Failed to load artifacts: {e}")
            sys.exit(1)

    # ===== Auto-extract members if not provided =====
    if not args.members:
        args.members = _extract_members_from_artifacts(mr_artifacts)
        logger.info(f"Auto-extracted {len(args.members)} unique members from artifacts:")
        logger.info(f"  {', '.join(args.members)}")
    else:
        logger.info(f"Using {len(args.members)} provided members:")
        logger.info(f"  {', '.join(args.members)}")

    # ===== STAGE 1: Extract quantitative (already in fixture) =====
    logger.info("=" * 60)
    logger.info("Stage 1: Quantitative metrics (from fixture)")
    logger.info("=" * 60)

    # Verify all have quantitative
    for mr in mr_artifacts:
        if "quantitative" not in mr:
            logger.warning(f"{mr['mr_id']}: missing quantitative — using defaults")
            mr["quantitative"] = {"X": 0.0, "S": 1.0, "Q": 1.0}

    logger.info("Quantitative metrics loaded from fixture")

    # ===== STAGE 2a: LLM evaluation of components =====
    logger.info("=" * 60)
    logger.info("Stage 2a: LLM component estimation (E, A, T_review, P)")
    logger.info("=" * 60)

    if args.llm_estimates and os.path.exists(args.llm_estimates):
        logger.info(f"Loading pre-computed LLM estimates from {args.llm_estimates}")
        llm_estimates = loader.load_llm_estimates(args.llm_estimates)
    else:
        logger.info("Running Stage 2a to estimate components...")
        output_path = os.path.join(args.output_dir, "mr_llm_estimates.json")
        llm_estimates = llm_stage2a.run_stage2a(
            mr_artifacts,
            dry_run=True,  # Cycle 1: dry_run only
            output_path=output_path
        )

    # ===== Load overrides =====
    logger.info("=" * 60)
    logger.info("Loading professor overrides (if any)")
    logger.info("=" * 60)

    overrides = None
    if args.overrides:
        overrides = loader.load_overrides(args.overrides)
        if overrides:
            logger.info(f"Loaded overrides for {len(overrides)} MRs")
        else:
            logger.info("No overrides found")

    # ===== STAGE 2b: Cross-MR pattern detection =====
    group_report = None
    if not args.skip_stage2b:
        logger.info("=" * 60)
        logger.info("Stage 2b: Cross-MR pattern detection")
        logger.info("=" * 60)

        output_path = os.path.join(args.output_dir, "group_report.json")
        group_report = llm_stage2b.detect_patterns(
            mr_artifacts,
            llm_estimates if llm_estimates else [],
            args.members,
            args.deadline,
            dry_run=True,  # Cycle 1: dry_run only
            output_path=output_path
        )

    # ===== STAGE 3: Compute per-member scores =====
    logger.info("=" * 60)
    logger.info("Stage 3: Aggregate scores per member")
    logger.info("=" * 60)

    scores = scorer.compute_scores(
        mr_artifacts,
        llm_estimates,
        overrides,
        args.members,
        direct_committers=args.direct_committers if args.direct_committers else None
    )

    logger.info(f"Computed scores for {len(scores)} members")

    # ===== STAGE 4: Generate reports =====
    logger.info("=" * 60)
    logger.info("Stage 4: Generate reports")
    logger.info("=" * 60)

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # Print summary
    report.print_summary(scores, group_report)

    # Export full report
    full_report_path = os.path.join(args.output_dir, "full_report.json")
    report.export_full_report(
        mr_artifacts,
        llm_estimates,
        scores,
        group_report,
        output_path=full_report_path
    )

    logger.info("=" * 60)
    logger.info("Pipeline completed successfully")
    logger.info("=" * 60)
    logger.info(f"Reports generated in {args.output_dir}/")


if __name__ == "__main__":
    main()
