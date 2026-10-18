# Research: GitHub Platform Support and Cross-File Review

**Feature**: `007-github-and-cross-file` | **Date**: 2026-10-18 | **Plan**: [plan.md](./plan.md)

Decisions D1-D20, evidence E1-E24. Every evidence item was read in the code or measured on
2026-10-18 at commit `7eddb98`; nothing here is restated from an earlier feature's documents
without being re-checked.

---

## Evidence

| # | Fact | Where |
|---|---|---|
| E1 | **597 tests pass at `7eddb98`**, measured with `python -m pytest tests`. CLAUDE.md's "532" was the count before 006 landed | measured |
| E2 | The pipeline builds exactly one client, `TfsClient(config)`, at `main.py:218`, and uses it for every read **and every write** | `main.py:218, 150-152, 428` |
| E3 | **`TfsClient(purpose="post")` is never constructed anywhere.** `TFS_PAT_FOR_PR` is required by `load_config` before `--post` runs (`config.py:474`), and then never used: posts go out on the reading token | `grep "purpose="` — only the definition |
| E4 | 22 tests replace `main_module.call_llm`; 6 replace `main_module.TfsClient` with `lambda config: FakeTfsClient()`. `tests/demo/run.py:309` replaces it with `_call_llm(prompt, _config)` — **no `**kwargs`**, so any new keyword passed to `call_llm` breaks it | `grep monkeypatch` |
| E5 | `FakeTfsClient` implements 12 methods: `get_pull_request`, `get_linked_work_item_ids`, `get_work_item`, `get_iterations`, `get_iteration_changes`, `get_file_content`, `list_items`, `get_file_on_branch`, `get_threads`, `create_thread`, `add_comment`, `update_comment` | `tests/fakes.py` |
| E6 | `call_llm` returns `extract(payload)` — a `str`. The provider's `usage` object is in `payload` and is discarded on the same line | `llm_adapter.py:167` |
| E7 | Transport retries (3 attempts, statuses 429/5xx, timeouts) happen **inside** `call_llm`. The log sees one exchange per `call_llm` call, so a send that was retried twice is logged once | `llm_adapter.py:128-175`, `main.py:374-408` |
| E8 | `ExchangeRecord.attempt` must be 1 or 2 (the parse retry). `LogSession._guarded` catches **only `OSError`** — a `ValueError` from a record invariant would propagate into the review | `llm_log.py:116-117, 235-241` |
| E9 | Log-format strings asserted by tests: `"\| chunk 1 of 1 \| attempt 1 ---"`, `"=== end \| N exchanges \| outcome X ==="`, `"outcome  : ok in 8,431 ms \| response 16 characters"`, `"prompt   : 40 characters"`, and `text.count("--- exchange ") == calls` | `tests/integration/test_llm_log_run.py:73-142`, `tests/unit/test_llm_log.py:114-180` |
| E10 | Chunking: `chunk_files(reviewable, max_lines)` packs whole files by **changed-line count**, default `LLM_MAX_CHUNK_LINES=1200`. One test sets it to `1` to force a chunk per file | `prompt_builder.py:131-150`, `test_llm_log_run.py:67` |
| E11 | `prompt_builder.estimated_size` (chars/4) is called from nowhere | grep |
| E12 | Every prompt repeats SYSTEM_ROLE + RULES + CONTRACT + story + scope + checklist. The checklist alone renders to ~48,500 characters (165 rules) — the fixed part of every prompt is ~14,000 tokens before any diff | `config.py:503-506` |
| E13 | `DEFAULT_MAX_TOKENS = 4096` for the Claude response. A single call covering a whole PR returns more findings than a chunk did; 4096 output tokens is the ceiling | `llm_adapter.py:25` |
| E14 | `validate_payload` requires `coverage`, `checklist_violations`, `code_issues` (lists) and a non-empty `summary`; **unknown keys are ignored**. New optional keys do not invalidate any existing fixture | `parser.py:111-178` |
| E15 | Dedupe reads `client.get_threads()` and expects `[{id, threadContext:{filePath}, comments:[{id, content}]}]`. It keys on the `ai-review:` marker in the text, never on the author | `dedupe.py:70-120` |
| E16 | `post_plan` creates the summary thread (or PATCHes it, falling back to `add_comment`) and then **one `create_thread` per inline comment** | `output_layer.py:500-518` |
| E17 | `load_config` unconditionally requires `TFS_BASE_URL`, `TFS_PROJECT`, `TFS_REPO_CODE_SAMPLE`, `TFS_PR_ID`, a TFS token, and `TFS_REPO_CODE_REVIEW_CodeReviewAgent` (unless `--local`) | `config.py:388-453` |
| E18 | `source_fetch.clone_url` builds `{TFS_BASE_URL}/{project}/_git/{repo}` and the header is `Basic base64(":" + token)` — no username. GitHub's git endpoint needs a username in Basic auth (`x-access-token`) | `source_fetch.py:99-141` |
| E19 | The checklist corpus is obtained by `source_fetch.clone(config, config.checklist_repo)` (document path) with `client.list_items` / `client.get_file_on_branch` as the markdown fallback | `checklist.py:79, 338-374` |
| E20 | `tests/conftest.py::_isolate_env` clears `TFS_`, `LLM_`, `CHECKLIST_`, `REVIEW_`, `SYSTEM_`, `DRY_RUN`, `FAIL_ON_` — **not** `GH_`, `GITHUB_`, `PLATFORM`, `STORY_SOURCE`. Inside GitHub Actions, `GITHUB_TOKEN`-style variables would leak into every test | `tests/conftest.py:23-35` |
| E21 | `.env` now carries `GIT_REPO_TOKEN` (a fine-grained token). Checked with status codes only: it reads all three repositories with admin, push and pull | measured, value never printed |
| E22 | **The repository URL variables are swapped.** `GIT_REPO_CODE_SAMPLE` → `vijayclarion/codereviewagent` (holds `review_agent/`, `tests/`, `specs/001-006`); `GIT_REPO_CODE_REVIEW_CodeReviewAgent` → `vijayclarion/codereviewsample` (holds `src/eShop.Api/`, `demo/`, `azure-pipelines.yml`). The checklist URL is correct | measured by repository content |
| E23 | GitHub `codereviewagent` master is at `7eddb98` — the same commit as this working copy, which has **no remote configured**. All three repositories are public, single-branch (`master`), with no pull requests, Actions enabled, and no secrets | measured |
| E24 | The sample is C#: `src/eShop.Api/Controllers/CartController.cs`, `Models/Cart.cs`, `Services/Interfaces.cs`. The `ICartService` / `CartController` demo needs no new project | measured |

