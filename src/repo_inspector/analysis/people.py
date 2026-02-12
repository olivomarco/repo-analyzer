"""People analysis — deterministic stats from GitHub data."""

from collections import defaultdict
from pathlib import PurePosixPath

from repo_inspector.models import (
    Commit,
    ContributorStats,
    Issue,
    PullRequest,
)


def compute_contributor_stats(
    commits: list[Commit],
    prs: list[PullRequest],
    issues: list[Issue],
) -> list[ContributorStats]:
    """Build deterministic contribution stats from raw GitHub data."""

    by_login: dict[str, ContributorStats] = {}

    # ── Commits ───────────────────────────────────────────────────────────
    for c in commits:
        key = c.author_login or c.author_email or c.author_name
        if key not in by_login:
            by_login[key] = ContributorStats(
                login=key,
                name=c.author_name,
                email=c.author_email,
            )
        s = by_login[key]
        s.commit_count += 1
        s.lines_added += c.additions
        s.lines_removed += c.deletions

        for fp in c.files_changed:
            if fp not in s.files_touched:
                s.files_touched.append(fp)

        if s.first_commit_date is None or c.date < s.first_commit_date:
            s.first_commit_date = c.date
        if s.last_commit_date is None or c.date > s.last_commit_date:
            s.last_commit_date = c.date

    # ── PRs ───────────────────────────────────────────────────────────────
    for pr in prs:
        key = pr.author
        if key not in by_login:
            by_login[key] = ContributorStats(login=key)
        s = by_login[key]
        s.prs_opened += 1
        if pr.merged_at:
            s.prs_merged += 1

    # ── Issues ────────────────────────────────────────────────────────────
    for issue in issues:
        key = issue.author
        if key not in by_login:
            by_login[key] = ContributorStats(login=key)
        s = by_login[key]
        s.issues_opened += 1
        if issue.closed_at:
            s.issues_closed += 1

    # ── Top directories ───────────────────────────────────────────────────
    for s in by_login.values():
        dir_counts: dict[str, int] = defaultdict(int)
        for fp in s.files_touched:
            parts = PurePosixPath(fp).parts
            if len(parts) > 1:
                dir_counts[parts[0]] += 1
            else:
                dir_counts["."] += 1
        s.top_directories = [
            d for d, _ in sorted(dir_counts.items(), key=lambda x: -x[1])[:5]
        ]

    # Sort by commit count descending
    return sorted(by_login.values(), key=lambda s: -s.commit_count)


def compute_bus_factor(stats: list[ContributorStats], threshold: float = 0.8) -> int:
    """Estimate bus factor: minimum contributors covering `threshold` of commits."""
    total = sum(s.commit_count for s in stats)
    if total == 0:
        return 0
    cumulative = 0
    for i, s in enumerate(stats, start=1):
        cumulative += s.commit_count
        if cumulative / total >= threshold:
            return i
    return len(stats)
