"""T036 (feature 007) - linked issues on GitHub Enterprise Server, and failures as notes.

The github.com cases are in tests/unit/test_github_client.py.
"""

import pytest
import responses

from review_agent.config import load_config
from review_agent.github_client import GitHubClient
from tests.fixtures import github_pr as gh

GHE = "https://ghe.example/api/v3"


@pytest.fixture
def ghe_client(github_env, monkeypatch):
    monkeypatch.setenv("GH_API_URL", GHE)
    monkeypatch.setenv("GH_REPOSITORY", gh.REPO)
    return GitHubClient(load_config(dry_run_override=True), sleep=lambda _s: None)


@responses.activate
def test_graphql_goes_to_the_enterprise_endpoint(ghe_client):
    responses.add(responses.GET, f"{GHE}/repos/{gh.REPO}/pulls/12", json=dict(gh.PULL, body=""))
    responses.add(responses.POST, "https://ghe.example/api/graphql", json=gh.GRAPHQL_LINKED)
    ghe_client.get_pull_request_context()
    assert ghe_client.linked_issue_numbers().numbers == (7,)


@responses.activate
def test_an_unreadable_graphql_endpoint_is_a_note_and_the_body_still_counts(ghe_client):
    responses.add(responses.GET, f"{GHE}/repos/{gh.REPO}/pulls/12", json=dict(gh.PULL, body="Closes #7"))
    responses.add(responses.POST, "https://ghe.example/api/graphql", status=404)
    ghe_client.get_pull_request_context()
    links = ghe_client.linked_issue_numbers()
    assert links.numbers == (7,)
    assert links.notes and "linked issues could not be read" in links.notes[0]


@responses.activate
def test_a_cross_repository_graphql_result_is_noted(ghe_client):
    other = {"data": {"repository": {"pullRequest": {"closingIssuesReferences": {"nodes": [
        {"number": 3, "repository": {"nameWithOwner": "elsewhere/repo"}},
    ]}}}}}
    responses.add(responses.GET, f"{GHE}/repos/{gh.REPO}/pulls/12", json=dict(gh.PULL, body=""))
    responses.add(responses.POST, "https://ghe.example/api/graphql", json=other)
    ghe_client.get_pull_request_context()
    links = ghe_client.linked_issue_numbers()
    assert links.numbers == ()
    assert links.notes == ("elsewhere/repo#3 is in another repository and was not read",)
