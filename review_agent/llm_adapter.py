"""The only module that knows a provider's wire format (FR-032, FR-033).

`call_llm` returns raw model text. Everything downstream is provider-blind, so
switching provider is a configuration change and one branch here - never a change
to the reviewing logic. That boundary is enforced by
tests/contract/test_import_boundaries.py.

Raw `requests` rather than provider SDKs: the deciding factor is the self-hosted
build agent, where three dependencies with no compiled extensions install
reliably and an SDK's transitive tree may not (research R1).
"""

import time
from dataclasses import dataclass

import requests

from .errors import DegradedReview, SetupFailure

TIMEOUT = 180
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = (1, 2, 4)
RETRY_STATUSES = (429, 500, 502, 503, 504)

ANTHROPIC_VERSION = "2023-06-01"
#: Feature 007: was 4096. A whole-PR call returns more findings than a chunk did,
#: and a truncated JSON response degrades the entire run (research D8).
DEFAULT_MAX_TOKENS = 8192

_DEFAULT_BASE_URLS = {
    "claude": "https://api.anthropic.com",
    "openai": "https://api.openai.com",
}


def _base_url(config):
    if config.llm_base_url:
        return config.llm_base_url.rstrip("/")
    default = _DEFAULT_BASE_URLS.get(config.llm_provider)
    if not default:
        raise SetupFailure(
            f"LLM_BASE_URL is required for LLM_PROVIDER={config.llm_provider}",
            remedy="set LLM_BASE_URL",
        )
    return default


