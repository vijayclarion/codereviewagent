# Phase 1 Data Model

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

The spec names nine entities. **Seven already exist** in `review_agent/models.py`, built by
an earlier cycle and in four cases never populated by anything. This document is therefore
mostly a delta: what each entity already carries, what it gains, and which invariant makes
it impossible to hold a silent outcome.

House rules, unchanged: frozen dataclasses, invariants in `__post_init__`, no inheritance,
no module here talks to TFS or to a provider.

---

## Entity map

| Spec entity | Module home | State today |
|---|---|---|
| Checklist Repository Source | `models.ChecklistSource` | **new** |
| Checklist Document | `models.ChecklistDocument` | exists, complete |
| Checklist Rule | `models.ChecklistItem` | exists; identifier derivation changes (R4) |
| Rule Corpus | `models.CombinedChecklist` | exists, never constructed; gains 4 members |
| Linked Work Item | `models.WorkItem` | exists, complete |
| Acceptance Criterion | `models.AcceptanceCriterion` | exists, complete |
| Finding | `ChecklistViolation` / `CodeIssue` / `CoverageEntry` / `FalseCoverageClaim` | exist; violation gains `rule_id` |
| Run Inventory | `models.RunInventory` | **new** |
| Deliberate Fault | not a runtime entity | documentation only — see [contracts/demonstration.md](./contracts/demonstration.md) |

---

## New: `ChecklistSource`

Where the rules came from, and — when they did not come at all — why.

```python
@dataclass(frozen=True)
class ChecklistSource:
    repo: str = ""              # repository name as configured
    ref: str = ""               # branch or reference the copy was taken at
    commit: str = ""            # short sha of that copy
    setting: str = ""           # which configuration name supplied `repo` (R1)
    available: bool = False
    unavailable_reason: str = ""
```

**Invariants**

- `available=False` requires a non-empty `unavailable_reason`. An unavailable source with
  no reason is the silence Principle VII forbids, and it is the condition this project has
  actually been in.
- `available=True` requires a non-empty `repo`.
- `commit` is never required: a source can be available and its sha unreadable.

**`unavailable_reason` must distinguish the four conditions of FR-024 / US4**, because each
names a different correction:

| Condition | Reason states |
|---|---|
| no setting | the setting to set, by name — `TFS_REPO_CODE_REVIEW_CodeReviewChecklist` |
| not found | the repository name tried and the branch |
| not permitted | that the credential lacks Code (read) on *that* repository |
| nothing matched | the pattern applied, the path, the branch, and that the repository was reachable |

**Never carries**: a URL containing a credential, or a token in any form. The clone URL is
built in `source_fetch` and does not travel on this entity.

---

## `ChecklistItem` — identifier derivation changes

Fields are unchanged (`item_id`, `title`, `detail`, `severity`, `section`, `documents`,
`derived_id`). What changes is how `item_id` is produced when the document supplies none.

| Source | `item_id` today | `item_id` after |
|---|---|---|
| spreadsheet, `#` populated | the cell, verbatim | unchanged — verbatim (FR-009) |
| spreadsheet, `#` empty | `{stem}:{sheet}:{row}` | `{stem}:{sheet}:{digest8}` |
| docx, `SEC-WEB-01` marker | the marker, verbatim | unchanged — verbatim |
| docx, tolerant fallback | `{stem}:{ordinal}` | `{stem}:{digest8}` |

`digest8` is the first 8 hex characters of `sha256(f"{filename}|{section}|{title}")`.

**Invariant added**: two rules in one corpus may not share an `item_id`. A collision means
two rules with identical filename, section and text — a genuine duplicate — and
`merged_with` (already present, `models.py:304`) folds them into one rule citing both
documents. Collision resolution therefore happens on the way into the corpus, not by
mutating the id.

**Why this matters beyond tidiness**: after R7 the `item_id` *is* a posted comment's
identity. A row inserted above a rule must not resurface every comment below it.

---

## `CombinedChecklist` — the Rule Corpus

Gains four members; the existing eight properties are untouched.

```python
items: tuple                    # ChecklistItem, in applied order        (exists)
documents: tuple                # ChecklistDocument, every one found     (exists)
dropped_for_budget: tuple       # ChecklistItem omitted by the bound     (exists, never set)
source: ChecklistSource = None  # NEW — where the corpus came from
selection_basis: str = ""       # NEW — "" when all rules fit, else "relevance to the changed files"
unavailable_reason: str = ""    # NEW — shared shape with Checklist (R9)
prompt_text: str                # NEW property — what the prompt renders (R9)
```

**Invariants**

