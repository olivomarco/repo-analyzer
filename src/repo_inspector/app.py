"""Main Textual TUI application for repo-inspector."""

import asyncio
from datetime import datetime, timezone

import httpx
from textual.app import App

from repo_inspector.analyzer import Analyzer
from repo_inspector.models import InspectionResult
from repo_inspector.screens.home import HomeScreen
from repo_inspector.screens.loading import LoadingScreen
from repo_inspector.screens.results import ResultsScreen


class RepoInspectorApp(App):
    """TUI application for GitHub repository inspection."""

    TITLE = "Repo Inspector"
    SUB_TITLE = "People · Functions · Security · Knowledge · Reviews · What-If"

    CSS = """
    Screen {
        background: $background;
    }
    """

    SCREENS = {
        "home": HomeScreen,
    }

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())

    def run_inspection(
        self, owner: str, repo: str, since: datetime
    ) -> None:
        """Kick off the inspection — called from HomeScreen."""
        loading = LoadingScreen()
        self.push_screen(loading)

        async def _do_work() -> None:
            status_counter = {"n": 0}
            total_steps = 18  # approximate (core + extended analyses)

            def on_status(msg: str) -> None:
                status_counter["n"] += 1
                pct = min(int(status_counter["n"] / total_steps * 100), 95)
                self.call_from_thread(loading.update_status, msg, pct)

            analyzer = Analyzer(on_status=on_status)
            try:
                result = await analyzer.inspect(owner, repo, since)
                self.call_from_thread(loading.update_status, "Complete!", 100)
                self.call_from_thread(self._show_results, result)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    self.call_from_thread(
                        loading.update_status,
                        f"❌ Repository '{owner}/{repo}' not found. Check the owner/repo name and try again.",
                        None,
                    )
                elif e.response.status_code == 403:
                    import os
                    resp_text = getattr(e.response, "text", "")
                    has_token = bool(
                        os.environ.get("GITHUB_TOKEN")
                        or os.environ.get("GH_TOKEN")
                    )
                    if "rate limit" in resp_text.lower():
                        if has_token:
                            msg = (
                                "❌ GitHub API rate limit exceeded. "
                                "Wait a few minutes and retry. "
                                "If the error persists, check that your PAT "
                                "is authorized for this org's SAML SSO at: "
                                "github.com/settings/tokens → Configure SSO."
                            )
                        else:
                            msg = (
                                "❌ GitHub API rate limit exceeded "
                                "(unauthenticated: 60 req/hour). "
                                "Set GITHUB_TOKEN to get 5 000 req/hour."
                            )
                    elif "SAML" in resp_text:
                        msg = (
                            "❌ This org requires SAML SSO. "
                            "Go to github.com/settings/tokens → "
                            "click 'Configure SSO' next to your token → "
                            "Authorize it for this organization."
                        )
                    elif has_token:
                        msg = (
                            "❌ Access denied. The repository may be private "
                            "or your token lacks permissions."
                        )
                    else:
                        msg = (
                            "❌ Access denied — no GitHub token found. "
                            "Set GITHUB_TOKEN env var: "
                            "export GITHUB_TOKEN=ghp_… "
                            "(or: export GITHUB_TOKEN=$(gh auth token))"
                        )
                    self.call_from_thread(
                        loading.update_status, msg, None,
                    )
                elif e.response.status_code == 401:
                    self.call_from_thread(
                        loading.update_status,
                        "❌ Authentication failed. Please check your GitHub token.",
                        None,
                    )
                else:
                    self.call_from_thread(
                        loading.update_status,
                        f"❌ GitHub API error ({e.response.status_code}): {e.response.reason_phrase}",
                        None,
                    )
                self.call_from_thread(self._show_error_back_button)
            except httpx.ConnectError:
                self.call_from_thread(
                    loading.update_status,
                    "❌ Could not connect to GitHub. Check your internet connection.",
                    None,
                )
                self.call_from_thread(self._show_error_back_button)
            except Exception as e:
                self.call_from_thread(
                    loading.update_status,
                    f"❌ Unexpected error: {e}",
                    None,
                )
                self.call_from_thread(self._show_error_back_button)
            finally:
                await analyzer.close()

        self.run_worker(_do_work(), thread=True)

    def _show_results(self, result: InspectionResult) -> None:
        """Replace loading screen with results."""
        self.pop_screen()  # Remove loading
        self.push_screen(ResultsScreen(result))

    def _show_error_back_button(self) -> None:
        """Add a back-button hint to the loading screen on error."""
        try:
            loading = self.screen
            if isinstance(loading, LoadingScreen):
                loading.set_phase("Press [b]  b  [/b] to go back and try again.")
        except Exception:
            pass