Tooling on this machine: git 2.51 (header-in-environment needs ≥ 2.31), Python 3.13, Java 8,
**no PlantUML**. PyYAML 6.0.3 is installed but is not in `requirements-dev.txt`.

---

## Decisions

### D1 — A normalized `PlatformClient` protocol, with TFS behind an adapter

**Decision**: New module `review_agent/platform.py` defines the `PlatformClient` protocol
(see `contracts/platform-client.md`) and a `TfsPlatform` adapter that **composes** an object
with `TfsClient`'s 12-method surface. `github_client.py` implements the protocol directly.
`main.run_review` builds the platform through `platform.make_platform(config, tfs_factory=...)`
where `tfs_factory` is `main.TfsClient`, **looked up at call time**.

**Rationale**: `tfs_client.py` must not change (T1), and six tests monkeypatch
`main_module.TfsClient` with `FakeTfsClient` (E4, E5). An adapter over the existing surface
means `FakeTfsClient` keeps working unmodified, because the adapter only ever calls the 12
methods it already has. Posting through the adapter produces **byte-identical writes** to
today, which the existing posting tests assert.

**Alternatives rejected**:
- *Rename `TfsClient`'s methods to the protocol's names* — breaks `FakeTfsClient` and every
  test that asserts on `fake.calls`.
