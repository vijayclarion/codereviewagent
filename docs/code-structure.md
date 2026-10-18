# Code Structure

Every file in this repository: what it is for, what it is responsible for, its main
functions and classes, what goes in and comes out, what it depends on, and what calls it.

> **Generated in part.** The *depends on* and *called by* columns come from an AST scan of
> every `import` in `review_agent/` and `tests/`, not from memory. Regenerate them when
> modules change. Measured at the end of feature 007.

## Repository tree

```text
.
├── .github/workflows/code-review.yml   reusable GitHub workflow (007)
├── docs/                               diagrams, developer guide, setup guide, this file
├── review_agent/                       the agent package (one responsibility per module)
├── tests/
│   ├── contract/                       architecture invariants - break one, a test fails
│   ├── integration/                    whole pipeline against fakes, no network
│   ├── unit/                           one module at a time
│   ├── demo/                           feature 003's self-contained demo (python -m tests.demo.run)
│   ├── fixtures/                       recorded payloads and builders
│   ├── fakes.py, fakes_github.py       platform and provider stand-ins
│   └── conftest.py                     environment isolation and shared fixtures
├── specs/001-... 007-...               one directory per Spec Kit feature
├── req/                                requirement documents
├── CLAUDE.md, pytest.ini, .gitignore
└── .specify/, .claude/                 Spec Kit tooling
```

Boundaries enforced by `tests/contract/test_import_boundaries.py` and
`tests/contract/test_github_boundary.py`: `config.py` alone reads the environment;
`tfs_client.py` alone speaks TFS REST; `github_client.py` alone speaks the GitHub API;
`llm_adapter.py` alone knows a provider's wire format; `source_fetch.py` (and `bootstrap.py`,
which re-executes) alone run a child process; `checklist_docs.py` alone reads `.xlsx`/`.docx`;
`source_fetch.py` and `llm_log.py` alone delete a path.

## `review_agent/` - the agent

### `review_agent/__init__.py`

- **Purpose**: Package marker.
- **Responsibility**: Holds `__version__`.
- **Main functions/classes**: `__version__`
- **Inputs -> outputs**: -
- **Depends on**: -
- **Called by**: -

### `review_agent/__main__.py`

- **Purpose**: `python -m review_agent` entry point.
- **Responsibility**: Hands control to the bootstrap.
- **Main functions/classes**: -
- **Inputs -> outputs**: argv -> exit code
- **Depends on**: `bootstrap.py`
- **Called by**: -

### `review_agent/bootstrap.py`

- **Purpose**: Fetches the agent repository and re-runs the review inside it, unless `--local`.
- **Responsibility**: Guarantees a review is produced by committed logic, and says which copy ran.
- **Main functions/classes**: `main`, `run_fetched`, `source_from_marker`
- **Inputs -> outputs**: argv, Config -> child process exit code
- **Depends on**: `config.py`, `errors.py`, `main.py`, `models.py`, `run.py`, `source_fetch.py`
- **Called by**: `__main__.py`; tested by 1 test module(s)

### `review_agent/checklist.py`

- **Purpose**: Builds the rule corpus the review measures against.
- **Responsibility**: Obtains the checklist working copy and reads every document; markdown fallback through the platform.
- **Main functions/classes**: `obtain_corpus`, `fetch_checklist`, `matching_files`, `combine`
- **Inputs -> outputs**: Config, platform -> `CombinedChecklist` / `Checklist`
- **Depends on**: `checklist_docs.py`, `config.py`, `errors.py`, `models.py`, `source_fetch.py`
- **Called by**: `main.py`; tested by 7 test module(s)

### `review_agent/checklist_docs.py`

- **Purpose**: Reads `.xlsx` and `.docx` checklists into citable rules.
- **Responsibility**: The only module that knows those formats.
- **Main functions/classes**: `read`, `document_format`, `derive_id`
- **Inputs -> outputs**: file path -> `ChecklistDocument`
- **Depends on**: `models.py`
- **Called by**: `checklist.py`; tested by 2 test module(s)

### `review_agent/chunk_planner.py`

- **Purpose**: Divides a pull request between model calls (007).
- **Responsibility**: Token budget, dependency groups, packing, hunk pieces with skeletons, the PR outline.
- **Main functions/classes**: `plan_chunks`, `render_outline`, `estimate_tokens`, `ChunkPlan`, `ChunkPiece`, `related`, `stem`
- **Inputs -> outputs**: ReviewableSet, fixed prompt text, Config -> `ChunkPlan`, outline markdown
- **Depends on**: `declarations.py`
- **Called by**: `prompt_builder.py`; tested by 1 test module(s)

