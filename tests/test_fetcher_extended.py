"""Extended tests for the fetcher module — covering additional branches."""

from datetime import datetime, timezone

import httpx
import pytest
import respx

from repo_inspector.fetcher import GitHubFetcher


@pytest.fixture
def github_fetcher():
    return GitHubFetcher(token="test-token")


class TestSamlFallback:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_saml_fallback(self, github_fetcher):
        """Test that SAML 403 triggers auth removal and retry."""
        route = respx.get("https://api.github.com/repos/owner/repo")
        route.side_effect = [
            httpx.Response(403, text="Organization requires SAML authentication"),
            httpx.Response(200, json={"name": "repo"}),
        ]
        result = await github_fetcher.fetch_repo_info("owner", "repo")
        await github_fetcher.close()
        assert result["name"] == "repo"
        assert github_fetcher.is_unauthenticated is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_post_saml_fallback(self, github_fetcher):
        """Test SAML fallback on POST requests."""
        route = respx.post("https://api.github.com/repos/owner/repo/issues")
        route.side_effect = [
            httpx.Response(403, text="Organization requires SAML authentication"),
            httpx.Response(201, json={"number": 1, "html_url": "https://github.com/owner/repo/issues/1"}),
        ]
        result = await github_fetcher.create_issue("owner", "repo", "Test", "Body")
        await github_fetcher.close()
        assert result["number"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limit_error(self, github_fetcher):
        """Test that rate limit 403 raises an exception."""
        respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(
                403,
                text="API rate limit exceeded",
                headers={
                    "x-ratelimit-remaining": "0",
                    "x-ratelimit-reset": "1700000000",
                },
            )
        )
        with pytest.raises(httpx.HTTPStatusError, match="rate limit"):
            await github_fetcher.fetch_repo_info("owner", "repo")
        await github_fetcher.close()


class TestIsUnauthenticated:
    def test_initially_false(self):
        fetcher = GitHubFetcher(token="test")
        assert fetcher.is_unauthenticated is False

    def test_no_token_headers(self):
        fetcher = GitHubFetcher()
        assert "Authorization" not in fetcher.headers


class TestFetchBranches:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_branches(self, github_fetcher):
        mock_branches = [
            {"name": "main", "commit": {"sha": "abc123"}},
            {"name": "feature-x", "commit": {"sha": "def456"}},
        ]
        respx.get("https://api.github.com/repos/owner/repo/branches").mock(
            return_value=httpx.Response(200, json=mock_branches)
        )
        branches = await github_fetcher.fetch_branches("owner", "repo")
        await github_fetcher.close()
        assert len(branches) == 2
        assert branches[0]["name"] == "main"


class TestFetchBranchCompare:
    @pytest.mark.asyncio
    @respx.mock
    async def test_compare_branches(self, github_fetcher):
        respx.get("https://api.github.com/repos/owner/repo/compare/main...feature").mock(
            return_value=httpx.Response(200, json={"ahead_by": 3, "behind_by": 1})
        )
        result = await github_fetcher.fetch_branch_compare("owner", "repo", "main", "feature")
        await github_fetcher.close()
        assert result["ahead_by"] == 3
        assert result["behind_by"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_compare_branches_404(self, github_fetcher):
        respx.get("https://api.github.com/repos/owner/repo/compare/main...gone").mock(
            return_value=httpx.Response(404)
        )
        result = await github_fetcher.fetch_branch_compare("owner", "repo", "main", "gone")
        await github_fetcher.close()
        assert result == {"ahead_by": 0, "behind_by": 0}


class TestFetchPrReviews:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_reviews(self, github_fetcher):
        mock_reviews = [
            {"id": 1, "user": {"login": "reviewer"}, "state": "APPROVED"},
        ]
        respx.get("https://api.github.com/repos/owner/repo/pulls/1/reviews").mock(
            return_value=httpx.Response(200, json=mock_reviews)
        )
        reviews = await github_fetcher.fetch_pr_reviews("owner", "repo", 1)
        await github_fetcher.close()
        assert len(reviews) == 1
        assert reviews[0]["state"] == "APPROVED"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_review_comments(self, github_fetcher):
        mock_comments = [
            {"id": 1, "body": "Looks good", "user": {"login": "reviewer"}},
        ]
        respx.get("https://api.github.com/repos/owner/repo/pulls/1/comments").mock(
            return_value=httpx.Response(200, json=mock_comments)
        )
        comments = await github_fetcher.fetch_pr_review_comments("owner", "repo", 1)
        await github_fetcher.close()
        assert len(comments) == 1


class TestFetchDefaultBranch:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_default_branch(self, github_fetcher):
        respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(200, json={"default_branch": "develop"})
        )
        branch = await github_fetcher.fetch_default_branch("owner", "repo")
        await github_fetcher.close()
        assert branch == "develop"

    @pytest.mark.asyncio
    @respx.mock
    async def test_default_branch_fallback(self, github_fetcher):
        respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(200, json={})
        )
        branch = await github_fetcher.fetch_default_branch("owner", "repo")
        await github_fetcher.close()
        assert branch == "main"


