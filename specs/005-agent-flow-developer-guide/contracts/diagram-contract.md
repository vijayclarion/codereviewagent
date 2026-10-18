# Contract: `docs/local-mode-pr-review-activity.puml`

**Feature**: `005-agent-flow-developer-guide` | **Date**: 2026-09-17
**Satisfies**: FR-001 – FR-008, FR-029 | **Verified by**: gate G4, plus the structural
self-check below

The diagram is the deliverable a reader meets first and trusts most. This contract states
what it must contain, what it must not, and how each clause is checked. Planning expected
"it renders" to be unavailable as a check here; it turned out not to be, and the diagram was
rendered — see the superseding note on **D3**.

---

## C1 — File and format

| Clause | Requirement |
|---|---|
| **C1.1** | Path is exactly `docs/local-mode-pr-review-activity.puml` |
| **C1.2** | Opens with `@startuml` and closes with `@enduml`, one pair, nothing outside them |
| **C1.3** | Uses the **modern activity syntax** — `start`, `:action;`, `if (…) then (…)`, `else`, `endif`, `stop`. The legacy `(*) --> "…"` form is **forbidden**: it requires Graphviz, which is absent here (**D2**, **E4**) |
| **C1.4** | No `!include`, no remote `!theme`, no network reference of any kind. The file renders from itself alone |
| **C1.5** | Plain ASCII except where a quoted log line requires otherwise. The console this project targets is cp1252 (`config.prepare_console` exists for that reason) |

## C2 — Content

| Clause | Requirement | Source |
|---|---|---|
| **C2.1** | All **twelve** Ledger stages appear, exactly once each, in execution order | FR-003 |
| **C2.2** | Every stage node names its **owning file**, readable from the diagram alone | FR-004 |
| **C2.3** | All **fourteen** decision points appear as `if`/`else` (or `switch`) constructs | FR-005 |
| **C2.4** | Every branch is **labelled** and reaches `stop`, `end`, or a named stage. No unterminated edge | FR-005 |
| **C2.5** | Stage 0 shows the entry-point fork — `--local`, already-bootstrapped, and fetch — and shows where the paths rejoin at stage 1 | FR-006 |
| **C2.6** | The reductions at stages 6, 7 and 9 are visible as flow, not as a note: files leave the path at exclusion and at the bound, and stage 9 shows the split into *N* passes | FR-007 |
| **C2.7** | Stage 9 shows **what is assembled into the request** — diff, story, scope, rules — distinguished from what stage 6 retrieved and did not send | FR-029 |
| **C2.8** | Exit codes 0, 1 and 2 appear as distinct terminals | FR-003, FR-013 |

## C3 — Legibility

| Clause | Requirement |
|---|---|
| **C3.1** | ~~Readable on one screen at 100%.~~ **Not met, and not achievable** — see the deviation below |
| **C3.2** | No stage node text exceeds roughly 60 characters. Longer belongs in the guide |
| **C3.3** | A header note carries the exact command the diagram depicts, and a pointer to `docs/developer-guide.md` for the method-level detail | FR-008 |
| **C3.4** | Where a decision has a 004 fork identifier (`A1`–`A9`), the label carries it, so the two documents are cross-navigable | FR-032 |

## C4 — Forbidden content

| Clause | Requirement |
|---|---|
| **C4.1** | No host, collection URL, project name, repository name, pull-request id, or token — in any node, label, note or comment | FR-035 |
| **C4.2** | No invented log line. A quoted line is copied from an executed run or is absent | FR-030 |
| **C4.3** | No stage, method or branch that does not exist in the code as of the stated commit | FR-030 |

---

## Structural self-check

This check is cheaper than a render and catches the same class of error, so it was kept even
once rendering became available. Each item is mechanical: a reader with the file and no
renderer can confirm it. The result is recorded in the guide's Verification Record.

1. `@startuml` count = `@enduml` count = 1.
2. `if (` count = `endif` count. Same for `fork` / `end fork`, `split` / `end split`,
   `partition {` / `}`.
3. Every `if` has at least one `else` or an explicit `(no)` branch — an unhandled negative
   path is C2.4's failure mode.
4. Every `:action;` line terminates with `;`.
5. Count of `stop` + `end` ≥ count of distinct terminal outcomes named in C2.4 and C2.8.
6. Every stage name in the file appears in the Flow Ledger, and every Ledger stage appears in
   the file — a two-way set comparison, twelve each way.
7. `grep` for each `.env` key name's **value** returns nothing (C4.1). Performed without
   printing any value.

**Recorded outcome, 2026-09-17** — all seven items pass: `@startuml`/`@enduml` 1/1 ·
`if`/`endif` 16/16 · `note`/`end note` 2/2 · `legend`/`endlegend` 1/1 · every `if` carries a
negative branch (16 `if`, 20 `else`/`elseif`) · 13/13 stage labels present both ways · 7
terminals · no non-ASCII · no remote reference.

**Rendering is `[executed]`, not `[unobserved]`.** `plantuml.jar` proved obtainable, so the
diagram was rendered locally — see the superseding note on **D3**. It found two defects the
structural check could not: creole strikethrough in the title, and silent PNG truncation at
4096 px (**005-C2**). Both fixed; the render instruction is now `-tsvg`.

---

## Recorded deviation — C3.1

**C3.1 is not met.** The rendered diagram is 858 x 4179 px. It does not fit one screen, and
compacting it to do so was attempted and abandoned: two rounds of trimming notes and merging
nodes moved the height by under 2%, because the height is driven by twelve stages and sixteen
decisions, not by prose. Meeting C3.1 would mean dropping stages or decisions, which FR-003
and FR-005 forbid, or splitting into two diagrams, which the spec's Assumption forbids.

What was done instead, in the spirit of the clause: every note whose content the guide carries
better was removed, node text was held near the C3.2 limit, and the flow reads top-to-bottom in
one column so scrolling is the only cost. **The clause was wrong, not the diagram** — an
activity diagram of a thirteen-stage pipeline is a tall document, and a future revision of this
contract should say "legible while scrolling, one column, no horizontal pan" instead.

Recorded here rather than quietly passed, because a contract clause silently ignored is worth
less than one openly amended.

---

## Render instruction the guide must carry

The guide states, verbatim, how a reader renders it — since no committed image exists and one
would go stale invisibly:

```text
java -jar plantuml.jar -tsvg docs/local-mode-pr-review-activity.puml
```

plus three notes: that any PlantUML-capable viewer (the VS Code extension, the IntelliJ
plugin) opens it directly; that **Graphviz is not required** for this diagram's syntax — the
reason C1.3 exists, and worth telling a reader who has hit that requirement before; and that
**SVG is not optional** — the diagram is ~4180 px tall and PlantUML's PNG writer truncates at
4096 without warning, losing the last two stages and the legend.