### `review_agent/config.py`

- **Purpose**: Configuration, validation and secret hygiene.
- **Responsibility**: The only module that reads the environment; the redaction registry; the single output path `emit`.
- **Main functions/classes**: `load_config`, `Config`, `redact`, `register_secret`, `emit`, `child_environment`
- **Inputs -> outputs**: environment / `.env` -> frozen `Config`
- **Depends on**: `errors.py`
- **Called by**: `bootstrap.py`, `checklist.py`, `github_client.py`, `llm_log.py`, `main.py`, `output_layer.py`, `source_fetch.py`; tested by 31 test module(s)

### `review_agent/declarations.py`

- **Purpose**: Declarations a change adds and removes, and file skeletons (007).
- **Responsibility**: Pattern-based extraction for C-family languages and Python.
- **Main functions/classes**: `extract`, `skeleton`, `match_declaration`, `Declarations`
- **Inputs -> outputs**: diff text, path, file content -> `Declarations` / skeleton text
- **Depends on**: -
- **Called by**: `chunk_planner.py`; tested by 1 test module(s)

### `review_agent/dedupe.py`

- **Purpose**: Recovers what the agent already posted.
- **Responsibility**: Reads the `ai-review:` markers back from the platform's threads.
- **Main functions/classes**: `read_prior_feedback`, `PriorFeedback`, `parse_markers`
- **Inputs -> outputs**: platform threads -> `PriorFeedback`
- **Depends on**: `parser.py`
- **Called by**: `main.py`; tested by 4 test module(s)

### `review_agent/diff_builder.py`

- **Purpose**: Turns change entries into unified diffs.
- **Responsibility**: Fetches blobs, computes diffs, and the diff-line -> new-line map for anchoring.
- **Main functions/classes**: `build_change_set`, `build_file_diff`, `map_line`, `resolve_iteration`
- **Inputs -> outputs**: platform, PR context, change entries (TFS dicts or `ChangeEntry`) -> `ChangeSet`
- **Depends on**: `models.py`
- **Called by**: `main.py`, `platform.py`; tested by 6 test module(s)

### `review_agent/errors.py`

- **Purpose**: Error types and exit codes.
- **Responsibility**: The vocabulary of setup failure versus degraded review.
- **Main functions/classes**: `SetupFailure`, `DegradedReview`, `WorkItemAccessDenied`, `EXIT_*`
- **Inputs -> outputs**: -
- **Depends on**: -
- **Called by**: `bootstrap.py`, `checklist.py`, `config.py`, `github_client.py`, `llm_adapter.py`, `main.py`, `parser.py`, `platform.py`, `source_fetch.py`, `stories.py`, `tfs_client.py`; tested by 19 test module(s)

### `review_agent/github_client.py`

- **Purpose**: The GitHub implementation of `PlatformClient` (007).
- **Responsibility**: The only module that speaks the GitHub API (REST + GraphQL); one review per run; 422 fallback; read/post clients.
- **Main functions/classes**: `GitHubClient`, `make_github_platform`, `IssueLinks`, `CLOSING_KEYWORD`
- **Inputs -> outputs**: Config -> PR context, revision, changed files, blobs, threads, issues; writes summary and review
- **Depends on**: `config.py`, `errors.py`, `models.py`, `tfs_client.py`
- **Called by**: `platform.py`; tested by 13 test module(s)

### `review_agent/llm_adapter.py`

- **Purpose**: Calls the model provider.
- **Responsibility**: The only module that knows a provider's wire format; transport retries; usage extraction (007).
- **Main functions/classes**: `call_llm`, `LlmText`, `SendRecord`, `TokenUsage`
- **Inputs -> outputs**: prompt, Config -> `LlmText` (text + usage + sends)
- **Depends on**: `errors.py`
- **Called by**: `main.py`; tested by 3 test module(s)

### `review_agent/llm_log.py`

- **Purpose**: The opt-in prompt/response log (006), with tokens and cost (007).
- **Responsibility**: One redacted file per run; pruning of its own files only; run totals.
- **Main functions/classes**: `open_session`, `LogSession`, `ExchangeRecord`, `RunUsage`, `prune`
- **Inputs -> outputs**: exchange records -> `.llm-logs/*.log`; usage -> totals line
- **Depends on**: `config.py`
- **Called by**: `main.py`; tested by 4 test module(s)

