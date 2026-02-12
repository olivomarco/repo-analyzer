"""GitHub data fetching via REST API."""

from datetime import datetime
from typing import Optional

import httpx

from repo_inspector.models import Commit, Issue, PullRequest


class GitHubFetcher:
    """Fetches commits, PRs, and issues from the GitHub REST API."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token
        self.base_url = "https://api.github.com"
        self._client: Optional[httpx.AsyncClient] = None
        self._saml_fallback = False  # True if we dropped auth due to SAML

    # ── HTTP plumbing ─────────────────────────────────────────────────────

    @property
    def headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token and not self._saml_fallback:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def _client_instance(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=30.0,
            )
        return self._client

    async def _rebuild_client_without_auth(self) -> None:
        """Drop auth and rebuild client for SAML-protected public repos."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._saml_fallback = True
        await self._client_instance()

    async def _get(self, path: str, **kwargs) -> httpx.Response:  # type: ignore[no-untyped-def]
        """GET with automatic SAML fallback and rate-limit awareness."""
        client = await self._client_instance()
        resp = await client.get(path, **kwargs)
        if resp.status_code == 403 and "SAML" in resp.text:
            await self._rebuild_client_without_auth()
            client = await self._client_instance()
            resp = await client.get(path, **kwargs)
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            remaining = resp.headers.get("x-ratelimit-remaining", "0")
            reset = resp.headers.get("x-ratelimit-reset", "")
            if self._saml_fallback:
                hint = (
                    "Running unauthenticated (60 req/hour) due to SAML fallback. "
                    "Authorize your PAT for this org via SAML SSO to get 5 000 req/hour."
                )
            else:
                hint = (
                    f"Authenticated rate limit hit (remaining: {remaining}). "
                    "Wait a few minutes and retry."
                )
            raise httpx.HTTPStatusError(
                f"GitHub API rate limit exceeded. {hint}",
                request=resp.request,
                response=resp,
            )
        return resp

    @property
    def is_unauthenticated(self) -> bool:
        """True if we fell back to no-auth (SAML) mode."""
        return self._saml_fallback

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Paginated helper ──────────────────────────────────────────────────

    async def _paginate(
        self,
        path: str,
        params: Optional[dict[str, str]] = None,
        max_pages: int = 10,
    ) -> list[dict]:
        """Fetch all pages from a paginated GitHub endpoint."""
        params = dict(params or {})
        params.setdefault("per_page", "100")

        results: list[dict] = []
        for page in range(1, max_pages + 1):
            params["page"] = str(page)
            resp = await self._get(path, params=params)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            results.extend(data)
            if len(data) < int(params["per_page"]):
                break
        return results

    # ── Commits ───────────────────────────────────────────────────────────

    async def fetch_commits(
        self,
        owner: str,
        repo: str,
        since: datetime,
        until: datetime,
    ) -> list[Commit]:
        """Fetch commits in the given time window."""
        raw = await self._paginate(
            f"/repos/{owner}/{repo}/commits",
            params={
                "since": since.isoformat(),
                "until": until.isoformat(),
            },
        )
        commits: list[Commit] = []
        for item in raw:
            commit_detail = item.get("commit", {})
            author_info = commit_detail.get("author", {})
            commits.append(
                Commit(
                    sha=item["sha"],
                    message=commit_detail.get("message", ""),
                    author_name=author_info.get("name", "Unknown"),
                    author_email=author_info.get("email", ""),
                    author_login=(item.get("author") or {}).get("login"),
                    date=datetime.fromisoformat(
                        author_info["date"].replace("Z", "+00:00")
                    ),
                    url=item["html_url"],
                )
            )
        return commits

    async def fetch_commit_detail(
        self, owner: str, repo: str, sha: str
    ) -> dict:
        """Fetch full commit details (with file stats)."""
        resp = await self._get(f"/repos/{owner}/{repo}/commits/{sha}")
        resp.raise_for_status()
        return resp.json()

    # ── Pull Requests ─────────────────────────────────────────────────────

    async def fetch_pull_requests(
        self,
        owner: str,
        repo: str,
        since: datetime,
        until: datetime,
        state: str = "all",
    ) -> list[PullRequest]:
        """Fetch PRs updated in the given time window."""
        raw = await self._paginate(
            f"/repos/{owner}/{repo}/pulls",
            params={
                "state": state,
                "sort": "updated",
                "direction": "desc",
            },
        )
        prs: list[PullRequest] = []
        for item in raw:
            created_at = datetime.fromisoformat(
                item["created_at"].replace("Z", "+00:00")
            )
            # Filter by time window
            if created_at > until:
                continue
            updated_at = datetime.fromisoformat(
                item["updated_at"].replace("Z", "+00:00")
            )
            if updated_at < since:
                break  # Sorted desc by updated — can stop early

            merged_at = None
            if item.get("merged_at"):
                merged_at = datetime.fromisoformat(
                    item["merged_at"].replace("Z", "+00:00")
                )
            closed_at = None
            if item.get("closed_at"):
                closed_at = datetime.fromisoformat(
                    item["closed_at"].replace("Z", "+00:00")
                )

            prs.append(
                PullRequest(
                    number=item["number"],
                    title=item["title"],
                    body=item.get("body"),
                    author=item["user"]["login"],
                    created_at=created_at,
                    merged_at=merged_at,
                    closed_at=closed_at,
                    url=item["html_url"],
                    labels=[l["name"] for l in item.get("labels", [])],
                    additions=item.get("additions", 0),
                    deletions=item.get("deletions", 0),
                    changed_files=item.get("changed_files", 0),
                )
            )
        return prs

    # ── Issues ────────────────────────────────────────────────────────────

    async def fetch_issues(
        self,
        owner: str,
        repo: str,
        since: datetime,
        state: str = "all",
    ) -> list[Issue]:
        """Fetch issues updated since the given date (excludes PRs)."""
        raw = await self._paginate(
            f"/repos/{owner}/{repo}/issues",
            params={
                "state": state,
                "since": since.isoformat(),
                "sort": "updated",
                "direction": "desc",
            },
        )
        issues: list[Issue] = []
        for item in raw:
            if "pull_request" in item:
                continue
            closed_at = None
            if item.get("closed_at"):
                closed_at = datetime.fromisoformat(
                    item["closed_at"].replace("Z", "+00:00")
                )
            issues.append(
                Issue(
                    number=item["number"],
                    title=item["title"],
                    body=item.get("body"),
                    author=item["user"]["login"],
                    state=item["state"],
                    created_at=datetime.fromisoformat(
                        item["created_at"].replace("Z", "+00:00")
                    ),
                    closed_at=closed_at,
                    url=item["html_url"],
                    labels=[l["name"] for l in item.get("labels", [])],
                )
            )
        return issues

    # ── Repo metadata ─────────────────────────────────────────────────────

    async def fetch_repo_info(self, owner: str, repo: str) -> dict:
        """Fetch basic repo information."""
        resp = await self._get(f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        return resp.json()

    async def fetch_readme(self, owner: str, repo: str) -> Optional[str]:
        """Fetch decoded README content."""
        resp = await self._get(
            f"/repos/{owner}/{repo}/readme",
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.text

    # ── Branches ──────────────────────────────────────────────────────────

    async def fetch_branches(
        self, owner: str, repo: str, max_pages: int = 5
    ) -> list[dict]:
        """Fetch all branches with their last commit info."""
        return await self._paginate(
            f"/repos/{owner}/{repo}/branches",
            max_pages=max_pages,
        )

    async def fetch_branch_compare(
        self, owner: str, repo: str, base: str, head: str
    ) -> dict:
        """Compare two branches (ahead/behind counts)."""
        resp = await self._get(
            f"/repos/{owner}/{repo}/compare/{base}...{head}"
        )
        if resp.status_code == 404:
            return {"ahead_by": 0, "behind_by": 0}
        resp.raise_for_status()
        return resp.json()

    # ── PR Reviews ────────────────────────────────────────────────────────

    async def fetch_pr_reviews(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict]:
        """Fetch reviews for a single PR."""
        return await self._paginate(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            max_pages=3,
        )

    async def fetch_pr_review_comments(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict]:
        """Fetch review comments for a single PR."""
        return await self._paginate(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            max_pages=3,
        )

    async def fetch_default_branch(self, owner: str, repo: str) -> str:
        """Get the default branch name for a repository."""
        info = await self.fetch_repo_info(owner, repo)
        return info.get("default_branch", "main")
