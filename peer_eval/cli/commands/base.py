"""Abstract base class for CLI commands."""

from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from typing import Optional


class BaseCommand(ABC):
    """
    Abstract base class for all peer-eval subcommands.

    Subclasses must implement:
    - register(): Register the command with argparse subparsers
    - execute(): Execute the command logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the command name (e.g., 'gitlab', 'fixture')."""
        pass

    @property
    @abstractmethod
    def help(self) -> str:
        """Return short help text for this command."""
        pass

    @abstractmethod
    def register(self, subparsers) -> None:
        """
        Register this command with argparse subparsers.

        Args:
            subparsers: argparse._SubParsersAction object
        """
        pass

    @abstractmethod
    def execute(self, args: Namespace) -> int:
        """
        Execute the command.

        Args:
            args: Parsed command-line arguments

        Returns:
            Exit code (0 for success, 1+ for error)
        """
        pass
