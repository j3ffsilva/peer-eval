"""
GitLab data provider — collects MR artifacts from GitLab API.
"""

import logging
import os
from typing import List, Dict, Any, Optional

from .base import EvaluationProvider

logger = logging.getLogger(__name__)


class GitLabProvider(EvaluationProvider):
    """Collect MR artifacts from GitLab."""

    def __init__(
        self,
        project_id: str,
        url: str = "https://gitlab.com",
        token: Optional[str] = None,
        token_env: str = "GITLAB_TOKEN",
        repo_path: str = ".",
        since: Optional[str] = None,
        until: Optional[str] = None,
        ssl_verify: bool = True,
    ):
        """
        Initialize GitLab provider.

        Args:
            project_id: GitLab project ID or namespace/repo
            url: GitLab instance URL
            token: Personal access token (if None, reads from env)
            token_env: Env var name for token
            repo_path: Path to cloned repository
            since: Start date (ISO 8601)
            until: End date (ISO 8601)
            ssl_verify: Whether to verify SSL
        """
        self.project_id = project_id
        self.url = url
        self.token = token or os.getenv(token_env)
        self.repo_path = repo_path
        self.since = since
        self.until = until
        self.ssl_verify = ssl_verify

    def validate(self) -> List[str]:
        """
        Validate that all required GitLab parameters are present.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not self.project_id:
            errors.append("--project-id is required for gitlab mode")

        if not self.token:
            errors.append(
                f"GitLab token required. "
                f"Provide via --token or set {os.getenv('GITLAB_TOKEN') and 'GITLAB_TOKEN' or 'GITLAB_TOKEN'} env var"
            )

        if not self.since:
            errors.append("--since is required for gitlab mode (ISO 8601 format)")

        if not self.until:
            errors.append("--until is required for gitlab mode (ISO 8601 format)")

        return errors

    def collect(self) -> Dict[str, Any]:
        """
        Collect MR artifacts from GitLab API.

        Returns:
            Dictionary with "artifacts" and "members" keys

        Raises:
            ImportError: If collector module is not available
            Exception: If GitLab API call fails
        """
        # Lazy import from existing collector module
        try:
            from .. import collector
        except ImportError:
            raise ImportError(
                "Failed to import collector module. "
                "Ensure peer_eval package is properly installed."
            )

        logger.info(f"Collecting artifacts from GitLab ({self.project_id})")

        artifacts = collector.collect(
            gitlab_url=self.url,
            project_id=self.project_id,
            token=self.token,
            repo_path=self.repo_path,
            since=self.since,
            until=self.until,
            output_path=None,  # Don't save intermediate output
            ssl_verify=self.ssl_verify,
        )

        return {
            "artifacts": artifacts,
            "members": None,  # Will be auto-extracted
        }
