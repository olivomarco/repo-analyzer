"""Tests for the changelog analysis module."""

from datetime import datetime, timezone

import pytest

from repo_inspector.analysis.changelog import (
    _infer_category,
    build_changelog,
    render_changelog_markdown,
)
from repo_inspector.models import Commit, PullRequest


@pytest.fixture
def cl_commits():
    base = datetime(2025, 1, 15, tzinfo=timezone.utc)
    return [
        Commit(
            sha="aaa111bbb", message="feat: add new login flow",
            author_name="Alice", author_login="alice", date=base,
            url="https://github.com/o/r/commit/aaa111bbb",
        ),
        Commit(
            sha="bbb222ccc", message="fix: null pointer in auth",
            author_name="Bob", author_login="bob", date=base,
            url="https://github.com/o/r/commit/bbb222ccc",
        ),
        Commit(
            sha="ccc333ddd", message="Merge pull request #1",
            author_name="Alice", author_login="alice", date=base,
            url="https://github.com/o/r/commit/ccc333ddd",
        ),
        Commit(
            sha="ddd444eee", message="bump",
            author_name="Bot", author_login="bot", date=base,
            url="https://github.com/o/r/commit/ddd444eee",
        ),
    ]


@pytest.fixture
def cl_prs():
    base = datetime(2025, 1, 10, tzinfo=timezone.utc)
    return [
        PullRequest(
            number=1, title="Add OAuth support", author="alice",
            created_at=base,
            merged_at=datetime(2025, 1, 12, tzinfo=timezone.utc),
            url="https://github.com/o/r/pull/1",
        ),
        PullRequest(
            number=2, title="Fix login bug", author="bob",
            created_at=base,
            merged_at=datetime(2025, 1, 13, tzinfo=timezone.utc),
            url="https://github.com/o/r/pull/2",
        ),
        PullRequest(
            number=3, title="WIP: Refactoring", author="charlie",
            created_at=base,
            url="https://github.com/o/r/pull/3",  # Not merged
        ),
    ]


class TestInferCategory:
    def test_feat(self):
        assert _infer_category("feat: add login") == "feat"

    def test_fix(self):
        assert _infer_category("fix: null pointer") == "fix"

    def test_docs(self):
        assert _infer_category("docs: update README") == "docs"

    def test_refactor(self):
        assert _infer_category("refactor: clean up auth module") == "refactor"

    def test_chore_default(self):
        assert _infer_category("misc: tweaks") == "chore"

    def test_feature_keyword(self):
        assert _infer_category("Add new feature for search") == "feat"

    def test_performance(self):
        assert _infer_category("optimize query performance") == "perf"


class TestBuildChangelog:
    def test_includes_merged_prs(self, cl_commits, cl_prs):
        report = build_changelog(cl_commits, cl_prs)
        descs = [e.description for e in report.entries]
        assert "Add OAuth support" in descs
        assert "Fix login bug" in descs

    def test_excludes_unmerged_prs(self, cl_commits, cl_prs):
        report = build_changelog(cl_commits, cl_prs)
        descs = [e.description for e in report.entries]
        assert "WIP: Refactoring" not in descs

    def test_excludes_merge_commits(self, cl_commits, cl_prs):
        report = build_changelog(cl_commits, cl_prs)
        descs = [e.description for e in report.entries]
        assert not any("Merge pull request" in d for d in descs)

    def test_excludes_short_messages(self, cl_commits, cl_prs):
        report = build_changelog(cl_commits, cl_prs)
        descs = [e.description for e in report.entries]
        assert "bump" not in descs

    def test_pr_entries_have_pr_number(self, cl_commits, cl_prs):
        report = build_changelog(cl_commits, cl_prs)
        pr_entries = [e for e in report.entries if e.pr_number]
        assert len(pr_entries) == 2

    def test_deduplication(self, cl_commits, cl_prs):
        # Duplicate commit shouldn't create duplicate entry
        report = build_changelog(cl_commits, cl_prs)
        descs = [e.description.lower().strip()[:60] for e in report.entries]
        assert len(descs) == len(set(descs))


class TestRenderMarkdown:
    def test_produces_markdown(self, cl_commits, cl_prs):
        report = build_changelog(cl_commits, cl_prs)
        md = render_changelog_markdown(report)
        assert "# Changelog" in md
        assert report.markdown == md

    def test_includes_pr_refs(self, cl_commits, cl_prs):
        report = build_changelog(cl_commits, cl_prs)
        md = render_changelog_markdown(report)
        assert "(#1)" in md

    def test_includes_authors(self, cl_commits, cl_prs):
        report = build_changelog(cl_commits, cl_prs)
        md = render_changelog_markdown(report)
        assert "@alice" in md
