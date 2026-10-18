"""T064 - four misconfigurations, four different answers (US4, FR-024).

The condition this project was actually in for two features: a configured name
with one character too many, resolving to nothing, and every run reporting a
clean review against no checklist at all. What made it survive so long is that
the run said the same thing - nothing - in all four cases.

So the assertion here is on DISTINCTNESS, not on non-emptiness. Four reasons that
are all present and all say "the checklist could not be used" would pass a weaker
test and would have left this project exactly where it was.
"""

import pytest

from review_agent import checklist as checklist_module
from review_agent.config import CHECKLIST_REPO_SETTING, load_config
from review_agent.errors import SetupFailure
from tests.fixtures import docs_builder as build


@pytest.fixture
def diagnose(base_env, monkeypatch, checklist_working_copy):
    """Produce the run's own explanation for one misconfiguration."""

    def _for(condition):
        monkeypatch.setenv("TFS_REPO_CODE_REVIEW_CodeReviewChecklist", "CodeReviewChecklist")

        if condition == "no setting":
            monkeypatch.delenv("TFS_REPO_CODE_REVIEW_CodeReviewChecklist", raising=False)
            monkeypatch.delenv("CHECKLIST_REPO_URL", raising=False)
        elif condition == "not found":
            def _absent(config, repo, ref=None):
                raise SetupFailure(f"could not obtain {repo}: repository not found")

            monkeypatch.setattr(checklist_module, "_fetch", _absent)
        elif condition == "not permitted":
            def _refused(config, repo, ref=None):
                raise SetupFailure(f"could not obtain {repo}: Authentication failed")

            monkeypatch.setattr(checklist_module, "_fetch", _refused)
        elif condition == "nothing matched":
            checklist_working_copy({"README.md": b"# not a checklist document"})
        elif condition == "nothing readable":
            checklist_working_copy({"Broken.xlsx": build.corrupt_bytes()})
        else:  # pragma: no cover - a typo in a test is not a condition
            raise AssertionError(condition)

        corpus = checklist_module.obtain_corpus(load_config(dry_run_override=True))
        assert not corpus.available
        return corpus.unavailable_reason

    return _for


CONDITIONS = ("no setting", "not found", "not permitted", "nothing matched", "nothing readable")


def test_every_condition_produces_a_different_answer(diagnose):
    reasons = {condition: diagnose(condition) for condition in CONDITIONS}
    assert len(set(reasons.values())) == len(CONDITIONS), (
        "two misconfigurations that read alike are one misconfiguration nobody fixes"
    )


def test_an_absent_setting_names_the_setting_to_provide(diagnose):
    reason = diagnose("no setting")
    assert CHECKLIST_REPO_SETTING in reason


def test_an_absent_setting_names_only_the_canonical_one(diagnose):
    """Offering an operator four names to choose between is not help."""
    reason = diagnose("no setting")
    assert "CHECKLIST_REPO_URL" not in reason
    assert CHECKLIST_REPO_SETTING + "T" not in reason


def test_not_found_names_the_repository_and_the_setting(diagnose):
    reason = diagnose("not found")
    assert "CodeReviewChecklist" in reason
    assert "was found" in reason
    assert CHECKLIST_REPO_SETTING in reason


def test_not_permitted_names_the_access_rather_than_the_name(diagnose):
    """A different correction: a token scope, not a spelling."""
    reason = diagnose("not permitted")
    assert "Code (read)" in reason
    assert "TFS_PAT" in reason
    assert "not found" not in reason.lower()


def test_nothing_matched_reports_the_selection_the_path_and_the_reference(diagnose):
    reason = diagnose("nothing matched")
    assert "*.xlsx" in reason
    assert "master" in reason
    assert "reached" in reason, "the operator needs to know the repository itself was fine"


def test_nothing_readable_is_distinct_from_nothing_matched(diagnose):
    """FR-013: found-but-unreadable and not-found-at-all are different answers."""
    reason = diagnose("nothing readable")
    assert "none could be read" in reason
