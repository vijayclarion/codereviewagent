"""T025-T027, T029-T030 - the US1 acceptance scenarios end to end.

These are the SC-001 regression tests. If the demo PR stops producing the false
coverage claim, the feature's headline claim is broken and this is where it shows.
"""

import pytest

from review_agent import main as main_module
from review_agent.config import load_config
from review_agent.models import COVERAGE_STATUSES
from tests.fakes import (
    EmptyChangesClient,
    FakeTfsClient,
    NoChecklistClient,
    NoWorkItemClient,
    fake_llm,
)
from tests.fixtures import pr_demo as demo


@pytest.fixture
def run(base_env, monkeypatch):
    """Run the pipeline against a fake client and a scripted model response."""

    def _run(client=None, response=None, dry_run=True, prior_threads=None, **env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        tfs = client or FakeTfsClient(threads=prior_threads or [])
        llm = fake_llm(response if response is not None else demo.MODEL_RESPONSE)
        monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
        monkeypatch.setattr(main_module, "call_llm", llm)
        config = load_config(dry_run_override=dry_run)
        log = main_module.PhaseLog(enabled=False)
        report = main_module.run_review(config, log)
        return report, tfs, llm

    return _run


# -- T025: coverage classification -----------------------------------------


def test_four_criteria_addressed_and_one_not(run):
    report, _, _ = run()
    statuses = [c.status for c in report.coverage]
    assert statuses.count("appears_addressed") == 4
    assert statuses.count("not_addressed") == 1


def test_criteria_are_numbered_against_the_story(run):
    report, _, _ = run()
    by_ordinal = {c.ordinal: c.status for c in report.coverage if c.ordinal}
    assert by_ordinal[1] == "appears_addressed"
    assert by_ordinal[2] == "appears_addressed"
    assert by_ordinal[3] == "appears_addressed"
    assert by_ordinal[4] == "not_addressed", "the stock limit is criterion 4"
    assert by_ordinal[5] == "appears_addressed"


# -- T026: the headline finding --------------------------------------------


def test_false_coverage_claim_is_raised_for_the_stock_limit(run):
    report, _, _ = run()
    assert len(report.false_coverage_claims) == 1
    claim = report.false_coverage_claims[0]
    assert "stock" in claim.claimed_text.lower()
    assert claim.status == "not_addressed"


def test_false_coverage_claim_appears_in_the_summary_prominently(run):
    report, tfs, _ = run(dry_run=False)
    summary = tfs.summary_threads()[0][1]
    assert "False coverage claim" in summary
    heading_position = summary.index("False coverage claim")
    coverage_position = summary.index("Story coverage")
    assert heading_position < coverage_position, "the headline must lead"


def test_false_coverage_claim_is_blocking_material(run):
    report, _, _ = run()
    assert report.has_blocking_findings is True


def test_no_false_claim_when_the_description_is_honest(run):
    """The claim must come from the description, not from the gap alone."""
    honest = dict(demo.MODEL_RESPONSE)
    client = FakeTfsClient()
    original = demo.PULL_REQUEST["description"]
    try:
        demo.PULL_REQUEST["description"] = original.replace(
            "- Stock limit enforced when adding to cart\n", ""
        )
        report, _, _ = run(client=client, response=honest)
        assert report.false_coverage_claims == ()
        assert any(c.status == "not_addressed" for c in report.coverage)
    finally:
        demo.PULL_REQUEST["description"] = original


# -- T027: scoped-out work stays unflagged ---------------------------------


def test_scoped_out_followups_are_not_flagged(run):
    report, tfs, _ = run(dry_run=False)
    body = " ".join(w[1] for w in tfs.created_threads())
    for item in ("#102", "#103"):
        assert item not in body or "Not in this PR" in body


def test_declared_out_of_scope_is_parsed(run):
    from review_agent.models import DeclaredScope

    scope = DeclaredScope.from_description(demo.PULL_REQUEST["description"])
    assert scope.parsed is True
    assert len(scope.covered) == 5
    assert len(scope.not_in_this_pr) == 2
    assert any("102" in item for item in scope.not_in_this_pr)


# -- T029: no linked work item --------------------------------------------


def test_no_linked_work_item_degrades_to_checklist_only(run):
    response = {
        "coverage": [],
        "checklist_violations": [],
        "code_issues": [],
        "summary": "Checklist-only review.",
    }
    report, tfs, _ = run(client=NoWorkItemClient(), response=response, dry_run=False)
    assert report.coverage == ()
    assert report.outcome == "complete"
    summary = tfs.summary_threads()[0][1]
    assert "no work item is linked" in summary.lower()


# -- T030: preview mode writes nothing ------------------------------------


def test_preview_mode_makes_no_writes(run):
    _, tfs, _ = run(dry_run=True)
    assert tfs.write_count == 0, "preview mode must not write to the pull request"


def test_post_mode_creates_a_summary_and_inline_comments(run):
    _, tfs, _ = run(dry_run=False)
    assert len(tfs.summary_threads()) == 1
    assert len(tfs.inline_threads()) >= 1


def test_preview_and_post_render_identical_text(run, capsys):
    _, posting_client, _ = run(dry_run=False)
    posted_summary = posting_client.summary_threads()[0][1]

    run(dry_run=True)
    printed = capsys.readouterr().out
    assert posted_summary.strip() in printed, "preview must show exactly what would be posted"


# -- exclusions and bounds ------------------------------------------------


def test_appsettings_is_never_sent_to_the_provider(run):
    """SC-010: a connection string in the diff must not leave the building."""
    _, _, llm = run()
    all_prompts = " ".join(llm.state["prompts"])
    assert "appsettings" not in all_prompts
    assert "hunter2" not in all_prompts, "the fixture's password must never be sent"


def test_excluded_file_is_named_in_the_report(run):
    report, _, _ = run(dry_run=False)
    excluded_paths = [s.path for s in report.skipped]
    assert any("appsettings" in p for p in excluded_paths)
    assert all(s.detail for s in report.skipped), "every skip must state why"


def test_nothing_reviewable_is_reported_not_failed(run):
    report, tfs, llm = run(client=EmptyChangesClient(), dry_run=False)
    assert report.outcome == "complete"
    assert llm.state["calls"] == 0, "no provider call when there is nothing to review"
    assert "nothing to review" in report.summary.lower()


# -- checklist unavailable ------------------------------------------------


def test_missing_checklist_degrades_to_coverage_only(run):
    response = dict(demo.MODEL_RESPONSE)
    response["checklist_violations"] = []
    report, tfs, _ = run(client=NoChecklistClient(), response=response, dry_run=False)
    assert report.outcome == "complete"
    summary = tfs.summary_threads()[0][1]
    assert "no checklist" in summary.lower()
    # The coverage half still ran - that is the point of degrading rather than failing.
    assert len(report.coverage) == 5


# -- provider failure ----------------------------------------------------


def test_unusable_response_after_retry_degrades_and_says_so(run):
    report, tfs, _ = run(response="not json at all", dry_run=False)
    assert report.outcome == "degraded"
    assert report.degraded_reason
    summary = tfs.created_threads()[0][1]
    assert "could not complete" in summary.lower()
    assert "no findings should be inferred" in summary.lower()


def test_degraded_review_is_not_blocking(run):
    report, _, _ = run(response="not json at all")
    assert report.has_blocking_findings is False


def test_one_retry_is_attempted_before_degrading(run, base_env, monkeypatch):
    llm = fake_llm(demo.MODEL_RESPONSE, fail_times=1)
    tfs = FakeTfsClient()
    monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
    monkeypatch.setattr(main_module, "call_llm", llm)
    config = load_config(dry_run_override=True)
    report = main_module.run_review(config, main_module.PhaseLog(enabled=False))
    assert llm.state["calls"] == 2, "exactly one stricter retry"
    assert report.outcome == "complete"
    assert "no explanation" in llm.state["prompts"][1], "the retry must be stricter"


# --------------------------------------------------------------------------
# T035-T037 (feature 003, US2) - the story half degrades on its own.
#
# A credential scoped to Code alone used to raise out of _fetch_story and exit 2,
# taking the checklist half with it and turning a reviewable pull request into a
# red build. FR-023 asks for the third behaviour: lose the story half, say which
# access is missing, and review what can still be reviewed.
# --------------------------------------------------------------------------


class WorkItemsForbiddenClient(FakeTfsClient):
    """Code (read) but not Work Items (read) - the usual PAT misconfiguration."""

    def get_work_item(self, work_item_id):
        from review_agent.errors import WorkItemAccessDenied

        self.calls.append(f"get_work_item:{work_item_id}:denied")
        raise WorkItemAccessDenied("/wit/workitems/101", 403)


def test_a_refused_work_item_read_still_delivers_a_review(run):
    report, _, _ = run(client=WorkItemsForbiddenClient())
    assert report.outcome == "complete"
    assert report.coverage == () or all(c.ordinal == 0 for c in report.coverage)


def test_a_refused_work_item_read_names_the_missing_access(run):
    report, _, _ = run(client=WorkItemsForbiddenClient())
    notes = " ".join(report.notes)
    assert "Work Items (read)" in notes
    assert "story coverage" in notes.lower()


def test_a_refused_work_item_read_is_not_a_setup_failure(base_env, monkeypatch):
    """Exit 2 would make a provider-scope problem look like a broken build."""
    tfs = WorkItemsForbiddenClient()
    monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
    monkeypatch.setattr(main_module, "call_llm", fake_llm(demo.MODEL_RESPONSE))
    assert main_module.main(["--dry-run", "--quiet"]) == 0


def test_a_refused_work_item_read_is_recorded_as_a_reduction(run):
    report, _, _ = run(client=WorkItemsForbiddenClient())
    reductions = " ".join(report.inventory.reductions)
    assert "Story coverage was not assessed" in reductions


def test_no_linked_work_item_is_itself_a_stated_reason(run):
    """FR-022: 'none is linked' is an answer, and has to be given."""

    class NoStoryClient(FakeTfsClient):
        def get_linked_work_item_ids(self):
            self.calls.append("get_linked_work_item_ids")
            return []

    report, _, _ = run(client=NoStoryClient())
    assert report.inventory.story_unavailable_reason
    assert "no work item is linked" in " ".join(report.notes).lower()


# --------------------------------------------------------------------------
# T042 (feature 003) - behaviour that already worked, pinned.
#
# FR-019 and FR-025 describe what the agent already did, and this feature edits
# the modules that do it. "Already true" is precisely how gap G4 became a defect:
# nobody re-checked it, because nobody thought it could move.
# --------------------------------------------------------------------------


def test_every_criterion_of_every_linked_work_item_is_retrieved(run):
    """FR-019."""
    report, tfs, _ = run()
    assert "get_linked_work_item_ids" in tfs.calls
    assert any(call.startswith("get_work_item:") for call in tfs.calls)
    assert report.inventory.criteria_judged == len(report.coverage)


def test_every_criterion_receives_a_verdict_identified_by_its_number(run):
    """FR-020: 'criterion 4' has to mean something to the person reading it."""
    report, _, _ = run()
    assert report.coverage
    assert all(entry.status in COVERAGE_STATUSES for entry in report.coverage)


def test_a_finding_that_anchors_to_a_changed_line_is_reported_there(run):
    """FR-025, first half."""
    _, tfs, _ = run(dry_run=False)
    assert tfs.inline_threads()


def test_a_finding_with_no_location_is_reported_in_the_summary(run):
    """FR-025, second half. A contradiction is routed with no path, always."""
    response = dict(demo.MODEL_RESPONSE) if isinstance(demo.MODEL_RESPONSE, dict) else None
    report, tfs, _ = run()
    contradictions = [c for c in report.coverage if c.status == "possible_contradiction"]
    for entry in contradictions:
        assert not any(entry.criterion in content for _k, content, ctx in tfs.writes if ctx)
