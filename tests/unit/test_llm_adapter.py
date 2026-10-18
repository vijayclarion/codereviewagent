"""T077, T080 - every provider behind one signature (FR-033).

Swapping provider must be a configuration change. These tests are what make that
claim checkable: they assert the request shape and the extraction path per
provider, all through the same `call_llm`.
"""

import json

import pytest
import responses

from review_agent import llm_adapter
from review_agent.config import load_config
from review_agent.errors import DegradedReview, SetupFailure


def _config(base_env, monkeypatch, provider, **extra):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LLM_MODEL", "test-model")
    for key, value in extra.items():
        monkeypatch.setenv(key, value)
    return load_config()


# -- claude -----------------------------------------------------------------


@responses.activate
def test_claude_request_and_extraction(base_env, monkeypatch):
    config = _config(base_env, monkeypatch, "claude")
    responses.add(
        responses.POST,
        "https://api.anthropic.com/v1/messages",
        json={"content": [{"type": "text", "text": "hello from claude"}]},
        status=200,
    )
    assert llm_adapter.call_llm("prompt", config) == "hello from claude"

    request = responses.calls[0].request
    assert request.headers["x-api-key"] == "llm-secret-value"
    assert request.headers["anthropic-version"]
    body = json.loads(request.body)
    assert body["model"] == "test-model"
    assert body["messages"][0]["content"] == "prompt"
    assert "max_tokens" in body


@responses.activate
def test_claude_concatenates_multiple_text_blocks(base_env, monkeypatch):
    config = _config(base_env, monkeypatch, "claude")
    responses.add(
        responses.POST,
        "https://api.anthropic.com/v1/messages",
        json={"content": [{"text": "part one "}, {"text": "part two"}]},
        status=200,
    )
    assert llm_adapter.call_llm("p", config) == "part one part two"


# -- openai -----------------------------------------------------------------


@responses.activate
def test_openai_request_and_extraction(base_env, monkeypatch):
    config = _config(base_env, monkeypatch, "openai")
    responses.add(
        responses.POST,
        "https://api.openai.com/v1/chat/completions",
        json={"choices": [{"message": {"content": "hello from openai"}}]},
        status=200,
    )
    assert llm_adapter.call_llm("prompt", config) == "hello from openai"

    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer llm-secret-value"
    assert json.loads(request.body)["temperature"] == 0


# -- azure ------------------------------------------------------------------


@responses.activate
def test_azure_uses_the_deployment_path_and_api_key_header(base_env, monkeypatch):
    config = _config(
        base_env, monkeypatch, "azure", LLM_BASE_URL="https://my.openai.azure.com"
    )
    responses.add(
        responses.POST,
        "https://my.openai.azure.com/openai/deployments/test-model/chat/completions",
        json={"choices": [{"message": {"content": "hello from azure"}}]},
        status=200,
    )
    assert llm_adapter.call_llm("prompt", config) == "hello from azure"
    assert responses.calls[0].request.headers["api-key"] == "llm-secret-value"


def test_azure_without_a_base_url_is_a_configuration_error(base_env, monkeypatch):
    from review_agent.errors import MissingConfiguration

    monkeypatch.setenv("LLM_PROVIDER", "azure")
    with pytest.raises(MissingConfiguration) as exc:
        load_config()
    assert "LLM_BASE_URL" in " ".join(exc.value.problems)


# -- ollama -----------------------------------------------------------------


@responses.activate
def test_ollama_is_keyless_and_uses_the_configured_base_url(base_env, monkeypatch):
    """T080: FR-005 - a keyless internal model must need no LLM_API_KEY."""
    monkeypatch.delenv("LLM_API_KEY")
    config = _config(
        base_env, monkeypatch, "ollama", LLM_BASE_URL="http://localhost:11434"
    )
    assert config.llm_api_key == ""
    responses.add(
        responses.POST,
        "http://localhost:11434/api/generate",
        json={"response": "hello from ollama"},
        status=200,
    )
    assert llm_adapter.call_llm("prompt", config) == "hello from ollama"

    request = responses.calls[0].request
    assert "Authorization" not in request.headers
    assert "x-api-key" not in request.headers


# -- base url override ------------------------------------------------------


@responses.activate
def test_base_url_overrides_the_provider_default(base_env, monkeypatch):
    """A gateway in front of the provider must need no code change."""
    config = _config(
        base_env, monkeypatch, "claude", LLM_BASE_URL="https://gateway.internal/anthropic"
    )
    responses.add(
        responses.POST,
        "https://gateway.internal/anthropic/v1/messages",
        json={"content": [{"text": "via gateway"}]},
        status=200,
    )
    assert llm_adapter.call_llm("p", config) == "via gateway"


# -- failure handling -------------------------------------------------------


@responses.activate
def test_a_rejected_credential_is_a_setup_failure(base_env, monkeypatch):
    config = _config(base_env, monkeypatch, "claude")
    responses.add(responses.POST, "https://api.anthropic.com/v1/messages", status=401)
    with pytest.raises(SetupFailure) as exc:
        llm_adapter.call_llm("p", config)
    assert "LLM_API_KEY" in exc.value.remedy


@responses.activate
def test_an_unknown_model_is_a_setup_failure(base_env, monkeypatch):
    config = _config(base_env, monkeypatch, "claude")
    responses.add(responses.POST, "https://api.anthropic.com/v1/messages", status=404)
    with pytest.raises(SetupFailure) as exc:
        llm_adapter.call_llm("p", config)
    assert "LLM_MODEL" in exc.value.remedy


@responses.activate
def test_a_server_error_degrades_rather_than_failing_the_build(base_env, monkeypatch):
    config = _config(base_env, monkeypatch, "claude")
    for _ in range(3):
        responses.add(responses.POST, "https://api.anthropic.com/v1/messages", status=503)
    with pytest.raises(DegradedReview):
        llm_adapter.call_llm("p", config, sleep=lambda _s: None)


@responses.activate
def test_transient_failures_are_retried_then_succeed(base_env, monkeypatch):
    config = _config(base_env, monkeypatch, "claude")
    responses.add(responses.POST, "https://api.anthropic.com/v1/messages", status=503)
    responses.add(
        responses.POST,
        "https://api.anthropic.com/v1/messages",
        json={"content": [{"text": "recovered"}]},
        status=200,
    )
    assert llm_adapter.call_llm("p", config, sleep=lambda _s: None) == "recovered"
    assert len(responses.calls) == 2


@responses.activate
def test_an_empty_response_degrades(base_env, monkeypatch):
    config = _config(base_env, monkeypatch, "claude")
    responses.add(
        responses.POST, "https://api.anthropic.com/v1/messages",
        json={"content": [{"text": "   "}]}, status=200,
    )
    with pytest.raises(DegradedReview) as exc:
        llm_adapter.call_llm("p", config)
    assert "empty" in str(exc.value)


@responses.activate
def test_a_non_json_body_degrades(base_env, monkeypatch):
    config = _config(base_env, monkeypatch, "claude")
    responses.add(
        responses.POST, "https://api.anthropic.com/v1/messages",
        body="<html>gateway error</html>", status=200,
    )
    with pytest.raises(DegradedReview):
        llm_adapter.call_llm("p", config)
