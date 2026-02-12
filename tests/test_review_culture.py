"""Tests for the review culture analysis module."""

from datetime import datetime, timezone

import pytest

from repo_inspector.analysis.review_culture import build_review_culture
from repo_inspector.models import PullRequest


@pytest.fixture
def rc_prs():
    return [
        PullRequest(
            number=1, title="Add auth", author="alice",
            created_at=datetime(2025, 1, 10, 10, 0, tzinfo=timezone.utc),
            merged_at=datetime(2025, 1, 12, tzinfo=timezone.utc),
            url="https://github.com/o/r/pull/1",
        ),
        PullRequest(
            number=2, title="Fix bug", author="bob",
            created_at=datetime(2025, 1, 11, 8, 0, tzinfo=timezone.utc),
            url="https://github.com/o/r/pull/2",
        ),
        PullRequest(
            number=3, title="Update docs", author="alice",
            created_at=datetime(2025, 1, 12, 12, 0, tzinfo=timezone.utc),
            url="https://github.com/o/r/pull/3",
        ),
    ]


@pytest.fixture
def rc_reviews():
    return {
        1: [
            {
                "user": {"login": "bob"},
                "state": "APPROVED",
                "submitted_at": "2025-01-10T14:00:00Z",
            },
        ],
        2: [
            {
                "user": {"login": "alice"},
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2025-01-11T12:00:00Z",
            },
            {
                "user": {"login": "alice"},
                "state": "APPROVED",
                "submitted_at": "2025-01-11T16:00:00Z",
            },
        ],
        # PR #3 has no reviews
    }


class TestBuildReviewCulture:
    def test_total_prs_reviewed(self, rc_prs, rc_reviews):
        report = build_review_culture(rc_prs, rc_reviews)
        assert report.total_prs_reviewed == 2  # PR 1 and 2 have reviews

    def test_reviewer_stats(self, rc_prs, rc_reviews):
        report = build_review_culture(rc_prs, rc_reviews)
        alice_r = next((r for r in report.reviewers if r.login == "alice"), None)
        assert alice_r is not None
        assert alice_r.reviews_given == 2
        assert alice_r.approvals == 1
        assert alice_r.rejections == 1

    def test_bob_reviewer(self, rc_prs, rc_reviews):
        report = build_review_culture(rc_prs, rc_reviews)
        bob_r = next((r for r in report.reviewers if r.login == "bob"), None)
        assert bob_r is not None
        assert bob_r.reviews_given == 1
        assert bob_r.approvals == 1

    def test_time_to_first_review(self, rc_prs, rc_reviews):
        report = build_review_culture(rc_prs, rc_reviews)
        assert report.avg_time_to_first_review_hours > 0

    def test_bottleneck_detection(self, rc_prs, rc_reviews):
        report = build_review_culture(rc_prs, rc_reviews)
        # alice has 2/3 reviews = 66% > 40% threshold
        assert "alice" in report.bottleneck_reviewers

    def test_review_pairs(self, rc_prs, rc_reviews):
        report = build_review_culture(rc_prs, rc_reviews)
        assert len(report.review_pairs) > 0

    def test_empty_reviews(self, rc_prs):
        report = build_review_culture(rc_prs, {})
        assert report.total_prs_reviewed == 0
        assert len(report.reviewers) == 0

    def test_reviewed_authors_tracked(self, rc_prs, rc_reviews):
        report = build_review_culture(rc_prs, rc_reviews)
        alice_r = next(r for r in report.reviewers if r.login == "alice")
        assert "bob" in alice_r.reviewed_authors
