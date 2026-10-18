"""T010, T011, T025, T036, T037 - the log module on its own.

Everything here writes to `tmp_path`. A test that dropped a log beside the suite
would be collected by the next run - `pytest.ini` sets `testpaths = tests`.
"""

from datetime import datetime

import pytest

from review_agent import config as cfg
from review_agent import llm_log

STARTED = datetime(2026, 9, 17, 14, 30, 22)


def destination(tmp_path, keep=10):
    return llm_log.LogDestination(str(tmp_path), keep)


def record(**overrides):
    values = dict(
        index=1,
        chunk=1,
        chunk_total=3,
        attempt=1,
        sent_at="2026-09-17 14:30:23",
        elapsed_ms=8431,
        prompt="REVIEW THIS DIFF\n+ added a line\n",
        outcome="ok",
        response='{"findings": []}',
    )
    values.update(overrides)
    return llm_log.ExchangeRecord(**values)


def session_at(tmp_path, pr_id=1234, started=STARTED):
    dest = destination(tmp_path)
    return llm_log.LogSession(
        path=dest.path_for(pr_id, started), pr_id=pr_id, started=started, enabled=True
    )


# --------------------------------------------------------------------------
# T011 - naming
# --------------------------------------------------------------------------


def test_the_name_carries_the_pull_request_and_the_start_time(tmp_path):
    path = destination(tmp_path).path_for(1234, STARTED)
    assert path.endswith("llm-pr1234-20260917-143022.log")


def test_a_second_run_in_the_same_second_never_reuses_the_name(tmp_path):
    """FR-014a. run_id is pr.iteration and repeats, so the name must not."""
    first = destination(tmp_path).path_for(1234, STARTED)
    open(first, "w").close()
    second = destination(tmp_path).path_for(1234, STARTED)
    assert second != first
    assert second.endswith("llm-pr1234-20260917-143022-2.log")

    open(second, "w").close()
    third = destination(tmp_path).path_for(1234, STARTED)
    assert third.endswith("llm-pr1234-20260917-143022-3.log")


def test_a_relative_destination_is_refused(tmp_path):
    """A relative path here means it was resolved in the child, whose working
    directory is a fetched clone that is deleted moments later."""
    with pytest.raises(ValueError, match="absolute"):
        llm_log.LogDestination(".llm-logs", 10)


def test_keeping_zero_logs_would_delete_the_current_run(tmp_path):
    with pytest.raises(ValueError):
        llm_log.LogDestination(str(tmp_path), 0)


# --------------------------------------------------------------------------
# T010 - the format
# --------------------------------------------------------------------------


def test_the_head_names_the_run_the_pull_request_and_the_provider(tmp_path):
    session = session_at(tmp_path)
    session.head(provider="claude", model="a-model", agent_source="local working copy")
    text = open(session.path, encoding="utf-8").read()

    assert text.startswith("=== ai-review llm log ===")
    assert "run          : pending" in text
    assert "pull request : 1234" in text
    assert "provider     : claude / a-model" in text
    assert "started      : 2026-09-17 14:30:22" in text
    assert "agent source : local working copy" in text


def test_the_run_identifier_replaces_pending_once_it_is_known(tmp_path):
    session = session_at(tmp_path)
    session.head(provider="claude", model="a-model")
    session.set_run_id("1234.7")
    text = open(session.path, encoding="utf-8").read()

    assert "run          : 1234.7" in text
    assert "pending" not in text


def test_an_entry_carries_its_position_attempt_and_both_bodies(tmp_path):
    session = session_at(tmp_path)
    session.record(record(index=2, chunk=2, attempt=2, prompt="P" * 40))
    text = open(session.path, encoding="utf-8").read()

    assert "--- exchange 2 of 3 | chunk 2 of 3 | attempt 2 ---" in text
    assert "sent     : 2026-09-17 14:30:23" in text
    assert "prompt   : 40 characters" in text
    assert "outcome  : ok in 8,431 ms | response 16 characters" in text
    assert "P" * 40 in text
    assert '{"findings": []}' in text


def test_bodies_are_written_verbatim_so_a_prompt_can_be_replayed(tmp_path):
    """FR-012, FR-015a. Nothing escaped, quoted, indented, or truncated."""
    awkward = 'line one\n  indented "quoted" \\backslash\n{"json": true}\n=== not a rule'
    session = session_at(tmp_path)
    session.record(record(prompt=awkward, response=awkward))
    text = open(session.path, encoding="utf-8").read()

    assert text.count(awkward) == 2


def test_a_large_prompt_is_never_truncated(tmp_path):
    """FR-015. The checklist corpus repeats in every chunk; that is accepted."""
    huge = "x" * 150_000
    session = session_at(tmp_path)
    session.record(record(prompt=huge))
    assert huge in open(session.path, encoding="utf-8").read()


def test_the_foot_states_the_count_and_the_outcome(tmp_path):
    session = session_at(tmp_path)
    session.record(record())
    session.record(record(index=2, chunk=2))
    session.close("complete")
    text = open(session.path, encoding="utf-8").read()

    assert "=== end | 2 exchanges | outcome complete ===" in text


