"""Tests for the knowledge map analysis module."""

from datetime import datetime, timezone

import pytest

from repo_inspector.analysis.knowledge_map import build_knowledge_map
from repo_inspector.models import Commit, ContributorStats


@pytest.fixture
def km_commits():
    base = datetime(2025, 1, 15, tzinfo=timezone.utc)
    return [
        Commit(
            sha="a1", message="work on api", author_name="Alice",
            author_login="alice", date=base,
            url="https://github.com/o/r/commit/a1",
            additions=100, deletions=10,
            files_changed=["src/api/routes.py", "src/api/models.py"],
        ),
        Commit(
            sha="a2", message="more api", author_name="Alice",
            author_login="alice", date=base,
            url="https://github.com/o/r/commit/a2",
            additions=50, deletions=5,
            files_changed=["src/api/views.py"],
        ),
        Commit(
            sha="b1", message="fix tests", author_name="Bob",
            author_login="bob", date=base,
            url="https://github.com/o/r/commit/b1",
            additions=20, deletions=5,
            files_changed=["tests/test_api.py"],
        ),
        Commit(
            sha="b2", message="add test utils", author_name="Bob",
            author_login="bob", date=base,
            url="https://github.com/o/r/commit/b2",
            additions=30, deletions=0,
            files_changed=["tests/utils.py", "src/api/helpers.py"],
        ),
    ]


@pytest.fixture
def km_stats():
    return [
        ContributorStats(login="alice", commit_count=2),
        ContributorStats(login="bob", commit_count=2),
    ]


class TestBuildKnowledgeMap:
    def test_returns_contributors_and_folders(self, km_stats, km_commits):
        km = build_knowledge_map(km_stats, km_commits, ["src", "tests"])
        assert "alice" in km.contributors
        assert "bob" in km.contributors
        assert "src" in km.folders
        assert "tests" in km.folders

    def test_cell_count(self, km_stats, km_commits):
        km = build_knowledge_map(km_stats, km_commits, ["src", "tests"])
        # 2 contributors × 2 folders
        assert len(km.cells) == 4

    def test_alice_dominates_src(self, km_stats, km_commits):
        km = build_knowledge_map(km_stats, km_commits, ["src", "tests"])
        cell = next(c for c in km.cells if c.login == "alice" and c.folder == "src")
        assert cell.commits == 3  # a1 (2 files in src), a2 (1 file in src)

    def test_bob_dominates_tests(self, km_stats, km_commits):
        km = build_knowledge_map(km_stats, km_commits, ["src", "tests"])
        cell = next(c for c in km.cells if c.login == "bob" and c.folder == "tests")
        assert cell.commits == 2

    def test_detects_knowledge_silos(self, km_stats, km_commits):
        km = build_knowledge_map(km_stats, km_commits, ["tests"])
        # Bob has 2/2 commits in tests = 100% → silo
        assert any("tests" in s for s in km.knowledge_silos)

    def test_empty_commits(self, km_stats):
        km = build_knowledge_map(km_stats, [], ["src"])
        assert len(km.knowledge_silos) == 0
        assert all(c.commits == 0 for c in km.cells)

    def test_score_normalized(self, km_stats, km_commits):
        km = build_knowledge_map(km_stats, km_commits, ["src", "tests"])
        for cell in km.cells:
            assert 0.0 <= cell.score <= 1.0
