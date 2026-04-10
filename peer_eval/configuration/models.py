"""Configuration data models for peer-eval."""

from dataclasses import dataclass, field
from typing import Optional, Literal, List


@dataclass
class ProjectConfig:
    """Project-level configuration."""

    id: str
    """Project identifier (e.g., 'G03')."""

    repo_path: str = "."
    """Path to repository (default: current directory)."""

    deadline: Optional[str] = None
    """Project deadline (ISO 8601 format)."""

    since: Optional[str] = None
    """Start date for evaluation period (ISO 8601 format)."""

    until: Optional[str] = None
    """End date for evaluation period (ISO 8601 format)."""

    output_dir: str = "output"
    """Directory for output reports."""


@dataclass
class LLMConfig:
    """LLM evaluation configuration."""

    mode: Literal["live", "dry-run", "skip"] = "dry-run"
    """LLM mode: live (Anthropic API), dry-run (mock), skip (none)."""


@dataclass
class GitLabConfig:
    """GitLab-specific configuration."""

    url: str = "https://gitlab.com"
    """GitLab instance URL."""

    project_id: Optional[str] = None
    """GitLab project ID or namespace/repo."""

    ssl_verify: bool = True
    """Whether to verify SSL certificates."""


@dataclass
class GitHubConfig:
    """GitHub-specific configuration."""

    url: str = "https://api.github.com"
    """GitHub API URL."""

    repo: Optional[str] = None
    """GitHub repository (org/repo format)."""


@dataclass
class EvaluationConfig:
    """Full evaluation configuration."""

    project: ProjectConfig
    llm: LLMConfig = field(default_factory=LLMConfig)
    gitlab: GitLabConfig = field(default_factory=GitLabConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)

    # Evaluation-specific options
    members: Optional[List[str]] = None
    """List of team member usernames."""

    direct_committers: Optional[List[str]] = None
    """Members who made direct commits (zeroed out)."""

    overrides_file: Optional[str] = None
    """Path to professor overrides JSON."""

    skip_stage2b: bool = False
    """Skip Stage 2b (group pattern detection)."""
