# Implementation Plan: Local-Mode Call Flow Diagram and Developer Onboarding Guide

**Branch**: `005-agent-flow-developer-guide` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-agent-flow-developer-guide/spec.md`

## Summary

A PlantUML activity diagram of the local-mode review flow, plus a companion document that
walks the same flow method by method, maps every file to the stage it serves, and answers
three questions nothing in the project answers today: **what the reviewer can see**, **what
happens to a very large change**, and **what happens when a model limit is exceeded**.

**This feature writes no agent code.** Like 002 and 004, editing `review_agent/*.py` or
`tests/` means you have left the feature. Unlike 004 it touches no existing document either:
both deliverables are new files in `docs/`, and the only edit outside them is one pointer
line in `CLAUDE.md`. See [Scope of changes](#scope-of-changes).

**Three things decided the shape of this plan.**

1. **Feature 004 already covers half the surface.** Its `guide.md` carries the operator
   runbook, the comment-routing rules, the exit codes, a file inventory, an eleven-row stage
   table and a nine-row fork table. Re-deriving any of that is the expensive mistake
   available here. The [Delegation Map](#delegation-map) says, per section, whether 005
   links, extends, or writes fresh — and the answer is *link* more often than it is *write*.

2. **A diagram and a prose walkthrough of the same flow will drift apart** unless they are
   generated from one description. So the spine of this plan is the
   [Flow Ledger](#flow-ledger): twelve stages, each with its owning file, its methods in call
   order, its input, its output and its log line. **The diagram and the walkthrough are both
   renderings of the Ledger, not independent authorings.** A task that edits one without the
   other has introduced the defect this structure exists to prevent.

3. **The three hard questions have answers the code contradicts a reader's intuition on.**
   The survey found, among others, that `prompt_builder.estimated_size` — the only function
   in the package that estimates token count — **is called from nowhere**, so no request is
   ever measured against a model's limit; that a provider rejection of *one* chunk discards
   the findings of every chunk already parsed in the same run; and that the 4096-token answer
   cap applies to one provider only. These sit in the [Boundary Register](#boundary-register)
   with their anchors, because a document that states the comfortable version of any of them
   is worse than no document.

## Technical Context

**Language/Version**: No code is authored. The documented subject is Python 3.13.14.
**Primary Dependencies**: None added. PlantUML is required to *render* the deliverable, not
to read it; see **D3** in [research.md](./research.md) for what is and is not available here.
**Storage**: Two files in `docs/`. No generator, no build step, no committed image.
**Testing**: `python -m pytest tests` — **532 passed in 7.64 s**, executed 2026-09-17 at
`1aab763`. Note the command: **not** `-q`; `pytest.ini` already sets it and a second `-q`
silences the summary line (004 **C2**).
**Target Platform**: Windows 11, PowerShell, repository root. Git Bash also present.
**Project Type**: Documentation deliverable for a single Python package with a CLI.
**Performance Goals**: None. SC-001's thirty minutes is measured on a person, not a machine.
**Constraints**: Every behavioural claim carries a source anchor (FR-030); a claim that was
not observed says so (FR-031); no credential, token, host or live project identifier appears
(FR-035); no agent source or test is modified (FR-034).
**Scale/Scope**: 2 deliverable files. 12 flow stages, ~60 methods to place, 14 decision
points, 20 shipped modules plus 8 non-module paths to inventory, 3 context sources, 6 size
limits, 7 failure modes, 5 blind-spot classes.

No NEEDS CLARIFICATION remains. Every value above was read out of the repository or executed
on 2026-09-17; anything that could not be executed is marked `[unobserved]` in
[research.md](./research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still an unfilled template. The formal gate passes
vacuously for the **fifth** feature running.

Feature 001 reconstructed five de-facto principles from the code and its contract tests. A
documentation feature cannot break four of them by construction — it authors no code that
could import anything. It can break the fifth, and it can break something the five do not
name.

| Reconstructed principle | Enforced by | Exposure here | How the plan holds it |
|---|---|---|---|
| **I — One module reads the environment** | `test_import_boundaries.py` | None; no code authored | Described, not touched. The Ledger names `config.py` as the sole reader at stage 2 |
| **IV — Format knowledge is isolated** | `test_import_boundaries.py` | None | Described at stage 5 |
| **VII — No silent outcome** | `models.py` invariants | The deliverable can be silent about a reduction it did not verify | FR-031 plus a required Verification Record. `RunInventory.reductions` is the model this document copies |
| **Nothing hard-coded** | `test_import_boundaries.py` | Low. A flow document has little reason to name a host | FR-035, plus the redaction gate before done |
| **Secrets never escape** | `test_no_secrets_leak.py` | **Moderate.** Stage 2 of the Ledger is configuration, and the honest way to document it is to show a real `.env` | Variable **names** only, never values. `.env` was surveyed by key name during planning; no value was read, printed or stored. Every transcript comes from the offline demo |

**The principle the five do not name, and that this feature depends on**: *a claim closed by
reasoning alone is not closed.* 001 closed gap G4 by reasoning about `fingerprint`'s inputs
and was wrong; 002 found the defect by running the thing twice. This feature is made entirely
of claims about a flow, so it adopts the rule explicitly — FR-031, the `[unobserved]` marker,
and the Verification Record.

**Where this feature is most likely to lose it**: the Boundary Register. Every one of its
rows is reachable by reading the code, and **none of the three failure rows can be executed
here** — they need a live provider that rejects an oversized request. They are marked
`[read]`, not `[executed]`, and **D7** in research says what would close them.

**Post-Phase-1 re-check**: design holds all five. The near miss is recorded as **D6** — the
natural way to document the context boundary is to paste a real assembled prompt, which would
carry a project identifier and a checklist excerpt out of the repository.

**Unchanged recommendation from 001 through 004**: run `/speckit.constitution` and ratify
these five in writing. Five features have now passed this gate vacuously.

## Delegation Map

The first half of the spine. 004's `guide.md` is the incumbent; **where it is already correct,
005 links and does not restate** (FR-032). Where it is thin, 005 goes deeper *in the same
direction* rather than contradicting it (FR-033 if it ever must).

| Subject | 004's coverage | 005's action |
|---|---|---|
| How to configure and run the agent | `guide.md` Part 1, nine steps, verified | **Link only.** 005's reader is assumed able to run it (spec Assumption) |
| What becomes a comment; the inline rule; exit codes | Part 2 | **Link only.** Referenced from Ledger stage 11, never re-derived |
| File inventory, one line each | Part 3, alphabetical by module | **Extend, do not copy.** 005 re-cuts the same set by *call-flow position* — which stage each file serves — and marks the files that serve none. The one-line purposes are cited to Part 3 |
| The five architecture invariants | Part 3 | **Link**, and bind each to the stage where it constrains a change |
| Stage-level flow | Part 4, 11 rows, log lines, anchors | **Extend.** 005's Ledger is the same spine at method granularity, and adds the entry-point stage 004's table starts after. Stage names and log lines are **copied verbatim** so the two documents cannot disagree |
| Fork conditions | Part 4, 9 rows (A1–A9) | **Reuse the identifiers.** 005's decision points cite A1–A9 where they coincide and add the five 004 does not cover (per-file skip, exclusion, bound, chunk count, suppression) |
| Size limits | Part 3, a 3-row table of names and defaults | **Write fresh.** Order of application, selection basis, what is reported — none of it exists today |
| What the reviewer can see | **Absent** | **Write fresh.** US4's whole subject |
| Token-limit behaviour | **Absent** (one row names `LLM_MAX_CHUNK_LINES`) | **Write fresh.** US6's whole subject |
| A diagram of any kind | **Absent** | **Write fresh.** US1 |

**Rule for every task**: before writing a paragraph, check this table. If the row says *link*,
the paragraph is a link.

## Flow Ledger

The second half of the spine, and the single source both deliverables render. Twelve stages
for `python -m review_agent --local --pr <id>`. Log lines are quoted from the executed demo
(2026-09-17); stages 0–1 print no phase line and are marked accordingly.

| # | Stage | Owning file | Methods, in call order | In → Out | Log line |
|---|---|---|---|---|---|
| **0** | **logic** | `bootstrap.py` | `main` → `main.build_parser` → `already_bootstrapped` → `config.bootstrap_marker` → `local_source` → `run.main` | argv → which copy reviews | `review logic: LOCAL WORKING COPY (--local)` |
| **1** | **config** | `config.py` | `main.main` → `main.resolve_dry_run` → `load_config` → `load_dotenv_if_present` → `_env` → `register_secret` → `_resolve_checklist_repo` → `_parse_int`/`_parse_bool` → `Config` | environment + `.env` + flags → frozen `Config` | `phase=config mode=dry-run auth=basic` |
| **2** | **pullrequest** | `tfs_client.py`, `models.py` | `TfsClient.__init__` → `get_pull_request` → `PullRequestContext.from_payload` → `DeclaredScope.from_description` | PR id → branches, description, declared scope | `phase=pullrequest source=… target=… scope=parsed` |
| **3** | **workitems** | `main.py`, `textutil.py` | `_fetch_story` → `client.get_linked_work_item_ids` → `client.get_work_item` → `WorkItem.from_payload` → `textutil.html_to_text` → `textutil.split_criteria` | linked ids → stories and enumerated criteria | `phase=workitems count=1 criteria=6` |
| **4** | **checklists** | `checklist.py`, `checklist_docs.py` | `_fetch_checklist` → `obtain_corpus` → `_acquire` → `source_fetch.clone` → `matching_files` → `_read_corpus` → `checklist_docs.read` → `_fold_duplicates` → (fallback) `fetch_checklist` | checklist repository → citable rules | `phase=checklists documents=4 rules=7 skipped=1` |
| **5** | **iteration** | `diff_builder.py` | `client.get_iterations` → `resolve_iteration` → `pr_context.with_iteration` → `log.set_run_id` | iterations → head and base commits | *(folded into the `changes` line; run id appears from here on)* |
| **6** | **changes** | `diff_builder.py` | `client.get_iteration_changes` → `build_change_set` → `_normalise_change_type` → `looks_binary` → `client.get_file_content` ×2 → `build_file_diff` | change entries → diffs + line maps | `phase=changes changed=2 reviewed=1 excluded=1 unreviewed=0 lines=65` |
| **7** | **selection** | `selection.py` | `select_reviewable` → `match_exclusion` → `_keywords` → `score_relevance` → bounds → `select_rules` → `rule_relevance` → `rule_cost` | diffs + rules → what survives | `phase=rules applied=7 omitted=0` (+ the `changes` counts) |
| **8** | **prior** | `dedupe.py` | `read_prior_feedback` → `client.get_threads` → `parse_markers` → `strip_footer` | the PR's own threads → what was already said | `phase=prior posted=0 summary=False` |
| **9** | **llm** | `prompt_builder.py`, `llm_adapter.py`, `parser.py` | `build_prompts` → `chunk_files` → `_story_section` → `_scope_section` → `_checklist_section` → `_diff_section` → `parse_with_retry` → `call_llm` → `_request_for` → `_extract_*` → `parse_response` → `extract_json` → `validate_payload` | prompt(s) → validated result(s) | `phase=llm chunks=1 retries=0` |
| **10** | **parse** | `parser.py` | `merge_results` → `build_report` → `resolve_citations` → `_assign_ordinals` → `match_claim` → `derive_false_coverage_claims` → `main._build_inventory` | results → one `ReviewReport` | `phase=parse coverage=6 violations=4 issues=1 false_claims=1` |
| **11** | **post** | `output_layer.py` | `_deliver` → `build_plan` → `build_inline_comments` → `diff_builder.map_line` → `render_summary` → `render_inventory` → `_already_said` → `print_plan` \| `post_plan` | report → printed or posted | `phase=post outcome=dry-run inline=6 suppressed=0 summary=create` |
| **12** | **done** | `main.py` | `PhaseLog.done` → exit code | outcome → 0 / 1 / 2 | `phase=done outcome=… exit=0` |

**Two Ledger rules.** Stage 5 is split out of 004's `changes` row because the diagram needs a
decision there (*no iterations* → degraded) that the prose table folded away. Stage 7 is split
out for the same reason — it is where three of the six size limits act. Everywhere else the
stage names and log lines are 004's, unchanged, so a reader moving between the documents does
not have to translate.

### Stage detail — methods and roles

The `MethodRole` records. Every `file.method` below resolved in the tree at `1aab763`
(gate **G3** pre-check, task T008). A role that merely re-spells its method's name is a
defect, not a description.

**Stage 0 — logic** (`bootstrap.py`)

| Method | Role |
|---|---|
| `__main__` | Two lines. The only thing `python -m review_agent` does is hand argv to `bootstrap.main` |
| `bootstrap.main` | Decides **which copy of the review logic runs**, and says so out loud before running it |
| `main.build_parser` | Parses argv here as well as in stage 1 — bootstrap needs `--local` and `--pr` before a `Config` exists |
| `bootstrap.already_bootstrapped` | Stops a fetched child re-fetching itself forever |
| `config.bootstrap_marker` | Reads the marker environment variables, so even this stays inside the one module allowed to touch the environment |
| `bootstrap.local_source` | Builds the `AgentSource` that makes the run's provenance reportable |
| `bootstrap.run_fetched` | *(default path only)* Re-executes the review as a child process inside the clone — re-exec rather than a `sys.path` insert, so a review can never be a mixture of two copies |
| `run.main` | The reviewing entry point with no bootstrapping. Exists as a separate target precisely so the child cannot recurse |

**Stage 1 — config** (`config.py`)

| Method | Role |
|---|---|
| `main.main` | Orchestrates: parse, log, load config, review, choose the exit code |
| `main.resolve_dry_run` | Turns `--dry-run` / `--post` into `True` / `False` / `None`, where `None` means "fall through to `DRY_RUN`" |
| `config.load_config` | Builds one frozen `Config`, collecting **every** problem before raising rather than failing on the first |
| `config.load_dotenv_if_present` | Reads `.env` for manual runs. Pipeline variables win over it |
| `config._env` | The single point of environment access the boundary test enforces |
| `config.register_secret` | Registers each token with the redactor, so `emit` cannot print it later |
| `config._resolve_checklist_repo` | Picks the checklist repository and remembers *which setting* supplied it, so an error can name the one to correct |
| `config._parse_int` / `_parse_bool` | Parse with a default and a stated minimum, adding to the problem list rather than raising |

**Stage 2 — pullrequest** (`tfs_client.py`, `models.py`)

| Method | Role |
|---|---|
| `TfsClient.__init__` | The only object that speaks TFS REST. `purpose="read"` selects which of the two tokens it carries |
| `TfsClient.get_pull_request` | One GET. Everything about branches and description comes from this payload |
| `PullRequestContext.from_payload` | Extracts source and target branches, the description, and derives the run id |
| `DeclaredScope.from_description` | Parses the author's own "Covered / Not in this PR" section — the claims the review later verifies against the diff |

**Stage 3 — workitems** (`main.py`, `textutil.py`)

| Method | Role |
|---|---|
| `main._fetch_story` | Recovers the linked work items **and the reason when there are none**, so a token without Work Items access loses the story half loudly instead of failing the whole run |
| `TfsClient.get_linked_work_item_ids` | The PR's work-item relations |
| `TfsClient.get_work_item` | One GET per linked item |
| `WorkItem.from_payload` | Builds the entity and numbers its criteria, so a finding can cite "criterion 4" stably across runs |
| `textutil.html_to_text` | TFS returns descriptions as HTML; the model gets text |
| `textutil.split_criteria` | Splits one acceptance-criteria blob into individually judgeable criteria |

**Stage 4 — checklists** (`checklist.py`, `checklist_docs.py`)

| Method | Role |
|---|---|
| `main._fetch_checklist` | Runs the document path first, falls back to the markdown path, and **never raises** — a missing checklist degrades the review, it does not end it |
| `checklist.obtain_corpus` | Every rule the review measures against. Cleans up the working copy on **every** path, including the one where reading raised |
| `checklist._acquire` | Distinguishes the four acquisition failures — unconfigured, not found, not permitted, unreachable — because each has a different correction |
| `source_fetch.clone` | Clones the checklist repository, presenting the token as an `Authorization` header because this collection never prompts for a password |
| `checklist.matching_files` | Walks the working copy for `.xlsx`/`.docx` matching the configured pattern |
| `checklist._read_corpus` → `checklist_docs.read` | The only module that knows the document formats. One unreadable document is recorded and skipped, not fatal |
| `checklist._fold_duplicates` | Merges rules that say the same thing in two documents, keeping both sources |
| `checklist.fetch_checklist` | The markdown fallback, retained so an operator configured as 002 left them does not silently lose their checklist |

**Stage 5 — iteration** (`diff_builder.py`)

| Method | Role |
|---|---|
| `TfsClient.get_iterations` | The PR's iterations. **No iterations is a degraded review**, not an error |
| `diff_builder.resolve_iteration` | Picks the latest iteration and the commit to diff against, falling back through `commonRefCommit` → `lastMergeTargetCommit` for older servers |
| `PullRequestContext.with_iteration` | Returns a new context carrying head and base commits — the entity is frozen, so this is a replacement, not a mutation |
| `PhaseLog.set_run_id` | From here on every log line carries `run=<pr>.<iteration>` |

**Stage 6 — changes** (`diff_builder.py`)

| Method | Role |
|---|---|
| `TfsClient.get_iteration_changes` | Returns change **entries** — a path and a change type — not patch text |
| `diff_builder.build_change_set` | Turns entries into diffs. **This is where the context boundary is set**: it fetches both complete blobs and emits only a diff |
| `diff_builder._normalise_change_type` | TFS reports composites like `edit, rename`; takes the meaningful part |
| `diff_builder.looks_binary` | By extension first, then by a NUL byte in the content |
| `TfsClient.get_file_content` | Called **twice per file** — the blob at the iteration commit and the blob at the base commit |
| `diff_builder.build_file_diff` | Computes the unified diff with **three context lines**, and builds the diff-line → new-file-line map inline while emitting, because reparsing hunk headers is where anchoring bugs live |

**Stage 7 — selection** (`selection.py`)

| Method | Role |
|---|---|
| `selection.select_reviewable` | Applies exclusions, then ranks, then bounds — in that order, which is the fact a settings table destroys |
| `selection.match_exclusion` | Path matching only. A safety net against a certificate or an environment file leaving the building, not secret scanning |
| `selection._keywords` | The words the story and the checklist are *about*, stopwords removed |
| `selection.score_relevance` | Story words ×3, checklist words ×2, source file +1 — relevance means "related to the two things the review measures against" |
| `selection.select_rules` | The same job one level down: ranks rules against the files that survived, so the corpus the model sees is the part that relates to what actually changed |
| `selection.rule_relevance` / `rule_cost` | Rank and price each rule against the changed paths and extensions, within `CHECKLIST_MAX_CHARS` |

**Stage 8 — prior** (`dedupe.py`)

| Method | Role |
|---|---|
| `dedupe.read_prior_feedback` | Recovers what this agent already said, by reading the pull request's own threads. **Best-effort**: unreadable threads mean a duplicate comment, which beats refusing to review |
| `TfsClient.get_threads` | All threads on the pull request |
| `dedupe.parse_markers` | Finds the `ai-review:` markers — keyed on the comment text, not the author id, because a manual run and a pipeline run post under different identities |
| `dedupe.strip_footer` | The comment without the marker footer, so prose can be compared |

**Stage 9 — llm** (`prompt_builder.py`, `llm_adapter.py`, `parser.py`)

| Method | Role |
|---|---|
| `prompt_builder.build_prompts` | One prompt per chunk. **Story, scope and checklist repeat in every one** |
| `prompt_builder.chunk_files` | Splits on file boundaries so a file is never judged from half of itself; a file over the limit goes alone, oversized |
| `prompt_builder._story_section` | The linked story and its enumerated criteria, or the instruction to return empty coverage |
| `prompt_builder._scope_section` | The description and the author's declared scope — what to verify, and what never to report |
| `prompt_builder._checklist_section` | The selected rules, each as `[IDENTIFIER] rule text` so a finding can be traced to its document |
| `prompt_builder._diff_section` | **The only place changed code enters the request.** Adds the part-of-N warning when the review is split |
| `parser.parse_with_retry` | One stricter retry, then degrade. Never returns partial findings: a shape we cannot trust is content we cannot trust |
| `llm_adapter.call_llm` | Sends one prompt, returns raw text. A provider that cannot be reached is a **degraded review, not a setup failure** |
| `llm_adapter._request_for` | The only place a provider's wire format is known. Four branches, one per provider |
| `llm_adapter._extract_anthropic` / `_extract_openai` / `_extract_ollama` | Pull the text out of each provider's envelope, so everything downstream is provider-blind |
| `parser.parse_response` → `extract_json` → `validate_payload` | Find the JSON, then reject anything not matching the contract shape |

**Stage 10 — parse** (`parser.py`)

| Method | Role |
|---|---|
| `parser.merge_results` | Folds the per-chunk results into one, de-duplicating across chunks |
| `parser.build_report` | Assembles the `ReviewReport` every downstream stage renders |
| `parser.resolve_citations` | Matches each cited rule identifier to an applied rule; a citation matching nothing is **dropped and counted**, never reported as a finding |
| `parser._assign_ordinals` | Numbers each judged criterion against its story, so "criterion 4" means the same thing next run |
| `parser.match_claim` | Matches a declared-scope claim to the criterion it concerns, by distinctiveness rather than by position |
| `parser.derive_false_coverage_claims` | The headline finding: the description claims an item is covered and the diff does not implement it |
| `main._build_inventory` | Builds `RunInventory`, whose `reductions` are **derived** from its fields — so a new way to cover less cannot be added without appearing in the summary |

**Stage 11 — post** (`output_layer.py`)

| Method | Role |
|---|---|
| `main._deliver` | Builds the plan, then prints it or posts it |
| `output_layer.build_plan` | Splits located findings from summary-only ones and drops what was already said |
| `output_layer.build_inline_comments` | Routes each finding. Keys on an **identity** — rule id, criterion number, or severity and line — never on the provider's prose, which is regenerated every run |
| `diff_builder.map_line` | Validates a model-reported line against the file's real changed lines; `None` sends the finding to the summary rather than anchoring it to unrelated code |
| `output_layer.render_summary` | The one summary discussion: what was applied, the findings, and the `### Not sent for review` table |
| `output_layer.render_inventory` | What the run actually applied, before any finding — so a reader seeing no violations knows whether that means "none" or "none looked for" |
| `output_layer._already_said` | Prose-level suppression on top of fingerprint matching |
| `output_layer.print_plan` | Preview. Exactly the text that would be posted |
| `output_layer.post_plan` | Creates **active** threads; never resolves or deletes. Falls back from comment-PATCH to append where an on-prem server refuses the edit |

**Stage 12 — done** (`main.py`)

| Method | Role |
|---|---|
| `PhaseLog.done` | The last line: outcome and exit code, so a build log answers "what happened" on its own |
| `ReviewReport.has_blocking_findings` | Consulted **only** when `FAIL_ON_CONTRADICTION=true` — the sole route to exit 1 |

### Decision points

The fourteen `DecisionPoint` records. `Ref` cites 004's fork identifier where the same fork is
already recorded there; the five with no reference are new in this feature.

| # | Stage | Condition | Branches → destination | Signal | Ref |
|---|---|---|---|---|---|
| **D-A** | 0 | Which copy of the logic reviews? | `--local` → stage 1 · already bootstrapped → stage 1 · otherwise fetch → child → stage 1 · **fetch fails → exit 2** | The `review logic:` line, or its absence | A1 |
| **D-B** | 3 | Is a story linked, and readable? | linked and readable → criteria judged · none linked → checklist-only · **401/403 → checklist-only, degraded** | `phase=workitems count=N outcome=` | A3, A4 |
| **D-C** | 4 | Which checklist path? | documents read → citable rules · unreadable or unresolved → markdown fallback · neither → coverage-only | `documents=`/`rules=` vs `files=` vs `outcome=degraded` | A2 |
| **D-D** | 5 | Any iterations? | yes → stage 6 · **no → degraded, exit 0** | Run stops after `phase=pullrequest` | A5 |
| **D-E** | 6 | Per file: reviewable at all? | deleted / binary / unretrievable → skipped · otherwise → diff | `### Not sent for review` row | *new* |
| **D-F** | 7 | Does the path match an exclusion? | match → excluded, never sent · no match → ranked | same table, reason `excluded` | *new* |
| **D-G** | 7 | Is a bound already reached? | within bounds → reviewed · over `REVIEW_MAX_FILES` or `REVIEW_MAX_DIFF_LINES` → unreviewed | same table, reason `bound` | *new* |
| **D-H** | 7 | Anything reviewable left? | yes → stage 8 · **no → "nothing to review", delivered, exit 0** | `phase=llm outcome=skipped chunks=0` | A6 |
| **D-I** | 9 | One chunk or many? | ≤ `LLM_MAX_CHUNK_LINES` → one pass · over → N passes, each warned it sees only part | `chunks=N` | *new* |
| **D-J** | 9 | Does the response parse? | valid → stage 10 · invalid → **one** stricter retry → valid, or **degraded, exit 0** | `retries=1`, or `outcome=degraded` | A7 |
| **D-K** | 11 | Does the finding anchor to a changed line? | anchors → inline comment · does not → summary only | `inline=N` vs the summary's own list | *new* |
| **D-L** | 11 | Is the coverage entry `not_addressed`? | `not_addressed` → **no comment ever** · `possible_contradiction` → routed | Absent from comments; present in the coverage table | — |
| **D-M** | 11 | Was this already said? | new → posted · already posted → suppressed | `suppressed=N`, `summary=update` | A9 |
| **D-N** | 11 | Preview or post? | `DRY_RUN` → printed · `--post` → active threads created | `outcome=dry-run`, or its absence | A8 |

**D-L is the one row not under `tests/contract/`** — it is asserted by
`tests/unit/test_routing_not_addressed.py`, and it is the rule that stops the tool being noise
on every partial pull request.

### Ledger chain check (T006)

The `input` of stage *n* equals the `output` of stage *n−1* everywhere except three places,
each of which is a real discontinuity a reader should be told about rather than a gap:

- **0 → 1.** Stage 1's input is the environment and `.env`, not stage 0's output. Configuration
  is read fresh, not handed down — which is why a fetched child re-reads it rather than
  inheriting a serialised `Config`.
- **1 → 2.** Stage 2's input is the PR id out of `Config`, plus a network response. Everything
  from here is server state, not derived from what came before.
- **7 → 8.** Stage 8 reads the pull request's own threads. Its input comes from the *pull
  request*, not from stage 7 — the agent is stateless and recovers what it already said from
  where it said it.

Everywhere else the chain is continuous, and the guide states it stage by stage (FR-011).

## Boundary Register

The three questions that have no answer in the project today. Each row is an answer plus the
anchor that proves it; `[executed]` was observed on 2026-09-17, `[read]` was established from
the code only.

### B1 — What the reviewer can see (US4, FR-021…FR-029)

| # | Finding | Anchor | Evidence |
|---|---|---|---|
| **B1.1** | **The change only.** Each changed file is presented as a unified diff with **3 lines of context** around each hunk — not the whole file | `diff_builder.py:14` `CONTEXT_LINES = 3`; `build_file_diff` passes `n=CONTEXT_LINES` | `[executed]` demo diff |
| **B1.2** | **A newly added file is the exception**: it diffs against empty, so effectively all of it is shown | `build_change_set`: `before = ""` when `change_type == "add"` | `[read]` |
| **B1.3** | **A file the PR did not touch is never fetched and never sent.** The loop iterates `changeEntries` only | `build_change_set` | `[read]` |
| **B1.4** | **Full file contents are fetched and then withheld.** Both complete blobs are retrieved to compute the diff locally; only `ChangedFile.diff` reaches the prompt | `client.get_file_content` ×2 → `build_file_diff`; `prompt_builder._diff_section` renders `changed.diff` alone | `[read]` — the distinction FR-025 exists for |
| **B1.5** | **Three other context sources**: the linked story with enumerated criteria, the PR description and its declared scope, and the selected checklist rules | `_story_section`, `_scope_section`, `_checklist_section` | `[executed]` |
| **B1.6** | **A split pass sees only its own files**, and is told so: *"you are seeing only some of the changed files; do not conclude anything about files not shown"* | `_diff_section` when `chunk_total > 1` | `[read]` |
| **B1.7** | **The boundary is stated to the model**: *"You reason only over the diff text you are shown; you cannot run or test the code"* | `prompt_builder.SYSTEM_ROLE` | `[read]` |
| **B1.8** | **A finding that cannot be anchored is not dropped** — it is routed to the summary instead of an inline comment | `diff_builder.map_line` returns `None`; `output_layer._locate` → summary-only | `[executed]` |
| **B1.9** | **Blind spots follow from B1.1–B1.3**: an unchanged caller, a base class, a project-wide convention, whether a test exists elsewhere, whether the changed code is reachable | derived from the above | `[read]` |

### B2 — How a large change is handled (US5, FR-016, FR-017)

Six reductions, in the order they apply. **Every one is reported**, not silently applied.

| Order | Reduction | Default | Setting | Where reported |
|---|---|---|---|---|
| 1 | Deleted, binary, or unretrievable files dropped | — | — | `### Not sent for review` table |
| 2 | Path exclusions | — | `REVIEW_EXCLUDE_PATTERNS`, `REVIEW_EXCLUDE_MODE` | same table |
| 3 | Relevance ranking: story words ×3, checklist words ×2, source file +1; ties broken smallest-first so the bound covers more files | — | — | `selection_basis` in the inventory |
| 4 | File-count bound | **40** | `REVIEW_MAX_FILES` | `### Not sent for review`, reason `bound` |
| 5 | Diff-line bound | **3000** | `REVIEW_MAX_DIFF_LINES` | same |
| 6 | Rule-corpus budget | **60000** chars | `CHECKLIST_MAX_CHARS` | `RunInventory.reductions` |
| 7 | Prompt split | **1200** changed lines | `LLM_MAX_CHUNK_LINES` | `phase=llm chunks=N` |

Anchors: `selection.select_reviewable` and `select_rules`; `config.py:233,245–247`;
`prompt_builder.chunk_files`; `output_layer.render_summary` (`"### Not sent for review"`);
`models.RunInventory.reductions`. **B2.1 `[read]`**: `chunk_files` splits on file boundaries,
so *a single file larger than the limit goes alone rather than being cut mid-hunk* — the one
case that produces an oversized request by design.

### B3 — What happens when a model limit is exceeded (US6, FR-018…FR-020)

| # | Finding | Anchor | Evidence |
|---|---|---|---|
| **B3.1** | **Nothing measures a request against the model's limit.** `prompt_builder.estimated_size` is the only token estimator in the package and **is called from nowhere** | `prompt_builder.py:192`; `grep -rn estimated_size` returns one line, its own definition | `[executed]` grep |
| **B3.2** | **Splitting bounds changed diff lines, not tokens** — and the story, the scope and the whole rule corpus **repeat in every chunk**, so splitting reduces the variable part of a request and not the fixed part | `chunk_files`; `build_prompts` re-emits `story`, `scope`, `rules_block` per chunk | `[read]` |
| **B3.3** | **A provider rejection degrades the entire run, not the chunk.** The `try` wraps the whole chunk loop, so results already parsed are discarded | `main.run_review` — `except DegradedReview` encloses `for prompt in prompts` | `[read]` |
| **B3.4** | Outcome of B3.3: a notice on the pull request, `phase=llm outcome=degraded`, and **exit 0** — an outage must not gate a merge | `main._report_degraded`; `main.main` returns `EXIT_OK` | `[read]` |
| **B3.5** | **The 4096-token answer cap applies to `claude` only.** The openai/azure and ollama bodies set no answer limit | `llm_adapter.DEFAULT_MAX_TOKENS` appears in the claude branch alone | `[read]` — and `.env` here is `LLM_PROVIDER=claude` |
| **B3.6** | **A truncated answer is a shape failure, not a size failure**: invalid JSON → `ContractViolation` → **one** stricter retry → `DegradedReview` | `parser.parse_with_retry` (attempts `(1, 2)`); `prompt_builder.STRICTER_RETRY` | `[read]` |
| **B3.7** | **Rate limiting is retried, credentials are not.** 429/500/502/503/504 → 3 attempts, backoff 1/2/4 s, `Retry-After` honoured and capped at 30 s. 401/403 and 404 → `SetupFailure`, **exit 2** | `llm_adapter.call_llm`, `_retry_after` | `[read]` |
| **B3.8** | **The levers that actually shrink a request** are B2's rows 2, 4, 5, 6 and 7. There is no token budget to set | derived | `[read]` |

**None of B3.3–B3.6 can be executed here** — each needs a live provider that rejects an
oversized request. They are marked `[read]` throughout, and **D7** in research states what
observation would close them.

## Project Structure

### Documentation (this feature)

```text
specs/005-agent-flow-developer-guide/
├── plan.md              # This file
├── spec.md              # The specification
├── research.md          # Phase 0 — decisions D1-D10, evidence E1-E18
├── data-model.md        # Phase 1 — the seven record types both deliverables render
├── quickstart.md        # Phase 1 — implementer's quickstart
├── contracts/
│   ├── diagram-contract.md    # What the .puml must contain and how it is checked
│   └── guide-contract.md      # Required sections, anchoring, and the delegation rule
├── checklists/
│   └── requirements.md  # Spec quality checklist (16/16)
└── tasks.md             # Phase 2 — NOT created by /speckit.plan
```

### Deliverables (repository root)

```text
docs/                                    # currently empty; both deliverables land here
├── local-mode-pr-review-activity.puml   # US1 — the activity diagram source
└── developer-guide.md                   # US2-US6 — the companion document

CLAUDE.md                                # one pointer line added, between the SPECKIT markers
```

**Structure Decision**: `docs/` at the repository root, because the request named it and
because these two files are a standing developer reference rather than the record of one
feature. The feature directory holds the planning artifacts and points at `docs/`; `docs/`
points back at the spec. Nothing under `review_agent/` or `tests/` is touched.

## Scope of changes

| Path | Change | Why permitted |
|---|---|---|
| `docs/local-mode-pr-review-activity.puml` | **New** | FR-001 |
| `docs/developer-guide.md` | **New** | FR-009 |
| `specs/005-agent-flow-developer-guide/**` | **New** | Planning artifacts |
| `CLAUDE.md` | **Active-feature block** inside the existing SPECKIT markers: 005 promoted, 004 demoted to prior, and one stale line corrected (**005-C1**: it called 004's `guide.md` "not yet written"; it is written) | Phase 1 step 3 of the plan workflow. No behavioural claim is altered; the correction is recorded in research **D10**/**E18** rather than applied silently (FR-033) |
| `review_agent/**`, `tests/**` | **None** | FR-034. Verified by `git status` before done |

