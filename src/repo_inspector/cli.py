"""CLI entry point for repo-inspector."""


def main() -> None:
    """Launch the Repo Inspector TUI."""
    from dotenv import load_dotenv

    load_dotenv()  # Load .env file (e.g. GITHUB_TOKEN)

    from repo_inspector.app import RepoInspectorApp

    app = RepoInspectorApp()
    app.run()


if __name__ == "__main__":
    main()