def _request_for(config, prompt):
    """Build (url, headers, body, extractor) for the configured provider."""
    provider = config.llm_provider
    base = _base_url(config)

    if provider == "claude":
        return (
            f"{base}/v1/messages",
            {
                "x-api-key": config.llm_api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            {
                "model": config.llm_model,
                "max_tokens": int(getattr(config, "llm_max_output_tokens", DEFAULT_MAX_TOKENS)),
                "messages": [{"role": "user", "content": prompt}],
            },
            _extract_anthropic,
        )

    if provider in ("openai", "azure"):
        if provider == "azure":
            url = (
                f"{base}/openai/deployments/{config.llm_model}/chat/completions"
                f"?api-version=2024-02-01"
            )
            headers = {"api-key": config.llm_api_key, "content-type": "application/json"}
        else:
            url = f"{base}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {config.llm_api_key}",
                "content-type": "application/json",
            }
        return (
            url,
            headers,
            {
                "model": config.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            _extract_openai,
        )

    if provider == "ollama":
        return (
            f"{base}/api/generate",
            {"content-type": "application/json"},
            {"model": config.llm_model, "prompt": prompt, "stream": False},
            _extract_ollama,
        )

    raise SetupFailure(
        f"unsupported LLM_PROVIDER: {provider}",
        remedy="use one of claude, openai, azure, ollama",
    )


def _extract_anthropic(payload):
    blocks = (payload or {}).get("content") or []
    return "".join(b.get("text", "") for b in blocks if isinstance(b, dict))


def _extract_openai(payload):
    choices = (payload or {}).get("choices") or []
    if not choices:
        return ""
    return ((choices[0] or {}).get("message") or {}).get("content", "") or ""


def _extract_ollama(payload):
    return (payload or {}).get("response", "") or ""


@dataclass(frozen=True)
class TokenUsage:
    """What the provider says a call consumed. Never estimated (FR-022)."""

    input: object = None
    output: object = None

    @property
    def reported(self):
        return self.input is not None or self.output is not None


@dataclass(frozen=True)
class SendRecord:
    """One HTTP attempt inside `call_llm` (feature 007, D14)."""

    number: int
    outcome: str  # "ok" | "retried" | "failed"
    detail: str = ""
    elapsed_ms: int = 0
    usage: object = None
    text: str = ""

    def __post_init__(self):
        if self.outcome not in ("ok", "retried", "failed"):
            raise ValueError(f"unknown send outcome: {self.outcome!r}")
        if self.outcome != "ok" and not self.detail:
            raise ValueError("a send that did not succeed must say why")


class LlmText(str):
    """The model's text - a `str`, so every caller and every test fake keeps
    working - carrying what the provider reported and every send it took.

    Feature 007 (D14): usage rides on the return value rather than on a new
    parameter or return type, because 22 tests replace `call_llm` with fakes
    that return plain strings, one of them with no `**kwargs` at all.
    """

    def __new__(cls, text, usage=None, sends=()):
        value = super().__new__(cls, text)
        value.usage = usage
        value.sends = tuple(sends)
        return value


def _number(value):
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _usage(provider, payload):
    """The provider's own token counts. Only this module knows where they live."""
    data = payload or {}
    if provider == "claude":
        usage = data.get("usage") or {}
        found = TokenUsage(_number(usage.get("input_tokens")), _number(usage.get("output_tokens")))
    elif provider in ("openai", "azure"):
        usage = data.get("usage") or {}
        found = TokenUsage(_number(usage.get("prompt_tokens")), _number(usage.get("completion_tokens")))
    elif provider == "ollama":
        found = TokenUsage(_number(data.get("prompt_eval_count")), _number(data.get("eval_count")))
    else:
        found = TokenUsage()
    return found if found.reported else None


def _with_sends(exc, sends):
    exc.sends = tuple(sends)
    return exc


def call_llm(prompt, config, session=None, sleep=time.sleep):
    """Send one prompt, return the model's raw text (an `LlmText`).

    A provider that cannot be reached is a degraded review, not a setup failure:
    an outage must not gate a merge (FR-029).
    """
    url, headers, body, extract = _request_for(config, prompt)
    http = session or requests
    last_detail = None
    sends = []

    def _record(number, outcome, detail, started, usage=None, text=""):
        sends.append(
            SendRecord(number, outcome, detail, int((time.monotonic() - started) * 1000), usage, text)
        )

    for attempt in range(RETRY_ATTEMPTS):
        number = attempt + 1
        started = time.monotonic()
        try:
            response = http.post(url, headers=headers, json=body, timeout=TIMEOUT)
        except requests.RequestException as exc:
            last_detail = type(exc).__name__
            if attempt < RETRY_ATTEMPTS - 1:
                _record(number, "retried", last_detail, started)
                sleep(RETRY_BACKOFF[attempt])
                continue
            _record(number, "failed", last_detail, started)
            raise _with_sends(
                DegradedReview(
                    f"the AI provider was unreachable after {RETRY_ATTEMPTS} attempts "
                    f"({last_detail})"
                ),
                sends,
            )

        status = response.status_code
        if status in RETRY_STATUSES and attempt < RETRY_ATTEMPTS - 1:
            _record(number, "retried", f"HTTP {status}", started)
            sleep(_retry_after(response, attempt))
            continue

        if status in (401, 403):
            _record(number, "failed", f"HTTP {status}", started)
            raise _with_sends(
                SetupFailure(
                    f"the AI provider rejected the credential (HTTP {status})",
                    remedy="check LLM_API_KEY",
                ),
                sends,
            )
        if status == 404:
            _record(number, "failed", "HTTP 404", started)
            raise _with_sends(
                SetupFailure(
                    "the AI provider has no such model or endpoint (HTTP 404)",
                    remedy="check LLM_MODEL and LLM_BASE_URL",
                ),
                sends,
            )
        if status >= 400:
            _record(number, "failed", f"HTTP {status}", started)
            raise _with_sends(DegradedReview(f"the AI provider returned HTTP {status}"), sends)

        try:
            payload = response.json()
        except ValueError:
            _record(number, "failed", "non-JSON body", started)
            raise _with_sends(DegradedReview("the AI provider returned a non-JSON body"), sends)

        text = extract(payload)
        usage = _usage(config.llm_provider, payload)
        if not text.strip():
            _record(number, "failed", "empty response", started, usage)
            raise _with_sends(DegradedReview("the AI provider returned an empty response"), sends)
        _record(number, "ok", "", started, usage, text)
        return LlmText(text, usage=usage, sends=sends)

    raise _with_sends(
        DegradedReview(
            f"the AI provider was unreachable after {RETRY_ATTEMPTS} attempts ({last_detail})"
        ),
        sends,
    )


def _retry_after(response, attempt):
    header = response.headers.get("Retry-After") if hasattr(response, "headers") else None
    if header:
        try:
            return min(float(header), 30.0)
        except (TypeError, ValueError):
            pass
    return RETRY_BACKOFF[attempt]
