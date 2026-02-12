"""Copilot SDK–powered analysis engine.

Orchestrates GitHub data fetching, local clone analysis, and LLM calls
to produce a complete InspectionResult.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from repo_inspector.analysis.bus_mitigation import build_bus_mitigation
from repo_inspector.analysis.changelog import build_changelog, render_changelog_markdown
from repo_inspector.analysis.code import build_folder_analyses
from repo_inspector.analysis.dependencies import build_dependency_report
from repo_inspector.analysis.functional import build_functional_areas, gather_code_samples
from repo_inspector.analysis.knowledge_map import build_knowledge_map
from repo_inspector.analysis.people import compute_bus_factor, compute_contributor_stats
from repo_inspector.analysis.review_culture import build_review_culture
from repo_inspector.analysis.stale_branches import build_stale_branch_report
from repo_inspector.analysis.time_machine import build_time_comparison
from repo_inspector.analysis.what_if import build_what_if_report
from repo_inspector.cloner import RepoCloner
from repo_inspector.fetcher import GitHubFetcher
from repo_inspector.models import (
    BusFactorMitigationReport,
    CodeFinding,
    CodeReport,
    ContributorInsight,
    DependencyReport,
    ExtendedResult,
    FunctionalReport,
    InspectionResult,
    PeopleReport,
    ReviewCultureReport,
    SeverityLevel,
    StaleBranchReport,
    Timeframe,
    TimeMachineReport,
    WhatIfReport,
)


class Analyzer:
    """End-to-end repo inspection powered by Copilot SDK."""

    def __init__(
        self,
        token: Optional[str] = None,
        model: str = "gpt-4.1",
        on_status: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or None
        self.model = model
        self._on_status = on_status or (lambda _: None)
        self._fetcher = GitHubFetcher(token=self.token)
        self._cloner = RepoCloner(token=self.token)
        self._copilot_client: object | None = None
        self._copilot_session: object | None = None

    # ── Status helper ─────────────────────────────────────────────────────

    def _status(self, msg: str) -> None:
        self._on_status(msg)

    # ── Copilot SDK lifecycle ─────────────────────────────────────────────

    async def _ensure_copilot(self) -> None:
        """Lazily start the CopilotClient and create a session."""
        if self._copilot_session is not None:
            return
        import stat
        import tempfile

        from copilot import CopilotClient  # type: ignore[import-untyped]

        # Workaround: the pip-installed SDK may ship the CLI binary without
        # execute permission.  Fix it automatically if needed.
        try:
            import copilot.bin as _bin_pkg
            cli_bin = Path(_bin_pkg.__file__).parent / "copilot"
            if cli_bin.exists() and not os.access(cli_bin, os.X_OK):
                cli_bin.chmod(cli_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except Exception:
            pass

        # Use a temp directory as CWD so the Copilot CLI doesn't try to
        # write state files into the (possibly read-only) workspace.
        copilot_cwd = tempfile.mkdtemp(prefix="repoinspect-copilot-")
        self._copilot_client = CopilotClient({
            "cwd": copilot_cwd,
        })
        await self._copilot_client.start()  # type: ignore[union-attr]

        # Deny all tool use via hooks — we only want pure LLM text responses,
        # not agentic behaviour (filesystem browsing, git ops, etc.)
        async def deny_all_tools(input: dict, invocation: object) -> dict:
            return {
                "permissionDecision": "deny",
            }

        self._copilot_session = await self._copilot_client.create_session(  # type: ignore[union-attr]
            {
                "model": self.model,
                "infinite_sessions": {"enabled": False},
                "system_message": {
                    "content": (
                        "You are a code analysis assistant for the repo-inspector tool. "
                        "You ONLY analyze data provided to you in the prompt. "
                        "You NEVER use tools, browse the filesystem, run commands, or "
                        "access external resources. You respond ONLY with the requested "
                        "format (JSON or plain text). Be concise and precise."
                    ),
                },
                "hooks": {
                    "on_pre_tool_use": deny_all_tools,
                },
            }
        )

    async def _ask_llm(self, prompt: str) -> str:
        """Send a prompt to Copilot and collect the full response."""
        await self._ensure_copilot()
        session = self._copilot_session
        done = asyncio.Event()
        result_parts: list[str] = []

        def _on_event(event: object) -> None:
            etype = getattr(getattr(event, "type", None), "value", "")
            data = getattr(event, "data", None)
            if etype == "assistant.message" and data:
                content = getattr(data, "content", "") or ""
                if content:
                    result_parts.append(content)
                done.set()
            elif etype == "session.idle":
                done.set()

        # Subscribe and capture the unsubscribe function so we
        # don't stack handlers across multiple _ask_llm calls.
        unsubscribe = session.on(_on_event)  # type: ignore[union-attr]
        try:
            await session.send({"prompt": prompt})  # type: ignore[union-attr]
            await done.wait()
        finally:
            # Unsubscribe this handler regardless of success/failure
            if callable(unsubscribe):
                unsubscribe()

        return "".join(result_parts).strip()

    async def close(self) -> None:
        """Tear down resources."""
        await self._fetcher.close()
        self._cloner.cleanup()
        if self._copilot_session:
            try:
                await self._copilot_session.destroy()  # type: ignore[union-attr]
            except Exception:
                pass
        if self._copilot_client:
            try:
                await self._copilot_client.stop()  # type: ignore[union-attr]
            except Exception:
                pass

    # ── Full inspection ───────────────────────────────────────────────────

    async def inspect(
        self,
        owner: str,
        repo: str,
        since: datetime,
        until: Optional[datetime] = None,
    ) -> InspectionResult:
        """Run the entire inspection pipeline."""
        until = until or datetime.now(timezone.utc)
        timeframe = Timeframe(since=since, until=until)

        # 1. Fetch GitHub data
        self._status("Fetching commits …")
        commits = await self._fetcher.fetch_commits(owner, repo, since, until)

        self._status("Fetching pull requests …")
        prs = await self._fetcher.fetch_pull_requests(owner, repo, since, until)

        self._status("Fetching issues …")
        issues = await self._fetcher.fetch_issues(owner, repo, since)

        # Enrich commits with file-level stats
        # Use fewer calls when unauthenticated (rate limit: 60/hour)
        enrich_limit = 10 if self._fetcher.is_unauthenticated else 50
        self._status(f"Enriching commit details ({enrich_limit}) …")
        for c in commits[:enrich_limit]:
            try:
                detail = await self._fetcher.fetch_commit_detail(owner, repo, c.sha)
                c.additions = detail.get("stats", {}).get("additions", 0)
                c.deletions = detail.get("stats", {}).get("deletions", 0)
                c.files_changed = [f["filename"] for f in detail.get("files", [])]
            except Exception:
                pass

        # 2. Clone repo
        self._status("Cloning repository …")
        self._cloner.clone(owner, repo)

        # 3. People analysis
        self._status("Analyzing contributors …")
        contributor_stats = compute_contributor_stats(commits, prs, issues)
        bus_factor = compute_bus_factor(contributor_stats)
        contributor_insights = await self._analyze_people_llm(
            owner, repo, contributor_stats, timeframe
        )

        people_summary = await self._ask_llm(
            f"In 2-3 sentences, summarize the contributor landscape for {owner}/{repo} "
            f"during {timeframe.label}. There are {len(contributor_stats)} contributors, "
            f"bus factor is {bus_factor}. Top contributor has {contributor_stats[0].commit_count if contributor_stats else 0} commits."
        )

        people_report = PeopleReport(
            total_contributors=len(contributor_stats),
            stats=contributor_stats,
            insights=contributor_insights,
            bus_factor=bus_factor,
            llm_summary=people_summary,
        )

        # 4. Functional analysis
        self._status("Analyzing functional areas …")
        readme = await self._fetcher.fetch_readme(owner, repo) or ""
        repo_info = await self._fetcher.fetch_repo_info(owner, repo)
        areas = build_functional_areas(self._cloner)
        tree = self._cloner.get_tree_summary(max_depth=2)

        functional_report = await self._analyze_functional_llm(
            owner, repo, readme, repo_info, areas, tree
        )

        # 5. Code / Security analysis
        self._status("Analyzing code quality & security …")
        folder_analyses = build_folder_analyses(self._cloner)
        code_report = await self._analyze_code_llm(owner, repo, folder_analyses)

        self._status("Done!")

        result = InspectionResult(
            repo=f"{owner}/{repo}",
            timeframe=timeframe,
            people=people_report,
            functional=functional_report,
            code=code_report,
            commits=commits,
            pull_requests=prs,
            issues=issues,
        )

        # 6. Extended analyses
        self._status("Running extended analyses …")
        extended = await self._run_extended_analyses(
            owner, repo, result, timeframe, since, until
        )
        result.extended = extended

        self._status("All analyses complete!")
        return result

    # ── Extended analysis orchestrator ────────────────────────────────────

    async def _run_extended_analyses(
        self,
        owner: str,
        repo: str,
        result: InspectionResult,
        timeframe: Timeframe,
        since: datetime,
        until: datetime,
    ) -> ExtendedResult:
        """Run all extended analyses: time machine, knowledge map, etc."""
        extended = ExtendedResult()
        low_api = self._fetcher.is_unauthenticated  # conserve API budget

        # Knowledge Map
        self._status("Building knowledge map …")
        top_dirs = self._cloner.list_top_level_dirs()
        km = build_knowledge_map(result.people.stats, result.commits, top_dirs)
        if km.knowledge_silos:
            silos_text = "\n".join(f"- {s}" for s in km.knowledge_silos)
            km.pairing_suggestions = await self._ask_llm_list(
                f"Given these knowledge silos in {owner}/{repo}:\n{silos_text}\n\n"
                f"Contributors: {', '.join(km.contributors[:10])}\n"
                "Suggest 3-5 specific pairing recommendations to spread knowledge. "
                "Return a JSON array of strings, each a recommendation. "
                "Return ONLY the JSON array."
            )
        km.llm_summary = await self._ask_llm(
            f"Summarize the knowledge distribution in {owner}/{repo} in 2 sentences. "
            f"There are {len(km.contributors)} active contributors and {len(km.folders)} folders. "
            f"Knowledge silos: {len(km.knowledge_silos)}."
        )
        extended.knowledge_map = km

        # Dependency Scanner
        self._status("Scanning dependencies …")
        dep_report = build_dependency_report(self._cloner)
        if dep_report.dependencies:
            dep_report = await self._analyze_dependencies_llm(
                owner, repo, dep_report
            )
        extended.dependencies = dep_report

        # Review Culture (skip in low-API mode — fetches reviews per PR)
        if not low_api:
            self._status("Analyzing review culture …")
            review_report = await self._analyze_review_culture(
                owner, repo, result.pull_requests
            )
            extended.review_culture = review_report
        else:
            self._status("Skipping review culture (unauthenticated rate limit) …")

        # Stale Branches (skip in low-API mode — fetches branch comparisons)
        if not low_api:
            self._status("Scanning for stale branches …")
            stale_report = await self._analyze_stale_branches(owner, repo)
            extended.stale_branches = stale_report
        else:
            self._status("Skipping stale branches (unauthenticated rate limit) …")

        # Changelog
        self._status("Generating changelog …")
        changelog = build_changelog(result.commits, result.pull_requests)
        render_changelog_markdown(changelog)
        changelog.llm_summary = await self._ask_llm(
            f"Summarize this changelog for {owner}/{repo} in 2 sentences. "
            f"There are {len(changelog.entries)} entries."
        )
        extended.changelog = changelog

        # Bus Factor Mitigation
        self._status("Building bus factor mitigation plan …")
        mitigation = build_bus_mitigation(
            result.people.stats, result.commits,
            result.people.bus_factor,
        )
        if mitigation.risk_level in ("critical", "high"):
            mitigation = await self._analyze_mitigation_llm(
                owner, repo, mitigation
            )
        extended.bus_mitigation = mitigation

        # What-If Simulator
        self._status("Running what-if simulations …")
        what_if = build_what_if_report(
            result.people.stats, result.commits,
            result.pull_requests, result.issues,
            result.people.bus_factor, top_dirs,
        )
        what_if = await self._analyze_what_if_llm(owner, repo, what_if)
        extended.what_if = what_if

        # Time Machine (skip in low-API mode — fetches full historical data)
        if not low_api:
            self._status("Running time machine comparison …")
            time_machine = await self._run_time_machine(
                owner, repo, result, timeframe, since, until
            )
            extended.time_machine = time_machine
        else:
            self._status("Skipping time machine (unauthenticated rate limit) …")

        return extended

    # ── LLM sub-analyses ─────────────────────────────────────────────────

    async def _analyze_people_llm(
        self,
        owner: str,
        repo: str,
        stats: list,
        timeframe: Timeframe,
    ) -> list[ContributorInsight]:
        """Ask the LLM to provide insights on each contributor."""
        if not stats:
            return []

        stats_text = "\n".join(
            f"- @{s.login}: {s.commit_count} commits, +{s.lines_added}/-{s.lines_removed} lines, "
            f"{s.prs_opened} PRs ({s.prs_merged} merged), dirs: {', '.join(s.top_directories[:3])}"
            for s in stats[:20]
        )

        prompt = (
            f"You are analyzing contributors to {owner}/{repo} during {timeframe.label}.\n\n"
            f"Contributor stats:\n{stats_text}\n\n"
            "For EACH contributor listed, respond with a JSON array of objects with these keys:\n"
            '  "login", "inferred_role" (e.g. "Backend Engineer", "DevOps"), '
            '"activity_summary" (1 sentence), "judgment" (1 sentence assessment), '
            '"risk_notes" (any concerns, or empty string).\n\n'
            "Return ONLY the JSON array, no markdown fences."
        )

        raw = await self._ask_llm(prompt)
        return self._parse_contributor_insights(raw)

    def _parse_contributor_insights(self, raw: str) -> list[ContributorInsight]:
        """Parse JSON array of contributor insights from LLM response."""
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
        try:
            data = json.loads(text)
            return [ContributorInsight(**item) for item in data]
        except (json.JSONDecodeError, Exception):
            return [
                ContributorInsight(
                    login="(parse error)",
                    activity_summary=raw[:300],
                )
            ]

    async def _analyze_functional_llm(
        self,
        owner: str,
        repo: str,
        readme: str,
        repo_info: dict,
        areas: list,
        tree: str,
    ) -> FunctionalReport:
        """Use the LLM to generate a functional overview."""
        areas_text = "\n".join(
            f"- {a.name}/ — {a.description}" for a in areas
        )
        desc = repo_info.get("description", "") or ""
        topics = repo_info.get("topics", []) or []

        prompt = (
            f"You are analyzing the repository {owner}/{repo}.\n"
            f"Description: {desc}\n"
            f"Topics: {', '.join(topics)}\n\n"
            f"README (first 2000 chars):\n{readme[:2000]}\n\n"
            f"Directory tree:\n{tree[:3000]}\n\n"
            f"Functional areas identified:\n{areas_text}\n\n"
            "Provide a JSON object with these keys:\n"
            '  "repo_description": (2-3 sentence overview),\n'
            '  "tech_stack": (array of technology names),\n'
            '  "architecture_notes": (paragraph about architecture),\n'
            '  "area_improvements": (object mapping area name to improvement suggestions string),\n'
            '  "summary": (2-3 sentence summary)\n\n'
            "Return ONLY the JSON object, no markdown fences."
        )

        raw = await self._ask_llm(prompt)
        return self._parse_functional_report(raw, areas)

    def _parse_functional_report(
        self, raw: str, areas: list
    ) -> FunctionalReport:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
        try:
            data = json.loads(text)
            improvements = data.get("area_improvements", {})
            for area in areas:
                area.improvement_notes = improvements.get(area.name, "")
            return FunctionalReport(
                repo_description=data.get("repo_description", ""),
                tech_stack=data.get("tech_stack", []),
                areas=areas,
                architecture_notes=data.get("architecture_notes", ""),
                llm_summary=data.get("summary", ""),
            )
        except (json.JSONDecodeError, Exception):
            return FunctionalReport(
                repo_description=raw[:500],
                areas=areas,
                llm_summary="(Failed to parse LLM response)",
            )

    async def _analyze_code_llm(
        self,
        owner: str,
        repo: str,
        folder_analyses: list,
    ) -> CodeReport:
        """Analyze each folder for code quality and security issues."""
        all_findings: list[CodeFinding] = []

        for fa in folder_analyses:
            if fa.file_count == 0:
                continue
            self._status(f"Analyzing {fa.path}/ …")

            code_samples = gather_code_samples(self._cloner, fa.path)
            if not code_samples.strip():
                continue

            prompt = (
                f"You are a senior code reviewer analyzing the '{fa.path}/' directory "
                f"of {owner}/{repo}.\n"
                f"Languages: {', '.join(fa.languages)}\n"
                f"Files: {fa.file_count}, Lines: {fa.total_lines}\n\n"
                f"Code samples:\n{code_samples[:6000]}\n\n"
                "Identify code quality issues, refactoring opportunities, and security "
                "concerns. For each finding, provide a JSON array of objects:\n"
                '  "category": "security"|"refactoring"|"performance"|"style",\n'
                '  "severity": "critical"|"high"|"medium"|"low"|"info",\n'
                '  "title": short title,\n'
                '  "description": detailed explanation,\n'
                '  "suggestion": how to fix,\n'
                '  "file": relevant file path (if applicable, else "")\n\n'
                "Be specific and actionable. Return ONLY the JSON array, no markdown fences. "
                "If there are no findings, return an empty array []."
            )

            raw = await self._ask_llm(prompt)
            findings = self._parse_code_findings(raw, fa.path)
            fa.findings = findings
            all_findings.extend(findings)

            # Get overall notes for the folder
            fa.llm_notes = await self._ask_llm(
                f"In 1-2 sentences, summarize the code quality of '{fa.path}/' in {owner}/{repo}. "
                f"Found {len(findings)} issues."
            )

        security_count = sum(1 for f in all_findings if f.category == "security")
        refactor_count = sum(1 for f in all_findings if f.category == "refactoring")

        summary = await self._ask_llm(
            f"Summarize the code analysis of {owner}/{repo} in 2-3 sentences. "
            f"Total findings: {len(all_findings)} ({security_count} security, "
            f"{refactor_count} refactoring). Folders analyzed: {len(folder_analyses)}."
        )

        return CodeReport(
            folders=folder_analyses,
            total_findings=len(all_findings),
            security_findings=security_count,
            refactoring_findings=refactor_count,
            llm_summary=summary,
        )

    def _parse_code_findings(self, raw: str, folder: str) -> list[CodeFinding]:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
        try:
            data = json.loads(text)
            findings = []
            for i, item in enumerate(data):
                findings.append(
                    CodeFinding(
                        id=f"{folder}-{i+1}",
                        folder=folder,
                        file=item.get("file", ""),
                        category=item.get("category", "style"),
                        severity=SeverityLevel(item.get("severity", "medium")),
                        title=item.get("title", "Untitled"),
                        description=item.get("description", ""),
                        suggestion=item.get("suggestion", ""),
                    )
                )
            return findings
        except (json.JSONDecodeError, ValueError, Exception):
            return []

    # ── Extended LLM helpers ──────────────────────────────────────────────

    async def _ask_llm_list(self, prompt: str) -> list[str]:
        """Ask the LLM and parse a JSON array of strings."""
        raw = await self._ask_llm(prompt)
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [str(item) for item in data]
        except (json.JSONDecodeError, Exception):
            pass
        return [raw[:300]] if raw else []

    async def _analyze_dependencies_llm(
        self, owner: str, repo: str, report: DependencyReport
    ) -> DependencyReport:
        """Use LLM to assess dependency risks."""
        deps_text = "\n".join(
            f"- {d.name} {d.version} ({d.ecosystem}, from {d.source_file})"
            for d in report.dependencies[:40]
        )
        prompt = (
            f"Analyze the dependencies of {owner}/{repo}:\n\n{deps_text}\n\n"
            "Provide a JSON object with:\n"
            '  "risk_notes": object mapping package_name to a short risk note '
            "(outdated, abandoned, license concern, etc. — empty string if fine),\n"
            '  "summary": 2-3 sentence overall assessment.\n\n'
            "Return ONLY the JSON object, no markdown fences."
        )
        raw = await self._ask_llm(prompt)
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
        try:
            data = json.loads(text)
            risk_notes = data.get("risk_notes", {})
            for dep in report.dependencies:
                dep.risk_notes = risk_notes.get(dep.name, "")
            report.llm_summary = data.get("summary", "")
        except (json.JSONDecodeError, Exception):
            report.llm_summary = raw[:300]
        return report

    async def _analyze_review_culture(
        self, owner: str, repo: str, prs: list
    ) -> ReviewCultureReport:
        """Fetch review data and build review culture report."""
        reviews_by_pr: dict[int, list[dict]] = {}
        # Fetch reviews for recent PRs (limit to 20 for performance)
        for pr in prs[:20]:
            try:
                reviews = await self._fetcher.fetch_pr_reviews(
                    owner, repo, pr.number
                )
                reviews_by_pr[pr.number] = reviews
            except Exception:
                pass

        report = build_review_culture(prs, reviews_by_pr)

        if report.reviewers:
            reviewers_text = "\n".join(
                f"- @{r.login}: {r.reviews_given} reviews, "
                f"avg {r.avg_review_time_hours}h, "
                f"{r.approvals} approvals, {r.rejections} rejections"
                for r in report.reviewers[:10]
            )
            report.llm_summary = await self._ask_llm(
                f"Analyze the review culture of {owner}/{repo}:\n\n"
                f"Total PRs reviewed: {report.total_prs_reviewed}\n"
                f"Avg time to first review: {report.avg_time_to_first_review_hours}h\n"
                f"Bottleneck reviewers: {', '.join(report.bottleneck_reviewers) or 'none'}\n\n"
                f"Reviewer breakdown:\n{reviewers_text}\n\n"
                "In 3-4 sentences, assess the health of the review process and "
                "suggest improvements."
            )
        return report

    async def _analyze_stale_branches(
        self, owner: str, repo: str
    ) -> StaleBranchReport:
        """Fetch branch data and build stale branch report."""
        try:
            branches = await self._fetcher.fetch_branches(owner, repo)
            default_branch = await self._fetcher.fetch_default_branch(owner, repo)
        except Exception:
            return StaleBranchReport()

        # Compare each non-default branch (limit to 30 for performance)
        compare_data: dict[str, dict] = {}
        non_default = [b for b in branches if b.get("name") != default_branch]
        for branch in non_default[:30]:
            name = branch.get("name", "")
            try:
                cmp = await self._fetcher.fetch_branch_compare(
                    owner, repo, default_branch, name
                )
                compare_data[name] = cmp
            except Exception:
                pass

        report = build_stale_branch_report(
            branches, default_branch, compare_data
        )

        if report.stale_branches:
            branches_text = "\n".join(
                f"- {b.name}: {b.days_stale}d stale, {b.category}, {b.ahead_behind}"
                for b in report.stale_branches[:10]
            )
            report.llm_summary = await self._ask_llm(
                f"Summarize the branch hygiene of {owner}/{repo}:\n"
                f"Total branches: {report.total_branches}\n"
                f"Stale branches: {len(report.stale_branches)}\n"
                f"Cleanup candidates: {report.cleanup_candidates}\n\n"
                f"Stale branches:\n{branches_text}\n\n"
                "In 2-3 sentences, assess the branch cleanup situation."
            )
        return report

    async def _analyze_mitigation_llm(
        self, owner: str, repo: str, report: BusFactorMitigationReport
    ) -> BusFactorMitigationReport:
        """Generate LLM-powered mitigation actions."""
        monopolists_text = ", ".join(f"@{m}" for m in report.knowledge_monopolists)
        exclusive_text = "\n".join(
            f"- @{login}: {len(files)} exclusive files (e.g. {', '.join(files[:3])})"
            for login, files in list(report.exclusive_files.items())[:5]
        )

        prompt = (
            f"The repository {owner}/{repo} has a bus factor of {report.bus_factor} "
            f"(risk: {report.risk_level}).\n\n"
            f"Knowledge monopolists: {monopolists_text}\n\n"
            f"Exclusive file ownership:\n{exclusive_text}\n\n"
            "Generate a JSON object with:\n"
            '  "actions": array of objects with keys "priority" (1-5), "action" (string), '
            '"target_contributor" (login), "target_area" (folder/area), "rationale" (string).\n'
            '  "summary": 2-3 sentence mitigation plan.\n\n'
            "Return ONLY the JSON object, no markdown fences."
        )
        raw = await self._ask_llm(prompt)
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
        try:
            from repo_inspector.models import MitigationAction
            data = json.loads(text)
            report.actions = [
                MitigationAction(**a) for a in data.get("actions", [])
            ]
            report.llm_summary = data.get("summary", "")
        except (json.JSONDecodeError, Exception):
            report.llm_summary = raw[:300]
        return report

    async def _analyze_what_if_llm(
        self, owner: str, repo: str, report: WhatIfReport
    ) -> WhatIfReport:
        """Generate LLM summaries for what-if scenarios."""
        scenarios_text = ""
        for s in report.scenarios:
            scenarios_text += (
                f"\n- Scenario: {s.scenario} ({s.parameter})\n"
                f"  Bus factor: {s.bus_factor_before} → {s.bus_factor_after}\n"
                f"  Orphaned files: {len(s.orphaned_files)}\n"
                f"  Affected areas: {', '.join(s.affected_areas[:5])}\n"
            )

        prompt = (
            f"Analyze these what-if scenarios for {owner}/{repo}:\n{scenarios_text}\n\n"
            "For each scenario, provide a 1-2 sentence impact summary. "
            "Return a JSON object with:\n"
            '  "impact_summaries": object mapping "scenario_type:parameter" to impact string,\n'
            '  "summary": 2-3 sentence overall risk assessment.\n\n'
            "Return ONLY the JSON object, no markdown fences."
        )
        raw = await self._ask_llm(prompt)
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
        try:
            data = json.loads(text)
            summaries = data.get("impact_summaries", {})
            for s in report.scenarios:
                key = f"{s.scenario}:{s.parameter}"
                s.impact_summary = summaries.get(key, "")
            report.llm_summary = data.get("summary", "")
        except (json.JSONDecodeError, Exception):
            report.llm_summary = raw[:300]
        return report

    async def _run_time_machine(
        self,
        owner: str,
        repo: str,
        current_result: InspectionResult,
        timeframe: Timeframe,
        since: datetime,
        until: datetime,
    ) -> TimeMachineReport:
        """Compare current timeframe with the previous period of same length."""
        period_days = (until - since).days
        old_until = since
        old_since = old_until - timedelta(days=period_days)
        old_timeframe = Timeframe(since=old_since, until=old_until)

        # Fetch old period data
        try:
            old_commits = await self._fetcher.fetch_commits(
                owner, repo, old_since, old_until
            )
            old_prs = await self._fetcher.fetch_pull_requests(
                owner, repo, old_since, old_until
            )
            old_issues = await self._fetcher.fetch_issues(
                owner, repo, old_since
            )
        except Exception:
            return TimeMachineReport(
                old_timeframe=old_timeframe,
                new_timeframe=timeframe,
                llm_summary="Could not fetch historical data for comparison.",
            )

        old_stats = compute_contributor_stats(old_commits, old_prs, old_issues)
        old_bus = compute_bus_factor(old_stats)

        report = build_time_comparison(
            old_stats=old_stats,
            new_stats=current_result.people.stats,
            old_timeframe=old_timeframe,
            new_timeframe=timeframe,
            old_bus_factor=old_bus,
            new_bus_factor=current_result.people.bus_factor,
            old_finding_count=0,  # We don't re-run code analysis for old period
            new_finding_count=current_result.code.total_findings,
        )

        deltas_text = "\n".join(
            f"- {d.metric}: {d.old_value} → {d.new_value} ({d.change})"
            for d in report.deltas
        )
        report.llm_summary = await self._ask_llm(
            f"Compare two periods for {owner}/{repo}:\n"
            f"Old: {old_timeframe.label}\n"
            f"New: {timeframe.label}\n\n"
            f"Deltas:\n{deltas_text}\n\n"
            f"Joined: {', '.join(report.contributor_churn[:5]) or 'none'}\n"
            f"Departed: {', '.join(report.contributor_departed[:5]) or 'none'}\n\n"
            "In 3-4 sentences, summarize the evolution and highlight trends."
        )
        return report
