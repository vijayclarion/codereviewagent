"""T060, T062-T063, T065 - posting, thread payloads, and incremental re-review."""

import pytest

from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import FakeTfsClient, fake_llm
from tests.fixtures import pr_demo as demo


@pytest.fixture
def run(base_env, monkeypatch):
    def _run(client=None, response=None, dry_run=False, **env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        tfs = client or FakeTfsClient()
        monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
        monkeypatch.setattr(
            main_module, "call_llm", fake_llm(response or demo.MODEL_RESPONSE)
        )
        config = load_config(dry_run_override=dry_run)
        report = main_module.run_review(config, main_module.PhaseLog(enabled=False))
        return report, tfs

    return _run


# -- T060: thread payloads -------------------------------------------------


def test_exactly_one_summary_thread_is_created(run):
    _, tfs = run()
    assert len(tfs.summary_threads()) == 1


def test_the_summary_thread_has_no_thread_context(run):
    _, tfs = run()
    assert tfs.summary_threads()[0][2] is None


def test_inline_threads_carry_a_thread_context(run):
    _, tfs = run()
    assert tfs.inline_threads(), "the demo produces at least one located finding"
    for _, _, context in tfs.inline_threads():
        assert "filePath" in context
        assert "rightFileStart" in context
        assert "rightFileEnd" in context


def test_thread_context_uses_right_side_lines_only(run):
    """Research R4: a left-side anchor would point at removed code."""
    _, tfs = run()
    for _, _, context in tfs.inline_threads():
        assert "leftFileStart" not in context
        assert "leftFileEnd" not in context


def test_thread_context_file_path_is_absolute(run):
    _, tfs = run()
    for _, _, context in tfs.inline_threads():
        assert context["filePath"].startswith("/")


def test_the_anchored_line_is_a_positive_integer(run):
    _, tfs = run()
    for _, _, context in tfs.inline_threads():
        assert isinstance(context["rightFileStart"]["line"], int)
        assert context["rightFileStart"]["line"] >= 1


def test_every_posted_comment_carries_the_attribution_footer(run):
    _, tfs = run()
    for write in tfs.created_threads():
        assert "AI code review" in write[1]
        assert "ai-review:" in write[1]


# -- T062: incremental re-review -----------------------------------------


def _threads_from(tfs):
    """Turn a run's writes into the thread listing the next run would read."""
    threads = []
    for index, write in enumerate(tfs.created_threads(), start=1):
        threads.append(
            {"id": index, "isDeleted": False, "comments": [{"id": index * 10, "content": write[1]}]}
        )
    return threads


def test_a_second_run_posts_no_duplicate_inline_comments(run):
    _, first = run()
    _, second = run(client=FakeTfsClient(threads=_threads_from(first)))
    assert second.inline_threads() == [], "already-posted findings must not repeat"


def test_a_second_run_updates_the_summary_in_place(run):
    _, first = run()
    _, second = run(client=FakeTfsClient(threads=_threads_from(first)))
    updates = [w for w in second.writes if w[0] == "update_comment"]
    assert len(updates) == 1
    assert second.summary_threads() == [], "no second summary thread"


def test_the_updated_summary_targets_the_original_thread_and_comment(run):
    _, first = run()
    prior_threads = _threads_from(first)
    _, second = run(client=FakeTfsClient(threads=prior_threads))
    update = [w for w in second.writes if w[0] == "update_comment"][0]
    assert update[1] == prior_threads[0]["id"]
    assert update[2] == prior_threads[0]["comments"][0]["id"]


def test_a_new_finding_on_a_re_review_is_posted(run):
    _, first = run()
    extended = {
        **demo.MODEL_RESPONSE,
        "code_issues": [
            {
                "severity": "medium",
                "issue": "quantity addition can overflow for very large values",
                "file": "src/eShop.Api/Controllers/CartController.cs",
                "line": 26,
            }
        ],
    }
    _, second = run(client=FakeTfsClient(threads=_threads_from(first)), response=extended)
    assert len(second.inline_threads()) == 1, "only the new finding"
    assert "overflow" in second.inline_threads()[0][1]


def test_the_agent_never_resolves_or_deletes_its_own_threads(run):
    _, first = run()
    _, second = run(client=FakeTfsClient(threads=_threads_from(first)))
    kinds = {w[0] for w in second.writes}
    assert kinds <= {"create_thread", "add_comment", "update_comment"}


def test_patch_failure_falls_back_to_appending_in_the_same_thread(run):
    """Research R5: some on-prem versions refuse a comment PATCH."""
    _, first = run()
    client = FakeTfsClient(threads=_threads_from(first), fail_patch=True)
    _, second = run(client=client)
    appended = [w for w in second.writes if w[0] == "add_comment"]
    assert len(appended) == 1
    assert appended[0][1] == 1, "same thread, so still one summary discussion"


def test_prior_feedback_is_read_before_posting(run):
    _, tfs = run()
    assert "get_threads" in tfs.calls
    assert tfs.calls.index("get_threads") < len(tfs.calls)


# -- T063: unlocated findings ---------------------------------------------


def test_a_finding_with_no_file_goes_to_the_summary(run):
    response = {
        **demo.MODEL_RESPONSE,
        "code_issues": [{"severity": "low", "issue": "consider extracting a service"}],
    }
    _, tfs = run(response=response)
    summary = tfs.summary_threads()[0][1]
    assert "consider extracting a service" in summary


def test_a_finding_on_an_unknown_file_goes_to_the_summary(run):
    response = {
        **demo.MODEL_RESPONSE,
        "code_issues": [
            {"severity": "low", "issue": "odd naming here", "file": "src/NotInDiff.cs", "line": 5}
        ],
    }
    _, tfs = run(response=response)
    inline = " ".join(w[1] for w in tfs.inline_threads())
    assert "odd naming here" not in inline
    assert "odd naming here" in tfs.summary_threads()[0][1]


def test_a_finding_on_a_line_outside_the_diff_goes_to_the_summary(run):
    response = {
        **demo.MODEL_RESPONSE,
        "code_issues": [
            {
                "severity": "low",
                "issue": "line far beyond the diff",
                "file": "src/eShop.Api/Controllers/CartController.cs",
                "line": 9999,
            }
        ],
    }
    _, tfs = run(response=response)
    assert "line far beyond the diff" in tfs.summary_threads()[0][1]


# -- T065: exit codes ----------------------------------------------------


def test_default_run_with_findings_exits_zero(base_env, monkeypatch):
    monkeypatch.setattr(main_module, "TfsClient", lambda config: FakeTfsClient())
    monkeypatch.setattr(main_module, "call_llm", fake_llm(demo.MODEL_RESPONSE))
    assert main_module.main(["--dry-run", "--quiet"]) == 0


def test_blocking_mode_exits_one_on_a_false_coverage_claim(base_env, monkeypatch):
    monkeypatch.setenv("FAIL_ON_CONTRADICTION", "true")
    monkeypatch.setattr(main_module, "TfsClient", lambda config: FakeTfsClient())
    monkeypatch.setattr(main_module, "call_llm", fake_llm(demo.MODEL_RESPONSE))
    assert main_module.main(["--dry-run", "--quiet"]) == 1


def test_blocking_mode_exits_zero_on_a_clean_review(base_env, monkeypatch):
    clean = {
        "coverage": [
            {"criterion": c["criterion"], "status": "appears_addressed", "evidence": "ok"}
            for c in demo.MODEL_RESPONSE["coverage"]
        ],
        "checklist_violations": [],
        "code_issues": [],
        "summary": "All good.",
    }
    monkeypatch.setenv("FAIL_ON_CONTRADICTION", "true")
    monkeypatch.setattr(main_module, "TfsClient", lambda config: FakeTfsClient())
    monkeypatch.setattr(main_module, "call_llm", fake_llm(clean))
    assert main_module.main(["--dry-run", "--quiet"]) == 0


def test_blocking_mode_exits_zero_on_a_degraded_review(base_env, monkeypatch):
    """An outage must not gate a merge even in blocking mode (FR-029)."""
    monkeypatch.setenv("FAIL_ON_CONTRADICTION", "true")
    monkeypatch.setattr(main_module, "TfsClient", lambda config: FakeTfsClient())
    monkeypatch.setattr(main_module, "call_llm", fake_llm("not json"))
    assert main_module.main(["--dry-run", "--quiet"]) == 0


def test_setup_failure_exits_two(base_env, monkeypatch):
    from review_agent.errors import SetupFailure

    def explode(config):
        raise SetupFailure("cannot reach the collection", remedy="check TFS_BASE_URL")

    monkeypatch.setattr(main_module, "TfsClient", explode)
    assert main_module.main(["--dry-run", "--quiet"]) == 2


def test_missing_configuration_exits_two(monkeypatch):
    monkeypatch.setenv("TFS_BASE_URL", "https://x/tfs/C")
    assert main_module.main(["--dry-run", "--quiet"]) == 2


# -- degraded posting ----------------------------------------------------


def test_a_degraded_run_posts_the_notice_to_the_pull_request(run):
    _, tfs = run(response="not json", dry_run=False)
    assert len(tfs.created_threads()) == 1
    body = tfs.created_threads()[0][1]
    assert "could not complete" in body.lower()
    assert "no findings should be inferred" in body.lower()


def test_a_degraded_run_updates_an_existing_summary_rather_than_adding_one(run):
    _, first = run()
    client = FakeTfsClient(threads=_threads_from(first))
    _, second = run(client=client, response="not json")
    assert [w for w in second.writes if w[0] == "update_comment"]
    assert second.summary_threads() == []


# --------------------------------------------------------------------------
# T046 (feature 003) - a second posting run repeats nothing.
#
# The defect these close: two posting runs against an unchanged pull request
# produced suppressed=0 and nine inline comments where five were expected,
# because every finding's identity was the provider's prose and the provider
# rewords. Feature 001's gap G4 called this "no gap" by reasoning about the
# fingerprint function without noticing what was passed to it.
#
# Behaviours B1-B5 of contracts/finding-identity.md.
# --------------------------------------------------------------------------

import json

from review_agent.output_layer import SEVERITY_HEADER


def _threads_from(tfs):
    """The pull request as the next run would read it back."""
    threads = []
    for index, (_kind, content, context) in enumerate(tfs.writes, start=1):
        thread = {"id": index, "comments": [{"id": index, "content": content}]}
        if context:
            thread["threadContext"] = context
        threads.append(thread)
    return threads


def _reworded(response):
    """The same findings, said differently - which is what a provider does."""
    payload = json.loads(response) if isinstance(response, str) else dict(response)
    for violation in payload["checklist_violations"]:
        violation["issue"] = "Restated: " + violation["issue"][::-1]
        violation["item"] = violation["item"].upper()
    for entry in payload["coverage"]:
        entry["evidence"] = "Restated: " + entry.get("evidence", "")
    return json.dumps(payload)


def test_a_second_run_against_an_unchanged_pull_request_adds_nothing(run):
    """B1."""
    _, first = run()
    inline_first = len(first.inline_threads())
    assert inline_first, "the demo must post at least one inline comment to be a test"

    _, second = run(client=FakeTfsClient(threads=_threads_from(first)))
    assert second.inline_threads() == []


def test_a_second_run_suppresses_even_when_every_finding_is_reworded(run):
    """B2 - the actual defect. Identity must not depend on what a finding is called."""
    _, first = run()
    _, second = run(
        client=FakeTfsClient(threads=_threads_from(first)),
        response=_reworded(demo.MODEL_RESPONSE),
    )
    assert second.inline_threads() == []


def test_a_genuinely_new_finding_is_still_posted(run):
    """B5 - suppression must not become silence."""
    _, first = run()
    payload = json.loads(demo.MODEL_RESPONSE) if isinstance(demo.MODEL_RESPONSE, str) else dict(demo.MODEL_RESPONSE)
    payload["code_issues"] = list(payload.get("code_issues", [])) + [
        {
            "severity": "high",
            "issue": "A newly introduced null dereference",
            "file": demo.CART_CONTROLLER_PATH,
            "line": 26,
        }
    ]
    _, second = run(client=FakeTfsClient(threads=_threads_from(first)), response=json.dumps(payload))
    assert len(second.inline_threads()) == 1


def test_the_summary_is_updated_rather_than_repeated(run):
    """Already true before this feature, and worth keeping true."""
    _, first = run()
    _, second = run(client=FakeTfsClient(threads=_threads_from(first)))
    assert second.summary_threads() == []


# --------------------------------------------------------------------------
# R14 (feature 003) - what the LIVE second run found, pinned.
#
# The identity work above fixed every finding that has something stable to key
# on. A code issue has nothing: observed on 2026-09-16 against a real pull
# request, the provider reworded all four code issues AND attributed them to
# different lines between two runs minutes apart. inline=3 suppressed=2 where
# inline=0 suppressed=5 was expected.
#
# So a code issue is additionally matched against the TEXT already posted on the
# same file, which is readable from the pull request and does not depend on the
# provider saying the same thing twice.
# --------------------------------------------------------------------------


def _posted_code_comment(path, text, thread_id=1):
    return {
        "id": thread_id,
        "threadContext": {"filePath": path, "rightFileStart": {"line": 10, "offset": 1}},
        "comments": [
            {
                "id": thread_id,
                "content": f"**Code issue (medium)**\n\n{text}\n\n---\n"
                f"AI code review `ai-review:code:aaaaaaaaaaaa`",
            }
        ],
    }


REWORDED = json.dumps(
    {
        "coverage": [],
        "checklist_violations": [],
        "code_issues": [
            {
                "severity": "medium",
                "issue": "Catching a broad Exception and returning the original total "
                "masks bugs instead of surfacing a specific error type.",
                "file": demo.CART_CONTROLLER_PATH,
                "line": 26,
            }
        ],
        "summary": "Reviewed again.",
    }
)

ORIGINAL_TEXT = (
    "Blanket exception handling masks real defects by returning the original "
    "total as if the discount had succeeded, giving no diagnostic signal."
)


def test_a_reworded_code_issue_on_the_same_file_is_not_repeated(run):
    """The live failure, in miniature."""
    prior = [_posted_code_comment(demo.CART_CONTROLLER_PATH, ORIGINAL_TEXT)]
    _, tfs = run(client=FakeTfsClient(threads=prior), response=REWORDED)
    assert tfs.inline_threads() == []


def test_a_code_issue_moved_to_another_line_is_not_repeated(run):
    """The provider also moves the line it attributes a finding to."""
    prior = [_posted_code_comment(demo.CART_CONTROLLER_PATH, ORIGINAL_TEXT)]
    moved = json.loads(REWORDED)
    moved["code_issues"][0]["line"] = 30
    _, tfs = run(client=FakeTfsClient(threads=prior), response=json.dumps(moved))
    assert tfs.inline_threads() == []


def test_a_different_code_issue_in_the_same_file_is_still_posted(run):
    """Suppression must not become silence - this is the expensive error."""
    prior = [_posted_code_comment(demo.CART_CONTROLLER_PATH, ORIGINAL_TEXT)]
    different = json.loads(REWORDED)
    different["code_issues"][0]["issue"] = "An unused import of json is left in the module."
    _, tfs = run(client=FakeTfsClient(threads=prior), response=json.dumps(different))
    assert len(tfs.inline_threads()) == 1


def test_the_same_text_on_a_different_file_is_still_posted(run):
    prior = [_posted_code_comment("/src/Other.cs", ORIGINAL_TEXT)]
    _, tfs = run(client=FakeTfsClient(threads=prior), response=REWORDED)
    assert len(tfs.inline_threads()) == 1
