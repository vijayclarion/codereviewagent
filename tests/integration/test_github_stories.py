"""T037 (feature 007) - a PR linked to an issue gets a verdict per criterion (US2)."""

import pytest

from review_agent import github_client
from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import fake_llm
from tests.fakes_github import FakeGitHubClient
from tests.fixtures import github_pr as gh


def _response(statuses):
    criteria = [
        "Quantity must be a positive integer; a request with zero or a negative quantity is "
        "rejected with a validation error.",
        "Adding an unknown product returns a not-found response and does not change the cart.",
        "The system must not allow adding more items than are available in stock; a request "
        "exceeding available stock is rejected.",
    ]
    return {
        "coverage": [
            {"criterion": c, "status": s, "evidence": f"evidence for {s}"}
            for c, s in zip(criteria, statuses)
        ],
        "checklist_violations": [],
        "code_issues": [],
        "summary": "Reviewed.",
    }


@pytest.fixture
def run(github_env, monkeypatch, capsys):
    def _run(statuses, dry_run=True):
        fake = FakeGitHubClient()
        monkeypatch.setattr(github_client, "make_github_platform", lambda config: fake)
        monkeypatch.setattr(main_module, "call_llm", fake_llm(_response(statuses)))
        config = load_config(dry_run_override=dry_run)
        report = main_module.run_review(config, main_module.PhaseLog(enabled=False))
        return report, fake, capsys.readouterr().out

    return _run


def test_three_criteria_three_verdicts(run):
    report, _fake, out = run(["appears_addressed", "not_addressed", "possible_contradiction"])
    assert [(c.ordinal, c.status, c.work_item_id) for c in report.coverage] == [
        (1, "appears_addressed", 7),
        (2, "not_addressed", 7),
        (3, "possible_contradiction", 7),
    ]
    assert "| 1 |" in out and "| 2 |" in out and "| 3 |" in out
    assert "story #7" in out


def test_a_contradiction_comments_and_not_addressed_never_does(run):
    _report, fake, _out = run(
        ["appears_addressed", "not_addressed", "possible_contradiction"], dry_run=False
    )
    posted = " ".join(c[2] for r in fake.reviews() for c in r[2])
    summary = fake.summaries()[0][1]
    # A coverage finding carries no file, so - on TFS as on GitHub - it is listed
    # under "Findings without a specific location" rather than anchored.
    assert "Possible contradiction with acceptance criterion 3" in summary
    assert "acceptance criterion 2" not in posted + summary.split("### Story coverage")[0]
    assert "acceptance criterion 2" not in posted  # not_addressed: summary row only
