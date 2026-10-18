"""T017 (feature 007) - the GitHub transport, where URL shapes actually matter."""

import json

import pytest
import requests
import responses

from review_agent.config import load_config
from review_agent.errors import DegradedReview, SetupFailure, WorkItemAccessDenied
from review_agent.github_client import GitHubClient
from review_agent.models import ChangeEntry
from tests.fixtures import github_pr as gh

R = f"{gh.API}/repos/{gh.REPO}"


@pytest.fixture
def config(github_env, monkeypatch):
    monkeypatch.setenv("GH_REPOSITORY", gh.REPO)
    return load_config(dry_run_override=True)


@pytest.fixture
def client(config):
    return GitHubClient(config, sleep=lambda _s: None)


@responses.activate
def test_headers_and_pull_request(client):
    responses.add(responses.GET, f"{R}/pulls/12", json=gh.PULL)
    ctx = client.get_pull_request_context()
    sent = responses.calls[0].request.headers
    assert sent["Authorization"] == "Bearer gh-read-secret-value"
    assert sent["Accept"] == "application/vnd.github+json"
    assert sent["X-GitHub-Api-Version"] == "2022-11-28"
    assert sent["User-Agent"].startswith("najm-ai-code-review/")
    assert (ctx.pr_id, ctx.platform, ctx.title) == (12, "github", "Add item to cart")


@responses.activate
def test_revision_is_the_merge_base_not_the_target_tip(client):
    responses.add(responses.GET, f"{R}/pulls/12", json=gh.PULL)
    responses.add(responses.GET, f"{R}/compare/{gh.TARGET}...{gh.HEAD}", json=gh.COMPARE)
    revision = client.get_revision()
    assert (revision.head, revision.base, revision.iteration_id) == (gh.HEAD, gh.MERGE_BASE, 2)


@responses.activate
def test_every_page_of_changed_files_is_read(client):
    page2 = f"{R}/pulls/12/files?per_page=100&page=2"
    responses.add(
        responses.GET,
        f"{R}/pulls/12/files",
        json=gh.FILES_PAGE_1,
        headers={"Link": f'<{page2}>; rel="next", <{page2}>; rel="last"'},
    )
    responses.add(responses.GET, page2, json=gh.FILES_PAGE_2)
    entries = client.get_changed_files()
    assert entries == [
        ChangeEntry("/" + gh.CART_PATH, "edit"),
        ChangeEntry("/" + gh.APPSETTINGS_PATH, "edit"),
    ]  # "unchanged" carries no diff
    assert len(responses.calls) == 2


@responses.activate
def test_status_mapping_and_renames(client):
    responses.add(
        responses.GET,
        f"{R}/pulls/12/files",
        json=[
            {"filename": "a.cs", "status": "added"},
            {"filename": "b.cs", "status": "removed"},
            {"filename": "c.cs", "status": "renamed", "previous_filename": "old.cs"},
            {"filename": "d.cs", "status": "copied"},
        ],
    )
    entries = client.get_changed_files()
    assert [(e.path, e.change_type, e.previous_path) for e in entries] == [
        ("/a.cs", "add", ""),
        ("/b.cs", "delete", ""),
        ("/c.cs", "rename", "/old.cs"),
        ("/d.cs", "add", ""),
    ]


@responses.activate
def test_file_content_is_raw_and_a_missing_path_is_none(client):
    responses.add(
        responses.GET,
        f"{R}/contents/{gh.CART_PATH}",
        body="class CartController {}",
        match=[responses.matchers.query_param_matcher({"ref": gh.HEAD})],
    )
    responses.add(responses.GET, f"{R}/contents/missing.cs", status=404)
    assert client.get_file_content("/" + gh.CART_PATH, gh.HEAD) == "class CartController {}"
    assert responses.calls[0].request.headers["Accept"] == "application/vnd.github.raw"
    assert client.get_file_content("/missing.cs", gh.HEAD) is None


@responses.activate
def test_threads_are_mapped_to_the_neutral_shape(client):
    responses.add(
        responses.GET,
        f"{R}/pulls/12/comments",
        json=[gh.review_comment(1, "src/a.cs", "x `ai-review:code:abc123`")],
    )
    responses.add(
        responses.GET,
        f"{R}/issues/12/comments",
        json=[gh.issue_comment(2, "summary `ai-review:summary`")],
    )
    assert client.get_threads() == [
        {"id": 1, "threadContext": {"filePath": "/src/a.cs"},
         "comments": [{"id": 1, "content": "x `ai-review:code:abc123`"}]},
        {"id": 2, "threadContext": None,
         "comments": [{"id": 2, "content": "summary `ai-review:summary`"}]},
    ]


