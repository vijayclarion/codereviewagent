"""Feature 007 - the two repeats the live re-run on sample PR #3 posted (T090).

Run 1 posted 6 inline comments; run 2, against the unchanged pull request,
suppressed 5 and posted 2 more. The texts below are the provider's own, from
those two runs. Fixes approved by the requester:

1. A finding reported summary-only carries a hidden marker in the summary, so
   a later run that anchors it recognises it.
2. Checklist findings in the same file are also matched on their wording, so
   citing a different rule for the same problem is recognised.
"""

from review_agent import output_layer
from review_agent.dedupe import read_prior_feedback
from review_agent.diff_builder import build_file_diff, map_line
from review_agent.models import (
    ChangedFile,
    ChecklistViolation,
    CoverageEntry,
    FalseCoverageClaim,
    PullRequestContext,
    ReviewableSet,
    ReviewReport,
)

CTX = PullRequestContext(pr_id=3, iteration_id=2, platform="github")
CART = "src/eShop.Api/Models/Cart.cs"
CRITERION = "The cart total is recalculated with the coupon discount applied before the cart is saved."
CLAIM = "The cart total is recalculated with the coupon discount applied before the cart is saved"

RUN1_TESTS = (
    "New coupon-application logic that changes the financial cart total (`ApplyCoupon`) and the "
    "changed `Save` contract are not accompanied by any unit tests in the diff."
)
RUN2_TESTS = (
    "New coupon-storage and coupon-discount behaviour (Cart.ApplyCoupon, CartController coupon "
    "handling, ICartRepository.Save signature change) has no accompanying test changes in the diff."
)


def _reviewable():
    before = "".join(f"line {i}\n" for i in range(1, 31))
    after = before.replace("line 22\n", "line 22\nadded 23\nadded 24\nadded 25\n")
    diff, line_map, changed = build_file_diff(CART, before, after)
    return ReviewableSet(reviewed=(ChangedFile("/" + CART, diff=diff, line_map=line_map, changed_lines=changed),))


def _coverage():
    return (CoverageEntry(CRITERION, "possible_contradiction", "applied after save", ordinal=3, work_item_id=2),)


def _prior_from(plan):
    """What the next run reads back: the summary and every inline comment posted."""
    threads = [{"id": 1, "threadContext": None, "comments": [{"id": 1, "content": plan.summary_markdown}]}]
    for index, comment in enumerate(plan.inline, start=2):
        threads.append({"id": index, "threadContext": {"filePath": "/" + comment.path.lstrip("/")},
                        "comments": [{"id": index, "content": comment.markdown}]})

    class _Platform:
        def get_threads(self):
            return threads

    return read_prior_feedback(_Platform())


def _plan(report, prior=None):
    return output_layer.build_plan(report, (), CTX, _reviewable(), map_line, prior)


def test_a_summary_only_finding_is_not_reposted_once_it_gains_a_location():
    unlocated = FalseCoverageClaim(CRITERION, CLAIM, "possible_contradiction", "after save")
    run1 = _plan(ReviewReport(coverage=_coverage(), false_coverage_claims=(unlocated,)))
    assert not any(c.kind == "false-coverage" for c in run1.inline)
    assert "<!-- ai-review:false-coverage:" in run1.summary_markdown  # the hidden marker

    located = FalseCoverageClaim(CRITERION, CLAIM, "possible_contradiction", "after save", file=CART, line=23)
    run2 = _plan(ReviewReport(coverage=_coverage(), false_coverage_claims=(located,)), _prior_from(run1))
    assert [c.kind for c in run2.inline] == []
    assert [c.kind for c in run2.suppressed] == ["false-coverage"]


def test_the_hidden_markers_do_not_disturb_the_summary_identity():
    unlocated = FalseCoverageClaim(CRITERION, CLAIM, "possible_contradiction", "after save")
    plan = _plan(ReviewReport(coverage=_coverage(), false_coverage_claims=(unlocated,)))
    prior = _prior_from(plan)
    assert prior.summary_thread_id == 1 and prior.summary_comment_id == 1
    assert plan.summary_markdown.rstrip().endswith("`ai-review:summary`")


