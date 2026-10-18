"""T066 (feature 007) - the provider's own token counts, and every send."""

import pytest
import requests
import responses

from review_agent.errors import DegradedReview, SetupFailure
from review_agent.llm_adapter import LlmText, SendRecord, TokenUsage, call_llm


class _Cfg:
    def __init__(self, provider="claude", base=""):
        self.llm_provider = provider
        self.llm_model = "a-model"
        self.llm_api_key = "key-secret-value"
        self.llm_base_url = base
        self.llm_max_output_tokens = 8192


ANTHROPIC = "https://api.anthropic.com/v1/messages"
OPENAI = "https://api.openai.com/v1/chat/completions"


def _call(cfg, **kwargs):
    return call_llm("prompt", cfg, sleep=lambda _s: None, **kwargs)


@responses.activate
def test_claude_usage_and_the_result_is_still_a_str():
    responses.add(responses.POST, ANTHROPIC, json={
        "content": [{"type": "text", "text": "{}"}],
        "usage": {"input_tokens": 1200, "output_tokens": 340},
    })
    text = _call(_Cfg())
    assert isinstance(text, str) and isinstance(text, LlmText)
    assert text == "{}"
    assert text.usage == TokenUsage(1200, 340)
    assert [s.outcome for s in text.sends] == ["ok"]
    assert text.sends[0].usage == TokenUsage(1200, 340)


@responses.activate
@pytest.mark.parametrize("provider, base", [("openai", ""), ("azure", "https://az.example")])
def test_openai_and_azure_usage(provider, base):
    url = OPENAI if provider == "openai" else (
        "https://az.example/openai/deployments/a-model/chat/completions"
    )
    responses.add(responses.POST, url, json={
        "choices": [{"message": {"content": "{}"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 3},
    })
    assert _call(_Cfg(provider, base)).usage == TokenUsage(10, 3)


@responses.activate
def test_ollama_usage():
    responses.add(responses.POST, "http://ollama.local/api/generate",
                  json={"response": "{}", "prompt_eval_count": 7, "eval_count": 2})
    assert _call(_Cfg("ollama", "http://ollama.local")).usage == TokenUsage(7, 2)


@responses.activate
def test_absent_usage_is_none_never_zero():
    responses.add(responses.POST, ANTHROPIC, json={"content": [{"type": "text", "text": "{}"}]})
    text = _call(_Cfg())
    assert text.usage is None and text.sends[0].usage is None


@responses.activate
def test_a_retried_send_is_its_own_record():
    responses.add(responses.POST, ANTHROPIC, status=429)
    responses.add(responses.POST, ANTHROPIC, json={
        "content": [{"type": "text", "text": "{}"}], "usage": {"input_tokens": 5, "output_tokens": 1},
    })
    text = _call(_Cfg())
    assert [(s.number, s.outcome, s.detail) for s in text.sends] == [
        (1, "retried", "HTTP 429"), (2, "ok", ""),
    ]
    assert text.sends[0].usage is None and text.usage == TokenUsage(5, 1)


@responses.activate
def test_three_timeouts_degrade_and_carry_all_three_sends():
    for _ in range(3):
        responses.add(responses.POST, ANTHROPIC, body=requests.Timeout("slow"))
    with pytest.raises(DegradedReview) as caught:
        _call(_Cfg())
    assert [(s.outcome, s.detail) for s in caught.value.sends] == [
        ("retried", "Timeout"), ("retried", "Timeout"), ("failed", "Timeout"),
    ]


@responses.activate
def test_a_rejected_credential_carries_its_send():
    responses.add(responses.POST, ANTHROPIC, status=401)
    with pytest.raises(SetupFailure) as caught:
        _call(_Cfg())
    assert [(s.outcome, s.detail) for s in caught.value.sends] == [("failed", "HTTP 401")]


@responses.activate
def test_max_tokens_comes_from_configuration():
    import json

    responses.add(responses.POST, ANTHROPIC, json={"content": [{"type": "text", "text": "{}"}]})
    cfg = _Cfg()
    cfg.llm_max_output_tokens = 1234
    _call(cfg)
    assert json.loads(responses.calls[0].request.body)["max_tokens"] == 1234


def test_send_record_invariants():
    with pytest.raises(ValueError):
        SendRecord(1, "retried")  # a send that did not succeed must say why
    with pytest.raises(ValueError):
        SendRecord(1, "maybe", "x")
