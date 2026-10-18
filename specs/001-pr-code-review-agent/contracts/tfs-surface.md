# Contract: TFS REST Surface

**Feature**: [../spec.md](../spec.md) | **Implemented in**: `review_agent/tfs_client.py` — the only module that speaks TFS REST (Principle IV, asserted by `test_import_boundaries.py`)

Every endpoint the agent depends on. Keeping this list closed is what makes the agent's blast radius knowable: it reads pull requests, work items, and file contents, and it writes comment threads. Nothing else.

**API version** is configurable (`TFS_API_VERSION`, default `6.0`) because on-premises TFS versions differ. Fall back to `5.0`, then `4.1`, on an older server.

**Base**: `{TFS_BASE_URL}/{TFS_PROJECT}/_apis`

## Read operations

| Operation | Endpoint | Purpose | Requirement |
|---|---|---|---|
| `get_pull_request` | `GET git/repositories/{repo}/pullRequests/{id}` | Title, description, branches, state | FR-002 |
| `get_linked_work_item_ids` | `GET git/repositories/{repo}/pullRequests/{id}/workitems` | Which stories are linked | FR-010 |
| `get_work_item` | `GET wit/workitems/{id}` | Title, description, acceptance criteria | FR-010, FR-013 |
| `get_iterations` | `GET git/repositories/{repo}/pullRequests/{id}/iterations` | Latest iteration and its base commit | FR-007 |
| `get_iteration_changes` | `GET git/repositories/{repo}/pullRequests/{id}/iterations/{n}/changes` | Which files changed, and how | FR-007 |
| `get_file_content` | `GET git/repositories/{repo}/items?path&version={sha}` | Blob at a commit, for local diffing | FR-007 |
| `list_items` | `GET git/repositories/{repo}/items?scopePath&version={branch}&recursionLevel` | Recursive listing — used for checklist discovery | FR-008 |
| `get_file_on_branch` | `GET git/repositories/{repo}/items?path&version={branch}` | Checklist document contents | FR-008 |
| `get_threads` | `GET git/repositories/{repo}/pullRequests/{id}/threads` | Recover what the agent already said | FR-020, FR-020a |

## Write operations

| Operation | Endpoint | Purpose | Requirement |
|---|---|---|---|
| `create_thread` | `POST git/repositories/{repo}/pullRequests/{id}/threads` | Inline comment (with `threadContext`) or summary (without) | FR-018, FR-019 |
| `add_comment` | `POST …/threads/{tid}/comments` | Reply into an existing thread | FR-019 |
| `update_comment` | `PATCH …/threads/{tid}/comments/{cid}` | Amend a prior comment | — |

**These three are the entire write surface.** FR-022 — the agent never votes, approves, completes, or otherwise changes the pull request — holds because no endpoint that could do so is reachable from this client. That is a structural guarantee, not a behavioural promise, and it is why the client's endpoint list is worth keeping closed.

## Credential separation

The client is constructed with a `purpose` of `read` or `write`, and selects its token accordingly:

| Purpose | Credential | Source |
|---|---|---|
| `read` | `tfs_token` | `SYSTEM_ACCESSTOKEN` (bearer) or `TFS_PAT` (basic) |
| `write` | `post_token` | `TFS_PAT_FOR_PR` |

This is what makes "a preview cannot write" a **property rather than a promise**: a dry run never constructs a write client, so it never holds a credential capable of posting. `config.load_config` requires `TFS_PAT_FOR_PR` only when `dry_run` is false, so a preview run succeeds without one ever being present. Asserted by `test_preview_makes_no_writes.py`.

## Inline anchoring

`create_thread` anchors a comment via `threadContext`:

```json
{ "filePath": "/src/Payments/Processor.cs",
  "rightFileStart": { "line": 88, "offset": 1 },
  "rightFileEnd":   { "line": 88, "offset": 1 } }
```

The line must come from `ChangedFile.line_map`, produced by local diffing. A comment whose line cannot be mapped is routed to the summary instead of anchored approximately — which is what makes SC-003 ("100% of inline comments land on a line the PR changed") achievable rather than aspirational.

Threads are posted as **active**, so they appear in the normal review flow. If the team also enables "all comments resolved before merge", someone must resolve them — including the summary on a clean review. Leave that policy off to keep the agent fully out of the merge path.

## Why diffs are computed locally

The `changes` endpoint returns change *entries*, not patch text, and no on-premises endpoint reliably returns unified diff across TFS versions. The agent therefore fetches the base and iteration blobs and diffs them in `diff_builder.py`.

The second reason matters more: local diffing produces the **line map** that inline anchoring needs. Without it, FR-018 and SC-003 are unachievable. Recorded because this looks like an obvious simplification target and is not one (research R8).

## Failure handling

| Condition | Treated as | Exit |
|---|---|---|
| HTML sign-in page returned instead of JSON | Authentication failure (`SetupFailure`) | 2 |
| `api-version` rejected | `SetupFailure` naming the version to try | 2 |
| 404 on the pull request | `SetupFailure` — wrong repo or id | 2 |
| 403 on a write | `SetupFailure` naming the missing permission | 2 |
| Checklist source unavailable | `DegradedReview` — review continues, says so | 0 / 3 |
| Transport failure on a read | Retried with backoff, then degraded | 0 / 3 |

`_looks_like_html` exists because a TFS instance answers an unauthenticated API request with a sign-in **page**, not a 401. Without that check the failure surfaces as a JSON parse error, which sends the operator hunting in entirely the wrong place.

**TLS is never disabled.** `truststore` binds `requests` to the OS trust store so a private internal CA validates; the fallback is `REQUESTS_CA_BUNDLE`. Asserted by `test_tls_never_disabled.py`.