def test_the_same_checklist_problem_under_a_different_rule_is_recognised():
    first = ChecklistViolation(
        item="Create Unit Tests for critical parts of the application business using XUnit + NCrunch",
        rule_id="NFR:unit-tests-xunit", source="Non Functional Requirements Checklist v2.0.xlsx",
        issue=RUN1_TESTS, file=CART, line=24,
    )
    second = ChecklistViolation(
        item="Create unit tests", rule_id="NFR:create-unit-tests",
        source="Non Functional Requirements Checklist v2.0.xlsx",
        issue=RUN2_TESTS, file=CART, line=23,
    )
    run1 = _plan(ReviewReport(checklist_violations=(first,)))
    assert len(run1.inline) == 1
    run2 = _plan(ReviewReport(checklist_violations=(second,)), _prior_from(run1))
    assert run2.inline == () and len(run2.suppressed) == 1


def test_a_genuinely_different_checklist_violation_in_the_same_file_is_still_posted():
    tests = ChecklistViolation(item="Create unit tests", rule_id="NFR:tests", issue=RUN1_TESTS, file=CART, line=24)
    clock = ChecklistViolation(
        item="Deterministic Time Handling", rule_id="DEV-STD-06",
        issue="CouponAppliedAt is assigned DateTime.Now instead of an injected UTC clock.",
        file=CART, line=23,
    )
    run1 = _plan(ReviewReport(checklist_violations=(tests,)))
    run2 = _plan(ReviewReport(checklist_violations=(clock,)), _prior_from(run1))
    assert [c.kind for c in run2.inline] == ["checklist"]


# -- Attempt 5: the same defect under a different kind -------------------------

CONTROLLER = "src/eShop.Api/Controllers/CartController.cs"
INTERFACES = "src/eShop.Api/Services/Interfaces.cs"
CROSS_FILE_TEXT = (
    "`ICartRepository.Save` signature was changed from `Save(Cart cart)` to "
    "`Save(Cart cart, string appliedCouponCode)`, but `CartController.cs` still calls "
    "`_carts.Save(cart);` with the old single-argument form, which will not compile against "
    "the new interface."
)
CODE_TEXT = (
    "`_carts.Save(cart);` is still called with a single argument even though "
    "`ICartRepository.Save` now requires `Save(Cart cart, string appliedCouponCode)` - this "
    "will not compile."
)


def _reviewable_two():
    def one(path, n):
        before = "".join(f"line {i}\n" for i in range(1, 80))
        after = before.replace(f"line {n}\n", f"line {n}\nadded\n")
        diff, line_map, changed = build_file_diff(path, before, after)
        return ChangedFile("/" + path, diff=diff, line_map=line_map, changed_lines=changed)

    return ReviewableSet(reviewed=(one(INTERFACES, 7), one(CONTROLLER, 69)))


def test_a_code_issue_restating_a_posted_cross_file_issue_is_recognised():
    from review_agent.models import CodeIssue, CrossFileIssue

    cross = CrossFileIssue("high", CROSS_FILE_TEXT, files=("/" + INTERFACES, "/" + CONTROLLER),
                           file=INTERFACES, line=8)
    run1 = output_layer.build_plan(ReviewReport(cross_file_issues=(cross,)), (), CTX,
                                   _reviewable_two(), map_line)
    assert [c.kind for c in run1.inline] == ["cross-file"]
    assert run1.inline[0].path.endswith("Interfaces.cs")

    code = CodeIssue("high", CODE_TEXT, file=CONTROLLER, line=70)
    run2 = output_layer.build_plan(ReviewReport(code_issues=(code,)), (), CTX,
                                   _reviewable_two(), map_line, _prior_from(run1))
    assert run2.inline == () and [c.kind for c in run2.suppressed] == ["code"]


