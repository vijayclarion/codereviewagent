# Implementation Plan: GitHub Platform Support and Cross-File Review

**Branch**: `007-github-and-cross-file` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-github-and-cross-file/spec.md`, from `req/REq1.md`

## Summary

The agent gains a second hosting platform (GitHub, including Enterprise Server), a second
story source (GitHub Issues), the ability to see defects that span files, real token counts
and cost in its log, and a reusable GitHub workflow that any repository adopts with one
short caller file.

The technical approach in five lines:

1. **A normalized `PlatformClient` protocol** (`platform.py`). TFS sits behind an adapter that
   composes the untouched `TfsClient`; GitHub is a new module, `github_client.py` (D1-D3).
2. **Stories are selected, not hard-wired** (`stories.py`, `WorkItem.from_issue`) (D7).
3. **A token budget replaces the line budget**, so a normal PR is one call; when it is not,
   **an outline in every chunk, dependency-aware grouping, and one synthesis call** find
   cross-file defects even when the files are apart (D8-D13).
4. **Usage rides on the returned string** (`LlmText`), so `call_llm`'s signature — which 22
   tests depend on — is unchanged, and every transport resend becomes a log entry (D14-D16).
5. **The workflow's authority is its `permissions:` block**: reads and posts use
   `github.token`; the bot token only clones the checklist repository (D17).

**The suite is the contract: 597 passing at `7eddb98`, measured** (research E1).
Every one of those tests passes unmodified at every step; only `tests/conftest.py`'s
isolation list grows (D5).

## Technical Context

**Language/Version**: Python 3 (3.13 here; workflow uses 3.12; no version-specific syntax)
**Primary Dependencies**: none new at runtime — `requests` (already present) speaks REST and
GraphQL. Test-only: PyYAML added to `requirements-dev.txt` for the workflow contract test
**Storage**: none new. The 006 log files gain lines
**Testing**: pytest — `python -m pytest tests` (never `-q`); `responses` for transport tests;
protocol-level fakes for pipeline tests
**Target Platform**: Windows self-hosted TFS agents (unchanged), developer workstations,
GitHub-hosted `ubuntu-latest` runners
**Project Type**: single-package CLI tool, plus two GitHub workflow files
**Performance Goals**: a default-budget review is one provider call (SC-005); a multi-chunk
review costs exactly one extra call. Workflow timeout 15 minutes
**Constraints**: no runtime dependency; `config.py` the only environment reader; one module
per external surface; DRY_RUN defaults true everywhere; no secret in any output; TLS never
disabled; TFS behaviour unchanged
**Scale/Scope**: ~8 changed agent modules, 6 new (`platform`, `github_client`, `stories`,
`declarations`, `chunk_planner`, plus fakes); ~150-200 new tests; 2 workflow files; 3 docs;
changes in three repositories

No NEEDS CLARIFICATION remains. One decision is the requester's (Open Questions, Q1).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still an unfilled template — the formal gate passes
vacuously for the sixth feature running. The reconstructed principles are live here, and
this feature puts more pressure on them than any since 001:

| Principle | Enforced by | Exposure here | How the plan holds it |
|---|---|---|---|
| **I — One module reads the environment** | `test_import_boundaries.py` | **Real.** ~17 new settings; workflow variables | All in `load_config` (contracts/configuration.md). New modules are added to the "reads no environment" assertions |
| **II — One responsibility per module** | convention + boundary test | **Highest.** Platform, stories, planning and synthesis could all land in `main.py` | Five new single-purpose modules; `main.py` gains orchestration only (Call Site Ledger) |
| **III — One module per external surface** | `test_import_boundaries.py` | **Real.** A second REST API and a GraphQL API | `github_client.py` alone; boundary test asserts its markers appear nowhere else and `requests` stays in three modules |
| **IV — git in one module** | `test_import_boundaries.py` | Moderate: GitHub clone URLs and header | `source_fetch.py` only (D6) |
| **VII — No silent outcome** | `models.py` invariants, `PhaseLog` | **Real.** Synthesis failure, a refused GitHub review, an unread issue, an unreported token count | Each has a stated note (D3, D7, D12, D14). Usage "not reported" is never shown as 0 |
| **Secrets never escape** | `test_no_secrets_leak.py`, `test_llm_log_is_redacted.py` | **Highest.** Three new token settings, a new header form, a workflow, an uploaded artifact | Registered at load; dropped from git children; a contract test per token name and for the `x-access-token` header; the artifact holds only the already-redacted log |
| **Preview issues no write** | `test_preview_makes_no_writes.py` | **Real** on a new platform | Dry run never constructs a posting client (contracts/platform-client.md); a GitHub variant of the contract test |

**Gate result**: pass. No violation needs justifying (Complexity Tracking is empty).

**Post-design re-check**: pass. The design adds modules rather than widening any. The one
place it changes behaviour on TFS is chunking (D8), which is the feature itself and is
covered by the existing test that pins `LLM_MAX_CHUNK_LINES`.

## Call Site Ledger

Every existing line this feature changes, and why. Anything not listed is not touched.

| Where | Today | After | Decision |
|---|---|---|---|
| `main.py:218` | `client = TfsClient(config)` | `platform = make_platform(config, tfs_factory=TfsClient)` — name resolved at call time | D1 |
| `main.py:220-221` | `get_pull_request` → `from_payload` | `platform.get_pull_request_context()` | D1 |
| `main.py:230` | `_fetch_story(client, log)` | `stories.fetch_stories(config, platform, log)`; `_fetch_story` kept as delegate | D7 |
| `main.py:234-244` | iterations → `resolve_iteration` → changes | `get_revision()` → `get_changed_files(revision)` | D1 |
| `main.py:299-316` | `build_prompts` + per-chunk loop | `plan_chunks` → `build_prompts(plan, outline)` → loop → synthesis when > 1 chunk | D8-D12 |
| `main.py:150-152, 428` | direct `create_thread` / `update_comment`, `post_plan(plan, client, prior)` | `platform.post_summary(...)`, `platform.deliver(...)` | D3 |
| `main.py:360-410` | one record per `call_llm` | one record per send when `.sends` present; usage, model, kind | D14, D16 |
| `config.py` | TFS-only requirements | platform-conditional; new settings | D5 |
| `llm_adapter.py:25, 167` | `max_tokens 4096`; returns `str` | `config.llm_max_output_tokens`; returns `LlmText` with `.usage`, `.sends` | D8, D14 |
| `llm_log.py` | `_guarded` catches `OSError`; no tokens | catches `Exception`; new lines; `RunUsage` | D15, D16 |
| `prompt_builder.py` | `chunk_files` by lines; no outline | builds from `ChunkPlan`; outline section; cross-file rule; synthesis prompt. `chunk_files` kept | D8-D13 |
| `parser.py` | three finding kinds | `cross_file_issues`, `change_notes`, `parse_synthesis`, `apply_synthesis` | D12, D13 |
| `output_layer.py` | three finding kinds | cross-file routing and summary section; "commit" wording on GitHub | D13 |
| `diff_builder.py` | TFS entry dicts | also `ChangeEntry`; stores `content` | D9 |
| `source_fetch.py:99-141` | TFS URL, `:token` header | platform-aware URL and header | D6 |
| `bootstrap.py`, `checklist.py` | TFS repository names | the platform's repository name (no logic change) | D6 |
| `models.py` | — | `ChangeEntry`, `Revision`, `CrossFileIssue`, `WorkItem.from_issue`, fields | data-model |
| `tests/conftest.py:30` | 7 prefixes | + `GH_`, `GITHUB_`, `GIT_REPO_`, `PLATFORM`, `STORY_SOURCE` | D5 |
| `tests/contract/test_import_boundaries.py` | 2 REST modules | + `github_client.py`; new markers; new modules' assertions | contracts/platform-client.md |

**Not touched**: `tfs_client.py`, `dedupe.py`, `selection.py`, `checklist_docs.py`,
`textutil.py`, `errors.py`, `tests/fakes.py`, every existing test file except the two above.

## Safety Register

| Risk | Consequence | Guard | Test |
|---|---|---|---|
| A GitHub token in output, log, comment, or artifact | credential leak | `register_secret` on all aliases; `SECRET_ENV_NAMES`; single `emit`/`_write` paths | `test_no_secrets_leak.py` + new cases per name and header |
| A dry run writes to GitHub | unrequested public comment | no post client exists in dry run; `write_count == 0` | `test_preview_makes_no_writes_github.py` |
| Fork code runs with secrets | secret exfiltration | `pull_request` only; job `if` excludes forks; no `pull_request_target` | `test_workflow_contract.py` |
| Workflow token over-privileged | blast radius | `permissions:` exactly three; posts use `github.token` | `test_workflow_contract.py` |
| Re-run duplicates comments on GitHub | noise | markers on both platforms; review comments read back | integration re-run test + **live second run** |
| Existing TFS behaviour drifts | the "unchanged" promise breaks | adapter delegates verbatim; `tfs_client.py` untouched; 597 tests | full suite every step |
| Logging crashes a review | lost review | widened guard | `test_llm_log.py` new case raising `ValueError` |
| A truncated response degrades a whole-PR call | lost review | `LLM_MAX_OUTPUT_TOKENS` 8192 | adapter body test |
| Outward steps in three repositories | irreversible public changes | each push, issue, PR confirmed first; no push to `master` | — (process) |

## Secrets the requester must configure (no value is ever set by the agent)

| Secret / variable | Where | Permissions |
|---|---|---|
| `AI_REVIEW_LLM_API_KEY` | `codereviewsample` → Settings → Secrets → Actions (and each onboarded repo) | provider API key |
| `AI_REVIEW_BOT_TOKEN` | same | fine-grained PAT, **Contents: read on `codereviewchecklist` only**. Optional while that repository is public |
| Workflow permissions | nothing to change | the caller file declares its own three permissions; the repository default may stay read-only (an organization policy that forbids write tokens would block posting) |
| `.env` (local only) | this machine | `GIT_REPO_TOKEN` already set; add `PLATFORM`, `GH_REPOSITORY`, `GH_CHECKLIST_REPO` for GitHub runs; **rename the swapped `GIT_REPO_*` URL variables** (E22) |

## Open Questions (the requester's call)

**Q1 — TFS posts with the reading token** (research E3, D4). `TFS_PAT_FOR_PR` is demanded
and then never used. Fixing it is a two-line change in `make_platform`, but it changes which
TFS identity posts comments. **Recommendation: fix it in 007** — the platform factory is
the natural place and it makes feature 002's design true. Default in the task list: a
separately-marked task, not applied until confirmed.

## Project Structure

### Documentation (this feature)

```text
specs/007-github-and-cross-file/
├── spec.md
├── plan.md              # this file
├── research.md          # D1-D20, E1-E24
├── data-model.md
├── quickstart.md        # implementer order of work and traps
├── contracts/
│   ├── platform-client.md
│   ├── configuration.md
│   ├── llm-response.md
│   ├── log-format.md
│   ├── finding-identity.md
│   └── workflow.md
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
review_agent/
├── platform.py          # NEW  PlatformClient protocol, TfsPlatform adapter, make_platform
├── github_client.py     # NEW  the only module that speaks the GitHub API (REST + GraphQL)
├── stories.py           # NEW  STORY_SOURCE selector; TFS and GitHub-issue readers
├── declarations.py      # NEW  declaration extraction, skeletons, outline rendering
├── chunk_planner.py     # NEW  token budget, dependency groups, packing, hunk pieces
├── main.py              # orchestration only (Call Site Ledger)
├── config.py  llm_adapter.py  llm_log.py  prompt_builder.py  parser.py
├── output_layer.py  diff_builder.py  source_fetch.py  models.py
└── tfs_client.py  dedupe.py  ...          # unchanged

