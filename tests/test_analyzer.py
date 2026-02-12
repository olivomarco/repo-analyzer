"""Tests for the analyzer module."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_inspector.analyzer import Analyzer
from repo_inspector.models import (
    BusFactorMitigationReport,
    CodeFinding,
    CodeReport,
    ContributorInsight,
    ContributorStats,
    FolderAnalysis,
    FunctionalArea,
    FunctionalReport,
    InspectionResult,
    MitigationAction,
    PeopleReport,
    SeverityLevel,
    Timeframe,
    WhatIfReport,
    WhatIfScenario,
)


class TestAnalyzerInit:
    def test_init_with_token(self):
        analyzer = Analyzer(token="my-token")
        assert analyzer.token == "my-token"
        assert analyzer.model == "gpt-4.1"

    def test_init_without_token(self):
        with patch.dict("os.environ", {}, clear=True):
            analyzer = Analyzer()
            assert analyzer.token is None

    def test_init_with_env_token(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}):
            analyzer = Analyzer()
            assert analyzer.token == "env-token"

    def test_init_with_gh_token(self):
        with patch.dict("os.environ", {"GH_TOKEN": "gh-token"}, clear=True):
            analyzer = Analyzer()
            assert analyzer.token == "gh-token"

    def test_init_custom_model(self):
        analyzer = Analyzer(model="gpt-3.5-turbo")
        assert analyzer.model == "gpt-3.5-turbo"

    def test_on_status_callback(self):
        messages = []
        analyzer = Analyzer(on_status=messages.append)
        analyzer._status("hello")
        assert messages == ["hello"]

    def test_default_on_status(self):
        analyzer = Analyzer()
        analyzer._status("no-op")  # should not raise


class TestParseContributorInsights:
    def setup_method(self):
        self.analyzer = Analyzer(token="test")

    def test_parses_valid_json(self):
        raw = json.dumps([
            {
                "login": "alice",
                "inferred_role": "Backend Engineer",
                "activity_summary": "Active contributor",
                "judgment": "Strong contributor",
                "risk_notes": "",
            }
        ])
        insights = self.analyzer._parse_contributor_insights(raw)
        assert len(insights) == 1
        assert insights[0].login == "alice"
        assert insights[0].inferred_role == "Backend Engineer"

    def test_parses_json_with_fences(self):
        raw = '```json\n[{"login": "bob", "activity_summary": "writes code"}]\n```'
        insights = self.analyzer._parse_contributor_insights(raw)
        assert len(insights) == 1
        assert insights[0].login == "bob"

    def test_handles_invalid_json(self):
        raw = "This is not JSON at all"
        insights = self.analyzer._parse_contributor_insights(raw)
        assert len(insights) == 1
        assert insights[0].login == "(parse error)"

    def test_handles_empty_array(self):
        raw = "[]"
        insights = self.analyzer._parse_contributor_insights(raw)
        assert insights == []


class TestParseFunctionalReport:
    def setup_method(self):
        self.analyzer = Analyzer(token="test")

    def test_parses_valid_json(self):
        areas = [
            FunctionalArea(name="src", path="src", description="Source code"),
        ]
        raw = json.dumps({
            "repo_description": "A test repo",
            "tech_stack": ["Python"],
            "architecture_notes": "Clean architecture",
            "area_improvements": {"src": "Add more tests"},
            "summary": "Good repo",
        })
        report = self.analyzer._parse_functional_report(raw, areas)
        assert report.repo_description == "A test repo"
        assert "Python" in report.tech_stack
        assert areas[0].improvement_notes == "Add more tests"

    def test_handles_invalid_json(self):
        areas = [FunctionalArea(name="src", path="src")]
        raw = "Not valid JSON"
        report = self.analyzer._parse_functional_report(raw, areas)
        assert report.llm_summary == "(Failed to parse LLM response)"

    def test_handles_json_with_fences(self):
        areas = []
        raw = '```json\n{"repo_description": "test", "summary": "ok"}\n```'
        report = self.analyzer._parse_functional_report(raw, areas)
        assert report.repo_description == "test"


class TestParseCodeFindings:
    def setup_method(self):
        self.analyzer = Analyzer(token="test")

    def test_parses_valid_findings(self):
        raw = json.dumps([
            {
                "category": "security",
                "severity": "high",
                "title": "SQL Injection",
                "description": "User input not sanitized",
                "suggestion": "Use parameterized queries",
                "file": "src/db.py",
            },
            {
                "category": "refactoring",
                "severity": "low",
                "title": "Long function",
                "description": "Function too long",
                "suggestion": "Break into smaller functions",
                "file": "src/main.py",
            },
        ])
        findings = self.analyzer._parse_code_findings(raw, "src")
        assert len(findings) == 2
        assert findings[0].category == "security"
        assert findings[0].severity == SeverityLevel.high
        assert findings[0].id == "src-1"
        assert findings[1].id == "src-2"

    def test_handles_invalid_json(self):
        findings = self.analyzer._parse_code_findings("not json", "src")
        assert findings == []

    def test_handles_empty_array(self):
        findings = self.analyzer._parse_code_findings("[]", "src")
        assert findings == []

    def test_parses_with_markdown_fences(self):
        raw = '```\n[{"category":"style","severity":"info","title":"Naming","description":"bad name","suggestion":"rename"}]\n```'
        findings = self.analyzer._parse_code_findings(raw, "utils")
        assert len(findings) == 1
        assert findings[0].folder == "utils"


class TestAskLlmList:
    def setup_method(self):
        self.analyzer = Analyzer(token="test")

    @pytest.mark.asyncio
    async def test_parses_json_list(self):
        self.analyzer._ask_llm = AsyncMock(return_value='["item1", "item2"]')
        result = await self.analyzer._ask_llm_list("test prompt")
        assert result == ["item1", "item2"]

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self):
        self.analyzer._ask_llm = AsyncMock(return_value="not json")
        result = await self.analyzer._ask_llm_list("test prompt")
        assert len(result) == 1
        assert "not json" in result[0]

    @pytest.mark.asyncio
    async def test_handles_empty_response(self):
        self.analyzer._ask_llm = AsyncMock(return_value="")
        result = await self.analyzer._ask_llm_list("test prompt")
        assert result == []

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self):
        self.analyzer._ask_llm = AsyncMock(return_value='```json\n["a", "b"]\n```')
        result = await self.analyzer._ask_llm_list("test prompt")
        assert result == ["a", "b"]


class TestAnalyzerClose:
    @pytest.mark.asyncio
    async def test_close_cleans_up(self):
        analyzer = Analyzer(token="test")
        analyzer._fetcher.close = AsyncMock()
        analyzer._cloner.cleanup = MagicMock()
        await analyzer.close()
        analyzer._fetcher.close.assert_called_once()
        analyzer._cloner.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_copilot_session(self):
        analyzer = Analyzer(token="test")
        analyzer._fetcher.close = AsyncMock()
        analyzer._cloner.cleanup = MagicMock()
        mock_session = MagicMock()
        mock_session.destroy = AsyncMock()
        analyzer._copilot_session = mock_session
        mock_client = MagicMock()
        mock_client.stop = AsyncMock()
        analyzer._copilot_client = mock_client
        await analyzer.close()
        mock_session.destroy.assert_called_once()
        mock_client.stop.assert_called_once()


class TestAnalyzeDependenciesLlm:
    @pytest.mark.asyncio
    async def test_enriches_report(self):
        from repo_inspector.models import DependencyInfo, DependencyReport

        analyzer = Analyzer(token="test")
        analyzer._ask_llm = AsyncMock(
            return_value=json.dumps({
                "risk_notes": {"flask": "Consider updating"},
                "summary": "Dependencies look good overall.",
            })
        )
        report = DependencyReport(
            dependencies=[
                DependencyInfo(name="flask", version=">=2.0", ecosystem="python"),
                DependencyInfo(name="requests", version="==2.28", ecosystem="python"),
            ],
            total_deps=2,
            ecosystems=["python"],
        )
        result = await analyzer._analyze_dependencies_llm("owner", "repo", report)
        assert result.llm_summary == "Dependencies look good overall."
        flask_dep = next(d for d in result.dependencies if d.name == "flask")
        assert flask_dep.risk_notes == "Consider updating"

    @pytest.mark.asyncio
    async def test_handles_invalid_llm_response(self):
        from repo_inspector.models import DependencyInfo, DependencyReport

        analyzer = Analyzer(token="test")
        analyzer._ask_llm = AsyncMock(return_value="Not valid json!")
        report = DependencyReport(
            dependencies=[DependencyInfo(name="flask", ecosystem="python")],
            total_deps=1,
        )
        result = await analyzer._analyze_dependencies_llm("owner", "repo", report)
        assert "Not valid json!" in result.llm_summary


class TestAnalyzeMitigationLlm:
    @pytest.mark.asyncio
    async def test_generates_actions(self):
        analyzer = Analyzer(token="test")
        analyzer._ask_llm = AsyncMock(
            return_value=json.dumps({
                "actions": [
                    {
                        "priority": 1,
                        "action": "Pair program",
                        "target_contributor": "alice",
                        "target_area": "src",
                        "rationale": "Spread knowledge",
                    }
                ],
                "summary": "Focus on knowledge sharing.",
            })
        )
        report = BusFactorMitigationReport(
            bus_factor=1,
            risk_level="critical",
            knowledge_monopolists=["alice"],
            exclusive_files={"alice": ["src/main.py"]},
        )
        result = await analyzer._analyze_mitigation_llm("owner", "repo", report)
        assert len(result.actions) == 1
        assert result.actions[0].action == "Pair program"
        assert result.llm_summary == "Focus on knowledge sharing."


class TestAnalyzeWhatIfLlm:
    @pytest.mark.asyncio
    async def test_enriches_scenarios(self):
        analyzer = Analyzer(token="test")
        analyzer._ask_llm = AsyncMock(
            return_value=json.dumps({
                "impact_summaries": {
                    "remove_contributor:alice": "Major impact on auth module",
                },
                "summary": "Alice is critical.",
            })
        )
        report = WhatIfReport(
            scenarios=[
                WhatIfScenario(
                    scenario="remove_contributor",
                    parameter="alice",
                    bus_factor_before=2,
                    bus_factor_after=1,
                    orphaned_files=["src/auth.py"],
                    affected_areas=["src"],
                ),
            ],
        )
        result = await analyzer._analyze_what_if_llm("owner", "repo", report)
        assert result.llm_summary == "Alice is critical."
        assert result.scenarios[0].impact_summary == "Major impact on auth module"


class TestInspect:
    @pytest.mark.asyncio
    async def test_full_inspect_pipeline(self):
        """Test the full inspect pipeline with all external calls mocked."""
        from repo_inspector.models import Commit, PullRequest, Issue

        analyzer = Analyzer(token="test")
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 2, 1, tzinfo=timezone.utc)

        # Mock fetcher
        mock_commits = [
            Commit(
                sha="abc123", message="feat: add auth", author_name="Alice",
                author_login="alice", date=since, url="https://example.com/c/1",
                additions=100, deletions=10, files_changed=["src/auth.py"],
            ),
        ]
        mock_prs = [
            PullRequest(
                number=1, title="Add auth", author="alice",
                created_at=since, merged_at=since, url="https://example.com/pr/1",
            ),
        ]
        mock_issues = [
            Issue(
                number=10, title="Bug", author="bob", state="open",
                created_at=since, url="https://example.com/i/10",
            ),
        ]

        analyzer._fetcher.fetch_commits = AsyncMock(return_value=mock_commits)
        analyzer._fetcher.fetch_pull_requests = AsyncMock(return_value=mock_prs)
        analyzer._fetcher.fetch_issues = AsyncMock(return_value=mock_issues)
        analyzer._fetcher.fetch_commit_detail = AsyncMock(return_value={
            "stats": {"additions": 50, "deletions": 5},
            "files": [{"filename": "src/auth.py"}],
        })
        analyzer._fetcher.fetch_readme = AsyncMock(return_value="# Test Repo")
        analyzer._fetcher.fetch_repo_info = AsyncMock(return_value={
            "description": "Test", "topics": ["python"], "default_branch": "main",
        })
        analyzer._fetcher._saml_fallback = False
        analyzer._fetcher.fetch_branches = AsyncMock(return_value=[])
        analyzer._fetcher.fetch_default_branch = AsyncMock(return_value="main")

        # Mock cloner
        analyzer._cloner.clone = MagicMock(return_value=MagicMock())
        analyzer._cloner.list_top_level_dirs = MagicMock(return_value=["src", "tests"])
        analyzer._cloner.folder_stats = MagicMock(return_value={"files": 5, "lines": 100})
        analyzer._cloner.detect_languages = MagicMock(return_value=["Python"])
        analyzer._cloner.list_files_in_dir = MagicMock(return_value=[])
        analyzer._cloner.get_tree_summary = MagicMock(return_value="src/\n  main.py")
        analyzer._cloner.read_file = MagicMock(return_value="")
        analyzer._cloner.parse_dependencies = MagicMock(return_value=[])
        analyzer._cloner.detect_dependency_files = MagicMock(return_value={})

        # Mock LLM
        analyzer._ask_llm = AsyncMock(return_value="Test summary")
        analyzer._ask_llm_list = AsyncMock(return_value=["suggestion 1"])
        analyzer._analyze_people_llm = AsyncMock(return_value=[])
        analyzer._analyze_functional_llm = AsyncMock(return_value=FunctionalReport(
            repo_description="Test repo",
            areas=[FunctionalArea(name="src", path="src")],
        ))
        analyzer._analyze_code_llm = AsyncMock(return_value=CodeReport())
        analyzer._run_extended_analyses = AsyncMock(return_value=None)

        result = await analyzer.inspect("owner", "repo", since, until)

        assert result.repo == "owner/repo"
        assert result.people.total_contributors >= 1
        assert result.people.bus_factor >= 1
        analyzer._fetcher.fetch_commits.assert_called_once()
        analyzer._cloner.clone.assert_called_once()


class TestAnalyzePeopleLlm:
    @pytest.mark.asyncio
    async def test_returns_insights(self):
        analyzer = Analyzer(token="test")
        analyzer._ask_llm = AsyncMock(
            return_value=json.dumps([{
                "login": "alice",
                "inferred_role": "Backend Engineer",
                "activity_summary": "Active",
                "judgment": "Strong",
                "risk_notes": "",
            }])
        )
        stats = [ContributorStats(
            login="alice", commit_count=10, lines_added=500,
            lines_removed=50, prs_opened=3, prs_merged=2,
            top_directories=["src"],
        )]
        tf = Timeframe(
            since=datetime(2025, 1, 1, tzinfo=timezone.utc),
            until=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        insights = await analyzer._analyze_people_llm("owner", "repo", stats, tf)
        assert len(insights) == 1
        assert insights[0].login == "alice"

    @pytest.mark.asyncio
    async def test_empty_stats_returns_empty(self):
        analyzer = Analyzer(token="test")
        tf = Timeframe(
            since=datetime(2025, 1, 1, tzinfo=timezone.utc),
            until=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        result = await analyzer._analyze_people_llm("owner", "repo", [], tf)
        assert result == []


class TestAnalyzeReviewCulture:
    @pytest.mark.asyncio
    async def test_builds_review_report(self):
        from repo_inspector.models import PullRequest

        analyzer = Analyzer(token="test")
        analyzer._fetcher.fetch_pr_reviews = AsyncMock(return_value=[
            {"id": 1, "user": {"login": "bob"}, "state": "APPROVED",
             "submitted_at": "2025-01-12T10:00:00Z"},
        ])
        analyzer._ask_llm = AsyncMock(return_value="Review culture is healthy.")

        prs = [
            PullRequest(
                number=1, title="Add auth", author="alice",
                created_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
                url="https://example.com/pr/1",
            ),
        ]
        report = await analyzer._analyze_review_culture("owner", "repo", prs)
        assert report.total_prs_reviewed >= 0


class TestAnalyzeStaleBranches:
    @pytest.mark.asyncio
    async def test_builds_stale_report(self):
        analyzer = Analyzer(token="test")
        analyzer._fetcher.fetch_branches = AsyncMock(return_value=[
            {"name": "main", "commit": {"sha": "abc", "commit": {"author": {"date": "2025-01-15T00:00:00Z"}}}},
            {"name": "old-feat", "commit": {"sha": "def", "commit": {"author": {"date": "2024-01-01T00:00:00Z"}}}},
        ])
        analyzer._fetcher.fetch_default_branch = AsyncMock(return_value="main")
        analyzer._fetcher.fetch_branch_compare = AsyncMock(return_value={"ahead_by": 3, "behind_by": 12})
        analyzer._ask_llm = AsyncMock(return_value="Branch hygiene needs attention.")

        report = await analyzer._analyze_stale_branches("owner", "repo")
        assert report.total_branches >= 0

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        analyzer = Analyzer(token="test")
        analyzer._fetcher.fetch_branches = AsyncMock(side_effect=Exception("Network error"))

        report = await analyzer._analyze_stale_branches("owner", "repo")
        assert report.total_branches == 0


class TestRunExtendedAnalyses:
    @pytest.mark.asyncio
    async def test_runs_all_analyses(self):
        from repo_inspector.models import (
            Commit, PullRequest, Issue, ExtendedResult
        )

        analyzer = Analyzer(token="test")
        analyzer._fetcher._saml_fallback = False

        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 2, 1, tzinfo=timezone.utc)
        tf = Timeframe(since=since, until=until)

        commits = [
            Commit(
                sha="abc123", message="feat: auth", author_name="Alice",
                author_login="alice", date=since, url="https://x.com/c/1",
                additions=100, deletions=10, files_changed=["src/auth.py"],
            ),
        ]
        prs = [
            PullRequest(
                number=1, title="Add auth", author="alice",
                created_at=since, merged_at=since, url="https://x.com/pr/1",
            ),
        ]
        issues = [
            Issue(
                number=10, title="Bug", author="bob",
                created_at=since, url="https://x.com/i/10",
            ),
        ]
        stats = [ContributorStats(login="alice", commit_count=10)]

        result = InspectionResult(
            repo="owner/repo", timeframe=tf,
            people=PeopleReport(
                total_contributors=1, stats=stats, bus_factor=1,
            ),
            code=CodeReport(),
            commits=commits, pull_requests=prs, issues=issues,
        )

        # Mock everything
        analyzer._cloner.list_top_level_dirs = MagicMock(return_value=["src"])
        analyzer._cloner.parse_dependencies = MagicMock(return_value=[])
        analyzer._cloner.detect_dependency_files = MagicMock(return_value={})
        analyzer._ask_llm = AsyncMock(return_value="Summary text")
        analyzer._ask_llm_list = AsyncMock(return_value=["pair suggestion"])
        analyzer._analyze_dependencies_llm = AsyncMock(side_effect=lambda o, r, rep: rep)
        analyzer._analyze_review_culture = AsyncMock(
            return_value=MagicMock(reviewers=[], llm_summary="")
        )
        analyzer._analyze_stale_branches = AsyncMock(
            return_value=MagicMock(stale_branches=[], llm_summary="")
        )
        analyzer._analyze_what_if_llm = AsyncMock(
            return_value=WhatIfReport(scenarios=[])
        )
        analyzer._run_time_machine = AsyncMock(return_value=MagicMock())

        extended = await analyzer._run_extended_analyses(
            "owner", "repo", result, tf, since, until
        )

        assert extended.knowledge_map is not None
        assert extended.dependencies is not None
        assert extended.changelog is not None
        assert extended.bus_mitigation is not None
        assert extended.what_if is not None


class TestAnalyzeCodeLlm:
    @pytest.mark.asyncio
    async def test_analyze_code_folders(self):
        analyzer = Analyzer(token="test")
        analyzer._ask_llm = AsyncMock(return_value=json.dumps([
            {
                "category": "security",
                "severity": "high",
                "title": "SQL Injection",
                "description": "Unsanitized input",
                "suggestion": "Parameterize queries",
                "file": "src/db.py",
            }
        ]))
        analyzer._cloner = MagicMock()
        analyzer._cloner.list_files_in_dir = MagicMock(return_value=[])
        analyzer._cloner.read_file = MagicMock(return_value="def foo(): pass")

        # Patch gather_code_samples to return code
        with patch("repo_inspector.analyzer.gather_code_samples", return_value="def foo(): pass"):
            folders = [
                FolderAnalysis(path="src", file_count=5, total_lines=100, languages=["Python"]),
            ]
            report = await analyzer._analyze_code_llm("owner", "repo", folders)
            assert report.total_findings >= 1
            assert report.security_findings >= 1

    @pytest.mark.asyncio
    async def test_skips_empty_folders(self):
        analyzer = Analyzer(token="test")
        analyzer._ask_llm = AsyncMock(return_value="Summary")

        with patch("repo_inspector.analyzer.gather_code_samples", return_value=""):
            folders = [
                FolderAnalysis(path="empty", file_count=0, total_lines=0),
            ]
            report = await analyzer._analyze_code_llm("owner", "repo", folders)
            assert report.total_findings == 0


class TestRunTimeMachine:
    @pytest.mark.asyncio
    async def test_compares_periods(self):
        from repo_inspector.models import Commit, PullRequest, Issue

        analyzer = Analyzer(token="test")
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 2, 1, tzinfo=timezone.utc)
        tf = Timeframe(since=since, until=until)

        old_commits = [
            Commit(
                sha="old1", message="old feat", author_name="Bob",
                author_login="bob", date=datetime(2024, 12, 15, tzinfo=timezone.utc),
                url="https://x.com/c/old1", additions=50, deletions=5,
                files_changed=["src/old.py"],
            ),
        ]
        analyzer._fetcher.fetch_commits = AsyncMock(return_value=old_commits)
        analyzer._fetcher.fetch_pull_requests = AsyncMock(return_value=[])
        analyzer._fetcher.fetch_issues = AsyncMock(return_value=[])
        analyzer._ask_llm = AsyncMock(return_value="Time machine summary")

        current_result = InspectionResult(
            repo="owner/repo", timeframe=tf,
            people=PeopleReport(
                total_contributors=1,
                stats=[ContributorStats(login="alice", commit_count=10)],
                bus_factor=1,
            ),
            code=CodeReport(total_findings=3),
        )

        report = await analyzer._run_time_machine(
            "owner", "repo", current_result, tf, since, until
        )
        assert report.llm_summary == "Time machine summary"
        assert report.old_timeframe is not None
        assert report.new_timeframe == tf

    @pytest.mark.asyncio
    async def test_handles_fetch_error(self):
        analyzer = Analyzer(token="test")
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        until = datetime(2025, 2, 1, tzinfo=timezone.utc)
        tf = Timeframe(since=since, until=until)

        analyzer._fetcher.fetch_commits = AsyncMock(side_effect=Exception("API error"))

        current_result = InspectionResult(
            repo="owner/repo", timeframe=tf,
            people=PeopleReport(bus_factor=1),
            code=CodeReport(),
        )

        report = await analyzer._run_time_machine(
            "owner", "repo", current_result, tf, since, until
        )
        assert "Could not fetch" in report.llm_summary
