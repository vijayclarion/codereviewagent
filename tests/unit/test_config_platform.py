"""T006 (feature 007) - one switch, platform-conditional requirements.

contracts/configuration.md. A TFS run must read exactly what it read before;
a GitHub run must need no TFS setting at all.
"""

import pytest

from review_agent import config as config_module
from review_agent.config import load_config, redact
from review_agent.errors import MissingConfiguration


def _problems(**overrides):
    with pytest.raises(MissingConfiguration) as caught:
        load_config(**overrides)
    return caught.value.describe()


# -- TFS: unchanged -----------------------------------------------------------


def test_tfs_is_the_default_and_carries_no_github_values(base_env):
    config = load_config(dry_run_override=True)
    assert config.platform == "tfs"
    assert config.story_source == "tfs"
    assert config.pr_id == config.tfs_pr_id == 1234
    assert config.gh_token == "" and config.gh_repository == ""


def test_tfs_ignores_github_settings(base_env, monkeypatch):
    monkeypatch.setenv("GH_REPOSITORY", "not-a-valid-repository")
    config = load_config(dry_run_override=True)
    assert config.platform == "tfs"


def test_unknown_platform_is_reported(base_env, monkeypatch):
    monkeypatch.setenv("PLATFORM", "gitlab")
    assert "PLATFORM must be one of tfs/github" in _problems(dry_run_override=True)


# -- GitHub ------------------------------------------------------------------


def test_github_needs_no_tfs_setting(github_env):
    config = load_config(dry_run_override=True)
    assert config.platform == "github"
    assert config.story_source == "github-issues"
    assert config.gh_repository == "acme/shop"
    assert config.pr_id == config.gh_pr_number == 12
    assert config.tfs_base_url == "" and config.tfs_token == ""
    assert config.checklist_repo == "acme/checklists"
    assert config.checklist_setting == "GH_CHECKLIST_REPO"
    assert config.agent_repo == "acme/agent"


def test_github_requirements_are_reported_together(monkeypatch):
    monkeypatch.setenv("PLATFORM", "github")
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_API_KEY", "k" * 10)
    text = _problems(dry_run_override=True)
    assert "GH_REPOSITORY is required" in text
    assert "GH_PR_NUMBER is required" in text
    assert "GH_TOKEN is required" in text
    assert "GH_AGENT_REPO is required (or run with --local)" in text
    assert "TFS_" not in text


def test_github_repository_must_be_owner_slash_name(github_env, monkeypatch):
    monkeypatch.setenv("GH_REPOSITORY", "shop")
    assert "GH_REPOSITORY must be owner/name" in _problems(dry_run_override=True)


def test_pr_override_wins_on_github(github_env):
    assert load_config(dry_run_override=True, pr_id_override=99).pr_id == 99


@pytest.mark.parametrize(
    "alias, value",
    [("GITHUB_TOKEN", "workflow-token-123"), ("GIT_REPO_TOKEN", "dotenv-token-456")],
)
def test_read_token_aliases(github_env, monkeypatch, alias, value):
    monkeypatch.delenv("GH_TOKEN")
    monkeypatch.setenv(alias, value)
    config = load_config(dry_run_override=True)
    assert config.gh_token == value
    assert redact(f"x {value} y") == "x *** y"


def test_repository_and_api_aliases(github_env, monkeypatch):
    monkeypatch.delenv("GH_REPOSITORY")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_API_URL", "https://ghe.example/api/v3/")
    config = load_config(dry_run_override=True)
    assert config.gh_repository == "o/r"
    assert config.gh_api_url == "https://ghe.example/api/v3"


def test_post_token_required_only_to_post(github_env, monkeypatch):
    monkeypatch.delenv("GH_TOKEN_FOR_PR")
    load_config(dry_run_override=True)  # a preview needs no write credential
    assert "GH_TOKEN_FOR_PR is required to post" in _problems(dry_run_override=False)


def test_checklist_token_defaults_to_the_read_token(github_env, monkeypatch):
    assert load_config(dry_run_override=True).gh_checklist_token == "gh-read-secret-value"
    monkeypatch.setenv("GH_CHECKLIST_TOKEN", "bot-token-789")
    assert load_config(dry_run_override=True).gh_checklist_token == "bot-token-789"


