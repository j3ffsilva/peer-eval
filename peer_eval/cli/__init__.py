"""
CLI module for peer-eval.

This module provides the refactored subcommand-based interface:
- peer-eval init
- peer-eval doctor
- peer-eval gitlab
- peer-eval github
- peer-eval fixture
"""

import sys


def cli():
    """Entry point for the peer-eval CLI command."""
    from .dispatcher import main as cli_main
    exit_code = cli_main()
    sys.exit(exit_code)


__all__ = ["cli"]