- *Make GitHub impersonate TFS* (fake "iterations" and "changeEntries") — leaks TFS concepts
  into the GitHub module and makes the protocol a lie.
- *A `PlatformClient` base class that `TfsClient` inherits* — edits `tfs_client.py`.

### D2 — The thread shape is the neutral shape for prior comments

**Decision**: `PlatformClient.get_threads()` returns
`[{id, threadContext: {filePath} | None, comments: [{id, content}]}]` on both platforms.
`github_client` maps each pull-request review comment to a one-comment thread with its
`path`, and each issue comment to a context-less thread. `dedupe.py` is not edited.

**Rationale**: E15 — dedupe already keys on the marker, not the author, which is exactly
what GitHub needs (a local PAT run and a workflow run post as different identities). The
shape carries everything dedupe reads.

### D3 — Delivery moves behind the platform

**Decision**: Two protocol methods replace direct writes from `main`/`output_layer`:
`deliver(plan, prior, pr_context)` and `post_summary(markdown, prior)`.
`TfsPlatform.deliver` **is** `output_layer.post_plan(plan, client, prior)`, unchanged.
`GitHubClient.deliver` posts the summary (create or `PATCH` in place) and then **one**
review: `POST /pulls/{n}/reviews` with `event: COMMENT`, `commit_id` = head SHA, and every
inline comment as `{path, line, side: "RIGHT", body}`.

**422 fallback**: GitHub rejects the *whole* review if any comment's line is outside its
diff. On 422 the client re-posts the review with no inline comments and a body listing each
finding with its location and the stated reason ("GitHub refused an inline anchor"), so no
finding is lost and the cause is visible (Principle VII).

**Rationale**: FR-005 (one review) is impossible through `post_plan`'s one-call-per-comment
loop (E16). Keeping TFS on `post_plan` verbatim is what makes "no behaviour change" true.

### D4 — The unused posting credential (E3): recorded, not silently changed

**Finding**: The TFS posting token `TFS_PAT_FOR_PR` is required and never used; posting runs
on `TFS_PAT`. Feature 002's design (`purpose="post"`) was never wired in.

**Decision**: GitHub is built correctly from the start — a `purpose="read"` client for every
read and a separate `purpose="post"` client, constructed **only** when `dry_run` is false.
For TFS, `make_platform` *can* build the post client the same way, but doing so changes
which token TFS posts with. That is a behaviour change on the one platform this feature
promised not to change, so it is **an explicit question for the requester** (plan.md, Open
Questions Q1) and a separately-marked task, default **not applied**.

### D5 — Configuration: one switch, platform-conditional requirements

**Decision**: `PLATFORM` (`tfs` default | `github`). `load_config` requires the TFS settings
only when `PLATFORM=tfs`, and the GitHub settings only when `PLATFORM=github`; every problem
is still reported at once (`_Problems`). New settings are listed in
`contracts/configuration.md`. Highlights:

- `GH_API_URL` default `https://api.github.com`; GitHub Enterprise Server is
  `https://<host>/api/v3`. The web/git host and the GraphQL endpoint are derived from it
  (`https://<host>` and `https://<host>/api/graphql`; github.com → `https://github.com`,
  `https://api.github.com/graphql`).
- `GH_REPOSITORY` (`owner/name`, alias `GITHUB_REPOSITORY`), `GH_PR_NUMBER` (or `--pr`).
- Tokens: `GH_TOKEN` (read; aliases `GITHUB_TOKEN`, **`GIT_REPO_TOKEN`** — the name the
  requester's `.env` uses), `GH_TOKEN_FOR_PR` (post; required only for `--post`, mirroring
  `TFS_PAT_FOR_PR`), `GH_CHECKLIST_TOKEN` (clone the checklist repository; defaults to the
  read token). All registered as secrets and added to `SECRET_ENV_NAMES` so git children
  never inherit them.
