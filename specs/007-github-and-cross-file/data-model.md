# Data Model: GitHub Platform Support and Cross-File Review

**Feature**: `007-github-and-cross-file` | **Plan**: [plan.md](./plan.md)

Conventions kept: frozen dataclasses, invariants in `__post_init__`, every skipped or
degraded outcome carries a stated reason. "New" = added by this feature; "Extended" = an
existing entity gains optional fields whose defaults reproduce today's behaviour exactly.

---

## Configuration

### `Config` (extended, `config.py`)

| Field | Type | Default | Notes |
|---|---|---|---|
| `platform` | str | `"tfs"` | `tfs` \| `github` |
| `story_source` | str | platform-native | `tfs` \| `github-issues` \| `none` |
| `gh_api_url` | str | `https://api.github.com` | trailing `/` stripped |
| `gh_repository` | str | `""` | `owner/name`; required on GitHub |
| `gh_pr_number` | int | `0` | required on GitHub (or `--pr`) |
| `gh_token` | str (secret) | `""` | read token; required on GitHub |
| `gh_post_token` | str (secret) | `""` | required on GitHub only when `dry_run` is false |
| `gh_checklist_token` | str (secret) | = `gh_token` | clone of the checklist repository |
| `gh_checklist_repo` | str | `""` | `owner/name`; falls back to the existing checklist settings |
| `gh_agent_repo` | str | `""` | `owner/name`; required on GitHub unless `--local` |
| `llm_max_prompt_tokens` | int | `120000` | ≥ 8,000 |
| `llm_max_output_tokens` | int | `8192` | ≥ 256 |
| `llm_max_chunk_lines` | int | `0` | **was 1200**; 0 = no line cap (D8) |
| `llm_price_input_per_mtok` | float \| None | `None` | ≥ 0 |
| `llm_price_output_per_mtok` | float \| None | `None` | ≥ 0 |
| `llm_price_currency` | str | `"USD"` | label only |

Derived properties: `pr_id` (TFS → `tfs_pr_id`, GitHub → `gh_pr_number`),
`gh_web_url` (`https://github.com` for the public API, else the API URL minus `/api/v3`),
`gh_graphql_url` (`https://api.github.com/graphql`, or `https://<host>/api/graphql`).

`SECRET_FIELDS` gains `gh_token`, `gh_post_token`, `gh_checklist_token`.
`SECRET_ENV_NAMES` gains `GH_TOKEN`, `GH_TOKEN_FOR_PR`, `GH_CHECKLIST_TOKEN`, `GITHUB_TOKEN`,
`GIT_REPO_TOKEN`.

**Invariants (reported together by `load_config`)**:
- `PLATFORM=tfs` → TFS settings required as today; GitHub settings ignored.
- `PLATFORM=github` → `GH_REPOSITORY` (`^[\w.-]+/[\w.-]+$`), PR number, read token required;
  TFS settings ignored.
- `STORY_SOURCE=github-issues` requires `PLATFORM=github`; `STORY_SOURCE=tfs` requires
  `PLATFORM=tfs`.
- `llm_max_output_tokens < llm_max_prompt_tokens / 2`.

---

## Platform

### `PlatformClient` (new protocol, `platform.py`)

Full method contract in [contracts/platform-client.md](./contracts/platform-client.md).

### `ChangeEntry` (new, `models.py`)

| Field | Type | Notes |
|---|---|---|
| `path` | str | repository-relative, leading `/` as TFS reports it |
| `change_type` | str | `add` \| `edit` \| `delete` \| `rename` |
| `previous_path` | str | rename source, else `""` |

Mapping from GitHub `files[].status`: `added`→`add`, `removed`→`delete`,
`modified`/`changed`→`edit`, `renamed`→`rename`, `copied`→`add`, `unchanged`→skipped
(no diff). `diff_builder.build_change_set` accepts `ChangeEntry` **or** the TFS entry dict
it accepts today.

### `Revision` (new, `models.py`)

| Field | Type | Notes |
|---|---|---|
| `iteration_id` | int | TFS: iteration id. GitHub: the PR's commit count |
| `head` | str | head commit SHA |
| `base` | str | TFS: `commonRefCommit` with fallback. GitHub: compare-API **merge base** |

### `PullRequestContext` (extended)

| New field | Type | Default | Notes |
|---|---|---|---|
| `platform` | str | `"tfs"` | summary wording ("iteration 3" vs "commit abc1234") |
| `is_draft` | bool | `False` | GitHub only; informational for local runs |
| `is_fork` | bool | `False` | GitHub only; `head.repo.full_name != base.repo.full_name` |

`PullRequestContext.from_github(number, payload)` builds it from a pull-request payload.

### `ChangedFile` (extended)

| New field | Type | Default | Notes |
|---|---|---|---|
| `content` | str | `""` | post-change text; `compare=False, repr=False`; feeds the skeleton |

---

## Stories

### `WorkItem` (extended — new constructor only)

`WorkItem.from_issue(payload, ordinal_start=1)`:
- `id` ← `number`; `title` ← `title`; `description` ← body without the criteria section;
  `acceptance_criteria` ← the section text; `work_item_type` ← `"GitHub issue"`;
  `state` ← `state`; `tags` ← label names.
- `criteria` ← `split_criteria(section with "[ ]"/"[x]" markers stripped)`, numbered from
  `ordinal_start`; if no section exists, from the description (as TFS does).

### `StoryOutcome` (new, `stories.py`)

