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
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import loader
import llm_stage2a
import llm_stage2b
import model
import scorer
import report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main execution flow."""
    parser = argparse.ArgumentParser(
        description="Contribution Factor Model v3.0 - Evaluate student contributions"
    )

    parser.add_argument(
        "--fixture",
        required=True,
        help="Path to MR artifacts fixture (JSON)"
    )

    parser.add_argument(
        "--members",
        required=True,
        nargs="+",
        help="List of team member usernames"
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

    args = parser.parse_args()

    # ===== STAGE 0: Load artifacts =====
    logger.info("=" * 60)
    logger.info("Stage 0: Loading artifacts")
    logger.info("=" * 60)

    try:
        mr_artifacts = loader.load_artifacts(args.fixture)
        logger.info(f"Loaded {len(mr_artifacts)} MR artifacts")
    except Exception as e:
        logger.error(f"Failed to load artifacts: {e}")
        sys.exit(1)

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
