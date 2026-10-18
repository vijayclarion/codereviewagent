# Phase 0 Research: PR Code Review Agent (Local Mode)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-15

Every item below was resolved by reading the committed code and running its test suite, not by assumption. Where a finding contradicts something the code's own documentation claims, that is called out — those are the expensive ones.

---

## R1 — Which checklist path survives, and why one was orphaned

**Decision**: Wire `checklist_docs.py` into the run as the primary checklist source. Retain `checklist.py` (markdown) as a fallback for this change only, and retire it in a later one.

**Rationale**: The repository contains two complete checklist implementations.

- `checklist.py` — enumerates files matching `CHECKLIST_FILE_PATTERN` (default `*.md`) on `CHECKLIST_BRANCH` (default `main`), concatenates them into `combined_markdown`. Wired into `main.py:150`.
- `checklist_docs.py` — reads `.xlsx` and `.docx` into structured, citable `ChecklistItem` objects with stable rule identifiers. Unit-tested by `test_checklist_docs_xlsx.py` and `test_checklist_docs_docx.py`. **Imported by no production module.**

A grep for importers of `checklist_docs` returns only `models.py`, and only because `models.py` *defines* the entities it returns. The orphaning is real, not an artefact of the search: `main.py` mentions `checklist` eleven times and `checklist_docs` zero.

The document reader is unambiguously the better one and matches the clarified FR-008. It was written against the real corpus and encodes what that corpus actually looks like — merged title banners in row 1 with the real header in row 2, multi-sheet workbooks where only one sheet holds rules, `Title` in one document versus `Checklist Item` in another, and a `#` column that exists but is empty in every data row, which is why identifiers are derived rather than required. None of that knowledge exists in the markdown path.

**Why keep the markdown path for now**: retiring it in the same change that promotes its replacement makes a regression in either indistinguishable from the other. It costs nothing to leave in place for one cycle.

**Alternatives considered**: Delete `checklist.py` immediately — rejected on the debuggability grounds above. Merge the two behind one interface — rejected as premature; they return different shapes (`combined_markdown` versus `CombinedChecklist`), and the markdown shape is the one being retired.

---

## R2 — Mapping existing findings onto Blocker / Major / Minor

**Decision**: Treat severity as a property derived at routing time from *finding kind plus existing severity*, rather than renaming the `high`/`medium`/`low` field. Map as follows:

| Finding | Current signal | New severity |
|---|---|---|
| False coverage claim | always blocking | **Blocker** |
| Coverage `possible_contradiction` | always blocking | **Blocker** |
| `code_issue` severity `high` | blocking | **Blocker** |
| `code_issue` severity `medium` | non-blocking | **Major** |
| `code_issue` severity `low` | non-blocking | **Minor** |
| Checklist violation | non-blocking, inline if located | **Major** |
| Coverage `appears_addressed` | never comments | not a finding |
| Coverage `not_addressed` | **never comments** | not a finding |

**Rationale**: `ReviewReport.has_blocking_findings` already draws exactly the Blocker line — false coverage claims, possible contradictions, and high-severity code issues. The spec's Blocker tier and the code's existing blocking set coincide, so the mapping is a renaming of an existing concept rather than a new judgement.

Keeping the provider-facing `high`/`medium`/`low` vocabulary unchanged matters: it is what the model is prompted to emit and what `parser.py` validates. Changing the wire vocabulary would invalidate the prompt, the response contract, and the parser's retry instruction all at once, for no gain the reader ever sees.

**The one thing that must not break**: `not_addressed` never produces a comment. This is protected by a dedicated contract test (`tests/unit/test_routing_not_addressed.py`) and is the single most important noise control in the agent — a pull request routinely implements only part of a story, and flagging that would make the tool unusable on most pull requests. The new severity threshold must sit *downstream* of kind-based routing, never replace it. FR-019b ("the threshold must not cause a finding to be discarded silently") is about findings, and `not_addressed` is a coverage *observation*, not a finding; it continues to reach the summary and never the diff.

