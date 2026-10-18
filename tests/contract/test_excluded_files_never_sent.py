"""T086 - SC-010: excluded content never reaches the AI provider.

A gate on the outbound boundary. The scenario is mundane and common: someone
commits a connection string alongside real code. The review must not be the thing
that carries it out of the building.
"""

import pytest

from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import FakeTfsClient, fake_llm
from tests.fixtures import pr_demo as demo

SECRET_VALUES = ("hunter2", "Password=", "ConnectionStrings")


@pytest.fixture
def captured_prompts(base_env, monkeypatch):
    def _run(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        llm = fake_llm(demo.MODEL_RESPONSE)
        monkeypatch.setattr(main_module, "TfsClient", lambda config: FakeTfsClient())
        monkeypatch.setattr(main_module, "call_llm", llm)
        report = main_module.run_review(
            load_config(dry_run_override=True), main_module.PhaseLog(enabled=False)
        )
        return report, " ".join(llm.state["prompts"])

    return _run


def test_no_byte_of_an_excluded_file_reaches_the_provider(captured_prompts):
    _, prompts = captured_prompts()
    for value in SECRET_VALUES:
        assert value not in prompts, f"{value!r} from appsettings.json reached the provider"


def test_the_excluded_file_path_is_not_even_named_in_the_prompt(captured_prompts):
    _, prompts = captured_prompts()
    assert "appsettings" not in prompts


def test_the_excluded_file_is_named_in_the_report(captured_prompts):
    """Skipped, not silently dropped (FR-014c)."""
    report, _ = captured_prompts()
    paths = [s.path for s in report.skipped]
    assert any("appsettings" in p for p in paths)


def test_the_skip_states_which_pattern_matched(captured_prompts):
    report, _ = captured_prompts()
    entry = next(s for s in report.skipped if "appsettings" in s.path)
    assert "appsettings*.json" in entry.detail
    assert entry.reason == "excluded"


def test_the_summary_tells_the_reviewer_the_file_was_skipped(captured_prompts):
    from review_agent import output_layer
    from review_agent.models import PullRequestContext

    report, _ = captured_prompts()
    summary = output_layer.render_summary(
        report, (), PullRequestContext(pr_id=1, iteration_id=1)
    )
    assert "Not sent for review" in summary
    assert "appsettings" in summary


def test_a_team_can_opt_in_to_reviewing_configuration(captured_prompts):
    """FR-014b: the appsettings default must be removable."""
    _, prompts = captured_prompts(REVIEW_EXCLUDE_PATTERNS="*.dll", REVIEW_EXCLUDE_MODE="replace")
    assert "appsettings" in prompts, "replace mode must let the file through"


def test_reviewable_code_is_still_sent(captured_prompts):
    """The gate must not be satisfied by sending nothing."""
    _, prompts = captured_prompts()
    assert "CartController" in prompts
    assert "AddItem" in prompts


def test_every_default_secret_pattern_is_actually_excluded():
    """SC-010 says "verified for every path in the default exclusion list"."""
    from review_agent.config import DEFAULT_EXCLUDE_PATTERNS
    from review_agent.selection import match_exclusion

    samples = {
        ".env": ".env",
        ".env.*": "src/.env.production",
        "*.pem": "certs/server.pem",
        "*.key": "certs/private.key",
        "*.pfx": "certs/site.pfx",
        "*.p12": "certs/store.p12",
        "*.cer": "certs/ca.cer",
        "*.crt": "certs/ca.crt",
        "*.jks": "certs/keys.jks",
        "*.keystore": "certs/app.keystore",
        "*.snk": "sign/key.snk",
        "id_rsa*": "id_rsa.pub",
        "*secrets*.json": "config/app-secrets.json",
        "*.publishsettings": "deploy/site.publishsettings",
        "appsettings*.json": "src/App/appsettings.Production.json",
    }
    for pattern, sample in samples.items():
        assert match_exclusion(sample, DEFAULT_EXCLUDE_PATTERNS) is not None, (
            f"{sample} (for pattern {pattern}) is not excluded"
        )