## Verification strategy

Five gates, all runnable from the repository root. The suite is the backstop even though no
code changes — it is what proves FR-034 held.

| Gate | Command or method | Pass condition |
|---|---|---|
| **G1 — suite unchanged** | `python -m pytest tests` | `532 passed`. Not `-q` |
| **G2 — no agent code touched** | `git status --short` | No entry under `review_agent/` or `tests/` |
| **G3 — every method named exists** | Extract every `file.method` from the guide, assert each resolves | 100% resolve. Automatable as a throwaway script; **not** a committed test (that would be code) |
| **G4 — diagram renders** | `java -jar plantuml.jar -tsvg docs/local-mode-pr-review-activity.puml` | **Closed `[executed]` 2026-09-17.** The jar was obtainable after all, so the gate was discharged by rendering rather than by the planned `[unobserved]` marker — see the superseding note on **D3**. The structural self-check was kept alongside it |
| **G5 — redaction** | Every `.env` key's value tested for presence in the deliverables, without printing any | No *sensitive* value matches. See the note below |

**Gates run at planning time (2026-09-17, commit `1aab763`)**

- **G1** `[executed]` — `532 passed`. The baseline FR-034 will be checked against.
- **G2** `[executed]` — modified: `CLAUDE.md`, `.specify/feature.json`. Untracked: this
  feature's directory. **Nothing under `review_agent/` or `tests/`.**
