"""Tests for the what-if simulator module."""

from datetime import datetime, timezone

import pytest

from repo_inspector.analysis.what_if import (
    build_what_if_report,
    simulate_deprecate_module,
    simulate_remove_contributor,
)
from repo_inspector.models import Commit, ContributorStats, Issue, PullRequest


@pytest.fixture
def wi_commits():
    base = datetime(2025, 1, 15, tzinfo=timezone.utc)
    return [
        Commit(
            sha="a1", message="auth work", author_name="Alice",
            author_login="alice", date=base,
            url="https://github.com/o/r/commit/a1",
            files_changed=["src/auth.py", "src/session.py"],
        ),
        Commit(
            sha="a2", message="more auth", author_name="Alice",
            author_login="alice", date=base,
            url="https://github.com/o/r/commit/a2",
            files_changed=["src/auth.py", "tests/test_auth.py"],
        ),
        Commit(
            sha="b1", message="api work", author_name="Bob",
            author_login="bob", date=base,
            url="https://github.com/o/r/commit/b1",
            files_changed=["src/api.py", "src/auth.py"],
        ),
    ]


@pytest.fixture
def wi_prs():
    return [
        PullRequest(
            number=1, title="Auth PR", author="alice",
            created_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
            url="https://github.com/o/r/pull/1",
        ),
    ]


@pytest.fixture
def wi_issues():
    return []


@pytest.fixture
def wi_stats():
    return [
        ContributorStats(login="alice", commit_count=2),
        ContributorStats(login="bob", commit_count=1),
    ]


class TestSimulateRemoveContributor:
    def test_orphaned_files(self, wi_commits, wi_prs, wi_issues):
        result = simulate_remove_contributor(
            "alice", wi_commits, wi_prs, wi_issues, 2
        )
        # src/session.py and tests/test_auth.py are only touched by alice
        assert "src/session.py" in result.orphaned_files
        assert "tests/test_auth.py" in result.orphaned_files

    def test_shared_files_not_orphaned(self, wi_commits, wi_prs, wi_issues):
        result = simulate_remove_contributor(
            "alice", wi_commits, wi_prs, wi_issues, 2
        )
        # src/auth.py is touched by both alice and bob
        assert "src/auth.py" not in result.orphaned_files

    def test_bus_factor_changes(self, wi_commits, wi_prs, wi_issues):
        result = simulate_remove_contributor(
            "alice", wi_commits, wi_prs, wi_issues, 2
        )
        assert result.bus_factor_before == 2
        assert result.bus_factor_after >= 1

    def test_scenario_metadata(self, wi_commits, wi_prs, wi_issues):
        result = simulate_remove_contributor(
            "alice", wi_commits, wi_prs, wi_issues, 2
        )
        assert result.scenario == "remove_contributor"
        assert result.parameter == "alice"


class TestSimulateDeprecateModule:
    def test_finds_affected_files(self, wi_commits):
        result = simulate_deprecate_module("src", wi_commits)
        assert len(result.orphaned_files) > 0
        assert any("src/" in f for f in result.orphaned_files)

    def test_finds_affected_contributors(self, wi_commits):
        result = simulate_deprecate_module("src", wi_commits)
        assert "alice" in result.affected_areas
        assert "bob" in result.affected_areas

    def test_scenario_metadata(self, wi_commits):
        result = simulate_deprecate_module("src", wi_commits)
        assert result.scenario == "deprecate_module"
        assert result.parameter == "src"


class TestBuildWhatIfReport:
    def test_generates_scenarios(self, wi_stats, wi_commits, wi_prs, wi_issues):
        report = build_what_if_report(
            wi_stats, wi_commits, wi_prs, wi_issues, bus_factor=2, top_dirs=["src"]
        )
        scenarios = report.scenarios
        # Should have contributor removal + module deprecation scenarios
        types = [s.scenario for s in scenarios]
        assert "remove_contributor" in types
        assert "deprecate_module" in types

    def test_limits_to_top_contributors(self, wi_stats, wi_commits, wi_prs, wi_issues):
        report = build_what_if_report(
            wi_stats, wi_commits, wi_prs, wi_issues, bus_factor=2, top_dirs=["src"]
        )
        removals = [s for s in report.scenarios if s.scenario == "remove_contributor"]
        assert len(removals) <= 3
