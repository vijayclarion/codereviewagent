"""T020, T021 - reviewing against the team's real checklist documents (US1).

The half of the review the team asked for and has never had. Until this feature
`checklist_docs.py` was complete, unit-tested, and imported by nothing, while the
run fetched `*.md` over an interface that cannot carry a spreadsheet - so every
review measured the code against no checklist at all and said so nowhere.
"""

import json

import pytest

from review_agent import checklist as checklist_module
from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import FakeTfsClient, fake_llm
from tests.fixtures import docs_builder as build
from tests.fixtures import pr_demo as demo

SPREADSHEET = "API-Security-Checklist.xlsx"
WORD_DOCUMENT = "Secure-Coding-Standard.docx"

CORPUS = {
    SPREADSHEET: build.xlsx([build.checklist_sheet_with_ids(count=3)]),
    WORD_DOCUMENT: build.marked_rules_document(count=2),
}


@pytest.fixture
def corpus(base_env, checklist_working_copy, monkeypatch):
    monkeypatch.setenv("TFS_REPO_CODE_REVIEW_CodeReviewChecklist", "CodeReviewChecklist")

    def _build(files=None, **kwargs):
        checklist_working_copy(files if files is not None else CORPUS, **kwargs)
        return checklist_module.obtain_corpus(load_config(dry_run_override=True))

    return _build


@pytest.fixture
def review(base_env, monkeypatch):
    """A full preview run, with the provider's response under the test's control."""

    def _run(response):
        tfs = FakeTfsClient()
        llm = fake_llm(json.dumps(response) if isinstance(response, dict) else response)
        monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
        monkeypatch.setattr(main_module, "call_llm", llm)
        report = main_module.run_review(
            load_config(dry_run_override=True), main_module.PhaseLog(enabled=False)
        )
        return report, llm

    return _run


def _response(violations):
    return {
        "coverage": [{"criterion": "Stock is checked", "status": "appears_addressed", "evidence": "x"}],
        "checklist_violations": violations,
        "code_issues": [],
        "summary": "Reviewed.",
    }


# -- rules reach the review -------------------------------------------------


def test_both_formats_contribute_rules(corpus):
    result = corpus()
    documents = {d.filename: d for d in result.documents}
    assert documents[SPREADSHEET].rule_count == 3
    assert documents[WORD_DOCUMENT].rule_count == 2


def test_a_word_documents_own_identifier_is_used_verbatim(corpus):
    """FR-009: the team's identifiers are exactly what a citation needs."""
    result = corpus()
    assert any(item.item_id.startswith("SEC-WEB-") for item in result.items)


def test_the_rules_reach_the_prompt_with_their_identifiers(corpus, base_env, monkeypatch):
    corpus()
    tfs = FakeTfsClient()
    llm = fake_llm(json.dumps(_response([])))
    monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
    monkeypatch.setattr(main_module, "call_llm", llm)
    main_module.run_review(
        load_config(dry_run_override=True), main_module.PhaseLog(enabled=False)
    )
    prompt = llm.state["prompts"][0]
    assert f"## From: {SPREADSHEET}" in prompt
    assert "[SEC-WEB-01]" in prompt
    assert 'set "rule_id"' in prompt


# -- FR-017: a violation cites its rule and its document --------------------


def test_a_violation_cites_the_spreadsheet_rule_and_its_filename(corpus, review):
    corpus()
    report, _ = review(_response([{"rule_id": "1", "item": "Rule number 1", "issue": "Broken", "file": demo.CART_CONTROLLER_PATH, "line": 12}]))
    violation = report.checklist_violations[0]
    assert violation.rule_id == "1"
    assert violation.source == SPREADSHEET


def test_a_violation_cites_the_word_rule_and_its_filename(corpus, review):
    corpus()
    report, _ = review(_response([{"rule_id": "SEC-WEB-01", "item": "whatever", "issue": "Broken"}]))
    violation = report.checklist_violations[0]
    assert violation.rule_id == "SEC-WEB-01"
    assert violation.source == WORD_DOCUMENT


def test_the_filename_comes_from_the_corpus_not_from_the_model(corpus, review):
    """A filename that looks authoritative and is wrong is worse than none."""
    corpus()
    report, _ = review(
        _response([{"rule_id": "SEC-WEB-01", "item": "x", "issue": "y", "source": "Invented.xlsx"}])
    )
    assert report.checklist_violations[0].source == WORD_DOCUMENT


def test_a_citation_matching_no_applied_rule_is_reported_not_posted(corpus, review):
    corpus()
    report, _ = review(_response([{"rule_id": "SEC-WEB-99", "item": "Invented", "issue": "y"}]))
    assert report.checklist_violations == ()
    assert report.dropped_citations == ("SEC-WEB-99",)


def test_a_violation_naming_the_rule_by_its_title_still_resolves(corpus, review):
    """R2 of the resolution table: a model that ignores rule_id is not a failure."""
    corpus()
    report, _ = review(_response([{"item": "Rule number 2", "issue": "Broken"}]))
    assert report.checklist_violations[0].rule_id == "2"


# -- FR-006, SC-009: degradation ------------------------------------------


def test_an_unreachable_repository_still_delivers_the_story_half(review, base_env):
    """The autouse no-clone fixture is exactly this condition."""
    report, _ = review(_response([]))
    assert report.coverage, "story coverage must survive an unavailable checklist"
    assert report.outcome == "complete"


def test_an_unreachable_repository_is_not_a_setup_failure(base_env, monkeypatch):
    tfs = FakeTfsClient()
    monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
    monkeypatch.setattr(main_module, "call_llm", fake_llm(demo.MODEL_RESPONSE))
    exit_code = main_module.main(["--dry-run", "--quiet"])
    assert exit_code == 0


def test_the_inventory_states_why_no_checklist_was_applied(base_env, monkeypatch):
    monkeypatch.delenv("CHECKLIST_REPO_URL", raising=False)
    tfs = FakeTfsClient(checklist_files={})
    monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
    monkeypatch.setattr(main_module, "call_llm", fake_llm(demo.MODEL_RESPONSE))
    report = main_module.run_review(
        load_config(dry_run_override=True), main_module.PhaseLog(enabled=False)
    )
    assert "TFS_REPO_CODE_REVIEW_CodeReviewChecklist" in report.inventory.source.unavailable_reason
    assert any("No checklist was applied" in r for r in report.inventory.reductions)
