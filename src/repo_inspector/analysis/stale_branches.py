"""Stale Branch Cemetery — identify abandoned branches."""

from datetime import datetime, timezone

from repo_inspector.models import StaleBranch, StaleBranchReport


def build_stale_branch_report(
    branches: list[dict],
    default_branch: str,
    compare_data: dict[str, dict],
    stale_threshold_days: int = 60,
) -> StaleBranchReport:
    """Analyze branches for staleness.

    Args:
        branches: Raw branch data from GitHub API.
        default_branch: The repo's default branch name.
        compare_data: Mapping of branch_name -> compare API response.
        stale_threshold_days: Days without commits to consider stale.
    """
    now = datetime.now(timezone.utc)
    stale: list[StaleBranch] = []

    for branch in branches:
        name = branch.get("name", "")
        if name == default_branch:
            continue

        commit_info = branch.get("commit", {})

        # Try to get last commit date from commit info
        last_date = None
        commit_data = commit_info.get("commit", {})
        if commit_data:
            author_info = commit_data.get("author", {}) or commit_data.get("committer", {})
            date_str = author_info.get("date", "")
            if date_str:
                try:
                    last_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

        days_old = (now - last_date).days if last_date else 999

        if days_old < stale_threshold_days:
            continue

        # Determine ahead/behind
        cmp = compare_data.get(name, {})
        ahead = cmp.get("ahead_by", 0)
        behind = cmp.get("behind_by", 0)
        ahead_behind = f"{ahead} ahead, {behind} behind"

        # Get author
        author = ""
        commit_author = commit_data.get("author", {})
        if commit_author:
            author = commit_author.get("name", "")

        # Categorize
        name_lower = name.lower()
        if "wip" in name_lower or "draft" in name_lower:
            category = "wip"
        elif "feature" in name_lower or "feat" in name_lower:
            category = "stale-feature"
        elif "fix" in name_lower or "bug" in name_lower or "hotfix" in name_lower:
            category = "stale-fix"
        elif ahead == 0:
            category = "orphan"
        else:
            category = "abandoned"

        stale.append(
            StaleBranch(
                name=name,
                last_commit_date=last_date,
                author=author,
                days_stale=days_old,
                ahead_behind=ahead_behind,
                category=category,
            )
        )

    # Sort by staleness
    stale.sort(key=lambda b: -b.days_stale)

    return StaleBranchReport(
        total_branches=len(branches),
        stale_branches=stale,
        cleanup_candidates=sum(1 for b in stale if b.category in ("orphan", "wip")),
    )