- `Config` gains `platform`, the `gh_*` fields and a `pr_id` property (TFS → `tfs_pr_id`,
  GitHub → `gh_pr_number`). `llm_log` reads `pr_id` with a `tfs_pr_id` fallback so its own
  unit tests' `FakeConfig` keeps working.

`tests/conftest.py::_isolate_env` gains the `GH_`, `GITHUB_`, `GIT_REPO_`, `PLATFORM`,
`STORY_SOURCE` prefixes (E20). This is a fixture change, not a test change: without it the
GitHub suite would read a developer's real token.

### D6 — git for GitHub stays in `source_fetch.py`

**Decision**: `clone_url` / `public_url` become platform-aware. On GitHub the URL is
`https://x-access-token@<host>/<owner>/<name>.git`, the header is
`Authorization: Basic base64("x-access-token:" + token)`, presented through
`GIT_CONFIG_COUNT/KEY/VALUE` exactly as for TFS (E18). Both forms are registered as
secrets. `checklist.py` and `bootstrap.py` are unchanged except for which repository name
they pass. On GitHub the checklist repository is `owner/name` (`GH_CHECKLIST_REPO`, falling
back to the existing checklist settings), and the agent repository is `GH_AGENT_REPO`
(required unless `--local`, exactly as on TFS).

**Alternative rejected**: have the workflow check out the checklist repository with
`actions/checkout` and point the agent at a directory. It removes nothing — a local GitHub
run still has to clone — and would add a second checklist-acquisition path to test.

### D7 — Story sources: a selector over two readers