| Field | Type | Notes |
|---|---|---|
| `work_items` | tuple[WorkItem] | |
| `reason` | str | why there are none, or `""` |
| `notes` | tuple[str] | per-issue observations: "issue #9 is a pull request", "#4 has no Acceptance criteria section", "acme/other#3 is in another repository and was not read" |

---

## Cross-file review

### `Declarations` (new, `declarations.py`)

| Field | Type | Notes |
|---|---|---|
| `added` | tuple[str] | signatures as written, whitespace-normalized |
| `removed` | tuple[str] | |
| `types` | frozenset[str] | type names declared or referenced, for dependency edges |
| `supported` | bool | False → the outline says "not extracted for this file type" |

### `ChunkPiece` (new, `chunk_planner.py`)

| Field | Type | Notes |
|---|---|---|
| `file` | ChangedFile | |
| `part` | int | 1-based; 1 when the file is whole |
| `parts` | int | ≥ 1 |
| `diff` | str | the hunks of this piece |
| `skeleton` | str | `""` unless `parts > 1` |
| `split_inside_hunk` | bool | |

Invariant: `1 ≤ part ≤ parts`; `parts == 1` ⇒ `diff == file.diff` and `skeleton == ""`.

### `ChunkPlan` (new)

| Field | Type | Notes |
|---|---|---|
| `chunks` | tuple[tuple[ChunkPiece]] | ordered |
| `assignment` | dict[path → tuple[int]] | which chunk(s) review each file |
| `groups` | tuple[frozenset[path]] | dependency components, for the outline and tests |
| `budget_tokens` | int | diff budget per chunk |

Invariants: every reviewed file appears in ≥ 1 chunk; every chunk's estimated size ≤ the
whole-prompt budget unless it holds a single piece that cannot be split further (then
`split_inside_hunk` is true and the outline says so).

### `PrOutline` (new)

Rows of `(path, change_type, added_lines, removed_lines, chunks, declarations)`, rendered
once and included verbatim in every chunk prompt and in the synthesis prompt.

### `CrossFileIssue` (new, `models.py`)

| Field | Type | Notes |
|---|---|---|
| `severity` | str | `high` \| `medium` \| `low` |
| `issue` | str | non-empty |
| `files` | tuple[str] | ≥ 2 distinct, normalized |
| `file` | str | optional anchor |
| `line` | int | optional anchor, 0 = none |

Identity: `cross_file_key(issue) = "|".join(sorted(normalized files))`.

### `ReviewReport` (extended)

| New field | Type | Default |
|---|---|---|
| `cross_file_issues` | tuple[CrossFileIssue] | `()` |
| `synthesis` | str | `"not needed"` \| `"complete"` \| `"failed: <reason>"` |
| `usage` | RunUsage \| None | `None` |

`has_blocking_findings` additionally returns True for a `high` cross-file issue.

### `SynthesisResult` (new, `parser.py`)

`summary` (non-empty), `coverage` (CoverageEntry list), `cross_file_issues`.

---

## Logging and usage

### `TokenUsage` (new, `llm_adapter.py`)

`input: int | None`, `output: int | None`. Both None = "not reported".

### `SendRecord` (new, `llm_adapter.py`)

| Field | Type | Notes |
|---|---|---|
| `number` | int | 1..`RETRY_ATTEMPTS` |
| `outcome` | str | `ok` \| `retried` \| `failed` |
| `detail` | str | `HTTP 429`, `ReadTimeout`, … ; required unless `ok` |
| `elapsed_ms` | int | |
| `usage` | TokenUsage \| None | |
| `text` | str | response text on `ok` |

### `LlmText(str)` (new, `llm_adapter.py`)

A `str` — so every caller and every fake keeps working — with `.usage` and `.sends`.

### `ExchangeRecord` (extended, `llm_log.py`)

| New field | Type | Default | Notes |
|---|---|---|---|
| `kind` | str | `"review"` | `review` \| `synthesis` |
| `send` | int | `1` | 1..3 |
| `provider` | str | `""` | |
| `model` | str | `""` | |
| `input_tokens` | int \| None | `None` | None = not reported |
| `output_tokens` | int \| None | `None` | |

Chunk-position invariant applies only when `kind == "review"`.

### `RunUsage` (new, `llm_log.py`)

| Field | Type | Notes |
|---|---|---|
| `calls` | int | sends recorded |
| `reported` | int | sends with usage |
| `input_tokens` | int | sum of reported |
| `output_tokens` | int | sum of reported |
| `cost` | float \| None | None = not estimated (no prices) |
| `currency` | str | |

`describe()` → `"input 12,345 · output 1,234 · cost 0.0412 USD"`, with
`" · partial — 2 of 3 calls reported usage"` when `reported < calls`.

---

## State transitions

```text
run_review
  ├─ platform built (read client; post client only if not dry_run)
  ├─ PR context ─► stories (by STORY_SOURCE) ─► checklist ─► revision ─► change set
  ├─ selection ─► prior feedback (threads)
  ├─ nothing reviewable ─► deliver "nothing to review"                    [synthesis: not needed]
  ├─ plan chunks (budget, groups, pieces) ─► outline
  ├─ per chunk: send (parse retry ≤ 1, transport retry ≤ 2 per send) ─► parse
  │     └─ DegradedReview ─► post degraded summary ─► exit 0
  ├─ chunks > 1 ─► synthesis send ─► parse_synthesis
  │     ├─ ok      ─► apply summary / verdicts / cross-file issues        [synthesis: complete]
  │     └─ failed  ─► keep merged report + note                           [synthesis: failed: …]
  └─ deliver (dry run: print │ post: platform.deliver) ─► usage line ─► exit 0/1
```
