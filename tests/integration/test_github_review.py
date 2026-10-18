"""T022 (feature 007) - a GitHub pull request, previewed end to end.

The GitHub counterpart of tests/integration/test_us1_review.py: the same cart
change, the same fake provider, reviewed through `FakeGitHubClient`.
"""

import pytest

from review_agent import github_client
from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import fake_llm
from tests.fakes_github import FakeGitHubClient
from tests.fixtures import github_pr as gh
from tests.fixtures import pr_demo as demo


@pytest.fixture
def review(github_env, monkeypatch, capsys):
    def _review(fake=None, response=None, dry_run=True, **env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        fake = fake or FakeGitHubClient()
        llm = fake_llm(response if response is not None else demo.MODEL_RESPONSE)
        monkeypatch.setattr(github_client, "make_github_platform", lambda config: fake)
        monkeypatch.setattr(main_module, "call_llm", llm)
        config = load_config(dry_run_override=dry_run)
        report = main_module.run_review(config, main_module.PhaseLog(enabled=True))
        return report, fake, llm, capsys.readouterr().out

    return _review


def test_a_github_preview_reviews_and_writes_nothing(review):
    report, fake, llm, out = review()
    assert fake.write_count == 0
    assert llm.state["calls"] == 1
    assert report.outcome == "complete"
    assert "DRY RUN - the following would be posted" in out
    assert f"**Reviewed**: PR #12, commit {gh.HEAD[:7]}" in out
    assert "iteration" not in out.split("**Reviewed**", 1)[1].split("\n", 1)[0]


def test_the_story_comes_from_the_linked_issue(review):
    report, fake, _llm, out = review()
    assert "linked_issue_numbers" in fake.calls and "get_issue:7" in fake.calls
    assert len(report.coverage) >= 3
    assert "phase=workitems" in out and "source=github-issues" in out


def test_the_diff_is_taken_against_the_merge_base(review):
    _report, fake, _llm, _out = review()
    assert f"get_file_content:/{gh.CART_PATH}@{gh.MERGE_BASE[:4]}" in fake.calls
    assert f"get_file_content:/{gh.CART_PATH}@{gh.HEAD[:4]}" in fake.calls


def test_excluded_files_are_never_sent(review):
    _report, _fake, llm, _out = review()
    for prompt in llm.state["prompts"]:
        assert "appsettings.json" not in prompt.split("## Diff", 1)[-1]


def test_findings_anchor_to_changed_lines(review):
    # The fake serves no checklist, so the demo's checklist violation is (rightly)
    # dropped as an uncited rule; a code issue is what anchors here.
    response = dict(demo.MODEL_RESPONSE)
    response["code_issues"] = [
        {"severity": "low", "issue": "Magic number for the maximum quantity.",
         "file": gh.CART_PATH, "line": 26},
    ]
    _report, _fake, _llm, out = review(response=response)
    assert f"--- inline comment: /{gh.CART_PATH}:" in out


def test_phase_log_names_the_platform(review):
    _report, _fake, _llm, out = review()
    assert "phase=pullrequest" in out and "platform=github" in out and "draft=False" in out
    for phase in ("workitems", "checklists", "changes", "prior", "llm", "parse", "post"):
        assert f"phase={phase}" in out


def test_a_draft_reviewed_locally_says_so(review):
    draft = dict(gh.PULL, draft=True)
    _report, _fake, _llm, out = review(fake=FakeGitHubClient(pull=draft))
    assert "This pull request is a draft" in out


def test_story_source_none_is_a_stated_checklist_only_review(review):
    report, fake, _llm, out = review(STORY_SOURCE="none")
    assert "linked_issue_numbers" not in fake.calls
    assert "story source is set to none" in out
    assert report.inventory.work_items == ()


def test_set_aside_issues_are_reported_not_dropped(review):
    fake = FakeGitHubClient(
        linked=(7, 8),
        issues={7: gh.ISSUE_7, 8: {"number": 8, "pull_request": {}}},
        notes=("other/repo#4 is in another repository and was not read",),
    )
    _report, _fake, _llm, out = review(fake=fake)
    assert "#8 is a pull request, not an issue" in out
    assert "other/repo#4 is in another repository" in out
