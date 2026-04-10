"""Helpers for loading peer-eval environment files."""

from pathlib import Path
from typing import Iterable, Optional, Sequence

from dotenv import load_dotenv

DEFAULT_ENV_FILES = (".peer-eval.env", ".env")


def _extract_env_file_arg(argv: Sequence[str]) -> Optional[str]:
    """Extract the explicit env file path from CLI args, if present."""
    for index, arg in enumerate(argv):
        if arg == "--env-file" and index + 1 < len(argv):
            return argv[index + 1]

        if arg.startswith("--env-file="):
            _, _, value = arg.partition("=")
            return value or None

    return None


def discover_env_files(cwd: Optional[Path] = None) -> Iterable[Path]:
    """Yield the default env file candidates in lookup order."""
    base_dir = cwd or Path.cwd()
    for filename in DEFAULT_ENV_FILES:
        yield base_dir / filename


def load_cli_env(argv: Optional[Sequence[str]] = None) -> Optional[Path]:
    """
    Load environment variables for the CLI.

    Lookup order:
    1. Explicit --env-file path
    2. .peer-eval.env in current working directory
    3. .env in current working directory

    Returns:
        The loaded file path, or None if no env file was found.
    """
    args = list(argv or [])
    explicit_path = _extract_env_file_arg(args)

    candidates = [Path(explicit_path)] if explicit_path else list(discover_env_files())

    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)
            return path.resolve()

    return None
