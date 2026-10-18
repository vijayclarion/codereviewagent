# Phase 1 Data Model: PR Code Review Agent (Local Mode)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-15

Every entity is a frozen dataclass in `review_agent/models.py`. Frozen is load-bearing: the pipeline passes entities between modules that must not mutate each other's data, and immutability is what lets `tfs_client` stay pure REST while `parser` stays provider-blind.

**Status key**: ✅ exists and matches the spec · ⚠️ exists, needs change · 🆕 to be added

---

## Configuration

### `Config` ⚠️

Frozen; the sole product of the only module that reads the environment. Secrets are declared in `SECRET_FIELDS` and redacted by a custom `__repr__`, so a stray repr in a traceback cannot leak one.

| Field | Type | Default | Notes |
|---|---|---|---|
| `tfs_base_url`, `tfs_project`, `tfs_repo`, `tfs_pr_id` | str/int | — | Required |
| `tfs_api_version` | str | `6.0` | Fall back to `5.0`, then `4.1` on older servers |
| `auth_mode` | str | — | `bearer` (pipeline) or `basic` (PAT) |
| `tfs_token` | str | — | **Secret.** Reading credential |
| `post_token` | str | `""` | **Secret.** Writing credential, required only when posting |
| `llm_provider`, `llm_model`, `llm_base_url` | str | — | `claude`/`openai`/`azure`/`ollama` |
| `llm_api_key` | str | — | **Secret** |
| `checklist_repo` | str | `""` | From `TFS_REPO_CODE_REVIEW_CodeReviewChecklistT` |
| `checklist_path`, `checklist_file_pattern`, `checklist_branch` | str | `/`, `*.md`, `main` | ⚠️ **G1** — contradicts FR-008 |
| `checklist_max_chars` | int | `60000` | Measured, not guessed: the real corpus is 48,485 chars |
| `dry_run` | bool | `True` | Safe default |
| `fail_on_contradiction` | bool | `False` | Never blocks by default |
| `review_exclude_patterns` | tuple | built-in | Never sent to the provider |
| `review_max_files`, `review_max_diff_lines`, `llm_max_chunk_lines` | int | 40 / 3000 / 1200 | Review bounds |
| `agent_repo`, `agent_ref`, `local_logic`, `bootstrapped_sha` | — | — | Feature 002 bootstrap; out of scope, retained |
| `inline_severity_threshold` | str | `major` | 🆕 **G3** — `blocker`/`major`/`minor` |
| `report_dir` | str | `.review-reports` | 🆕 **G2** |

**Changes required**

- 🆕 `inline_severity_threshold` (FR-019a). Validated against the three-level scale; an unrecognised value is a configuration problem reported alongside every other, not a silent fallback.
- 🆕 `report_dir` (FR-033).
- ⚠️ `checklist_file_pattern` / `checklist_branch`: FR-008 makes discovery **unconfigurable** — all `.xlsx` and `.docx`, default branch, recursive. The fields stay for the retained markdown path but stop governing document discovery.

---

## Story and pull request

### `WorkItem` ✅ and `AcceptanceCriterion` ✅

`WorkItem.from_payload` strips HTML from every field and falls back from the dedicated acceptance-criteria field to the description when the work-item template lacks one — losing criteria silently would hollow out the coverage map. `AcceptanceCriterion` carries `ordinal`, `text`, and `work_item_id`, which is what lets a finding cite a specific criterion (FR-015).

### `PullRequestContext` ✅

Carries `pr_id`, title, description, branches, and — after `with_iteration` — `iteration_id`, `iteration_commit`, `base_commit`. Its `run_id` property (`<pr_id>.<iteration_id>`) becomes the run report's identity (**G2**), so no new concept is needed.

### `DeclaredScope` ✅

Parses the author's "Covered" / "Not in this PR" lists out of the pull request description. Authoritative for intent — the "Not in this PR" list is never flagged — but every "Covered" line is verified against the diff. That check produces the agent's headline finding, the false coverage claim.

---

## Changes

### `ChangedFile` ✅, `SkippedFile` ✅, `ChangeSet` ✅, `ReviewableSet` ✅

`ChangedFile` holds `path`, `change_type`, `is_binary`, `diff`, `line_map`, `changed_lines`, `relevance`. The `line_map` is excluded from equality (`compare=False`) and is what makes inline anchoring possible — see research R8 for why diffs are computed locally rather than fetched.

`SkippedFile.reason` is a closed vocabulary: `excluded`, `bound`, `binary`, `deleted`, `unavailable`. Every skip is reported (FR-017), which is the reconstructed Principle VII in entity form.

`ReviewableSet` partitions into `reviewed` / `excluded` / `unreviewed`. **`excluded` is the FR-028 and SC-012 boundary**: nothing in it reaches the provider, asserted by `tests/contract/test_excluded_files_never_sent.py`.

---

## Checklist

### `ChecklistDocument` ✅ and `ChecklistItem` ✅ — present, unreachable

Both are complete and unit-tested. Neither is reachable from a run, because nothing imports `checklist_docs.py` (**G1**, research R1).

`ChecklistDocument` — `filename`, `format`, `status`, `skip_reason`, `rule_count`, `sheets_ignored`. Its `__post_init__` refuses a `skipped` document with no `skip_reason`: *"an unexplained skip is exactly the silence Principle VII forbids."* This invariant is what makes FR-008a ("name every document it found but could not read") true by construction.

