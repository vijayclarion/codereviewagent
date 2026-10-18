# Contract: Checklist Corpus Acquisition and Inventory

**Feature**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md)

What a run must do to turn a configured repository name into rules, and what it must say
about it. Every clause here is observable from the run's own output — that is the point.
A clause that can only be verified by reading the source is not a contract, it is a wish.

---

## 1. Identifying the source

Resolution order, first non-empty wins:

| # | Name | Status |
|---|---|---|
| 1 | `TFS_REPO_CODE_REVIEW_CodeReviewChecklist` | canonical |
| 2 | `TFS_REPO_CODE_REVIEW_CodeReviewChecklistT` | accepted, legacy |
| 3 | `CHECKLIST_REPO` | accepted, legacy |
| 4 | `_git/{name}` segment of `CHECKLIST_REPO_URL` | accepted, legacy |

**MUST**: the run records which of the four supplied the name (`ChecklistSource.setting`).
**MUST NOT**: require an operator to rename anything they already have set (FR-001).
**When all four are empty**: the run names **(1) only** as the setting to provide.

## 2. Obtaining the working copy

| Clause | Requirement |
|---|---|
| C2.1 | The copy is obtained by a means that carries binary documents intact (FR-002) |
| C2.2 | Only what the review needs is retrieved — no full history (FR-003) |
| C2.3 | `CHECKLIST_BRANCH` unset takes the repository's own default branch, and the run states which reference it read |
| C2.4 | No credential is written to disk, stored in the copy's settings, or appears in output (FR-004) |
| C2.5 | The copy is removed when the run ends, on every path including failure (FR-005) |
| C2.6 | Failure to obtain the copy degrades to a story-coverage-only review with a stated reason, and is **neither** a successful review **nor** a setup failure (FR-006) |

C2.6 is the one most easily broken by accident: the natural implementation lets the
existing `SetupFailure` from `source_fetch.clone` propagate, which exits 2 and loses the
story half of the review as well.

## 3. Which files are considered

- Recursive walk from `CHECKLIST_PATH` (default: repository root).
- Filename matched case-insensitively against `CHECKLIST_FILE_PATTERN`, a comma-separated
  list, default `*.xlsx,*.docx`. A pattern the document reader cannot handle routes to the
  text path instead; when the document path yields nothing, the text path runs with `*.md`
  so that a feature-002 configuration keeps working unchanged.
- `~$*` lock files are ignored and are **not** reported as skipped documents — they are not
  documents.
- **MUST**: adding a document to the repository requires no configuration change (FR-007,
  SC-010).
- **MUST**: the default includes both spreadsheets and Word documents, and the list remains
  operator-adjustable without a code change.

## 4. Per-document outcome

Every matched file reaches exactly one terminal state, and carries either a count or a
reason:

| State | Carries | Condition |
|---|---|---|
| `read` | `rule_count > 0` | parsed, rules found |
| `no_rules` | — | parsed, zero rules (FR-013) |
| `skipped` | `skip_reason` | unreadable, encrypted, corrupt, or unsupported (FR-012) |

**MUST**: one unreadable document never stops the run and never affects another document.
**MUST**: `len(inventory.documents) == number of files the walk matched`. This equality is
SC-002 and is the single most useful assertion in the suite.

## 5. Budget and selection

- Rules are applied in relevance order until `CHECKLIST_MAX_CHARS` is reached (FR-016).
- Selection is **deterministic**: same change + same documents ⇒ same applied set, on every
  run and for every operator. Ties break on `(document filename, item_id)`.
- Omission requires a stated basis. `dropped_for_budget` non-empty with an empty
  `selection_basis` is an invariant violation, not a log line.
- The run states: rules applied, rules omitted, and that relevance to the changed files was
  the basis.

## 6. What the run must say

One block, identical in preview and in the posted summary:

```
Checklist: <repo> @ <ref> (<commit>)            ← or: not applied — <reason>
  API-Security-Checklist.xlsx      read, 42 rules
  Secure-Coding-Standard.docx      read, 31 rules
  Architecture-Notes.docx          read, no rules
  Legacy-Standards.xlsx            skipped — not a readable spreadsheet (corrupt or encrypted file)
  Rules applied: 68 of 73 (5 omitted — relevance to the changed files)
Story: #4412, 6 criteria judged    ← or: not assessed — <reason>
```

**MUST**: every reduction in coverage appears here (FR-014, FR-026, SC-004).
**MUST NOT**: any of this reach only the phase log — the phase log is not posted, and a
reader on the pull request would see a clean-looking summary and nothing else.

## 7. The four distinguishable misconfigurations

US4 requires each to produce a different, actionable statement. The test for this contract
asserts four **distinct** reasons, not four non-empty ones:

| Condition | The statement names |
|---|---|
| no setting | `TFS_REPO_CODE_REVIEW_CodeReviewChecklist`, as the setting to provide |
| repository not found | the name tried and the reference |
| not permitted | that the credential lacks Code (read) **on that repository**, distinct from not-found |
| no document matched | the pattern, the path, the reference, and that the repository *was* reachable |

## 8. Boundaries this contract must not breach

Enforced by `tests/contract/test_import_boundaries.py`. Breaking one breaks a test by
design:

- The corpus module **MUST NOT** contain the literal `git` or any `subprocess` call — it
  asks `source_fetch` (`test_git_is_invoked_from_one_module_only`).
- It **MUST NOT** import `openpyxl` or parse a document itself — it hands bytes to
  `checklist_docs.read` (`test_document_format_libraries_stay_in_one_module`).
- It **MUST NOT** read the environment — it receives a `Config`
  (`test_environment_is_read_only_in_config`).
- Checklist documents **MUST NOT** appear in the review's changed-file counts or findings
  (FR-018). `*.xlsx` and `*.docx` join `DEFAULT_EXCLUDE_PATTERNS`.
- Preview issues no write. Cloning is a read; it is permitted in preview and must remain so,
  or the preview stops previewing the thing that will be posted
  (`test_preview_makes_no_writes.py`).
