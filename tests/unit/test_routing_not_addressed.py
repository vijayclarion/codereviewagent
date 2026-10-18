"""T028 - `not_addressed` is inert (FR-016, SC-006).

The single most important negative guarantee in the feature. A pull request
routinely implements only part of a story; if that produced comments or failures
the agent would be noise on every partial PR, which is most of them.
"""

import pytest

from review_agent import diff_builder, output_layer
from review_agent.models import (
    ChangedFile,
    CodeIssue,
    CoverageEntry,
    PullRequestContext,
    ReviewableSet,
    ReviewReport,
    WorkItem,
)


def _reviewable():
    diff, line_map, changed = diff_builder.build_file_diff(
        "src/Cart.cs", "a\nb\n", "a\nb\nc\n"
    )
    return ReviewableSet(
        reviewed=(
            ChangedFile(
                path="src/Cart.cs", diff=diff, line_map=line_map, changed_lines=changed
            ),
        )
    )


def _report(**kw):
    defaults = dict(summary="s", coverage=(), checklist_violations=(), code_issues=())
    defaults.update(kw)
    return ReviewReport(**defaults)


ALL_NOT_ADDRESSED = (
    CoverageEntry(criterion="first criterion", status="not_addressed", evidence="none", ordinal=1),
    CoverageEntry(criterion="second criterion", status="not_addressed", evidence="none", ordinal=2),
)


def test_not_addressed_produces_no_inline_comments():
    inline, summary_only = output_layer.build_inline_comments(
        _report(coverage=ALL_NOT_ADDRESSED), _reviewable(), diff_builder.map_line
    )
    assert inline == []
    assert summary_only == []


def test_not_addressed_never_blocks():
    assert _report(coverage=ALL_NOT_ADDRESSED).has_blocking_findings is False


def test_not_addressed_still_appears_in_the_coverage_map():
    summary = output_layer.render_summary(
        _report(coverage=ALL_NOT_ADDRESSED),
        (WorkItem(id=101, title="Story"),),
        PullRequestContext(pr_id=1, iteration_id=1),
        _reviewable(),
    )
    assert "first criterion" in summary
    assert "not addressed" in summary


def test_the_summary_explains_that_not_addressed_is_neutral():
    summary = output_layer.render_summary(
        _report(coverage=ALL_NOT_ADDRESSED),
        (WorkItem(id=101),),
        PullRequestContext(pr_id=1, iteration_id=1),
        _reviewable(),
    )
    assert "neutral" in summary.lower()
    assert "not defects" in summary.lower()


def test_contradiction_does_produce_a_finding():
    """The contrast that makes the guarantee meaningful."""
    coverage = (
        CoverageEntry(criterion="the cart must never go negative",
                      status="possible_contradiction", evidence="it can", ordinal=1),
    )
    report = _report(coverage=coverage)
    assert report.has_blocking_findings is True
    _, summary_only = output_layer.build_inline_comments(
        report, _reviewable(), diff_builder.map_line
    )
    assert len(summary_only) == 1, "no location, so it belongs in the summary"


@pytest.mark.parametrize(
    "severity,blocking", [("high", True), ("medium", False), ("low", False)]
)
def test_only_high_severity_issues_block(severity, blocking):
    report = _report(code_issues=(CodeIssue(severity=severity, issue="x"),))
    assert report.has_blocking_findings is blocking


def test_a_clean_report_does_not_block():
    coverage = (
        CoverageEntry(criterion="c", status="appears_addressed", evidence="yes", ordinal=1),
    )
    assert _report(coverage=coverage).has_blocking_findings is False
