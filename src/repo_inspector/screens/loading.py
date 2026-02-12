"""Loading screen — shows progress during analysis."""

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ProgressBar, Static


class LoadingScreen(Screen):
    """Displayed while the inspection is running."""

    BINDINGS = [
        ("b", "go_back", "Back"),
    ]

    CSS = """
    LoadingScreen {
        align: center middle;
    }
    #loading-container {
        width: 72;
        height: auto;
        padding: 2 4;
        border: round $primary;
        background: $surface;
    }
    #loading-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 2;
    }
    #status-label {
        text-align: center;
        margin-bottom: 1;
    }
    #progress-bar {
        margin: 1 0;
    }
    #phase-label {
        text-align: center;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Center():
            with Vertical(id="loading-container"):
                yield Static("🔍  Inspecting Repository …", id="loading-title")
                yield Label("Initializing …", id="status-label")
                yield ProgressBar(total=100, show_eta=False, id="progress-bar")
                yield Label("", id="phase-label")
        yield Footer()

    def update_status(self, message: str, progress: int | None = None) -> None:
        """Update the status message and optionally the progress bar."""
        try:
            self.query_one("#status-label", Label).update(message)
            if progress is not None:
                self.query_one("#progress-bar", ProgressBar).update(progress=progress)
        except Exception:
            pass

    def set_phase(self, phase: str) -> None:
        try:
            self.query_one("#phase-label", Label).update(phase)
        except Exception:
            pass

    def action_go_back(self) -> None:
        """Return to the home screen."""
        self.app.pop_screen()