class TestFetchReadme:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_readme(self, github_fetcher):
        respx.get("https://api.github.com/repos/owner/repo/readme").mock(
            return_value=httpx.Response(200, text="# My Repo\nThis is a test.")
        )
        readme = await github_fetcher.fetch_readme("owner", "repo")
        await github_fetcher.close()
        assert "My Repo" in readme

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_readme_not_found(self, github_fetcher):
        respx.get("https://api.github.com/repos/owner/repo/readme").mock(
            return_value=httpx.Response(404)
        )
        readme = await github_fetcher.fetch_readme("owner", "repo")
        await github_fetcher.close()
        assert readme is None


class TestFetchCommitDetail:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_commit_detail(self, github_fetcher):
        mock_detail = {
            "sha": "abc123",
            "stats": {"additions": 50, "deletions": 10},
            "files": [{"filename": "src/main.py", "status": "modified"}],
        }
        respx.get("https://api.github.com/repos/owner/repo/commits/abc123").mock(
            return_value=httpx.Response(200, json=mock_detail)
        )
        detail = await github_fetcher.fetch_commit_detail("owner", "repo", "abc123")
        await github_fetcher.close()
        assert detail["stats"]["additions"] == 50


class TestPagination:
    @pytest.mark.asyncio
    @respx.mock
    async def test_paginate_multiple_pages(self, github_fetcher):
        """Test that pagination fetches multiple pages."""
        def _make_commit(i):
            return {
                "sha": f"commit{i:03d}",
                "commit": {
                    "message": f"commit {i}",
                    "author": {
                        "name": "Dev",
                        "email": "dev@test.com",
                        "date": "2025-01-15T10:00:00Z",
                    },
                },
                "author": {"login": "dev"},
                "html_url": f"https://github.com/owner/repo/commit/commit{i:03d}",
            }

        page1 = [_make_commit(i) for i in range(100)]
        page2 = [_make_commit(i) for i in range(100, 150)]

        route = respx.get("https://api.github.com/repos/owner/repo/commits")
        route.side_effect = [
            httpx.Response(200, json=page1),
            httpx.Response(200, json=page2),
        ]

        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 2, 1, tzinfo=timezone.utc)
        commits = await github_fetcher.fetch_commits("owner", "repo", since, until)
        await github_fetcher.close()

        # Should have fetched all 150 commits across 2 pages
        assert len(commits) == 150

    @pytest.mark.asyncio
    @respx.mock
    async def test_paginate_stops_on_empty(self, github_fetcher):
        """Test that pagination stops on empty page."""
        page1 = [{"sha": "c1", "commit": {"message": "m", "author": {"name": "A", "email": "a@b.c", "date": "2025-01-15T00:00:00Z"}}, "author": {"login": "a"}, "html_url": "https://x.com/c"}]

        route = respx.get("https://api.github.com/repos/owner/repo/commits")
        route.side_effect = [
            httpx.Response(200, json=page1),
            httpx.Response(200, json=[]),
        ]

        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 2, 1, tzinfo=timezone.utc)
        commits = await github_fetcher.fetch_commits("owner", "repo", since, until)
        await github_fetcher.close()

        assert len(commits) == 1


class TestCreateIssueWithoutLabels:
    @pytest.mark.asyncio
    @respx.mock
    async def test_create_issue_no_labels(self, github_fetcher):
        respx.post("https://api.github.com/repos/owner/repo/issues").mock(
            return_value=httpx.Response(201, json={"number": 42, "html_url": "https://github.com/owner/repo/issues/42"})
        )
        result = await github_fetcher.create_issue("owner", "repo", "Title", "Body")
        await github_fetcher.close()
        assert result["number"] == 42


class TestClientLifecycle:
    @pytest.mark.asyncio
    async def test_close_without_client(self):
        fetcher = GitHubFetcher()
        await fetcher.close()  # should not raise

    @pytest.mark.asyncio
    @respx.mock
    async def test_close_after_use(self, github_fetcher):
        respx.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(200, json={"name": "repo"})
        )
        await github_fetcher.fetch_repo_info("owner", "repo")
        await github_fetcher.close()
        assert github_fetcher._client is None
