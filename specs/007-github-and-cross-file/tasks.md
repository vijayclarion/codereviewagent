---
description: "Task list for 007 GitHub Platform Support and Cross-File Review"
---

# Tasks: GitHub Platform Support and Cross-File Review

**Input**: `specs/007-github-and-cross-file/` — plan.md, spec.md, research.md (D1-D20, E1-E24),
data-model.md, contracts/, quickstart.md
**Tests**: **Required** — spec FR-039 (unit, contract, fake-backed integration for every new
module; a GitHub suite equivalent to the TFS one). Within each story, tests are written first
and must fail before the implementation task that satisfies them.

**The contract**: `python -m pytest tests` → **597 passed at `7eddb98`** (never `-q`).
Every checkpoint below re-runs it. A count of pre-existing passing tests below 597 is a stop:
fix the implementation, never the existing test. The only existing test files that may change
are `tests/conftest.py` (T003) and `tests/contract/test_import_boundaries.py` (T012).

**Outward-facing tasks** are marked **⚠ confirm**: push, issue, PR, upload. Ask the requester
immediately before each one. Never set a secret value. Never print a token — check presence by
count or status code only.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable — different file, no dependency on an incomplete task
- **[USn]**: the spec's user story

---

## Phase 1: Setup

- [X] T001 Re-measure the baseline with `python -m pytest tests` and record the exact count and commit at the top of `specs/007-github-and-cross-file/validation.md` (create the file; it collects every measured result of this feature)
- [X] T002 [P] Add `pyyaml>=6.0` to `review_agent/requirements-dev.txt` with a comment "test-only: workflow contract test (007 D20)"; do not touch `review_agent/requirements.txt`
- [X] T003 [P] In `tests/conftest.py::_isolate_env`, add the prefixes `GH_`, `GITHUB_`, `GIT_REPO_` and the exact names `PLATFORM`, `STORY_SOURCE` to the cleared set (research D5, E20); run the suite — still 597

---

## Phase 2: Foundational (blocks every story)

**Purpose**: the platform seam and the shared model/config, invisible on TFS.

