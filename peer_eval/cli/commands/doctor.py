"""
'peer-eval doctor' command — quick environment diagnostic.

Checks Python version, package installation, config files, and credentials.
"""

import os
import sys
import platform
from argparse import ArgumentParser, Namespace
from pathlib import Path

from ..env import discover_env_files
from .base import BaseCommand


class DoctorCommand(BaseCommand):
    """Run diagnostics on the peer-eval environment."""

    @property
    def name(self) -> str:
        return "doctor"

    @property
    def help(self) -> str:
        return "Diagnose environment and configuration"

    def register(self, subparsers) -> None:
        """Register the doctor subcommand."""
        parser = subparsers.add_parser(
            self.name,
            help=self.help,
            description="Quick diagnostic of peer-eval environment"
        )
        parser.set_defaults(command_obj=self)

    def execute(self, args: Namespace) -> int:
        """Execute the doctor command."""
        print("Peer-Eval Doctor\n")

        # Python environment
        print("Environment")
        print(f"  Python: {sys.version.split()[0]} ({platform.python_implementation()})")
        print(f"  Executable: {sys.executable}")
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        print(f"  Virtual env: {'✓' if in_venv else '✗'}")
        print()

        # Peer-eval package
        print("Package")
        try:
            import peer_eval
            print(f"  peer-eval: {getattr(peer_eval, '__version__', 'unknown')}")
        except ImportError:
            print("  peer-eval: ✗ not installed")
        print()

        # Project configuration
        print("Configuration")
        config_exists = Path(".peer-eval.toml").exists()
        env_candidates = list(discover_env_files())
        env_path = next((path for path in env_candidates if path.exists()), None)
        print(f"  .peer-eval.toml: {'✓' if config_exists else '✗'}")
        print(f"  env file: {'✓ ' + env_path.name if env_path else '✗'}")
        print()

        # Credentials
        print("Credentials")
        gitlab_token = bool(os.getenv("GITLAB_TOKEN"))
        github_token = bool(os.getenv("GITHUB_TOKEN"))
        anthropic_key = bool(os.getenv("ANTHROPIC_API_KEY"))
        print(f"  GITLAB_TOKEN: {'✓' if gitlab_token else '✗'}")
        print(f"  GITHUB_TOKEN: {'✓' if github_token else '✗'}")
        print(f"  ANTHROPIC_API_KEY: {'✓' if anthropic_key else '✗'}")

        return 0
