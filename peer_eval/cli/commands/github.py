"""
'peer-eval github' command — evaluate using GitHub data.

Placeholder for future GitHub support.
"""

import logging
from argparse import Namespace

from ..parser import add_common_arguments, add_github_arguments
from ...providers.github import GitHubProvider
from .base import BaseCommand

logger = logging.getLogger(__name__)


class GitHubCommand(BaseCommand):
    """Evaluate using GitHub repository data (not yet implemented)."""

    @property
    def name(self) -> str:
        return "github"

    @property
    def help(self) -> str:
        return "Evaluate a GitHub repository (not yet implemented)"

    def register(self, subparsers) -> None:
        """Register the github subcommand."""
        parser = subparsers.add_parser(
            self.name,
            help=self.help,
            description="Collect PRs from GitHub API and run evaluation (STUB - not implemented)",
        )

        # GitHub-specific arguments
        add_github_arguments(parser)

        # Common arguments
        add_common_arguments(parser)

        parser.set_defaults(command_obj=self)

    def execute(self, args: Namespace) -> int:
        """Execute the github command."""
        logger.info("=" * 60)
        logger.info("GitHub Provider - Not Yet Implemented")
        logger.info("=" * 60)
        logger.error(
            "GitHub provider is not yet implemented. "
            "Please use 'peer-eval gitlab ...' or 'peer-eval fixture ...' for now."
        )
        return 1
