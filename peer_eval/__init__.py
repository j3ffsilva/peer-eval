"""
Peer-Eval: Contribution Factor Model v3.0

A tool for evaluating student contributions in collaborative projects
using GitLab merge requests, code analysis, and survival metrics.

Features:
- Real-time GitLab data collection
- Quantitative contribution metrics (X, S, Q)
- LLM-powered quality estimation (Cycle 2+)
- Automated member extraction
- Repository-organized output
- CLI-based evaluation

Usage:
    peer-eval --since 2026-03-16 \\
              --until 2026-03-27 \\
              --deadline 2026-03-27T23:59:00Z \\
              --output-dir output/

Environment Variables (.env):
    GITLAB_URL: GitLab instance URL
    GITLAB_TOKEN: Personal Access Token
    GITLAB_PROJECT: Project ID or namespace/repo
    REPO_PATH: Local repository path
    GITLAB_SSL_VERIFY: SSL verification (true/false)
"""

__version__ = "3.0.0"
__author__ = "Jefferson Silva"
__license__ = "MIT"
