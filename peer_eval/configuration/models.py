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

    anthropic_key_env: str = "ANTHROPIC_API_KEY"
    """Environment variable name for Anthropic API key."""


@dataclass
class GitLabConfig:
    """GitLab-specific configuration."""

    url: str = "https://gitlab.com"
    """GitLab instance URL."""

    project_id: Optional[str] = None
    """GitLab project ID or namespace/repo."""

    token_env: str = "GITLAB_TOKEN"
    """Environment variable name for GitLab token."""

    ssl_verify: bool = True
    """Whether to verify SSL certificates."""


@dataclass
class GitHubConfig:
    """GitHub-specific configuration."""

    url: str = "https://api.github.com"
    """GitHub API URL."""

    repo: Optional[str] = None
    """GitHub repository (org/repo format)."""

    token_env: str = "GITHUB_TOKEN"
    """Environment variable name for GitHub token."""


@dataclass
class AuthConfig:
    """Authentication configuration."""

    gitlab_token_env: str = "GITLAB_TOKEN"
    """Env var for GitLab token."""

    github_token_env: str = "GITHUB_TOKEN"
    """Env var for GitHub token."""

    anthropic_key_env: str = "ANTHROPIC_API_KEY"
    """Env var for Anthropic API key."""


@dataclass
class EvaluationConfig:
    """Full evaluation configuration."""

    project: ProjectConfig
    llm: LLMConfig = field(default_factory=LLMConfig)
    gitlab: GitLabConfig = field(default_factory=GitLabConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)

    # Evaluation-specific options
    members: Optional[List[str]] = None
    """List of team member usernames."""

    direct_committers: Optional[List[str]] = None
    """Members who made direct commits (zeroed out)."""

    overrides_file: Optional[str] = None
    """Path to professor overrides JSON."""

    skip_stage2b: bool = False
    """Skip Stage 2b (group pattern detection)."""
