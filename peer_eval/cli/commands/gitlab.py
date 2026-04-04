"""
'peer-eval gitlab' command — evaluate using GitLab data.

Collects MRs from GitLab API and runs the evaluation pipeline.
"""

import logging
import os
import sys
from argparse import Namespace

from ..parser import add_common_arguments, add_gitlab_arguments
from ...providers.gitlab import GitLabProvider
from ..runners.shared import run_evaluation
from .base import BaseCommand

logger = logging.getLogger(__name__)


class GitLabCommand(BaseCommand):
    """Evaluate using GitLab repository data."""

    @property
    def name(self) -> str:
        return "gitlab"

    @property
    def help(self) -> str:
        return "Evaluate a GitLab project"

    def register(self, subparsers) -> None:
        """Register the gitlab subcommand."""
        parser = subparsers.add_parser(
            self.name,
            help=self.help,
            description="Collect MRs from GitLab API and run evaluation pipeline",
        )

        # GitLab-specific arguments
        add_gitlab_arguments(parser)

        # Common arguments
        add_common_arguments(parser)

        parser.set_defaults(command_obj=self)

    def execute(self, args: Namespace) -> int:
        """Execute the gitlab command."""
        logger.info("=" * 60)
        logger.info("Peer-Eval: GitLab Mode")
        logger.info("=" * 60)

        # Create provider
        provider = GitLabProvider(
            project_id=args.project_id,
            url=args.url,
            token=args.token,
            repo_path=args.repo_path,
            since=args.since,
            until=args.until,
            ssl_verify=not args.no_ssl_verify,
        )

        # Validate configuration
        errors = provider.validate()
        if errors:
            logger.error("GitLab validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return 1

        try:
            # Collect artifacts from GitLab
            logger.info(f"Collecting artifacts from GitLab ({args.project_id})")
            data = provider.collect()
            artifacts = data["artifacts"]
            members = args.members if args.members else None

            logger.info(f"Collected {len(artifacts)} MRs")

            # Run evaluation pipeline
            scores = run_evaluation(
                artifacts=artifacts,
                members=members,
                deadline=args.deadline,
                llm_mode=args.llm_mode,
                anthropic_key=None,  # Will get from env if needed
                output_dir=args.output_dir,
                overrides=args.overrides,
                skip_stage2b=args.skip_stage2b,
                direct_committers=args.direct_committers,
            )

            logger.info("=" * 60)
            logger.info("Evaluation completed successfully")
            logger.info("=" * 60)
            return 0

        except Exception as e:
            logger.error(f"GitLab evaluation failed: {e}", exc_info=True)
            return 1
