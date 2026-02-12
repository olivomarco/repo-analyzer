# Copilot Instructions for Repo Inspector

## Project Overview

This project is a TUI tool called `repo-inspector` that inspects any GitHub repository using the GitHub Copilot SDK. It produces analysis across multiple categories:

1. **People** — Contributor statistics (deterministic + LLM-powered insights)
2. **Functional** — Repository overview, functional areas, and improvement suggestions
3. **Code & Security** — Folder-level code quality, refactoring opportunities, and security findings
4. **Time Machine** — Historical comparison between two time periods
5. **Knowledge Map** — Contributor × Folder heatmap showing who knows what
6. **Dependencies** — Dependency risk scanning across ecosystems
7. **Review Culture** — PR review patterns, bottleneck reviewers, review pairs
8. **Stale Branches** — Abandoned branch detection and cleanup recommendations
9. **Changelog** — Auto-generated changelog from commits and PRs
10. **Bus Factor Mitigation** — Actionable plans to reduce bus factor risk
11. **What-If Simulator** — Impact simulation for contributor departure or module deprecation

## Architecture

- **TUI Framework**: Textual for full-featured terminal UI
- **GitHub Integration**: httpx for GitHub REST API data fetching + GitPython for local clone
- **AI Engine**: GitHub Copilot SDK (`github-copilot-sdk`) for all LLM-powered analysis
- **Data Models**: Pydantic v2 for structured data

## Code Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep functions focused and single-purpose
- Use Pydantic models for data structures

## Project Structure

```
src/
  repo_inspector/
    __init__.py
    cli.py              # CLI entry point (loads .env, launches TUI)
    app.py              # Textual TUI application
    models.py           # Pydantic data models (core + extended)
    fetcher.py          # GitHub REST API data fetching (SAML-aware)
    cloner.py           # Git clone + local file + dependency detection
    analyzer.py         # Copilot SDK analysis orchestrator
    analysis/           # Analysis modules
      __init__.py
      people.py         # Deterministic contributor stats
      functional.py     # Functional area identification
      code.py           # Code quality folder analysis
      knowledge_map.py  # Contributor × folder heatmap
      dependencies.py   # Dependency risk scanning
      review_culture.py # PR review pattern analysis
      stale_branches.py # Abandoned branch detection
      changelog.py      # Auto-generated changelog
      bus_mitigation.py # Bus factor mitigation plans
      what_if.py        # What-if scenario simulation
      time_machine.py   # Historical period comparison
    screens/            # Textual TUI screens
      __init__.py
      home.py           # Repo + timeframe input
      loading.py        # Progress display
      results.py        # Tabbed results (11 tabs)
      issue.py          # Issue creation with LLM pre-fill
tests/
  conftest.py
  test_models.py
  test_fetcher.py
  test_generator.py         # People analysis tests
  test_cli.py
  test_knowledge_map.py     # Knowledge map tests
  test_changelog.py         # Changelog tests
  test_review_culture.py    # Review culture tests
  test_stale_branches.py    # Stale branch tests
  test_bus_mitigation.py    # Bus factor mitigation tests
  test_what_if.py           # What-if simulator tests
  test_time_machine.py      # Time machine tests
```

## Key User Flow

1. User runs `repo-inspector` → TUI launches
2. Home screen: Enter repo (owner/repo) and timeframe (default 1 month)
3. Loading screen: Fetches GitHub data, clones repo, runs LLM analysis
4. Results screen: Eleven tabs — People, Functional, Code & Security, Time Machine, Knowledge Map, Dependencies, Reviews, Stale Branches, Changelog, Bus Factor, What-If
5. From Code tab: Create GitHub issue pre-filled with findings

## Features

- Deterministic contributor stats (commits, lines, PRs, issues, directories)
- LLM-powered contributor role inference and activity judgments
- Bus factor calculation
- Functional area discovery from repo structure
- Per-folder code quality and security analysis via Copilot SDK
- GitHub issue creation from TUI with LLM-drafted content
- Knowledge map heatmap (contributor × folder) with silo detection
- Dependency risk scanning across Python, npm, Rust, Go, Ruby ecosystems
- PR review culture analysis (bottleneck reviewers, review times, pairs)
- Stale branch detection with categorization (orphan, wip, abandoned)
- Auto-generated changelog from commits and merged PRs
- Bus factor mitigation plans with LLM-generated actions
- What-if simulator for contributor departure and module deprecation
- Time machine for comparing two analysis periods
- SAML-aware GitHub API client (auto-fallback for SAML-protected orgs)
- `.env` file support for GITHUB_TOKEN via python-dotenv
- Beautiful, consistent output format

## Testing

- Use pytest for all tests
- Mock GitHub API calls with respx
- Test deterministic logic thoroughly (people stats, bus factor)
- Use fixtures for common test data

## Dependencies

- `textual` for TUI
- `rich` for terminal formatting
- `httpx` for HTTP
- `pydantic` for data validation
- `python-dotenv` for `.env` file loading
- `github-copilot-sdk` for Copilot LLM integration
- `gitpython` for repo cloning
- `humanize` for human-readable formatting
- `pytest` for testing
