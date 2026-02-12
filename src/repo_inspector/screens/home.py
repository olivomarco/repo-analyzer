"""Home screen — repo input and timeframe selection."""

from datetime import datetime, timedelta, timezone

from textual import on
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static


class HomeScreen(Screen):
    """Initial screen to collect repo and timeframe."""

    CSS = """
    HomeScreen {
        align: center middle;
    }
    #home-container {
        width: 72;
        height: auto;
        padding: 1 4;
        border: round $primary;
        background: $surface;
    }
    #title-art {
        text-align: center;
        color: $accent;
        margin-bottom: 0;
    }
    #subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }
    .field-label {
        margin-top: 1;
        color: $text;
    }
    #repo-input {
        margin-bottom: 1;
    }
    #start-btn {
        margin-top: 2;
        width: 100%;
    }
    #error-label {
        color: $error;
        text-align: center;
        margin-top: 1;
    }
    """

    TITLE_ART = """

  ╭──────────────────────────────────────────────────────╮
  │                                                      │
  │   ┏━┓┏━╸┏━┓┏━┓   ╻┏┓╻┏━┓┏━┓┏━╸┏━╸╺┳╸┏━┓┏━┓        │
  │   ┣┳┛┣╸ ┣━┛┃ ┃   ┃┃┗┫┗━┓┣━┛┣╸ ┃   ┃ ┃ ┃┣┳┛        │
  │   ╹┗╸┗━╸╹  ┗━┛   ╹╹ ╹┗━┛╹  ┗━╸┗━╸ ╹ ┗━┛╹┗╸        │
  │                                                      │
  │        Analyze any GitHub repo with AI               │
  ╰──────────────────────────────────────────────────────╯
"""

    TIMEFRAME_OPTIONS = [
        ("Last 1 week", 7),
        ("Last 2 weeks", 14),
        ("Last 1 month", 30),
        ("Last 3 months", 90),
        ("Last 6 months", 180),
        ("Last 1 year", 365),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Center():
            with Vertical(id="home-container"):
                yield Static(self.TITLE_ART, id="title-art")
                yield Static(
                    "People · Functions · Security",
                    id="subtitle",
                )
                yield Label("Repository (owner/repo):", classes="field-label")
                yield Input(
                    placeholder="e.g. excalidraw/excalidraw",
                    id="repo-input",
                )
                yield Label("Timeframe:", classes="field-label")
                yield Select(
                    [(label, days) for label, days in self.TIMEFRAME_OPTIONS],
                    value=30,
                    id="timeframe-select",
                )
                yield Button("▶  Start Inspection", id="start-btn", variant="primary")
                yield Label("", id="error-label")
        yield Footer()

    def on_mount(self) -> None:
        """Focus the repo input on screen mount so paste works immediately."""
        self.query_one("#repo-input", Input).focus()

    @on(Button.Pressed, "#start-btn")
    def start_inspection(self) -> None:
        repo_input = self.query_one("#repo-input", Input)
        timeframe_select = self.query_one("#timeframe-select", Select)
        error_label = self.query_one("#error-label", Label)

        repo = repo_input.value.strip()
        if "/" not in repo or len(repo.split("/")) != 2:
            error_label.update("⚠  Enter a valid owner/repo (e.g. excalidraw/excalidraw)")
            return

        owner, repo_name = repo.split("/", 1)
        if not owner or not repo_name:
            error_label.update("⚠  Both owner and repo name are required")
            return

        days = timeframe_select.value
        if days is Select.BLANK:
            days = 30

        since = datetime.now(timezone.utc) - timedelta(days=int(days))

        self.app.run_inspection(owner, repo_name, since)  # type: ignore[attr-defined]

    @on(Input.Submitted, "#repo-input")
    def submit_on_enter(self) -> None:
        self.start_inspection()
