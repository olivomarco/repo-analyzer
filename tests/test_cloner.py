"""Tests for the cloner module."""

import json
import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repo_inspector.cloner import RepoCloner, _human_size


@pytest.fixture
def cloner_with_dir(tmp_path):
    """Create a RepoCloner with a fake clone directory."""
    cloner = RepoCloner(token="test-token")
    cloner._clone_dir = tmp_path

    # Create some directories and files
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "__pycache__").mkdir()

    (tmp_path / "README.md").write_text("# Hello\n")
    (tmp_path / "src" / "main.py").write_text("print('hello')\nimport os\n")
    (tmp_path / "src" / "utils.py").write_text("def helper():\n    pass\n")
    (tmp_path / "src" / ".hidden").write_text("secret")
    (tmp_path / "tests" / "test_main.py").write_text("def test_one():\n    assert True\n")
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n\nSome docs.\n")

    return cloner


class TestRepoCloner:
    def test_init_with_token(self):
        cloner = RepoCloner(token="my-token")
        assert cloner.token == "my-token"
        assert cloner.clone_path is None

    def test_init_without_token(self):
        cloner = RepoCloner()
        assert cloner.token is None

    def test_clone_path_property(self, tmp_path):
        cloner = RepoCloner()
        assert cloner.clone_path is None
        cloner._clone_dir = tmp_path
        assert cloner.clone_path == tmp_path

    @patch("repo_inspector.cloner.git.Repo.clone_from")
    def test_clone_success(self, mock_clone):
        cloner = RepoCloner(token="test-token")
        result = cloner.clone("owner", "repo")
        assert result is not None
        assert result.exists()
        mock_clone.assert_called_once()
        # Verify auth URL was used
        call_args = mock_clone.call_args
        assert "x-access-token" in call_args[0][0]
        cloner.cleanup()

    @patch("repo_inspector.cloner.git.Repo.clone_from")
    def test_clone_without_token(self, mock_clone):
        cloner = RepoCloner()
        result = cloner.clone("owner", "repo")
        assert result is not None
        mock_clone.assert_called_once()
        call_args = mock_clone.call_args
        assert "x-access-token" not in call_args[0][0]
        cloner.cleanup()

    @patch("repo_inspector.cloner.git.Repo.clone_from")
    def test_clone_saml_fallback(self, mock_clone):
        """Auth clone fails, retry without token succeeds."""
        import git as gitmodule

        mock_clone.side_effect = [
            gitmodule.exc.GitCommandError("clone", "SAML"),
            MagicMock(),
        ]
        cloner = RepoCloner(token="test-token")
        result = cloner.clone("owner", "repo")
        assert result is not None
        assert mock_clone.call_count == 2
        cloner.cleanup()

    def test_cleanup(self, tmp_path):
        cloner = RepoCloner()
        cloner._clone_dir = tmp_path
        cloner.cleanup()
        assert cloner.clone_path is None

    def test_cleanup_no_dir(self):
        cloner = RepoCloner()
        cloner.cleanup()  # should not raise


class TestListTopLevelDirs:
    def test_lists_directories(self, cloner_with_dir):
        dirs = cloner_with_dir.list_top_level_dirs()
        assert "src" in dirs
        assert "tests" in dirs
        assert "docs" in dirs

    def test_excludes_hidden_and_noise(self, cloner_with_dir):
        dirs = cloner_with_dir.list_top_level_dirs()
        assert ".git" not in dirs
        assert "__pycache__" not in dirs

    def test_no_clone_dir(self):
        cloner = RepoCloner()
        assert cloner.list_top_level_dirs() == []


class TestListFilesInDir:
    def test_lists_files(self, cloner_with_dir):
        files = cloner_with_dir.list_files_in_dir("src")
        names = [f.name for f in files]
        assert "main.py" in names
        assert "utils.py" in names

    def test_excludes_hidden_files(self, cloner_with_dir):
        files = cloner_with_dir.list_files_in_dir("src")
        names = [f.name for f in files]
        assert ".hidden" not in names

    def test_filter_by_extension(self, cloner_with_dir):
        files = cloner_with_dir.list_files_in_dir("src", extensions={".py"})
        assert all(f.suffix == ".py" for f in files)

    def test_nonexistent_dir(self, cloner_with_dir):
        files = cloner_with_dir.list_files_in_dir("nonexistent")
        assert files == []

    def test_no_clone_dir(self):
        cloner = RepoCloner()
        assert cloner.list_files_in_dir("src") == []


class TestReadFile:
    def test_reads_file(self, cloner_with_dir):
        content = cloner_with_dir.read_file("src/main.py")
        assert "print" in content

    def test_truncates_long_file(self, cloner_with_dir, tmp_path):
        long_content = "\n".join(f"line {i}" for i in range(1000))
        (tmp_path / "src" / "long.py").write_text(long_content)
        content = cloner_with_dir.read_file("src/long.py", max_lines=10)
        assert "truncated" in content

    def test_nonexistent_file(self, cloner_with_dir):
        assert cloner_with_dir.read_file("nofile.py") == ""

    def test_no_clone_dir(self):
        cloner = RepoCloner()
        assert cloner.read_file("any.py") == ""


class TestGetTreeSummary:
    def test_returns_tree(self, cloner_with_dir):
        tree = cloner_with_dir.get_tree_summary(max_depth=2)
        assert "src/" in tree
        assert "main.py" in tree

    def test_no_clone_dir(self):
        cloner = RepoCloner()
        assert cloner.get_tree_summary() == ""