**Decision**: New module `review_agent/stories.py` exposes
`fetch_stories(config, platform, log) -> (work_items, reason)`, selected by `STORY_SOURCE`
(`tfs` | `github-issues` | `none`; default = the platform's native source).
- `tfs`: the existing `_fetch_story` logic, moved verbatim; `main._fetch_story` stays as a
  one-line delegate because two tests reference its behaviour by name.
- `github-issues`: `platform.linked_issue_numbers()` (GraphQL `closingIssuesReferences`
  ∪ `(close[sd]?|fix(e[sd])?|resolve[sd]?) #N` in the body, case-insensitive, deduplicated,
  same-repository only), then `platform.get_issue(n)`. A number that is a pull request, or
  an issue in another repository, is reported in the reason, never silently dropped.
- `WorkItem.from_issue(payload, ordinal_start)` in `models.py` parses the body: the
  `## Acceptance criteria` section (any heading level, case-insensitive) until the next
  heading; checkbox markers `[ ]`/`[x]` are stripped, then the existing `split_criteria`
  enumerates. No section → criteria fall back to the description, as TFS does
  (`models.py:61-63`), and the run states that the issue had no criteria section.
- Mismatches are setup failures with a remedy: `github-issues` on `PLATFORM=tfs`, `tfs` on
  `PLATFORM=github`.

### D8 — Token budget replaces the line budget

**Decision**: `LLM_MAX_PROMPT_TOKENS` (default 120,000) is the budget for a **whole prompt**.
Tokens are estimated as `ceil(chars / 3)` — deliberately pessimistic for code, which
tokenizes denser than prose. The diff budget per chunk is
`budget − estimate(fixed sections + outline) − LLM_MAX_OUTPUT_TOKENS`.
`LLM_MAX_CHUNK_LINES` stays accepted, but becomes an **optional additional cap**, applied
only when set (default: unset). This keeps E10's test meaningful.

`LLM_MAX_OUTPUT_TOKENS` (default 8,192) replaces the hard-coded 4,096 (E13), because a
single call for a whole PR returns more findings than a chunk did, and a truncated JSON
response degrades the entire run.

**Rationale**: SC-005. With E12's ~14k fixed tokens, the default leaves ~98k tokens
(~290,000 characters) of diff per call. `REVIEW_MAX_DIFF_LINES=3000` changed lines, at a
typical ~60 characters per diff line with context, is ~180,000-250,000 characters, so under
default settings **almost every review that passes selection is one call** — to be measured
against the sample corpus during implementation, not assumed.
The cross-file machinery (D9-D12) only engages for operators who raise the diff bound or
lower the budget, and in the tests that force it.

**Alternative rejected**: a real tokenizer — provider-specific, and a dependency (E11's
original reasoning still holds).

### D9 — Declarations, outline and skeleton: one pure module

**Decision**: New module `review_agent/declarations.py`, no I/O:
- `extract(diff_or_text, path) -> Declarations(added, removed)` over C#/Java/TypeScript
  (`class|interface|record|struct|enum` and method signatures with an access modifier or
  return type), and Python (`class`, `def`). Unknown languages → empty, and the outline says
  "declarations not extracted for this file type".
- `skeleton(text, path)` → type, field and member-signature lines of a whole file, bodies
  dropped.
- `render_outline(plan)` → the PR outline (FR-015): every file, change type, `+a/−r`, which
  part reviews it, added/removed declarations.

`ChangedFile` gains `content: str = ""` (`compare=False, repr=False`), filled by
`diff_builder` from the `after` blob it already fetches, so the skeleton costs no extra call.

### D10 — Dependency-aware grouping

**Decision**: New module `review_agent/chunk_planner.py`. Files are nodes; an edge joins two
files when any of these holds:
1. a type declared (added or present) in one appears as a whole word in the other's diff or
   content;
2. interface/implementation naming: `IFoo` ↔ `Foo`, `FooImpl`, or any type declaring
   `: IFoo` / `implements Foo`;
3. same stem after stripping role suffixes (`Controller`, `Service`, `Repository`,
   `Handler`, `Tests`, `Test`, `Spec`, `.spec`, `.test`, `test_`) and a leading `I`;
4. source ↔ test by the same stem rule.

Connected components (union-find) are packed first-fit-decreasing into chunks under the
diff budget. A component larger than the budget is split along the order that keeps the
most edges inside a chunk (files sorted by edge count, greedy). Deterministic: ties break on
path, so the same PR always plans the same way.

**Rationale**: Heuristics are cheap and good enough *because they are not the last line of
defence* — the outline (D9) and the synthesis pass (D12) catch what grouping misses. This is
the explicit design: SC-003 must hold **when the files land in different chunks**.

### D11 — Oversized single files

**Decision**: A file whose diff exceeds the diff budget is split on hunk boundaries
(greedy, in order). Each piece is presented as
`### path (edit) — part i of n` followed by the file's skeleton and that piece's hunks. A
single hunk larger than the budget is split on line boundaries, and the outline marks the
file "split inside a hunk". Line anchoring is unaffected: `line_map` belongs to the file, not
the piece.

### D12 — The synthesis pass

**Decision**: When more than one chunk was reviewed, `main` makes **one** extra call,
built by `prompt_builder.build_synthesis_prompt(outline, work_items, merged, notes)` and
parsed by `parser.parse_synthesis` (its own contract — `contracts/llm-response.md`). It goes
through the same `parse_with_retry` and the same recording sender, labelled
`synthesis`. Its result:
- **summary** replaces the joined chunk summaries;
- **coverage** verdicts replace the merged ones criterion by criterion (unmatched criteria
  keep the merged verdict);
- **cross_file_issues** are unioned with any the chunks reported, deduplicated by their file
  set.

It **cannot** add or remove code issues or checklist violations: per-chunk findings came from
seeing the code; the synthesis sees only findings.

A `DegradedReview` from synthesis is caught: the merged per-chunk report is delivered with a
note "Synthesis did not complete: <reason>. Cross-file issues may be missing." (FR-020).
With one chunk, no synthesis call is made and that chunk's own `cross_file_issues` stand.

### D13 — `cross_file_issues` in the contract, the report and the summary

**Decision**: Optional key in both response contracts (E14 — absent means `[]`, so every
existing fixture still validates). Each entry: `severity`, `issue`, `files` (≥ 2 distinct
paths), optional `file`/`line` anchor. An entry naming fewer than two files is demoted to a
code issue rather than dropped. `ReviewReport.cross_file_issues` is a new tuple field.

- **Identity** (`contracts/finding-identity.md` extension): kind `cross-file`, key =
  sorted, normalized file set. Stable against rewording; two different issues over the same
  file set collapse into one comment, the same "cheaper error" 003 chose for code issues.
- **Routing**: inline at its anchor when the anchor maps to a changed line, otherwise
  summary-only. Always listed in the summary under `### Cross-file issues (N)`, with an
  explicit "None found" — the existing convention that a missing section is
  indistinguishable from a failed one (`output_layer.py:7-9`).
- **Blocking**: a `high` cross-file issue blocks under `FAIL_ON_CONTRADICTION`, exactly as a
  `high` code issue does (`models.py:617-629`).

### D14 — Usage and every send, without changing `call_llm`'s signature

**Decision**: `call_llm(prompt, config)` keeps its signature and still returns a `str` —
specifically an `LlmText(str)` subclass carrying `.usage` (`TokenUsage(input, output)` or
`None`) and `.sends` (one `SendRecord` per HTTP attempt: number, outcome, status or
exception name, elapsed ms, usage). A `DegradedReview`/`SetupFailure` raised by `call_llm`
carries the same `.sends`. Usage fields are read in `llm_adapter.py` only:
Claude `usage.input_tokens/output_tokens`; OpenAI/Azure `usage.prompt_tokens/completion_tokens`;
Ollama `prompt_eval_count/eval_count`. Absent → `None`, never estimated (FR-022).

`main._recording_sender` reads `getattr(response, "sends", None)`. Present → one log entry
per send (so a timeout followed by success is two entries — FR-021). Absent (every test
fake, E4) → one entry, usage "not reported", exactly today's behaviour.

**Alternatives rejected**: a new keyword argument (breaks `tests/demo/run.py:309`, E4); a
new return type (breaks 22 monkeypatched fakes); a module-level observer (hidden global
state, and the log would learn about transport).

### D15 — Totals and cost

**Decision**: `LLM_PRICE_INPUT_PER_MTOK` and `LLM_PRICE_OUTPUT_PER_MTOK` (decimal, per
million tokens, optional) and `LLM_PRICE_CURRENCY` (label, default `USD`). Totals are summed
from reported usage only; when some calls reported none, totals say
`partial — N of M calls reported usage`. Cost without prices is `not estimated`. Written as a
`usage` line in the log immediately **before** the unchanged `=== end` line (E9), and to the
console as the `phase=llm` line's extras plus one `llm usage:` line.

### D16 — "Logging never crashes a review", made true

**Decision**: `LogSession._guarded` catches `Exception`, not just `OSError` (E8), and the
recording sender builds records inside the guard. `ExchangeRecord` gains `kind`
(`review`|`synthesis`), `send` (1-3), `provider`, `model`, `input_tokens`, `output_tokens`
(None = not reported); the chunk-position invariant applies to `review` records only. The
entry header is unchanged for a first send (`| attempt N ---`, E9); a resend appends
`| send k of 3`; synthesis is `--- exchange N | synthesis | attempt A ---`. New fields go on
new lines (`model    :`, `tokens   :`), so every asserted line keeps its exact text.

### D17 — The reusable workflow

**Decision** (full contract in `contracts/workflow.md`):
- `.github/workflows/code-review.yml` in the agent repository, `on: workflow_call`.
- Inputs: `model`, `story_source`, `checklist_repo`, `dry_run` (default **true**),
  `llm_log` (default false), `fail_on_contradiction` (default false), plus `llm_provider`
  (default `claude`) and `agent_ref` (default `master`), which the run cannot work without.
- Secrets: `llm_api_key` (required), `review_bot_token` (optional).
- **Which token does what** — the decision that makes the permissions block meaningful:
  reads of the PR and issues, and all posting, use the job's `github.token`, so the
  `permissions:` block (`contents: read`, `pull-requests: write`, `issues: write`) *is* the
  agent's authority. `review_bot_token` is used only to clone the checklist repository,
  which `github.token` cannot read when that repository is private. It falls back to
  `github.token` when omitted, which works for a public checklist repository.
- Draft and fork pull requests are skipped by a job-level `if:`; a sibling `skipped` job
  with the inverse condition prints the reason (FR-029, "a stated reason").
- `concurrency: ai-review-${{ github.repository }}-${{ github.event.pull_request.number }}`,
  `cancel-in-progress: true`, inside the reusable workflow so callers stay thin.
- `on: pull_request` in the caller — never `pull_request_target`.
- The log is uploaded with `actions/upload-artifact@v4`, `retention-days: 3`,
  `if: always() && inputs.llm_log`.
- The agent checks itself out by `agent_repository`/`agent_ref` inputs because a called
  workflow's `github` context describes the **caller**, not the workflow's own repository.

### D18 — Documentation and diagram validation

**Decision**: `docs/review-flow.puml`, `docs/code-structure.md`, `docs/github-setup.md`,
with README and CLAUDE.md updated. PlantUML is not installed; validation downloads
`plantuml.jar` into the scratch directory and renders with the local Java. If that Java is
too old for the current jar, an older jar release that supports Java 8 is used. Sending the
diagram to a public PlantUML server is **not** done without asking: it is outward-facing.
If neither works, the validation is recorded as not performed, not claimed.

### D19 — The three repositories (T7)

**Decision**: Work is mapped **by content, not by variable name** (E22). The requester is
told to rename `GIT_REPO_CODE_SAMPLE` ↔ `GIT_REPO_CODE_REVIEW_CodeReviewAgent` in `.env`;
the agent itself never reads either variable.
- **Agent** (`vijayclarion/codereviewagent`): this working copy *is* its master (E23). Add it
  as `origin`, push `007-github-and-cross-file`, open a PR.
- **Sample** (`vijayclarion/codereviewsample`): branch with the caller workflow, the issue
  template, `.gitignore` check; create the sample issue; a second branch with the demo change
  (an `ICartService` signature change that `CartController` does not follow, plus one
  violation of a rule that exists in the checklist corpus); open both PRs.
- **Checklist** (`vijayclarion/codereviewchecklist`): has no `.gitignore`; a PR adds one with
  `.env`. No other change.

Every push, issue and PR is confirmed with the requester before it is made. Secrets are
never set by the agent (FR-037/038).

### D20 — Testing strategy

**Decision**:
- **Unit**: `github_client` transport with `responses` (URLs, pagination, merge base, 404 →
  None, 422 fallback, GHES URL derivation, GraphQL); `stories` (body regex, criteria
  section, checkboxes, dedupe); `declarations`, `chunk_planner` (edges, grouping, budget,
  hunk split, determinism); `llm_adapter` usage extraction per provider and `.sends`;
  `llm_log` new lines and totals; config platform validation.
- **Contract**: boundary tests extended (`github_client.py` is the only module with the
  GitHub API's markers; `requests` allowed there; new modules read no environment and run no
  git); no-secrets-leak for the four GitHub token names and the clone header; preview makes
  no writes on GitHub; the cross-file acceptance (`ICartService`/`CartController`,
  together and forced apart); every send logged; workflow file invariants.
- **Integration**: an equivalent of `test_us1_review` / `test_us3_posting` against
  `FakeGitHubClient` (protocol-level fake in `tests/fakes_github.py`), including the
  re-run-adds-nothing case.
- **Workflow file test**: parsed with PyYAML, added to `requirements-dev.txt` — a test-only
  dependency, not a runtime one (FR-040).
- `tests/fakes.py` and every existing test file stay untouched; only `conftest.py` changes
  (D5).
