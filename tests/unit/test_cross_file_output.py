"""T048 (feature 007) - cross-file issues on the pull request."""

from review_agent import output_layer
from review_agent.dedupe import read_prior_feedback
from review_agent.diff_builder import build_file_diff, map_line
from review_agent.models import ChangedFile, CrossFileIssue, PullRequestContext, ReviewableSet, ReviewReport

CTX = PullRequestContext(pr_id=12, iteration_id=1)


def _reviewable():
    before = "".join(f"line {i}\n" for i in range(1, 11))
    after = before.replace("line 5\n", "line 5 changed\n")
    diff, line_map, changed = build_file_diff("src/b.cs", before, after)
    return ReviewableSet(reviewed=(ChangedFile("/src/b.cs", diff=diff, line_map=line_map, changed_lines=changed),))


def _report(*issues):
    return ReviewReport(cross_file_issues=issues)


def test_anchored_issue_goes_inline_with_every_file_named():
    issue = CrossFileIssue("high", "caller not updated", files=("src/a.cs", "src/b.cs"), file="src/b.cs", line=5)
    inline, summary_only = output_layer.build_inline_comments(_report(issue), _reviewable(), map_line)
    (comment,) = inline
    assert comment.kind == "cross-file" and comment.right_line == 5
    assert "`src/a.cs`" in comment.markdown and "`src/b.cs`" in comment.markdown
    assert "ai-review:cross-file:" in comment.markdown
    assert summary_only == []


def test_unanchored_issue_is_summary_only():
    issue = CrossFileIssue("medium", "config key missing", files=("src/a.cs", "appsettings.json"))
    inline, summary_only = output_layer.build_inline_comments(_report(issue), _reviewable(), map_line)
    assert inline == [] and len(summary_only) == 1


def test_summary_always_has_the_section():
    empty = output_layer.render_summary(ReviewReport(), (), CTX)
    assert "### Cross-file issues (0)\n\nNone found." in empty
    issue = CrossFileIssue("high", "caller not updated", files=("src/a.cs", "src/b.cs"))
    full = output_layer.render_summary(_report(issue), (), CTX)
    assert "### Cross-file issues (1)" in full
    assert "- **high** — caller not updated\n  Files: `src/a.cs`, `src/b.cs`" in full


def test_identity_survives_rewording_so_a_rerun_suppresses_it():
    first = CrossFileIssue("high", "caller not updated", files=("src/a.cs", "src/b.cs"), file="src/b.cs", line=5)
    plan = output_layer.build_plan(_report(first), (), CTX, _reviewable(), map_line)
    (posted,) = plan.inline

    class _Client:
        def get_threads(self):
            return [{"id": 1, "threadContext": {"filePath": "/src/b.cs"},
                     "comments": [{"id": 1, "content": posted.markdown}]}]

    prior = read_prior_feedback(_Client())
    reworded = CrossFileIssue("low", "the controller still uses the old signature",
                              files=("src/b.cs", "/src/A.cs"), file="src/b.cs", line=5)
    again = output_layer.build_plan(_report(reworded), (), CTX, _reviewable(), map_line, prior)
    assert again.inline == () and len(again.suppressed) == 1
