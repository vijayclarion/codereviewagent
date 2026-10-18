"""T012, T013, T026, T034, T035 - the log across a whole review.

The unit tests prove the module writes what it says. These prove the *run* hands
it the right things: every send, in order, including the ones the run itself
throws away.

The last of them is the one that matters most to anybody but the operator:
turning this on must change nothing about the review.
"""

import pytest

from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import EmptyChangesClient, FakeTfsClient, fake_llm
from tests.fixtures import pr_demo as demo


@pytest.fixture
def run(base_env, monkeypatch, tmp_path):
    """A review with logging pointed at a temp directory."""

    def _run(response=None, client=None, logging=True, keep=10, fail_times=0, **env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        if logging:
            monkeypatch.setenv("LLM_LOG", "true")
            monkeypatch.setenv("LLM_LOG_DIR", str(tmp_path / "logs"))
            monkeypatch.setenv("LLM_LOG_KEEP", str(keep))

        tfs = client or FakeTfsClient()
        llm = fake_llm(
            response if response is not None else demo.MODEL_RESPONSE,
            fail_times=fail_times,
        )
        monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
        monkeypatch.setattr(main_module, "call_llm", llm)
        config = load_config(dry_run_override=True)
        report = main_module.run_review(config, main_module.PhaseLog(enabled=False))
        return report, llm

    return _run


def only_log(tmp_path):
    logs = sorted((tmp_path / "logs").glob("*.log"))
    assert len(logs) == 1, f"expected one log, found {[p.name for p in logs]}"
    return logs[0].read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# T012 - every send, in order
# --------------------------------------------------------------------------


def test_every_prompt_the_run_sent_is_in_the_file_in_full(run, tmp_path):
    _, llm = run()
    text = only_log(tmp_path)

    assert llm.state["calls"] >= 1
    for prompt in llm.state["prompts"]:
        assert prompt in text, "a prompt was sent but not recorded verbatim"


def test_entries_appear_in_the_order_they_were_sent(run, tmp_path, monkeypatch):
    """FR-005. A three-chunk review keeps its order."""
    monkeypatch.setenv("LLM_MAX_CHUNK_LINES", "1")  # force a chunk per file
    _, llm = run()
    text = only_log(tmp_path)

    positions = [text.index(p) for p in llm.state["prompts"]]
    assert positions == sorted(positions)
    assert text.count("--- exchange ") == llm.state["calls"]


def test_the_head_carries_the_run_identity_and_the_foot_the_count(run, tmp_path):
    _, llm = run()
    text = only_log(tmp_path)

    # Scoped to the head: a prompt body carries arbitrary text, and asserting
    # a word is absent from the whole file asserts something about the diff.
    head = text.split("\n\n", 1)[0]
    assert head.startswith("=== ai-review llm log ===")
    assert "pull request : 1234" in head
    assert "run          : 1234." in head
    assert "pending" not in head, "the run identifier should have been resolved"
    assert f"=== end | {llm.state['calls']} exchange" in text
    assert "outcome complete" in text


# --------------------------------------------------------------------------
# T013 - a run that calls nobody
# --------------------------------------------------------------------------


def test_a_run_with_nothing_reviewable_still_leaves_a_file_saying_so(run, tmp_path):
    """FR-011. An absent file and a run that made no call must not look alike."""
    report, llm = run(client=EmptyChangesClient())

    assert report.outcome != "degraded"
    assert llm.state["calls"] == 0
    text = only_log(tmp_path)
    assert "=== end | 0 exchanges | outcome no exchange ===" in text


# --------------------------------------------------------------------------
# T034 - the stricter retry
# --------------------------------------------------------------------------


def test_a_retry_records_both_attempts_for_the_same_chunk(run, tmp_path):
    """US3 AS1. The second send carries the stricter instruction, visibly."""
    from review_agent import prompt_builder

    run(fail_times=1)
    text = only_log(tmp_path)

    assert "| chunk 1 of 1 | attempt 1 ---" in text
    assert "| chunk 1 of 1 | attempt 2 ---" in text
    assert prompt_builder.STRICTER_RETRY in text


def test_the_unparseable_first_response_is_recorded_not_discarded(run, tmp_path):
    """The response that caused the retry is the whole point of reading the log."""
    run(fail_times=1)
    text = only_log(tmp_path)
    assert "I cannot produce JSON right now." in text


# --------------------------------------------------------------------------
# T035 - the degraded run
# --------------------------------------------------------------------------


def test_a_degraded_run_still_leaves_every_response_it_received(run, tmp_path):
    """SC-007. The run reports no findings; the log holds the work anyway."""
    report, llm = run(response="not json at all")

    assert report.outcome == "degraded"
    text = only_log(tmp_path)
    assert text.count("not json at all") == 2, "both attempts should be recorded"
    assert "=== end | 2 exchanges | outcome degraded ===" in text


def test_a_provider_failure_records_the_reason_in_place_of_a_response(
    run, tmp_path, monkeypatch
):
    """US3 AS2. FR-008."""
    from review_agent.errors import DegradedReview

    def _unreachable(prompt, config=None, **kwargs):
        raise DegradedReview("the AI provider was unreachable after 3 attempts")

    monkeypatch.setattr(main_module, "call_llm", _unreachable)
    monkeypatch.setenv("LLM_LOG", "true")
    monkeypatch.setenv("LLM_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(main_module, "TfsClient", lambda config: FakeTfsClient())
    config = load_config(dry_run_override=True)
    report = main_module.run_review(config, main_module.PhaseLog(enabled=False))

    assert report.outcome == "degraded"
    text = only_log(tmp_path)
    assert "outcome  : failed in" in text
    assert "unreachable after 3 attempts" in text


# --------------------------------------------------------------------------
# T026 - the review does not notice
# --------------------------------------------------------------------------


def _shape(report):
    """Everything about a report a reviewer would see."""
    return {
        "outcome": report.outcome,
        "summary": report.summary,
        "coverage": [(c.ordinal, c.status) for c in report.coverage],
        "violations": [v.rule_id for v in report.checklist_violations],
        "issues": [(i.path, i.line, i.severity) for i in report.code_issues],
        "false_claims": len(report.false_coverage_claims),
        "blocking": report.has_blocking_findings,
    }


def test_logging_changes_nothing_about_the_review(run, tmp_path):
    """FR-017, SC-004. The whole feature is worthless if this ever fails."""
    with_logging, _ = run(logging=True)
    without_logging, _ = run(logging=False)

    assert _shape(with_logging) == _shape(without_logging)


def test_logging_off_writes_nothing_anywhere(run, tmp_path):
    """FR-002, SC-003."""
    run(logging=False)
    assert not (tmp_path / "logs").exists()


def test_the_prompts_sent_are_identical_with_logging_on_and_off(run):
    on = run(logging=True)[1].state["prompts"]
    off = run(logging=False)[1].state["prompts"]
    assert on == off
