# Implementation Plan: PR Code Review Agent (Local Mode)

**Branch**: `001-pr-code-review-agent` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-pr-code-review-agent/spec.md`

## Summary

The agent reviews a TFS pull request against the team's checklist corpus and the user stories linked to it, then posts inline comments and one summary comment back onto the pull request.

**This feature is already substantially built.** The repository contains a committed `review_agent/` package of roughly 9,000 lines with 409 passing tests, produced by an earlier spec-kit cycle whose specification artifacts are no longer present in `specs/`. The plan is therefore a **gap-closure plan, not a greenfield build**: its job is to reconcile the existing implementation with the five decisions taken in this spec's clarification session, wire up one substantial module that was written but never connected, and add the one capability that is entirely absent.

The single most important finding from the survey: **`review_agent/checklist_docs.py` is dead code.** It is a complete, unit-tested reader for the `.xlsx` and `.docx` checklist corpus — the heart of FR-008 — and no module imports it. `main.py` still calls the older markdown path (`checklist.py`) with a default pattern of `*.md` on a default branch of `main`. On the current configuration the agent would find zero checklist documents and report a degraded review. Closing that is the highest-value work in this plan.

## Technical Context

**Language/Version**: Python 3.13 (3.13.14 and 3.13.7 both present; code uses no version-specific syntax and runs on 3.9+)
**Primary Dependencies**: `requests` (all HTTP), `python-dotenv` (configuration), `truststore` (binds requests to the OS trust store so a private internal CA validates), `openpyxl` (`.xlsx` reading). `.docx` is read with the standard library — `zipfile` plus `xml.etree` — with no third-party dependency.
**Storage**: No database. Configuration in `.env`; review state lives on the pull request itself, recovered by reading the agent's own comment threads. Phase 1 adds a local run-report folder of per-run JSON files.
**Testing**: `pytest` with `responses` for HTTP stubbing; `pytest.ini` sets `testpaths = tests`. 409 tests currently pass with no live network. Tiers: `tests/contract/` (invariants), `tests/integration/` (user-story flows), `tests/unit/`.
**Target Platform**: Windows 11 local developer machine (primary, per the spec's local-mode framing); the code also carries working support for a self-hosted build agent. Console encoding is explicitly handled for cp1252.
**Project Type**: Single-package Python CLI tool.
**Performance Goals**: SC-002 — a typical pull request (≤20 files, ≤500 changed lines) reviewed and posted within 10 minutes. Existing bounds: `REVIEW_MAX_FILES=40`, `REVIEW_MAX_DIFF_LINES=3000`, `LLM_MAX_CHUNK_LINES=1200`.
**Constraints**: TLS verification must never be disabled (enforced by a contract test). No secret may reach stdout, logs, the prompt, posted comments, or run reports (enforced by a contract test). Preview mode must issue no writes (enforced by a contract test). Excluded files must never be transmitted to the provider (enforced by a contract test).
**Scale/Scope**: One pull request per invocation. Real checklist corpus measured at 48,485 characters across 165 rules in five documents — the reason `CHECKLIST_MAX_CHARS` defaults to 60,000 rather than the 40,000 originally planned.

No NEEDS CLARIFICATION remains: every value above is observed in the repository rather than assumed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is an **unfilled template** — every principle is still a `[PRINCIPLE_N_NAME]` placeholder. There are therefore no ratified project principles to gate against, and the formal gate passes vacuously.

That is a reporting result, not a licence. The existing code cites numbered principles throughout its docstrings ("Principle I", "Principle IV", "Principle VII"), so the previous cycle ratified a constitution that has since been lost along with its specs. Those principles are **reconstructible from the code and its contract tests**, and this plan treats them as binding de-facto constraints because the implementation and its test suite already enforce them:

| Reconstructed principle | Evidence in code | Enforced by |
|---|---|---|
| **I — One module reads the environment** | `config.py` docstring: "The only module that reads the environment" | `tests/contract/test_import_boundaries.py` |
| **IV — Format knowledge is isolated** | `checklist_docs.py`: "The only module that knows what a .xlsx or .docx looks like"; `tfs_client.py`: "The only module that speaks TFS REST"; `llm_adapter.py`: "The only module that knows a provider's wire format" | `tests/contract/test_import_boundaries.py` |
| **VII — No silent outcome** | `ChecklistDocument.__post_init__` refuses a skipped document with no reason: "an unexplained skip is exactly the silence Principle VII forbids" | `models.py` invariants; `tests/contract/test_output_encoding.py` |
| **(unnumbered) — Nothing hard-coded** | Every value arrives via `Config` | `tests/contract/test_import_boundaries.py` |
| **(unnumbered) — Secrets never escape** | `register_secret` / `redact` / `emit` single output path | `tests/contract/test_no_secrets_leak.py` |

**Recommended follow-up, outside this plan's scope**: run `/speckit.constitution` to re-ratify these five as a written constitution. Until then the contract tests are the only thing holding them, and a contributor who has not read the docstrings has nothing to consult.

**Post-Phase-1 re-check**: the designed changes preserve all five. The new run-report writer reads no environment directly (takes a `Config`), knows no provider wire format, records a reason for every skipped item, hard-codes nothing, and routes through the existing redaction path. See `research.md` R5 for the one place this was nearly violated.

## Gap Analysis

The spine of this plan. Each row is the delta between the specification as clarified and the code as it stands.

| # | Spec requirement | Current state | Gap | Severity |
|---|---|---|---|---|
| **G1** | FR-008, FR-008a — every `.xlsx`/`.docx` in the checklist repo, default branch, recursive, unconfigurable; every document named in the report | `checklist_docs.py` is complete and unit-tested but **imported by nothing**. `main.py` uses `checklist.py` (markdown) with `CHECKLIST_FILE_PATTERN=*.md`, `CHECKLIST_BRANCH=main` | Wire the document path into the run; make discovery unconfigurable per the clarification; surface per-document status | **Blocker** |
| **G2** | FR-033–FR-037, SC-013 — one machine-readable report per run, written even on abort | **Nothing writes a report file.** Output is console plus pull request only; the only `write()` in the package is in `source_fetch.py` | Build the run-report writer from scratch | **Blocker** |
| **G3** | FR-016, FR-019a, FR-019b — severities Blocker/Major/Minor, configurable inline threshold, nothing dropped silently | Severities are `high`/`medium`/`low` on `code_issue` only; routing is by finding *kind*, not severity; no threshold exists | Introduce the three-level scale and the threshold; map existing kinds onto it without losing the `not_addressed` rule | **Major** |
| **G4** | FR-020b — one comment per rule per file, noting other occurrences | `fingerprint(kind, path, text)` already excludes the line number, which satisfies FR-020 and FR-020a | Only FR-020b's "and it occurs elsewhere in this file" note is missing | **Minor** |
| **G5** | Configuration must actually work | `.env` has no `LLM_PROVIDER`, which `config.py` requires — **the agent cannot start as configured**. `LLM_MODEL=claude-sonnet-4-6` is not a current model identifier; `.env.example` says `claude-sonnet-5` | Add the missing variable, correct the model id, align checklist defaults with G1 | **Blocker** |
| **G6** | FR-030 — state at startup which analysis service will receive content | `main.py` emits `review logic: …` (which *code* ran), not which *provider endpoint* receives the code | Add the provider disclosure line | **Minor** |
| **G7** | FR-025, FR-026, US4 — documented, repeatable sample setup and teardown | `tests/fixtures/pr_demo/` exists as a test fixture; no operator-facing runbook | Write the runbook; execute it once for real | **Major** |
| **G8** | FR-006 — distinct success and failure statuses | Exit codes 0/1/2/3 with a documented rationale | **No gap.** The existing taxonomy is richer than the spec requires and satisfies it | — |
| **G9** | — | Feature 002's bootstrap (`bootstrap.py`, `source_fetch.py`, `run.py`) re-fetches and re-executes the agent's own logic from TFS each run | **Out of scope, deliberately retained.** This spec neither requires nor forbids it; removing working, tested capability to match a spec that is silent would be destructive | — |

**Sequencing consequence**: G5 blocks every form of live verification, so it comes first — nothing else can be observed working until the agent starts. G1 and G2 are the substantive build. G3 touches the widest surface (models, parser, output layer, tests) and so follows the two blockers rather than preceding them.

## Project Structure

### Documentation (this feature)

```text
specs/001-pr-code-review-agent/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output — includes the US4 sample runbook
├── contracts/           # Phase 1 output
│   ├── cli.md           # Command-line surface
│   ├── run-report.md    # Run-report schema (new capability, G2)
│   ├── llm-response.md  # Provider response contract the parser validates
│   └── tfs-surface.md   # The TFS REST endpoints relied on
├── checklists/
│   └── requirements.md  # Spec quality checklist (already complete)
└── tasks.md             # Phase 2 output — NOT created by /speckit.plan
```

### Source Code (repository root)

The layout exists and is sound. Modules the gap analysis touches are marked.

```text
review_agent/
├── __init__.py
├── __main__.py
├── main.py              # CLI, orchestration, exit codes        [G1, G2, G3, G6]
├── config.py            # Sole reader of the environment        [G1, G3, G5]
├── errors.py            # SetupFailure / DegradedReview
├── models.py            # Frozen dataclasses for every entity    [G2, G3]
├── tfs_client.py        # Sole speaker of TFS REST
├── checklist.py         # Markdown checklist path (legacy)       [G1]
├── checklist_docs.py    # .xlsx/.docx reader — CURRENTLY UNUSED  [G1]
├── diff_builder.py      # Blobs → unified diff + line map
├── selection.py         # Exclusions, bounds, relevance ordering
├── prompt_builder.py    # Prompt assembly and chunking           [G1]
├── llm_adapter.py       # Sole knower of provider wire formats   [G6]
├── parser.py            # Response validation, fingerprints      [G3, G4]
├── dedupe.py            # Recover prior feedback from the PR     [G4]
├── output_layer.py      # Render, print, post                    [G3, G4]
├── run_report.py        # NEW — per-run machine-readable report  [G2]
├── bootstrap.py         # Feature 002 self-fetch                 [G9, untouched]
├── source_fetch.py      # Feature 002 git fetch                  [G9, untouched]
├── run.py               # Feature 002 re-execution               [G9, untouched]
├── textutil.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example                                                  [G5]
└── README.md                                                     [G1, G2, G3, G7]