def test_local_run_needs_no_agent_repository(github_env, monkeypatch):
    monkeypatch.delenv("GH_AGENT_REPO")
    load_config(dry_run_override=True, local_logic_override=True)


def test_every_github_token_is_redacted_and_kept_out_of_repr(github_env, monkeypatch):
    monkeypatch.setenv("GH_CHECKLIST_TOKEN", "checklist-secret-value")
    config = load_config(dry_run_override=False)
    text = repr(config)
    for value in ("gh-read-secret-value", "gh-post-secret-value", "checklist-secret-value"):
        assert value not in text
        assert value not in redact(f"leak {value}")


def test_secret_env_names_cover_every_github_token():
    for name in ("GH_TOKEN", "GH_TOKEN_FOR_PR", "GH_CHECKLIST_TOKEN", "GITHUB_TOKEN", "GIT_REPO_TOKEN"):
        assert name in config_module.SECRET_ENV_NAMES


# -- derived URLs ------------------------------------------------------------


@pytest.mark.parametrize(
    "api, web, graphql",
    [
        ("https://api.github.com", "https://github.com", "https://api.github.com/graphql"),
        ("https://ghe.example/api/v3", "https://ghe.example", "https://ghe.example/api/graphql"),
    ],
)
def test_web_and_graphql_urls(github_env, monkeypatch, api, web, graphql):
    monkeypatch.setenv("GH_API_URL", api)
    config = load_config(dry_run_override=True)
    assert config.gh_web_url == web
    assert config.gh_graphql_url == graphql


# -- story source ------------------------------------------------------------


def test_story_source_mismatches_are_setup_failures(base_env, github_env, monkeypatch):
    monkeypatch.setenv("STORY_SOURCE", "tfs")
    assert "STORY_SOURCE=tfs requires PLATFORM=tfs" in _problems(dry_run_override=True)


def test_github_issues_requires_github(base_env, monkeypatch):
    monkeypatch.setenv("STORY_SOURCE", "github-issues")
    assert "requires PLATFORM=github" in _problems(dry_run_override=True)


def test_story_source_none_is_accepted_on_both(base_env, monkeypatch):
    monkeypatch.setenv("STORY_SOURCE", "None")
    assert load_config(dry_run_override=True).story_source == "none"


# -- budget and cost ---------------------------------------------------------


def test_budget_defaults(base_env):
    config = load_config(dry_run_override=True)
    assert config.llm_max_prompt_tokens == 120000
    assert config.llm_max_output_tokens == 8192
    assert config.llm_max_chunk_lines == 0
    assert config.llm_price_input_per_mtok is None
    assert config.llm_price_currency == "USD"


def test_budget_bounds(base_env, monkeypatch):
    monkeypatch.setenv("LLM_MAX_PROMPT_TOKENS", "100")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "10")
    text = _problems(dry_run_override=True)
    assert "LLM_MAX_PROMPT_TOKENS must be >= 8000" in text
    assert "LLM_MAX_OUTPUT_TOKENS must be >= 256" in text


def test_output_must_be_under_half_the_budget(base_env, monkeypatch):
    monkeypatch.setenv("LLM_MAX_PROMPT_TOKENS", "10000")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "6000")
    assert "must be less than half" in _problems(dry_run_override=True)


def test_prices(base_env, monkeypatch):
    monkeypatch.setenv("LLM_PRICE_INPUT_PER_MTOK", "3")
    monkeypatch.setenv("LLM_PRICE_OUTPUT_PER_MTOK", "15.5")
    monkeypatch.setenv("LLM_PRICE_CURRENCY", "EUR")
    config = load_config(dry_run_override=True)
    assert (config.llm_price_input_per_mtok, config.llm_price_output_per_mtok) == (3.0, 15.5)
    assert config.llm_price_currency == "EUR"


def test_bad_prices(base_env, monkeypatch):
    monkeypatch.setenv("LLM_PRICE_INPUT_PER_MTOK", "-1")
    monkeypatch.setenv("LLM_PRICE_OUTPUT_PER_MTOK", "cheap")
    text = _problems(dry_run_override=True)
    assert "LLM_PRICE_INPUT_PER_MTOK must be >= 0" in text
    assert "LLM_PRICE_OUTPUT_PER_MTOK must be a number" in text
