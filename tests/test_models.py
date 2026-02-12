"""Tests for the data models."""

from datetime import datetime, timezone

import pytest

from repo_inspector.models import (
    CodeFinding,
    Commit,
    ContributorStats,
    FolderAnalysis,
    InspectionResult,
    Issue,
    PeopleReport,
    PullRequest,
    SeverityLevel,
    Timeframe,
)


class TestTimeframe:
    def test_label_format(self):
        tf = Timeframe(
            since=datetime(2025, 1, 1, tzinfo=timezone.utc),
            until=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        assert "2025-01-01" in tf.label
        assert "2025-02-01" in tf.label


class TestCommit:
    def test_create_commit(self):
        c = Commit(
            sha="abc123def456",
            message="feat: new feature",
            author_name="Dev",
            date=datetime.now(timezone.utc),
            url="https://github.com/owner/repo/commit/abc123def456",
        )
        assert c.sha == "abc123def456"
        assert c.short_sha == "abc123d"

    def test_short_sha_auto_generated(self):
        c = Commit(
            sha="1234567890abcdef",
            message="test",
            author_name="Dev",
            date=datetime.now(timezone.utc),
            url="https://github.com/x/y/commit/1234567890abcdef",
        )
        assert c.short_sha == "1234567"


class TestPullRequest:
    def test_create_pr(self):
        pr = PullRequest(
            number=42,
            title="Add feature",
            author="dev1",
            created_at=datetime.now(timezone.utc),
            url="https://github.com/owner/repo/pull/42",
        )
        assert pr.number == 42
        assert pr.labels == []
        assert pr.merged_at is None


class TestIssue:
    def test_create_issue(self):
        issue = Issue(
            number=10,
            title="Bug report",
            author="reporter",
            created_at=datetime.now(timezone.utc),
            url="https://github.com/owner/repo/issues/10",
        )
        assert issue.state == "open"


class TestContributorStats:
    def test_defaults(self):
        cs = ContributorStats(login="dev1")
        assert cs.commit_count == 0
        assert cs.files_touched == []
        assert cs.top_directories == []


class TestCodeFinding:
    def test_display_severity(self):
        f = CodeFinding(
            folder="src",
            category="security",
            severity=SeverityLevel.critical,
            title="SQL Injection",
            description="Unsafe query",
        )
        assert "CRITICAL" in f.display_severity
        assert "🔴" in f.display_severity

    def test_medium_default(self):
        f = CodeFinding(
            folder="lib",
            category="refactoring",
            title="Long method",
            description="Method too long",
        )
        assert f.severity == SeverityLevel.medium


class TestFolderAnalysis:
    def test_finding_count_by_severity(self):
        fa = FolderAnalysis(
            path="src",
            findings=[
                CodeFinding(folder="src", category="security", severity=SeverityLevel.high, title="A", description=""),
                CodeFinding(folder="src", category="security", severity=SeverityLevel.high, title="B", description=""),
                CodeFinding(folder="src", category="style", severity=SeverityLevel.low, title="C", description=""),
            ],
        )
        counts = fa.finding_count_by_severity
        assert counts["high"] == 2
        assert counts["low"] == 1


class TestInspectionResult:
    def test_create_result(self):
        tf = Timeframe(
            since=datetime(2025, 1, 1, tzinfo=timezone.utc),
            until=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        result = InspectionResult(repo="owner/repo", timeframe=tf)
        assert result.repo == "owner/repo"
        assert result.people.total_contributors == 0
        assert result.code.total_findings == 0
