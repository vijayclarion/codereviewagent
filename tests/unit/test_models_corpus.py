"""T008 - the corpus entities and the invariants that forbid a silent outcome.

Every assertion here is a condition under which this project has already shipped a
review that looked clean and was not. The invariants are the mechanism; these are
the cases they exist for.
"""

import pytest

from review_agent.models import (
    ChecklistDocument,
    ChecklistItem,
    ChecklistSource,
    CombinedChecklist,
    RunInventory,
)


def item(item_id="R-1", title="Validate input", **kwargs):
    return ChecklistItem(item_id=item_id, title=title, **kwargs)


# -- ChecklistSource --------------------------------------------------------


def test_an_unavailable_source_must_say_why():
    with pytest.raises(ValueError, match="must carry a reason"):
        ChecklistSource(available=False)


def test_an_available_source_must_name_its_repository():
    with pytest.raises(ValueError, match="must name its repository"):
        ChecklistSource(available=True)


def test_an_available_source_describes_repo_ref_and_commit():
    source = ChecklistSource(repo="CodeReviewChecklist", ref="master", commit="a1b2c3d", available=True)
    assert source.description == "CodeReviewChecklist@master (a1b2c3d)"


def test_an_unavailable_source_describes_the_reason():
    source = ChecklistSource(unavailable_reason="no repository was configured")
    assert "not applied" in source.description
    assert "no repository was configured" in source.description


def test_the_source_records_which_setting_named_it():
    """FR-001: an operator has to be able to tell which of four names was used."""
    source = ChecklistSource(
        repo="X", available=True, setting="TFS_REPO_CODE_REVIEW_CodeReviewChecklist"
    )
    assert source.setting == "TFS_REPO_CODE_REVIEW_CodeReviewChecklist"


# -- CombinedChecklist ------------------------------------------------------


def test_a_corpus_with_no_rules_must_say_why():
    with pytest.raises(ValueError, match="must carry a reason"):
        CombinedChecklist()


def test_a_corpus_that_omitted_rules_must_state_the_basis():
    with pytest.raises(ValueError, match="no stated basis"):
        CombinedChecklist(items=(item(),), dropped_for_budget=(item("R-2", "Other"),))


def test_a_rule_cannot_be_both_applied_and_omitted():
    with pytest.raises(ValueError, match="applied and omitted"):
        CombinedChecklist(
            items=(item(),),
            dropped_for_budget=(item(),),
            selection_basis="relevance to the changed files",
        )


def test_prompt_text_groups_by_document_and_leads_with_the_identifier():
    corpus = CombinedChecklist(
        items=(
            item("SEC-WEB-01", "No SQL concatenation", detail="Parameterise", documents=("Std.docx",)),
            item("API-02", "Validate identifiers", documents=("Api.xlsx",), severity="HIGH"),
        )
    )
    text = corpus.prompt_text
    assert "## From: Std.docx" in text
    assert "- [SEC-WEB-01] No SQL concatenation - Parameterise" in text
    assert "- [API-02] Validate identifiers (severity: HIGH)" in text


def test_an_empty_corpus_is_unavailable_but_constructible_with_a_reason():
    corpus = CombinedChecklist(unavailable_reason="the repository could not be reached")
    assert not corpus.available
    assert corpus.rule_count == 0


# -- RunInventory -----------------------------------------------------------


def inventory(**kwargs):
    defaults = dict(story_unavailable_reason="no work item is linked")
    defaults.update(kwargs)
    return RunInventory(**defaults)


def test_the_inventory_must_balance():
    with pytest.raises(ValueError, match="does not balance"):
        inventory(rules_read=10, rules_applied=4, rules_omitted=4)


def test_omitting_rules_requires_a_basis():
    with pytest.raises(ValueError, match="no stated basis"):
        inventory(rules_read=10, rules_applied=6, rules_omitted=4)


def test_no_work_items_requires_a_reason():
    """FR-022: 'none is linked' is itself a reason and has to be stated."""
    with pytest.raises(ValueError, match="must be stated"):
        RunInventory()


def test_reductions_are_derived_not_supplied():
    """A caller cannot forget to mention a reduction, because it cannot supply them."""
    with pytest.raises(TypeError):
        RunInventory(reductions=("something",))


def test_every_reduction_condition_produces_a_sentence():
    record = inventory(
        source=ChecklistSource(unavailable_reason="no repository was configured"),
        documents=(
            ChecklistDocument(filename="Bad.xlsx", status="skipped", skip_reason="corrupt"),
            ChecklistDocument(filename="Good.xlsx", format="xlsx", status="read", rule_count=3),
        ),
        rules_read=10,
        rules_applied=7,
        rules_omitted=3,
        selection_basis="relevance to the changed files",
        story_unavailable_reason="the credential cannot read work items",
        dropped_citations=("SEC-WEB-99",),
    )
    text = " ".join(record.reductions)
    assert "No checklist was applied" in text
    assert "Bad.xlsx was not read: corrupt" in text
    assert "Good.xlsx" not in text  # a document that was read is not a reduction
    assert "3 of 10 rules were not applied" in text
    assert "Story coverage was not assessed" in text
    assert "1 citation(s) matched no applied rule" in text


def test_a_complete_run_reports_no_reductions():
    record = RunInventory(
        source=ChecklistSource(repo="X", available=True),
        documents=(ChecklistDocument(filename="G.xlsx", format="xlsx", status="read", rule_count=3),),
        rules_read=3,
        rules_applied=3,
        work_items=(101,),
        criteria_judged=4,
    )
    assert record.reductions == ()
