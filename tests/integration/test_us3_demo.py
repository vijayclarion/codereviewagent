"""T051 - the self-contained demonstration, asserted (US3, SC-006, SC-007).

The one collected test in this file runs the operator-facing demonstration and
checks what `demo.md` claims about it. A demonstration whose claims are not
asserted anywhere decays into fiction between one feature and the next, which is
how feature 002's walkthrough came to describe a checklist path that resolved
nothing.
"""

import pytest

from tests.demo import run as demo


@pytest.fixture
def perform(monkeypatch, tmp_path):
    def _perform(threads=None, dry_run=True, workspace=None):
        return demo.perform(
            monkeypatch,
            str(workspace or tmp_path),
            threads=threads,
            dry_run=dry_run,
        )

    return _perform


# -- SC-006: the same inputs produce the same findings ----------------------


def test_two_runs_from_a_clean_start_produce_identical_findings(perform, tmp_path):
    """A difference between two runs of this is a defect, not a curiosity."""
    first, _, _ = perform(workspace=tmp_path / "one")
    second, _, _ = perform(workspace=tmp_path / "two")
    assert demo.findings_of(first) == demo.findings_of(second)


def test_the_inventory_does_not_follow_filesystem_order(perform):
    report, _, _ = perform()
    filenames = [document.filename for document in report.inventory.documents]
    assert filenames == sorted(filenames)


# -- the five checkpoint questions of contracts/demonstration.md ------------


def test_checkpoint_1_a_working_copy_was_obtained_and_its_reference_stated(perform):
    report, _, _ = perform()
    source = report.inventory.source
    assert source.available
    assert source.ref and source.commit


def test_checkpoint_2_both_formats_contributed_rules(perform):
    report, _, _ = perform()
    read = {d.filename: d for d in report.inventory.documents if d.status == "read"}
    assert any(name.endswith(".xlsx") for name in read)
    assert any(name.endswith(".docx") for name in read)
    assert all(document.rule_count > 0 for document in read.values())


def test_checkpoint_3_every_document_found_is_accounted_for(perform):
    report, _, _ = perform()
    assert len(report.inventory.documents) == 4
    for document in report.inventory.documents:
        assert document.rule_count or document.skip_reason or document.status == "no_rules"


def test_checkpoint_4_the_linked_story_was_read_and_judged(perform):
    report, _, _ = perform()
    assert report.inventory.work_items == (4101,)
    assert report.inventory.criteria_judged == 6


def test_checkpoint_5_a_finding_cites_a_rule_and_a_document(perform):
    report, _, _ = perform()
    cited = [v for v in report.checklist_violations if v.rule_id and v.source]
    assert cited
    assert any(v.source.endswith(".docx") for v in cited)
    assert any(v.source.endswith(".xlsx") for v in cited)


# -- what each deliberate fault produces (faults.md) ------------------------


def test_a_rule_with_its_own_identifier_is_cited_verbatim(perform):
    report, _, _ = perform()
    assert "SEC-WEB-01" in {v.rule_id for v in report.checklist_violations}


def test_a_rule_with_no_identifier_of_its_own_is_still_citable(perform):
    """The NFR spreadsheet's `#` column is present and empty in every row."""
    report, _, _ = perform()
    derived = [v for v in report.checklist_violations if v.source.startswith("Najm-NFR")]
    assert derived, "the derived-identifier rule must still produce a citable finding"
    assert derived[0].rule_id.startswith("Najm-NFR-Checklist:")


def test_the_unclaimed_unimplemented_criterion_is_not_a_defect(perform):
    """Criterion 6 - outside this change's scope, and never reported as a fault."""
    report, _, _ = perform()
    sixth = next(c for c in report.coverage if c.ordinal == 6)
    assert sixth.status == "not_addressed"
    assert not any("remove" in claim.criterion.lower() for claim in report.false_coverage_claims)


def test_the_claimed_unimplemented_criterion_is_the_headline(perform):
    """Criterion 4 - claimed as covered, not implemented."""
    report, _, _ = perform()
    assert len(report.false_coverage_claims) == 1
    assert "Stock limit" in report.false_coverage_claims[0].claimed_text


def test_an_invented_citation_is_reported_and_not_posted(perform):
    report, client, _ = perform()
    assert report.dropped_citations == ("SEC-WEB-99",)
    assert not any("SEC-WEB-99" in content for _k, content, _c in client.writes)


def test_the_unreadable_document_costs_only_itself(perform):
    report, _, _ = perform()
    skipped = [d for d in report.inventory.documents if d.status == "skipped"]
    assert len(skipped) == 1
    assert skipped[0].skip_reason
    assert report.inventory.rules_applied == 7


def test_the_checklist_documents_are_never_reviewed_as_code(perform):
    """FR-018: the standard is what a review measures against."""
    report, _, prompts = perform()
    assert ".xlsx" not in prompts[0].split("## Diff")[1]


def test_no_credential_appears_in_anything_the_run_produced(perform, capsys):
    """SC-008, the part a machine can check."""
    report, client, prompts = perform(dry_run=False)
    written = "".join(content for _k, content, _c in client.writes)
    everything = written + "".join(prompts) + capsys.readouterr().out
    for secret in ("not-a-real-token-value", "not-a-real-posting-token", "not-a-real-api-key"):
        assert secret not in everything


# -- SC-007: the second run --------------------------------------------------


def test_the_second_posting_run_adds_no_comment(perform, tmp_path):
    """What the live run must also show. Here it is asserted every time."""
    _, first, _ = perform(dry_run=False, workspace=tmp_path / "first")
    posted = [w for w in first.writes if w[0] == "create_thread" and w[2] is not None]
    assert posted, "the first run must post something for this to mean anything"

    _, second, _ = perform(
        threads=first.threads_for_next_run(),
        dry_run=False,
        workspace=tmp_path / "second",
    )
    repeated = [w for w in second.writes if w[0] == "create_thread" and w[2] is not None]
    assert repeated == [], "a second run must not repeat a comment the reviewer has seen"


def test_the_second_run_updates_the_one_summary_rather_than_adding_another(perform, tmp_path):
    _, first, _ = perform(dry_run=False, workspace=tmp_path / "first")
    _, second, _ = perform(
        threads=first.threads_for_next_run(), dry_run=False, workspace=tmp_path / "second"
    )
    assert not [w for w in second.writes if w[0] == "create_thread" and w[2] is None]
    assert [w for w in second.writes if w[0] in ("update_comment", "add_comment")]
