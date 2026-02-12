"""Dependency Risk Scanner — detect and analyze project dependencies."""

from repo_inspector.cloner import RepoCloner
from repo_inspector.models import DependencyInfo, DependencyReport


def build_dependency_report(cloner: RepoCloner) -> DependencyReport:
    """Parse dependency files and build a risk report skeleton."""
    raw_deps = cloner.parse_dependencies()
    ecosystems: set[str] = set()
    deps: list[DependencyInfo] = []

    for d in raw_deps:
        ecosystems.add(d["ecosystem"])
        deps.append(
            DependencyInfo(
                name=d["name"],
                version=d.get("version", ""),
                source_file=d.get("source_file", ""),
                ecosystem=d["ecosystem"],
            )
        )

    return DependencyReport(
        dependencies=deps,
        total_deps=len(deps),
        ecosystems=sorted(ecosystems),
    )
