"""T004 (feature 007) - the platform-neutral and cross-file vocabulary."""

import pytest

from review_agent.models import (
    ChangedFile,
    ChangeEntry,
    CodeIssue,
    CrossFileIssue,
    PullRequestContext,
    ReviewReport,
    Revision,
)


def test_change_entry_requires_a_path_and_a_known_type():
    entry = ChangeEntry("/src/a.cs", "rename", previous_path="/src/b.cs")
    assert entry.previous_path == "/src/b.cs"
    with pytest.raises(ValueError):
        ChangeEntry("", "edit")
    with pytest.raises(ValueError):
        ChangeEntry("/a", "modified")


def test_revision_defaults_are_empty():
    assert Revision() == Revision(0, "", "")


def test_cross_file_issue_names_two_distinct_files():
    issue = CrossFileIssue("high", "caller not updated", files=("a.cs", "b.cs"))
    assert issue.files == ("a.cs", "b.cs")
    with pytest.raises(ValueError):
        CrossFileIssue("high", "x", files=("a.cs",))
    with pytest.raises(ValueError):
        # The same file twice, spelled two ways, is still one file.
        CrossFileIssue("high", "x", files=("/A.cs", "a.cs"))
    with pytest.raises(ValueError):
        CrossFileIssue("urgent", "x", files=("a.cs", "b.cs"))
    with pytest.raises(ValueError):
        CrossFileIssue("low", "  ", files=("a.cs", "b.cs"))


def _github_payload(**overrides):
    payload = {
        "number": 12,
        "title": "Add coupon",
        "body": "Closes #7",
        "draft": False,
        "head": {"ref": "demo/cart", "sha": "h" * 40, "repo": {"full_name": "o/r"}},
        "base": {"ref": "master", "sha": "b" * 40, "repo": {"full_name": "o/r"}},
    }
    payload.update(overrides)
    return payload


def test_pull_request_context_from_github():
    ctx = PullRequestContext.from_github(12, _github_payload())
    assert (ctx.pr_id, ctx.title, ctx.description) == (12, "Add coupon", "Closes #7")
    assert (ctx.source_branch, ctx.target_branch) == ("demo/cart", "master")
    assert ctx.platform == "github"
    assert not ctx.is_draft and not ctx.is_fork


def test_pull_request_context_detects_draft_and_fork():
    fork = _github_payload(
        draft=True,
        head={"ref": "x", "sha": "h", "repo": {"full_name": "someone/r"}},
    )
    ctx = PullRequestContext.from_github(3, fork)
    assert ctx.is_draft and ctx.is_fork

    deleted_fork = _github_payload(head={"ref": "x", "sha": "h", "repo": None})
    assert PullRequestContext.from_github(3, deleted_fork).is_fork


def test_tfs_context_is_unchanged_by_default():
    ctx = PullRequestContext.from_payload(1, {"title": "t"})
    assert ctx.platform == "tfs" and not ctx.is_draft and not ctx.is_fork


def test_changed_file_content_is_not_part_of_identity():
    a = ChangedFile("/a.cs", diff="d", content="one")
    b = ChangedFile("/a.cs", diff="d", content="two")
    assert a == b
    assert "one" not in repr(a)


def test_report_defaults_and_blocking():
    report = ReviewReport()
    assert report.cross_file_issues == ()
    assert report.synthesis == "not needed"
    assert not report.has_blocking_findings

    low = CrossFileIssue("low", "x", files=("a", "b"))
    high = CrossFileIssue("high", "x", files=("a", "b"))
    assert not ReviewReport(cross_file_issues=(low,)).has_blocking_findings
    assert ReviewReport(cross_file_issues=(high,)).has_blocking_findings
    # Unchanged: a high code issue still blocks on its own.
    assert ReviewReport(code_issues=(CodeIssue("high", "x"),)).has_blocking_findings
