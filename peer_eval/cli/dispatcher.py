"""
Main entry point and command dispatcher for peer-eval.

This module orchestrates subcommand registration and dispatch.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """
    Create the main argument parser with all subcommands.

    Returns:
        ArgumentParser for the CLI
    """
    parser = argparse.ArgumentParser(
        prog="peer-eval",
        description=(
            "Contribution Factor Model v3.0 — Evaluate student contributions\n"
            "Choose a data source: gitlab, github, fixture, or use utilities: init, doctor"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0"  # TODO: Read from __version__
    )

    parser.add_argument(
        "--env-file",
        help=(
            "Load credentials from a specific env file. "
            "If omitted, peer-eval tries .peer-eval.env and then .env in the current directory."
        ),
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest="command",
        help="Command to execute"
    )

    # Import and register commands
    _register_commands(subparsers)

    return parser


def _register_commands(subparsers) -> None:
    """
    Register all available subcommands.

    Args:
        subparsers: argparse subparsers object
    """
    # Lazy import to avoid circular dependencies
    from .commands.init import InitCommand
    from .commands.doctor import DoctorCommand
    from .commands.gitlab import GitLabCommand
    from .commands.github import GitHubCommand
    from .commands.fixture import FixtureCommand

    commands = [
        InitCommand(),
        DoctorCommand(),
        GitLabCommand(),
        GitHubCommand(),
        FixtureCommand(),
    ]

    for cmd in commands:
        cmd.register(subparsers)


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        argv: Command-line arguments (if None, use sys.argv[1:])

    Returns:
        Exit code (0 for success, 1+ for error)
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    try:
        # Dynamic import and execution of command
        command_name = args.command
        if command_name == "init":
            from .commands.init import InitCommand
            cmd = InitCommand()
        elif command_name == "doctor":
            from .commands.doctor import DoctorCommand
            cmd = DoctorCommand()
        elif command_name == "gitlab":
            from .commands.gitlab import GitLabCommand
            cmd = GitLabCommand()
        elif command_name == "github":
            from .commands.github import GitHubCommand
            cmd = GitHubCommand()
        elif command_name == "fixture":
            from .commands.fixture import FixtureCommand
            cmd = FixtureCommand()
        else:
            logger.error(f"Unknown command: {command_name}")
            return 1

        return cmd.execute(args)

    except KeyboardInterrupt:
        print("\n❌ Interrupted by user")
        return 130  # Standard Unix exit code for SIGINT
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 2
