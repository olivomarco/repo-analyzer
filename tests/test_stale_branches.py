"""Tests for the stale branches analysis module."""

from datetime import datetime, timezone

import pytest

from repo_inspector.analysis.stale_branches import build_stale_branch_report


def _make_branch(name: str, days_ago: int, author: str = "dev") -> dict:
    """Helper to create a branch dict."""
    from datetime import timedelta
    date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "name": name,
        "commit": {
            "sha": f"sha-{name}",
            "commit": {
                "author": {"name": author, "date": date},
            },
        },
    }


class TestBuildStaleBranchReport:
    def test_excludes_default_branch(self):
        branches = [_make_branch("main", 1), _make_branch("old-feature", 100)]
        report = build_stale_branch_report(branches, "main", {})
        names = [b.name for b in report.stale_branches]
        assert "main" not in names

    def test_detects_stale_branches(self):
        branches = [
            _make_branch("main", 1),
            _make_branch("feature/old", 90),
            _make_branch("feature/recent", 10),
        ]
        report = build_stale_branch_report(branches, "main", {}, stale_threshold_days=60)
        assert len(report.stale_branches) == 1
        assert report.stale_branches[0].name == "feature/old"

    def test_categorizes_wip(self):
        branches = [_make_branch("wip-experiment", 100)]
        report = build_stale_branch_report(branches, "main", {})
        assert report.stale_branches[0].category == "wip"

    def test_categorizes_feature(self):
        branches = [_make_branch("feature/login", 100)]
        report = build_stale_branch_report(branches, "main", {})
        assert report.stale_branches[0].category == "stale-feature"

    def test_categorizes_orphan(self):
        branches = [_make_branch("some-branch", 100)]
        compare = {"some-branch": {"ahead_by": 0, "behind_by": 15}}
        report = build_stale_branch_report(branches, "main", compare)
        assert report.stale_branches[0].category == "orphan"

    def test_total_branches_count(self):
        branches = [
            _make_branch("main", 1),
            _make_branch("dev", 5),
            _make_branch("old", 100),
        ]
        report = build_stale_branch_report(branches, "main", {})
        assert report.total_branches == 3

    def test_cleanup_candidates(self):
        branches = [
            _make_branch("wip-test", 100),
            _make_branch("feature/done", 100),
        ]
        compare = {"wip-test": {"ahead_by": 0, "behind_by": 5}}
        report = build_stale_branch_report(branches, "main", compare)
        # wip → cleanup candidate, orphan → cleanup candidate
        assert report.cleanup_candidates >= 1

    def test_sorted_by_staleness(self):
        branches = [
            _make_branch("a", 200),
            _make_branch("b", 100),
            _make_branch("c", 300),
        ]
        report = build_stale_branch_report(branches, "main", {})
        days = [b.days_stale for b in report.stale_branches]
        assert days == sorted(days, reverse=True)

    def test_no_stale_branches(self):
        branches = [_make_branch("main", 1), _make_branch("dev", 5)]
        report = build_stale_branch_report(branches, "main", {})
        assert len(report.stale_branches) == 0

    def test_ahead_behind_info(self):
        branches = [_make_branch("old", 100)]
        compare = {"old": {"ahead_by": 3, "behind_by": 12}}
        report = build_stale_branch_report(branches, "main", compare)
        assert "3 ahead" in report.stale_branches[0].ahead_behind
        assert "12 behind" in report.stale_branches[0].ahead_behind
