"""Tests for the bus factor mitigation module."""

from datetime import datetime, timezone

import pytest

from repo_inspector.analysis.bus_mitigation import build_bus_mitigation
from repo_inspector.models import Commit, ContributorStats


@pytest.fixture
def bm_commits():
    base = datetime(2025, 1, 15, tzinfo=timezone.utc)
    return [
        Commit(
            sha="a1", message="work", author_name="Alice",
            author_login="alice", date=base,
            url="https://github.com/o/r/commit/a1",
            files_changed=["src/auth.py", "src/models.py", "src/config.py",
                           "src/routes.py", "src/utils.py", "src/db.py"],
        ),
        Commit(
            sha="b1", message="help", author_name="Bob",
            author_login="bob", date=base,
            url="https://github.com/o/r/commit/b1",
            files_changed=["tests/test_auth.py"],
        ),
    ]


@pytest.fixture
def bm_stats():
    return [
        ContributorStats(login="alice", commit_count=50),
        ContributorStats(login="bob", commit_count=5),
    ]


class TestBuildBusMitigation:
    def test_critical_risk(self, bm_stats, bm_commits):
        report = build_bus_mitigation(bm_stats, bm_commits, bus_factor=1)
        assert report.risk_level == "critical"

    def test_high_risk(self, bm_stats, bm_commits):
        report = build_bus_mitigation(bm_stats, bm_commits, bus_factor=2)
        assert report.risk_level == "high"

    def test_medium_risk(self, bm_stats, bm_commits):
        report = build_bus_mitigation(bm_stats, bm_commits, bus_factor=3)
        assert report.risk_level == "medium"

    def test_low_risk(self, bm_stats, bm_commits):
        report = build_bus_mitigation(bm_stats, bm_commits, bus_factor=5)
        assert report.risk_level == "low"

    def test_finds_exclusive_files(self, bm_stats, bm_commits):
        report = build_bus_mitigation(bm_stats, bm_commits, bus_factor=1)
        # Alice has exclusive ownership of src files, Bob of tests
        assert "alice" in report.exclusive_files
        assert len(report.exclusive_files["alice"]) >= 5

    def test_identifies_monopolists(self, bm_stats, bm_commits):
        report = build_bus_mitigation(bm_stats, bm_commits, bus_factor=1)
        assert "alice" in report.knowledge_monopolists

    def test_dominant_contributor_flagged(self):
        stats = [
            ContributorStats(login="megadev", commit_count=90),
            ContributorStats(login="helper", commit_count=10),
        ]
        commits = [
            Commit(
                sha="m1", message="x", author_name="Mega",
                author_login="megadev",
                date=datetime(2025, 1, 1, tzinfo=timezone.utc),
                url="u", files_changed=["a.py"],
            ),
        ]
        report = build_bus_mitigation(stats, commits, bus_factor=1)
        assert "megadev" in report.knowledge_monopolists
