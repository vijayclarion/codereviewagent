# Contract: `PlatformClient`

**Module**: `review_agent/platform.py` (protocol, `TfsPlatform`, `make_platform`)
**Implementations**: `TfsPlatform` (adapter over `TfsClient`), `GitHubClient` (`github_client.py`)
**Research**: D1-D4, D7

The pipeline (`main.run_review`, `stories`, `checklist`, `diff_builder`, `dedupe`) talks to
the hosting platform **only** through these methods. Neither implementation's wire format
leaves its module.

## Construction

```python
make_platform(config, tfs_factory) -> PlatformClient
```

- `PLATFORM=tfs` → `TfsPlatform(tfs_factory(config))`. `tfs_factory` is `main.TfsClient`,
  passed **at call time** so that `monkeypatch.setattr(main_module, "TfsClient", ...)` keeps
  working (E4). The read client is used for writes too, exactly as today (D4 / Q1).
- `PLATFORM=github` → `GitHubClient(config, purpose="read")`; when `config.dry_run` is
  false, a second `GitHubClient(config, purpose="post")` is attached as the writer. **A dry
  run never constructs a client holding the posting token.**

## Reads

| Method | Returns | TFS (`TfsPlatform`) | GitHub (`GitHubClient`) |
|---|---|---|---|
| `get_pull_request_context()` | `PullRequestContext` | `from_payload(get_pull_request())` | `GET /repos/{r}/pulls/{n}` → `from_github` |
| `get_revision()` | `Revision` | `resolve_iteration(get_iterations(), pr)`; no iterations → `DegradedReview` (today's message) | head = `head.sha`; base = `GET /repos/{r}/compare/{base.sha}...{head.sha}` → `merge_base_commit.sha`; iteration = `commits` |
| `get_changed_files(revision)` | `list[ChangeEntry \| dict]` | `get_iteration_changes(id)["changeEntries"]` (dicts, unchanged) | `GET /pulls/{n}/files?per_page=100`, **every page** (Link header) |
| `get_file_content(path, sha, repo=None)` | `str \| None` | delegate | `GET /repos/{r}/contents/{path}?ref={sha}`, `Accept: application/vnd.github.raw`; 404 → `None` |
| `get_threads()` | thread dicts (D2) | delegate | `GET /pulls/{n}/comments` + `GET /issues/{n}/comments`, every page |
| `list_items(scope, branch, repo)` | TFS-shaped item dicts | delegate | `GET /repos/{repo}/git/trees/{branch or default}?recursive=1` mapped to `{path, isFolder}` |
| `get_file_on_branch(path, branch, repo)` | `str \| None` | delegate | contents API at `ref=branch` |
| `linked_work_item_ids()` | `list[int]` | delegate to `get_linked_work_item_ids` | — (not used) |
| `get_work_item(id)` | TFS payload | delegate | — |
| `linked_issue_numbers()` | `IssueLinks(numbers, notes)` | — | GraphQL `closingIssuesReferences(first: 50)` ∪ body regex; same repository only |
| `get_issue(number)` | issue payload \| `None` | — | `GET /repos/{r}/issues/{n}`; payload with `pull_request` key → `None` + note |

Thread shape (D2), both platforms:

```python
{"id": <thread id>, "threadContext": {"filePath": "/path"} | None,
 "comments": [{"id": <comment id>, "content": "<markdown>"}]}
```

GitHub: review comment → thread `id = comment id`, `filePath = "/" + path`; issue comment →
`threadContext = None`. Deleted/minimized comments are not returned by the API and need no
filter.

## Writes

| Method | TFS | GitHub |
|---|---|---|
| `post_summary(markdown, prior)` | `update_comment` if prior summary, falling back to `add_comment`; else `create_thread` — today's `_report_degraded` / `post_plan` logic | `PATCH /repos/{r}/issues/comments/{id}` if prior summary, else `POST /repos/{r}/issues/{n}/comments` |
| `deliver(plan, prior, pr_context) -> int` | `output_layer.post_plan(plan, client, prior)` **verbatim** | `post_summary`, then one `POST /pulls/{n}/reviews` `{commit_id: head, event: "COMMENT", body: "", comments: [{path, line, side: "RIGHT", body}]}`; no inline comments → no review. Returns inline count |
| `write_count` | client's | sum of both clients |

**GitHub 422 fallback** (D3): the review is re-posted with `comments: []` and a body that
lists every refused finding with `path:line` and the reason. The returned count is 0 and
the phase log says `inline=0 refused=N`.

## Errors

Both implementations raise the existing types only:

| Condition | Read | Write |
|---|---|---|
| Unreachable after 3 attempts | `DegradedReview` | `SetupFailure` |
| 401 | `SetupFailure` "authentication failed … check GH_TOKEN" | same |
| 403 on an issue read | `WorkItemAccessDenied` (story half lost, review continues) | — |
| 403 otherwise | `SetupFailure` with the token setting and permission to grant | same |
| 404 on the PR | `SetupFailure` "check GH_REPOSITORY and GH_PR_NUMBER" | — |
| 429 / 502 / 503 / 504, secondary rate limit (403 + `Retry-After`) | retried, `Retry-After` honoured ≤ 30 s | same |

`GitHubClient` never puts a token in a message: endpoints are reported without query
strings, and every token is registered with `redact`.

## Headers (GitHub)

`Authorization: Bearer <token>`, `Accept: application/vnd.github+json`,
`X-GitHub-Api-Version: 2022-11-28`, `User-Agent: najm-ai-code-review/<version>`.
TLS: `inject_system_trust()` is reused (no verification ever disabled).

## Boundary (tests/contract/test_import_boundaries.py)

- `requests` may be imported by `tfs_client.py`, `llm_adapter.py`, `github_client.py` only.
- The strings `api.github.com`, `/pulls/`, `/repos/`, `graphql`, `closingIssuesReferences`,
  `X-GitHub-Api-Version` appear only in `github_client.py` (and `config.py` for the default
  `GH_API_URL` and the derived GraphQL URL).
- `platform.py` imports neither `requests` nor `subprocess` and reads no environment.