def test_one_exchange_is_not_pluralised(tmp_path):
    session = session_at(tmp_path)
    session.record(record())
    session.close("complete")
    assert "| 1 exchange |" in open(session.path, encoding="utf-8").read()


def test_entries_are_on_disk_before_the_next_call_begins(tmp_path):
    """FR-010a. A run that is killed keeps every exchange that finished."""
    session = session_at(tmp_path)
    session.record(record())
    assert "exchange 1 of 3" in open(session.path, encoding="utf-8").read()
    session.record(record(index=2, chunk=2))
    assert "exchange 2 of 3" in open(session.path, encoding="utf-8").read()


# --------------------------------------------------------------------------
# T037 - a run that never finishes
# --------------------------------------------------------------------------


def test_a_killed_run_leaves_a_readable_file_with_no_summary(tmp_path):
    """FR-010b, SC-007a. The missing summary is the signal."""
    session = session_at(tmp_path)
    session.head(provider="claude", model="a-model")
    session.record(record())
    session.record(record(index=2, chunk=2))
    # No close() - the process died here.
    text = open(session.path, encoding="utf-8").read()

    assert "exchange 1 of 3" in text
    assert "exchange 2 of 3" in text
    assert "=== end" not in text


# --------------------------------------------------------------------------
# T036 - failures
# --------------------------------------------------------------------------


def test_a_failed_exchange_records_the_reason_in_place_of_a_response(tmp_path):
    session = session_at(tmp_path)
    session.record(
        record(
            outcome="failed",
            response="",
            failure="the AI provider was unreachable after 3 attempts (ConnectionError)",
            elapsed_ms=184003,
        )
    )
    text = open(session.path, encoding="utf-8").read()

    assert "outcome  : failed in 184,003 ms" in text
    assert "unreachable after 3 attempts" in text


def test_a_failure_with_no_stated_reason_is_refused():
    """Silence about a failure is the defect the conventions name."""
    with pytest.raises(ValueError, match="state why"):
        record(outcome="failed", response="", failure="")


def test_an_unknown_outcome_is_refused():
    with pytest.raises(ValueError):
        record(outcome="maybe")


def test_a_third_attempt_is_refused():
    """parse_with_retry sends at most two."""
    with pytest.raises(ValueError):
        record(attempt=3)


def test_a_chunk_outside_the_run_is_refused():
    with pytest.raises(ValueError):
        record(chunk=4, chunk_total=3)


# --------------------------------------------------------------------------
# T025 - off by default
# --------------------------------------------------------------------------


class FakeConfig:
    def __init__(self, directory, llm_log=False, keep=10, pr_id=1234):
        self.llm_log = llm_log
        self.llm_log_dir = directory
        self.llm_log_keep = keep
        self.tfs_pr_id = pr_id


def test_logging_off_creates_nothing_at_all(tmp_path, capsys):
    """FR-002, SC-003. Not even an empty directory."""
    target = tmp_path / "logs"
    session = llm_log.open_session(FakeConfig(str(target), llm_log=False))

    session.head(provider="claude", model="a-model")
    session.record(record())
    session.close("complete")

    assert not target.exists()
    assert capsys.readouterr().out == ""


def test_logging_on_creates_the_directory_and_announces_the_file(tmp_path, capsys):
    target = tmp_path / "logs"
    session = llm_log.open_session(
        FakeConfig(str(target), llm_log=True), provider="claude", model="a-model"
    )
    out = capsys.readouterr().out

    assert session.enabled
    assert target.exists()
    assert "llm log: " in out
    assert "removed no older logs (keeping 10)" in out


def test_a_destination_that_cannot_be_written_disables_logging_quietly(
    tmp_path, capsys, monkeypatch
):
    """FR-018. The operator loses their log, never their review."""

    def _refuse(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(llm_log.os, "makedirs", _refuse)
    session = llm_log.open_session(FakeConfig(str(tmp_path / "logs"), llm_log=True))

    assert not session.enabled
    assert "llm log: disabled" in capsys.readouterr().out
    # And nothing raises when the run carries on using it.
    session.record(record())
    session.close("complete")


def test_a_write_failure_is_stated_once_and_then_the_session_goes_quiet(
    tmp_path, capsys, monkeypatch
):
    """D9. One line, not one per chunk."""
    session = session_at(tmp_path)

    def _refuse(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(llm_log, "_write", _refuse)
    session.record(record())
    session.record(record(index=2, chunk=2))
    session.record(record(index=3, chunk=3))

    assert capsys.readouterr().out.count("llm log: could not") == 1
    assert not session.enabled


# --------------------------------------------------------------------------
# Redaction, at the unit level. The contract test is the gate.
# --------------------------------------------------------------------------


def test_every_body_passes_through_the_redaction_registry(tmp_path):
    cfg.clear_secrets()
    cfg.register_secret("pat-secret-value")
    try:
        session = session_at(tmp_path)
        session.record(
            record(
                prompt="a diff containing pat-secret-value inline",
                response="the model repeated pat-secret-value back",
            )
        )
        text = open(session.path, encoding="utf-8").read()
    finally:
        cfg.clear_secrets()

    assert "pat-secret-value" not in text
    assert text.count("***") == 2
