"""Commit Journal — auto-generated changelog from commits and PRs."""

from repo_inspector.models import ChangelogEntry, ChangelogReport, Commit, PullRequest


def build_changelog(
    commits: list[Commit],
    prs: list[PullRequest],
) -> ChangelogReport:
    """Build a changelog skeleton from commits and PRs.

    Uses PR titles when available; falls back to commit messages.
    Categorizes entries by conventional-commit-like prefixes.
    """
    entries: list[ChangelogEntry] = []
    seen_prs: set[int] = set()

    # Prefer merged PRs as changelog entries
    for pr in prs:
        if pr.merged_at and pr.number not in seen_prs:
            seen_prs.add(pr.number)
            category = _infer_category(pr.title)
            entries.append(
                ChangelogEntry(
                    category=category,
                    description=pr.title,
                    author=pr.author,
                    pr_number=pr.number,
                )
            )

    # Add notable commits not covered by PRs (merge commits excluded)
    for c in commits:
        msg = c.message.split("\n")[0].strip()
        if msg.startswith("Merge ") or msg.startswith("Merge pull request"):
            continue
        # Skip very short messages
        if len(msg) < 10:
            continue
        category = _infer_category(msg)
        entries.append(
            ChangelogEntry(
                category=category,
                description=msg,
                author=c.author_login or c.author_name,
                sha=c.short_sha,
            )
        )

    # Deduplicate by description similarity
    entries = _deduplicate(entries)

    return ChangelogReport(entries=entries)


def _infer_category(text: str) -> str:
    """Infer conventional commit category from text."""
    lower = text.lower()
    if lower.startswith("feat") or "feature" in lower or "add " in lower or "new " in lower:
        return "feat"
    if lower.startswith("fix") or "bug" in lower or "patch" in lower or "repair" in lower:
        return "fix"
    if lower.startswith("docs") or "readme" in lower or "documentation" in lower:
        return "docs"
    if lower.startswith("refactor") or "cleanup" in lower or "clean up" in lower:
        return "refactor"
    if lower.startswith("test") or "spec" in lower:
        return "test"
    if lower.startswith("chore") or "bump" in lower or "update dep" in lower or "upgrade" in lower:
        return "chore"
    if "perf" in lower or "speed" in lower or "optim" in lower:
        return "perf"
    if "ci" in lower or "pipeline" in lower or "workflow" in lower or "action" in lower:
        return "ci"
    if "style" in lower or "format" in lower or "lint" in lower:
        return "style"
    return "chore"


def _deduplicate(entries: list[ChangelogEntry]) -> list[ChangelogEntry]:
    """Remove near-duplicate entries (same description)."""
    seen: set[str] = set()
    unique: list[ChangelogEntry] = []
    for e in entries:
        key = e.description.lower().strip()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def render_changelog_markdown(report: ChangelogReport) -> str:
    """Render a ChangelogReport as markdown text."""
    category_labels = {
        "feat": "✨ Features",
        "fix": "🐛 Bug Fixes",
        "docs": "📚 Documentation",
        "refactor": "♻️ Refactoring",
        "test": "🧪 Tests",
        "chore": "🔧 Chores",
        "perf": "⚡ Performance",
        "ci": "🔄 CI/CD",
        "style": "💅 Style",
    }

    # Group by category
    by_cat: dict[str, list[ChangelogEntry]] = {}
    for e in report.entries:
        by_cat.setdefault(e.category, []).append(e)

    lines: list[str] = ["# Changelog\n"]

    for cat in ("feat", "fix", "refactor", "perf", "docs", "test", "ci", "chore", "style"):
        items = by_cat.get(cat, [])
        if not items:
            continue
        label = category_labels.get(cat, cat.title())
        lines.append(f"## {label}\n")
        for e in items:
            ref = ""
            if e.pr_number:
                ref = f" (#{e.pr_number})"
            elif e.sha:
                ref = f" ({e.sha})"
            author = f" — @{e.author}" if e.author else ""
            lines.append(f"- {e.description}{ref}{author}")
        lines.append("")

    md = "\n".join(lines)
    report.markdown = md
    return md
