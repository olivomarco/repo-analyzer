"""Tests for the CLI entry point."""

from repo_inspector.cli import main


class TestCLI:
    def test_main_importable(self):
        """Test that main function is importable."""
        assert callable(main)
