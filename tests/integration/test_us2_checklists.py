"""T049-T053 - the shared checklists: combining, citation, and degrading."""

import pytest

from review_agent import checklist as checklist_module
from review_agent import main as main_module
from review_agent.config import load_config
from review_agent.errors import SetupFailure
from tests.fakes import FakeTfsClient, NoChecklistClient, fake_llm
from tests.fixtures import pr_demo as demo


class _Cfg:
    def __init__(self, **kw):
        self.checklist_repo = kw.get("repo", "TestMarkDown")
        self.checklist_path = kw.get("path", "/")
        self.checklist_file_pattern = kw.get("pattern", "*.md")
        self.checklist_branch = kw.get("branch", "master")


# -- T049: combining -------------------------------------------------------


def test_all_matching_files_are_read_and_combined():
    result = checklist_module.fetch_checklist(FakeTfsClient(), _Cfg())
    assert result.available is True
    assert len(result.sources) == 2
    assert set(result.filenames) == {"code-review-checklist.md", "security-checklist.md"}


def test_each_section_is_labelled_with_its_source_file():
    result = checklist_module.fetch_checklist(FakeTfsClient(), _Cfg())
    assert "## From: code-review-checklist.md" in result.combined_markdown
    assert "## From: security-checklist.md" in result.combined_markdown


def test_folders_and_non_matching_files_are_ignored():
    """The fixture listing includes /docs (a folder) and README.txt."""
    result = checklist_module.fetch_checklist(FakeTfsClient(), _Cfg())
    assert "README" not in result.combined_markdown
    assert all(f.endswith(".md") for f in result.filenames)


def test_a_new_file_is_picked_up_with_no_configuration_change():
    """FR-013: adding a checklist must not require touching config."""
    client = FakeTfsClient(
        checklist_files={
            "/code-review-checklist.md": demo.CHECKLIST_MAIN,
            "/security-checklist.md": demo.CHECKLIST_SECURITY,
            "/performance-checklist.md": "# Performance\n\n- No N+1 queries.\n",
        }
    )
    original = demo.CHECKLIST_ITEMS["value"]
    try:
        demo.CHECKLIST_ITEMS["value"] = original + [
            {"path": "/performance-checklist.md", "isFolder": False, "gitObjectType": "blob"}
        ]
        result = checklist_module.fetch_checklist(client, _Cfg())
        assert "performance-checklist.md" in result.filenames
        assert "N+1" in result.combined_markdown
    finally:
        demo.CHECKLIST_ITEMS["value"] = original


def test_pattern_can_be_narrowed_by_configuration():
    result = checklist_module.fetch_checklist(
        FakeTfsClient(), _Cfg(pattern="security-*.md")
    )
    assert result.filenames == ("security-checklist.md",)


def test_sources_are_ordered_deterministically():
    """Two runs must produce the same combined checklist, so the prompt is stable."""
    a = checklist_module.fetch_checklist(FakeTfsClient(), _Cfg()).combined_markdown
    b = checklist_module.fetch_checklist(FakeTfsClient(), _Cfg()).combined_markdown
    assert a == b


# -- T050 / T053: citation and repo derivation ----------------------------


@pytest.fixture
def run(base_env, monkeypatch):
    def _run(client=None, response=None, dry_run=False):
        tfs = client or FakeTfsClient()
        monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
        monkeypatch.setattr(
            main_module, "call_llm", fake_llm(response or demo.MODEL_RESPONSE)
        )
        config = load_config(dry_run_override=dry_run)
        report = main_module.run_review(config, main_module.PhaseLog(enabled=False))
        return report, tfs

    return _run


def test_violation_cites_its_source_checklist_file(run):
    report, _ = run()
    assert len(report.checklist_violations) == 1
    assert report.checklist_violations[0].source == "code-review-checklist.md"


def test_violation_appears_in_the_summary_with_its_source(run):
    _, tfs = run()
    summary = tfs.summary_threads()[0][1]
    assert "code-review-checklist.md" in summary
    assert "Business rules" in summary


def test_violation_inline_comment_cites_the_source(run):
    _, tfs = run()
    inline_bodies = " ".join(w[1] for w in tfs.inline_threads())
    assert "code-review-checklist.md" in inline_bodies


def test_checklist_reaches_the_prompt(run, base_env, monkeypatch):
    tfs = FakeTfsClient()
    llm = fake_llm(demo.MODEL_RESPONSE)
    monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
    monkeypatch.setattr(main_module, "call_llm", llm)
    main_module.run_review(
        load_config(dry_run_override=True), main_module.PhaseLog(enabled=False)
    )
    prompt = llm.state["prompts"][0]
    assert "Business rules from the story are enforced" in prompt
    assert "From: code-review-checklist.md" in prompt
    assert "Report only real violations" in prompt


# -- T051: no filler on a clean diff --------------------------------------


