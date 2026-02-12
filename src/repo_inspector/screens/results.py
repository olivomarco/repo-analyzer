"""Results screen — tabbed view with People / Functional / Code tabs + extended analysis."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
)

from repo_inspector.models import CodeFinding, InspectionResult


class ResultsScreen(Screen):
    """Main results display with three analysis tabs."""

    CSS = """
    ResultsScreen {
        layout: vertical;
    }
    #results-header {
        height: 3;
        background: $primary;
        color: $text;
        text-align: center;
        padding: 1 2;
        text-style: bold;
    }
    .section-title {
        text-style: bold;
        margin: 1 0;
        color: $secondary;
    }
    .metric-row {
        height: 3;
        margin: 0 1;
    }
    .metric-value {
        text-style: bold;
        color: $accent;
    }
    #people-table {
        height: auto;
        max-height: 20;
        margin: 1 0;
    }
    .insight-card {
        border: round $primary-lighten-2;
        padding: 1 2;
        margin: 1 0;
        background: $surface;
        height: auto;
    }
    .finding-card {
        border: round $warning;
        padding: 1 2;
        margin: 1 0;
        background: $surface;
        height: auto;
    }
    .finding-card.security {
        border: round $error;
    }
    #issue-btn-row {
        height: 4;
        margin: 1 0;
        align: center middle;
    }
    #back-btn {
        dock: bottom;
        margin: 1 2;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("b", "go_back", "Back"),
        ("i", "create_issue", "Create Issue"),
    ]

    def __init__(self, result: InspectionResult, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self.result = result
        self._selected_findings: list[CodeFinding] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            f"  📊  {self.result.repo}  ·  {self.result.timeframe.label}  ",
            id="results-header",
        )

        with TabbedContent(
            "👥 People", "🏗 Functional", "🔒 Code & Security",
            "⏰ Time Machine", "🗺 Knowledge Map", "📦 Dependencies",
            "👀 Reviews", "🪦 Stale Branches", "📝 Changelog",
            "🚌 Bus Factor", "🔮 What-If",
        ):
            with TabPane("👥 People"):
                yield from self._compose_people()
            with TabPane("🏗 Functional"):
                yield from self._compose_functional()
            with TabPane("🔒 Code & Security"):
                yield from self._compose_code()
            with TabPane("⏰ Time Machine"):
                yield from self._compose_time_machine()
            with TabPane("🗺 Knowledge Map"):
                yield from self._compose_knowledge_map()
            with TabPane("📦 Dependencies"):
                yield from self._compose_dependencies()
            with TabPane("👀 Reviews"):
                yield from self._compose_reviews()
            with TabPane("🪦 Stale Branches"):
                yield from self._compose_stale_branches()
            with TabPane("📝 Changelog"):
                yield from self._compose_changelog()
            with TabPane("🚌 Bus Factor"):
                yield from self._compose_bus_factor()
            with TabPane("🔮 What-If"):
                yield from self._compose_what_if()

        yield Footer()

    # ── People tab ────────────────────────────────────────────────────────

    def _compose_people(self) -> ComposeResult:
        p = self.result.people
        with VerticalScroll():
            yield Static("CONTRIBUTOR OVERVIEW", classes="section-title")
            yield Label(
                f"Contributors: {p.total_contributors}  ·  "
                f"Bus Factor: {p.bus_factor}  ·  "
                f"Commits: {sum(s.commit_count for s in p.stats)}"
            )

            if p.llm_summary:
                yield Markdown(f"> {p.llm_summary}")

            yield Static("TOP CONTRIBUTORS", classes="section-title")
            table = DataTable(id="people-table")
            table.add_columns(
                "Contributor", "Commits", "+Lines", "-Lines",
                "PRs (merged)", "Top Dirs",
            )
            for s in p.stats[:15]:
                table.add_row(
                    f"@{s.login}",
                    str(s.commit_count),
                    f"+{s.lines_added}",
                    f"-{s.lines_removed}",
                    f"{s.prs_opened} ({s.prs_merged})",
                    ", ".join(s.top_directories[:3]),
                )
            yield table

            if p.insights:
                yield Static("LLM INSIGHTS", classes="section-title")
                for ins in p.insights:
                    if ins.login == "(parse error)":
                        yield Label(f"⚠ {ins.activity_summary}")
                        continue
                    md = (
                        f"**@{ins.login}** — _{ins.inferred_role}_\n\n"
                        f"{ins.activity_summary}\n\n"
                        f"**Assessment:** {ins.judgment}"
                    )
                    if ins.risk_notes:
                        md += f"\n\n⚠️ **Risk:** {ins.risk_notes}"
                    with Vertical(classes="insight-card"):
                        yield Markdown(md)

    # ── Functional tab ────────────────────────────────────────────────────

    def _compose_functional(self) -> ComposeResult:
        f = self.result.functional
        has_content = (
            f.repo_description or f.tech_stack or f.architecture_notes
            or f.areas or f.llm_summary
        )
        with VerticalScroll():
            if not has_content:
                yield Static("FUNCTIONAL ANALYSIS", classes="section-title")
                yield Markdown(
                    "> **No functional analysis data available.**\n\n"
                    "This may happen when the repository had no commits in the "
                    "selected timeframe, or the repository structure could not "
                    "be analyzed. Try selecting a longer timeframe."
                )
                return

            yield Static("REPOSITORY OVERVIEW", classes="section-title")
            if f.repo_description:
                yield Markdown(f.repo_description)
            if f.tech_stack:
                yield Label(f"Tech Stack: {', '.join(f.tech_stack)}")
            if f.architecture_notes:
                yield Static("ARCHITECTURE", classes="section-title")
                yield Markdown(f.architecture_notes)

            if f.areas:
                yield Static("FUNCTIONAL AREAS", classes="section-title")
                for area in f.areas:
                    content = f"### {area.name}/\n\n{area.description}"
                    if area.key_files:
                        content += "\n\n**Key files:** " + ", ".join(
                            f"`{kf}`" for kf in area.key_files[:8]
                        )
                    if area.improvement_notes:
                        content += f"\n\n💡 **Improvements:** {area.improvement_notes}"
                    with Vertical(classes="insight-card"):
                        yield Markdown(content)

            if f.llm_summary:
                yield Static("SUMMARY", classes="section-title")
                yield Markdown(f"> {f.llm_summary}")

    # ── Code & Security tab ───────────────────────────────────────────────

    def _compose_code(self) -> ComposeResult:
        c = self.result.code
        has_content = c.folders or c.llm_summary or c.total_findings > 0
        with VerticalScroll():
            if not has_content:
                yield Static("CODE & SECURITY ANALYSIS", classes="section-title")
                yield Markdown(
                    "> **No code analysis data available.**\n\n"
                    "This may happen when the repository had no commits in the "
                    "selected timeframe, or no analyzable code files were found. "
                    "Try selecting a longer timeframe."
                )
                return

            yield Static("CODE ANALYSIS OVERVIEW", classes="section-title")
            yield Label(
                f"Total Findings: {c.total_findings}  ·  "
                f"Security: {c.security_findings}  ·  "
                f"Refactoring: {c.refactoring_findings}"
            )
            if c.llm_summary:
                yield Markdown(f"> {c.llm_summary}")

            has_folder_content = False
            for fa in c.folders:
                if not fa.findings and not fa.llm_notes:
                    continue
                has_folder_content = True
                yield Static(
                    f"📁  {fa.path}/  ({fa.file_count} files, {fa.total_lines} lines)",
                    classes="section-title",
                )
                if fa.llm_notes:
                    yield Label(fa.llm_notes)

                for finding in fa.findings:
                    css_class = "finding-card security" if finding.category == "security" else "finding-card"
                    md = (
                        f"{finding.display_severity}  **{finding.title}**\n\n"
                        f"Category: `{finding.category}`"
                    )
                    if finding.file:
                        md += f" · File: `{finding.file}`"
                    md += f"\n\n{finding.description}"
                    if finding.suggestion:
                        md += f"\n\n✅ **Fix:** {finding.suggestion}"
                    with Vertical(classes=css_class):
                        yield Markdown(md)

            if not has_folder_content:
                yield Markdown(
                    "\n\n_No specific folder-level findings were identified._"
                )

            with Horizontal(id="issue-btn-row"):
                yield Button(
                    "📝  Create Issue from Findings",
                    id="create-issue-btn",
                    variant="warning",
                )

    # ── Time Machine tab ──────────────────────────────────────────────────

    def _compose_time_machine(self) -> ComposeResult:
        ext = self.result.extended
        tm = ext.time_machine if ext else None
        with VerticalScroll():
            yield Static("TIME MACHINE — HISTORICAL COMPARISON", classes="section-title")
            if not tm:
                yield Markdown("> _No time machine data available._")
                return

            yield Label(
                f"Comparing: {tm.old_timeframe.label}  vs  {tm.new_timeframe.label}"
            )

            if tm.llm_summary:
                yield Markdown(f"> {tm.llm_summary}")

            yield Static("METRIC DELTAS", classes="section-title")
            table = DataTable()
            table.add_columns("Metric", "Previous", "Current", "Change")
            for d in tm.deltas:
                table.add_row(
                    d.metric,
                    str(d.old_value),
                    str(d.new_value),
                    d.change,
                )
            yield table

            if tm.contributor_churn:
                yield Static("CONTRIBUTORS JOINED", classes="section-title")
                yield Label("  ".join(f"@{c}" for c in tm.contributor_churn))

            if tm.contributor_departed:
                yield Static("CONTRIBUTORS DEPARTED", classes="section-title")
                yield Label("  ".join(f"@{c}" for c in tm.contributor_departed))

    # ── Knowledge Map tab ─────────────────────────────────────────────────

    def _compose_knowledge_map(self) -> ComposeResult:
        ext = self.result.extended
        km = ext.knowledge_map if ext else None
        with VerticalScroll():
            yield Static("KNOWLEDGE MAP — WHO KNOWS WHAT", classes="section-title")
            if not km or not km.contributors:
                yield Markdown("> _No knowledge map data available._")
                return

            if km.llm_summary:
                yield Markdown(f"> {km.llm_summary}")

            # Build heatmap table
            yield Static("CONTRIBUTOR × FOLDER HEATMAP", classes="section-title")
            table = DataTable()
            table.add_column("Contributor", width=16)
            for folder in km.folders[:10]:
                table.add_column(folder, width=max(len(folder), 8))
            for login in km.contributors[:15]:
                row_values = [f"@{login}"]
                for folder in km.folders[:10]:
                    cell = next(
                        (c for c in km.cells if c.login == login and c.folder == folder),
                        None
                    )
                    if cell and cell.commits > 0:
                        # Visual bar using block chars
                        bar_len = max(1, int(cell.score * 5))
                        bar = "█" * bar_len + "░" * (5 - bar_len)
                        row_values.append(f"{bar} {cell.commits}")
                    else:
                        row_values.append("░░░░░ 0")
                table.add_row(*row_values)
            yield table

            if km.knowledge_silos:
                yield Static("⚠️  KNOWLEDGE SILOS", classes="section-title")
                for silo in km.knowledge_silos:
                    yield Label(f"  🔴 {silo}")

            if km.pairing_suggestions:
                yield Static("💡 PAIRING SUGGESTIONS", classes="section-title")
                for suggestion in km.pairing_suggestions:
                    yield Label(f"  • {suggestion}")

    # ── Dependencies tab ──────────────────────────────────────────────────

    def _compose_dependencies(self) -> ComposeResult:
        ext = self.result.extended
        dep = ext.dependencies if ext else None
        with VerticalScroll():
            yield Static("DEPENDENCY RISK SCANNER", classes="section-title")
            if not dep or not dep.dependencies:
                yield Markdown("> _No dependencies detected._")
                return

            yield Label(
                f"Total Dependencies: {dep.total_deps}  ·  "
                f"Ecosystems: {', '.join(dep.ecosystems)}"
            )

            if dep.llm_summary:
                yield Markdown(f"> {dep.llm_summary}")

            yield Static("DEPENDENCY LIST", classes="section-title")
            table = DataTable()
            table.add_columns(
                "Package", "Version", "Ecosystem", "Source", "Risk"
            )
            for d in dep.dependencies[:50]:
                risk_icon = "⚠️" if d.risk_notes else "✅"
                table.add_row(
                    d.name,
                    d.version or "—",
                    d.ecosystem,
                    d.source_file,
                    f"{risk_icon} {d.risk_notes}" if d.risk_notes else risk_icon,
                )
            yield table

    # ── Reviews tab ───────────────────────────────────────────────────────

    def _compose_reviews(self) -> ComposeResult:
        ext = self.result.extended
        rc = ext.review_culture if ext else None
        with VerticalScroll():
            yield Static("REVIEW CULTURE ANALYZER", classes="section-title")
            if not rc or not rc.reviewers:
                yield Markdown("> _No review data available._")
                return

            yield Label(
                f"PRs Reviewed: {rc.total_prs_reviewed}  ·  "
                f"Avg Time to First Review: {rc.avg_time_to_first_review_hours}h"
            )

            if rc.llm_summary:
                yield Markdown(f"> {rc.llm_summary}")

            yield Static("REVIEWER BREAKDOWN", classes="section-title")
            table = DataTable()
            table.add_columns(
                "Reviewer", "Reviews", "Avg Time (h)",
                "Approvals", "Rejections", "Authors Reviewed"
            )
            for r in rc.reviewers[:15]:
                bottleneck = " 🔴" if r.login in rc.bottleneck_reviewers else ""
                table.add_row(
                    f"@{r.login}{bottleneck}",
                    str(r.reviews_given),
                    f"{r.avg_review_time_hours:.1f}",
                    str(r.approvals),
                    str(r.rejections),
                    ", ".join(f"@{a}" for a in r.reviewed_authors[:3]),
                )
            yield table

            if rc.bottleneck_reviewers:
                yield Static("⚠️  BOTTLENECK REVIEWERS", classes="section-title")
                yield Label(
                    "  ".join(f"🔴 @{r}" for r in rc.bottleneck_reviewers)
                )

            if rc.review_pairs:
                yield Static("FREQUENT REVIEW PAIRS", classes="section-title")
                for pair in rc.review_pairs:
                    yield Label(f"  🔗 {pair}")

    # ── Stale Branches tab ────────────────────────────────────────────────

    def _compose_stale_branches(self) -> ComposeResult:
        ext = self.result.extended
        sb = ext.stale_branches if ext else None
        with VerticalScroll():
            yield Static("STALE BRANCH CEMETERY 🪦", classes="section-title")
            if not sb or not sb.stale_branches:
                yield Markdown("> _No stale branches found. Branch hygiene looks good!_ 🎉")
                return

            yield Label(
                f"Total Branches: {sb.total_branches}  ·  "
                f"Stale: {len(sb.stale_branches)}  ·  "
                f"Cleanup Candidates: {sb.cleanup_candidates}"
            )

            if sb.llm_summary:
                yield Markdown(f"> {sb.llm_summary}")

            yield Static("STALE BRANCHES", classes="section-title")
            table = DataTable()
            table.add_columns(
                "Branch", "Days Stale", "Author", "Category", "Ahead/Behind"
            )
            category_icons = {
                "orphan": "👻", "wip": "🚧", "stale-feature": "🏚",
                "stale-fix": "🩹", "abandoned": "💀",
            }
            for b in sb.stale_branches[:30]:
                icon = category_icons.get(b.category, "❓")
                table.add_row(
                    b.name,
                    str(b.days_stale),
                    b.author or "—",
                    f"{icon} {b.category}",
                    b.ahead_behind,
                )
            yield table

    # ── Changelog tab ─────────────────────────────────────────────────────

    def _compose_changelog(self) -> ComposeResult:
        ext = self.result.extended
        cl = ext.changelog if ext else None
        with VerticalScroll():
            yield Static("COMMIT JOURNAL — AUTO-GENERATED CHANGELOG", classes="section-title")
            if not cl or not cl.entries:
                yield Markdown("> _No changelog entries generated._")
                return

            yield Label(f"Total Entries: {len(cl.entries)}")

            if cl.llm_summary:
                yield Markdown(f"> {cl.llm_summary}")

            if cl.markdown:
                yield Markdown(cl.markdown)

    # ── Bus Factor Mitigation tab ─────────────────────────────────────────

    def _compose_bus_factor(self) -> ComposeResult:
        ext = self.result.extended
        bm = ext.bus_mitigation if ext else None
        with VerticalScroll():
            yield Static("BUS FACTOR MITIGATION PLAN", classes="section-title")
            if not bm:
                yield Markdown("> _No bus factor data available._")
                return

            risk_icons = {
                "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"
            }
            icon = risk_icons.get(bm.risk_level, "⚪")
            yield Label(
                f"Bus Factor: {bm.bus_factor}  ·  "
                f"Risk Level: {icon} {bm.risk_level.upper()}"
            )

            if bm.llm_summary:
                yield Markdown(f"> {bm.llm_summary}")

            if bm.knowledge_monopolists:
                yield Static("KNOWLEDGE MONOPOLISTS", classes="section-title")
                yield Label(
                    "  ".join(f"👤 @{m}" for m in bm.knowledge_monopolists)
                )

            if bm.exclusive_files:
                yield Static("EXCLUSIVE FILE OWNERSHIP", classes="section-title")
                for login, files in list(bm.exclusive_files.items())[:5]:
                    content = f"**@{login}** — {len(files)} exclusive file(s)\n\n"
                    for f in files[:10]:
                        content += f"- `{f}`\n"
                    if len(files) > 10:
                        content += f"\n... and {len(files) - 10} more"
                    with Vertical(classes="insight-card"):
                        yield Markdown(content)

            if bm.actions:
                yield Static("RECOMMENDED ACTIONS", classes="section-title")
                for action in bm.actions:
                    md = (
                        f"**Priority {action.priority}:** {action.action}\n\n"
                        f"Target: @{action.target_contributor} · `{action.target_area}`\n\n"
                        f"_{action.rationale}_"
                    )
                    with Vertical(classes="insight-card"):
                        yield Markdown(md)

    # ── What-If Simulator tab ─────────────────────────────────────────────

    def _compose_what_if(self) -> ComposeResult:
        ext = self.result.extended
        wi = ext.what_if if ext else None
        with VerticalScroll():
            yield Static("WHAT-IF SIMULATOR 🔮", classes="section-title")
            if not wi or not wi.scenarios:
                yield Markdown("> _No what-if simulations available._")
                return

            if wi.llm_summary:
                yield Markdown(f"> {wi.llm_summary}")

            for s in wi.scenarios:
                if s.scenario == "remove_contributor":
                    title = f"🚪 What if @{s.parameter} leaves?"
                    bus_text = f"Bus Factor: {s.bus_factor_before} → {s.bus_factor_after}"
                    delta = s.bus_factor_after - s.bus_factor_before
                    trend = "📉" if delta < 0 else ("📊" if delta == 0 else "📈")
                elif s.scenario == "deprecate_module":
                    title = f"🗑 What if `{s.parameter}/` is deprecated?"
                    bus_text = ""
                    trend = "📊"
                else:
                    title = f"❓ {s.scenario}: {s.parameter}"
                    bus_text = ""
                    trend = "📊"

                md = f"### {title}\n\n"
                if bus_text:
                    md += f"{trend} {bus_text}\n\n"
                if s.orphaned_files:
                    md += f"**Orphaned files:** {len(s.orphaned_files)}\n"
                    for f in s.orphaned_files[:5]:
                        md += f"- `{f}`\n"
                    if len(s.orphaned_files) > 5:
                        md += f"- ... and {len(s.orphaned_files) - 5} more\n"
                if s.affected_areas:
                    md += f"\n**Affected areas:** {', '.join(s.affected_areas)}\n"
                if s.impact_summary:
                    md += f"\n💡 _{s.impact_summary}_"

                with Vertical(classes="insight-card"):
                    yield Markdown(md)

    # ── Actions ───────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_create_issue(self) -> None:
        self._open_issue_screen()

    @on(Button.Pressed, "#create-issue-btn")
    def on_create_issue_btn(self) -> None:
        self._open_issue_screen()

    def _open_issue_screen(self) -> None:
        from repo_inspector.screens.issue import IssueScreen

        self.app.push_screen(IssueScreen(self.result))
