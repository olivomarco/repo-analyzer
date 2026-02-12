"""Knowledge Map — Contributor × Folder heatmap analysis."""

from collections import defaultdict

from repo_inspector.models import (
    Commit,
    ContributorStats,
    KnowledgeCell,
    KnowledgeMapReport,
)


def build_knowledge_map(
    stats: list[ContributorStats],
    commits: list[Commit],
    top_dirs: list[str],
) -> KnowledgeMapReport:
    """Build a contributor × folder knowledge matrix from commit data."""
    # Count commits and lines per (contributor, folder)
    contrib_folder_commits: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    contrib_folder_lines: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for c in commits:
        login = c.author_login or c.author_email or c.author_name
        for fp in c.files_changed:
            parts = fp.split("/")
            folder = parts[0] if len(parts) > 1 else "."
            if folder in top_dirs:
                contrib_folder_commits[login][folder] += 1
                contrib_folder_lines[login][folder] += c.additions + c.deletions

    # Get active contributors (limit to top 15 by commit count)
    active_logins = [s.login for s in stats[:15]]

    # Build cells with normalized scores
    cells: list[KnowledgeCell] = []
    max_commits = 1  # avoid division by zero
    for login in active_logins:
        for folder in top_dirs:
            ct = contrib_folder_commits[login].get(folder, 0)
            if ct > max_commits:
                max_commits = ct

    for login in active_logins:
        for folder in top_dirs:
            ct = contrib_folder_commits[login].get(folder, 0)
            lines = contrib_folder_lines[login].get(folder, 0)
            score = ct / max_commits if max_commits > 0 else 0.0
            cells.append(
                KnowledgeCell(
                    login=login,
                    folder=folder,
                    score=round(score, 3),
                    commits=ct,
                    lines_changed=lines,
                )
            )

    # Detect knowledge silos — folders where 80%+ commits come from one person
    silos: list[str] = []
    for folder in top_dirs:
        folder_total = sum(
            contrib_folder_commits[login].get(folder, 0) for login in active_logins
        )
        if folder_total == 0:
            continue
        for login in active_logins:
            ct = contrib_folder_commits[login].get(folder, 0)
            if ct / folder_total >= 0.8:
                silos.append(f"{folder}/ (dominated by @{login}, {ct}/{folder_total} commits)")
                break

    return KnowledgeMapReport(
        contributors=active_logins,
        folders=top_dirs,
        cells=cells,
        knowledge_silos=silos,
    )
