"""
Fixture data provider — loads artifacts from JSON file.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from .base import EvaluationProvider

logger = logging.getLogger(__name__)


class FixtureProvider(EvaluationProvider):
    """Load MR artifacts from a local JSON fixture file."""

    def __init__(self, input_file: str):
        """
        Initialize the fixture provider.

        Args:
            input_file: Path to JSON fixture file
        """
        self.input_file = Path(input_file)

    def validate(self) -> List[str]:
        """
        Validate that the fixture file exists and is readable.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not self.input_file.exists():
            errors.append(f"Fixture file not found: {self.input_file}")
            return errors

        if not self.input_file.is_file():
            errors.append(f"Not a file: {self.input_file}")
            return errors

        # Try to load to check validity
        try:
            with open(self.input_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                errors.append("Fixture must contain a JSON array of MR artifacts")
            elif not data:
                errors.append("Fixture is empty")
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in fixture: {e}")
        except Exception as e:
            errors.append(f"Failed to read fixture: {e}")

        return errors

    def collect(self) -> Dict[str, Any]:
        """
        Load and return artifacts from the fixture file.

        Returns:
            Dictionary with "artifacts" key containing list of MR dicts
        """
        try:
            with open(self.input_file, "r", encoding="utf-8") as f:
                artifacts = json.load(f)
            logger.info(f"Loaded {len(artifacts)} artifacts from {self.input_file}")
            return {
                "artifacts": artifacts,
                "members": None,  # Will be auto-extracted if not provided
            }
        except Exception as e:
            logger.error(f"Failed to load fixture: {e}")
            raise
