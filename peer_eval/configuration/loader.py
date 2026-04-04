"""Configuration loader with precedence: CLI > .toml > .env > defaults."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Try to import tomllib (Python 3.11+) or fallback to tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


def load_toml_config(toml_path: str = ".peer-eval.toml") -> Dict[str, Any]:
    """
    Load configuration from .peer-eval.toml file.

    Args:
        toml_path: Path to TOML config file

    Returns:
        Configuration dictionary (empty if file not found or no tomllib)
    """
    if not tomllib:
        logger.debug("tomllib not available, skipping TOML config")
        return {}

    path = Path(toml_path)
    if not path.exists():
        logger.debug(f"No {toml_path} found")
        return {}

    try:
        with open(path, "rb") as f:
            config = tomllib.load(f)
        logger.debug(f"Loaded config from {toml_path}")
        return config
    except Exception as e:
        logger.warning(f"Failed to load {toml_path}: {e}")
        return {}


def load_env_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables.

    Returns:
        Dictionary with env-based config
    """
    config = {}

    # GitLab credentials
    if gitlab_url := os.getenv("GITLAB_URL"):
        if "gitlab" not in config:
            config["gitlab"] = {}
        config["gitlab"]["url"] = gitlab_url

    if gitlab_token := os.getenv("GITLAB_TOKEN"):
        if "auth" not in config:
            config["auth"] = {}
        config["auth"]["gitlab_token_value"] = gitlab_token  # Hidden from TOML

    # GitHub credentials
    if github_token := os.getenv("GITHUB_TOKEN"):
        if "auth" not in config:
            config["auth"] = {}
        config["auth"]["github_token_value"] = github_token

    # Anthropic credentials
    if anthropic_key := os.getenv("ANTHROPIC_API_KEY"):
        if "auth" not in config:
            config["auth"] = {}
        config["auth"]["anthropic_key_value"] = anthropic_key

    if config:
        logger.debug("Loaded environment variables")

    return config


def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge multiple config dictionaries.

    Later arguments override earlier ones.
    Only set values if they exist (to preserve None defaults).

    Args:
        configs: Variable number of config dicts

    Returns:
        Merged configuration
    """
    result = {}
    for config in configs:
        if not config:
            continue
        for key, value in config.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = {**result[key], **value}
            else:
                result[key] = value
    return result


def load_config(
    toml_path: str = ".peer-eval.toml",
    load_env: bool = True,
) -> Dict[str, Any]:
    """
    Load configuration from multiple sources.

    Precedence:
    1. CLI arguments (caller must pass separately)
    2. .peer-eval.toml
    3. .env environment variables
    4. Hardcoded defaults

    Args:
        toml_path: Path to TOML config file
        load_env: Whether to load from environment

    Returns:
        Merged configuration dictionary
    """
    toml_config = load_toml_config(toml_path)
    env_config = load_env_config() if load_env else {}

    # Merge with TOML having precedence over ENV
    merged = merge_configs(env_config, toml_config)
    return merged


def get_from_config(
    config: Dict[str, Any],
    path: str,
    default: Any = None,
) -> Any:
    """
    Get a nested value from config dict using dot notation.

    Args:
        config: Configuration dictionary
        path: Dot-separated path (e.g., "gitlab.url")
        default: Default value if not found

    Returns:
        Config value or default
    """
    keys = path.split(".")
    current = config

    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default

    return current
