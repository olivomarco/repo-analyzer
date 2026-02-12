"""Tests for analysis/code.py — folder-level code analysis."""

from unittest.mock import MagicMock

from repo_inspector.analysis.code import build_folder_analyses


class TestBuildFolderAnalyses:
    def test_creates_analyses_for_each_dir(self):
        cloner = MagicMock()
        cloner.list_top_level_dirs.return_value = ["src", "tests", "docs"]
        cloner.folder_stats.side_effect = [
            {"files": 10, "lines": 500},
            {"files": 5, "lines": 200},
            {"files": 2, "lines": 50},
        ]
        cloner.detect_languages.side_effect = [
            ["Python"],
            ["Python"],
            ["Markdown"],
        ]

        analyses = build_folder_analyses(cloner)

        assert len(analyses) == 3
        assert analyses[0].path == "src"
        assert analyses[0].file_count == 10
        assert analyses[0].total_lines == 500
        assert analyses[0].languages == ["Python"]

    def test_empty_repo(self):
        cloner = MagicMock()
        cloner.list_top_level_dirs.return_value = []

        analyses = build_folder_analyses(cloner)
        assert analyses == []

    def test_single_dir(self):
        cloner = MagicMock()
        cloner.list_top_level_dirs.return_value = ["lib"]
        cloner.folder_stats.return_value = {"files": 3, "lines": 100}
        cloner.detect_languages.return_value = ["Go", "Shell"]

        analyses = build_folder_analyses(cloner)
        assert len(analyses) == 1
        assert analyses[0].languages == ["Go", "Shell"]
