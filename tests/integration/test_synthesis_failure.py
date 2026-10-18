"""T050 / T051 (feature 007) - a failed synthesis costs only itself; one call by default."""

import json

import pytest

from review_agent import github_client, prompt_builder
from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import FakeTfsClient, fake_llm
from tests.fakes_github import FakeGitHubClient
from tests.fixtures import cross_file_cart as cart
from tests.fixtures import pr_demo as demo


@pytest.fixture
def run(github_env, monkeypatch, capsys):
    def _run(provider, **env):
        monkeypatch.setenv("STORY_SOURCE", "none")
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        fake = FakeGitHubClient(files=cart.FILES, contents=cart.CONTENTS, linked=())
        monkeypatch.setattr(github_client, "make_github_platform", lambda config: fake)
        monkeypatch.setattr(main_module, "call_llm", provider)
        report = main_module.run_review(load_config(dry_run_override=True), main_module.PhaseLog(enabled=True))
        return report, capsys.readouterr().out

    return _run


def _unparseable_synthesis(prompt, config=None, **_kwargs):
    if prompt.startswith(prompt_builder.SYNTHESIS_ROLE):
        return "I would rather write prose."
    response = cart.chunk_response(False)
    response["code_issues"] = [{"severity": "low", "issue": "Kept from a chunk.", "file": cart.CART, "line": 6}]
    return json.dumps(response)


def test_a_failed_synthesis_keeps_every_chunk_finding(run):
    report, out = run(_unparseable_synthesis, LLM_MAX_CHUNK_LINES="1")
    assert report.outcome == "complete"
    assert report.synthesis.startswith("failed:")
    assert any(i.issue == "Kept from a chunk." for i in report.code_issues)
    assert any("Synthesis did not complete" in n for n in report.notes)
    assert "Synthesis did not complete" in out
    assert "phase=synthesis outcome=failed" in out


def test_a_single_chunk_run_makes_no_synthesis_call(run):
    provider = fake_llm(cart.chunk_response(False))
    report, out = run(provider)
    assert provider.state["calls"] == 1
    assert report.synthesis == "not needed"
    assert "phase=synthesis" not in out


def test_the_tfs_demo_is_one_call_by_default(base_env, monkeypatch):
    """SC-005 on the existing demo fixture."""
    provider = fake_llm(demo.MODEL_RESPONSE)
    monkeypatch.setattr(main_module, "TfsClient", lambda config: FakeTfsClient())
    monkeypatch.setattr(main_module, "call_llm", provider)
    report = main_module.run_review(load_config(dry_run_override=True), main_module.PhaseLog(enabled=False))
    assert provider.state["calls"] == 1
    assert report.synthesis == "not needed"
