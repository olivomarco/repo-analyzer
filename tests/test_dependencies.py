"""Tests for analysis/dependencies.py — dependency risk scanning."""

from unittest.mock import MagicMock

from repo_inspector.analysis.dependencies import build_dependency_report


class TestBuildDependencyReport:
    def test_basic_report(self):
        cloner = MagicMock()
        cloner.parse_dependencies.return_value = [
            {"name": "flask", "version": ">=2.0", "source_file": "requirements.txt", "ecosystem": "python"},
            {"name": "requests", "version": "==2.28", "source_file": "requirements.txt", "ecosystem": "python"},
        ]

        report = build_dependency_report(cloner)

        assert report.total_deps == 2
        assert len(report.dependencies) == 2
        assert "python" in report.ecosystems
        assert report.dependencies[0].name == "flask"
        assert report.dependencies[0].ecosystem == "python"

    def test_multiple_ecosystems(self):
        cloner = MagicMock()
        cloner.parse_dependencies.return_value = [
            {"name": "flask", "version": ">=2.0", "source_file": "requirements.txt", "ecosystem": "python"},
            {"name": "express", "version": "^4.18", "source_file": "package.json", "ecosystem": "npm"},
            {"name": "serde", "version": "1.0", "source_file": "Cargo.toml", "ecosystem": "rust"},
        ]

        report = build_dependency_report(cloner)

        assert report.total_deps == 3
        assert sorted(report.ecosystems) == ["npm", "python", "rust"]

    def test_empty_dependencies(self):
        cloner = MagicMock()
        cloner.parse_dependencies.return_value = []

        report = build_dependency_report(cloner)

        assert report.total_deps == 0
        assert report.dependencies == []
        assert report.ecosystems == []

    def test_missing_optional_fields(self):
        cloner = MagicMock()
        cloner.parse_dependencies.return_value = [
            {"name": "pkg", "ecosystem": "python"},
        ]

        report = build_dependency_report(cloner)

        assert report.total_deps == 1
        assert report.dependencies[0].version == ""
        assert report.dependencies[0].source_file == ""
