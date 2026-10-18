"""T018 (feature 007) - one summary, one review, and what happens on a 422."""

import json

import pytest
import responses

from review_agent import output_layer
from review_agent.config import load_config
from review_agent.dedupe import PriorFeedback
from review_agent.errors import SetupFailure
from review_agent.github_client import REFUSED_ANCHOR, GitHubClient, make_github_platform
from review_agent.models import PullRequestContext
from tests.fixtures import github_pr as gh

R = f"{gh.API}/repos/{gh.REPO}"
CTX = PullRequestContext(pr_id=12, platform="github").with_iteration(2, gh.HEAD, gh.MERGE_BASE)


@pytest.fixture
def platform(github_env, monkeypatch):
    monkeypatch.setenv("GH_REPOSITORY", gh.REPO)
    config = load_config(dry_run_override=False)
    return make_github_platform(config)


def _plan(inline=2, action="create_summary"):
    comments = [
        output_layer.InlineComment(
            f"/src/f{i}.cs", 10 + i, f"**Finding {i}**\n\nbody\n\n---\nfooter", f"fp{i}", "code",
            f"**Finding {i}**\n\nbody",
        )
        for i in range(inline)
    ]
    return output_layer.FeedbackPlan("## summary", comments, [], [], action)


def _bodies(method, url):
    return [json.loads(c.request.body) for c in responses.calls
            if c.request.method == method and c.request.url.split("?")[0] == url]


@responses.activate
def test_summary_then_one_review_with_every_inline_comment(platform):
    responses.add(responses.POST, f"{R}/issues/12/comments", json={"id": 1}, status=201)
    responses.add(responses.POST, f"{R}/pulls/12/reviews", json={"id": 2})
    assert platform.deliver(_plan(3), None, CTX) == 3

    assert [c.request.method for c in responses.calls] == ["POST", "POST"]
    (review,) = _bodies("POST", f"{R}/pulls/12/reviews")
    assert review["event"] == "COMMENT"
    assert review["commit_id"] == gh.HEAD
    assert [(c["path"], c["line"], c["side"]) for c in review["comments"]] == [
        ("src/f0.cs", 10, "RIGHT"), ("src/f1.cs", 11, "RIGHT"), ("src/f2.cs", 12, "RIGHT"),
    ]
    assert responses.calls[1].request.headers["Authorization"] == "Bearer gh-post-secret-value"
    assert platform.write_count == 2


@responses.activate
def test_a_prior_summary_is_edited_in_place(platform):
    responses.add(responses.PATCH, f"{R}/issues/comments/77", json={"id": 77})
    prior = PriorFeedback(summary_thread_id=77, summary_comment_id=77)
    platform.deliver(_plan(0, action="update_summary"), prior, CTX)
    assert _bodies("PATCH", f"{R}/issues/comments/77") == [{"body": "## summary"}]
    assert len(responses.calls) == 1  # no inline comment -> no review at all


@responses.activate
def test_a_refused_review_lists_every_finding_instead(platform):
    responses.add(responses.POST, f"{R}/issues/12/comments", json={"id": 1}, status=201)
    responses.add(responses.POST, f"{R}/pulls/12/reviews", status=422, json={"message": "Unprocessable"})
    responses.add(responses.POST, f"{R}/pulls/12/reviews", json={"id": 3})
    assert platform.deliver(_plan(2), None, CTX) == 0
    first, second = _bodies("POST", f"{R}/pulls/12/reviews")
    assert len(first["comments"]) == 2
    assert second["comments"] == []
    assert REFUSED_ANCHOR in second["body"]
    assert "`src/f0.cs:10` - **Finding 0**" in second["body"]
    assert "`src/f1.cs:11` - **Finding 1**" in second["body"]
    assert platform.refused_inline == 2


def test_a_preview_has_no_writer_at_all(github_env, monkeypatch):
    monkeypatch.setenv("GH_REPOSITORY", gh.REPO)
    preview = make_github_platform(load_config(dry_run_override=True))
    assert preview.writer is None
    with pytest.raises(SetupFailure):
        preview.post_summary("x", None)


def test_the_writer_holds_the_post_token_and_the_reader_does_not(platform):
    assert platform.token == "gh-read-secret-value"
    assert platform.writer.token == "gh-post-secret-value"
    assert isinstance(platform.writer, GitHubClient) and platform.writer.purpose == "post"
