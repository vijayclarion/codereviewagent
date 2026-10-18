"""T068 / T069 (feature 007) - every send is in the log, the totals add up,
and the new lines are redacted like the old ones (FR-021-FR-024, SC-006)."""

import json

import pytest

from review_agent import github_client, prompt_builder
from review_agent import main as main_module
from review_agent.config import load_config, register_secret
from review_agent.llm_adapter import LlmText, SendRecord, TokenUsage
from tests.fakes_github import FakeGitHubClient
from tests.fixtures import cross_file_cart as cart


class _Provider:
    """Returns LlmText with `.sends`; the first chunk call was retried once."""

    def __init__(self, echo=""):
        self.calls = 0
        self.sends = 0
        self.input = 0
        self.output = 0
        self.echo = echo

    def __call__(self, prompt, config=None, **_kwargs):
        self.calls += 1
        if prompt.startswith(prompt_builder.SYNTHESIS_ROLE):
            body = json.dumps(dict(cart.SYNTHESIS_RESPONSE, summary="whole " + self.echo))
        else:
            body = json.dumps(cart.chunk_response(False))
        usage = TokenUsage(1000 + self.calls, 100 + self.calls)
        sends = []
        if self.calls == 1:
            sends.append(SendRecord(1, "retried", "ReadTimeout", 30_000))
        sends.append(SendRecord(len(sends) + 1, "ok", "", 2000, usage, body))
        self.sends += len(sends)
        self.input += usage.input
        self.output += usage.output
        return LlmText(body, usage=usage, sends=sends)


@pytest.fixture
def run(github_env, monkeypatch, tmp_path, capsys):
    def _run(provider, logging=True):
        monkeypatch.setenv("STORY_SOURCE", "none")
        monkeypatch.setenv("LLM_MAX_CHUNK_LINES", "1")  # several chunks, so a synthesis call
        monkeypatch.setenv("LLM_PRICE_INPUT_PER_MTOK", "3")
        monkeypatch.setenv("LLM_PRICE_OUTPUT_PER_MTOK", "15")
        if logging:
            monkeypatch.setenv("LLM_LOG", "true")
            monkeypatch.setenv("LLM_LOG_DIR", str(tmp_path / "logs"))
        fake = FakeGitHubClient(files=cart.FILES, contents=cart.CONTENTS, linked=())
        monkeypatch.setattr(github_client, "make_github_platform", lambda config: fake)
        monkeypatch.setattr(main_module, "call_llm", provider)
        report = main_module.run_review(load_config(dry_run_override=True), main_module.PhaseLog(enabled=True))
        out = capsys.readouterr().out
        logs = sorted((tmp_path / "logs").glob("*.log")) if logging else []
        return report, out, logs[0].read_text(encoding="utf-8") if logs else ""

    return _run


def test_every_send_including_the_retry_and_the_synthesis_is_an_entry(run):
    provider = _Provider()
    report, _out, text = run(provider)
    assert report.synthesis == "complete"
    assert text.count("--- exchange ") == provider.sends
    assert provider.sends == provider.calls + 1  # one transport retry
    assert "| attempt 1 | send 2 of 3 ---" in text
    assert "ReadTimeout - retried" in text
    assert text.count("| synthesis |") == 1


def test_totals_equal_the_sum_of_reported_usage(run):
    provider = _Provider()
    report, out, text = run(provider)
    cost = provider.input / 1e6 * 3 + provider.output / 1e6 * 15
    expected = (
        f"input {provider.input:,} · output {provider.output:,} · cost {cost:.4f} USD"
        f" · partial — {provider.calls} of {provider.sends} calls reported usage"
    )
    assert f"usage    : {expected}" in text
    assert f"llm usage: {expected}" in out
    assert report.usage.input_tokens == provider.input
    assert "tokens_in=" in out and "cost=" in out


def test_usage_reaches_the_console_with_logging_off(run):
    provider = _Provider()
    _report, out, text = run(provider, logging=False)
    assert text == ""
    assert "llm usage: input " in out


def test_new_lines_are_redacted(run, monkeypatch):
    secret = "model-echoed-secret-123"
    register_secret(secret)
    monkeypatch.setenv("LLM_MODEL", f"model-{secret}")
    provider = _Provider(echo=secret)
    _report, out, text = run(provider)
    assert secret not in text
    assert secret not in out
    assert "model    : claude / model-***" in text
