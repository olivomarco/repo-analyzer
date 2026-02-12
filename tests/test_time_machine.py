"""Tests for the time machine (historical comparison) module."""

from datetime import datetime, timezone

import pytest

from repo_inspector.analysis.time_machine import build_time_comparison
from repo_inspector.models import ContributorStats, Timeframe


@pytest.fixture
def old_tf():
    return Timeframe(
        since=datetime(2024, 12, 1, tzinfo=timezone.utc),
        until=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def new_tf():
    return Timeframe(
        since=datetime(2025, 1, 1, tzinfo=timezone.utc),
        until=datetime(2025, 2, 1, tzinfo=timezone.utc),
    )


class TestBuildTimeComparison:
    def test_detects_new_contributors(self, old_tf, new_tf):
        old_stats = [ContributorStats(login="alice", commit_count=10)]
        new_stats = [
            ContributorStats(login="alice", commit_count=10),
            ContributorStats(login="bob", commit_count=5),
        ]
        report = build_time_comparison(
            old_stats, new_stats, old_tf, new_tf, 1, 2, 0, 0
        )
        assert "bob" in report.contributor_churn

    def test_detects_departed_contributors(self, old_tf, new_tf):
        old_stats = [
            ContributorStats(login="alice", commit_count=10),
            ContributorStats(login="charlie", commit_count=3),
        ]
        new_stats = [ContributorStats(login="alice", commit_count=12)]
        report = build_time_comparison(
            old_stats, new_stats, old_tf, new_tf, 2, 1, 0, 0
        )
        assert "charlie" in report.contributor_departed

    def test_commit_volume_delta(self, old_tf, new_tf):
        old_stats = [ContributorStats(login="a", commit_count=100)]
        new_stats = [ContributorStats(login="a", commit_count=150)]
        report = build_time_comparison(
            old_stats, new_stats, old_tf, new_tf, 1, 1, 0, 0
        )
        commit_delta = next(d for d in report.deltas if d.metric == "Commit Volume")
        assert commit_delta.old_value == 100
        assert commit_delta.new_value == 150
        assert "+" in commit_delta.change

    def test_bus_factor_delta(self, old_tf, new_tf):
        old_stats = [ContributorStats(login="a", commit_count=10)]
        new_stats = [ContributorStats(login="a", commit_count=10)]
        report = build_time_comparison(
            old_stats, new_stats, old_tf, new_tf,
            old_bus_factor=1, new_bus_factor=3,
            old_finding_count=0, new_finding_count=0,
        )
        bus_delta = next(d for d in report.deltas if d.metric == "Bus Factor")
        assert bus_delta.old_value == 1
        assert bus_delta.new_value == 3
        assert "+2" in bus_delta.change

    def test_findings_delta(self, old_tf, new_tf):
        report = build_time_comparison(
            [], [], old_tf, new_tf, 0, 0,
            old_finding_count=5, new_finding_count=12,
        )
        finding_delta = next(d for d in report.deltas if d.metric == "Code Findings")
        assert finding_delta.change == "+7"

    def test_timeframes_stored(self, old_tf, new_tf):
        report = build_time_comparison([], [], old_tf, new_tf, 0, 0, 0, 0)
        assert report.old_timeframe == old_tf
        assert report.new_timeframe == new_tf

    def test_all_deltas_present(self, old_tf, new_tf):
        report = build_time_comparison([], [], old_tf, new_tf, 0, 0, 0, 0)
        metric_names = {d.metric for d in report.deltas}
        assert "Commit Volume" in metric_names
        assert "Contributors" in metric_names
        assert "Bus Factor" in metric_names
        assert "Lines Changed" in metric_names
        assert "Code Findings" in metric_names