### `review_agent/main.py`

- **Purpose**: Orchestrates one review and sets the exit code.
- **Responsibility**: The pipeline: platform, stories, checklist, diff, selection, prompts, calls, synthesis, delivery.
- **Main functions/classes**: `run_review`, `main`, `build_parser`, `PhaseLog`, `_synthesise`, `_recording_sender`
- **Inputs -> outputs**: Config -> `ReviewReport`, posted or printed feedback, exit 0/1/2
- **Depends on**: `checklist.py`, `config.py`, `dedupe.py`, `diff_builder.py`, `errors.py`, `llm_adapter.py`, `llm_log.py`, `models.py`, `output_layer.py`, `parser.py`, `platform.py`, `prompt_builder.py`, `selection.py`, `stories.py`, `tfs_client.py`
- **Called by**: `bootstrap.py`, `run.py`; tested by 20 test module(s)

### `review_agent/models.py`

- **Purpose**: Frozen dataclasses shared by every module.
- **Responsibility**: Entities and their invariants: PR context, work items, changes, findings, report.
- **Main functions/classes**: `PullRequestContext`, `WorkItem` (`from_payload`, `from_issue`), `ChangeEntry`, `Revision`, `ChangedFile`, `CrossFileIssue`, `ReviewReport`
- **Inputs -> outputs**: -
- **Depends on**: `textutil.py`
- **Called by**: `bootstrap.py`, `checklist.py`, `checklist_docs.py`, `diff_builder.py`, `github_client.py`, `main.py`, `output_layer.py`, `parser.py`, `platform.py`, `prompt_builder.py`, `selection.py`, `stories.py`; tested by 22 test module(s)

### `review_agent/output_layer.py`

- **Purpose**: Renders feedback and prints or posts it.
- **Responsibility**: One renderer for preview and posting; routing inline vs summary; deduplication against prior comments.
- **Main functions/classes**: `build_plan`, `render_summary`, `build_inline_comments`, `print_plan`, `post_plan`
- **Inputs -> outputs**: ReviewReport, reviewable set, prior feedback -> `FeedbackPlan`
- **Depends on**: `config.py`, `models.py`, `parser.py`
- **Called by**: `main.py`, `platform.py`; tested by 10 test module(s)

### `review_agent/parser.py`

- **Purpose**: Validates the model's JSON and derives findings.
- **Responsibility**: Response contract (incl. cross-file issues), merge across chunks, synthesis, finding identity.
- **Main functions/classes**: `parse_with_retry`, `validate_payload`, `merge_results`, `parse_synthesis`, `apply_synthesis`, `build_report`, `fingerprint`, `cross_file_key`
- **Inputs -> outputs**: model text -> findings dict -> `ReviewReport`
- **Depends on**: `errors.py`, `models.py`
- **Called by**: `dedupe.py`, `main.py`, `output_layer.py`; tested by 3 test module(s)

### `review_agent/platform.py`

- **Purpose**: The hosting platform as the pipeline sees it (007).
- **Responsibility**: `PlatformClient` protocol; `TfsPlatform` adapter over the unchanged `TfsClient`; platform selection.
- **Main functions/classes**: `PlatformClient`, `TfsPlatform`, `make_platform`
- **Inputs -> outputs**: Config, TFS client factory -> platform
- **Depends on**: `diff_builder.py`, `errors.py`, `github_client.py`, `models.py`, `output_layer.py`
- **Called by**: `main.py`; tested by 1 test module(s)

### `review_agent/prompt_builder.py`

- **Purpose**: Assembles the prompts.
- **Responsibility**: Review rules and contract, story, scope, checklist, PR outline, diff pieces; the synthesis prompt.
- **Main functions/classes**: `build_review`, `build_prompts`, `build_synthesis_prompt`, `RULES`, `CONTRACT`
- **Inputs -> outputs**: stories, scope, checklist, reviewable set, Config -> prompts + plan + outline
- **Depends on**: `chunk_planner.py`, `models.py`
- **Called by**: `main.py`; tested by 4 test module(s)

### `review_agent/run.py`

