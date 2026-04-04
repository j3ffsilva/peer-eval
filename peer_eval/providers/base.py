"""Base protocol for evaluation data providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class EvaluationProvider(ABC):
    """
    Abstract base class for data providers (GitLab, GitHub, fixture).

    Implementations must:
    - validate(): Check if all required config is present
    - collect(): Load/fetch artifacts and related data
    """

    @abstractmethod
    def validate(self) -> List[str]:
        """
        Validate that all required configuration is present.

        Returns:
            List of error messages (empty list if valid).
            Example: ["--project-id is required", "--token not found in env"]
        """
        pass

    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """
        Collect and return evaluation input data.

        Returns:
            Dictionary containing:
            {
               "artifacts": List[Dict],  # MR/PR artifacts
               "members": Optional[List[str]],  # Extracted members (optional)
            }
        """
        pass
