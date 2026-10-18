# Implementation Plan: Checklist-Document Reviews from a Cloned Checklist Repository, with a Full-Cycle Demo

**Branch**: `003-checklist-repo-review-demo` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-checklist-repo-review-demo/spec.md`

## Summary

Make the team's real checklist corpus — spreadsheets and Word documents — actually reach a
review, make every reduction in a review's coverage state itself, and prove the whole cycle
with a demonstration that is executed rather than predicted.

This closes feature 001's gap **G1** ("`checklist_docs.py` is complete and unit-tested but
imported by nothing") and repairs the re-posting defect that 002's verification run
discovered and 001's gap **G4** had recorded as "no gap".

**The survey changed the shape of this plan, as it did for 002.** Reading `review_agent/`
against the spec found that most of this feature is already written and connected to
nothing. Three complete, tested components — the document readers, the credential-safe git
clone, and six entities in `models.py` — sit in the package unused. The work is wiring,
plus four genuine repairs. That is recorded below as the **Survey Findings** table, before
any task list exists, so that `/speckit.tasks` does not generate "build an .xlsx reader".

Unlike feature 002, **this feature writes code.** `CLAUDE.md`'s standing rule that editing
`review_agent/` means you have left the feature belonged to 002 and expires with this plan.

## Technical Context

**Language/Version**: Python 3.13 (the agent's own; `tests/` runs under pytest 9.1.1).
**Primary Dependencies**: None added. `openpyxl>=3.1.0` is already declared in
`review_agent/requirements.txt` and already used by `checklist_docs.py`; `.docx` is read
with `zipfile` + `xml.etree` from the standard library; git is invoked as a subprocess by
`source_fetch.py`, which already exists.
**Storage**: None. The checklist working copy is a temp directory removed when the run
ends; nothing is written to disk between runs (001's gap G2 stays open by the spec's own
scope boundary).
**Testing**: `python -m pytest tests -q` — 401 passing, no live network. New tests join the
existing three tiers (`contract/`, `integration/`, `unit/`). The self-contained
demonstration is additionally driven by one collected integration test.
**Target Platform**: Windows 11 developer machine, PowerShell; the same code runs on the
self-hosted build agent. `config.prepare_console` already handles the cp1252 console.
**Project Type**: Single Python package with a CLI entry point, plus a documentation
deliverable.
**Performance Goals**: No latency target changes. The added cost per run is one shallow
clone of a ~250 KB repository and the parsing of five documents — measured at 48,485
characters of rule text on 2026-09-15.
**Constraints**: Five architecture invariants enforced by `tests/contract/` (see
Constitution Check). The corpus budget is `CHECKLIST_MAX_CHARS`, default 60,000.
**Scale/Scope**: ~165 rules across five documents; one pull request; nine modules touched,
one new test package, one new operator document.

No NEEDS CLARIFICATION remains. Every value above was read out of the repository or fixed
by one of the five clarification answers.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still an unfilled template — every principle is a
`[PRINCIPLE_N_NAME]` placeholder. The formal gate passes vacuously, for the third feature
running.

Feature 001 reconstructed five de-facto principles from the code and its contract tests.
**This feature can violate all five**, which is new: 002 wrote no code and could only
breach two of them, in documentation form.

| Reconstructed principle | Enforced by | Where this feature could break it | How the design holds it |
|---|---|---|---|
| **I — One module reads the environment** | `test_import_boundaries.py` | New settings resolution | All four names resolve inside `config.load_config`; the corpus module receives a frozen `Config` |
| **IV — Format knowledge is isolated** | `test_import_boundaries.py` | A corpus module tempted to open a workbook itself | It hands bytes to `checklist_docs.read` and imports no document library. Likewise it never invokes git — it asks `source_fetch` |
| **VII — No silent outcome** | `models.py` invariants | Every degradation this feature introduces | `RunInventory.reductions` is **derived**, not assembled by hand, so a new reduction condition cannot be added without appearing in the summary. `ChecklistSource` refuses `available=False` with no reason |
| **Nothing hard-coded** | `test_import_boundaries.py` | Pattern defaults, branch defaults | Both arrive through `Config`; the branch default is "whatever the remote says", not a literal |
| **Secrets never escape** | `test_no_secrets_leak.py` | A clone URL, a git error message, the demonstration's transcript | The clone path already solves this (`GIT_ASKPASS`, scrubbed origin, `drop_secrets=True`); the document risk is held by a task-level redaction gate, as in 002 |

**Post-Phase-1 re-check**: the design holds all five. The one place it was nearly lost:
the natural way to obtain a working copy is to call `subprocess.run(["git", ...])` from a
new module, which breaks Principle IV and fails
`test_git_is_invoked_from_one_module_only` — the test greps for the literal string. Going
through `source_fetch.clone` was not merely tidier; it was the only route that keeps the
credential discipline that module already proved.

**Unchanged recommendation from 001 and 002**: run `/speckit.constitution` and ratify these
five in writing. Three features have now passed this gate vacuously.

## Survey Findings

The spine of this plan. Each row was read out of the code on this branch; where a 001 or
002 artifact disagrees, the code wins.

### Already built, connected to nothing

| # | What exists | Evidence | This feature's work |
|---|---|---|---|
| **S1** | A complete `.xlsx`/`.docx` reader producing citable rules, with severity, sections, commentary stripping, ignored-sheet tracking, and a terminal status per document | `checklist_docs.py` (429 lines), `tests/unit/test_checklist_docs_{xlsx,docx}.py`; imported by **nothing** | Import it. One change inside it: content-derived identifiers (R4) |
| **S2** | A credential-safe shallow clone with `GIT_ASKPASS`, no token in argv or on disk, scrubbed origin, and cleanup — whose docstring says it exists for "the checklist repository, whose documents it reviews against" | `source_fetch.py:1-30`, `tests/unit/test_source_fetch.py`; imported only by `bootstrap.py` | Call it. One change: an unset ref takes the remote's default branch |
| **S3** | Six entities for exactly this feature: `ChecklistDocument`, `ChecklistItem`, `CombinedChecklist`, and the `documents` / `dropped_for_budget` / `dropped_citations` fields on `ReviewReport` | `models.py:256-353`, `:452-458` | Populate them. `CombinedChecklist.by_id` and `dropped_citations` are currently called by nothing |
| **S4** | Relevance scoring against story and checklist keywords, with a deterministic tie-break | `selection.py:78-90`, `:114-121` | Extend the same machinery from files to rules (R5) |
| **S5** | A full fake TFS client and PR fixture package, used by the contract and integration tiers | `tests/fakes.py`, `tests/fixtures/pr_demo/`, `tests/fixtures/docs_builder.py` | The self-contained demonstration is built on these rather than on new scaffolding |

**Consequence**: the checklist half of this feature is roughly 250 lines of wiring across
modules that already own the responsibilities, not a new subsystem. Any task that proposes
a new document reader, a new git wrapper, or a new entity for a rule is a task that has not
read this table.

### Genuine repairs

| # | Defect | Evidence | Resolution |
|---|---|---|---|
| **S6** | **One character.** `config.py:380` reads `TFS_REPO_CODE_REVIEW_CodeReviewChecklistT`; `.env` supplies `TFS_REPO_CODE_REVIEW_CodeReviewChecklist`. Nothing matches, no repository resolves, every run reviews against nothing and reports success | `config.py:378-384` vs `.env` | The operator's spelling becomes canonical; the other three names stay accepted (R1) |
| **S7** | **Re-posting duplicates every inline comment.** `fingerprint`'s third argument is regenerated provider prose at all four call sites | `output_layer.py:113,123,130,135`; `parser.py:194-205` | Stable identity per finding kind (R7). 001's G4 recorded "no gap" by reasoning about `fingerprint` without noticing what is passed to it |
| **S8** | **A refused work-item read kills the whole review.** `_fetch_story` has no exception handling, so 401/403 raises `SetupFailure` out of `run_review` and `main` exits 2 — losing the checklist half too | `main.py:97-108`, `:339-342`; `tfs_client.py:167-179` | `WorkItemAccessDenied`, caught in `_fetch_story`, review continues checklist-only with the missing access named (R8) |
| **S9** | **A review with no checklist still asks for, and posts, checklist violations.** The model obliges from general knowledge; the findings cite `checklist` and are indistinguishable from real ones | `prompt_builder.py:99-106`; `output_layer.py:127-129` | Citation resolution against the applied corpus; unresolvable citations are reported, not posted (contracts/llm-response.md R3/R4) |

### Where a prior artifact is wrong about today's agent

| # | Prior artifact says | The code does | Resolution |
|---|---|---|---|
| **S10** | 001's G1 and its clarification: checklist discovery should be **unconfigurable** | `CHECKLIST_FILE_PATTERN` and `CHECKLIST_PATH` are configurable and used | This spec's FR-007 explicitly requires it to stay adjustable. **This spec supersedes 001's clarification.** Recorded so the difference is visible rather than accidental |
| **S11** | `CLAUDE.md`: a Code-only credential means "the review silently loses every requirement finding" | It exits 2 and loses the entire review, noisily | Neither is acceptable; FR-023 defines the third behaviour. `CLAUDE.md` is corrected as a task |
| **S12** | 001's G4: "No gap. `fingerprint` already excludes the line number" | True of `fingerprint`, irrelevant to the defect — the *input* is unstable | See S7. The lesson is procedural and is written into the contract: this repair is not believed until a second live posting run has been observed |

## Project Structure

### Documentation (this feature)

```text
specs/003-checklist-repo-review-demo/
├── plan.md                      # This file
├── spec.md                      # Clarified specification (5 answers integrated)
├── research.md                  # Phase 0 — 12 items
├── data-model.md                # Phase 1 — 2 new entities, 3 modified
├── quickstart.md                # Phase 1 — how an implementer executes this plan
├── contracts/                   # Phase 1
│   ├── checklist-corpus.md         # Acquisition, discovery, inventory, the four misconfigurations
│   ├── finding-identity.md         # Identity per finding kind; suppression behaviour
│   ├── llm-response.md             # Response delta (rule_id) and citation resolution
│   └── demonstration.md            # Required sections, expected-results format, execution protocol
├── checklists/
│   └── requirements.md          # Spec quality checklist (complete)
├── demo.md                      # THE DELIVERABLE — written in the implement phase
├── demo-files/                  # THE DELIVERABLE — faulty sample code + document generator
└── tasks.md                     # Phase 2 — NOT created by /speckit.plan
```

### Source code

```text
review_agent/
├── checklist.py         # + document-corpus path; markdown path retained    [S1,S2,R9]
├── checklist_docs.py    # content-derived identifiers, nothing else         [R4]
├── source_fetch.py      # unset ref takes the remote default branch         [S2,R2]
├── selection.py         # + select_rules(): relevance ranking for rules     [S4,R5]
├── parser.py            # citation resolution; identity keys                [S7,S9,R6,R7]
├── output_layer.py      # 4 identity call sites; the inventory block        [S7,R7,R11]
├── models.py            # ChecklistSource, RunInventory, + 4 members        [S3]
├── errors.py            # WorkItemAccessDenied                              [S8,R8]
├── tfs_client.py        # raises it for work-item endpoints                 [S8]
├── config.py            # setting resolution order; pattern default         [S6,R1,R3]
├── main.py              # orchestration; story degradation; cleanup         [S8,R2]
└── prompt_builder.py    # rules rendered with identifiers                   [R6]

