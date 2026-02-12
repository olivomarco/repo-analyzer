"""Bus Factor Mitigation — generate actionable plans for low bus factor."""

from collections import defaultdict

from repo_inspector.models import (
    BusFactorMitigationReport,
    Commit,
    ContributorStats,
)


def build_bus_mitigation(
    stats: list[ContributorStats],
    commits: list[Commit],
    bus_factor: int,
) -> BusFactorMitigationReport:
    """Build a mitigation report for low bus factor scenarios.

    Identifies knowledge monopolists and their exclusive file ownership.
    """
    # Risk level
    if bus_factor <= 1:
        risk_level = "critical"
    elif bus_factor <= 2:
        risk_level = "high"
    elif bus_factor <= 3:
        risk_level = "medium"
    else:
        risk_level = "low"

    # Map files to contributors who touched them
    file_owners: dict[str, set[str]] = defaultdict(set)
    for c in commits:
        login = c.author_login or c.author_email or c.author_name
        for fp in c.files_changed:
            file_owners[fp].add(login)

    # Find exclusive files (only one contributor)
    exclusive: dict[str, list[str]] = defaultdict(list)
    for fp, owners in file_owners.items():
        if len(owners) == 1:
            owner = next(iter(owners))
            exclusive[owner].append(fp)

    # Sort exclusive files per person, limit to top 20
    for login in exclusive:
        exclusive[login] = sorted(exclusive[login])[:20]

    # Knowledge monopolists: contributors with exclusive areas
    monopolists: list[str] = []
    for s in stats[:10]:
        if len(exclusive.get(s.login, [])) > 5:
            monopolists.append(s.login)

    # Also consider top contributor if they have 60%+ of commits
    total_commits = sum(s.commit_count for s in stats)
    if stats and total_commits > 0:
        top_share = stats[0].commit_count / total_commits
        if top_share > 0.6 and stats[0].login not in monopolists:
            monopolists.insert(0, stats[0].login)

    return BusFactorMitigationReport(
        bus_factor=bus_factor,
        risk_level=risk_level,
        knowledge_monopolists=monopolists,
        exclusive_files=dict(exclusive),
    )
