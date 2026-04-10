"""
GitLab contribution data collector — Cycle 2: Real data integration.

Collects MR artifacts from GitLab.com (or self-hosted) API and local git repository,
enriching with git blame, approvals, comments, and linked issues.

Main entry point:
    collect(gitlab_url, project_id, token, repo_path, since, until, output_path, ssl_verify)

This module bridges real GitLab projects with the contribution model.
All artifacts are saved in the schema compatible with the scorer.

Supports both gitlab.com and self-hosted GitLab instances.
For self-hosted with self-signed certificates, set ssl_verify=False.
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from fnmatch import fnmatch

import git
import gitlab
from tenacity import retry, stop_after_attempt, wait_exponential

from . import config
from . import model

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# RetryDecorator for API rate limiting
# ═══════════════════════════════════════════════════════════════════════════


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def _api_call_with_retry(fn):
    """Wrapper for API calls with exponential backoff on rate limiting."""
    return fn()


# ═══════════════════════════════════════════════════════════════════════════
# Core public interface
# ═══════════════════════════════════════════════════════════════════════════


def collect(
    gitlab_url: str,
    project_id: str,
    token: str,
    repo_path: str,
    since: str,
    until: str,
    output_path: str = "output/mr_artifacts.json",
    ssl_verify: bool = True
) -> List[Dict[str, Any]]:
    """
    Collect MR artifacts from GitLab and local git, save to output_path.

    Args:
        gitlab_url: GitLab instance URL (e.g., "https://gitlab.com" or "https://gitlab.your-org.edu.br")
        project_id: Project ID or namespace/repo (e.g., "123" or "group/project")
        token: Personal Access Token with 'api' scope
        repo_path: Absolute path to cloned repository
        since: ISO 8601 start date (e.g., "2024-09-01T00:00:00Z")
        until: ISO 8601 end date (e.g., "2024-12-01T23:59:59Z")
        output_path: Where to save JSON artifacts (default: "output/mr_artifacts.json")
        ssl_verify: Whether to verify SSL certificates (False for self-signed certs)

    Returns:
        List of mr_artifact dicts
    """
    logger.info("=" * 70)
    logger.info(f"Collecting from {gitlab_url}/{project_id}")
    logger.info(f"  Period: {since} to {until}")
    logger.info(f"  Repo: {repo_path}")
    logger.info("=" * 70)

    # Verify repo exists
    if not Path(repo_path).exists():
        raise RuntimeError(f"Repository not found: {repo_path}")

    # Connect to GitLab
    try:
        gl = gitlab.Gitlab(gitlab_url, private_token=token, ssl_verify=ssl_verify)
        gl.auth()
        logger.info("✓ GitLab authentication successful")

        if not ssl_verify:
            logger.warning(
                "⚠️  SSL verification is DISABLED. "
                "Use only in trusted academic environments with self-signed certificates."
            )
    except gitlab.exceptions.GitlabAuthenticationError as e:
        raise RuntimeError(f"GitLab auth failed (401): {e}")
    except gitlab.exceptions.GitlabGetError as e:
        raise RuntimeError(f"GitLab connection failed (404): {e}")

    # Get project
    try:
        project = gl.projects.get(project_id)
        logger.info(f"✓ Project loaded: {project.name_with_namespace}")
    except gitlab.exceptions.GitlabGetError:
        raise RuntimeError(f"Project not found: {project_id}")

    # Fetch merged MRs
    mrs = _fetch_merged_mrs(project, since, until)
    logger.info(f"Found {len(mrs)} merged MRs in period")

    # Repository
    repo = git.Repo(repo_path)

    # Process each MR
    artifacts = []
    for mr in mrs:
        logger.info(f"  Processing MR-{mr.iid}: {mr.title[:50]}")

        try:
            # Fetch full MR object to get all attributes (diff_refs, approvals, etc.)
            # list() returns lightweight objects; we need get() for full data
            mr = _api_call_with_retry(lambda iid=mr.iid: project.mergerequests.get(iid))

            changes = _fetch_changes(project, mr)
            approvals = _fetch_approvals(project, mr)
            comments = _fetch_comments(project, mr)
            linked_issues = _fetch_linked_issues(project, mr)
            quantitative = _compute_quantitative(changes, mr, repo)
            commit_log = _collect_commit_log(repo, mr)

            mr_id = f"MR-{mr.iid}"
            type_declared = _extract_type_declared(mr.title)
            author = mr.author["username"] if mr.author else "unknown"

            # Split diff_summary: files with excerpt carry full data;
            # files without excerpt (empty diff or binary) are stored as a
            # flat list of paths to avoid sending useless zero-field objects
            # to the LLM.
            changes_with_excerpt = [
                c for c in changes if c.get("content_excerpt", "").strip()
            ]
            changes_other_files = [
                c["file"] for c in changes if not c.get("content_excerpt", "").strip()
            ]

            artifact = {
                "mr_id": mr_id,
                "author": author,
                "title": mr.title,
                "description": mr.description or "",
                "type_declared": type_declared,
                "opened_at": mr.created_at,
                "merged_at": mr.merged_at,
                "deadline": None,  # provided via CLI
                "linked_issues": linked_issues,
                "diff_summary": changes_with_excerpt,
                "diff_summary_other_files": changes_other_files,
                "review_comments": comments,
                "reviewers": approvals,
                "quantitative": quantitative,
                "commit_log": commit_log,
            }

            logger.debug(
                f"    X={quantitative['X']:.3f} "
                f"S={quantitative['S']:.3f} "
                f"Q={quantitative['Q']:.1f}"
            )

            artifacts.append(artifact)

        except Exception as e:
            logger.warning(f"  ✗ MR-{mr.iid} failed: {e}")
            continue

    # Save artifacts only when an output path is provided
    if output_path is not None:
        _save_artifacts(artifacts, output_path)

        logger.info("=" * 70)
        logger.info(f"✓ Artifacts saved to {output_path}")
        logger.info("=" * 70)
    else:
        logger.info("=" * 70)
        logger.info("✓ Artifacts collected (no intermediate file requested)")
        logger.info("=" * 70)

    return artifacts


# ═══════════════════════════════════════════════════════════════════════════
# Internal functions — MR fetching
# ═══════════════════════════════════════════════════════════════════════════


def _fetch_merged_mrs(project, since: str, until: str) -> List:
    """
    Fetch merged MRs from GitLab in date range.

    Args:
        project: python-gitlab Project object
        since: ISO 8601 start date
        until: ISO 8601 end date

    Returns:
        List of python-gitlab MergeRequest objects
    """
    try:
        # Query with updated_after/before for efficiency
        mrs = _api_call_with_retry(
            lambda: project.mergerequests.list(
                state="merged",
                updated_after=since,
                updated_before=until,
                all=True,
                order_by="updated_at",
            )
        )

        # Filter to ensure merged_at is actually in period
        filtered = [
            mr for mr in mrs
            if mr.merged_at and since <= mr.merged_at <= until
        ]

        return filtered

    except Exception as e:
        logger.error(f"Failed to fetch merged MRs: {e}")
        raise


def _fetch_changes(project, mr) -> List[Dict[str, Any]]:
    """
    Fetch diff for an MR, extract additions/deletions and content excerpt.

    Args:
        project: python-gitlab Project object
        mr: python-gitlab MergeRequest object

    Returns:
        List of {file, additions, deletions, content_excerpt}
    """
    try:
        changes = _api_call_with_retry(lambda: mr.changes())
    except Exception as e:
        logger.warning(f"  Could not fetch changes for MR-{mr.iid}: {e}")
        return []

    diff_summary = []

    for change in changes.get("changes", []):
        file_path = change["new_path"]

        # Skip ignored patterns
        if _should_ignore(file_path):
            continue

        # Parse additions/deletions from diff text.
        # The /merge_requests/:id/changes endpoint does NOT return these as
        # separate fields — change.get("additions", 0) always returns 0.
        diff_text = change.get("diff", "")
        additions = sum(
            1 for line in diff_text.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        deletions = sum(
            1 for line in diff_text.splitlines()
            if line.startswith("-") and not line.startswith("---")
        )
        content_excerpt = _extract_content_excerpt(diff_text)

        diff_summary.append(
            {
                "file": file_path,
                "additions": additions,
                "deletions": deletions,
                "content_excerpt": content_excerpt,
            }
        )

    return diff_summary


def _fetch_approvals(project, mr) -> List[str]:
    """
    Fetch list of usernames who approved the MR.

    Args:
        project: python-gitlab Project object
        mr: python-gitlab MergeRequest object (should be full object from get())

    Returns:
        List of usernames (strings)
    """
    try:
        # Note: mr should be a full object from get(), not from list()
        # Access approvals directly from the MR object
        approvals_data = getattr(mr, "approvals", None)

        if not approvals_data:
            return []

        # approvals_data can be a dict or object
        if isinstance(approvals_data, dict):
            approved_by = approvals_data.get("approved_by", [])
        else:
            approved_by = getattr(approvals_data, "approved_by", [])

        usernames = [
            u.get("user", u)["username"] if isinstance(u, dict) else u.user.username
            for u in approved_by
        ]
        return usernames

    except Exception as e:
        logger.warning(f"  Could not fetch approvals for MR-{mr.iid}: {e}")
        return []


def _fetch_comments(project, mr) -> List[Dict[str, str]]:
    """
    Fetch review comments and approvals for an MR.

    Args:
        project: python-gitlab Project object
        mr: python-gitlab MergeRequest object

    Returns:
        List of {author, type, body, created_at}
    """
    try:
        notes = _api_call_with_retry(lambda: mr.notes.list(all=True))
    except Exception as e:
        logger.warning(f"  Could not fetch comments for MR-{mr.iid}: {e}")
        return []

    comments = []
    for note in notes:
        # Skip system notes
        if note.system:
            continue

        # Determine type: approval or comment
        is_approval = note.body.lower().startswith("approved")
        note_type = "approval" if is_approval else "comment"

        comments.append(
            {
                "author": note.author["username"],
                "type": note_type,
                "body": note.body[:500],  # truncate to 500 chars
                "created_at": note.created_at,
            }
        )

    return comments


def _fetch_linked_issues(project, mr) -> List[Dict[str, Any]]:
    """
    Parse linked issues from MR description (Closes #N, Fixes #N, etc).

    Args:
        project: python-gitlab Project object
        mr: python-gitlab MergeRequest object

    Returns:
        List of {id, title, created_at, mr_opened_at}
    """
    description = mr.description or ""

    # Regex: case-insensitive match for "closes #N", "fixes #N", etc.
    pattern = r"(?:closes?|fixes?|resolves?)\s+#(\d+)"
    issue_ids = re.findall(pattern, description, re.IGNORECASE)

    linked_issues = []
    for issue_iid in issue_ids:
        try:
            issue = _api_call_with_retry(
                lambda iid=issue_iid: project.issues.get(iid)
            )

            linked_issues.append(
                {
                    "id": issue.iid,
                    "title": issue.title,
                    "created_at": issue.created_at,
                    "mr_opened_at": mr.created_at,
                }
            )

        except Exception as e:
            logger.warning(f"  Could not fetch issue #{issue_iid}: {e}")
            continue

    return linked_issues


# ═══════════════════════════════════════════════════════════════════════════
# Internal functions — Quantitative calculations
# ═══════════════════════════════════════════════════════════════════════════


def _compute_quantitative(
    changes: List[Dict], mr, repo: git.Repo
) -> Dict[str, float]:
    """
    Compute quantitative components X, S, Q for MR.

    Args:
        changes: List of {file, additions, deletions, content_excerpt}
        mr: python-gitlab MergeRequest object
        repo: gitpython Repo object

    Returns:
        Dict with {X, S, Q} rounded to 3-4 decimals
    """
    # X(k) — technical effort
    total_lines = sum(c["additions"] for c in changes)
    total_files = len(changes)
    modules = set(_extract_module(c["file"]) for c in changes)
    n_modules = len(modules)

    X = model.calc_x(total_lines, total_files, n_modules)

    # S(k) — survival via git blame
    S = _compute_survival(changes, mr, repo)

    # Q(k) — CI quality
    Q = _compute_ci_quality(mr)

    return {
        "X": round(X, 4),
        "S": round(S, 4),
        "Q": Q,
    }


def _extract_module(file_path: str) -> str:
    """
    Extract root module name from file path.

    Examples:
        "domain/payment.py" → "domain"
        "src/domain/payment.py" → "src"
        "payment.py" → "root"

    Args:
        file_path: Full file path

    Returns:
        Module name (string)
    """
    parts = Path(file_path).parts
    if len(parts) > 1:
        return parts[0]
    else:
        return "root"


def _compute_survival(changes: List[Dict], mr, repo: git.Repo) -> float:
    """
    Compute S(k) — survival rate via git blame.

    Counts lines remanescentes / linhas adicionadas using git blame on HEAD.

    Args:
        changes: List of file changes
        mr: python-gitlab MergeRequest object
        repo: gitpython Repo object

    Returns:
        Survival score in [0, 1]
    """
    try:
        # Get MR commits
        mr_commits = _get_mr_commits(repo, mr)
        if not mr_commits:
            logger.warning(f"  Could not identify MR-{mr.iid} commits, assuming S=1.0")
            return 1.0

        mr_commit_shas = {c.hexsha[:8] for c in mr_commits}

        total_added = 0
        total_surviving = 0

        for file_change in changes:
            file_path = file_change["file"]
            lines_added = file_change["additions"]

            if lines_added == 0:
                continue

            total_added += lines_added

            try:
                # git blame --porcelain HEAD -- <file>
                blame_data = repo.blame("HEAD", file_path)

                for commit, lines in blame_data:
                    if commit.hexsha[:8] in mr_commit_shas:
                        total_surviving += len(lines)

            except Exception as e:
                # File deleted, renamed, or not in repo: fallback to 100% survival
                logger.debug(f"  git blame failed for {file_path}: {e}")
                total_surviving += lines_added

        if total_added == 0:
            return 1.0

        return min(1.0, total_surviving / total_added)

    except Exception as e:
        logger.warning(f"  Could not compute survival for MR-{mr.iid}: {e}")
        return 1.0


def _collect_commit_log(repo: git.Repo, mr) -> List[Dict[str, Any]]:
    """
    Collect commit-level log for an MR (substantive commits only, max 15).

    Skips merge commits — esses são filtrados novamente pelo Stage 2.2, mas
    excluí-los aqui evita payload desnecessário.

    Campos retornados por commit:
      sha, author, authored_at, message, additions, deletions,
      files_touched, diff  (truncado em COMMIT_DIFF_MAX_CHARS)

    files_touched e diff são necessários para o Stage 2.2 avaliar
    scope_clarity e atomicity por commit.
    """
    commits = _get_mr_commits(repo, mr)
    log = []

    for commit in commits:
        message = commit.message.strip().split("\n")[0]

        # Merge commits: filtro aqui e no Stage 2.2 por redundância segura
        if message.lower().startswith("merge"):
            continue

        try:
            files_info = commit.stats.files
            additions = sum(f.get("insertions", 0) for f in files_info.values())
            deletions = sum(f.get("deletions", 0) for f in files_info.values())
            files_touched = list(files_info.keys())
        except Exception:
            additions = 0
            deletions = 0
            files_touched = []

        # Coleta diff truncado — necessário para atomicity e message_semantic
        diff_text = ""
        try:
            parent = commit.parents[0] if commit.parents else None
            if parent:
                raw_diff = repo.git.diff(parent.hexsha, commit.hexsha)
                diff_text = raw_diff[:config.COMMIT_DIFF_MAX_CHARS]
        except Exception:
            pass

        log.append({
            "sha":          commit.hexsha[:8],
            "author":       commit.author.name if commit.author else "unknown",
            "authored_at":  commit.authored_datetime.isoformat(),
            "message":      message,
            "additions":    additions,
            "deletions":    deletions,
            "files_touched": files_touched,
            "diff":          diff_text,
        })

    return log[:15]


def _get_mr_commits(repo: git.Repo, mr) -> List[git.Commit]:
    """
    Get list of commits in MR using git range diff_refs.

    Args:
        repo: gitpython Repo object
        mr: python-gitlab MergeRequest object

    Returns:
        List of git.Commit objects
    """
    try:
        diff_refs = mr.diff_refs
        if not diff_refs:
            return []

        base_sha = diff_refs.get("base_sha")
        head_sha = diff_refs.get("head_sha")

        if not (base_sha and head_sha):
            return []

        # Use git range notation
        commit_range = f"{base_sha}..{head_sha}"
        commits = list(repo.iter_commits(commit_range))
        return commits

    except Exception as e:
        logger.warning(f"  Could not identify commits for MR (diff_refs): {e}")
        return []


def _compute_ci_quality(mr) -> float:
    """
    Compute Q(k) — CI quality score based on pipeline status.

    Args:
        mr: python-gitlab MergeRequest object

    Returns:
        1.0 if green, 0.0 if failed, 0.5 if no CI or pending
    """
    try:
        pipeline = getattr(mr, "head_pipeline", None)

        if pipeline is None:
            return 0.5  # no CI configured

        # Handle dict or object
        if isinstance(pipeline, dict):
            status = pipeline.get("status", "")
        else:
            status = getattr(pipeline, "status", "")

        if status == "success":
            return 1.0
        elif status in ("failed", "canceled"):
            return 0.0
        else:
            # pending, running, skipped, etc.
            return 0.5

    except Exception as e:
        logger.warning(f"  Could not determine CI status: {e}")
        return 0.5


# ═══════════════════════════════════════════════════════════════════════════
# Internal functions — Utilities
# ═══════════════════════════════════════════════════════════════════════════


def _extract_type_declared(title: str) -> str:
    """
    Extract conventional commit type from MR title.

    Examples:
        "feat: add payment" → "feat"
        "fix(domain): bug in payment" → "fix"
        "refactor!" → "refactor"
        "Update docs" → "unknown"

    Args:
        title: MR title

    Returns:
        Type string (lowercase) or "unknown"
    """
    pattern = r"^(\w+)[\(:!]"
    match = re.match(pattern, title)
    if match:
        return match.group(1).lower()
    return "unknown"


def _extract_content_excerpt(diff_text: str, max_chars: int = 300) -> str:
    """
    Extract first 300 chars of added content from diff.

    Args:
        diff_text: Unified diff text
        max_chars: Maximum characters to extract

    Returns:
        Content excerpt (string, may be empty)
    """
    lines = diff_text.split("\n")
    added_content = []

    for line in lines:
        if line.startswith("+") and not line.startswith("+++"):
            # Remove leading "+" and add to content
            added_content.append(line[1:])

        if sum(len(l) for l in added_content) >= max_chars:
            break

    excerpt = " ".join(added_content)[:max_chars]
    return excerpt


def _should_ignore(file_path: str) -> bool:
    """
    Check if file matches ignore patterns.

    Args:
        file_path: File path

    Returns:
        True if should be ignored
    """
    for pattern in config.IGNORE_PATTERNS:
        if fnmatch(file_path, pattern):
            return True
    return False


def _save_artifacts(artifacts: List[Dict], output_path: str) -> None:
    """
    Save MR artifacts to JSON file.

    Args:
        artifacts: List of mr_artifact dicts
        output_path: Path to save JSON
    """
    if output_path is None:
        return

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(artifacts, f, indent=2, default=str)

    logger.info(f"Saved {len(artifacts)} artifacts to {output_path}")