- **Purpose**: Entry point used by the bootstrapped child.
- **Responsibility**: Prepares the console and calls `main.main`.
- **Main functions/classes**: `main`
- **Inputs -> outputs**: argv -> exit code
- **Depends on**: `main.py`
- **Called by**: `bootstrap.py`; tested by 1 test module(s)

### `review_agent/selection.py`

- **Purpose**: Decides what is sent for review.
- **Responsibility**: Exclusion patterns, file and line bounds, rule selection by relevance.
- **Main functions/classes**: `select_reviewable`, `select_rules`, `match_exclusion`
- **Inputs -> outputs**: ChangeSet, Config -> `ReviewableSet`; corpus -> applied corpus
- **Depends on**: `models.py`
- **Called by**: `main.py`; tested by 3 test module(s)

### `review_agent/source_fetch.py`

- **Purpose**: Clones repositories without leaking the credential.
- **Responsibility**: The only module that runs git; TFS and GitHub URL/header forms (007); cleanup.
- **Main functions/classes**: `clone`, `cleanup`, `clone_url`, `public_url`, `default_token`
- **Inputs -> outputs**: Config, repository -> `ClonedSource` in a temp directory
- **Depends on**: `config.py`, `errors.py`
- **Called by**: `bootstrap.py`, `checklist.py`; tested by 6 test module(s)

### `review_agent/stories.py`

- **Purpose**: Where a pull request's stories come from (007).
- **Responsibility**: STORY_SOURCE selector: TFS work items, GitHub issues, or none; every set-aside issue stated.
- **Main functions/classes**: `fetch_stories`, `fetch_tfs`, `fetch_github_issues`, `StoryOutcome`
- **Inputs -> outputs**: Config, platform -> work items, reason, notes
- **Depends on**: `errors.py`, `models.py`
- **Called by**: `main.py`; tested by 1 test module(s)

### `review_agent/textutil.py`

- **Purpose**: Text helpers.
- **Responsibility**: HTML to text; acceptance-criteria splitting.
- **Main functions/classes**: `html_to_text`, `split_criteria`
- **Inputs -> outputs**: text -> text / list
- **Depends on**: -
- **Called by**: `models.py`; tested by 1 test module(s)

### `review_agent/tfs_client.py`

- **Purpose**: The TFS implementation (unchanged by 007).
- **Responsibility**: The only module that speaks TFS REST; retries; auth modes; TLS via the OS store.
- **Main functions/classes**: `TfsClient`, `inject_system_trust`
- **Inputs -> outputs**: Config -> TFS payloads; writes threads and comments
- **Depends on**: `errors.py`
- **Called by**: `github_client.py`, `main.py`; tested by 1 test module(s)

### `review_agent/README.md`

- **Purpose**: Operator README: configuration, quick start, runs on TFS and GitHub.

### `review_agent/requirements.txt`

- **Purpose**: Runtime dependencies: requests, python-dotenv, truststore, openpyxl. 007 adds none.

### `review_agent/requirements-dev.txt`

- **Purpose**: Test dependencies: pytest, responses, pyyaml (007, workflow contract test only).

### `review_agent/.env.example`

- **Purpose**: Every setting with a placeholder value. Copy to `.env`; never commit `.env`.

## `tests/` - the contract

`python -m pytest tests` - no network, no credential, no git. Every test module below:
its purpose (its own docstring, first paragraph), what it exercises, and what uses it.

### Contract tests - architecture invariants

