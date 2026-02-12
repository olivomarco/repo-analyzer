"""Tests for the people analysis module."""

from datetime import datetime, timezone

import pytest

from repo_inspector.analysis.people import compute_bus_factor, compute_contributor_stats
from repo_inspector.models import Commit, ContributorStats, Issue, PullRequest


@pytest.fixture
def sample_commits():
    base = datetime(2025, 1, 15, tzinfo=timezone.utc)
    return [
        Commit(
            sha="aaa111",
            message="feat: add auth",
            author_name="Alice",
            author_email="alice@test.com",
            author_login="alice",
            date=base,
            url="https://github.com/o/r/commit/aaa111",
            additions=200,
            deletions=10,
            files_changed=["src/auth.py", "src/models.py"],
        ),
        Commit(
            sha="bbb222",
            message="fix: login bug",
            author_name="Bob",
            author_login="bob",
            date=base,
            url="https://github.com/o/r/commit/bbb222",
            additions=15,
            deletions=5,
            files_changed=["src/auth.py"],
        ),
        Commit(
            sha="ccc333",
            message="docs: update readme",
            author_name="Alice",
            author_login="alice",
            date=base,
            url="https://github.com/o/r/commit/ccc333",
            additions=30,
            deletions=0,
            files_changed=["README.md"],
        ),
    ]


@pytest.fixture
def sample_prs():
    return [
        PullRequest(
            number=1,
            title="Add auth",
            author="alice",
            created_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
            merged_at=datetime(2025, 1, 12, tzinfo=timezone.utc),
            url="https://github.com/o/r/pull/1",
        ),
        PullRequest(
            number=2,
            title="Fix login",
            author="bob",
            created_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            url="https://github.com/o/r/pull/2",
        ),
    ]


@pytest.fixture
def sample_issues():
    return [
        Issue(
            number=10,
            title="Bug report",
            author="charlie",
            created_at=datetime(2025, 1, 8, tzinfo=timezone.utc),
            closed_at=datetime(2025, 1, 14, tzinfo=timezone.utc),
            url="https://github.com/o/r/issues/10",
        ),
    ]


class TestComputeContributorStats:
    def test_commit_counts(self, sample_commits, sample_prs, sample_issues):
        stats = compute_contributor_stats(sample_commits, sample_prs, sample_issues)
        alice = next(s for s in stats if s.login == "alice")
        assert alice.commit_count == 2
        bob = next(s for s in stats if s.login == "bob")
        assert bob.commit_count == 1

    def test_lines_added(self, sample_commits, sample_prs, sample_issues):
        stats = compute_contributor_stats(sample_commits, sample_prs, sample_issues)
        alice = next(s for s in stats if s.login == "alice")
        assert alice.lines_added == 230  # 200 + 30

    def test_pr_counts(self, sample_commits, sample_prs, sample_issues):
        stats = compute_contributor_stats(sample_commits, sample_prs, sample_issues)
        alice = next(s for s in stats if s.login == "alice")
        assert alice.prs_opened == 1
        assert alice.prs_merged == 1

    def test_issue_counts(self, sample_commits, sample_prs, sample_issues):
        stats = compute_contributor_stats(sample_commits, sample_prs, sample_issues)
        charlie = next(s for s in stats if s.login == "charlie")
        assert charlie.issues_opened == 1
        assert charlie.issues_closed == 1

    def test_sorted_by_commit_count(self, sample_commits, sample_prs, sample_issues):
        stats = compute_contributor_stats(sample_commits, sample_prs, sample_issues)
        assert stats[0].login == "alice"

    def test_top_directories(self, sample_commits, sample_prs, sample_issues):
        stats = compute_contributor_stats(sample_commits, sample_prs, sample_issues)
        alice = next(s for s in stats if s.login == "alice")
        assert "src" in alice.top_directories


class TestBusFactor:
    def test_single_contributor(self):
        stats = [ContributorStats(login="dev1", commit_count=100)]
        assert compute_bus_factor(stats) == 1

    def test_two_equal_contributors(self):
        stats = [
            ContributorStats(login="dev1", commit_count=50),
            ContributorStats(login="dev2", commit_count=50),
        ]
        assert compute_bus_factor(stats) == 2  # need both to reach 80%

    def test_no_commits(self):
        assert compute_bus_factor([]) == 0

    def test_uneven_distribution(self):
        stats = [
            ContributorStats(login="dev1", commit_count=90),
            ContributorStats(login="dev2", commit_count=5),
            ContributorStats(login="dev3", commit_count=5),
        ]
        assert compute_bus_factor(stats) == 1  # dev1 covers 90%