tests/
├── contract/            # Invariants: secrets, TLS, preview, boundaries, routing
├── integration/         # User-story flows
├── unit/
├── fakes.py
└── fixtures/
    ├── docs_builder.py
    └── pr_demo/                                                  [G7]

.env                     # Real credentials — gitignored, never committed
pytest.ini
```

**Structure Decision**: Retain the existing single-package layout unchanged. It already enforces the reconstructed constitution through one-responsibility modules and a contract-test tier that checks the boundaries hold. Exactly one new module is added — `review_agent/run_report.py` for G2 — placed alongside `output_layer.py` because it is a second rendering destination, not a new concern. Every other gap is closed by modifying a module that already owns the relevant responsibility, which is what keeps the import-boundary contract test passing.

## Phase 0: Research

See [research.md](./research.md). Ten items, all resolved from the codebase and its measured behaviour rather than from assumption. The load-bearing ones:

- **R1** — why `checklist_docs.py` ended up orphaned, and which of the two checklist paths survives
- **R2** — mapping `high`/`medium`/`low` and the finding *kinds* onto Blocker/Major/Minor without losing the `not_addressed` rule that keeps the agent quiet
- **R5** — how the run report avoids becoming a second place secrets can escape
- **R9** — the correct current Claude model identifier, and why `.env` is wrong

## Phase 1: Design & Contracts

- **[data-model.md](./data-model.md)** — the entity set, which already exists in `models.py`, plus the additions G2 and G3 require and the validation invariants each carries.
- **[contracts/cli.md](./contracts/cli.md)** — the command-line surface, including the flags G2 and G3 add.
- **[contracts/run-report.md](./contracts/run-report.md)** — the run-report schema. The one genuinely new contract.
- **[contracts/llm-response.md](./contracts/llm-response.md)** — the JSON the provider must return, which `parser.py` validates with one strict retry.
- **[contracts/tfs-surface.md](./contracts/tfs-surface.md)** — every TFS REST endpoint relied on, and why diffs are computed locally.
- **[quickstart.md](./quickstart.md)** — operator setup, plus the US4 sample runbook satisfying FR-025 and FR-026.
- **Agent context** — `CLAUDE.md` updated between its `<!-- SPECKIT START -->` markers to point at this plan.

## Complexity Tracking

No constitution violations to justify — the gate passed vacuously, and the design preserves all five reconstructed principles. Two deliberate scope decisions are recorded here instead, because both are places where a reader might expect different work:

| Decision | Why | Alternative rejected because |
|---|---|---|
| Retain Feature 002's bootstrap machinery (`bootstrap.py`, `source_fetch.py`, `run.py`) | This spec is silent on it; it is committed, tested, and working | Deleting tested capability because the current spec does not mention it destroys work for no stated requirement. Silence is not prohibition. |
| Keep `checklist.py` (markdown path) alongside the document path rather than deleting it | G1 wires the document path in; the markdown path still has passing tests and may hold real configurations | Deleting it in the same change that wires in its replacement makes one regression indistinguishable from the other. Retire it in a later change, once the document path has run against the real corpus. |

## What this plan does not do

Stated plainly so the boundary is not inferred:

- It does not implement anything. `/speckit.tasks` then `/speckit.implement` follow.
- It does not re-ratify the constitution (G-gate). That needs `/speckit.constitution` and a human decision on wording.
- It does not resolve whether your organisation permits source code to reach a third-party provider. FR-032 obliges the documentation to state the exposure; whether that is acceptable is a policy decision outside this repository.
- It does not touch `.env`. That file holds live credentials; G5's corrections are described in `quickstart.md` for a human to apply.