tests/
├── contract/            # + corpus boundaries; + inventory completeness
├── integration/         # + test_us3_demo.py — runs the harness twice (SC-006)
├── unit/                # + identity, resolution, ranking, derivation
└── demo/                # NEW package — the self-contained demonstration harness
```

### Files outside this feature that change

```text
CLAUDE.md                # Active feature; the G1/G4 notes; the S11 correction
review_agent/README.md   # The document path; a link to demo.md
review_agent/.env.example # The canonical checklist setting name; the new pattern default
```

`.env` itself is **not** touched — it holds live credentials and is gitignored. Its
corrections (gap G5) remain a human-applied prerequisite, as in 001 and 002.

**Structure Decision**: Retain the single-package layout and add **no new module to
`review_agent/`**. Every change lands in the module that already owns the responsibility —
which is what keeps the import-boundary contract tests passing and is the whole reason the
package is shaped this way. Acquisition and corpus assembly go into `checklist.py` because
that module's stated job is already "fetch and combine the shared checklists"; rule ranking
goes into `selection.py` because its stated job is already "decide what actually gets sent
to the AI provider". The one new package is `tests/demo/`, which is test scaffolding, not
agent code.

The deliberately faulty sample code lives under `specs/`, following 002: `pytest.ini` sets
`testpaths = tests` and `test_import_boundaries.py:13` scans only `review_agent/`, so
nothing there is collected or boundary-checked.

## Phase 0: Research

See [research.md](./research.md). Twelve items. Eleven are answered from the repository;
**R10** has a half that requires the live collection and is scheduled as the first
implementation action rather than resolved here — the checklist repository's default branch
and folder layout, and whether the sample repository still holds 002's artifacts.

- **R1** which configuration name identifies the checklist repository
- **R2** how the documents are obtained — and why the REST text path cannot carry them
- **R3** which files in the working copy are considered
- **R4** how a document becomes rules, and the one fix `checklist_docs.py` needs
- **R5** what happens when the corpus exceeds one pass
- **R6** how a violation cites a rule, and why the filename is resolved not reported
- **R7** finding identity — including where the line does and does not participate
- **R8** when the credential cannot read work items
- **R9** two corpus shapes, one prompt builder
- **R10** executing the demonstration; the two operational facts the live run depends on
- **R11** making every reduction in coverage visible
- **R12** the demonstration's sample checklist documents

## Phase 1: Design & Contracts

- **[data-model.md](./data-model.md)** — nine spec entities against `models.py`: seven
  exist, two are new, and the invariants that make a silent outcome impossible to
  construct.
- **[contracts/checklist-corpus.md](./contracts/checklist-corpus.md)** — the acquisition
  and inventory contract, including the four misconfigurations US4 requires to be
  distinguishable and the boundary clauses that keep Principle IV.
- **[contracts/finding-identity.md](./contracts/finding-identity.md)** — identity per
  finding kind, the six behaviours it must produce, the one-time migration cost, and the
  rule that this contract is satisfied only by an observed second live posting run.
- **[contracts/llm-response.md](./contracts/llm-response.md)** — the additive `rule_id`
  field and the four-case resolution table.
- **[contracts/demonstration.md](./contracts/demonstration.md)** — seventeen required
  sections, the expected-results format with its mandatory availability column, the
  five-question checkpoint, and the two-execution evidence protocol.
- **[quickstart.md](./quickstart.md)** — how an implementer executes this plan, the three
  hard orderings, and the two boundary traps that fail non-obviously.
- **Agent context** — `CLAUDE.md` updated between its `<!-- SPECKIT START -->` markers.

## Sequencing

Four orderings that are not negotiable, each discovered rather than assumed:

1. **`.env` blocks every live run** (001's gap G5, still open). `config.py:359-367`
   requires `LLM_PROVIDER` and `LLM_MODEL`, and `.env` supplies a model identifier that
   does not exist. All self-contained work proceeds without it; nothing live does.
2. **Identifier derivation (R4) precedes finding identity (R7).** Identity keys on the rule
   identifier. Land them in the wrong order and the suppression tests pass while the
   behaviour is still wrong the first time someone edits a spreadsheet.
3. **The corpus must exist before the prompt renders it and before rules can be ranked.**
   R3 → R4 → R5/R6 is a chain; R7, R8 and R11 are independent of it and can proceed in
   parallel.
4. **The live run is last and gated**, on `.env`, on `TFS_API_VERSION=5.0`, on a credential
   carrying Work Items (read), and on either pushing this branch to the agent repository or
   running `--local` — because the default entry point re-fetches and re-executes the
   committed logic (R10). Without one of those two the live run reviews with code that does
   not contain this feature, and the checklist section of its output will be empty for a
   reason the operator will spend an afternoon looking for in the wrong place.

## Complexity Tracking

No constitution violations to justify. Four scope decisions are recorded instead, because
each is a place a reader might reasonably expect different work:

| Decision | Why | Alternative rejected because |
|---|---|---|
| Repair the re-posting defect here (clarification Q1) rather than document it | SC-007 is written as a hard outcome, and a demonstration that knowingly posts nine comments where five are expected also breaks SC-006 | Documenting it makes the feature's headline deliverable — the demonstration — a record of a known failure, which is a strange thing to hand an operator |
| Include the line in a code issue's identity, but not in any other kind's | A code issue has no natural identifier; keying it on prose is the defect being fixed. Everything with an identifier stays line-independent, preserving 001's FR-030 | Including the line everywhere regresses three finding kinds for no gain. Excluding it everywhere leaves code issues keyed on regenerated prose, which is where this started |
| Keep `CHECKLIST_FILE_PATTERN` configurable, against 001's clarification (S10) | FR-007 requires it, and an operator whose corpus grows a `.md` index or loses `.docx` should not need a release | Hard-coding the extension set is simpler and would satisfy most runs — but it converts an operator's five-second edit into a code change, and 001's reason for the clarification is not recorded anywhere we can consult |
| Add no new module to `review_agent/` | Every change has an existing owner, and the boundary tests are the mechanism that keeps ownership honest | A `checklist_source.py` would read better in isolation and would immediately raise "why is acquisition separate from assembly" — the answer being "it is not", which is why they stay together |

## What this plan does not do

- It does not write `demo.md` or the sample files. `/speckit.tasks` then
  `/speckit.implement` follow.
- It does not write a run report to disk. 001's gap **G2** stays open, by the spec's own
  scope boundary.
- It does not introduce a severity threshold for inline-versus-summary placement. 001's
  gap **G3** stays open; routing remains "anchors to a changed line or does not".
- It does not change which exit statuses the agent returns. `EXIT_DEGRADED` remains
  defined and unused.
- It does not touch `.env`, and it does not convert the markdown checklist path into the
  document path — 002's walkthrough stays valid, and research R9 records the unification
  as the obvious next simplification rather than this feature's work.
- It does not decide whether your organisation permits checklist rule text and source code
  to reach a third-party provider. The demonstration states the exposure before the
  operator creates anything; whether it is acceptable is a policy decision outside this
  repository.