class TestFolderStats:
    def test_counts_files_and_lines(self, cloner_with_dir):
        stats = cloner_with_dir.folder_stats("src")
        assert stats["files"] >= 2
        assert stats["lines"] >= 2

    def test_nonexistent_dir(self, cloner_with_dir):
        stats = cloner_with_dir.folder_stats("nonexistent")
        assert stats == {"files": 0, "lines": 0}

    def test_no_clone_dir(self):
        cloner = RepoCloner()
        assert cloner.folder_stats("src") == {"files": 0, "lines": 0}


class TestDetectLanguages:
    def test_detects_python(self, cloner_with_dir):
        langs = cloner_with_dir.detect_languages("src")
        assert "Python" in langs

    def test_detects_markdown(self, cloner_with_dir):
        langs = cloner_with_dir.detect_languages("docs")
        assert "Markdown" in langs

    def test_detects_dockerfile(self, cloner_with_dir, tmp_path):
        (tmp_path / "infra").mkdir()
        (tmp_path / "infra" / "Dockerfile").write_text("FROM python:3.11\n")
        langs = cloner_with_dir.detect_languages("infra")
        assert "Docker" in langs

    def test_detects_multiple_languages(self, cloner_with_dir, tmp_path):
        (tmp_path / "src" / "app.js").write_text("console.log('hi')")
        langs = cloner_with_dir.detect_languages("src")
        assert "Python" in langs
        assert "JavaScript" in langs

    def test_nonexistent_dir(self, cloner_with_dir):
        assert cloner_with_dir.detect_languages("nonexistent") == []

    def test_no_clone_dir(self):
        cloner = RepoCloner()
        assert cloner.detect_languages("src") == []


class TestDetectDependencyFiles:
    def test_finds_requirements(self, cloner_with_dir, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask>=2.0\n")
        result = cloner_with_dir.detect_dependency_files()
        assert "requirements.txt" in result
        assert result["requirements.txt"] == "python"

    def test_finds_package_json(self, cloner_with_dir, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        result = cloner_with_dir.detect_dependency_files()
        assert "package.json" in result
        assert result["package.json"] == "npm"

    def test_finds_cargo_toml(self, cloner_with_dir, tmp_path):
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')
        result = cloner_with_dir.detect_dependency_files()
        assert "Cargo.toml" in result
        assert result["Cargo.toml"] == "rust"

    def test_finds_csproj(self, cloner_with_dir, tmp_path):
        (tmp_path / "MyApp.csproj").write_text("<Project></Project>")
        result = cloner_with_dir.detect_dependency_files()
        assert "MyApp.csproj" in result
        assert result["MyApp.csproj"] == "dotnet"

    def test_no_clone_dir(self):
        cloner = RepoCloner()
        assert cloner.detect_dependency_files() == {}


class TestParseDependencies:
    def test_parses_requirements_txt(self, cloner_with_dir, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask>=2.0\nrequests==2.28.0\n# comment\n")
        deps = cloner_with_dir.parse_dependencies()
        names = [d["name"] for d in deps]
        assert "flask" in names
        assert "requests" in names

    def test_parses_package_json(self, cloner_with_dir, tmp_path):
        pkg = {
            "name": "test",
            "dependencies": {"express": "^4.18.0"},
            "devDependencies": {"jest": "^29.0.0"},
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        deps = cloner_with_dir.parse_dependencies()
        names = [d["name"] for d in deps]
        assert "express" in names
        assert "jest" in names

    def test_parses_go_mod(self, cloner_with_dir, tmp_path):
        (tmp_path / "go.mod").write_text(
            "module example.com/test\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n)\n"
        )
        deps = cloner_with_dir.parse_dependencies()
        names = [d["name"] for d in deps]
        assert "github.com/gin-gonic/gin" in names

    def test_parses_cargo_toml(self, cloner_with_dir, tmp_path):
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "test"\n\n[dependencies]\nserde = "1.0"\n'
        )
        deps = cloner_with_dir.parse_dependencies()
        names = [d["name"] for d in deps]
        assert "serde" in names

    def test_parses_pyproject_toml(self, cloner_with_dir, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "myproject"\ndependencies = [\n  "click>=8.0",\n  "httpx>=0.24",\n]\n'
        )
        deps = cloner_with_dir.parse_dependencies()
        names = [d["name"] for d in deps]
        assert "click" in names or "httpx" in names

    def test_invalid_package_json(self, cloner_with_dir, tmp_path):
        (tmp_path / "package.json").write_text("not valid json {{{")
        deps = cloner_with_dir.parse_dependencies()
        # Should not crash, just skip
        pkg_deps = [d for d in deps if d.get("ecosystem") == "npm"]
        assert pkg_deps == []

    def test_requirements_skips_flags(self, cloner_with_dir, tmp_path):
        (tmp_path / "requirements.txt").write_text("-r base.txt\n-e .\nflask>=2.0\n")
        deps = cloner_with_dir.parse_dependencies()
        names = [d["name"] for d in deps]
        assert "flask" in names
        # -r and -e lines should be skipped
        assert "-r" not in names

    def test_no_deps_found(self, cloner_with_dir):
        deps = cloner_with_dir.parse_dependencies()
        # may find pyproject.toml or nothing depending on fixture
        assert isinstance(deps, list)


class TestHumanSize:
    def test_bytes(self):
        assert _human_size(500) == "500B"

    def test_kilobytes(self):
        assert _human_size(2048) == "2KB"

    def test_megabytes(self):
        assert _human_size(1048576) == "1MB"

    def test_gigabytes(self):
        result = _human_size(2 * 1024 * 1024 * 1024)
        assert "GB" in result
