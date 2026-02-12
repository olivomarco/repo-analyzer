"""What-If Simulator — simulate contributor/module removal scenarios."""

from repo_inspector.analysis.people import compute_bus_factor, compute_contributor_stats
from repo_inspector.models import (
    Commit,
    ContributorStats,
    Issue,
    PullRequest,
    WhatIfReport,
    WhatIfScenario,
)


def simulate_remove_contributor(
    login: str,
    commits: list[Commit],
    prs: list[PullRequest],
    issues: list[Issue],
    current_bus_factor: int,
) -> WhatIfScenario:
    """Simulate what happens if a contributor leaves."""
    # Filter out the contributor's commits
    filtered_commits = [
        c for c in commits
        if (c.author_login or c.author_email or c.author_name) != login
    ]
    filtered_prs = [p for p in prs if p.author != login]
    filtered_issues = [i for i in issues if i.author != login]

    # Recompute stats
    new_stats = compute_contributor_stats(filtered_commits, filtered_prs, filtered_issues)
    new_bus_factor = compute_bus_factor(new_stats)

    # Find orphaned files (files only this contributor touched)
    contributor_files: set[str] = set()
    other_files: set[str] = set()
    for c in commits:
        c_login = c.author_login or c.author_email or c.author_name
        for fp in c.files_changed:
            if c_login == login:
                contributor_files.add(fp)
            else:
                other_files.add(fp)

    orphaned = sorted(contributor_files - other_files)

    # Find affected areas (top-level dirs)
    affected_dirs: set[str] = set()
    for fp in orphaned:
        parts = fp.split("/")
        if len(parts) > 1:
            affected_dirs.add(parts[0])

    return WhatIfScenario(
        scenario="remove_contributor",
        parameter=login,
        bus_factor_before=current_bus_factor,
        bus_factor_after=new_bus_factor,
        orphaned_files=orphaned[:30],
        affected_areas=sorted(affected_dirs),
    )


def simulate_deprecate_module(
    module: str,
    commits: list[Commit],
) -> WhatIfScenario:
    """Simulate what happens if a module/directory is deprecated."""
    # Find contributors who primarily work in this module
    affected_contributors: set[str] = set()
    module_files: list[str] = []

    for c in commits:
        login = c.author_login or c.author_email or c.author_name
        for fp in c.files_changed:
            if fp.startswith(module + "/") or fp.startswith(module):
                affected_contributors.add(login)
                module_files.append(fp)

    unique_files = sorted(set(module_files))

    return WhatIfScenario(
        scenario="deprecate_module",
        parameter=module,
        bus_factor_before=0,  # N/A for module deprecation
        bus_factor_after=0,
        orphaned_files=unique_files[:30],
        affected_areas=sorted(affected_contributors),
    )


def build_what_if_report(
    stats: list[ContributorStats],
    commits: list[Commit],
    prs: list[PullRequest],
    issues: list[Issue],
    bus_factor: int,
    top_dirs: list[str],
) -> WhatIfReport:
    """Build what-if simulations for top contributors and key modules."""
    scenarios: list[WhatIfScenario] = []

    # Simulate removing top 3 contributors
    for s in stats[:3]:
        scenario = simulate_remove_contributor(
            s.login, commits, prs, issues, bus_factor
        )
        scenarios.append(scenario)

    # Simulate deprecating largest directories
    for d in top_dirs[:3]:
        scenario = simulate_deprecate_module(d, commits)
        scenarios.append(scenario)

    return WhatIfReport(scenarios=scenarios)
