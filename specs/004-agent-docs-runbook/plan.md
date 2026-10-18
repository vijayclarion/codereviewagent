# Implementation Plan: Agent Documentation and Manual Run Runbook

**Branch**: `004-agent-docs-runbook` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-agent-docs-runbook/spec.md`

## Summary

One reference that answers four questions — what is in this repository, what happens when
a review runs, what the tool will do to a pull request, and how to run it by hand — with
every claim anchored to the code that proves it.

**This feature writes no agent code.** Like 002 and unlike 003, editing `review_agent/`
means you have left the feature. The two exceptions are surgical and listed in
[Scope of code changes](#scope-of-code-changes): correcting `review_agent/README.md` where
the survey proved it wrong, and correcting `CLAUDE.md` where it is stale. Neither touches
behaviour; both are asserted by the same suite that guards everything else.

**The survey is again the thing that changed the plan.** Documentation for this project
already exists in seven places, and reading them against the code found **fifteen**
disagreements — including three that stop a first-time operator outright:

- the token that posting actually requires is not the one the README documents
  (**C3**),
- the command the README gives never goes through the entry point that the project's own
  design considers the default (**C5**),
- and the test command every document prescribes prints no result at all (**C2**).

So the spine of this plan is not a build order. It is the **Documentation Inventory** and
the **Correction Register**: what already exists and is right (link it), what exists and
is wrong (correct it, name it), and what does not exist (write it). A task that proposes
"document the exit codes" without reading the register will re-document what
`review_agent/README.md` already carries correctly, and will repeat C3 while doing it.

## Technical Context

**Language/Version**: No code is authored. The documented subject is Python 3.13.14; the
suite runs under pytest 9.1.1.
**Primary Dependencies**: None added, none required to read the deliverable. Verifying it
needs only what `review_agent/requirements.txt` and `requirements-dev.txt` already declare.
**Storage**: Markdown in this feature's directory. No generator, no build step, no site.
**Testing**: `python -m pytest tests` — **532 passing**, no live network, 2.76 s
(measured 2026-09-16 at `33535f0`). Note the command: not `-q`. See **C2**.
**Target Platform**: Windows 11, PowerShell, from the repository root. Git Bash is present
and is the second shell the runbook must account for.
**Project Type**: Documentation deliverable for a single Python package with a CLI.
**Performance Goals**: None. The only timed claim in the deliverable is SC-001's
thirty-minute first run, which is measured on a person, not a machine.
**Constraints**: Every claim carries a source anchor (FR-025); nothing unverifiable is
asserted (FR-026); no credential, token, live host, or live project identifier appears
(FR-028). The five architecture invariants are the *subject* here, not a constraint on the
work — except that describing them wrongly is the failure mode this feature exists to end.
**Scale/Scope**: One deliverable file, four parts. 20 shipped modules, 4 entry points,
5 contract invariants, 3 exit codes, 6 finding kinds to route, ~28 configuration settings,
532 tests to group, 7 existing documents to reconcile, 15 corrections to record.

No NEEDS CLARIFICATION remains. Every value above was executed or read out of the
repository on 2026-09-16; what could not be executed is marked as such in
[research.md](./research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still an unfilled template. The formal gate passes
vacuously for the **fourth** feature running.

Feature 001 reconstructed five de-facto principles from the code and its contract tests.
A documentation feature cannot break four of them by construction — it writes no code that
could import anything. It can break the fifth spectacularly, and it can break something
the principles do not name.

| Reconstructed principle | Enforced by | Exposure in this feature | How the plan holds it |
|---|---|---|---|
| **I — One module reads the environment** | `test_import_boundaries.py` | None. No code is authored | Unaffected; the deliverable *describes* the rule and names the test |
| **IV — Format knowledge is isolated** | `test_import_boundaries.py` | None | Unaffected; described |
| **VII — No silent outcome** | `models.py` invariants | The deliverable itself can be silent about a reduction it did not verify | FR-026 makes every unobserved claim say so; the Verification Record is a required section, not a courtesy |
| **Nothing hard-coded** | `test_import_boundaries.py` | A runbook is the one artifact where hard-coding a host or a project name is *tempting* and *useful* | FR-028 plus a redaction gate before the deliverable is considered done, as in 002 and 003 |
| **Secrets never escape** | `test_no_secrets_leak.py` | **High.** The runbook's subject is credentials. A pasted `.env`, a quoted error message, a real PAT in a transcript | Placeholders only. `.env` was surveyed by **key name only** during planning — no value was read, printed, or stored. Every transcript in the deliverable is produced from the offline demo or from redacted output |

**The principle the five do not name, and this feature needs**: *a claim closed by
reasoning alone is not closed.* 001 closed G4 by reasoning about `fingerprint`'s inputs and
was wrong; 002 found the defect by running the thing twice. This feature is made entirely
of claims, so it adopts that rule explicitly: FR-026, the Verification Record, and the
`[unobserved]` marker.

**Post-Phase-1 re-check**: the design holds all five. The place it was nearly lost is
recorded as **D4** in research — the natural way to write a runbook is to paste a working
`.env` and a real transcript, which breaches the fifth principle in the one artifact most
likely to be copied outside the repository.

**Unchanged recommendation from 001, 002 and 003**: run `/speckit.constitution` and ratify
these five in writing. Four features have now passed this gate vacuously.

## Documentation Inventory

The first half of the spine. Every document that currently claims authority over part of
this feature's subject. **Where a document disagrees with the code, the code wins** — and
the disagreement becomes a row in the Correction Register below rather than a silent
overwrite.

| # | Document | Authoritative for | Status | This feature's action |
|---|---|---|---|---|
| **I1** | `review_agent/README.md` | The package's front door: what it finds, CLI, configuration, exit codes, security, troubleshooting | **Mostly right, wrong in six places** (C3, C4, C5, C6, C11, C15) | **Correct in place**, then link. It stays the first thing a reader meets; the deliverable is the depth behind it |
| **I2** | `specs/002-pr-review-walkthrough/walkthrough.md` | The markdown-checklist path, end to end against a real pull request, verified 2026-09-15 | Current | **Link, never restate.** The deliverable's runbook is the general procedure; this is one executed instance of it |
| **I3** | `specs/003-checklist-repo-review-demo/demo.md` | The document-checklist path, including the offline demonstration | Current; **CLAUDE.md wrongly says it does not exist** (C8) | **Link.** Its offline half is the deliverable's no-server path (FR-022) |
| **I4** | `specs/001-pr-code-review-agent/quickstart.md` Part 1 | Operator setup — the original one | **Stale**: its required correction (`.env` lacks `LLM_PROVIDER`, model identifier wrong) was applied; CLAUDE.md records G5 closed | **Supersede for setup**, with a pointer at the top of I4 saying so. Do not delete — Part 2 and its history stay useful |
| **I5** | `specs/003-.../quickstart.md` | How to *implement* 003 | Current except the test count (C1) | Leave. Correct the count only if a task touches it |
| **I6** | `CLAUDE.md` | The agent's own standing context: active feature, the two settings the defaults get wrong, known defects, invariants | **Right about the hard-won things, stale in four** (C1, C8, C9, C13) | **Correct in place.** It is the one document read on every session; a stale line here costs more than anywhere else |
| **I7** | `Req.md` | The original brief, in the operator's words | Historical | Leave untouched. Cite once, as provenance for the variable names that look odd (`TFS_REPO_CODE_SAMPLE`, `TFS_PAT_FOR_PR`) |

**What no document covers at all** — this is what the deliverable must actually write:

| # | Gap | Why it matters |
|---|---|---|
| **G-A** | **The four entry points and what each does.** `python review_agent/main.py`, `python -m review_agent`, `python -m review_agent.run`, `python -m review_agent --local` | They are not interchangeable. One clones the agent repository and re-executes; one reviews with the working copy; the README documents only the third-party-looking one and never says the others exist (**C5**, **C6**) |
| **G-B** | **A stage-by-stage flow with the log line each stage prints.** | `run_review` emits eight phase lines. Nothing maps them to what produced them, so a run that stops early cannot be read |
| **G-C** | **A file-by-file structure map.** The README's module table covers 14 of 20 shipped modules and no test, spec, or root file | FR-004 and FR-010; a maintainer cannot find the owner of a behaviour from a partial table |
| **G-D** | **What a repeat posting run does.** | The 003 repair is asserted by two integration tests and has **never been observed live**. The deliverable must say exactly that, and say what observation would close it |
| **G-E** | **The preconditions of a manual run that are not in any table**: the working directory, the second token, the API version this collection needs, the variables `.env` does not carry | Each of these is an afternoon (**C3**, **C7**, **C12**, **C13**) |

## Correction Register

The second half of the spine. Fifteen disagreements between an existing document and the
code, each verified on 2026-09-16 at `33535f0`. Full method and evidence in
[research.md](./research.md); this table is the index the tasks are generated from.

**Blocking a first manual run** — an operator who follows today's documents hits these:

| # | Document says | The code does | Evidence |
|---|---|---|---|
| **C2** | `python -m pytest tests -q` — "401 passing" (CLAUDE.md ×2, 003 quickstart) | `pytest.ini` already sets `addopts = -q`, so the documented command runs at **`-qq` and prints no summary line at all**. Output ends at `[100%]` | Executed; output captured. The observable command is `python -m pytest tests` |
| **C3** | Authentication — "exactly one" of `SYSTEM_ACCESSTOKEN` or `TFS_PAT` (README) | **Posting additionally requires `TFS_PAT_FOR_PR`.** Without it: `TFS_PAT_FOR_PR is required to post (omit --post for a dry run)` | `config.py:463-466`; `.env` carries it, the README never names it |
| **C5** | Quick start and CLI are `python review_agent/main.py ...` (README) | That path skips the bootstrap entirely. The design's default entry point is `python -m review_agent`, which **clones the agent repository and re-executes the review inside the clone**, and which fails without `TFS_REPO_CODE_REVIEW_CodeReviewAgent` | `bootstrap.py:83-125`; `config.py:437-441`; `__main__.py` docstring |
| **C7** | *(nothing says this)* | `.env` is read from **the current working directory**. Run from anywhere but the repository root and every setting silently disappears into `missing required configuration` | `config.load_dotenv_if_present`, `root = repo_root or os.getcwd()` |
| **C13** | *(nothing says this)* | `.env` carries **no** `TFS_PR_ID`, **no** `TFS_API_VERSION`, and **no** `TFS_REPO`/`TFS_REPO_CODE_SAMPLE` override beyond the sample repository. A manual run must supply `--pr` and set `TFS_API_VERSION=5.0` | `.env` surveyed by key name only (10 keys, no value read) |

**Wrong, not blocking** — they mislead rather than stop:

| # | Document says | The code does | Evidence |
|---|---|---|---|
| **C1** | "401 passing tests" (CLAUDE.md, 003 quickstart) | **532 passed in 2.76s**; 532 collected | Executed 2026-09-16 |
| **C4** | `TFS_REPO` is the required repository variable (README) | `TFS_REPO_CODE_SAMPLE` is canonical; `TFS_REPO` is the alias. The failure message names the canonical one, which appears in no table | `config.py:373-374`, `:386` |
| **C6** | The CLI has four flags (README) | Five. **`--local`** — "review with this working copy instead of the fetched agent source" — is undocumented, and is the flag a developer needs most often | `main.py:387-391` |
| **C8** | "`demo.md` — not yet written" (CLAUDE.md) | It exists, 16.6 KB, and the README already links it | `specs/003-.../demo.md` |
| **C9** | "`checklist_docs.py` imported by nothing" framing; "Active feature: 003" (CLAUDE.md) | 003 is complete: the inventory is emitted, the suite is green at 532 | CLAUDE.md's own Known-state section already says G1 is closed — the header contradicts it |
| **C11** | "Fingerprints exclude the line number" (README, *How it works*) | No longer true for code issues. 003 gave them the identity `severity@line` precisely **because** they have no natural identifier | `parser.py:302-303` (`code_issue_key`) |
| **C15** | Inline placement: "yes, if located" (README's routing table) | Two conditions, not one. A finding is posted inline only if it has a **stable identity** *and* resolves to a changed line. No identity ⇒ summary, always — even when the line is anchorable | `output_layer.py:106-121` |

**Verified correct — record so a later reader does not "fix" them**:

| # | Claim | Status |
|---|---|---|
| **C10** | Exit `3` is defined and never returned | Confirmed: `errors.py:26` defines `EXIT_DEGRADED`; every return in `main.py:424-446` is 0, 1, or 2 |
| **C12** | `TFS_API_VERSION` defaults to `6.0`, which 404s against this collection | Confirmed at `config.py:473`. The README frames `5.0` as a contingency for "an older server"; here it is the requirement |
| **C14** | The offline demonstration runs with no server | Executed: `python -m tests.demo.run` → exit 0, eight phase lines, a dry-run summary naming four checklist documents |

## Project Structure

### Documentation (this feature)

```text
specs/004-agent-docs-runbook/
├── spec.md              # Phase -1
├── plan.md              # This file
├── research.md          # Phase 0 — decisions D1-D8, verification record C1-C15
├── data-model.md        # Phase 1 — the deliverable's own structure, as entities
├── quickstart.md        # Phase 1 — how to execute this plan
├── contracts/
│   ├── documentation-contract.md   # Assertable clauses the deliverable must satisfy
│   └── verification-record.md      # What "verified" is allowed to mean here
├── checklists/
│   └── requirements.md  # Spec quality gate, passed
├── guide.md             # THE DELIVERABLE — not yet written
└── tasks.md             # Phase 2 (/speckit.tasks — not created by /speckit.plan)
```

### Scope of code changes

```text
review_agent/README.md   # CORRECTED: C3, C4, C5, C6, C11, C15
CLAUDE.md                # CORRECTED: C1, C8, C9, C13; active feature -> 004
specs/001-.../quickstart.md   # One superseding pointer at the top (I4)
review_agent/**.py       # UNTOUCHED. Editing any of these means you have left the feature
tests/**                 # UNTOUCHED. 532 before, 532 after (SC-009)
```

**Already applied during planning**: `/speckit.plan` updates the active-feature block in
`CLAUDE.md` as part of its own workflow, and that edit incidentally closed **C8** (the
claim that `demo.md` does not exist) and **C9** (the header contradicting the known-state
section). `CLAUDE.md`'s remaining corrections — **C1** (401 → 532, in two places) and
**C13** (what `.env` does not carry) — are still open and belong to Phase 4. No task
should re-apply C8 or C9.

**Structure Decision**: the deliverable is **one file**, `guide.md`, with four parts in
the order a reader needs them — *Run it* (P1), *What it does* (P4), *Where things live*
(P2), *How a review flows* (P3). One file because it is the form the previous two
documentation features used, because every claim in it carries a file-and-symbol anchor
that a reader will `grep` for, and because four files would need a fifth to index them.
Rationale and the rejected alternatives are **D1** in research.

Note that the deliverable's part order is **not** the spec's story priority order
reversed by accident: P1 must be first because an operator arrives mid-incident, and P4
is second because the next question after "how do I run it" is "what will it do to my pull
request". P2 and P3 are reference material and belong after the narrative.

## Execution Phasing

| Phase | Produces | Gate to leave it |
|---|---|---|
| **0 — Research** | `research.md`: D1-D8 decisions, C1-C15 verification record | Every C-row in the register has evidence that was executed or read, and a citation |
| **1 — Design** | `data-model.md`, `contracts/`, `quickstart.md` | The contract's clauses are each assertable by a person in under a minute |
| **2 — Tasks** | `tasks.md` (`/speckit.tasks`) | Not this command |
| **3 — Write** | `guide.md`, four parts | Every clause of the documentation contract passes |
| **4 — Correct** | README, CLAUDE.md, the I4 pointer | Each correction cites its C-row; the suite is still 532 |
| **5 — Verify** | The Verification Record inside `guide.md` | Every runbook command executed as written, or marked `[unobserved]` with the observation that would close it |

Phase 5 is not a formality here. Three of the fifteen corrections exist because someone
wrote a plausible command and never ran it.

## Complexity Tracking

No constitutional violation requires justification. One decision is worth recording
because it *looks* like scope creep and is not:

| Decision | Why needed | Simpler alternative rejected because |
|---|---|---|
| Correcting `review_agent/README.md` inside a documentation feature | Six of the fifteen corrections live in it, three of them blocking. Writing a correct guide beside an uncorrected front door means the first document a reader meets still sends them at the wrong token and the wrong entry point | "Only add the new guide" was rejected: the README is the file a new reader opens first, and a correction register nobody reads is not a correction |
| Correcting `CLAUDE.md` | It is loaded into every session. C1, C8 and C9 actively mislead the next agent that reads it | "Leave it for the next feature" was rejected — that is how C8 and C9 got there |
