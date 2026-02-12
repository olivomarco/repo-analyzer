"""Git repo cloning and local file analysis utilities."""

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import git  # GitPython


class RepoCloner:
    """Clones a GitHub repo to a temporary directory for local analysis."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token
        self._clone_dir: Optional[Path] = None

    @property
    def clone_path(self) -> Optional[Path]:
        return self._clone_dir

    def clone(self, owner: str, repo: str, depth: int = 1) -> Path:
        """Shallow-clone the repo and return the local path."""
        self._clone_dir = Path(tempfile.mkdtemp(prefix=f"repoinspect-{repo}-"))
        url = f"https://github.com/{owner}/{repo}.git"
        auth_url = url
        if self.token and self.token.strip():
            auth_url = f"https://x-access-token:{self.token}@github.com/{owner}/{repo}.git"

        env = {"GIT_TERMINAL_PROMPT": "0"}  # Never prompt for credentials

        try:
            git.Repo.clone_from(
                auth_url,
                str(self._clone_dir),
                depth=depth,
                single_branch=True,
                env=env,
            )
        except git.exc.GitCommandError:
            # Auth clone failed (e.g. SAML-protected org) — retry without token
            if auth_url != url:
                shutil.rmtree(self._clone_dir, ignore_errors=True)
                self._clone_dir = Path(tempfile.mkdtemp(prefix=f"repoinspect-{repo}-"))
                git.Repo.clone_from(
                    url,
                    str(self._clone_dir),
                    depth=depth,
                    single_branch=True,
                    env=env,
                )
            else:
                raise
        return self._clone_dir

    def cleanup(self) -> None:
        """Remove the cloned directory."""
        if self._clone_dir and self._clone_dir.exists():
            shutil.rmtree(self._clone_dir, ignore_errors=True)
            self._clone_dir = None

    # ── Directory / file helpers ──────────────────────────────────────────

    def list_top_level_dirs(self) -> list[str]:
        """Return top-level directories (excluding hidden / common noise)."""
        if not self._clone_dir:
            return []
        skip = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}
        return sorted(
            d.name
            for d in self._clone_dir.iterdir()
            if d.is_dir() and d.name not in skip and not d.name.startswith(".")
        )

    def list_files_in_dir(
        self, subdir: str, extensions: Optional[set[str]] = None
    ) -> list[Path]:
        """List all files under a subdirectory, optionally filtered by extension."""
        if not self._clone_dir:
            return []
        target = self._clone_dir / subdir
        if not target.exists():
            return []
        files = []
        for p in target.rglob("*"):
            if not p.is_file():
                continue
            if p.name.startswith("."):
                continue
            if extensions and p.suffix not in extensions:
                continue
            files.append(p.relative_to(self._clone_dir))
        return sorted(files)

    def read_file(self, relpath: str, max_lines: int = 500) -> str:
        """Read a file from the cloned repo (truncated)."""
        if not self._clone_dir:
            return ""
        fpath = self._clone_dir / relpath
        if not fpath.is_file():
            return ""
        try:
            lines = fpath.read_text(errors="replace").splitlines()
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} lines truncated)"
            return "\n".join(lines)
        except Exception:
            return ""

    def get_tree_summary(self, max_depth: int = 3) -> str:
        """Generate a tree-like summary of the repo structure."""
        if not self._clone_dir:
            return ""
        lines: list[str] = []
        skip = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox", ".mypy_cache"}
        self._walk_tree(self._clone_dir, lines, skip, depth=0, max_depth=max_depth)
        return "\n".join(lines)

    def _walk_tree(
        self,
        path: Path,
        lines: list[str],
        skip: set[str],
        depth: int,
        max_depth: int,
    ) -> None:
        if depth > max_depth:
            return
        indent = "  " * depth
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for entry in entries:
            if entry.name in skip or entry.name.startswith("."):
                continue
            if entry.is_dir():
                lines.append(f"{indent}{entry.name}/")
                self._walk_tree(entry, lines, skip, depth + 1, max_depth)
            else:
                size = entry.stat().st_size
                lines.append(f"{indent}{entry.name}  ({_human_size(size)})")

    def folder_stats(self, subdir: str) -> dict[str, int]:
        """Count files and total lines in a subdirectory."""
        if not self._clone_dir:
            return {"files": 0, "lines": 0}
        target = self._clone_dir / subdir
        if not target.exists():
            return {"files": 0, "lines": 0}
        file_count = 0
        line_count = 0
        for p in target.rglob("*"):
            if not p.is_file() or p.name.startswith("."):
                continue
            file_count += 1
            try:
                line_count += len(p.read_text(errors="replace").splitlines())
            except Exception:
                pass
        return {"files": file_count, "lines": line_count}

    def detect_languages(self, subdir: str) -> list[str]:
        """Detect programming languages in a subdirectory by extension."""
        ext_map: dict[str, str] = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".jsx": "React JSX", ".tsx": "React TSX", ".go": "Go",
            ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
            ".cs": "C#", ".rb": "Ruby", ".php": "PHP",
            ".swift": "Swift", ".c": "C", ".cpp": "C++",
            ".h": "C/C++ Header", ".sh": "Shell", ".yml": "YAML",
            ".yaml": "YAML", ".json": "JSON", ".toml": "TOML",
            ".md": "Markdown", ".html": "HTML", ".css": "CSS",
            ".scss": "SCSS", ".sql": "SQL", ".tf": "Terraform",
            ".dockerfile": "Docker", ".proto": "Protobuf",
        }
        if not self._clone_dir:
            return []
        target = self._clone_dir / subdir
        if not target.exists():
            return []
        langs: set[str] = set()
        for p in target.rglob("*"):
            if p.is_file():
                lang = ext_map.get(p.suffix.lower())
                if lang:
                    langs.add(lang)
                elif p.name.lower() == "dockerfile":
                    langs.add("Docker")
        return sorted(langs)

    # ── Dependency detection ──────────────────────────────────────────────

    def detect_dependency_files(self) -> dict[str, str]:
        """Find dependency/manifest files and return {path: ecosystem}."""
        if not self._clone_dir:
            return {}
        patterns: dict[str, str] = {
            "requirements.txt": "python",
            "requirements-dev.txt": "python",
            "requirements-test.txt": "python",
            "Pipfile": "python",
            "pyproject.toml": "python",
            "setup.py": "python",
            "setup.cfg": "python",
            "package.json": "npm",
            "yarn.lock": "npm",
            "Cargo.toml": "rust",
            "go.mod": "go",
            "Gemfile": "ruby",
            "composer.json": "php",
            "pom.xml": "java",
            "build.gradle": "java",
            "build.gradle.kts": "kotlin",
            "pubspec.yaml": "dart",
            "Package.swift": "swift",
            "*.csproj": "dotnet",
            "*.fsproj": "dotnet",
        }
        found: dict[str, str] = {}
        for p in self._clone_dir.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(self._clone_dir))
            for pattern_name, eco in patterns.items():
                if pattern_name.startswith("*"):
                    if p.suffix == pattern_name[1:]:
                        found[rel] = eco
                elif p.name == pattern_name:
                    found[rel] = eco
        return found

    def parse_dependencies(self) -> list[dict[str, str]]:
        """Parse dependency files and return list of {name, version, source_file, ecosystem}."""
        dep_files = self.detect_dependency_files()
        deps: list[dict[str, str]] = []

        for rel_path, ecosystem in dep_files.items():
            fpath = self._clone_dir / rel_path if self._clone_dir else None
            if not fpath or not fpath.is_file():
                continue
            try:
                content = fpath.read_text(errors="replace")
            except Exception:
                continue

            if ecosystem == "python" and fpath.name == "requirements.txt" or "requirements" in fpath.name and fpath.suffix == ".txt":
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    match = re.match(r"^([A-Za-z0-9_.-]+)\s*([><=!~]+\s*[^\s,;#]+)?", line)
                    if match:
                        deps.append({
                            "name": match.group(1),
                            "version": (match.group(2) or "").strip(),
                            "source_file": rel_path,
                            "ecosystem": ecosystem,
                        })
            elif ecosystem == "python" and fpath.name == "pyproject.toml":
                in_deps = False
                for line in content.splitlines():
                    if "[project]" in line or "dependencies" in line and "=" in line:
                        in_deps = True
                        continue
                    if in_deps and line.strip().startswith("]"):
                        in_deps = False
                    if in_deps:
                        match = re.match(r'^\s*"?([A-Za-z0-9_.-]+)\s*([><=!~]+[^"]*)?', line)
                        if match and match.group(1) not in ("name", "version", "description"):
                            deps.append({
                                "name": match.group(1),
                                "version": (match.group(2) or "").strip().rstrip('",'),
                                "source_file": rel_path,
                                "ecosystem": ecosystem,
                            })
            elif ecosystem == "npm" and fpath.name == "package.json":
                try:
                    pkg = json.loads(content)
                    for section in ("dependencies", "devDependencies"):
                        for name, ver in pkg.get(section, {}).items():
                            deps.append({
                                "name": name,
                                "version": ver,
                                "source_file": rel_path,
                                "ecosystem": ecosystem,
                            })
                except json.JSONDecodeError:
                    pass
            elif ecosystem == "go" and fpath.name == "go.mod":
                for line in content.splitlines():
                    match = re.match(r"^\s+([\w./\-]+)\s+(v[\w.+-]+)", line)
                    if match:
                        deps.append({
                            "name": match.group(1),
                            "version": match.group(2),
                            "source_file": rel_path,
                            "ecosystem": ecosystem,
                        })
            elif ecosystem == "rust" and fpath.name == "Cargo.toml":
                in_deps = False
                for line in content.splitlines():
                    if "[dependencies]" in line or "[dev-dependencies]" in line:
                        in_deps = True
                        continue
                    if in_deps and line.strip().startswith("["):
                        in_deps = False
                    if in_deps:
                        match = re.match(r'^([A-Za-z0-9_-]+)\s*=\s*"?([^"]+)"?', line)
                        if match:
                            deps.append({
                                "name": match.group(1),
                                "version": match.group(2).strip(),
                                "source_file": rel_path,
                                "ecosystem": ecosystem,
                            })
        return deps


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024  # type: ignore[assignment]
    return f"{size:.1f}GB"
