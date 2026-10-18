"""T030 - preview mode is read-only (FR-007, FR-026).

A gate. Preview is the default and the mode the quickstart tells people to run
first, so a write escaping in preview would surprise someone on a real pull
request. The assertion is on *any* non-GET call, not on the absence of specific
methods, so a future code path cannot slip past it.
"""

import pytest

from review_agent import main as main_module
from review_agent.config import load_config
from tests.fakes import FakeTfsClient, fake_llm
from tests.fixtures import pr_demo as demo


class StrictReadOnlyClient(FakeTfsClient):
    """Fails loudly on any write instead of recording it."""

    def create_thread(self, content, thread_context=None):
        raise AssertionError("preview mode attempted to create a thread")

    def add_comment(self, thread_id, content):
        raise AssertionError("preview mode attempted to add a comment")

    def update_comment(self, thread_id, comment_id, content):
        raise AssertionError("preview mode attempted to update a comment")


@pytest.fixture
def preview_run(base_env, monkeypatch):
    def _run(response=None, client=None, threads=None):
        tfs = client or StrictReadOnlyClient(threads=threads or [])
        monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
        monkeypatch.setattr(
            main_module, "call_llm", fake_llm(response or demo.MODEL_RESPONSE)
        )
        config = load_config(dry_run_override=True)
        report = main_module.run_review(config, main_module.PhaseLog(enabled=False))
        return report, tfs

    return _run


def test_a_normal_preview_run_writes_nothing(preview_run):
    report, tfs = preview_run()
    assert report.outcome == "complete"
    assert tfs.write_count == 0


def test_a_degraded_preview_run_writes_nothing(preview_run):
    """The degraded notice is printed, not posted, in preview mode."""
    report, tfs = preview_run(response="not json")
    assert report.outcome == "degraded"
    assert tfs.write_count == 0


def test_preview_prints_the_summary_and_the_inline_comments(preview_run, capsys):
    preview_run()
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "AI Code Review" in out
    assert "inline comment:" in out


def test_preview_output_carries_the_attribution_marker(preview_run, capsys):
    """FR-031: a reader must be able to tell this from a human's comment."""
    preview_run()
    out = capsys.readouterr().out
    assert "ai-review:summary" in out
    assert "AI code review" in out


def test_the_dry_run_flag_overrides_a_post_configuration(base_env, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    tfs = StrictReadOnlyClient()
    monkeypatch.setattr(main_module, "TfsClient", lambda config: tfs)
    monkeypatch.setattr(main_module, "call_llm", fake_llm(demo.MODEL_RESPONSE))
    exit_code = main_module.main(["--dry-run", "--quiet"])
    assert exit_code == 0
    assert tfs.write_count == 0


def test_the_agent_never_votes_or_resolves():
    """Out of scope by design: comment only, never act on the pull request."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "review_agent").rglob("*.py")
    forbidden = ("/vote", "\"vote\"", "'vote'", "autoComplete", "abandon")
    offenders = []
    for path in source:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.name}:{token}")
    assert not offenders, "the agent must not act on a pull request: " + ", ".join(offenders)


def test_no_status_other_than_active_is_ever_sent():
    """FR-024a: created active; resolving is a human's decision."""
    from pathlib import Path

    client_source = (
        Path(__file__).resolve().parents[2] / "review_agent" / "tfs_client.py"
    ).read_text(encoding="utf-8")
    for banned in ('"closed"', '"fixed"', '"wontFix"', '"byDesign"', '"pending"'):
        assert banned not in client_source, f"thread status {banned} must never be sent"
    assert '"status": "active"' in client_source
