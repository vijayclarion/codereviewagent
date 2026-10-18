# Data Model: Agent Documentation and Manual Run Runbook

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-16

The entities here are **parts of a document**, not Python classes. Nothing in this feature
becomes a dataclass; `models.py` is not touched. What this file fixes is the *shape* each
part of `guide.md` must have, so that a reader can trust one section the way they trust
another and so that `/speckit.tasks` generates "write N entries of shape X" rather than
"write about modules".

Every entity below states its fields, the rule that makes an instance valid, and where its
content is sourced from. **Where a source already exists, the entry is transcription with
verification — not authorship.** That distinction is the whole reason this file exists.

---

## 1. Documentation Reference

The deliverable itself: `specs/004-agent-docs-runbook/guide.md`.

| Field | Content |
|---|---|
| `audience` | Who it is for and who it is not for — one paragraph |
| `scope_statement` | What this document covers, and what `walkthrough.md`, `demo.md` and the README cover, with links (FR-002) |
| `parts` | Exactly four, in the D2 order: Run, What, Where, Flow |
| `verification_record` | One instance of entity 9, at the end |
| `maintenance_note` | What to update here when a module, entry point, setting or finding kind changes (FR-029) |

**Valid when**: all five fields present; `scope_statement` fits on one screen; every link
resolves to a file that exists in this repository.

**Invalid when**: it opens with a table of contents and no scope statement — the failure
that sends a reader looking for a walkthrough into a reference document.

---

## 2. Structure Entry

One row of the *Where things live* part. One per file or directory that ships.

| Field | Content | Required |
|---|---|---|
| `path` | Repository-relative | yes |
| `purpose` | One line, plain language | yes |
| `responsibility` | The single thing this module owns | modules only |
| `invariant` | The architectural rule it carries, and the test that enforces it | where one applies |
| `deliberate_state` | "This looks broken and is not" plus why | where it applies |

**Sources**:

- 14 module rows exist in `review_agent/README.md`'s module table — **transcribe and
  verify**, do not re-derive.
- 6 modules are missing from it (`__init__`, `__main__`, `run`, `bootstrap`, `textutil`,
  `source_fetch`) — new.
- 5 invariants come from `CLAUDE.md`'s table, each naming its `tests/contract/` file —
  transcribe.
- `deliberate_state` rows are known and enumerable: `specs/002-.../example-files/`
  (deliberately faulty, never collected, never to be fixed), `specs/003-.../demo-files/`,
  `.specify/memory/constitution.md` (unfilled template, four features running), and the
  `tests/fixtures/` corrupt-document fixture that the demo reports as skipped.

**Valid when**: every shipped path appears exactly once (SC-010), and every module row
carrying an invariant names the test file.

---

## 3. Test Group

One row of the same part, grouping the 532 tests by what they prove.

| Field | Content |
|---|---|
| `group` | `contract` / `integration` / `unit` / `demo` / `fixtures` |
| `proves` | What a failure in this group means |
| `members` | The test files, each with its one-line subject |

**Source**: the directory listing plus `CLAUDE.md`'s invariant table. The four contract
files that map to invariants are already documented; `test_checklist_inventory.py` and
`test_output_encoding.py` are not, and are new rows.

**Valid when**: a reader changing a named behaviour can find the group that would break.

---

## 4. Flow Stage

One stage of the *How a review flows* part.

| Field | Content | Required |
|---|---|---|
| `name` | The phase name as the agent prints it | yes |
| `input` | What it receives from the previous stage | yes |
| `output` | What it hands to the next | yes |
| `signal` | The literal log line, with its counter names | yes |
| `anchor` | `module.symbol` (D3) | yes |
| `exits` | Alternate paths that leave here (entity 5) | where any exist |

**Source, and the reason this entity is cheap**: the stages are not a modelling choice —
they are `main.run_review`'s own `log.phase(...)` calls, and the eight signals were
captured verbatim from `python -m tests.demo.run` (C14). The set is:

```
config · pullrequest · workitems · checklists · rules · changes · prior · llm · parse
```

plus `log.done(outcome, exit_code)` as the terminal line. `config` is emitted by
`main.main` before `run_review` is entered; the demo transcript starts at `pullrequest`
because it drives `run_review` directly.

**Valid when**: every stage has a signal and every signal has a stage (SC-004).

---

## 5. Alternate Path

A documented departure from the straight-through review. Nine of them, fixed by FR-009.

| Field | Content |
|---|---|
| `condition` | What selects this path |
| `signal` | How a reader can tell it was taken |
| `outcome` | Where the run ends up, and the exit code |
| `anchor` | `module.symbol` |

**The nine**:

| # | Condition | Where |
|---|---|---|
| A1 | Bootstrapped clone vs `--local` vs direct `main.py` | `bootstrap.main` — see D6 |
| A2 | Document checklists vs the markdown fallback | `checklist` |
| A3 | No linked story | `main._fetch_story` |
| A4 | Story exists, token cannot read it (`WorkItemAccessDenied`) | `main._fetch_story`; 003's S8 |
| A5 | No iterations on the pull request | `main.run_review` → `DegradedReview` |
| A6 | Nothing reviewable after exclusions | `main.run_review`, `reviewable.is_empty` |
| A7 | Provider unreachable, or unusable after the strict retry | `parser.parse_with_retry` → `main._report_degraded` |
| A8 | Preview vs posting | `output_layer.print_plan` / `post_plan` |
| A9 | A repeat run recognising its own prior comments | `dedupe.read_prior_feedback`, `output_layer.build_plan` |

