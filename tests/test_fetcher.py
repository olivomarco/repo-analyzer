"""Tests for the fetcher module."""

from datetime import datetime, timezone

import httpx
import pytest
import respx

from repo_inspector.fetcher import GitHubFetcher


@pytest.fixture
def github_fetcher():
    return GitHubFetcher(token="test-token")


class TestGitHubFetcher:
    def test_init_with_token(self):
        fetcher = GitHubFetcher(token="my-token")
        assert fetcher.token == "my-token"
        assert "Authorization" in fetcher.headers

    def test_init_without_token(self):
        fetcher = GitHubFetcher()
        assert fetcher.token is None
        assert "Authorization" not in fetcher.headers

    def test_headers_include_api_version(self, github_fetcher):
        assert "X-GitHub-Api-Version" in github_fetcher.headers

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_commits(self, github_fetcher):
        mock_commits = [
            {
                "sha": "abc123def456",
                "commit": {
                    "message": "Test commit",
                    "author": {
                        "name": "Test Author",
                        "email": "dev@test.com",
                        "date": "2025-01-15T10:00:00Z",
                    },
                },
                "author": {"login": "testuser"},
                "html_url": "https://github.com/owner/repo/commit/abc123def456",
            }
        ]
        respx.get("https://api.github.com/repos/owner/repo/commits").mock(
            return_value=httpx.Response(200, json=mock_commits)
        )
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 2, 1, tzinfo=timezone.utc)
        commits = await github_fetcher.fetch_commits("owner", "repo", since, until)
        await github_fetcher.close()

        assert len(commits) == 1
        assert commits[0].sha == "abc123def456"
        assert commits[0].author_login == "testuser"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_pull_requests(self, github_fetcher):
        mock_prs = [
            {
                "number": 1,
                "title": "Test PR",
                "body": "Test body",
                "user": {"login": "testuser"},
                "created_at": "2025-01-10T00:00:00Z",
                "updated_at": "2025-01-15T00:00:00Z",
                "merged_at": "2025-01-12T00:00:00Z",
                "closed_at": None,
                "html_url": "https://github.com/owner/repo/pull/1",
                "labels": [{"name": "enhancement"}],
                "additions": 100,
                "deletions": 20,
                "changed_files": 5,
            }
        ]
        respx.get("https://api.github.com/repos/owner/repo/pulls").mock(
            return_value=httpx.Response(200, json=mock_prs)
        )
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 2, 1, tzinfo=timezone.utc)
        prs = await github_fetcher.fetch_pull_requests("owner", "repo", since, until)
        await github_fetcher.close()

        assert len(prs) == 1
        assert prs[0].number == 1
        assert "enhancement" in prs[0].labels

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_issues_excludes_prs(self, github_fetcher):
        mock_issues = [
            {
                "number": 5,
                "title": "Bug report",
                "body": "Something broke",
                "user": {"login": "reporter"},
                "state": "open",
                "created_at": "2025-01-10T00:00:00Z",
                "updated_at": "2025-01-15T00:00:00Z",
                "closed_at": None,
                "html_url": "https://github.com/owner/repo/issues/5",
                "labels": [],
            },
            {
                "number": 6,
                "title": "PR disguised as issue",
                "user": {"login": "dev"},
                "state": "closed",
                "created_at": "2025-01-10T00:00:00Z",
                "updated_at": "2025-01-15T00:00:00Z",
                "closed_at": "2025-01-12T00:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/6",
                "labels": [],
                "pull_request": {"url": "..."},
            },
        ]
        respx.get("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(200, json=mock_issues)
        )
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        issues = await github_fetcher.fetch_issues("owner", "repo", since)
        await github_fetcher.close()

        assert len(issues) == 1
        assert issues[0].number == 5

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_repo_info(self, github_fetcher):
        mock_info = {
            "name": "repo",
            "description": "A test repo",
            "topics": ["python", "cli"],
        }
        respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(200, json=mock_info)
        )
        info = await github_fetcher.fetch_repo_info("owner", "repo")
        await github_fetcher.close()

        assert info["description"] == "A test repo"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_issue(self, github_fetcher):
        respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(
                201,
                json={
                    "number": 99,
                    "html_url": "https://github.com/owner/repo/issues/99",
                },
            )
        )
        result = await github_fetcher.create_issue(
            "owner", "repo", "Test Issue", "Body text", labels=["bug"]
        )
        await github_fetcher.close()

        assert result["number"] == 99
