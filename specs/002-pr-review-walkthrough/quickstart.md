# Quickstart: Executing This Plan

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-15

For the implementer of this feature, not for the operator. The operator's document is `walkthrough.md`, which does not exist yet — producing it is the job described here.

> **Do not confuse the two.** This file explains how to build the walkthrough. The walkthrough explains how to run the agent. Content belongs in exactly one of them.

---

## What you are producing

| Artifact | Path | Contract |
|---|---|---|
| The walkthrough | `specs/002-pr-review-walkthrough/walkthrough.md` | [contracts/walkthrough-structure.md](./contracts/walkthrough-structure.md) |
| The example files | `specs/002-pr-review-walkthrough/example-files/` | [data-model.md](./data-model.md) § Sample change set |
| A pointer replacing 001's Part 2 | `specs/001-pr-code-review-agent/quickstart.md` | FR-003a |
| Two discoverability links | `CLAUDE.md`, `review_agent/README.md` | FR-002 |

Nothing under `review_agent/` changes. If you are editing a module, you have left this feature.

---

## Order of work

### 1. Close research R1 and R6 — one lookup each

Both need the live environment and both block the example files.

- **R1** — list `TFS_REPO_CODE_SAMPLE` on its default branch. The plurality language wins; Python if empty or mixed. Record which branch of the rule applied.
- **R6** — list the sample repository's branches and the project's work items for leftovers from earlier demonstrations. The naming scheme is fixed either way (`sample/pr-review-walkthrough-<YYYYMMDD>`); the lookup decides whether teardown needs a warning about pre-existing artifacts.

Writing the example files before this means writing them twice.

### 2. Write the example files

Design constraint, from research R4 — the sample carries **two** requirement defects, not one:

| Defect | Produces | Placement |
|---|---|---|
| A criterion left unimplemented, claimed as covered in the PR description | `false_coverage_claim` | `either` |
| A criterion implemented in a way that conflicts with what it states | `coverage` / `possible_contradiction` | **always summary-only** |

The second is what satisfies FR-011 as amended. Do not reach for a low-severity nit instead — severity does not affect placement, so it would land inline whenever the provider supplies a line. See [contracts/expected-results.md](./contracts/expected-results.md).

### 3. Draft everything that does not need the run

Sections 1–7 and 11–13 of the structure contract can be written from the repository alone: prerequisites, the sample artifacts, PR creation, the preview command, the symptom reference, teardown, provenance.

Leave section 8 (expected results) empty. It is filled from observation, not from reading the code.

### 4. Pass the gate, then run it live

The gate is in [contracts/verification-run.md](./contracts/verification-run.md). The first item stops most attempts:

```bash
python review_agent/main.py --dry-run --pr <id>
```

If this reports `LLM_PROVIDER is required`, **the `.env` corrections have not been applied.** A human applies them — this feature does not touch `.env`, exactly as feature 001 did not:

| Change | From | To |
|---|---|---|
| Add `LLM_PROVIDER` | absent | `claude` |
| Correct `LLM_MODEL` | `claude-sonnet-4-6` | `claude-sonnet-5` |

`LLM_BASE_URL` is **not** needed for a `claude` setup — it is gated on `azure`/`ollama` (`config.py:107`).

Expect validation in **rounds**, not one report: several checks are skipped while `LLM_PROVIDER` is unset (`config.py:369-376`), so fixing one thing can reveal the next.

Then run the six stages in order, capturing evidence as you go.

### 5. Fill in the expected results

From captured output only. The one rule that matters: **a finding the run did not produce may not be listed as `observed`** (FR-035). Checklist findings will be absent — list them as `expected-absent` with the reason, rather than omitting them, so the reader learns what gap G1 is costing them.

### 6. Redact, then link

Run the redaction scan over the finished document before committing it. This is the likeliest defect in the whole feature and it arrives by copy-paste.

Then add the two links, and replace 001's Part 2 with a pointer.

---

## Three traps, all found during planning

Each is a place where the spec describes feature 001's intended agent rather than the one that exists. Full detail in [plan.md](./plan.md) § Reality Reconciliation.

| Trap | Reality |
|---|---|
| **There is no severity threshold.** Writing "minor findings appear in the summary only" documents behaviour the agent does not have | Routing is by whether a finding anchors to a changed line (`output_layer.py:87-137`). `possible_contradiction` is the only kind guaranteed summary-only |
| **Exit `3` is never returned.** 001's `contracts/cli.md` and quickstart both document it for a degraded run | `EXIT_DEGRADED` is defined (`errors.py:26`) and unused; `main()` returns `0` for a degraded review (`main.py:343-346`). Since a degraded run is the *likely* outcome here, documenting `3` would tell readers a healthy run had failed |
| **Nothing writes a run report.** 001's Part 2 tells the reader to check `.review-reports/` | Gap G2 is open. Remove the checkpoint; do not carry it forward (FR-026a) |

There is also no `--inline-threshold` and no `--report-dir`. 001's CLI contract marks both 🆕 as planned; `build_parser` has neither.

---

## Done when

- [ ] `walkthrough.md` carries all 13 sections in order
- [ ] Example files exist, in the language research R1 fixed, with both defects
- [ ] Every expected-results entry traces to captured output
- [ ] No credential, real host, project, repository name, or identifier anywhere in the document
- [ ] No checkpoint the reader cannot satisfy today
- [ ] 001's Part 2 replaced by a pointer; Part 1 untouched
- [ ] Links from `CLAUDE.md` and `review_agent/README.md`
- [ ] Teardown performed — sample repository clean
- [ ] `python -m pytest tests -q` → 401 passing
