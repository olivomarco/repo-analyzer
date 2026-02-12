"""Tests for analysis/functional.py — functional area analysis."""

from pathlib import PurePosixPath
from unittest.mock import MagicMock

from repo_inspector.analysis.functional import build_functional_areas, gather_code_samples


class TestBuildFunctionalAreas:
    def test_creates_areas_for_each_dir(self):
        cloner = MagicMock()
        cloner.list_top_level_dirs.return_value = ["src", "docs"]
        cloner.folder_stats.side_effect = [
            {"files": 10, "lines": 500},
            {"files": 3, "lines": 100},
        ]
        cloner.detect_languages.side_effect = [
            ["Python", "JavaScript"],
            ["Markdown"],
        ]
        cloner.list_files_in_dir.side_effect = [
            [PurePosixPath("src/main.py"), PurePosixPath("src/utils.py")],
            [PurePosixPath("docs/guide.md")],
        ]

        areas = build_functional_areas(cloner)

        assert len(areas) == 2
        assert areas[0].name == "src"
        assert areas[0].path == "src"
        assert "10 files" in areas[0].description
        assert "500 lines" in areas[0].description
        assert "Python" in areas[0].description
        assert len(areas[0].key_files) == 2

    def test_empty_repo(self):
        cloner = MagicMock()
        cloner.list_top_level_dirs.return_value = []

        areas = build_functional_areas(cloner)
        assert areas == []

    def test_no_languages_detected(self):
        cloner = MagicMock()
        cloner.list_top_level_dirs.return_value = ["data"]
        cloner.folder_stats.return_value = {"files": 1, "lines": 10}
        cloner.detect_languages.return_value = []
        cloner.list_files_in_dir.return_value = []

        areas = build_functional_areas(cloner)
        assert len(areas) == 1
        assert "unknown" in areas[0].description


class TestGatherCodeSamples:
    def test_gathers_code_files(self):
        cloner = MagicMock()
        cloner.list_files_in_dir.return_value = [
            PurePosixPath("src/main.py"),
            PurePosixPath("src/utils.py"),
        ]
        cloner.read_file.side_effect = [
            "def main():\n    pass",
            "def helper():\n    return 42",
        ]

        result = gather_code_samples(cloner, "src")

        assert "main.py" in result
        assert "utils.py" in result
        assert "def main" in result

    def test_skips_empty_files(self):
        cloner = MagicMock()
        cloner.list_files_in_dir.return_value = [
            PurePosixPath("src/empty.py"),
            PurePosixPath("src/real.py"),
        ]
        cloner.read_file.side_effect = ["", "print('hello')"]

        result = gather_code_samples(cloner, "src")

        assert "empty.py" not in result
        assert "real.py" in result

    def test_limits_files(self):
        cloner = MagicMock()
        cloner.list_files_in_dir.return_value = [
            PurePosixPath(f"src/file{i}.py") for i in range(20)
        ]
        cloner.read_file.return_value = "x = 1"

        result = gather_code_samples(cloner, "src", max_files=3)

        # Should only read 3 files
        assert cloner.read_file.call_count == 3

    def test_no_files(self):
        cloner = MagicMock()
        cloner.list_files_in_dir.return_value = []

        result = gather_code_samples(cloner, "src")
        assert result == ""
