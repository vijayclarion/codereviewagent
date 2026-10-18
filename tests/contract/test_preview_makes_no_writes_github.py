"""T019 (feature 007) - a GitHub preview cannot write, by construction.

The TFS form of this invariant is tests/contract/test_preview_makes_no_writes.py,
untouched. Here the stronger property is asserted: in a dry run no client that
holds the posting token is ever constructed.
"""

import pytest

from review_agent import github_client
from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import fake_llm
from tests.fakes_github import FakeGitHubClient
from tests.fixtures import pr_demo as demo


@pytest.fixture
def constructed(monkeypatch):
    """Replace the real client with a fake, recording each purpose asked for."""
    purposes = []
    fakes = []

    def _spy(config, session=None, sleep=None, purpose="read", writer=None):
        purposes.append(purpose)
        fake = FakeGitHubClient()
        fakes.append(fake)
        return fake

    monkeypatch.setattr(github_client, "GitHubClient", _spy)
    return purposes, fakes


def test_a_dry_run_constructs_no_posting_client(github_env, monkeypatch, constructed):
    purposes, fakes = constructed
    monkeypatch.delenv("GH_TOKEN_FOR_PR")  # not needed for a preview
    monkeypatch.setattr(main_module, "call_llm", fake_llm(demo.MODEL_RESPONSE))
    config = load_config(dry_run_override=True)
    main_module.run_review(config, main_module.PhaseLog(enabled=False))
    assert purposes == ["read"]
    assert sum(f.write_count for f in fakes) == 0


def test_a_posting_run_constructs_both(github_env, constructed):
    purposes, _ = constructed
    github_client.make_github_platform(load_config(dry_run_override=False))
    assert sorted(purposes) == ["post", "read"]
