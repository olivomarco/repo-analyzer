"""Additional model tests for extended models."""

from datetime import datetime, timezone

from repo_inspector.models import (
    BusFactorMitigationReport,
    ChangelogEntry,
    ChangelogReport,
    DependencyInfo,
    DependencyReport,
    ExtendedResult,
    KnowledgeCell,
    KnowledgeMapReport,
    MitigationAction,
    ReviewCultureReport,
    ReviewerStats,
    SeverityLevel,
    StaleBranch,
    StaleBranchReport,
    TimeComparisonDelta,
    TimeMachineReport,
    Timeframe,
    WhatIfReport,
    WhatIfScenario,
)


class TestExtendedModels:
    def test_knowledge_cell(self):
        cell = KnowledgeCell(login="alice", folder="src", score=0.8, commits=5, lines_changed=200)
        assert cell.score == 0.8
        assert cell.commits == 5

    def test_knowledge_map_report(self):
        report = KnowledgeMapReport(
            contributors=["alice", "bob"],
            folders=["src", "tests"],
            knowledge_silos=["docs"],
        )
        assert len(report.contributors) == 2
        assert len(report.knowledge_silos) == 1

    def test_dependency_info(self):
        dep = DependencyInfo(name="flask", version=">=2.0", ecosystem="python", is_outdated=True)
        assert dep.is_outdated is True
        assert dep.risk_notes == ""

    def test_dependency_report(self):
        report = DependencyReport(total_deps=3, ecosystems=["python", "npm"])
        assert report.total_deps == 3

    def test_reviewer_stats(self):
        reviewer = ReviewerStats(
            login="bob", reviews_given=10, avg_review_time_hours=2.5,
            approvals=8, rejections=1, reviewed_authors=["alice"],
        )
        assert reviewer.reviews_given == 10
        assert "alice" in reviewer.reviewed_authors

    def test_review_culture_report(self):
        report = ReviewCultureReport(
            total_prs_reviewed=20,
            avg_time_to_first_review_hours=4.0,
            bottleneck_reviewers=["bob"],
        )
        assert report.total_prs_reviewed == 20

    def test_stale_branch(self):
        branch = StaleBranch(
            name="old-feature", author="alice", days_stale=120,
            ahead_behind="3 ahead, 15 behind", category="abandoned",
        )
        assert branch.days_stale == 120
        assert branch.category == "abandoned"

    def test_stale_branch_report(self):
        report = StaleBranchReport(total_branches=10, cleanup_candidates=3)
        assert report.total_branches == 10

    def test_changelog_entry(self):
        entry = ChangelogEntry(
            category="feat", scope="auth", description="Add login",
            author="alice", pr_number=42, sha="abc123",
        )
        assert entry.category == "feat"
        assert entry.pr_number == 42

    def test_changelog_report(self):
        report = ChangelogReport(
            entries=[ChangelogEntry(category="fix", description="Bug fix")],
            markdown="## Changelog\n- fix: Bug fix",
        )
        assert len(report.entries) == 1

    def test_mitigation_action(self):
        action = MitigationAction(
            priority=1, action="Pair program", target_contributor="alice",
            target_area="src", rationale="Spread knowledge",
        )
        assert action.priority == 1

    def test_bus_factor_mitigation_report(self):
        report = BusFactorMitigationReport(
            bus_factor=1, risk_level="critical",
            knowledge_monopolists=["alice"],
            exclusive_files={"alice": ["src/main.py"]},
        )
        assert report.risk_level == "critical"
        assert len(report.knowledge_monopolists) == 1

    def test_what_if_scenario(self):
        scenario = WhatIfScenario(
            scenario="remove_contributor", parameter="alice",
            bus_factor_before=2, bus_factor_after=1,
            orphaned_files=["src/main.py"],
            affected_areas=["src"],
        )
        assert scenario.bus_factor_after == 1

    def test_what_if_report(self):
        report = WhatIfReport(
            scenarios=[WhatIfScenario(scenario="remove_contributor", parameter="alice")]
        )
        assert len(report.scenarios) == 1

    def test_time_comparison_delta(self):
        delta = TimeComparisonDelta(
            metric="commits", old_value=50, new_value=75, change="+50%"
        )
        assert delta.change == "+50%"

    def test_time_machine_report(self):
        old_tf = Timeframe(
            since=datetime(2024, 12, 1, tzinfo=timezone.utc),
            until=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        new_tf = Timeframe(
            since=datetime(2025, 1, 1, tzinfo=timezone.utc),
            until=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        report = TimeMachineReport(
            old_timeframe=old_tf, new_timeframe=new_tf,
            contributor_churn=["newdev"], contributor_departed=["olddev"],
            bus_factor_old=2, bus_factor_new=1,
        )
        assert report.bus_factor_old == 2
        assert "newdev" in report.contributor_churn

    def test_extended_result(self):
        result = ExtendedResult()
        assert result.time_machine is None
        assert result.knowledge_map is None
        assert result.dependencies is None

    def test_severity_level_values(self):
        assert SeverityLevel.critical.value == "critical"
        assert SeverityLevel.high.value == "high"
        assert SeverityLevel.medium.value == "medium"
        assert SeverityLevel.low.value == "low"
        assert SeverityLevel.info.value == "info"
