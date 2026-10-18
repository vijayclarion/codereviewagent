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

import requests

from .errors import DegradedReview, SetupFailure

TIMEOUT = 180
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = (1, 2, 4)
RETRY_STATUSES = (429, 500, 502, 503, 504)

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096

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
                "max_tokens": DEFAULT_MAX_TOKENS,
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


def call_llm(prompt, config, session=None, sleep=time.sleep):
    """Send one prompt, return the model's raw text.

    A provider that cannot be reached is a degraded review, not a setup failure:
    an outage must not gate a merge (FR-029).
    """
    url, headers, body, extract = _request_for(config, prompt)
    http = session or requests
    last_detail = None

    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = http.post(url, headers=headers, json=body, timeout=TIMEOUT)
        except requests.RequestException as exc:
            last_detail = type(exc).__name__
            if attempt < RETRY_ATTEMPTS - 1:
                sleep(RETRY_BACKOFF[attempt])
                continue
            raise DegradedReview(
                f"the AI provider was unreachable after {RETRY_ATTEMPTS} attempts "
                f"({last_detail})"
            )

        if response.status_code in RETRY_STATUSES and attempt < RETRY_ATTEMPTS - 1:
            sleep(_retry_after(response, attempt))
            continue

        if response.status_code in (401, 403):
            raise SetupFailure(
                f"the AI provider rejected the credential (HTTP {response.status_code})",
                remedy="check LLM_API_KEY",
            )
        if response.status_code == 404:
            raise SetupFailure(
                "the AI provider has no such model or endpoint (HTTP 404)",
                remedy="check LLM_MODEL and LLM_BASE_URL",
            )
        if response.status_code >= 400:
            raise DegradedReview(
                f"the AI provider returned HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError:
            raise DegradedReview("the AI provider returned a non-JSON body")

        text = extract(payload)
        if not text.strip():
            raise DegradedReview("the AI provider returned an empty response")
        return text

    raise DegradedReview(
        f"the AI provider was unreachable after {RETRY_ATTEMPTS} attempts ({last_detail})"
    )


def _retry_after(response, attempt):
    header = response.headers.get("Retry-After") if hasattr(response, "headers") else None
    if header:
        try:
            return min(float(header), 30.0)
        except (TypeError, ValueError):
            pass
    return RETRY_BACKOFF[attempt]
