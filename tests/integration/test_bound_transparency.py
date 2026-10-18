"""T087-T088 - SC-011 and SC-007: truncation is visible, citations are real.

An unreviewed file that reads as reviewed-and-clean is worse than an obvious gap,
because it converts an absence of evidence into false confidence.
"""

from review_agent import output_layer, selection
from review_agent.models import (
    ChangedFile,
    Checklist,
    ChecklistFile,
    ChangeSet,
    ChecklistViolation,
    PullRequestContext,
    ReviewReport,
    WorkItem,
)


class _Cfg:
    review_exclude_patterns = ("*.dll",)
    review_max_files = 3
    review_max_diff_lines = 3000


def _files(count=10):
    return tuple(
        ChangedFile(path=f"src/File{i:02d}.cs", diff=f"diff {i}", changed_lines=10)
        for i in range(count)
    )


def _report_from(reviewable):
    return ReviewReport(
        summary="s",
        skipped=reviewable.excluded,
        unreviewed=reviewable.unreviewed,
    )


# -- SC-011 ----------------------------------------------------------------


def test_every_unreviewed_file_is_named():
    reviewable = selection.select_reviewable(ChangeSet(files=_files(10)), _Cfg())
    assert len(reviewable.reviewed) == 3
    assert len(reviewable.unreviewed) == 7

    summary = output_layer.render_summary(
        _report_from(reviewable), (), PullRequestContext(pr_id=1, iteration_id=1), reviewable
    )
    for skipped in reviewable.unreviewed:
        assert skipped.path in summary, f"{skipped.path} is unreviewed but unnamed"


def test_no_unreviewed_file_is_presented_as_clean():
    reviewable = selection.select_reviewable(ChangeSet(files=_files(10)), _Cfg())
    summary = output_layer.render_summary(
        _report_from(reviewable), (), PullRequestContext(pr_id=1, iteration_id=1), reviewable
    )
    section = summary[summary.index("Not sent for review") :]
    for skipped in reviewable.unreviewed:
        assert skipped.path in section
    assert "bound" in section


def test_the_reviewed_count_is_stated_honestly():
    reviewable = selection.select_reviewable(ChangeSet(files=_files(10)), _Cfg())
    summary = output_layer.render_summary(
        _report_from(reviewable), (), PullRequestContext(pr_id=1, iteration_id=1), reviewable
    )
    assert "3 of 10 changed files" in summary


def test_the_reason_distinguishes_a_bound_from_an_exclusion():
    files = _files(5) + (ChangedFile(path="src/App.dll", diff="d", changed_lines=1),)
    reviewable = selection.select_reviewable(ChangeSet(files=files), _Cfg())
    reasons = {s.reason for s in reviewable.excluded} | {
        s.reason for s in reviewable.unreviewed
    }
    assert reasons == {"excluded", "bound"}


def test_within_the_bound_nothing_is_reported_as_unreviewed():
    reviewable = selection.select_reviewable(ChangeSet(files=_files(2)), _Cfg())
    assert reviewable.unreviewed == ()
    summary = output_layer.render_summary(
        _report_from(reviewable), (), PullRequestContext(pr_id=1, iteration_id=1), reviewable
    )
    assert "Not sent for review" not in summary


# -- SC-007 ----------------------------------------------------------------


def _checklist():
    sources = (
        ChecklistFile(
            filename="code-review-checklist.md",
            path="/code-review-checklist.md",
            content="- Business rules from the story are enforced in code.\n"
            "- Input is validated before use.\n",
        ),
        ChecklistFile(
            filename="security-checklist.md",
            path="/security-checklist.md",
            content="- No secret appears in committed configuration.\n",
        ),
    )
    from review_agent.checklist import combine

    return Checklist(sources=sources, combined_markdown=combine(sources), available=True)


def test_a_violation_cites_a_file_that_exists_in_the_checklist():
    checklist = _checklist()
    violation = ChecklistViolation(
        item="Business rules from the story are enforced in code.",
        source="code-review-checklist.md",
        issue="no stock check",
        file="a.cs",
        line=1,
    )
    assert violation.source in checklist.filenames


def test_a_violation_item_traces_to_real_checklist_text():
    checklist = _checklist()
    violation = ChecklistViolation(
        item="Business rules from the story are enforced in code.",
        source="code-review-checklist.md",
    )
    source = next(s for s in checklist.sources if s.filename == violation.source)
    assert violation.item.rstrip(".") in source.content


def test_the_combined_checklist_labels_every_source_so_citation_is_possible():
    combined = _checklist().combined_markdown
    for filename in ("code-review-checklist.md", "security-checklist.md"):
        assert f"## From: {filename}" in combined


def test_a_violation_without_a_source_still_renders_rather_than_crashing():
    """Robustness: a model that omits `source` must not break the report."""
    report = ReviewReport(
        summary="s",
        checklist_violations=(ChecklistViolation(item="some rule", issue="broken"),),
    )
    summary = output_layer.render_summary(
        report, (WorkItem(id=1),), PullRequestContext(pr_id=1, iteration_id=1)
    )
    assert "some rule" in summary
    assert "checklist" in summary.lower()
