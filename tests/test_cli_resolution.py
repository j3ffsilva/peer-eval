"""Tests for CLI config and sprint resolution helpers."""

import pytest

from types import SimpleNamespace

from peer_eval.cli.resolution import (
    parse_sprint_selection,
    resolve_common_options,
    resolve_gitlab_options,
    resolve_sprint_window,
)


def test_parse_sprint_selection_combines_flags():
    args = SimpleNamespace(sprint=[1, 3], sprints="2,3,4")
    assert parse_sprint_selection(args) == [1, 2, 3, 4]


def test_parse_sprint_selection_rejects_invalid_values():
    args = SimpleNamespace(sprint=None, sprints="1,x")
    with pytest.raises(ValueError, match="Invalid sprint number"):
        parse_sprint_selection(args)


def test_resolve_sprint_window_uses_configured_calendar():
    config = {
        "sprints": {
            "start_date": "2026-03-16T00:00:00Z",
            "length_days": 15,
            "count": 5,
        }
    }

    resolved = resolve_sprint_window(config, [1, 2, 3])

    assert resolved["since"] == "2026-03-16T00:00:00Z"
    assert resolved["until"] == "2026-04-29T23:59:59Z"
    assert resolved["deadline"] == "2026-04-29T23:59:59Z"


def test_resolve_common_options_uses_sprint_deadline_when_missing():
    args = SimpleNamespace(deadline=None, sprint=[4], sprints=None)
    config = {
        "sprints": {
            "start_date": "2026-03-16T00:00:00Z",
            "length_days": 15,
            "count": 5,
        }
    }

    resolved = resolve_common_options(args, config)

    assert resolved["deadline"] == "2026-05-14T23:59:59Z"
    assert resolved["sprint_numbers"] == [4]


def test_resolve_gitlab_options_uses_sprint_window():
    args = SimpleNamespace(
        deadline=None,
        sprint=None,
        sprints="2,3",
        since=None,
        until=None,
        project_id="graduacao/2026-1a/t17/g03",
        url=None,
    )
    config = {
        "provider": {
            "gitlab": {
                "url": "https://git.inteli.edu.br",
            }
        },
        "sprints": {
            "start_date": "2026-03-16T00:00:00Z",
            "length_days": 15,
            "count": 5,
        }
    }

    resolved = resolve_gitlab_options(args, config)

    assert resolved["since"] == "2026-03-31T00:00:00Z"
    assert resolved["until"] == "2026-04-29T23:59:59Z"
    assert resolved["deadline"] == "2026-04-29T23:59:59Z"
    assert resolved["project_id"] == "graduacao/2026-1a/t17/g03"
    assert resolved["url"] == "https://git.inteli.edu.br"


def test_resolve_gitlab_options_rejects_mixed_manual_and_sprint_windows():
    args = SimpleNamespace(
        deadline=None,
        sprint=[1],
        sprints=None,
        since="2026-03-16T00:00:00Z",
        until=None,
        project_id="graduacao/2026-1a/t17/g03",
        url=None,
    )

    with pytest.raises(ValueError, match="Use either --since/--until or --sprint/--sprints"):
        resolve_gitlab_options(args, {"sprints": {"start_date": "2026-03-16T00:00:00Z", "length_days": 15}})
