"""Data models for repo-inspector."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Timeframe ──────────────────────────────────────────────────────────────

class Timeframe(BaseModel):
    """Analysis timeframe."""

    since: datetime
    until: datetime = Field(default_factory=datetime.now)

    @property
    def label(self) -> str:
        """Human-readable label."""
        return f"{self.since:%Y-%m-%d} → {self.until:%Y-%m-%d}"


# ── Raw GitHub data ───────────────────────────────────────────────────────

class Commit(BaseModel):
    """A single Git commit."""

    sha: str
    short_sha: str = ""
    message: str
    author_name: str
    author_email: str = ""
    author_login: Optional[str] = None
    date: datetime
    url: str
    additions: int = 0
    deletions: int = 0
    files_changed: list[str] = Field(default_factory=list)

    def model_post_init(self, _ctx: object) -> None:
        if not self.short_sha:
            self.short_sha = self.sha[:7]


class PullRequest(BaseModel):
    """A GitHub Pull Request."""

    number: int
    title: str
    body: Optional[str] = None
    author: str
    created_at: datetime
    merged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    url: str
    labels: list[str] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    review_comments: int = 0


class Issue(BaseModel):
    """A GitHub Issue."""

    number: int
    title: str
    body: Optional[str] = None
    author: str
    state: str = "open"
    created_at: datetime
    closed_at: Optional[datetime] = None
    url: str
    labels: list[str] = Field(default_factory=list)


# ── People analysis ──────────────────────────────────────────────────────

class ContributorStats(BaseModel):
    """Deterministic stats for one contributor."""

    login: str
    name: str = ""
    email: str = ""
    commit_count: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    prs_opened: int = 0
    prs_merged: int = 0
    issues_opened: int = 0
    issues_closed: int = 0
    files_touched: list[str] = Field(default_factory=list)
    top_directories: list[str] = Field(default_factory=list)
    first_commit_date: Optional[datetime] = None
    last_commit_date: Optional[datetime] = None


class ContributorInsight(BaseModel):
    """LLM-generated insight for a contributor."""

    login: str
    inferred_role: str = ""
    activity_summary: str = ""
    judgment: str = ""
    risk_notes: str = ""


class PeopleReport(BaseModel):
    """Full people analysis report."""

    total_contributors: int = 0
    stats: list[ContributorStats] = Field(default_factory=list)
    insights: list[ContributorInsight] = Field(default_factory=list)
    bus_factor: int = 0
    llm_summary: str = ""


# ── Functional analysis ──────────────────────────────────────────────────

class FunctionalArea(BaseModel):
    """One logical area of the codebase."""

    name: str
    path: str
    description: str = ""
    key_files: list[str] = Field(default_factory=list)
    improvement_notes: str = ""


class FunctionalReport(BaseModel):
    """Functional overview of the repo."""

    repo_description: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    areas: list[FunctionalArea] = Field(default_factory=list)
    architecture_notes: str = ""
    llm_summary: str = ""


# ── Code / Security analysis ─────────────────────────────────────────────

class SeverityLevel(str, Enum):
    """Severity of a code finding."""

    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class CodeFinding(BaseModel):
    """A single code quality or security finding."""

    id: str = ""
    folder: str
    file: str = ""
    line: Optional[int] = None
    category: str  # "security", "refactoring", "performance", "style"
    severity: SeverityLevel = SeverityLevel.medium
    title: str
    description: str
    suggestion: str = ""

    @property
    def display_severity(self) -> str:
        icons = {
            SeverityLevel.critical: "🔴",
            SeverityLevel.high: "🟠",
            SeverityLevel.medium: "🟡",
            SeverityLevel.low: "🔵",
            SeverityLevel.info: "⚪",
        }
        return f"{icons[self.severity]} {self.severity.value.upper()}"


class FolderAnalysis(BaseModel):
    """Analysis results for one folder."""

    path: str
    file_count: int = 0
    total_lines: int = 0
    languages: list[str] = Field(default_factory=list)
    findings: list[CodeFinding] = Field(default_factory=list)
    llm_notes: str = ""

    @property
    def finding_count_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        return counts


class CodeReport(BaseModel):
    """Full code analysis report."""

    folders: list[FolderAnalysis] = Field(default_factory=list)
    total_findings: int = 0
    security_findings: int = 0
    refactoring_findings: int = 0
    llm_summary: str = ""


# ── Full inspection result ────────────────────────────────────────────────

class InspectionResult(BaseModel):
    """Complete result of a repo inspection."""

    repo: str
    timeframe: Timeframe
    generated_at: datetime = Field(default_factory=datetime.now)
    people: PeopleReport = Field(default_factory=PeopleReport)
    functional: FunctionalReport = Field(default_factory=FunctionalReport)
    code: CodeReport = Field(default_factory=CodeReport)

    # Raw data (kept for extended analyses)
    commits: list[Commit] = Field(default_factory=list)
    pull_requests: list[PullRequest] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)

    # Extended analysis results (populated after core inspection)
    extended: Optional["ExtendedResult"] = None

class TimeComparisonDelta(BaseModel):
    """Delta between two timeframes for a single metric."""

    metric: str
    old_value: Any = None
    new_value: Any = None
    change: str = ""  # e.g. "+15%", "-3"


class TimeMachineReport(BaseModel):
    """Comparison of two analysis timeframes."""

    old_timeframe: Timeframe
    new_timeframe: Timeframe
    contributor_churn: list[str] = Field(default_factory=list)  # joined
    contributor_departed: list[str] = Field(default_factory=list)  # left
    bus_factor_old: int = 0
    bus_factor_new: int = 0
    commit_count_old: int = 0
    commit_count_new: int = 0
    findings_old: int = 0
    findings_new: int = 0
    deltas: list[TimeComparisonDelta] = Field(default_factory=list)
    llm_summary: str = ""


# ── Knowledge Map ─────────────────────────────────────────────────────

class KnowledgeCell(BaseModel):
    """Contributor's familiarity with a folder (0.0–1.0)."""

    login: str
    folder: str
    score: float = 0.0  # normalized 0–1
    commits: int = 0
    lines_changed: int = 0


