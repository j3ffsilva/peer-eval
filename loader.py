"""
File I/O operations for loading artifacts, LLM estimates, and overrides.
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict
from exceptions import FixtureNotFoundError, MissingFieldError

logger = logging.getLogger(__name__)


def load_artifacts(path: str) -> List[Dict]:
    """
    Load MR artifacts from a JSON file.

    Args:
        path: Path to mr_artifacts.json

    Returns:
        List of MR artifact dicts

    Raises:
        FixtureNotFoundError: If file does not exist
        json.JSONDecodeError: If file is not valid JSON
    """
    if not os.path.exists(path):
        raise FixtureNotFoundError(f"Fixture file not found: {path}")

    logger.info(f"Loading artifacts from {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected list of artifacts, got {type(data)}")

    logger.info(f"Loaded {len(data)} artifacts")
    return data


def load_llm_estimates(path: str) -> Optional[List[Dict]]:
    """
    Load LLM estimates from a JSON file.

    Returns None if file does not exist (e.g., first run before stage 2a).

    Args:
        path: Path to mr_llm_estimates.json

    Returns:
        List of LLM estimate dicts, or None if file doesn't exist
    """
    if not os.path.exists(path):
        logger.info(f"LLM estimates file not found: {path} (will be generated)")
        return None

    logger.info(f"Loading LLM estimates from {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected list of estimates, got {type(data)}")

    logger.info(f"Loaded {len(data)} estimates")
    return data


def load_overrides(path: str) -> Optional[Dict]:
    """
    Load professor overrides for MR components.

    Format:
    {
      "MR-1": {"E": 0.4, "A": 0.7},
      "MR-2": {"P": 0.8},
      ...
    }

    Returns None if file does not exist.

    Args:
        path: Path to final_values.json

    Returns:
        Dict mapping MR ID to override dict, or None if file doesn't exist
    """
    if not os.path.exists(path):
        logger.info(f"Overrides file not found: {path}")
        return None

    logger.info(f"Loading overrides from {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected dict of MR overrides, got {type(data)}")

    logger.info(f"Loaded overrides for {len(data)} MRs")
    return data


def save_json(data: object, path: str) -> None:
    """
    Save data to JSON file, creating directories if necessary.

    Args:
        data: Object to serialize
        path: Output file path
    """
    output_dir = os.path.dirname(path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Saving to {path}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved to {path}")
