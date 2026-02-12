"""Time Machine — compare two analysis timeframes."""

from repo_inspector.models import (
    ContributorStats,
    TimeComparisonDelta,
    Timeframe,
    TimeMachineReport,
)


def build_time_comparison(
    old_stats: list[ContributorStats],
    new_stats: list[ContributorStats],
    old_timeframe: Timeframe,
    new_timeframe: Timeframe,
    old_bus_factor: int,
    new_bus_factor: int,
    old_finding_count: int,
    new_finding_count: int,
) -> TimeMachineReport:
    """Compare two analysis periods and surface deltas."""
    old_logins = {s.login for s in old_stats}
    new_logins = {s.login for s in new_stats}

    joined = sorted(new_logins - old_logins)
    departed = sorted(old_logins - new_logins)

    old_commits = sum(s.commit_count for s in old_stats)
    new_commits = sum(s.commit_count for s in new_stats)

    deltas: list[TimeComparisonDelta] = []

    # Commit volume
    commit_pct = (
        f"{((new_commits - old_commits) / old_commits * 100):+.0f}%"
        if old_commits > 0
        else "N/A"
    )
    deltas.append(
        TimeComparisonDelta(
            metric="Commit Volume",
            old_value=old_commits,
            new_value=new_commits,
            change=commit_pct,
        )
    )

    # Contributor count
    deltas.append(
        TimeComparisonDelta(
            metric="Contributors",
            old_value=len(old_stats),
            new_value=len(new_stats),
            change=f"{len(new_stats) - len(old_stats):+d}",
        )
    )

    # Bus factor
    deltas.append(
        TimeComparisonDelta(
            metric="Bus Factor",
            old_value=old_bus_factor,
            new_value=new_bus_factor,
            change=f"{new_bus_factor - old_bus_factor:+d}",
        )
    )

    # Lines changed
    old_lines = sum(s.lines_added + s.lines_removed for s in old_stats)
    new_lines = sum(s.lines_added + s.lines_removed for s in new_stats)
    deltas.append(
        TimeComparisonDelta(
            metric="Lines Changed",
            old_value=old_lines,
            new_value=new_lines,
            change=f"{new_lines - old_lines:+d}",
        )
    )

    # Findings
    deltas.append(
        TimeComparisonDelta(
            metric="Code Findings",
            old_value=old_finding_count,
            new_value=new_finding_count,
            change=f"{new_finding_count - old_finding_count:+d}",
        )
    )

    # Churn
    deltas.append(
        TimeComparisonDelta(
            metric="Contributors Joined",
            old_value=0,
            new_value=len(joined),
            change=f"+{len(joined)}",
        )
    )
    deltas.append(
        TimeComparisonDelta(
            metric="Contributors Departed",
            old_value=0,
            new_value=len(departed),
            change=f"-{len(departed)}",
        )
    )

    return TimeMachineReport(
        old_timeframe=old_timeframe,
        new_timeframe=new_timeframe,
        contributor_churn=joined,
        contributor_departed=departed,
        bus_factor_old=old_bus_factor,
        bus_factor_new=new_bus_factor,
        commit_count_old=old_commits,
        commit_count_new=new_commits,
        findings_old=old_finding_count,
        findings_new=new_finding_count,
        deltas=deltas,
    )