class KnowledgeMapReport(BaseModel):
    """Matrix of contributor knowledge across repository folders."""

    contributors: list[str] = Field(default_factory=list)
    folders: list[str] = Field(default_factory=list)
    cells: list[KnowledgeCell] = Field(default_factory=list)
    knowledge_silos: list[str] = Field(default_factory=list)  # folders with single owner
    pairing_suggestions: list[str] = Field(default_factory=list)
    llm_summary: str = ""


# ── Dependency Risk Scanner ───────────────────────────────────────────

class DependencyInfo(BaseModel):
    """A single project dependency."""

    name: str
    version: str = ""
    source_file: str = ""  # e.g. "requirements.txt"
    ecosystem: str = ""  # "python", "npm", "rust", etc.
    is_outdated: bool = False
    risk_notes: str = ""


class DependencyReport(BaseModel):
    """Full dependency risk analysis."""

    dependencies: list[DependencyInfo] = Field(default_factory=list)
    total_deps: int = 0
    ecosystems: list[str] = Field(default_factory=list)
    llm_summary: str = ""


# ── Review Culture Analyzer ───────────────────────────────────────────

class ReviewerStats(BaseModel):
    """Statistics for a single PR reviewer."""

    login: str
    reviews_given: int = 0
    avg_review_time_hours: float = 0.0
    comments_per_review: float = 0.0
    approvals: int = 0
    rejections: int = 0
    reviewed_authors: list[str] = Field(default_factory=list)


class ReviewCultureReport(BaseModel):
    """PR review culture analysis."""

    total_prs_reviewed: int = 0
    avg_time_to_first_review_hours: float = 0.0
    reviewers: list[ReviewerStats] = Field(default_factory=list)
    bottleneck_reviewers: list[str] = Field(default_factory=list)
    review_pairs: list[str] = Field(default_factory=list)  # "A ↔ B"
    llm_summary: str = ""


# ── Stale Branch Cemetery ────────────────────────────────────────────

class StaleBranch(BaseModel):
    """A branch that appears abandoned."""

    name: str
    last_commit_date: Optional[datetime] = None
    author: str = ""
    days_stale: int = 0
    ahead_behind: str = ""  # e.g. "3 ahead, 12 behind"
    category: str = ""  # "orphan", "wip", "stale-feature"


class StaleBranchReport(BaseModel):
    """Report on stale/abandoned branches."""

    total_branches: int = 0
    stale_branches: list[StaleBranch] = Field(default_factory=list)
    cleanup_candidates: int = 0
    llm_summary: str = ""


# ── Commit Journal (Changelog) ───────────────────────────────────────

class ChangelogEntry(BaseModel):
    """A single entry in the auto-generated changelog."""

    category: str = ""  # "feat", "fix", "chore", "docs", "refactor"
    scope: str = ""  # functional area
    description: str = ""
    author: str = ""
    pr_number: Optional[int] = None
    sha: str = ""


class ChangelogReport(BaseModel):
    """Auto-generated changelog from commits."""

    entries: list[ChangelogEntry] = Field(default_factory=list)
    markdown: str = ""
    llm_summary: str = ""


# ── Bus Factor Mitigation Plan ───────────────────────────────────────

class MitigationAction(BaseModel):
    """A single action to reduce bus factor risk."""

    priority: int = 0
    action: str = ""
    target_contributor: str = ""
    target_area: str = ""
    rationale: str = ""


class BusFactorMitigationReport(BaseModel):
    """Plan to mitigate bus factor risk."""

    bus_factor: int = 0
    risk_level: str = ""  # "critical", "high", "medium", "low"
    knowledge_monopolists: list[str] = Field(default_factory=list)
    exclusive_files: dict[str, list[str]] = Field(default_factory=dict)  # login -> files
    actions: list[MitigationAction] = Field(default_factory=list)
    llm_summary: str = ""


# ── What-If Simulator ────────────────────────────────────────────────

class WhatIfScenario(BaseModel):
    """A single what-if simulation result."""

    scenario: str = ""  # "remove_contributor", "deprecate_module", etc.
    parameter: str = ""  # e.g. contributor login or module name
    bus_factor_before: int = 0
    bus_factor_after: int = 0
    orphaned_files: list[str] = Field(default_factory=list)
    affected_areas: list[str] = Field(default_factory=list)
    impact_summary: str = ""


class WhatIfReport(BaseModel):
    """What-if simulation results."""

    scenarios: list[WhatIfScenario] = Field(default_factory=list)
    llm_summary: str = ""


# ── Extended InspectionResult ─────────────────────────────────────────

class ExtendedResult(BaseModel):
    """All additional analysis reports beyond the core inspection."""

    time_machine: Optional[TimeMachineReport] = None
    knowledge_map: Optional[KnowledgeMapReport] = None
    dependencies: Optional[DependencyReport] = None
    review_culture: Optional[ReviewCultureReport] = None
    stale_branches: Optional[StaleBranchReport] = None
    changelog: Optional[ChangelogReport] = None
    bus_mitigation: Optional[BusFactorMitigationReport] = None
    what_if: Optional[WhatIfReport] = None


# Resolve forward reference for InspectionResult.extended
InspectionResult.model_rebuild()
