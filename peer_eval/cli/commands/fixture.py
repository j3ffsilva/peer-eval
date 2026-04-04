"""
'peer-eval fixture' command — evaluate using local fixture file.

Loads predefined MR artifacts and runs the evaluation pipeline.
"""

import logging
import os
import sys
from argparse import Namespace

from ...configuration.loader import load_config
from ..parser import add_common_arguments, add_fixture_arguments
from ...providers.fixture import FixtureProvider
from ..runners.shared import run_evaluation
from .base import BaseCommand

logger = logging.getLogger(__name__)


class FixtureCommand(BaseCommand):
    """Evaluate using a local JSON fixture file."""

    @property
    def name(self) -> str:
        return "fixture"

    @property
    def help(self) -> str:
        return "Evaluate using a local fixture file"

    def register(self, subparsers) -> None:
        """Register the fixture subcommand."""
        parser = subparsers.add_parser(
            self.name,
            help=self.help,
            description="Run evaluation pipeline with a local JSON fixture (no external API calls)",
        )

        # Fixture-specific arguments
        add_fixture_arguments(parser)

        # Common arguments
        add_common_arguments(parser)

        parser.set_defaults(command_obj=self)

    def execute(self, args: Namespace) -> int:
        """Execute the fixture command."""
        logger.info("=" * 60)
        logger.info("Peer-Eval: Fixture Mode")
        logger.info("=" * 60)

        # Validate input file
        provider = FixtureProvider(args.input)
        errors = provider.validate()

        if errors:
            logger.error("Fixture validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return 1

        try:
            # Collect artifacts from fixture
            logger.info(f"Loading fixtures from {args.input}")
            data = provider.collect()
            artifacts = data["artifacts"]
            members = args.members if args.members else None

            logger.info(f"Loaded {len(artifacts)} artifacts")

            # Resolve anthropic_key: CLI args > environment > None
            anthropic_key = args.anthropic_key or os.getenv("ANTHROPIC_API_KEY")

            # Run evaluation pipeline
            scores = run_evaluation(
                artifacts=artifacts,
                members=members,
                deadline=args.deadline,
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
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            return 1