**Valid when**: each of the nine carries all four fields. A4, A6 and A7 additionally carry
the sentence the run prints to the pull request, because "silence is a defect" is the
project's own rule and a reader needs to recognise the message.

---

## 6. Capability Entry

One row of the *What it does* part. Two sub-kinds.

**Finding routing** — one per finding kind:

| Field | Content |
|---|---|
| `kind` | false coverage claim · possible contradiction · code issue (by severity) · checklist violation · appears addressed · not addressed |
| `inline` | Under what conditions — **both** of them (C15) |
| `summary` | Always / when not inline / never |
| `blocking` | Only with `FAIL_ON_CONTRADICTION=true`, and for which kinds |
| `identity` | The key that makes it recognisable next run |

**Exit code** — one per code:

| Field | Content |
|---|---|
| `code` | 0 / 1 / 2 (and 3, defined and never returned — C10) |
| `means` | What happened |
| `do` | What a person should do about it |

**Source**: the README's routing and exit tables are correct except for the identity
condition (C15) and carry the *why* for 0 covering two outcomes — transcribe, add the
missing column. `identity` is new material from `parser.checklist_key`,
`parser.criterion_key`, `parser.code_issue_key`.

**Valid when**: `not_addressed` reads "never, under any condition", and the row names
`tests/contract/test_routing_not_addressed.py`.

---

## 7. Limit Entry

One row of the same part, stating something the tool does not do (FR-015).

| Field | Content |
|---|---|
| `limit` | The boundary, stated plainly |
| `value` | Where it is numeric |
| `consequence` | What a user sees when it bites |

**The set, with values read at `33535f0`**: `REVIEW_MAX_FILES` 40 · `REVIEW_MAX_DIFF_LINES`
3000 · `LLM_MAX_CHUNK_LINES` 1200 · `CHECKLIST_MAX_CHARS` 60000 · excluded files are never
sent · no run report is written (gap G2) · no severity threshold exists (gap G3) · exit 3
never returned (C10) · reasons over diff text and cannot observe running behaviour · a
second live posting run has never been observed (G-D).

**Valid when**: every numeric limit states the setting that changes it, and every open gap
is attributed to its gap number rather than presented as a mystery.

---

## 8. Run Step

One numbered step of the *Run it by hand* part.

| Field | Content | Required |
|---|---|---|
| `n` | Position | yes |
| `action` | What the operator is doing, in words |
| `command` | Exactly as typed, PowerShell (D7) | where there is one |
| `success` | The output that means it worked | yes |
| `symptom` | What failure looks like | yes |
| `fix` | What to do about that symptom | yes |
| `marker` | `[executed]` / `[unobserved]` (D5) | yes |

**Valid when**: no step has `success` without `symptom`. A step that can only succeed is a
step nobody needed.

**The blocking corrections have a home here, by requirement**: C7 in step 1 (where you
stand), C13 and C12 in the configuration step, C3 at the posting step, C2 in the
install-check step. FR-019 is the rule — at the step, not in an appendix.

---

## 9. Verification Record

One instance, at the end of `guide.md`. Also the shape of this feature's own honesty.

| Field | Content |
|---|---|
| `commit` | What the document was verified against |
| `date` | When |
| `environment` | Platform, Python, pytest |
| `executed` | Commands run, with their results |
| `read` | Claims taken from code without exercising them |
| `unobserved` | Each with **the observation that would close it** (D5) |

**Valid when**: `unobserved` is non-empty. On today's evidence it has at least three
members (C3's two-token case, C12's 404, and G-D's second posting run); a record claiming
none would mean the author verified a live posting run, and that would be worth saying
loudly rather than silently.

---

## 10. Correction Record

One row of a short register inside `guide.md`, and the justification for each edit outside
this feature's directory.

| Field | Content |
|---|---|
| `id` | `C1`-`C15` — the same numbering as plan and research |
| `document` | Which one was wrong |
| `claimed` / `actual` | Both, in the document's own words where short |
| `evidence` | Anchor or executed command |
| `applied` | Whether this feature edited that document, or only recorded it |

**Valid when**: every row where `applied` is true has a corresponding edit in
`review_agent/README.md`, `CLAUDE.md`, or `specs/001-.../quickstart.md`, and no row edits
anything under `review_agent/*.py` or `tests/`.

---

## Relationships

```
Documentation Reference
├── part 1  Run it by hand      -> Run Step        (n)   -> Verification Record
├── part 2  What it does        -> Capability Entry (n)
│                               -> Limit Entry      (n)
├── part 3  Where things live   -> Structure Entry  (n)  -> Test Group (n)
├── part 4  How a review flows  -> Flow Stage       (n)  -> Alternate Path (n)
└── appendix                    -> Correction Record (15)
```

Two cross-cutting rules apply to every entity above:

1. **Anchored** — a claim a reader might act on carries `module.symbol` (D3).
2. **Marked** — a claim a reader might act on carries `[executed]`, `[read]` or
   `[unobserved]` (D5).

Everything else in this data model is a convenience. Those two are what make the document
different from the seven that preceded it.