| File | Purpose | Exercises (agent modules) | Used by |
|---|---|---|---|
| `tests/contract/__init__.py` | - | - | - |
| `tests/contract/test_checklist_inventory.py` | T019 - every document the walk matched is accounted for (SC-002). | `checklist.py`, `config.py` | - |
| `tests/contract/test_every_send_is_logged.py` | T068 / T069 (feature 007) - every send is in the log, the totals add up, and the new lines are redacted like the old ones (FR-021-FR-024, SC-006). | `config.py`, `github_client.py`, `llm_adapter.py`, `main.py`, `prompt_builder.py` | - |
| `tests/contract/test_excluded_files_never_sent.py` | T086 - SC-010: excluded content never reaches the AI provider. | `config.py`, `main.py`, `models.py`, `output_layer.py`, `selection.py` | - |
| `tests/contract/test_github_boundary.py` | T021 (feature 007) - the GitHub API is spoken in one module. | - | - |
| `tests/contract/test_github_secrets_never_leak.py` | T020 (feature 007) - no GitHub credential reaches anything a person can read. | `config.py`, `github_client.py`, `main.py`, `models.py`, `output_layer.py` | - |
| `tests/contract/test_import_boundaries.py` | T023 / T090 - the two replaceability boundaries, and config containment. | - | - |
| `tests/contract/test_llm_log_is_redacted.py` | T023 (feature 006) - no credential reaches the log file. THE GATE. | `config.py`, `llm_log.py`, `main.py` | - |
| `tests/contract/test_llm_log_prunes_only_its_own.py` | T024 (feature 006) - retention never destroys anything it did not create. | `llm_log.py` | - |
| `tests/contract/test_no_secrets_leak.py` | T021 - no credential reaches any output path (FR-006, SC-004). | `config.py`, `errors.py`, `main.py`, `source_fetch.py` | - |
| `tests/contract/test_output_encoding.py` | Regression: preview mode must survive a non-UTF-8 console. | `config.py`, `models.py`, `output_layer.py` | - |
| `tests/contract/test_preview_makes_no_writes.py` | T030 - preview mode is read-only (FR-007, FR-026). | `config.py`, `main.py` | - |
| `tests/contract/test_preview_makes_no_writes_github.py` | T019 (feature 007) - a GitHub preview cannot write, by construction. | `config.py`, `github_client.py`, `main.py` | - |
| `tests/contract/test_tls_never_disabled.py` | T022 - TLS verification is never disabled (FR-034). | - | - |
| `tests/contract/test_workflow_contract.py` | T062 (feature 007) - the workflow invariants of contracts/workflow.md. | - | - |

### Integration tests - the pipeline against fakes

| File | Purpose | Exercises (agent modules) | Used by |
|---|---|---|---|
| `tests/integration/__init__.py` | - | - | - |
| `tests/integration/test_bound_transparency.py` | T087-T088 - SC-011 and SC-007: truncation is visible, citations are real. | `checklist.py`, `models.py`, `output_layer.py`, `selection.py` | - |
| `tests/integration/test_cross_file_cart.py` | T049 (feature 007) - the acceptance test of US3 (quickstart section 4). | `config.py`, `github_client.py`, `main.py`, `prompt_builder.py` | - |
| `tests/integration/test_github_posting.py` | T023 (feature 007) - posting on GitHub, and a second run that adds nothing. | `config.py`, `github_client.py`, `main.py` | - |
| `tests/integration/test_github_review.py` | T022 (feature 007) - a GitHub pull request, previewed end to end. | `config.py`, `github_client.py`, `main.py` | - |
| `tests/integration/test_github_stories.py` | T037 (feature 007) - a PR linked to an issue gets a verdict per criterion (US2). | `config.py`, `github_client.py`, `main.py` | - |
| `tests/integration/test_llm_log_run.py` | T012, T013, T026, T034, T035 - the log across a whole review. | `config.py`, `errors.py`, `main.py`, `prompt_builder.py` | - |
| `tests/integration/test_synthesis_failure.py` | T050 / T051 (feature 007) - a failed synthesis costs only itself; one call by default. | `config.py`, `github_client.py`, `main.py`, `prompt_builder.py` | - |
| `tests/integration/test_us1_corpus.py` | T020, T021 - reviewing against the team's real checklist documents (US1). | `checklist.py`, `config.py`, `main.py` | - |
| `tests/integration/test_us1_review.py` | T025-T027, T029-T030 - the US1 acceptance scenarios end to end. | `config.py`, `errors.py`, `main.py`, `models.py` | - |
| `tests/integration/test_us2_checklists.py` | T049-T053 - the shared checklists: combining, citation, and degrading. | `checklist.py`, `config.py`, `errors.py`, `main.py` | - |
| `tests/integration/test_us3_demo.py` | T051 - the self-contained demonstration, asserted (US3, SC-006, SC-007). | - | - |
| `tests/integration/test_us3_posting.py` | T060, T062-T063, T065 - posting, thread payloads, and incremental re-review. | `config.py`, `errors.py`, `main.py`, `output_layer.py` | - |
| `tests/integration/test_us4_diagnosis.py` | T064 - four misconfigurations, four different answers (US4, FR-024). | `checklist.py`, `config.py`, `errors.py` | - |

### Unit tests - one module at a time