**Alternatives considered**: Rename the `severity` field on `CodeIssue` to the new vocabulary — rejected, it breaks the provider contract for a cosmetic gain. Route purely on severity and drop kind-based routing — rejected, it would let `not_addressed` comment.

---

## R3 — Where the inline threshold belongs

**Decision**: A `Config` field `inline_severity_threshold`, defaulting to `major` (meaning Blocker and Major post inline, Minor does not), read by `output_layer.build_inline_comments`.

**Rationale**: `build_inline_comments` is already the sole router — it decides inline versus summary-only via its internal `route()` closure, and its `summary_only` list already exists and is already rendered. The threshold is a filter inside `route()`, which means FR-019b is satisfied structurally: a finding below the threshold falls into `summary_only`, which is already printed and posted. There is no code path where it can be dropped.

**Alternatives considered**: Filter in `main.py` before rendering — rejected, it would create a second place findings can vanish and put the routing decision outside the module that owns rendering, violating the reconstructed Principle IV.

---

## R4 — Duplicate identity is already correct

**Decision**: No change to fingerprinting. Add only FR-020b's "occurs elsewhere in this file" note.

**Rationale**: `parser.fingerprint(kind, path, text)` already excludes the line number, and the code documents precisely the spec's reasoning: "Between iterations an unrelated edit shifts a finding's line; a line-sensitive fingerprint would re-post the same comment on every push." `dedupe.read_prior_feedback` recovers prior fingerprints by scanning the agent's own comment threads for the `ai-review:` marker, keyed on marker text rather than author id — deliberately, because a manual run and a pipeline run post under different identities. That satisfies FR-020a's "not from local state" requirement exactly.

This was the gap I expected to find and did not. The clarification answer (file + cited rule) and the implementation (kind + path + finding text) differ in that the code's `text` component is the finding's subject rather than the rule identifier. For checklist violations the subject *is* the rule, so they coincide; for code issues there is no cited rule, and the subject is the only stable key available. The code's choice is correct.

**Remaining work**: FR-020b — when one rule is breached several times in a file, post once and say so. `build_inline_comments` currently emits one comment per finding, so two findings citing the same rule in the same file produce two comments. Collapsing them requires grouping by `(path, rule)` before routing.

---

## R5 — Keeping the run report out of the secret-leak path

**Decision**: `run_report.py` serialises through `config.redact()` before writing, and takes a `Config` rather than reading the environment.

**Rationale**: This is where the new capability nearly breaks the reconstructed constitution. Today every user-visible byte passes through `config.emit`, which redacts. A new module that writes a file with `json.dump` bypasses that path entirely, and `tests/contract/test_no_secrets_leak.py` would not catch it, because that test watches stdout.

Two mitigations, both required:

1. The writer redacts the serialised string before writing, not the individual fields — field-by-field redaction misses a secret embedded in an exception message inside a `notes` entry, which is exactly how one would realistically escape.
2. `test_no_secrets_leak.py` is extended to assert the same property over a written report file. Without that, FR-036 and SC-011 are promises rather than properties.

**Alternatives considered**: Reuse `emit` by writing through it — rejected, `emit` targets streams and prepares console encoding; a file writer has different concerns. Trust field-level typing to keep secrets out — rejected for the `notes` reason above.

---

## R6 — Report format and location

**Decision**: One JSON file per run at `.review-reports/<pr-id>.<iteration>.<utc-timestamp>.json`, folder configurable via `REVIEW_REPORT_DIR`, added to `.gitignore`.

**Rationale**: JSON satisfies "machine-readable" (FR-033) and makes SC-004, SC-006, SC-011 and SC-012 checkable by script rather than by eye. `PullRequestContext.run_id` already exists and yields `<pr_id>.<iteration_id>`, so the naming needs no new concept; the timestamp distinguishes repeated runs against an unchanged iteration, which is exactly the SC-006 re-run scenario.

The folder must be gitignored. Reports embed source-code excerpts inside findings, and the existing `.gitignore` is already explicit about not committing sensitive material.

**Alternatives considered**: A single rolling file — rejected by the Q5 clarification. Writing beside the spec — rejected, run artefacts are not specification artefacts.

---

## R7 — Writing the report when the run aborts

