"""Tests for the CLI entry point."""

from unittest.mock import MagicMock, patch


class TestCli:
    def test_main_loads_env_and_runs(self):
        """Test that main() calls load_dotenv and launches the app."""
        mock_app_instance = MagicMock()
        with patch("dotenv.load_dotenv") as mock_ld:
            with patch("repo_inspector.app.RepoInspectorApp", return_value=mock_app_instance) as mock_cls:
                from repo_inspector.cli import main
                main()
                mock_ld.assert_called_once()
                mock_app_instance.run.assert_called_once()

    def test_main_callable(self):
        from repo_inspector.cli import main
        assert callable(main)