| File | Purpose | Exercises (agent modules) | Used by |
|---|---|---|---|
| `tests/unit/__init__.py` | - | - | - |
| `tests/unit/test_auth_modes.py` | T078-T079 - auth mode selection and retargeting by configuration alone. | `config.py`, `errors.py`, `main.py`, `tfs_client.py` | - |
| `tests/unit/test_bootstrap.py` | T030 - fetch-and-execute, the recursion guard, and --local (FR-012, R2). | `bootstrap.py`, `errors.py`, `run.py`, `source_fetch.py` | - |
| `tests/unit/test_checklist_docs_docx.py` | T036 - reading rules out of the Word standards documents. | `checklist_docs.py`, `models.py` | - |
| `tests/unit/test_checklist_docs_xlsx.py` | T035 - reading rules out of the spreadsheets the quality leads actually keep. | `checklist_docs.py` | - |
| `tests/unit/test_chunk_planner.py` | T046 (feature 007) - token budget, dependency groups, packing, pieces. | `chunk_planner.py`, `diff_builder.py`, `models.py` | - |
| `tests/unit/test_config.py` | T019 - configuration loading, precedence, and validation. | `config.py`, `errors.py` | - |
| `tests/unit/test_config_platform.py` | T006 (feature 007) - one switch, platform-conditional requirements. | `config.py`, `errors.py` | - |
| `tests/unit/test_cross_file_output.py` | T048 (feature 007) - cross-file issues on the pull request. | `dedupe.py`, `diff_builder.py`, `models.py`, `output_layer.py` | - |
| `tests/unit/test_cross_file_parsing.py` | T047 (feature 007) - the extended response contract and the synthesis merge rules. | `models.py`, `parser.py` | - |
| `tests/unit/test_declarations.py` | T045 (feature 007) - declarations from a diff, and a file's skeleton. | `declarations.py` | - |
| `tests/unit/test_dedupe.py` | T061 - fingerprints and recovering prior feedback from the pull request. | `dedupe.py`, `output_layer.py`, `parser.py` | - |
| `tests/unit/test_diff_builder.py` | T033 - diff construction, the line map, and anchoring. | `diff_builder.py`, `models.py` | - |
| `tests/unit/test_diff_builder_entries.py` | T011 (feature 007) - one change-set builder for both entry shapes. | `diff_builder.py`, `models.py` | - |
| `tests/unit/test_github_client.py` | T017 (feature 007) - the GitHub transport, where URL shapes actually matter. | `config.py`, `errors.py`, `github_client.py`, `models.py` | - |
| `tests/unit/test_github_delivery.py` | T018 (feature 007) - one summary, one review, and what happens on a 422. | `config.py`, `dedupe.py`, `errors.py`, `github_client.py`, `models.py`, `output_layer.py` | - |
| `tests/unit/test_github_issues.py` | T036 (feature 007) - linked issues on GitHub Enterprise Server, and failures as notes. | `config.py`, `github_client.py` | - |
| `tests/unit/test_issue_parsing.py` | T034 (feature 007) - acceptance criteria from a GitHub issue body. | `models.py` | - |
| `tests/unit/test_llm_adapter.py` | T077, T080 - every provider behind one signature (FR-033). | `config.py`, `errors.py`, `llm_adapter.py` | - |
| `tests/unit/test_llm_log.py` | T010, T011, T025, T036, T037 - the log module on its own. | `config.py`, `llm_log.py` | - |
| `tests/unit/test_llm_log_usage.py` | T067 (feature 007) - the new log lines, totals, and failure isolation. | `llm_log.py` | - |
| `tests/unit/test_llm_usage.py` | T066 (feature 007) - the provider's own token counts, and every send. | `errors.py`, `llm_adapter.py` | - |
| `tests/unit/test_models_007.py` | T004 (feature 007) - the platform-neutral and cross-file vocabulary. | `models.py` | - |
| `tests/unit/test_models_corpus.py` | T008 - the corpus entities and the invariants that forbid a silent outcome. | `models.py` | - |
| `tests/unit/test_parser.py` | T031 - the JSON contract, enum enforcement, retry, and claim derivation. | `errors.py`, `models.py`, `parser.py` | - |
| `tests/unit/test_platform.py` | T009 (feature 007) - the TFS adapter is invisible. | `dedupe.py`, `diff_builder.py`, `errors.py`, `models.py`, `output_layer.py`, `platform.py` | - |
| `tests/unit/test_routing_not_addressed.py` | T028 - `not_addressed` is inert (FR-016, SC-006). | `diff_builder.py`, `models.py`, `output_layer.py` | - |
| `tests/unit/test_selection.py` | T032 - exclusion list, review bound, and relevance ordering. | `config.py`, `models.py`, `selection.py` | - |
| `tests/unit/test_source_fetch.py` | T029 - fetching a repository without leaking the credential (FR-012, R3). | `errors.py`, `source_fetch.py` | `test_source_fetch_github.py` |
| `tests/unit/test_source_fetch_github.py` | T024 (feature 007) - cloning from GitHub without leaking the credential. | `config.py`, `source_fetch.py` | - |
| `tests/unit/test_stories.py` | T035 (feature 007) - STORY_SOURCE selects the reader, and nothing is dropped silently. | `errors.py`, `github_client.py`, `main.py`, `stories.py` | - |
| `tests/unit/test_textutil.py` | T020 - HTML to plain text, and criteria enumeration. | `textutil.py` | - |