def test_a_code_issue_in_a_file_the_cross_file_issue_does_not_name_is_still_posted():
    from review_agent.models import CodeIssue, CrossFileIssue

    cross = CrossFileIssue("high", CROSS_FILE_TEXT, files=("/" + INTERFACES, "/other/Unrelated.cs"),
                           file=INTERFACES, line=8)
    run1 = output_layer.build_plan(ReviewReport(cross_file_issues=(cross,)), (), CTX,
                                   _reviewable_two(), map_line)
    code = CodeIssue("high", CODE_TEXT, file=CONTROLLER, line=70)
    run2 = output_layer.build_plan(ReviewReport(code_issues=(code,)), (), CTX,
                                   _reviewable_two(), map_line, _prior_from(run1))
    assert [c.kind for c in run2.inline] == ["code"]


# -- Attempt 6: the same cross-file issue, anchored on its other file ----------


def test_a_cross_file_issue_anchored_on_another_of_its_files_is_recognised():
    from review_agent.models import CrossFileIssue

    files = ("/" + INTERFACES, "/" + CONTROLLER)
    on_interface = CrossFileIssue("high", CROSS_FILE_TEXT, files=files, file=INTERFACES, line=8)
    run1 = output_layer.build_plan(ReviewReport(cross_file_issues=(on_interface,)), (), CTX,
                                   _reviewable_two(), map_line)
    assert run1.inline[0].path.endswith("Interfaces.cs")

    on_controller = CrossFileIssue("high", "Reworded: the controller still calls Save(cart).",
                                   files=files, file=CONTROLLER, line=70)
    run2 = output_layer.build_plan(ReviewReport(cross_file_issues=(on_controller,)), (), CTX,
                                   _reviewable_two(), map_line, _prior_from(run1))
    assert run2.inline == () and [c.kind for c in run2.suppressed] == ["cross-file"]


# -- Same-commit guard (approved after attempt 7) -------------------------------

HEX_HEAD = "f204814" + "0" * 33


def test_a_rerun_of_a_reviewed_commit_posts_nothing_new_and_lists_it_in_the_summary():
    from review_agent.models import CodeIssue

    ctx = PullRequestContext(pr_id=3, iteration_id=2, platform="github").with_iteration(2, HEX_HEAD, "b" * 40)
    first = CodeIssue("low", "Magic number for the discount percentage.", file=CART, line=23)
    run1 = output_layer.build_plan(ReviewReport(code_issues=(first,)), (), ctx, _reviewable(), map_line)
    assert len(run1.inline) == 1
    assert f"<!-- ai-review:commit:{HEX_HEAD} -->" in run1.summary_markdown

    new = CodeIssue("low", "CouponCode is duplicated on CartItem with no apparent use.", file=CART, line=24)
    run2 = output_layer.build_plan(ReviewReport(code_issues=(first, new)), (), ctx, _reviewable(), map_line,
                                   _prior_from(run1))
    assert run2.inline == ()
    assert [c.body.splitlines()[-1] for c in run2.held] == ["CouponCode is duplicated on CartItem with no apparent use."]
    assert "### New on this re-review (not posted inline)" in run2.summary_markdown
    assert "CouponCode is duplicated on CartItem" in run2.summary_markdown


def test_a_new_commit_is_reviewed_and_commented_normally():
    from review_agent.models import CodeIssue

    old = PullRequestContext(pr_id=3, iteration_id=2).with_iteration(2, HEX_HEAD, "b" * 40)
    new_head = PullRequestContext(pr_id=3, iteration_id=3).with_iteration(3, "a" * 40, "b" * 40)
    first = CodeIssue("low", "Magic number for the discount percentage.", file=CART, line=23)
    run1 = output_layer.build_plan(ReviewReport(code_issues=(first,)), (), old, _reviewable(), map_line)
    new = CodeIssue("low", "CouponCode is duplicated on CartItem with no apparent use.", file=CART, line=24)
    run2 = output_layer.build_plan(ReviewReport(code_issues=(first, new)), (), new_head, _reviewable(), map_line,
                                   _prior_from(run1))
    assert len(run2.inline) == 1 and run2.held == ()


def test_a_non_hex_commit_records_no_marker():
    ctx = PullRequestContext(pr_id=1).with_iteration(1, "head-not-a-sha", "")
    assert output_layer.reviewed_commit_marker(ctx) == ""
