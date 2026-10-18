"""T020 (feature 007) - no GitHub credential reaches anything a person can read.

Console, the LLM log, posted markdown, and exception text. git's argv and child
environment are asserted in tests/unit/test_source_fetch_github.py. The TFS
form of this invariant, tests/contract/test_no_secrets_leak.py, is untouched.
"""

import json

import pytest
import responses

from review_agent import github_client, output_layer
from review_agent import main as main_module
from review_agent.config import load_config
from review_agent.github_client import make_github_platform
from review_agent.models import PullRequestContext
from tests.fakes import fake_llm
from tests.fakes_github import FakeGitHubClient
from tests.fixtures import github_pr as gh
from tests.fixtures import pr_demo as demo

TOKENS = {
    "GH_TOKEN": "gh-read-secret-value",
    "GH_TOKEN_FOR_PR": "gh-post-secret-value",
    "GH_CHECKLIST_TOKEN": "gh-checklist-secret-value",
}


def _leaky_response():
    """A model that echoes every credential back - the worst case."""
    response = dict(demo.MODEL_RESPONSE)
    response["summary"] = "Tokens seen: " + " ".join(TOKENS.values())
    return response


@pytest.fixture
def gh_env(github_env, monkeypatch, tmp_path):
    for key, value in TOKENS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("GH_REPOSITORY", gh.REPO)
    monkeypatch.setenv("LLM_LOG", "true")
    monkeypatch.setenv("LLM_LOG_DIR", str(tmp_path / "logs"))
    return tmp_path


def _assert_clean(text, where):
    for name, value in TOKENS.items():
        assert value not in text, f"{name} reached {where}"


def test_console_and_log_carry_no_github_token(gh_env, monkeypatch, capsys):
    monkeypatch.setattr(github_client, "make_github_platform", lambda config: FakeGitHubClient())
    monkeypatch.setattr(main_module, "call_llm", fake_llm(_leaky_response()))
    config = load_config(dry_run_override=True)
    main_module.run_review(config, main_module.PhaseLog(enabled=True))
    _assert_clean(capsys.readouterr().out, "the console")
    (log,) = (gh_env / "logs").glob("*.log")
    _assert_clean(log.read_text(encoding="utf-8"), "the LLM log")


@pytest.mark.parametrize("alias", ["GITHUB_TOKEN", "GIT_REPO_TOKEN"])
def test_an_aliased_read_token_is_redacted_too(github_env, monkeypatch, capsys, alias):
    monkeypatch.delenv("GH_TOKEN")
    monkeypatch.setenv(alias, "aliased-secret-value-123")
    config = load_config(dry_run_override=True)
    from review_agent.config import emit

    emit(f"oops {config.gh_token}")
    assert "aliased-secret-value-123" not in capsys.readouterr().out


@responses.activate
def test_posted_markdown_carries_no_github_token(gh_env):
    platform = make_github_platform(load_config(dry_run_override=False))
    responses.add(responses.POST, f"{gh.API}/repos/{gh.REPO}/issues/12/comments", json={"id": 1})
    responses.add(responses.POST, f"{gh.API}/repos/{gh.REPO}/pulls/12/reviews", json={"id": 2})
    leak = " ".join(TOKENS.values())
    inline = output_layer.InlineComment("/src/a.cs", 3, f"saw {leak}", "fp", "code", f"saw {leak}")
    plan = output_layer.FeedbackPlan(f"summary {leak}", [inline], [], [], "create_summary")
    ctx = PullRequestContext(pr_id=12, platform="github").with_iteration(1, gh.HEAD, gh.MERGE_BASE)
    platform.deliver(plan, None, ctx)
    for call in responses.calls:
        _assert_clean(call.request.body.decode("utf-8") if isinstance(call.request.body, bytes)
                      else call.request.body, "a posted comment")
        json.loads(call.request.body)  # still a valid body after redaction


@responses.activate
def test_error_text_carries_no_github_token(gh_env):
    platform = make_github_platform(load_config(dry_run_override=True))
    responses.add(
        responses.GET,
        f"{gh.API}/repos/{gh.REPO}/pulls/12",
        status=401,
        body=f"bad credentials {TOKENS['GH_TOKEN']}",
    )
    with pytest.raises(Exception) as caught:
        platform.get_pull_request_context()
    _assert_clean(str(caught.value), "an exception message")
