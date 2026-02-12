"""Functional analysis — repo overview via local file inspection."""

from pathlib import Path
from typing import Optional

from repo_inspector.cloner import RepoCloner
from repo_inspector.models import FunctionalArea


def build_functional_areas(cloner: RepoCloner) -> list[FunctionalArea]:
    """Identify logical functional areas from top-level directories."""
    dirs = cloner.list_top_level_dirs()
    areas: list[FunctionalArea] = []
    for d in dirs:
        stats = cloner.folder_stats(d)
        langs = cloner.detect_languages(d)
        key_files = [
            str(f) for f in cloner.list_files_in_dir(d)[:15]
        ]
        areas.append(
            FunctionalArea(
                name=d,
                path=d,
                key_files=key_files,
                description=f"{stats['files']} files, {stats['lines']} lines — {', '.join(langs) or 'unknown'}",
            )
        )
    return areas


def gather_code_samples(
    cloner: RepoCloner,
    folder: str,
    max_files: int = 8,
    max_lines_per_file: int = 120,
) -> str:
    """Collect representative code snippets from a folder for LLM analysis."""
    code_exts = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
        ".kt", ".cs", ".rb", ".php", ".swift", ".c", ".cpp", ".h",
        ".sh", ".tf", ".sql",
    }
    files = cloner.list_files_in_dir(folder, extensions=code_exts)[:max_files]
    parts: list[str] = []
    for fp in files:
        content = cloner.read_file(str(fp), max_lines=max_lines_per_file)
        if content.strip():
            parts.append(f"--- {fp} ---\n{content}")
    return "\n\n".join(parts)
