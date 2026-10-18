"""T049 (feature 007) - the acceptance test of US3 (quickstart section 4).

`ICartService.AddItem` changes signature and `CartController` is not updated.
The defect must be reported both when the two files are reviewed together and
when they are forced into different chunks - in which case only the synthesis
pass can see it.
"""

import json

import pytest

from review_agent import github_client, prompt_builder
from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes_github import FakeGitHubClient
from tests.fixtures import cross_file_cart as cart


class _Provider:
    """Answers chunk prompts and the synthesis prompt differently."""

    def __init__(self, chunk_has_issue, synthesis_has_issue=True):
        self.chunk_has_issue = chunk_has_issue
        self.synthesis_has_issue = synthesis_has_issue
        self.prompts = []

    def __call__(self, prompt, config=None, **_kwargs):
        self.prompts.append(prompt)
        if prompt.startswith(prompt_builder.SYNTHESIS_ROLE):
            response = dict(cart.SYNTHESIS_RESPONSE)
            if not self.synthesis_has_issue:
                response["cross_file_issues"] = []
            return json.dumps(response)
        return json.dumps(cart.chunk_response(self.chunk_has_issue))

    @property
    def review_prompts(self):
        return [p for p in self.prompts if not p.startswith(prompt_builder.SYNTHESIS_ROLE)]

    @property
    def synthesis_prompts(self):
        return [p for p in self.prompts if p.startswith(prompt_builder.SYNTHESIS_ROLE)]


@pytest.fixture
def run(github_env, monkeypatch, capsys):
    def _run(provider, **env):
        monkeypatch.setenv("STORY_SOURCE", "none")
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        fake = FakeGitHubClient(files=cart.FILES, contents=cart.CONTENTS, linked=())
        monkeypatch.setattr(github_client, "make_github_platform", lambda config: fake)
        monkeypatch.setattr(main_module, "call_llm", provider)
        plans = []
        real = prompt_builder.build_review

        def _capture(*args, **kwargs):
            review = real(*args, **kwargs)
            plans.append(review.plan)
            return review

        monkeypatch.setattr(prompt_builder, "build_review", _capture)
        config = load_config(dry_run_override=True)
        report = main_module.run_review(config, main_module.PhaseLog(enabled=False))
        return report, plans[0], capsys.readouterr().out

    return _run


def _assert_reported(report, out):
    assert len(report.cross_file_issues) == 1
    issue = report.cross_file_issues[0]
    assert set(issue.files) == {cart.INTERFACES, cart.CONTROLLER}
    assert "### Cross-file issues (1)" in out
    assert cart.INTERFACES in out and cart.CONTROLLER in out


def test_together_one_call_and_the_issue_is_reported(run):
    provider = _Provider(chunk_has_issue=True)
    report, plan, out = run(provider)
    assert plan.total == 1
    assert len(provider.prompts) == 1, "a default-budget review is one call (SC-005)"
    assert report.synthesis == "not needed"
    _assert_reported(report, out)


def test_the_outline_shows_the_signature_change(run):
    provider = _Provider(chunk_has_issue=True)
    run(provider)
    (prompt,) = provider.prompts
    outline = prompt.split("## Pull request outline", 1)[1].split("## Diff", 1)[0]
    row = next(line for line in outline.splitlines() if cart.INTERFACES in line)
    assert "removed: `void AddItem(int productId, int quantity)`" in row
    assert "added: `void AddItem(int productId, int quantity, string couponCode)`" in row


def test_apart_only_the_synthesis_sees_it_and_it_is_still_reported(run):
    provider = _Provider(chunk_has_issue=False)
    # A one-line cap forces every file into its own chunk, whatever their relations.
    report, plan, out = run(provider, LLM_MAX_CHUNK_LINES="1")
    assert plan.assignment["/" + cart.INTERFACES] != plan.assignment["/" + cart.CONTROLLER]
    assert len(provider.review_prompts) == plan.total > 1
    assert len(provider.synthesis_prompts) == 1
    assert report.synthesis == "complete"
    _assert_reported(report, out)


def test_the_synthesis_sees_the_outline_and_every_parts_notes(run):
    provider = _Provider(chunk_has_issue=False)
    _report, plan, _out = run(provider, LLM_MAX_CHUNK_LINES="1")
    (synthesis,) = provider.synthesis_prompts
    assert "## Pull request outline" in synthesis
    assert f"### Part {plan.total} of {plan.total}" in synthesis
    assert synthesis.count("Signatures and models changed in the files shown.") == plan.total


def test_related_files_share_a_chunk_when_the_budget_allows(run):
    """Grouping (D10): interface, implementation, controller and model are one component."""
    provider = _Provider(chunk_has_issue=True)
    _report, plan, _out = run(provider)
    group = next(g for g in plan.groups if "/" + cart.INTERFACES in g)
    assert {"/" + cart.SERVICE, "/" + cart.CONTROLLER} <= group