- `dropped_for_budget` non-empty requires `selection_basis` non-empty. A corpus cannot
  omit rules without stating on what basis it kept the others (FR-016).
- `available` (existing property, `bool(items)`) false requires `unavailable_reason`.
- No `ChecklistItem` appears in both `items` and `dropped_for_budget`.
- `documents` accounts for **every** file the walk matched, including those it could not
  read. This is the invariant SC-002 measures.

**`prompt_text` shape** — grouped by document, identifier first, so a violation can cite
what it saw:

```
## From: API-Security-Checklist.xlsx

- [SEC-API-01] Validate every inbound identifier against the caller's tenant — Detail…
- [API-Security-Checklist:Rules:9f3c1a77] Reject requests larger than 1 MB

## From: Secure-Coding-Standard.docx

- [SEC-WEB-01] Never concatenate user input into a SQL statement — Detail…
```

**Ordering**: applied order is the relevance rank of R5, tie-broken on
`(document filename, item_id)`. The corpus is therefore identical for the same change and
the same documents, whatever order the filesystem walk returned — which is what SC-006
rests on.

---

## `ChecklistViolation` — gains `rule_id`

```python
item: str          # what the model called the rule            (exists)
rule_id: str = ""  # NEW — resolved against the applied corpus
source: str = ""   # the document filename, RESOLVED not reported (R6)
issue: str = ""
file: str = ""
line: int = 0
```

**Resolution rule** (in `parser`, against the applied corpus):

1. `rule_id` returned by the model and present in the corpus → use it; `source` becomes
   that rule's document filename, overwriting whatever the model said.
2. No `rule_id`, but `item` matches a rule's identifier or title exactly (normalised) →
   same as (1).
3. Neither → the violation is **not** a finding. It goes to
   `ReviewReport.dropped_citations` and is reported in the summary as a citation that
   matched no applied rule.

Rule (3) is not tidiness either: an unresolvable citation has no stable identity, so under
R7 it would re-post on every run. Dropping it is the only behaviour consistent with FR-028.

---

## New: `RunInventory`

What one run actually applied. This is the object the demonstration's checkpoint is checked
against, and the thing rendered by R11.

```python
@dataclass(frozen=True)
class RunInventory:
    source: ChecklistSource = None
    documents: tuple = ()          # ChecklistDocument — all of them
    rules_read: int = 0
    rules_applied: int = 0
    rules_omitted: int = 0
    selection_basis: str = ""
    work_items: tuple = ()         # ids
    criteria_judged: int = 0
    story_unavailable_reason: str = ""
    dropped_citations: tuple = ()

    @property
    def reductions(self): ...     # one sentence per reduction in coverage
```

**Invariants**

- `rules_applied + rules_omitted == rules_read`.
- `rules_omitted > 0` requires `selection_basis`.
- `work_items` empty requires `story_unavailable_reason` — "no work item is linked" is
  itself a reason and must be stated (FR-022).
- Every document in `documents` has a terminal status; `ChecklistDocument.__post_init__`
  already refuses a skipped document with no reason.
- **`reductions` is derived, not assembled by hand.** Implemented as a read-only property
  computed from the fields above — a caller cannot supply it, so a new reduction condition
  cannot be added without appearing in it. This is the mechanical form of SC-004, and
  `tests/unit/test_models_corpus.py` asserts that passing `reductions=` raises.

`ReviewReport` gains one field, `inventory: RunInventory = None`, alongside the four it
already has for this purpose.

---

## State: a checklist document's outcome

Unchanged from `checklist_docs.read`, restated because it is the spine of FR-012/FR-013/FR-014.

```
                 ┌──────────────► skipped (+ reason)   unreadable, encrypted, unsupported
matched by walk ─┤
                 ├──────────────► no_rules             read; contained none
                 └──────────────► read (+ rule_count)  read; contributed N rules
```

There is no fourth state and no default. A document that reaches the walk reaches exactly
one of these three, and each carries either a count or a reason. A run whose inventory
shows fewer documents than the walk matched is a defect, not a quiet success.

---

## What is deliberately *not* modelled

- **A written run report.** Excluded by the spec's scope boundary (001's gap G2 stays open).
  `RunInventory` is rendered, not serialised to disk.
- **A severity threshold.** Routing remains "anchors to a changed line or does not"
  (`output_layer.py:87-137`). 001's G3 stays open; this feature's FR-025 restates today's
  behaviour rather than changing it.
- **A new exit status.** `EXIT_DEGRADED` remains defined and unused.
- **Deliberate Fault** as a runtime type. It is a row in the demonstration's
  expected-results table, not something the agent constructs.
