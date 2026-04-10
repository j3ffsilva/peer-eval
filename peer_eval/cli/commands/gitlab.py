"""
'peer-eval gitlab' command — evaluate using GitLab data.

Collects MRs from GitLab API and runs the evaluation pipeline.
"""

import logging
import os
import sys
from argparse import Namespace

from ..parser import add_common_arguments, add_gitlab_arguments
from ..resolution import load_project_config, resolve_gitlab_options
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

        try:
            config = load_project_config()
            resolved = resolve_gitlab_options(args, config)
        except ValueError as e:
            logger.error(str(e))
            return 1

        if resolved["sprint_numbers"]:
            logger.info(
                "Resolved sprint window %s -> %s from sprint(s) %s",
                resolved["since"],
                resolved["until"],
                ", ".join(str(number) for number in resolved["sprint_numbers"]),
            )

        # Create provider
        provider = GitLabProvider(
            project_id=resolved["project_id"],
            url=resolved["url"],
            token=args.token or os.getenv("GITLAB_TOKEN"),
            repo_path=args.repo_path,
            since=resolved["since"],
            until=resolved["until"],
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
            logger.info(f"Collecting artifacts from GitLab ({resolved['project_id']})")
            data = provider.collect()
            artifacts = data["artifacts"]
            members = args.members if args.members else None

            logger.info(f"Collected {len(artifacts)} MRs")

            # Resolve anthropic_key: CLI args > environment > None
            anthropic_key = args.anthropic_key or os.getenv("ANTHROPIC_API_KEY")

            # Run evaluation pipeline
            scores = run_evaluation(
                artifacts=artifacts,
                members=members,
                deadline=resolved["deadline"],
                llm_mode=args.llm_mode,
                anthropic_key=anthropic_key,
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
