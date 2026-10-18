"""T023 (feature 006) - no credential reaches the log file. THE GATE.

`CLAUDE.md` carries the warning this test enforces:

    A new output destination must route through `redact` too - a file writer
    that calls `json.dump` directly bypasses the only thing stopping a token
    escaping.

This feature is that new output destination, and it is a worse one than the
console: the console scrolls away, a log file sits on disk holding the pull
request's whole diff and the entire checklist corpus until someone reads it.

The realistic leak is never a deliberate write of a token. It is a diff hunk
that touches a configuration file, or a model that repeats back what it was
given. So this asserts on the *values*, through the *real* write path, for every
credential the agent accepts - the same shape as `test_no_secrets_leak.py`, for
the same reason.
"""

import pytest

from review_agent import config as cfg
from review_agent import llm_log
from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import FakeTfsClient, fake_llm

#: The three values `base_env` configures: the reading token, the provider key,
#: and the posting token. All three are registered by `load_config`.
SECRETS = ("pat-secret-value", "llm-secret-value", "post-secret-value")


@pytest.fixture
def logged_run(base_env, monkeypatch, tmp_path):
    """A real review, writing a real log, through the real write path."""

    def _run(response):
        monkeypatch.setenv("LLM_LOG", "true")
        monkeypatch.setenv("LLM_LOG_DIR", str(tmp_path / "logs"))
        monkeypatch.setattr(main_module, "TfsClient", lambda config: FakeTfsClient())
        monkeypatch.setattr(main_module, "call_llm", fake_llm(response))
        config = load_config(dry_run_override=True)
        main_module.run_review(config, main_module.PhaseLog(enabled=False))
        logs = list((tmp_path / "logs").glob("*.log"))
        assert len(logs) == 1
        return logs[0].read_text(encoding="utf-8")

    return _run


def test_a_credential_echoed_by_the_model_never_reaches_the_file(logged_run):
    """The model is handed a diff and repeats part of it back. It happens."""
    text = logged_run(f"here is your token {SECRETS[0]} and key {SECRETS[1]}")

    for secret in SECRETS:
        assert secret not in text
    assert "***" in text


def test_every_configured_credential_is_redacted(logged_run):
    leaky = " ".join(f"<{s}>" for s in SECRETS)
    text = logged_run(leaky)

    for secret in SECRETS:
        assert secret not in text, f"{secret} reached the log file"


def test_a_credential_inside_a_prompt_never_reaches_the_file(tmp_path):
    """The prompt carries the diff, and a diff can touch a configuration file."""
    cfg.clear_secrets()
    for secret in SECRETS:
        cfg.register_secret(secret)
    try:
        destination = llm_log.LogDestination(str(tmp_path), 10)
        session = llm_log.LogSession(
            path=destination.path_for(1, llm_log.datetime.now()),
            pr_id=1,
            enabled=True,
        )
        session.head(provider="claude", model="a-model")
        session.record(
            llm_log.ExchangeRecord(
                index=1,
                chunk=1,
                chunk_total=1,
                attempt=1,
                sent_at="2026-09-17 14:30:23",
                elapsed_ms=1,
                prompt="\n".join(f"+ SECRET={s}" for s in SECRETS),
                outcome="ok",
                response="{}",
            )
        )
        session.close("complete")
        text = open(session.path, encoding="utf-8").read()
    finally:
        cfg.clear_secrets()

    for secret in SECRETS:
        assert secret not in text


def test_a_credential_in_a_failure_reason_never_reaches_the_file(tmp_path):
    """An exception message is the classic accidental carrier."""
    cfg.clear_secrets()
    cfg.register_secret(SECRETS[1])
    try:
        destination = llm_log.LogDestination(str(tmp_path), 10)
        session = llm_log.LogSession(
            path=destination.path_for(1, llm_log.datetime.now()),
            pr_id=1,
            enabled=True,
        )
        session.record(
            llm_log.ExchangeRecord(
                index=1,
                chunk=1,
                chunk_total=1,
                attempt=1,
                sent_at="2026-09-17 14:30:23",
                elapsed_ms=1,
                prompt="anything",
                outcome="failed",
                failure=f"rejected the credential {SECRETS[1]}",
            )
        )
        text = open(session.path, encoding="utf-8").read()
    finally:
        cfg.clear_secrets()

    assert SECRETS[1] not in text
    assert "rejected the credential ***" in text


def test_there_is_exactly_one_function_that_writes_to_the_file():
    """The structural half of the guarantee.

    Redaction is safe because there is one door, not because every author
    remembers. If a second `open(...)` for writing appears in this module, that
    reasoning collapses - so the count is asserted rather than assumed.
    """
    import ast
    import inspect

    source = inspect.getsource(llm_log)
    tree = ast.parse(source)

    class Opens(ast.NodeVisitor):
        """Attribute each `open(...)` to its innermost enclosing function."""

        def __init__(self):
            self.stack = []
            self.found = []

        def visit_FunctionDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node):
            if getattr(node.func, "id", "") == "open":
                self.found.append(self.stack[-1] if self.stack else "<module>")
            self.generic_visit(node)

    opens = Opens()
    opens.visit(tree)

    # Exactly two: `_write` writes, and the `_resolve` closure inside
    # `set_run_id` reads the header back so `pending` can be replaced.
    # Anything else is a second door, and the redaction guarantee rests on
    # there being only one.
    assert sorted(opens.found) == ["_resolve", "_write"], (
        f"unexpected file access in llm_log.py: {sorted(opens.found)}"
    )
    assert "redact(text)" in source, "the one write path must redact"