@responses.activate
def test_list_items_uses_the_default_branch_and_scope(client):
    responses.add(responses.GET, f"{gh.API}/repos/acme/checklists", json={"default_branch": "main"})
    responses.add(
        responses.GET,
        f"{gh.API}/repos/acme/checklists/git/trees/main",
        json={"tree": [
            {"path": "rules", "type": "tree"},
            {"path": "rules/a.md", "type": "blob"},
            {"path": "other/b.md", "type": "blob"},
        ]},
    )
    items = client.list_items("/rules", None, repo="acme/checklists")
    assert items == [{"path": "/rules", "isFolder": True}, {"path": "/rules/a.md", "isFolder": False}]


@responses.activate
def test_enterprise_server_base_url(github_env, monkeypatch):
    monkeypatch.setenv("GH_API_URL", "https://ghe.example/api/v3")
    monkeypatch.setenv("GH_REPOSITORY", gh.REPO)
    client = GitHubClient(load_config(dry_run_override=True), sleep=lambda _s: None)
    responses.add(responses.GET, f"https://ghe.example/api/v3/repos/{gh.REPO}/pulls/12", json=gh.PULL)
    assert client.get_pull_request_context().pr_id == 12


# -- errors ------------------------------------------------------------------


@responses.activate
@pytest.mark.parametrize(
    "status, kind, fragment",
    [
        (401, SetupFailure, "check GH_TOKEN"),
        (403, SetupFailure, "grant Contents, Pull requests and Issues (read) to GH_TOKEN"),
        (404, SetupFailure, "check GH_REPOSITORY and GH_PR_NUMBER"),
        (500, SetupFailure, "unexpected HTTP 500"),
    ],
)
def test_error_mapping(client, status, kind, fragment):
    responses.add(responses.GET, f"{R}/pulls/12", status=status)
    with pytest.raises(kind) as caught:
        client.get_pull_request_context()
    assert fragment in caught.value.describe()
    assert "gh-read-secret-value" not in caught.value.describe()


@responses.activate
def test_a_refused_issue_read_costs_only_the_story(client):
    responses.add(responses.GET, f"{R}/issues/7", status=403)
    with pytest.raises(WorkItemAccessDenied) as caught:
        client.get_issue(7)
    assert "Issues (read)" in caught.value.describe()


@responses.activate
def test_retry_after_is_honoured_and_capped(config):
    slept = []
    client = GitHubClient(config, sleep=slept.append)
    responses.add(responses.GET, f"{R}/pulls/12", status=429, headers={"Retry-After": "120"})
    responses.add(responses.GET, f"{R}/pulls/12", status=403, headers={"Retry-After": "2"})
    responses.add(responses.GET, f"{R}/pulls/12", json=gh.PULL)
    assert client.get_pull_request_context().pr_id == 12
    assert slept == [30.0, 2.0]


@responses.activate
def test_unreachable_read_degrades_and_unreachable_write_is_setup(config):
    client = GitHubClient(config, sleep=lambda _s: None)
    for _ in range(3):
        responses.add(responses.GET, f"{R}/pulls/12", body=requests.ConnectionError("down"))
    with pytest.raises(DegradedReview):
        client.get_pull_request_context()

    for _ in range(3):
        responses.add(responses.POST, f"{R}/issues/12/comments", body=requests.ConnectionError("down"))
    with pytest.raises(SetupFailure):
        client._request("POST", f"{R}/issues/12/comments", json_body={"body": "x"})


# -- linked issues -----------------------------------------------------------


@responses.activate
def test_linked_issues_union_graphql_and_body(client):
    pull = dict(gh.PULL, body="Fixes #9 and resolves #7. See #3. Closes other/repo#4")
    responses.add(responses.GET, f"{R}/pulls/12", json=pull)
    responses.add(responses.POST, f"{gh.API}/graphql", json=gh.GRAPHQL_LINKED)
    client.get_pull_request_context()
    links = client.linked_issue_numbers()
    assert links.numbers == (7, 9)
    assert links.notes == ("other/repo#4 is in another repository and was not read",)
    body = json.loads(responses.calls[1].request.body)
    assert "closingIssuesReferences" in body["query"]
    assert body["variables"] == {"owner": "acme", "name": "shop", "number": 12}
    assert client.write_count == 0  # a GraphQL query writes nothing


@responses.activate
def test_graphql_errors_become_notes_not_failures(client):
    responses.add(responses.GET, f"{R}/pulls/12", json=dict(gh.PULL, body=""))
    responses.add(responses.POST, f"{gh.API}/graphql", json={"errors": [{"message": "nope"}]})
    client.get_pull_request_context()
    links = client.linked_issue_numbers()
    assert links.numbers == ()
    assert "nope" in links.notes[0]


@responses.activate
def test_get_issue_rejects_pull_requests(client):
    responses.add(responses.GET, f"{R}/issues/7", json=gh.ISSUE_7)
    responses.add(responses.GET, f"{R}/issues/8", json={"number": 8, "pull_request": {}})
    responses.add(responses.GET, f"{R}/issues/9", status=404)
    assert client.get_issue(7) == (gh.ISSUE_7, "")
    assert client.get_issue(8) == (None, "#8 is a pull request, not an issue")
    assert client.get_issue(9) == (None, "issue #9 was not found")
