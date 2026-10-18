"""T067 (feature 007) - the new log lines, totals, and failure isolation.

Every string tests/unit/test_llm_log.py and tests/integration/test_llm_log_run.py
assert is still produced (research E9); those files are untouched.
"""

import pytest

from review_agent import llm_log
from review_agent.llm_log import ExchangeRecord, LogSession, RunUsage


def _record(**overrides):
    fields = dict(index=1, chunk=1, chunk_total=1, attempt=1, sent_at="2026-10-18 14:02:11",
                  elapsed_ms=8431, prompt="p" * 40, outcome="ok", response="r" * 16)
    fields.update(overrides)
    return ExchangeRecord(**fields)


@pytest.fixture
def session(tmp_path):
    path = tmp_path / "run.log"
    path.write_text("", encoding="utf-8")
    return LogSession(path=str(path), pr_id=12, enabled=True), path


def test_first_send_keeps_the_006_lines_and_adds_model_and_tokens(session):
    s, path = session
    s.record(_record(provider="claude", model="a-model", input_tokens=1200, output_tokens=340))
    text = path.read_text(encoding="utf-8")
    assert "| chunk 1 of 1 | attempt 1 ---" in text
    assert "prompt   : 40 characters" in text
    assert "outcome  : ok in 8,431 ms | response 16 characters" in text
    assert "model    : claude / a-model" in text
    assert "tokens   : input 1,200 | output 340 (reported by provider)" in text
    assert "send " not in text.splitlines()[0]


def test_unreported_tokens_say_so(session):
    s, path = session
    s.record(_record())
    assert "tokens   : not reported" in path.read_text(encoding="utf-8")


def test_a_resend_header_names_the_send(session):
    s, path = session
    s.record(_record(send=2, outcome="failed", response="", failure="HTTP 429 - retried"))
    assert "| attempt 1 | send 2 of 3 ---" in path.read_text(encoding="utf-8")


def test_synthesis_header(session):
    s, path = session
    s.record(_record(index=3, kind="synthesis", chunk=2, chunk_total=2))
    assert "--- exchange 3 | synthesis | attempt 1 ---" in path.read_text(encoding="utf-8")


def test_usage_line_comes_immediately_before_the_unchanged_end_line(session):
    s, path = session
    usage = RunUsage(3.0, 15.0)
    usage.add(1_000_000, 100_000)
    s.record(_record())
    s.close("complete", usage)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[-2] == "usage    : input 1,000,000 · output 100,000 · cost 4.5000 USD"
    assert lines[-1].startswith("=== end | 1 exchange | outcome complete ===")


def test_close_without_usage_is_exactly_006(session):
    s, path = session
    s.close("complete")
    assert path.read_text(encoding="utf-8").startswith("=== end | 0 exchanges | outcome complete ===")


@pytest.mark.parametrize(
    "prices, calls, expected",
    [
        ((None, None), [(10, 2)], "input 10 · output 2 · cost not estimated (no LLM_PRICE_* set)"),
        ((1.0, 2.0), [(10, 2), (None, None)],
         "input 10 · output 2 · cost 0.0000 USD · partial — 1 of 2 calls reported usage"),
        ((1.0, 2.0), [], "no exchange"),
    ],
)
def test_run_usage_describe(prices, calls, expected):
    usage = RunUsage(*prices)
    for pair in calls:
        usage.add(*pair)
    assert usage.describe() == expected


def test_a_record_that_cannot_be_built_disables_the_log_without_raising(session, capsys):
    s, _path = session
    s._guarded(lambda: s.record(_record(send=9)), "build a log entry")
    assert not s.enabled
    out = capsys.readouterr().out
    assert out.count("llm log: could not build a log entry - ValueError") == 1


def test_any_exception_in_a_write_is_contained(session, monkeypatch, capsys):
    s, _path = session

    def _boom(*_a, **_k):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(llm_log, "_write", _boom)
    s.record(_record())  # must not raise
    assert not s.enabled
    assert "RuntimeError: disk on fire" in capsys.readouterr().out


def test_invariants():
    with pytest.raises(ValueError):
        _record(kind="other")
    with pytest.raises(ValueError):
        _record(send=0)
    _record(kind="synthesis", chunk=5, chunk_total=2)  # chunk position not checked for synthesis
