# Data Model: Local-Mode Call Flow Diagram and Developer Onboarding Guide

**Feature**: `005-agent-flow-developer-guide` | **Date**: 2026-09-17

These are **record types for a document**, not runtime classes. Nothing here is compiled or
imported; this feature authors no code (FR-034). Each type below says what one row of the
deliverable must carry, which requirement demands it, and the validation rule that makes a
half-filled row visible during review rather than after publication.

The organising fact: **`Stage` is the shared type.** The diagram renders its `name` and
`owning_file`; the guide renders all of it. Both come from the Flow Ledger in
[plan.md](./plan.md#flow-ledger) (decision **D1**), so a `Stage` edited in one place is
edited in both.

---

## Stage

One step of a review. Twelve exist.

| Field | Meaning |
|---|---|
| `number` | 0–12, execution order |
| `name` | The searchable short name — `config`, `changes`, `llm`. **Must equal 004's stage name** where 004 has one |
| `owning_file` | The module that owns the stage. More than one only where the stage genuinely spans modules (stage 9) |
| `methods` | Ordered list of `MethodRole`, in call order |
| `input` | What arrives from the previous stage, named as a thing not a type |
| `output` | What is handed to the next stage |
| `log_line` | The line a run prints, verbatim from an executed run, or `none` |
| `decisions` | The `DecisionPoint`s that leave this stage |

**Validation**

- `methods` is non-empty. A stage with no method is a stage that does not exist.
- `log_line` is either quoted from an executed run or the literal `none` — never invented.
  Stages 0, 1 and 5 legitimately carry `none` or a non-phase line (**E2**).
- `input` of stage *n* equals `output` of stage *n−1*, or the mismatch is explained.
  This is what FR-011 buys: no stage's input appears from nowhere.
- Every `name` that 004's Part 4 table also uses is spelled identically (**D5**, FR-032).

---

## MethodRole

One method inside a stage. Roughly sixty exist across the twelve stages.

| Field | Meaning |
|---|---|
| `file` | Repository-relative module path |
| `method` | The name as written in the source, including a leading `_` where private |
| `role` | **One line.** What it does, in the flow's terms, not a restatement of its name |
| `calls` | Optional: methods it delegates to that are worth following |

**Validation**

- `file` + `method` resolves in the current tree. This is verification gate **G3**, and it is
  the single most mechanical check in the feature — an extracted list, asserted one by one.
- `role` does not begin with the method's own name re-spelled. "`_fetch_story` fetches the
  story" fails; "recovers the linked work items, and the *reason* when there are none, so a
  token without Work Items access loses the story half loudly instead of failing the run"
  passes.
- A private method appears only where a reader following the flow would otherwise lose the
  thread. Completeness for its own sake fails FR-008.

---

## DecisionPoint

A place the run can diverge. Fourteen exist.

| Field | Meaning |
|---|---|
| `id` | `D-A` … `D-N` |
| `stage` | The stage it leaves |
| `condition` | What is being decided, in plain language |
| `branches` | Two or more `Branch` records |
| `fork_ref` | 004's `A1`–`A9` identifier where the same fork is already recorded, else empty |

### Branch

| Field | Meaning |
|---|---|
| `label` | The edge label in the diagram |
| `signal` | How an operator can tell this branch was taken — a log line, a summary phrase, an exit code |
| `destination` | The next stage, or a terminal outcome |

**Validation**

- Every `Branch` has a `destination`. **No path trails off** — FR-005, and the most likely
  way the diagram fails review.
- Every `Branch` has a non-empty `signal`. A fork a reader cannot detect from the outside is
  not documented, it is merely drawn.
- Where `fork_ref` is set, `signal` matches 004's row. Where it is empty, the guide says this
  fork is new here, so a reader does not go looking for it in 004.

**The fourteen**: `D-A` entry point (= A1) · `D-B` work items linked / readable (= A3, A4) ·
`D-C` document corpus → markdown fallback → none (= A2) · `D-D` iterations present (= A5) ·
`D-E` per-file deleted / binary / unretrievable · `D-F` exclusion match · `D-G` bound reached ·
`D-H` nothing reviewable (= A6) · `D-I` one chunk or many · `D-J` response parses / retry /
degrade (= A7) · `D-K` finding anchors to a changed line · `D-L` `not_addressed` → no comment ·
`D-M` already said → suppressed (= A9) · `D-N` preview or post (= A8).

---

## FileEntry

One shipped path. Twenty modules plus eight non-module paths.

| Field | Meaning |
|---|---|
| `path` | Repository-relative |
| `purpose` | One line. **Cited to 004 Part 3** where 004 has it (**D5**) |
| `stage` | The stage it serves, or `none` |
| `invariant` | The architectural rule constraining it, and the test that enforces it, or empty |

**Validation**

- Every path that ships appears. SC-004 is a 100% check, so the list is generated from the
  tree and then filled, never assembled from memory.
- `stage: none` is written explicitly. An omitted stage and a stage that does not exist must
  not look the same (FR-014).
- Where `invariant` is set, it names the enforcing test file. There are five, and they are
  004's table; this feature binds each to a stage rather than restating the rule.

---

## ContextSource — *new in this feature*

One thing placed in front of the model alongside the change. Four exist.

| Field | Meaning |
|---|---|
| `name` | Diff · linked story · PR description and declared scope · checklist rules |
| `contributes` | What judgement it makes possible |
| `always_present` | Whether a run can proceed without it, and what it says when it does |
| `shape` | What form it takes — for the diff, **three lines of context around each hunk** |
| `withheld` | What is retrieved but **not** sent, where the two differ (FR-025) |

**Validation**

- The diff row states the context width as a number, not as "some surrounding lines".
- The diff row states how an **added** file differs (**B1.2**, FR-022).
- `withheld` is non-empty for the diff row: both complete file blobs are fetched and only the
  diff is sent (**B1.4**). This row is the whole reason the field exists.
- Each row's `always_present` names the text a run emits when the source is missing —
  "No story coverage was assessed: …", "No checklist was applied (…)".

---

## ReviewBlindSpot — *new in this feature*

One judgement the tool cannot make. Five classes.

| Field | Meaning |
|---|---|
| `judgement` | What a reader might expect it to catch |
| `why_not` | Which `ContextSource` limit makes it impossible |
| `instead` | What a reader should do — a human reviewer, a test, a different rule |

**Validation**

- `why_not` points at a `ContextSource` row or a `SizeLimit` row. A blind spot with no named
  cause is an opinion.
- At least one row concerns the **split** case (`B1.6`): a pass that sees part of a change
  knows less than a pass that sees all of it, and that is a different cause from the diff
  width.
- The set is framed as consequences of a deliberate boundary, not as defects (FR-028).

---

## SizeLimit

One reduction. Seven rows (six limits plus the ranking that decides who survives them).

| Field | Meaning |
|---|---|
| `order` | 1–7. **The load-bearing field** (**D8**) |
| `bounds` | What it counts — files, diff lines, characters, changed lines per request |
| `default` | The value in the code |
| `setting` | The environment variable, or `—` where none exists |
| `reported_at` | The exact output that reveals it (**D9**) |

**Validation**

- `order` is unique and contiguous. If two reductions can be reordered without changing the
  result, say so rather than implying a sequence that is not one.
- `reported_at` quotes real output — `### Not sent for review`, a `reductions` line, `chunks=N`.
  "It is reported in the summary" fails.
- Row 3 (relevance ranking) states the weights and the tie-break, because "most relevant
  first" is unfalsifiable and the tie-break is what makes the bound cover more files.

---

## FailureMode

One departure from the straight-through path. Seven rows.

| Field | Meaning |
|---|---|
| `trigger` | What causes it |
| `recovery` | What is attempted, and **how many times** |
| `lost` | What the run gives up — the most under-documented field in the project |
| `visible` | What a person sees, on the console and on the pull request |
| `exit_code` | 0, 1 or 2 |
| `anchor` | The `ClaimAnchor` |

**Validation**

- `lost` is never blank. For a provider rejection it is *the findings of every chunk already
  parsed in this run* (**B3.3**), which is the fact a reader is least likely to guess.
- `recovery` gives a number. "It retries" fails; "three attempts, backoff 1/2/4 seconds" and
  "exactly one stricter retry" pass.
- `exit_code` is stated even where it is 0 — especially there, since a degraded review exiting
  0 is the project's most counter-intuitive contract.

---

## ClaimAnchor

Attached to every behavioural statement in both deliverables.

| Field | Meaning |
|---|---|
| `location` | `file.py:line` or `file.method`, or a document section for a delegated claim |
| `basis` | `[executed]` · `[read]` · `[unobserved]` |
| `closing_condition` | For `[unobserved]` only: what observation would close it |

**Validation**

- `[executed]` requires that something was actually run on a stated date, and the run is
  listed in the guide's Verification Record.
- `[unobserved]` **must** carry a `closing_condition` (**D7**). An unobserved claim with no
  route to closure is the shape of 001's gap G4, and this project has already paid for it.
- A claim delegated to 004 anchors to 004's section, not to the code — so a later reader
  correcting the code knows both documents are downstream of it.

---

## Relationships

```text
FlowLedger (plan.md)
   |
   +-- Stage (12) ---------+-- MethodRole (~60)      -> guide only
                           +-- DecisionPoint (14) ---+-- Branch (2+ each)
                           |                              -> diagram + guide
                           +-- FileEntry (28) via FileEntry.stage
                           +-- SizeLimit (7) at stages 6, 7, 9
                           +-- FailureMode (7) at stages 3, 4, 5, 7, 9
ContextSource (4) --- assembled at stage 9 -----------> ReviewBlindSpot (5)
ClaimAnchor -------- attached to every row of every type above
```

**The two invariants that hold this together**

1. **Every `Stage` appears in both deliverables.** The diagram renders `name` and
   `owning_file`; the guide renders the rest. A stage in one and not the other is the drift
   **D1** exists to prevent.
2. **Every row of every type carries a `ClaimAnchor`.** That is FR-030, and it is what lets a
   reader six months from now check this document against the code instead of trusting it.

---

# Frozen rows (T009)

The record instances, fixed at planning time so the guide's author fills prose around settled
facts rather than re-deriving them. Anchors and `[executed]`/`[read]` bases carry forward from
the [Boundary Register](./plan.md#boundary-register) unchanged.

## ContextSource — the four things placed in front of the model

| Name | Contributes | Always present? | Shape | Withheld |
|---|---|---|---|---|
| **The diff** | The only view of changed code | Yes — an empty one ends the run before stage 9 | Unified diff, **3 context lines** each side of a hunk. An **added** file diffs against empty, so effectively all of it | **Both complete file blobs.** Fetched to compute the diff locally; only the diff is sent |
| **Linked story** | Acceptance criteria to judge coverage against | No — "No story coverage was assessed: …" | Title, type, state, description, acceptance criteria, and criteria **enumerated** so a finding can cite number 4 | Every other field of the work item |
| **PR description + declared scope** | What the author claims is covered, to verify against the diff | No — "no Covered / Not-in-this-PR section, so no coverage claim can be verified" | Description verbatim, plus the parsed Covered / Not-in-this-PR lists | — |
| **Checklist rules** | The rules violations are reported against | No — "No checklist was applied (…)" | `[IDENTIFIER] rule text`, selected against the surviving files, within `CHECKLIST_MAX_CHARS` | Rules dropped for budget, counted in `RunInventory.reductions` |

## ReviewBlindSpot — the five classes

| Judgement | Why not | Instead |
|---|---|---|
| Whether a **caller elsewhere** is broken by this change | The caller's file is unchanged, so it is never fetched (**B1.3**) | A human reviewer, or a compiler/test run |
| Whether an override matches its **base class** contract | The base class is unchanged, so it is never fetched | A human reviewer |
| Whether the change follows a **project-wide convention** not written in the checklist | Only the changed region and the rules are shown | Write the convention into a checklist document |
| Whether a **test exists** for the new behaviour | Test files are separate files; unchanged ones are invisible, changed ones are judged as diffs like any other | A coverage gate |
| Whether the changed code is **reachable at all** | Reachability is a whole-program property | A human reviewer, or static analysis |
| *(split runs only)* Whether two changed files are **consistent with each other** | Each pass sees only its own chunk and is told so (**B1.6**) | Lower `LLM_MAX_CHUNK_LINES` pressure by narrowing scope, or review the pair by hand |

## SizeLimit — the seven reductions, in application order

| Order | Bounds | Default | Setting | Reported at |
|---|---|---|---|---|
| **1** | Files with nothing reviewable — deleted, binary by extension, binary by content, unretrievable | — | — | `### Not sent for review`, reason `deleted` / `binary` / `unavailable` |
| **2** | Paths matching an exclusion pattern | — | `REVIEW_EXCLUDE_PATTERNS`, `REVIEW_EXCLUDE_MODE` | same table, reason `excluded — matched <pattern>` |
| **3** | *(ranking, not a cut)* Order of survival: story words ×3, checklist words ×2, source file +1; ties broken **smallest change first**, so the bound covers more files rather than being eaten by one large one | — | — | `selection_basis` in the inventory |
| **4** | Count of files reviewed | **40** | `REVIEW_MAX_FILES` | same table, reason `bound` |
| **5** | Total changed diff lines reviewed | **3000** | `REVIEW_MAX_DIFF_LINES` | same table, reason `bound` |
| **6** | Characters of checklist corpus | **60000** | `CHECKLIST_MAX_CHARS` | `RunInventory.reductions` — "N of M rules were not applied, selected by …" |
| **7** | Changed lines per provider request | **1200** | `LLM_MAX_CHUNK_LINES` | `phase=llm chunks=N` |

Orders 4 and 5 are evaluated together per file and cannot be reordered; 6 applies to a corpus
already narrowed against the files that survived 1–5, so it genuinely follows them.

## FailureMode — the seven departures

| Trigger | Recovery | Lost | Visible | Exit |
|---|---|---|---|---|
| Agent source could not be fetched (default path) | None — **never** falls back to the local copy silently | The whole review | `ai-review setup failure: the review logic could not be obtained — …` | **2** |
| Token cannot read work items (401/403) | None; the rest of the review continues | Story coverage only | `phase=workitems outcome=degraded count=0`, and the reason in the summary | **0** |
| Checklist unreadable or unresolved | Markdown fallback; then coverage-only | The rules half, named | `phase=checklists outcome=degraded`, `files=` instead of `rules=` | **0** |
| Pull request has no iterations | None | The whole review | Run stops after `phase=pullrequest`; notice posted | **0** |
| Nothing reviewable after exclusions and bounds | Not a failure — a real answer | Nothing | "There was nothing to review …"; `phase=llm outcome=skipped chunks=0` | **0** |
| Provider unreachable, or rejects the request | 3 attempts on 429/500/502/503/504, backoff 1/2/4 s, `Retry-After` capped at 30 s. 401/403/404 are **not** retried | **Every finding from every chunk already parsed in this run** | `phase=llm outcome=degraded`; notice posted | **0** (401/403/404 → **2**) |
| Response unparseable, or answer truncated mid-JSON | **Exactly one** stricter retry | Every finding from every chunk already parsed | `phase=llm outcome=degraded retries=1` | **0** |

The row a reader is least likely to guess is the sixth: **the loss is the whole run's
findings, not the failed chunk's.**
