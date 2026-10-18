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
