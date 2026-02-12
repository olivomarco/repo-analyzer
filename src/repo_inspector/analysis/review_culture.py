"""Review Culture Analyzer — PR review pattern analysis."""

from collections import defaultdict
from datetime import datetime

from repo_inspector.models import PullRequest, ReviewCultureReport, ReviewerStats


def build_review_culture(
    prs: list[PullRequest],
    reviews_by_pr: dict[int, list[dict]],
) -> ReviewCultureReport:
    """Analyze PR review patterns from fetched review data.

    Args:
        prs: List of pull requests in the timeframe.
        reviews_by_pr: Mapping of PR number -> list of review dicts from GitHub API.
    """
    reviewer_data: dict[str, dict] = defaultdict(
        lambda: {
            "reviews_given": 0,
            "total_review_hours": 0.0,
            "total_comments": 0,
            "approvals": 0,
            "rejections": 0,
            "reviewed_authors": set(),
        }
    )

    total_reviewed = 0
    first_review_hours: list[float] = []

    for pr in prs:
        reviews = reviews_by_pr.get(pr.number, [])
        if not reviews:
            continue
        total_reviewed += 1

        # Find time-to-first-review
        review_times: list[datetime] = []
        for r in reviews:
            submitted = r.get("submitted_at")
            if submitted:
                try:
                    dt = datetime.fromisoformat(submitted.replace("Z", "+00:00"))
                    review_times.append(dt)
                except (ValueError, TypeError):
                    pass

            reviewer_login = r.get("user", {}).get("login", "unknown")
            state = r.get("state", "").upper()

            reviewer_data[reviewer_login]["reviews_given"] += 1
            reviewer_data[reviewer_login]["reviewed_authors"].add(pr.author)

            if state == "APPROVED":
                reviewer_data[reviewer_login]["approvals"] += 1
            elif state in ("CHANGES_REQUESTED", "REQUEST_CHANGES"):
                reviewer_data[reviewer_login]["rejections"] += 1

        if review_times:
            earliest_review = min(review_times)
            delta_hours = (earliest_review - pr.created_at).total_seconds() / 3600
            if delta_hours >= 0:
                first_review_hours.append(delta_hours)
                for r in reviews:
                    reviewer_login = r.get("user", {}).get("login", "unknown")
                    reviewer_data[reviewer_login]["total_review_hours"] += delta_hours

    # Build reviewer stats
    reviewer_stats: list[ReviewerStats] = []
    for login, data in sorted(reviewer_data.items(), key=lambda x: -x[1]["reviews_given"]):
        avg_hours = (
            data["total_review_hours"] / data["reviews_given"]
            if data["reviews_given"] > 0
            else 0.0
        )
        reviewer_stats.append(
            ReviewerStats(
                login=login,
                reviews_given=data["reviews_given"],
                avg_review_time_hours=round(avg_hours, 1),
                approvals=data["approvals"],
                rejections=data["rejections"],
                reviewed_authors=sorted(data["reviewed_authors"]),
            )
        )

    # Identify bottleneck reviewers (> 40% of all reviews)
    total_reviews = sum(r.reviews_given for r in reviewer_stats)
    bottlenecks = [
        r.login
        for r in reviewer_stats
        if total_reviews > 0 and r.reviews_given / total_reviews > 0.4
    ]

    # Identify frequent review pairs
    pairs: list[str] = []
    for rs in reviewer_stats[:5]:
        for author in rs.reviewed_authors[:3]:
            if author != rs.login:
                pairs.append(f"@{rs.login} → @{author}")

    avg_first = (
        round(sum(first_review_hours) / len(first_review_hours), 1)
        if first_review_hours
        else 0.0
    )

    return ReviewCultureReport(
        total_prs_reviewed=total_reviewed,
        avg_time_to_first_review_hours=avg_first,
        reviewers=reviewer_stats,
        bottleneck_reviewers=bottlenecks,
        review_pairs=pairs[:10],
    )