.github/workflows/code-review.yml          # NEW  reusable workflow (agent repository)

docs/
├── review-flow.puml     # NEW
├── code-structure.md    # NEW
└── github-setup.md      # NEW

tests/
├── fakes_github.py      # NEW  protocol-level FakeGitHubClient
├── contract/            # + github boundary, GH secrets, GH preview, workflow, cross-file, every-send
├── integration/         # + test_github_review.py, test_github_posting.py, test_cross_file_cart.py
└── unit/                # + test_github_client.py, test_platform.py, test_stories.py,
                         #   test_declarations.py, test_chunk_planner.py, test_synthesis.py, ...

# vijayclarion/codereviewsample (separate repository)
.github/workflows/ai-review.yml            # NEW  caller
.github/ISSUE_TEMPLATE/user-story.md       # NEW
src/eShop.Api/...                          # demo PR branch only

# vijayclarion/codereviewchecklist
.gitignore                                 # NEW  (.env)
```

**Structure Decision**: the existing single package. New responsibilities get new modules
because the boundary test is what keeps them honest; no restructuring of existing modules.

## Delivery phases

| Phase | Stories | Ships independently? |
|---|---|---|
| A | US1 (GitHub PR review, TFS unchanged) | yes — MVP |
| B | US2 (GitHub Issues) | yes, on A |
| C | US5 (tokens, cost, every send) | yes — independent of A |
| D | US3 (cross-file) | yes, on C's logging for verification |
| E | US4 (workflow) | on A |
| F | US6 (docs), US7 (live demo across repositories) | last |

## Complexity Tracking

No constitution violations. Nothing to justify.
