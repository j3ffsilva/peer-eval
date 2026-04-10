"""Resolution helpers for CLI configuration and sprint windows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..configuration.loader import load_toml_config


def load_project_config(toml_path: str = ".peer-eval.toml") -> Dict[str, Any]:
    """Load the project TOML used by the CLI."""
    return load_toml_config(toml_path)


def _get_config_value(config: Dict[str, Any], *paths: str, default: Any = None) -> Any:
    """Return the first configured value found across multiple dot-paths."""
    for path in paths:
        current: Any = config
        found = True

        for key in path.split("."):
            if not isinstance(current, dict) or key not in current:
                found = False
                break
            current = current[key]

        if found and current is not None:
            return current

    return default


def _parse_iso_datetime(value: str) -> datetime:
    """Parse ISO 8601 strings, accepting a trailing Z."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def _to_iso_string(value: datetime) -> str:
    """Format datetimes consistently for the CLI pipeline."""
    utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat().replace("+00:00", "Z")


def parse_sprint_selection(args) -> List[int]:
    """Collect sprint numbers from --sprint and --sprints."""
    sprint_numbers: List[int] = []

    if getattr(args, "sprint", None):
        sprint_numbers.extend(args.sprint)

    raw_sprints = getattr(args, "sprints", None)
    if raw_sprints:
        for raw_value in raw_sprints.split(","):
            value = raw_value.strip()
            if not value:
                continue
            try:
                sprint_numbers.append(int(value))
            except ValueError as exc:
                raise ValueError(f"Invalid sprint number in --sprints: {value!r}") from exc

    unique_sprints = sorted(set(sprint_numbers))
    if any(number < 1 for number in unique_sprints):
        raise ValueError("Sprint numbers must be greater than or equal to 1")

    return unique_sprints


def resolve_sprint_window(config: Dict[str, Any], sprint_numbers: List[int]) -> Dict[str, str]:
    """Resolve start/end/deadline timestamps for one or more sprint numbers."""
    if not sprint_numbers:
        raise ValueError("At least one sprint number is required")

    start_date = _get_config_value(config, "sprints.start_date")
    length_days = _get_config_value(config, "sprints.length_days")
    sprint_count = _get_config_value(config, "sprints.count")

    missing_fields = [
        field_name
        for field_name, value in (
            ("sprints.start_date", start_date),
            ("sprints.length_days", length_days),
        )
        if value in (None, "")
    ]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise ValueError(
            f"Sprint selection requires {joined} in .peer-eval.toml"
        )

    try:
        length_days_int = int(length_days)
    except (TypeError, ValueError) as exc:
        raise ValueError("sprints.length_days must be an integer") from exc

    if length_days_int <= 0:
        raise ValueError("sprints.length_days must be greater than zero")

    if sprint_count is not None:
        try:
            sprint_count_int = int(sprint_count)
        except (TypeError, ValueError) as exc:
            raise ValueError("sprints.count must be an integer") from exc

        if sprint_count_int <= 0:
            raise ValueError("sprints.count must be greater than zero")

        invalid = [number for number in sprint_numbers if number > sprint_count_int]
        if invalid:
            raise ValueError(
                f"Sprint numbers out of range for configured calendar: {invalid}"
            )

    project_start = _parse_iso_datetime(str(start_date))

    first_start = project_start + timedelta(days=(sprint_numbers[0] - 1) * length_days_int)
    last_start = project_start + timedelta(days=(sprint_numbers[-1] - 1) * length_days_int)
    last_end = last_start + timedelta(days=length_days_int) - timedelta(seconds=1)

    return {
        "since": _to_iso_string(first_start),
        "until": _to_iso_string(last_end),
        "deadline": _to_iso_string(last_end),
    }


def resolve_common_options(args, config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve deadline using CLI args, sprint selection, and TOML defaults."""
    sprint_numbers = parse_sprint_selection(args)
    resolved = {
        "deadline": getattr(args, "deadline", None),
        "sprint_numbers": sprint_numbers,
    }

    sprint_window = resolve_sprint_window(config, sprint_numbers) if sprint_numbers else None

    if sprint_window and not resolved["deadline"]:
        resolved["deadline"] = sprint_window["deadline"]

    if not resolved["deadline"]:
        resolved["deadline"] = _get_config_value(
            config,
            "evaluation.deadline",
            "project.deadline",
        )

    if not resolved["deadline"]:
        raise ValueError(
            "A deadline is required. Pass --deadline or select sprint(s) with "
            "--sprint/--sprints and configure [sprints] in .peer-eval.toml."
        )

    resolved["sprint_window"] = sprint_window
    return resolved


def resolve_gitlab_options(args, config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the effective GitLab date window and deadline."""
    resolved = resolve_common_options(args, config)

    if resolved["sprint_numbers"] and (args.since or args.until):
        raise ValueError(
            "Use either --since/--until or --sprint/--sprints, not both."
        )

    resolved_since = args.since
    resolved_until = args.until

    if resolved["sprint_window"]:
        resolved_since = resolved["sprint_window"]["since"]
        resolved_until = resolved["sprint_window"]["until"]

    if not resolved_since:
        resolved_since = _get_config_value(
            config,
            "evaluation.since",
            "project.since",
        )

    if not resolved_until:
        resolved_until = _get_config_value(
            config,
            "evaluation.until",
            "project.until",
        )

    resolved["since"] = resolved_since
    resolved["until"] = resolved_until
    return resolved