- [X] T004 [P] Add tests in `tests/unit/test_models_007.py` for: `ChangeEntry` and `Revision` construction; `CrossFileIssue` invariants (severity set, non-empty issue, ≥ 2 distinct files); `PullRequestContext.from_github` (title, body, branches, `is_draft`, `is_fork` when `head.repo.full_name != base.repo.full_name`); `ChangedFile.content` excluded from equality and repr; `ReviewReport.cross_file_issues` default `()`, `synthesis` default `"not needed"`; `has_blocking_findings` true for a `high` cross-file issue
- [X] T005 Implement in `review_agent/models.py` per data-model.md: `ChangeEntry`, `Revision`, `CrossFileIssue`, `PullRequestContext` fields `platform`/`is_draft`/`is_fork` + `from_github`, `ChangedFile.content` (`field(default="", compare=False, repr=False)`), `ReviewReport` fields `cross_file_issues`/`synthesis`/`usage`, and the `has_blocking_findings` extension. Summary wording uses `platform` later (T029)
- [X] T006 [P] Add tests in `tests/unit/test_config_platform.py` per `contracts/configuration.md`: default `PLATFORM=tfs` reproduces today's `Config`; `PLATFORM=github` requires `GH_REPOSITORY` (owner/name pattern), PR number (`GH_PR_NUMBER` or `pr_id_override`), and a read token; aliases `GITHUB_REPOSITORY`, `GITHUB_TOKEN`, `GIT_REPO_TOKEN`, `GITHUB_API_URL`; `GH_TOKEN_FOR_PR` required only when not dry run; `GH_CHECKLIST_TOKEN` defaults to the read token; `GH_AGENT_REPO` required unless `--local`; TFS settings not required on GitHub and vice versa; `STORY_SOURCE` defaults and mismatch errors; `LLM_MAX_PROMPT_TOKENS` ≥ 8000, `LLM_MAX_OUTPUT_TOKENS` ≥ 256 and < half the budget, `LLM_MAX_CHUNK_LINES` unset → 0; price settings parse as non-negative decimals; `pr_id`, `gh_web_url` (`https://github.com` for `https://api.github.com`; `https://host` for `https://host/api/v3`), `gh_graphql_url`; every GitHub token value registered with `redact` and absent from `repr(config)`; all problems reported together
- [X] T007 Implement T006 in `review_agent/config.py`: new `Config` fields and properties, `SECRET_FIELDS` and `SECRET_ENV_NAMES` additions, platform-conditional validation inside `load_config` (keep every existing message text identical for TFS), `llm_max_chunk_lines` default 0; nothing outside `config.py` reads the environment
- [X] T008 In `review_agent/llm_log.py` use `getattr(config, "pr_id", None) or getattr(config, "tfs_pr_id", 0)` in `open_session` (lines 355, 361) so `tests/unit/test_llm_log.py`'s `FakeConfig` keeps working
- [X] T009 [P] Add tests in `tests/unit/test_platform.py`: `TfsPlatform` over `FakeTfsClient` (from `tests/fakes.py`, unmodified) returns a `PullRequestContext`, a `Revision` matching `diff_builder.resolve_iteration`, the raw change entries, file content and threads by delegation; `deliver` produces **exactly** the `writes` list that `output_layer.post_plan(plan, fake, prior)` produces for the same plan (compare both lists); `post_summary` with and without a prior summary, and with `fail_patch=True` falling back to `add_comment`; no iterations → `DegradedReview` with the existing message; `make_platform(config, tfs_factory=lambda c: fake)` uses the factory it is given
- [X] T010 Implement `review_agent/platform.py` per `contracts/platform-client.md`: a `typing.Protocol` `PlatformClient`, `TfsPlatform` (composition only — calls nothing outside `FakeTfsClient`'s 12 methods, research E5), and `make_platform(config, tfs_factory)` with the TFS branch only for now. No `requests`, no `subprocess`, no environment reads, and no GitHub URL fragments in docstrings (quickstart trap 4)
- [X] T011 Make `review_agent/diff_builder.py::build_change_set` accept `ChangeEntry` objects as well as TFS entry dicts (one helper that yields `(path, change_type, is_folder)`), and store the fetched `after` text in `ChangedFile.content`; add cases to a new `tests/unit/test_diff_builder_entries.py`
- [X] T012 Extend `tests/contract/test_import_boundaries.py`: add `github_client.py` to `MAY_IMPORT_REQUESTS`; assert `platform.py`, `stories.py`, `declarations.py`, `chunk_planner.py` import neither `requests` nor `subprocess`, read no environment, and invoke no git (skip a module that does not exist yet with `pytest.skip`, so the test tightens as files land)
- [X] T013 Route `review_agent/main.py::run_review` through the platform (Call Site Ledger rows 218-244, 150-152, 428): `platform = make_platform(config, tfs_factory=TfsClient)` with `TfsClient` resolved inside the function body; `_report_degraded` uses `platform.post_summary`; `_deliver` uses `platform.deliver`; `read_prior_feedback(platform)`; `checklist_module.fetch_checklist(platform, ...)`
- [X] T014 **Checkpoint**: `python -m pytest tests` — the 597 pre-existing tests pass unmodified, plus T004/T006/T009/T011 tests. Record in `validation.md`

---

## Phase 3: User Story 1 — Review a GitHub pull request (P1) 🎯 MVP

**Goal**: preview and posting against a GitHub PR, one review for all inline comments, summary
edited in place, TFS unchanged.
**Independent test**: GitHub integration suite with `FakeGitHubClient` passes; full suite still green.

### Tests (write first, must fail)

- [X] T015 [P] [US1] Create `tests/fixtures/github_pr.py`: a PR payload (number 12, head/base SHAs, `draft`, `head.repo.full_name`, `commits: 2`), two pages of `/pulls/12/files` (Link header), a compare payload with `merge_base_commit.sha`, raw file contents at head and merge base for the `CartController.cs` demo, review comments and issue comments carrying `ai-review:` markers, an issue payload, a GraphQL `closingIssuesReferences` payload
- [X] T016 [P] [US1] Create `tests/fakes_github.py::FakeGitHubClient` implementing the `PlatformClient` protocol over T015 fixtures, recording `calls` and `writes` (`post_summary`, `create_review`, `update_summary`), with variants `refuse_inline` (simulates 422) and `threads=` for prior comments
- [X] T017 [P] [US1] `tests/unit/test_github_client.py` with `responses`: headers (`Bearer`, `application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, User-Agent); every page of `/files` read; base = merge base, not `base.sha`; contents via raw media type, 404 → `None`; `get_threads` maps review comments to `{id, threadContext:{filePath:"/"+path}, comments:[...]}` and issue comments to context-less threads; GHES base URL `https://ghe.example/api/v3`; errors per the contract table (401, 403, 403 on issue → `WorkItemAccessDenied`, 404 on PR with "check GH_REPOSITORY and GH_PR_NUMBER", 429 with `Retry-After` honoured ≤ 30 s, unreachable read → `DegradedReview`, unreachable write → `SetupFailure`); no token in any raised message
- [X] T018 [P] [US1] `tests/unit/test_github_delivery.py` with `responses`: summary created via `POST /issues/12/comments` when no prior, `PATCH /issues/comments/{id}` when prior; inline comments sent as **one** `POST /pulls/12/reviews` with `event: "COMMENT"`, `commit_id` = head SHA, `side: "RIGHT"`; zero inline → no review call; 422 → second review with `comments: []` and a body listing each refused finding and the reason; `write_count` counts both clients
- [X] T019 [P] [US1] `tests/contract/test_preview_makes_no_writes_github.py`: a dry run with `PLATFORM=github` constructs no `purpose="post"` client (assert via a factory spy) and performs zero writes; the post token is not required
- [X] T020 [P] [US1] `tests/contract/test_github_secrets_never_leak.py`: for each of `GH_TOKEN`, `GITHUB_TOKEN`, `GIT_REPO_TOKEN`, `GH_TOKEN_FOR_PR`, `GH_CHECKLIST_TOKEN`, and the `x-access-token` Basic header and its base64 form: never in stdout/stderr, the LLM log, posted markdown, git argv, the clone's `.git/config`, or exception messages; git children never inherit the token env names (mirror the structure of `test_no_secrets_leak.py` without editing it)
- [X] T021 [P] [US1] `tests/contract/test_github_boundary.py`: the strings `api.github.com`, `/pulls/`, `/repos/`, `graphql`, `closingIssuesReferences`, `X-GitHub-Api-Version` appear in no module except `github_client.py` (and `config.py` for the default API URL and derived GraphQL URL)
- [X] T022 [P] [US1] `tests/integration/test_github_review.py`: `PLATFORM=github` dry run end to end with `FakeGitHubClient` patched in via `main_module` → summary printed, findings anchored to changed lines, summary says "commit <short sha>" instead of "iteration", nothing excluded is sent to the provider, phase log has every phase
- [X] T023 [P] [US1] `tests/integration/test_github_posting.py`: post run → exactly one review with all inline comments + one summary; second run against threads read back from the first → zero new inline comments, `suppressed` = first run's inline count, summary updated in place (US1 AS2-AS4, SC-004 with fakes)
- [X] T024 [P] [US1] `tests/unit/test_source_fetch_github.py`: GitHub clone URL `https://x-access-token@github.com/owner/name.git`, `public_url` without credential, header `Authorization: Basic base64("x-access-token:" + token)` via `GIT_CONFIG_*` env, both forms registered as secrets, GHES host from `gh_web_url`; TFS URLs unchanged (existing `test_source_fetch.py` untouched and passing)

### Implementation

- [X] T025 [US1] Create `review_agent/github_client.py` transport: `GitHubClient(config, session=None, sleep=time.sleep, purpose="read"|"post")`, token per purpose (read → `gh_token`, post → `gh_post_token`), `inject_system_trust()` reused from `tfs_client`, headers per contract, `_request` with retry on 429/502/503/504 and secondary-rate-limit 403 + `Retry-After`, `Link`-header pagination helper, error mapping per `contracts/platform-client.md`, endpoints reported without query strings
- [X] T026 [US1] Add reads to `review_agent/github_client.py`: `get_pull_request_context`, `get_revision` (compare API merge base; iteration = `commits`), `get_changed_files` (status → `ChangeEntry` per data-model mapping; `unchanged` skipped), `get_file_content` (raw media type, 404 → `None`), `get_threads`, `list_items` (git trees API, recursive, mapped to `{path, isFolder}`), `get_file_on_branch`
- [X] T027 [US1] Add writes to `review_agent/github_client.py`: `post_summary(markdown, prior)`, `deliver(plan, prior, pr_context)` (summary first, then one review; 422 fallback with stated reason; returns inline count), `write_count`
- [X] T028 [US1] Add the GitHub branch to `review_agent/platform.py::make_platform`: read client always; post client constructed **only** when `not config.dry_run`, writes delegated to it (data-model "Platform"); import `GitHubClient` inside the function so TFS runs never import it
- [X] T029 [US1] In `review_agent/output_layer.py::render_summary`, when `pr_context.platform == "github"` render `**Reviewed**: PR #<n>, commit <7-char head sha>` instead of `iteration <id>`; TFS text unchanged
- [X] T030 [US1] Make `review_agent/source_fetch.py` platform-aware (research D6): `clone_url`, `public_url`, and a `clone(..., token=None)` parameter whose default is today's `config.tfs_token` on TFS; on GitHub the header uses `x-access-token`; keep `TOKEN_ENV` and the `GIT_CONFIG_*` mechanism; no token in argv
- [X] T031 [US1] In `review_agent/checklist.py` and `review_agent/bootstrap.py`, pass the platform's repository name and token: GitHub checklist → `config.gh_checklist_repo` with `gh_checklist_token`; GitHub agent → `config.gh_agent_repo` with `gh_token`; TFS paths unchanged; `checklist.py` still invokes no git (boundary test T018 of 003)
- [X] T032 [US1] In `review_agent/main.py`, emit `phase=pullrequest ... platform=github draft=<bool>` and, for a draft PR reviewed locally, a note in the summary "This pull request is a draft"; update `EPILOG` with the GitHub settings
- [X] T033 [US1] **Checkpoint**: full suite green (597 pre-existing unmodified + all US1 tests); record in `validation.md`

---

## Phase 4: User Story 2 — Judge a GitHub PR against its linked issue (P2)

**Goal**: per-criterion verdicts from GitHub Issues, same as TFS.
**Independent test**: a PR linked to an issue with three criteria yields three verdicts.

### Tests

- [X] T034 [P] [US2] `tests/unit/test_issue_parsing.py`: `WorkItem.from_issue` with `## Acceptance criteria` checkbox list, plain bullet list, `### acceptance Criteria` (case and level), nested bullets folded into their parent, criteria section stops at the next heading, `[x]`/`[ ]` stripped, no section → criteria from description, labels → tags, `ordinal_start` honoured across two issues
- [X] T035 [P] [US2] `tests/unit/test_stories.py`: `STORY_SOURCE` selection and platform defaults; `none` → empty with reason "story source is none"; body regex matches `Closes #7`, `fixes #7`, `Resolved #7`, not `#7` alone or `closes 7`; union with GraphQL numbers deduplicated (US2 AS1 — issue read once); `owner/other#3` reported "in another repository and was not read"; a number that is a PR reported and skipped; an issue read refused (`WorkItemAccessDenied`) → story half lost with stated reason, review continues; TFS path returns exactly what `main._fetch_story` returned before (run against `FakeTfsClient`)
- [X] T036 [P] [US2] `tests/unit/test_github_issues.py` with `responses`: GraphQL POST to `gh_graphql_url` with the `closingIssuesReferences` query (first: 50), GHES GraphQL URL, GraphQL `errors` array → notes not exception, `get_issue` 404 → `None` with note
- [X] T037 [P] [US2] `tests/integration/test_github_stories.py`: issue #7 with three criteria → summary table has three rows with statuses from the fake response; a `possible_contradiction` produces an inline/summary comment keyed `wi7:c<n>`; a `not_addressed` produces no comment (FR-016 rule, mirrors `tests/unit/test_routing_not_addressed.py`)

### Implementation

- [X] T038 [US2] Implement `WorkItem.from_issue` in `review_agent/models.py` (data-model "Stories"); reuse `textutil.split_criteria` after stripping checkbox markers
- [X] T039 [US2] Implement `linked_issue_numbers()` (GraphQL ∪ body regex, same repository only, returns numbers + notes) and `get_issue(number)` in `review_agent/github_client.py`
- [X] T040 [US2] Create `review_agent/stories.py::fetch_stories(config, platform, log) -> StoryOutcome`: TFS logic moved verbatim from `main._fetch_story` (same phase line `phase=workitems count=.. criteria=..`); GitHub-issues reader; notes appended to the summary notes; leave `main._fetch_story(client, log)` as a one-line delegate
- [X] T041 [US2] Wire `stories.fetch_stories` into `review_agent/main.py::run_review` and add the outcome's notes to `notes`
- [X] T042 [P] [US2] Stage the sample repository's issue template at `specs/007-github-and-cross-file/sample-repo/.github/ISSUE_TEMPLATE/user-story.md` (front matter `name: User story`, `labels: [user-story]`; sections `## Description` and `## Acceptance criteria` with three `- [ ]` placeholders); copied to the sample repository in T084
- [X] T043 [US2] **Checkpoint**: full suite green; record in `validation.md`

---

## Phase 5: User Story 3 — Catch defects that span files (P2)

**Goal**: token budget, outline, dependency-aware chunks, hunk pieces, synthesis, cross-file section.
**Independent test**: `tests/integration/test_cross_file_cart.py` passes with the files together and forced apart.

### Tests

- [X] T044 [P] [US3] Create `tests/fixtures/cross_file_cart.py`: `src/eShop.Api/Services/Interfaces.cs` changing `void AddItem(int productId, int quantity);` to `void AddItem(int productId, int quantity, string couponCode);`, `src/eShop.Api/Controllers/CartController.cs` with an unrelated edit that still calls `AddItem(productId, quantity)`, `src/eShop.Api/Models/Cart.cs` edit, a large unrelated file to force splitting, and fake provider responses: a chunk response with `cross_file_issues` naming both files; a chunk response without; a synthesis response with the cross-file issue
- [X] T045 [P] [US3] `tests/unit/test_declarations.py`: C# class/interface/record/enum/method signatures added and removed from a diff; Java and TypeScript equivalents; Python `class`/`def`; `types` set; unsupported extension → `supported=False`; `skeleton()` keeps types, fields and member signatures and drops bodies; outline rendering lists every file with change type, `+a/−r`, chunk numbers and declarations, and states "declarations not extracted for this file type"
- [X] T046 [P] [US3] `tests/unit/test_chunk_planner.py`: token estimate `ceil(chars/3)`; diff budget = budget − fixed − output reserve; edges for shared type name, `IFoo`↔`Foo`, `: IFoo`, same stem after suffix stripping, source↔test; components packed first-fit-decreasing; a component over budget split greedily; determinism (same input twice → same plan; ties by path); oversized file → hunk pieces each with skeleton and `part i of n`; single hunk over budget → line split with `split_inside_hunk=True`; `LLM_MAX_CHUNK_LINES` cap applied only when > 0; every reviewed file assigned to ≥ 1 chunk
- [X] T047 [P] [US3] `tests/unit/test_cross_file_parsing.py`: review response with no `cross_file_issues`/`change_notes` validates (every existing fixture shape); with them, parsed; < 2 files → demoted to code issue; `change_notes` truncated at 2,000 chars; `parse_synthesis` requires non-empty summary, accepts absent coverage/cross_file_issues, ignores other keys; merge rules 1-5 of `contracts/llm-response.md`, including synthesis winning a key collision and unmatched merged verdicts kept
- [X] T048 [P] [US3] `tests/unit/test_cross_file_output.py`: `cross_file_key` sorted and normalized; inline at a mapped anchor, summary-only otherwise; summary always has `### Cross-file issues (N)` with "None found" when empty; every involved file named; fingerprint marker `ai-review:cross-file:<fp>`; re-run with prior marker suppresses it
- [X] T049 [P] [US3] `tests/integration/test_cross_file_cart.py` (quickstart §4): **together** — default budget, one provider call, cross-file issue reported naming both files, outline lists `AddItem` removed and added for `Interfaces.cs`; **apart** — budget set so `ChunkPlan.assignment` puts the two files in different chunks (assert it), the fake returns the issue only from the synthesis call, the issue is reported; synthesis prompt contains the outline and both chunks' change notes
- [X] T050 [P] [US3] `tests/integration/test_synthesis_failure.py`: synthesis response unparseable twice → per-chunk findings delivered, `report.synthesis` starts `failed:`, summary note "Synthesis did not complete"; exit 0; single-chunk run makes no synthesis call and `report.synthesis == "not needed"`
- [X] T051 [P] [US3] `tests/integration/test_single_call_default.py`: the existing demo fixture and the cart fixture each produce exactly one provider call at default settings (SC-005)

### Implementation

- [X] T052 [US3] Create `review_agent/declarations.py` (research D9): `extract`, `skeleton`, `Declarations`; regexes per language family; pure functions, no I/O
- [X] T053 [US3] Create `review_agent/chunk_planner.py` (research D8, D10, D11): `estimate_tokens`, `plan_chunks(reviewable, fixed_text, config) -> ChunkPlan`, `ChunkPiece`, union-find grouping, FFD packing, hunk splitting with skeletons, `render_outline(plan)`
- [X] T054 [US3] Update `review_agent/prompt_builder.py`: `build_prompts` builds from `ChunkPlan` (keep `chunk_files` and `estimated_size` for compatibility); add the PR outline section to every chunk prompt; render pieces as `### path (edit) — part i of n` + skeleton; add the cross-file rule and `change_notes` instruction to `RULES` and the new keys to `CONTRACT` (`contracts/llm-response.md`); add `build_synthesis_prompt(outline, work_items, merged, notes)`
- [X] T055 [US3] Update `review_agent/parser.py`: optional `cross_file_issues` and `change_notes` in `validate_payload`, demotion rule, `cross_file_key`, `merge_results` union, `parse_synthesis`, `apply_synthesis`, `build_report` carries `cross_file_issues`
- [X] T056 [US3] In `review_agent/llm_log.py`, add `ExchangeRecord.kind` (`review`|`synthesis`, chunk invariant only for `review`) and the synthesis header `--- exchange N | synthesis | attempt A ---` (contracts/log-format.md); review headers byte-identical
- [X] T057 [US3] In `review_agent/main.py::run_review`: plan chunks → prompts → per-chunk loop → when `len(chunks) > 1` one synthesis call through `parse_with_retry` and a `_recording_sender(kind="synthesis")`; catch `DegradedReview` from synthesis only, set `report.synthesis` and add the note; phase line `phase=synthesis outcome=ok|failed|skipped`
- [X] T058 [US3] In `review_agent/output_layer.py`: route `cross_file_issues` (kind `cross-file`, identity `cross_file_key`) in `build_inline_comments`; add the `### Cross-file issues (N)` summary section after "Code issues"
- [X] T059 [US3] In `review_agent/llm_adapter.py`, send `config.llm_max_output_tokens` as Claude `max_tokens` (and `max_tokens` for OpenAI/Azure, `num_predict` for Ollama via `options`), defaulting to 8192 when the config lacks the attribute (unit-test configs)
- [X] T060 [US3] **Checkpoint**: full suite green. If the always-present cross-file section breaks a pre-existing test, render it only when the review had > 1 chunk or ≥ 1 cross-file issue, and record the reason in `research.md` D13 — never edit the test
- [X] T061 [US3] Measure against the real sample corpus (fetch `src/` of `vijayclarion/codereviewsample` read-only with `GIT_REPO_TOKEN`): estimated tokens of the fixed sections with the five real checklist documents, and the diff budget left; record in `validation.md` (research D8 asks for this measurement)

---

## Phase 6: User Story 4 — Central reusable workflow (P3)

**Goal**: one reusable workflow; a ~15-20 line caller; least privilege; drafts and forks skipped.
**Independent test**: `tests/contract/test_workflow_contract.py` passes; live in T094.

- [X] T062 [P] [US4] `tests/contract/test_workflow_contract.py` (PyYAML): the eight invariants of `contracts/workflow.md` against `.github/workflows/code-review.yml` and `specs/007-github-and-cross-file/sample-repo/.github/workflows/ai-review.yml`; also no `pull_request_target` in any `*.yml` under either path
- [X] T063 [US4] Create `.github/workflows/code-review.yml` per `contracts/workflow.md`: `workflow_call` inputs and secrets, `review` job (`if`, `permissions`, `concurrency`, `timeout-minutes: 15`), steps `actions/checkout@v4` (`repository: inputs.agent_repository`, `ref: inputs.agent_ref`, `persist-credentials: false`), `actions/setup-python@v5` (3.12, pip cache), `pip install -r review_agent/requirements.txt`, `python -m review_agent --local` with the env table (plus `LLM_LOG_DIR: ${{ github.workspace }}/.llm-logs`), `actions/upload-artifact@v4` (`if: always() && inputs.llm_log`, `retention-days: 3`, name `llm-log-pr-${{ github.event.pull_request.number }}`); `skipped` job printing the stated reason
- [X] T064 [US4] Stage the caller at `specs/007-github-and-cross-file/sample-repo/.github/workflows/ai-review.yml` per the contract, with `uses: vijayclarion/codereviewagent/.github/workflows/code-review.yml@007-github-and-cross-file` (the reusable workflow is not on `master` until the agent PR merges; switching to `@master` is T100) and the model id taken from `.env` `LLM_MODEL` (not a secret — read its value without printing any other variable)
- [X] T065 [US4] **Checkpoint**: full suite green

---

## Phase 7: User Story 5 — Every prompt, response, token count and cost (P3)

**Goal**: every send logged with provider-reported usage; run totals and cost in log and console; logging cannot crash a review.
**Independent test**: a two-chunk run with one transport retry has an entry per send including synthesis, and the total equals the sum.

### Tests

- [X] T066 [P] [US5] `tests/unit/test_llm_usage.py` with `responses`: `call_llm` returns an `LlmText` that `isinstance(str)` and equals the text; `.usage` from Claude `usage.input_tokens/output_tokens`, OpenAI and Azure `usage.prompt_tokens/completion_tokens`, Ollama `prompt_eval_count/eval_count`; absent usage → `None`; a 429 then 200 → `.sends` has two records (`retried` with `HTTP 429`, then `ok`); a timeout ×3 → `DegradedReview` carrying `.sends` of three; a 401 → `SetupFailure` carrying `.sends`
- [X] T067 [P] [US5] `tests/unit/test_llm_log_usage.py`: entry has `model    :` and `tokens   :` lines; `tokens   : not reported` when None; resend header `| attempt 1 | send 2 of 3 ---`; all strings asserted in research E9 still present for a first send; `RunUsage.describe()` with prices, without (`not estimated`), and partial; foot writes `usage    :` immediately before the unchanged `=== end` line; `usage    : no exchange` for zero calls; a record whose construction raises `ValueError` disables the session with one stated line and does not propagate
- [X] T068 [P] [US5] `tests/contract/test_every_send_is_logged.py`: with logging on and a fake `call_llm` returning `LlmText` objects carrying `.sends` (one transport retry), a forced two-chunk review → `text.count("--- exchange ")` == total sends including synthesis; log totals == sum of fake usage; console shows `llm usage:` with the same totals; the same run with logging **off** still prints `llm usage:`
- [X] T069 [P] [US5] `tests/contract/test_llm_log_usage_redacted.py`: a registered secret placed in the model name, a response, and a failure reason never appears in the log, including the new lines

### Implementation

- [X] T070 [US5] In `review_agent/llm_adapter.py` (research D14): `TokenUsage`, `SendRecord`, `LlmText(str)` with `.usage` and `.sends`; per-provider usage extraction (only here); attach `.sends` to every raised `DegradedReview`/`SetupFailure`; signature of `call_llm` unchanged
- [X] T071 [US5] In `review_agent/llm_log.py` (research D15, D16): `ExchangeRecord` fields `send`, `provider`, `model`, `input_tokens`, `output_tokens`; render the new lines and resend header; `RunUsage`; `LogSession.add_usage` / `close` writes the usage line before the end line; `_guarded` catches `Exception`
- [X] T072 [US5] In `review_agent/main.py::_recording_sender`: when the response or exception has `.sends`, write one record per send (prompt repeated, outcome per send); otherwise one record as today; build records inside the session guard; accumulate `RunUsage` for the run (independent of logging); add `tokens_in=`, `tokens_out=`, `cost=` to the `phase=llm` line and emit `llm usage: ...` once at the end of `run_review` on every path that made a call (including degraded)
- [X] T073 [US5] **Checkpoint**: full suite green; `tests/integration/test_llm_log_run.py` and `tests/unit/test_llm_log.py` pass unmodified

---

## Phase 8: User Story 6 — Understand, set up, onboard (P3)

**Goal**: diagram, structure doc, setup guide; README and CLAUDE.md current.
**Independent test**: diagram renders; a reader can onboard a repo from `docs/github-setup.md` alone.

- [X] T074 [P] [US6] Write `docs/review-flow.puml`: activity diagram with swimlanes Developer, GitHub/TFS, Workflow, Agent, LLM; both platform branches (PLATFORM switch), story source selection, checklist clone, revision + merge base, selection, prior feedback, chunk planning, per-chunk calls with parse retry and transport retry, synthesis when > 1 chunk (and its failure path), degraded paths (unreachable provider → degraded summary, exit 0), dedupe, DRY_RUN branch (print vs post; one GitHub review vs TFS threads), exit codes; notes with the worked example — issue #7 "Add item to cart" with 3 criteria → PR #12 changing 4 files → 2 chunks → findings → posted comments — labelled as illustrative numbers
- [X] T075 [US6] Validate the diagram renders: download `plantuml.jar` to the scratchpad directory (if the current release refuses Java 8, use the newest release that supports Java 8), run `java -jar plantuml.jar -tsvg docs/review-flow.puml -o <scratch>`, fix any syntax error; also render `docs/local-mode-pr-review-activity.puml` unchanged as a control. Do **not** send the diagram to a public PlantUML server without asking. Record the outcome — or "not validated" with the reason — in `validation.md`
- [X] T076 [P] [US6] Write `docs/code-structure.md`: repository tree; then for **every** file in `review_agent/`, `tests/` (each file, fixtures and fakes included), `specs/` (per feature directory and its artifacts), `docs/`, `.github/`, and config files (`pytest.ini`, `.gitignore`, `requirements*.txt`, `.env.example`): purpose, responsibility, main functions/classes, inputs/outputs, depends on, called by. Generate the "called by" column from an AST import scan, not from memory, and state that it was generated
- [X] T077 [P] [US6] Write `docs/github-setup.md`: tokens and permissions (table from `contracts/configuration.md`), the two Actions secrets and where to add them, onboarding a new repository (the caller file, ≤ 20 lines, and why it states its own permissions), `@ref` pinning, local run steps for GitHub and TFS, the LLM log warning (contains source code; 3-day artifact), troubleshooting (401/403/404/422, refused inline anchors, draft/fork skip, checklist clone failure on a private repo, GHES URLs, `TFS_API_VERSION=5.0` reminder)
- [X] T078 [US6] Update `review_agent/README.md` and `review_agent/.env.example`: every new setting with meaning and default (FR-035); `LLM_MAX_CHUNK_LINES` meaning change; GitHub quick start
- [X] T079 [US6] Update `CLAUDE.md`: configuration notes for GitHub runs, the Architecture invariants table (+ `github_client.py` is the only module that speaks the GitHub API; workflow invariants), Known state (GitHub supported, cross-file review), and the measured test count

---

## Phase 9: User Story 7 — Live demonstration across the three repositories (P3)

**Goal**: the Definition of Done, observed live.
**Independent test**: the demo PR's comments, and a second run that adds nothing.

- [ ] T080 [US7] Preflight, values never printed: confirm by count that `.env` holds `GIT_REPO_TOKEN`, `LLM_API_KEY`, `LLM_MODEL`, `TFS_PAT`; remind the requester the `GIT_REPO_*` URL variables are swapped (E22); confirm `gh` CLI availability (`gh --version`) or plan REST calls via a scratch Python script that reads the token from `.env` itself
- [ ] T081 [US7] TFS live preview: `TFS_API_VERSION=5.0 python -m review_agent --local --dry-run --pr <a known TFS PR>` → completes, zero writes, `llm usage:` shows real counts; record phase lines (redacted output) in `validation.md` (SC-002 TFS half)
- [ ] T082 [US7] ⚠ confirm — Agent repository: `git remote add origin <GIT_REPO_CODE_SAMPLE URL, which is the agent repo per E22>` (verify it resolves to `vijayclarion/codereviewagent` first), commit the feature on `007-github-and-cross-file` (commit message ends with the Co-Authored-By line), push the branch, open a PR to `master` with a summary and the 🤖 footer. Never push `master`
- [ ] T083 [US7] Clone `vijayclarion/codereviewsample` and `vijayclarion/codereviewchecklist` into the scratchpad directory (credential via header, not URL); read `src/eShop.Api/**` and the checklist documents; record which checklist rule identifier the demo will violate (run `checklist_docs` over the clone and pick a rule whose violation is unambiguous in C#, e.g. a hard-coded secret or missing input validation)
- [ ] T084 [US7] ⚠ confirm — Sample repository, branch `ai-review-setup` from `master`: copy `sample-repo/.github/workflows/ai-review.yml` and `sample-repo/.github/ISSUE_TEMPLATE/user-story.md`; ensure `.gitignore` contains `.env`; commit, push, open PR "Add AI review caller workflow and user-story template"
- [ ] T085 [US7] ⚠ confirm — Create the sample issue in `codereviewsample` from the template: title "Add item to cart with coupon", Description, and exactly three `- [ ]` acceptance criteria (one the demo implements, one it leaves unaddressed, one it contradicts); record its number
- [ ] T086 [US7] ⚠ confirm — Branch `demo/cart-coupon` **from `ai-review-setup`** (so the `pull_request` run uses the caller workflow): change `ICartService.AddItem` in `src/eShop.Api/Services/Interfaces.cs` to add `string couponCode` and leave `CartController.cs` calling the old signature (the deliberate cross-file defect); add the one checklist violation from T083 in `CartController.cs`; PR body with `Closes #<issue>` and a Covered / Not in this PR section; push; open the PR against `master`
- [ ] T087 [US7] GitHub live preview from this machine: `PLATFORM=github GH_REPOSITORY=vijayclarion/codereviewsample GH_CHECKLIST_REPO=vijayclarion/codereviewchecklist python -m review_agent --local --dry-run --log-llm --pr <demo PR>` → zero writes, three criterion verdicts, the cross-file finding, the checklist violation, real token counts in the log; record in `validation.md` (SC-002 GitHub half)
- [ ] T088 [US7] Hand the requester the secrets list (plan.md "Secrets") and wait until they confirm `AI_REVIEW_LLM_API_KEY` (and optionally `AI_REVIEW_BOT_TOKEN`) are set on `codereviewsample`; do not proceed, and do not work around, if they are not (FR-041)
- [ ] T089 [US7] Observe the workflow run on the demo PR (triggered by the push or by re-running): job green, inline comments on the defect lines in **one** review, one summary with verdicts and `### Cross-file issues (1)`; record run URL and counts in `validation.md`
- [ ] T090 [US7] ⚠ confirm — Re-run the workflow on the unchanged demo PR: phase log `suppressed=N inline=0`, summary edited in place, no new comment (SC-004; closes `contracts/finding-identity.md` only when observed)
- [ ] T091 [US7] Verify the draft/fork skip live: mark the demo PR draft → `skipped` job prints the reason, `review` job skipped; mark ready → review runs (`ready_for_review`); record
- [ ] T092 [US7] ⚠ confirm — Checklist repository: branch `add-gitignore`, `.gitignore` containing `.env`, push, open PR
- [ ] T093 [US7] Secret scan of every pushed branch in all three repositories: in a scratch script, load the token values from `.env` and search `git log -p <branch>` for each value and its base64 forms; print only the count of hits per branch (expected 0); record in `validation.md`

---

## Phase 10: Polish & cross-cutting

- [ ] T094 **Q1-gated — do not start without the requester's yes**: in `review_agent/platform.py::make_platform`, give TFS a separate `TfsClient(config, purpose="post")` writer constructed only when not dry run (research D4); test in `tests/unit/test_tfs_post_token.py` (dry run builds no post client; posting uses `TFS_PAT_FOR_PR`); full suite green; note the behaviour change in `CLAUDE.md`
- [X] T095 [P] Full suite: record the final count in `validation.md`, `CLAUDE.md` and `docs/code-structure.md`
- [X] T096 [P] Re-read the Call Site Ledger in `plan.md` against `git diff master --stat`; any file changed that the ledger does not list is either added to the ledger with a reason or reverted
- [X] T097 [P] Confirm `tfs_client.py`, `dedupe.py`, `tests/fakes.py` and every pre-existing test file except `tests/conftest.py` and `tests/contract/test_import_boundaries.py` are byte-identical to `7eddb98` (`git diff --stat 7eddb98 -- <paths>`)
- [X] T098 [P] Run `python -m tests.demo.run` (feature 003's self-contained demo) — still succeeds
- [ ] T099 Mark spec Definition-of-Done items in `validation.md` with evidence links (run URLs, PR links, counts)
- [ ] T100 ⚠ confirm — After the agent PR merges, switch the sample caller's `uses:` ref from `@007-github-and-cross-file` to `@master` in a follow-up PR on `codereviewsample`
- [ ] T101 Prepare the final report (req "Report back"): changes per repository, PR links, test results, the exact secrets list, assumptions, known limitations (heuristic grouping, regex declarations, same-repository issues only, GHES untested live unless available)

---

## Dependencies & Execution Order

```text
Phase 1 Setup ─► Phase 2 Foundational ─┬─► US1 (P1, MVP) ─┬─► US2 ─────────────┐
                                       │                  ├─► US4 workflow ────┤
                                       ├─► US5 logging ───┼─► US3 cross-file ──┤
                                       │   (independent)  │   (T056 needs T005)│
                                       │                  │                    ▼
                                       │                  └──────────────► US6 docs ─► US7 live ─► Polish
```

- **US1** needs Phase 2. **US2**, **US4** need US1 (GitHub client, platform). **US5** needs only
  Phase 2 and can run alongside US1. **US3** needs Phase 2; T057 builds on T013 and benefits from
  US5's per-send records but does not require them. **US6** documents US1-US5. **US7** needs all.
- Within a story: tests → models → modules → `main.py` wiring → checkpoint.
- `main.py` tasks (T013, T032, T041, T057, T072) touch one file — never in parallel.
- `github_client.py` tasks (T025-T027, T039) are sequential.

## Parallel Examples

```text
# Phase 2, together:
T004 tests/unit/test_models_007.py   T006 tests/unit/test_config_platform.py   T009 tests/unit/test_platform.py

# US1 tests, together (all different files):
T015 T016 T017 T018 T019 T020 T021 T022 T023 T024

# US3 tests, together:
T044 T045 T046 T047 T048 T049 T050 T051

# Across stories once Phase 2 is done:
US1 (T025-T032)  ||  US5 tests (T066-T069)  ||  US3 pure modules (T052 declarations, T053 chunk_planner)

# US6 docs, together:
T074 review-flow.puml   T076 code-structure.md   T077 github-setup.md
```

## Implementation Strategy

1. **MVP = Phase 1 + 2 + US1.** Stop at T033: a GitHub PR can be previewed and reviewed with
   fakes, TFS untouched. Demonstrable with T087 alone if the requester wants an early look.
2. Add **US5** (cost visibility) and **US2** (issues) — each independently shippable.
3. Add **US3** — the largest; its acceptance test (T049) is the gate.
4. **US4** workflow, then **US6** docs describing what exists.
5. **US7** live, with a confirmation before each outward step; then Polish.
