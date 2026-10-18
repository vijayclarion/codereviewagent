# Implementer Quickstart: 005 — Flow Diagram and Developer Guide

**Feature**: `005-agent-flow-developer-guide` | **Date**: 2026-09-17 | **Branch**:
`005-agent-flow-developer-guide`

For whoever picks this up. Read this, then [plan.md](./plan.md). Everything else is reference.

---

## In one paragraph

Write two files into `docs/`: a PlantUML activity diagram of the local-mode review flow, and a
companion document that walks the same flow method by method and answers three questions the
project has never answered — what the reviewer can see, what happens to a huge change, and
what happens when a model limit is exceeded. **No agent code. No test changes.** The research
is done; most of the remaining work is writing.

---

## Read in this order

1. **[plan.md](./plan.md)** — the [Flow Ledger](./plan.md#flow-ledger) (twelve stages), the
   [Boundary Register](./plan.md#boundary-register) (the three answers, with anchors), and the
   [Delegation Map](./plan.md#delegation-map) (what to link instead of writing).
2. **[contracts/diagram-contract.md](./contracts/diagram-contract.md)** and
   **[contracts/guide-contract.md](./contracts/guide-contract.md)** — the clause lists both
   deliverables are checked against.
3. **[research.md](./research.md)** — only when you want to know *why* a decision went the way
   it did. D2, D3, D6 and D7 are the ones that will bite if ignored.
4. **[data-model.md](./data-model.md)** — the field lists for each row type.
5. `specs/004-agent-docs-runbook/guide.md` — the incumbent. **Read Parts 3 and 4 before
   writing anything**, or you will rewrite them.

---

## Five things that will cost you a day each

1. **Do not re-document 004.** Its `guide.md` already has the runbook, comment routing, exit
   codes, a file inventory and a stage table. The Delegation Map says *link* more often than
   *write*. Check it before every paragraph.
2. **Do not author the diagram and the prose separately.** Both render the Flow Ledger
   (**D1**). Edit the Ledger, then both. Two independent authorings is the exact failure 004
   spent a feature repairing across seven documents.
3. **Use the modern PlantUML activity syntax** — `start` / `:action;` / `if…endif` / `stop`.
   The legacy `(*) -->` form needs Graphviz, and `dot` is **not installed here** (**E4**). A
   diagram no one on this machine can render is not a deliverable.
4. **Do not claim the diagram renders.** No renderer is available offline (**D3**). Run the
   structural self-check in the diagram contract and record rendering as `[unobserved]` with
   its closing condition. If you have network and can fetch `plantuml.jar`, render it and close
   G4 properly — that is the better outcome, just do not skip the distinction.
5. **Do not paste a real prompt** to explain the context boundary (**D6**). It would carry a
   project identifier, a branch name, a story and a checklist excerpt out of the repository.
   Describe the sections; quote only the fixed instructional text.

---

## Facts you will need, already verified

Do not re-derive these. Anchors are in the [Boundary Register](./plan.md#boundary-register).

| | |
|---|---|
| Diff context width | **3 lines** each side of a hunk (`diff_builder.py:14`) |
| Added files | diff against empty → effectively the whole file is shown |
| Untouched files | never fetched, never sent |
| Fetched but withheld | **both** complete file blobs; only the diff is sent |
| Other context | linked story · PR description + declared scope · selected checklist rules |
| Size limits, in order | skip → exclude → rank → `REVIEW_MAX_FILES` **40** → `REVIEW_MAX_DIFF_LINES` **3000** → `CHECKLIST_MAX_CHARS` **60000** → `LLM_MAX_CHUNK_LINES` **1200** |
| Nothing is dropped silently | `### Not sent for review` table + `RunInventory.reductions` |
| Token accounting | **none exists.** `prompt_builder.estimated_size` is called from nowhere |
| Chunk overhead | story, scope and rules repeat in **every** chunk |
| Provider rejection | degrades the **whole run**, discards parsed chunks, **exit 0** |
| Answer cap | 4096 tokens, **claude only** |
| Truncated answer | invalid JSON → **one** stricter retry → degraded |
| Retried statuses | 429, 500, 502, 503, 504 — 3 attempts, backoff 1/2/4 s. 401/403/404 → exit **2** |

---

## Commands

```bash
# The suite. NOT -q: pytest.ini already sets it, and a second -q prints nothing.
python -m pytest tests                  # expect: 532 passed

# The offline demo — every log line and rendered summary you quote comes from here.
python -m tests.demo.run                # no server, no provider, no credentials

# Prove FR-034 held.
git status --short                      # nothing under review_agent/ or tests/
```

---

## Definition of done

The seven acceptance clauses in
[contracts/guide-contract.md](./contracts/guide-contract.md#acceptance), plus:

- `docs/local-mode-pr-review-activity.puml` and `docs/developer-guide.md` both exist.
- Sections 4, 5 and 6 of the guide each answer their question **in the first sentence**.
- Every `[unobserved]` claim carries a closing condition.
- `CLAUDE.md` has one added pointer line inside the SPECKIT markers, and nothing else changed.

---

## What is deliberately not in scope

- **Changing the agent.** If the context boundary turns out to be too narrow for what your team
  wants, that is a separate feature. This one makes the current boundary visible so that
  decision can be taken deliberately (spec Assumption).
- **A second diagram.** Overflow detail goes to the guide.
- **A committed rendered image.** It would go stale invisibly; the source is the deliverable.
- **Fixing the demo files.** `specs/003-.../demo-files/` contains a deliberately unreadable
  document. It is meant to be unreadable.