`ChecklistItem` — `item_id`, `title`, `detail`, `severity`, `section`, `documents`, `derived_id`. The unit of citation (FR-015). Invariants: an item with no `item_id` is not citable and an item with no `title` is not a rule; both raise. `merged_with` collapses the same rule appearing in two documents into one rule citing both. `source_label` is how it is attributed in a prompt and in a posted comment.

### `CombinedChecklist` ✅

`items`, `documents`, `dropped_for_budget`, with `documents_read` / `documents_skipped` / `documents_without_rules` projections. These projections are exactly the FR-008a report surface — the data is ready; only the wiring is missing.

### `Checklist` / `ChecklistFile` ⚠️ (legacy)

The markdown path's shape (`combined_markdown`). Retained for one cycle, then retired (research R1).

---

## Findings

### `CoverageEntry` ✅

`criterion`, `status`, `evidence`, `ordinal`. Status vocabulary: `appears_addressed`, `not_addressed`, `possible_contradiction`.

**`not_addressed` never produces a comment.** Guarded by `tests/unit/test_routing_not_addressed.py`. This is the agent's primary noise control and the severity threshold must not disturb it (research R2).

### `ChecklistViolation` ✅, `CodeIssue` ⚠️, `FalseCoverageClaim` ✅

`CodeIssue.severity` keeps the provider-facing `high`/`medium`/`low` vocabulary. **G3 does not rename it** — that vocabulary is what the model is prompted to emit and what `parser.validate_payload` enforces; renaming it would invalidate prompt, contract, and parser at once for a change no reader sees. The Blocker/Major/Minor scale is derived at routing time by the mapping in research R2.

### `ReviewReport` ⚠️

Aggregates coverage, violations, code issues, false claims, skipped and unreviewed files, outcome (`complete`/`degraded`), notes, plus the Feature 002 provenance fields (`agent_source`, `documents`, `dropped_citations`, `dropped_for_budget`).

`has_blocking_findings` already draws exactly the spec's Blocker line: false coverage claims, possible contradictions, or any high-severity code issue. **No change needed** — the concept exists and is correct; G3 names it.

🆕 Add `severity_of(finding)` returning `blocker`/`major`/`minor` per the R2 mapping, so routing and the run report share one definition rather than each deriving its own.

---

## Run provenance and reporting

### `AgentSource` ✅

`mode` (`fetched`/`local`), `commit`, `ref`, `repo`. Printed first in every report and summary so a review produced from an uncommitted working copy can never be mistaken for one produced by committed logic. Feature 002; retained.

### `RunInvocation` ✅

`pr_id`, `dry_run`, `local_logic`.

### `RunReport` 🆕 — **G2, the one genuinely new entity**

The durable local record (FR-033–FR-037, SC-013). Nothing in the package writes a file today; the only `write()` is in `source_fetch.py`.

| Field | Type | Purpose |
|---|---|---|
| `run_id` | str | From `PullRequestContext.run_id` |
| `started_at`, `finished_at` | str | UTC ISO-8601 |
| `repository`, `pr_id` | str/int | What was reviewed (FR-034) |
| `dry_run` | bool | FR-037 — preview runs report identically, marked |
| `agent_source` | `AgentSource` | Which logic ran |
| `provider`, `model` | str | Which service received content (FR-030). **Never the key** |
| `findings` | tuple | Each with file, line, severity, text, cited rule, and disposition |
| `documents` | tuple | `ChecklistDocument` records — read, skipped, no rules |
| `work_items` | tuple | Linked stories considered |
| `excluded`, `unreviewed` | tuple | `SkippedFile` records |
| `failures` | tuple | Every failure met (FR-034) |
| `outcome` | str | `complete` / `degraded` / `aborted` |

**Finding disposition** is a closed vocabulary — `posted_inline`, `in_summary`, `suppressed_duplicate`, `post_failed`. This is what makes SC-006 ("no duplicates on re-run") and FR-021 ("name the findings in each group") verifiable by script.

**Invariants**

1. Serialised output passes through `config.redact()` **as a whole string**, not field by field. A secret realistically escapes inside an exception message in `failures`, which field-level redaction misses (research R5).
2. Written from a `finally`, so an aborted run still leaves evidence (FR-035, research R7).
3. Never contains `tfs_token`, `post_token`, or `llm_api_key` (FR-036). Asserted by an extension to `tests/contract/test_no_secrets_leak.py` — without that assertion this is a promise, not a property.

---

## Entity relationships

```text
Config ──────────► every module (sole environment reader, Principle I)

PullRequestContext ──► ChangeSet ──► ReviewableSet ──┬─► reviewed   ──► prompt ──► provider
                  │                                   ├─► excluded   ──► NEVER sent (SC-012)
                  │                                   └─► unreviewed ──► reported, not sent
                  │
                  ├──► WorkItem ──► AcceptanceCriterion ──┐
                  └──► DeclaredScope ────────────────────┤
                                                          ├──► ReviewReport ──┬──► inline comments
CombinedChecklist ──► ChecklistItem ─────────────────────┘                    ├──► summary comment
        └──► ChecklistDocument (status of every document, FR-008a)            └──► RunReport 🆕
```

---

## Summary of model changes

| Change | Entity | Requirement | Gap |
|---|---|---|---|
| Add `inline_severity_threshold` | `Config` | FR-019a | G3 |
| Add `report_dir` | `Config` | FR-033 | G2 |
| Stop `checklist_file_pattern`/`checklist_branch` governing document discovery | `Config` | FR-008 | G1 |
| Add `severity_of(finding)` | `ReviewReport` | FR-016 | G3 |
| Add entity and writer | `RunReport` | FR-033–FR-037 | G2 |

Everything else already exists and matches. The model was designed for this specification; it is the wiring that is missing.