### Feature 003's self-contained demo

| File | Purpose | Exercises (agent modules) | Used by |
|---|---|---|---|
| `tests/demo/__init__.py` | The self-contained half of the demonstration (feature 003, clarification Q2). | - | `test_us3_demo.py` |
| `tests/demo/run.py` | Drive one full review with no server, no credential and no provider (T050). | `checklist.py`, `config.py`, `main.py`, `source_fetch.py` | `test_us3_demo.py` |

### Fixtures

| File | Purpose | Exercises (agent modules) | Used by |
|---|---|---|---|
| `tests/fixtures/cross_file_cart.py` | T044 (feature 007) - the cross-file defect the acceptance test must find. | `models.py` | `test_every_send_is_logged.py`, `test_cross_file_cart.py`, `test_synthesis_failure.py`, `test_chunk_planner.py`, `test_declarations.py` |
| `tests/fixtures/docs_builder.py` | Generate checklist documents in the shapes the real corpus actually uses. | - | `test_checklist_inventory.py`, `test_us1_corpus.py`, `test_us2_checklists.py`, `test_us4_diagnosis.py`, `test_checklist_docs_docx.py`, `test_checklist_docs_xlsx.py` |
| `tests/fixtures/github_pr.py` | T015 (feature 007) - a GitHub pull request, as the GitHub API reports it. | - | `test_github_secrets_never_leak.py`, `fakes_github.py`, `cross_file_cart.py`, `test_github_review.py`, `test_github_stories.py`, `test_github_client.py`, `test_github_delivery.py`, `test_github_issues.py`, `test_stories.py` |
| `tests/fixtures/pr_demo/__init__.py` | Recorded payloads for the SC-001 demo scenario. | - | `test_excluded_files_never_sent.py`, `test_github_secrets_never_leak.py`, `test_preview_makes_no_writes.py`, `test_preview_makes_no_writes_github.py`, `fakes.py`, `github_pr.py`, `test_github_posting.py`, `test_github_review.py`, `test_llm_log_run.py`, `test_synthesis_failure.py`, `test_us1_corpus.py`, `test_us1_review.py`, `test_us2_checklists.py`, `test_us3_posting.py`, `test_auth_modes.py`, `test_cross_file_parsing.py`, `test_platform.py` |

### Shared test infrastructure

| File | Purpose | Exercises (agent modules) | Used by |
|---|---|---|---|
| `tests/__init__.py` | - | - | - |
| `tests/conftest.py` | Shared test fixtures. | `checklist.py`, `errors.py`, `source_fetch.py` | - |
| `tests/fakes.py` | Fakes standing in for TFS and the AI provider. | - | `test_excluded_files_never_sent.py`, `test_github_secrets_never_leak.py`, `test_llm_log_is_redacted.py`, `test_preview_makes_no_writes.py`, `test_preview_makes_no_writes_github.py`, `test_github_posting.py`, `test_github_review.py`, `test_github_stories.py`, `test_llm_log_run.py`, `test_synthesis_failure.py`, `test_us1_corpus.py`, `test_us1_review.py`, `test_us2_checklists.py`, `test_us3_posting.py`, `test_auth_modes.py`, `test_dedupe.py`, `test_platform.py`, `test_stories.py` |
| `tests/fakes_github.py` | T016 (feature 007) - a protocol-level stand-in for `GitHubClient`. | `github_client.py`, `models.py` | `test_every_send_is_logged.py`, `test_github_secrets_never_leak.py`, `test_preview_makes_no_writes_github.py`, `test_cross_file_cart.py`, `test_github_posting.py`, `test_github_review.py`, `test_github_stories.py`, `test_synthesis_failure.py`, `test_stories.py` |