**Decision**: Write from a `finally` in `main.main()`, using a report accumulator threaded through the run, rather than from the success path.

**Rationale**: FR-035 requires a report even when the run aborts, and `errors.py` defines three abort paths (`SetupFailure`, `DegradedReview`, and an unexpected exception reported as a setup failure). Writing on success only would leave exactly the runs a reader most needs to diagnose without evidence.

**Caveat worth stating**: a `MissingConfiguration` failure occurs *before* a `Config` exists, so the report folder is unknown. For that one case the report falls back to the default folder and records only the configuration problems. A configuration failure already prints every problem at once, so the loss is small; pretending otherwise would be worse than naming it.

---

## R8 — Why diffs are computed locally

**Decision**: No change. Retain local diff computation from two blobs.

**Rationale**: Confirmed from `diff_builder.py` and the README. The TFS `changes` endpoint returns change *entries*, not patch text, and no on-premises endpoint reliably returns unified diff across TFS versions. Computing locally from base and iteration blobs also produces the line map that inline anchoring depends on — without it, FR-018's "anchored to the corresponding line" and SC-003's "100% land on a changed line" are unachievable.

This is recorded because it looks like an obvious simplification target and is not one.

---

## R9 — The configured model identifier is wrong

**Decision**: `.env` must set `LLM_PROVIDER=claude` and correct `LLM_MODEL` to a current identifier — `claude-sonnet-5` for the default balance of capability and cost, or `claude-opus-5` where review quality matters more than throughput.

**Rationale**: Two independent configuration faults, both of which stop the agent before it reaches the provider or at the first call:

1. **`LLM_PROVIDER` is absent from `.env`.** `config.load_config` requires it unconditionally and raises `MissingConfiguration`. The agent cannot start as currently configured. This is the reason nothing in the gap analysis can be verified live until G5 is applied.
2. **`LLM_MODEL=claude-sonnet-4-6` is not a current model identifier.** The repository's own `.env.example` says `claude-sonnet-5`, so `.env` has drifted from the template it was copied from. `llm_adapter._request_for` sends the model string straight through, and the adapter already maps HTTP 404 to "the AI provider has no such model or endpoint" — so the symptom would be a degraded review with a misleading cause.

Current Claude model identifiers: `claude-opus-5`, `claude-sonnet-5`, `claude-fable-5-1`, `claude-haiku-4-5-20251001`.

**Not applied by this plan.** `.env` holds live credentials; the correction belongs to a human and is written up in `quickstart.md`.

---

## R10 — Contract artefacts referenced by code but missing from the repository

**Decision**: Recreate `contracts/llm-response.md` in Phase 1, and note the dangling reference.

**Rationale**: `parser.py` opens with "The contract in contracts/llm-response.schema.json", a path that exists nowhere in the repository. The earlier cycle's `specs/` directory was removed, taking its contracts with it and leaving the code pointing at documentation a reader cannot open.

The contract itself is fully recoverable from `parser.validate_payload`, which enforces it in executable form — the validator is the specification. Phase 1 documents it in prose at `contracts/llm-response.md`; whether to also emit a JSON Schema file at the path the docstring names is a task-level decision, not a planning one.

**Alternatives considered**: Edit the docstring to remove the reference — rejected, the reference is correct in intent and the right fix is to restore what it points at.

---

## Resolved unknowns summary

| Technical Context item | Status |
|---|---|
| Language/Version | Resolved — Python 3.13 present, code portable to 3.9+ |
| Primary Dependencies | Resolved — observed in `requirements.txt`; `.docx` uses stdlib only |
| Storage | Resolved — none today; per-run JSON added by G2 |
| Testing | Resolved — pytest + responses, 409 passing, three tiers |
| Target Platform | Resolved — Windows local, cp1252 console handled explicitly |
| Project Type | Resolved — single-package Python CLI |
| Performance Goals | Resolved — SC-002 plus existing bounds |
| Constraints | Resolved — four invariants, each with a contract test |
| Scale/Scope | Resolved — corpus measured at 48,485 chars / 165 rules |

No NEEDS CLARIFICATION markers remain.
