"""
CLI entry point for peer-eval v2.0 (refactored with subcommands).

New usage:
    peer-eval init
    peer-eval doctor
    peer-eval fixture --input fixtures/scenario.json --deadline 2026-03-27T23:59:00Z
    peer-eval gitlab --project-id 123 --deadline 2026-03-27T23:59:00Z
    peer-eval github --repo org/repo --deadline 2026-03-27T23:59:00Z
"""

import sys
from peer_eval.cli.dispatcher import main as cli_main


def cli():
    """Entry point for the peer-eval CLI command."""
    exit_code = cli_main()
    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