## `specs/` - one directory per feature

Each holds some of: `spec.md` requirements and user stories; `plan.md` implementation plan - the spine of each feature; `research.md` decisions and evidence; `data-model.md` entities and invariants; `quickstart.md` how to implement / run it; `tasks.md` the executed task list; `contracts/` interface contracts; `checklists/` spec quality checklist.
These are documents, not code: nothing imports them, and the suite does not read them
(except `007.../sample-repo/`, which the workflow contract test parses).

| Feature | What it holds | Artifacts present |
|---|---|---|
| `specs/001-pr-code-review-agent/` | The original agent. Spec, plan (Gap Analysis), research, data model, contracts, operator quickstart. Still the authority on the agent's core behaviour. | `checklists/`, `contracts/`, `data-model.md`, `plan.md`, `quickstart.md`, `research.md`, `spec.md` |
| `specs/002-pr-review-walkthrough/` | End-to-end operator walkthrough for the markdown checklist path. `example-files/` are deliberately faulty sample code - never imported or fixed. | `checklists/`, `contracts/`, `data-model.md`, `example-files/`, `plan.md`, `quickstart.md`, `research.md`, `spec.md`, `tasks.md`, `walkthrough.md` |
| `specs/003-checklist-repo-review-demo/` | `.xlsx`/`.docx` checklists wired in, story criteria judged, finding identity repaired. `demo-files/` are deliberate inputs; `demo.md` is the demo. | `checklists/`, `contracts/`, `data-model.md`, `demo-files/`, `demo.md`, `plan.md`, `quickstart.md`, `research.md`, `spec.md`, `tasks.md` |
| `specs/004-agent-docs-runbook/` | Documentation inventory and correction register; `guide.md` is the operator runbook. | `checklists/`, `contracts/`, `data-model.md`, `guide.md`, `plan.md`, `quickstart.md`, `research.md`, `spec.md`, `tasks.md` |
| `specs/005-agent-flow-developer-guide/` | Local-mode flow diagram and developer guide (deliverables in `docs/`). | `checklists/`, `contracts/`, `data-model.md`, `plan.md`, `quickstart.md`, `research.md`, `spec.md`, `tasks.md` |
| `specs/006-llm-prompt-response-log/` | The opt-in prompt/response log, its format and retention contracts. | `checklists/`, `contracts/`, `data-model.md`, `plan.md`, `quickstart.md`, `research.md`, `spec.md`, `tasks.md` |
| `specs/007-github-and-cross-file/` | GitHub platform, GitHub Issues, cross-file review, tokens and cost, the reusable workflow. `validation.md` records every measured result; `sample-repo/` stages the files delivered to the sample repository. | `checklists/`, `contracts/`, `data-model.md`, `plan.md`, `quickstart.md`, `research.md`, `sample-repo/`, `spec.md`, `tasks.md`, `validation.md` |

## `docs/`

| File | Purpose |
|---|---|
| `docs/developer-guide.md` | Developer onboarding guide (005): what each stage sees and does, limits, failure modes. |
| `docs/local-mode-pr-review-activity.puml` | Local-mode TFS call-flow diagram (005). |
| `docs/review-flow.puml` | Full flow, both platforms, with swimlanes and a worked example (007). |
| `docs/code-structure.md` | This document. |
| `docs/github-setup.md` | GitHub tokens, secrets, onboarding a repository, local runs, troubleshooting (007). |

## Configuration and tooling files

| File | Purpose |
|---|---|
| `pytest.ini` | pytest settings. Already sets `-q`: run `python -m pytest tests`, never with `-q` again (it prints no summary). |
| `.gitignore` | Ignores `.env`, keys, Python caches, `.llm-logs/` (logs hold source code). |
| `.env` | Local credentials. Gitignored. Never commit, never print. |
| `.github/workflows/code-review.yml` | The reusable workflow (007). Inputs, secrets, least-privilege permissions, draft/fork skip, concurrency, log artifact. |
| `CLAUDE.md` | Project guide for coding agents: active feature, invariants, known state. |
| `.specify/` | Spec Kit templates, scripts and extension hooks. |
| `.claude/` | Spec Kit skills for Claude Code. |
| `req/` | The requirement documents features are specified from. |

