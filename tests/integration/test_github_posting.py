"""T023 (feature 007) - posting on GitHub, and a second run that adds nothing.

US1 AS2-AS4 and SC-004 with fakes. The live counterpart is T090.
"""

import pytest

from review_agent import github_client
from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import fake_llm
from tests.fakes_github import FakeGitHubClient
from tests.fixtures import pr_demo as demo


def _response_with_findings():
    response = dict(demo.MODEL_RESPONSE)
    response["code_issues"] = [
        {"severity": "medium", "issue": "Catching Exception hides failures.",
         "file": "src/eShop.Api/Controllers/CartController.cs", "line": 26},
    ]
    return response


@pytest.fixture
def post(github_env, monkeypatch):
    def _post(fake):
        monkeypatch.setattr(github_client, "make_github_platform", lambda config: fake)
        monkeypatch.setattr(main_module, "call_llm", fake_llm(_response_with_findings()))
        config = load_config(dry_run_override=False)
        return main_module.run_review(config, main_module.PhaseLog(enabled=False))

    return _post


def test_one_review_carries_every_inline_comment(post):
    fake = FakeGitHubClient()
    post(fake)
    (review,) = fake.reviews()
    assert len(review[2]) >= 1
    assert review[1] == "h" * 40  # the head commit
    assert [w[0] for w in fake.summaries()] == ["create_summary"]


def test_a_second_run_adds_nothing_and_edits_the_summary_in_place(post):
    first = FakeGitHubClient()
    post(first)
    posted = len(first.reviews()[0][2])
    assert posted >= 1

    second = FakeGitHubClient(threads=first.as_threads())
    post(second)
    assert second.reviews() == [], "a re-run must not post a second review"
    (summary,) = second.summaries()
    assert summary[0] == "update_summary"


def test_a_refused_review_does_not_fail_the_run(post):
    fake = FakeGitHubClient(refuse_inline=True)
    report = post(fake)
    assert report.outcome == "complete"
    assert fake.reviews()[0][3] == "refused"
