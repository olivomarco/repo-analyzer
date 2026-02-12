"""Code / Security analysis — folder-level static inspection."""

from repo_inspector.cloner import RepoCloner
from repo_inspector.models import FolderAnalysis


def build_folder_analyses(cloner: RepoCloner) -> list[FolderAnalysis]:
    """Create a FolderAnalysis skeleton for each top-level directory."""
    dirs = cloner.list_top_level_dirs()
    analyses: list[FolderAnalysis] = []
    for d in dirs:
        stats = cloner.folder_stats(d)
        langs = cloner.detect_languages(d)
        analyses.append(
            FolderAnalysis(
                path=d,
                file_count=stats["files"],
                total_lines=stats["lines"],
                languages=langs,
            )
        )
    return analyses
