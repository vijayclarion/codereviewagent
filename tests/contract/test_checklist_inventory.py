"""T019 - every document the walk matched is accounted for (SC-002).

A gate, and the most useful assertion in this suite. A review against an empty
checklist and a review that found nothing wrong printed identical output for the
whole of this project's life, and the second is what everyone read. The equality
below - documents in the inventory == files matched - is what makes them
distinguishable, mechanically, rather than by someone remembering to look.
"""

import pytest

from review_agent import checklist as checklist_module
from review_agent.config import load_config
from tests.fixtures import docs_builder as build


@pytest.fixture
def corpus_of(base_env, checklist_working_copy, monkeypatch):
    def _build(files, **kwargs):
        monkeypatch.setenv("TFS_REPO_CODE_REVIEW_CodeReviewChecklist", "CodeReviewChecklist")
        served = checklist_working_copy(files, **kwargs)
        corpus = checklist_module.obtain_corpus(load_config(dry_run_override=True))
        return corpus, served

    return _build


EVERY_SHAPE = {
    "API-Security-Checklist.xlsx": build.xlsx([build.checklist_sheet_with_ids(count=3)]),
    "Secure-Coding-Standard.docx": build.marked_rules_document(count=2),
    "standards/Architecture.xlsx": build.xlsx([build.checklist_sheet_without_ids(count=2)]),
    "Empty-Guidance.docx": build.empty_document(),
    "Corrupt-Standard.xlsx": build.corrupt_bytes(),
}


def test_every_matched_file_appears_in_the_inventory(corpus_of):
    corpus, _ = corpus_of(EVERY_SHAPE)
    assert len(corpus.documents) == len(EVERY_SHAPE)
    assert {d.filename for d in corpus.documents} == set(EVERY_SHAPE)


def test_every_document_carries_a_count_or_a_reason(corpus_of):
    corpus, _ = corpus_of(EVERY_SHAPE)
    for document in corpus.documents:
        if document.status == "read":
            assert document.rule_count > 0
        elif document.status == "skipped":
            assert document.skip_reason, f"{document.filename} was skipped in silence"
        else:
            assert document.status == "no_rules"


def test_read_empty_and_unreadable_are_three_different_answers(corpus_of):
    corpus, _ = corpus_of(EVERY_SHAPE)
    by_name = {d.filename: d for d in corpus.documents}
    assert by_name["API-Security-Checklist.xlsx"].status == "read"
    assert by_name["Empty-Guidance.docx"].status == "no_rules"
    assert by_name["Corrupt-Standard.xlsx"].status == "skipped"


def test_one_unreadable_document_does_not_cost_the_others(corpus_of):
    """FR-012: a corrupt file is a reported outcome, not a failed run."""
    corpus, _ = corpus_of(EVERY_SHAPE)
    assert corpus.available
    assert corpus.rule_count >= 5


def test_a_nested_document_is_found_without_configuration(corpus_of):
    """SC-010: adding a document - or a folder - needs no configuration change."""
    corpus, _ = corpus_of(EVERY_SHAPE)
    assert "standards/Architecture.xlsx" in {d.filename for d in corpus.documents}


def test_office_lock_files_are_not_reported_as_documents(corpus_of):
    files = dict(EVERY_SHAPE)
    files["~$API-Security-Checklist.xlsx"] = b"lock"
    corpus, _ = corpus_of(files)
    assert not any(d.filename.startswith("~$") for d in corpus.documents)
    assert len(corpus.documents) == len(EVERY_SHAPE)


def test_the_working_copy_is_always_removed(corpus_of):
    """FR-005, contract C2.5."""
    _, served = corpus_of(EVERY_SHAPE)
    assert served.cleaned == [str(served.root)]


def test_the_working_copy_is_removed_even_when_reading_raises(
    base_env, checklist_working_copy, monkeypatch
):
    """The failure path is the one that leaks."""
    monkeypatch.setenv("TFS_REPO_CODE_REVIEW_CodeReviewChecklist", "CodeReviewChecklist")
    served = checklist_working_copy(EVERY_SHAPE)

    def _explode(*args, **kwargs):
        raise RuntimeError("something unforeseen")

    monkeypatch.setattr(checklist_module, "_read_corpus", _explode)
    with pytest.raises(RuntimeError):
        checklist_module.obtain_corpus(load_config(dry_run_override=True))
    assert served.cleaned == [str(served.root)]


def test_an_unset_branch_asks_for_no_particular_reference(corpus_of, monkeypatch):
    monkeypatch.delenv("CHECKLIST_BRANCH", raising=False)
    _, served = corpus_of(EVERY_SHAPE)
    assert served.requested_refs == [None]


def test_a_configured_branch_is_asked_for(corpus_of):
    """base_env sets CHECKLIST_BRANCH, and an operator who set it means it."""
    _, served = corpus_of(EVERY_SHAPE)
    assert served.requested_refs == ["master"]


def test_the_reference_the_corpus_was_read_at_is_recorded(corpus_of):
    """C2.3: "the default branch" is not something an operator can check against."""
    corpus, _ = corpus_of(EVERY_SHAPE, ref="main", commit="abc1234")
    assert corpus.source.ref == "main"
    assert corpus.source.commit == "abc1234"
    assert "main" in corpus.source.description
