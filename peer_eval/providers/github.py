"""
GitHub data provider — collects PR artifacts from GitHub API.

Currently a stub; can be extended in future releases.
"""

import logging
import os
from typing import List, Dict, Any, Optional

from .base import EvaluationProvider

logger = logging.getLogger(__name__)


class GitHubProvider(EvaluationProvider):
    """Collect PR artifacts from GitHub (stub implementation)."""

    def __init__(
        self,
        repo: str,
        url: str = "https://api.github.com",
        token: Optional[str] = None,
        token_env: str = "GITHUB_TOKEN",
        repo_path: str = ".",
        since: Optional[str] = None,
        until: Optional[str] = None,
    ):
        """
        Initialize GitHub provider.

        Args:
            repo: GitHub repository (org/repo format)
            url: GitHub API URL
            token: Personal access token (if None, reads from env)
            token_env: Env var name for token
            repo_path: Path to cloned repository
            since: Start date (ISO 8601)
            until: End date (ISO 8601)
        """
        self.repo = repo
        self.url = url
        self.token = token or os.getenv(token_env)
        self.repo_path = repo_path
        self.since = since
        self.until = until

    def validate(self) -> List[str]:
        """
        Validate that all required GitHub parameters are present.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not self.repo:
            errors.append("--repo is required for github mode (format: org/repo)")

        if not self.token:
            errors.append(
                f"GitHub token required. "
                f"Provide via --token or set GITHUB_TOKEN env var"
            )

        if not self.since:
            errors.append("--since is required for github mode (ISO 8601 format)")

        if not self.until:
            errors.append("--until is required for github mode (ISO 8601 format)")

        errors.append("GitHub provider is not yet implemented. Use --fixture or --gitlab mode.")

        return errors

    def collect(self) -> Dict[str, Any]:
        """
        Collect PR artifacts from GitHub API.

        Returns:
            Dictionary with "artifacts" and "members" keys

        Raises:
            NotImplementedError: GitHub support not yet available
        """
        raise NotImplementedError(
            "GitHub provider is not yet implemented. "
            "Use 'peer-eval gitlab ...' or 'peer-eval fixture ...' for now."
        )
