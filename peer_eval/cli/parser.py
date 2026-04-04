"""Shared argument parsing utilities for peer-eval CLI."""

import argparse
from typing import Optional


class RawDescriptionHelpFormatterWithDefaults(argparse.RawDescriptionHelpFormatter):
    """Formatter that preserves description formatting and shows defaults."""

    def _get_help_string(self, action):
        help = action.help
        if action.default is not argparse.SUPPRESS and action.default is not None:
            if not isinstance(action, (argparse._StoreAction, argparse._AppendAction)):
                return help
            defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
            if action.nargs not in defaulting_nargs:
                if help and action.default:
                    if "%(default)" not in help:
                        help += f" (default: {action.default})"
        return help


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add arguments common to most subcommands.

    Args:
        parser: ArgumentParser to add arguments to
    """
    parser.add_argument(
        "--deadline",
        required=True,
        help="Project deadline (ISO 8601 format, e.g., 2024-12-01T23:59:00Z)"
    )

    parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to cloned repository (default: current directory)"
    )

    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory for reports (default: output)"
    )

    parser.add_argument(
        "--members",
        nargs="*",
        default=None,
        help="List of team member usernames (auto-extracted from commits if omitted)"
    )

    parser.add_argument(
        "--direct-committers",
        nargs="*",
        default=None,
        help="Members who made direct commits (their scores are zeroed out)"
    )

    parser.add_argument(
        "--overrides",
        default=None,
        metavar="FILE",
        help="Path to professor overrides JSON file"
    )

    parser.add_argument(
        "--llm-mode",
        choices=["live", "dry-run", "skip"],
        default="dry-run",
        help="LLM evaluation mode: live (Claude API), dry-run (mock), skip (none)"
    )

    parser.add_argument(
        "--anthropic-key",
        default=None,
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)"
    )

    parser.add_argument(
        "--skip-stage2b",
        action="store_true",
        default=False,
        help="Skip Stage 2b (group pattern detection)"
    )


def add_gitlab_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add GitLab-specific arguments.

    Args:
        parser: ArgumentParser to add arguments to
    """
    parser.add_argument(
        "--project-id",
        required=True,
        help="GitLab project ID or namespace/repo (e.g., 123 or group/project)"
    )

    parser.add_argument(
        "--url",
        default="https://gitlab.com",
        help="GitLab instance URL (default: https://gitlab.com)"
    )

    parser.add_argument(
        "--token",
        default=None,
        help="GitLab Personal Access Token (or set GITLAB_TOKEN env var)"
    )

    parser.add_argument(
        "--since",
        default=None,
        help="Start date for MR collection (ISO 8601 format)"
    )

    parser.add_argument(
        "--until",
        default=None,
        help="End date for MR collection (ISO 8601 format)"
    )

    parser.add_argument(
        "--no-ssl-verify",
        action="store_true",
        default=False,
        help="Disable SSL verification (for self-signed certificates)"
    )


def add_github_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add GitHub-specific arguments.

    Args:
        parser: ArgumentParser to add arguments to
    """
    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub repository (format: org/repo)"
    )

    parser.add_argument(
        "--url",
        default="https://api.github.com",
        help="GitHub API URL (default: https://api.github.com)"
    )

    parser.add_argument(
        "--token",
        default=None,
        help="GitHub Personal Access Token (or set GITHUB_TOKEN env var)"
    )

    parser.add_argument(
        "--since",
        default=None,
        help="Start date for PR collection (ISO 8601 format)"
    )

    parser.add_argument(
        "--until",
        default=None,
        help="End date for PR collection (ISO 8601 format)"
    )


def add_fixture_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add fixture-specific arguments.

    Args:
        parser: ArgumentParser to add arguments to
    """
    parser.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Path to MR artifacts fixture JSON file"
    )