def test_clean_diff_yields_no_violations(run):
    response = dict(demo.MODEL_RESPONSE)
    response["checklist_violations"] = []
    report, tfs = run(response=response)
    assert report.checklist_violations == ()
    summary = tfs.summary_threads()[0][1]
    assert "Checklist violations (0)" in summary
    assert "None found" in summary


# -- T052: unavailable checklist degrades, never fails --------------------


def test_no_matching_files_degrades_with_the_branch_named():
    result = checklist_module.fetch_checklist(NoChecklistClient(), _Cfg(branch="master"))
    assert result.available is False
    assert "master" in result.unavailable_reason
    assert "*.md" in result.unavailable_reason


def test_unreachable_checklist_repo_degrades_rather_than_failing():
    class Unreachable(FakeTfsClient):
        def list_items(self, scope_path, branch, repo=None):
            raise SetupFailure("not permitted to read the checklist repository")

    result = checklist_module.fetch_checklist(Unreachable(), _Cfg())
    assert result.available is False
    assert "not permitted" in result.unavailable_reason


def test_listed_but_unreadable_files_degrade_with_a_count():
    client = FakeTfsClient(checklist_files={})
    result = checklist_module.fetch_checklist(client, _Cfg())
    assert result.available is False
    assert "none could be read" in result.unavailable_reason


def test_missing_checklist_url_degrades_with_a_named_cause():
    """FR-024: the reason names the setting to set, not the one 001 happened to read."""
    result = checklist_module.fetch_checklist(FakeTfsClient(), _Cfg(repo=""))
    assert result.available is False
    assert "TFS_REPO_CODE_REVIEW_CodeReviewChecklist" in result.unavailable_reason


def test_the_coverage_review_still_runs_without_a_checklist(run):
    response = dict(demo.MODEL_RESPONSE)
    response["checklist_violations"] = []
    report, tfs = run(client=NoChecklistClient(), response=response)
    assert len(report.coverage) == 5, "the coverage half must survive"
    assert report.false_coverage_claims, "including the headline finding"
    assert report.outcome == "complete"


def test_the_prompt_tells_the_model_there_is_no_checklist(base_env, monkeypatch):
    llm = fake_llm({**demo.MODEL_RESPONSE, "checklist_violations": []})
    monkeypatch.setattr(main_module, "TfsClient", lambda config: NoChecklistClient())
    monkeypatch.setattr(main_module, "call_llm", llm)
    main_module.run_review(
        load_config(dry_run_override=True), main_module.PhaseLog(enabled=False)
    )
    prompt = llm.state["prompts"][0]
    assert "No checklist is available" in prompt
    assert "empty" in prompt


# --------------------------------------------------------------------------
# T034 (feature 003) - the inventory reaches both destinations.
#
# The phase log is not posted. A reader looking at the pull request sees the
# summary and nothing else, so an inventory that lives only in the build log
# leaves them with exactly the clean-looking summary this feature exists to
# stop producing.
# --------------------------------------------------------------------------


@pytest.fixture
def inventory_run(base_env, checklist_working_copy, monkeypatch):
    from tests.fixtures import docs_builder as build

    def _run(dry_run=True):
        monkeypatch.setenv("TFS_REPO_CODE_REVIEW_CodeReviewChecklist", "CodeReviewChecklist")
        checklist_working_copy(
            {
                "API-Security-Checklist.xlsx": build.xlsx(
                    [build.checklist_sheet_with_ids(count=2)]
                ),
                "Corrupt-Standard.docx": build.corrupt_bytes(),
            }
        )
        tfs = FakeTfsClient()
        monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
        monkeypatch.setattr(main_module, "call_llm", fake_llm(demo.MODEL_RESPONSE))
        report = main_module.run_review(
            load_config(dry_run_override=dry_run), main_module.PhaseLog(enabled=False)
        )
        return report, tfs

    return _run


def test_the_preview_states_what_was_applied(inventory_run, capsys):
    inventory_run()
    printed = capsys.readouterr().out
    assert "What this review applied" in printed
    assert "API-Security-Checklist.xlsx" in printed
    assert "2 rules" in printed


def test_the_preview_states_why_a_document_was_skipped(inventory_run, capsys):
    inventory_run()
    printed = capsys.readouterr().out
    assert "Corrupt-Standard.docx" in printed
    assert "skipped" in printed


def test_the_posted_summary_carries_the_same_inventory(inventory_run):
    report, tfs = inventory_run(dry_run=False)
    summary = tfs.writes[0][1]
    assert "What this review applied" in summary
    assert "API-Security-Checklist.xlsx" in summary
    assert "Corrupt-Standard.docx" in summary


def test_the_inventory_names_the_reference_the_corpus_was_read_at(inventory_run, capsys):
    inventory_run()
    printed = capsys.readouterr().out
    assert "CodeReviewChecklist@master" in printed