- **G5** `[executed]` — 10 `.env` values tested against all 9 planning documents plus
  `CLAUDE.md`, no value printed. **Five matched, none sensitive**, and they reproduce exactly
  the pattern 004 recorded: `LLM_PROVIDER`'s value is the public provider identifier, and
  `TFS_REPO_CODE_REVIEW_CodeReviewAgent`'s value is a substring of its own variable name,
  already present in `CLAUDE.md` before this feature. No credential, host or project
  identifier appears. The same script re-runs against `docs/` at implementation.
- **G3, G4** — discharged at implementation: **G3** 93 method references and 14 paths, all
  resolve; **G4** renders clean to SVG at 858 x 4179, full content present.

## Complexity Tracking

> Filled only where the Constitution Check needed a justification.

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| Two deliverable files rather than one | The request names a `.puml` file explicitly, and a diagram cannot live inside a Markdown document as source | Embedding the PlantUML in a fenced block inside the guide would make it un-renderable without extraction, failing FR-002 |
| A Flow Ledger that neither deliverable is | Two renderings of one flow drift apart; 004's Correction Register exists because that already happened once across seven documents | Writing the diagram and the prose independently was rejected on exactly that evidence |
| Three `[read]`-only rows in B3 | The behaviour needs a live provider rejection to observe, which is not available offline | Asserting them as observed would repeat 001's gap-G4 mistake, which is the specific error this project has already paid for once |
