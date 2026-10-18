# Research: Local-Mode Call Flow Diagram and Developer Onboarding Guide

**Feature**: `005-agent-flow-developer-guide` | **Date**: 2026-09-17 | **Commit**: `1aab763`

Phase 0 output. Ten decisions (**D1–D10**) and twenty-one pieces of evidence (**E1–E21**);
**E19–E21 and the superseding note on D3 were added at implementation**, where rendering the
diagram closed a gate that planning had expected to leave open.
Every item is marked `[executed]` — observed by running something on 2026-09-17 — or
`[read]` — established from the source only. Nothing here is asserted from memory of how
such tools usually work.

No NEEDS CLARIFICATION entered Phase 0. The spec's three ambiguities were resolved into
Assumptions before planning began.

---

## Decisions

### D1 — The diagram and the walkthrough are both rendered from one Flow Ledger

**Decision**: The twelve-stage Flow Ledger in [plan.md](./plan.md#flow-ledger) is the single
description. The `.puml` and the guide's walkthrough are two renderings of it. A change to
one is a change to the Ledger, and therefore to both.

**Rationale**: This project has already paid for the alternative. Feature 004's survey found
**fifteen** disagreements across seven documents describing the same system, three of them
severe enough to stop a first manual run. Two documents describing the same flow, authored
independently, is that failure mode in miniature — and the diagram is the one a reader trusts
most, because a picture looks authoritative in a way a paragraph does not.

**Alternatives considered**: *Author each independently and reconcile at review* — rejected;
reconciliation is exactly what 004 had to do retroactively, at a cost of a whole feature.
*Generate the `.puml` from the guide with a script* — rejected; a generator is code, and this
feature writes none (FR-034). The Ledger is a table a human keeps in step, which is enough at
twelve rows.

---

### D2 — PlantUML **new** activity syntax (`start` / `:action;` / `if…then…else` / `stop`)

**Decision**: Use the modern activity-beta syntax, not the legacy `(*) --> "action"` form.

**Rationale**: Two reasons, and the second is decisive. First, the modern syntax supports
swimlanes, notes and grouped partitions, which is how a twelve-stage flow stays legible
(FR-008). Second — **the legacy activity syntax requires Graphviz, and the modern one does
not**. `dot` is **absent** on this machine (**E4**), so a diagram written in the legacy form
could not be rendered by any reader who is set up the way this repository's own machine is.

**Alternatives considered**: *A sequence diagram* — rejected; the request says "activity
diagram", and sequence notation handles the fourteen decision points badly. *Mermaid* —
rejected; the request names PlantUML, and Mermaid's flowchart would be a different artefact
than the one asked for.

---

### D3 — Rendering is verified by structure, and — as it turned out — by rendering

**Decision as planned**: FR-002 and SC-003 discharged in two parts. (a) The `.puml` carries a
**structural self-check** the author performs and records. (b) The guide states the exact
render command. **Actual rendering marked `[unobserved]`** until someone runs it.

**Rationale as planned**: no renderer appeared to be available. Java 8 is present (**E3**) but
there was no `plantuml.jar`; the `plantuml` Python package is installed but it is a **client
that posts to a remote PlantUML server** (**E5**), so using it would send the diagram — and
with it this repository's module names and flow — to a third party. That is not a call to make
silently in a project whose fifth principle is that nothing escapes.

> **Superseded at implementation, 2026-09-17.** The planned fallback — fetch `plantuml.jar`,
> listed under Alternatives below as "the right move if the implementer has network access" —
> **succeeded**. The jar was downloaded to the scratchpad and the diagram rendered locally with
> `java -jar plantuml.jar -tsvg`. **G4 is closed as `[executed]`, not `[unobserved]`.** The
> structural self-check was kept and still runs: it is cheaper than a render and catches the
> same class of error. Nothing was sent to a remote server.
>
> Rendering it also found **two defects that the structural check alone would not have**, both
> now fixed:
>
> - PlantUML's creole read `--local --pr` in the title as strikethrough markup. Each `--` is
>   now escaped with a leading `~`.
> - The diagram is ~4180 px tall and **PlantUML's PNG writer silently truncates at 4096**,
>   losing the last two stages and the legend with no warning. The render instruction is now
>   `-tsvg`, and the reason is stated in the guide and in the `.puml` header (**005-C2**).
>
> This is the case *for* rendering rather than reasoning, made by the thing itself: a diagram
> that passed every structural check was still wrong in two visible ways.

**Alternatives considered**: *Fetch `plantuml.jar`* — taken, see above. *Use the Python
client* — rejected on the egress point; still rejected. *Claim it renders* — rejected
outright; this is precisely the "closed by reasoning alone" error that cost feature 001 its
gap-G4 claim.

---

### D4 — Local mode is the spine; the fetched path is one decision at stage 0

**Decision**: The diagram's main path is `python -m review_agent --local --pr <id>`. The
default fetched path appears as the first decision, rejoining at stage 1.

**Rationale**: The difference between them is genuinely one stage — `bootstrap.main` either
re-executes the review inside a fetched clone or calls `run.main` directly, and from stage 1
onward the two are the same code. Drawing both as full paths would double the diagram to show
nothing new. Drawing only the local path would leave a reader who runs the default command
unable to match their output to the picture.

**Alternatives considered**: *Two diagrams* — rejected under the spec's Assumption that one
diagram is the deliverable. *Omit the fetched path* — rejected; FR-006 requires it, and a
reader whose first run is the default would conclude the diagram is wrong.

---

### D5 — The file inventory is cut by call-flow position, and cites 004 for purposes

**Decision**: US3's structure section lists every shipped path grouped by **the stage it
serves**, with files that serve no stage in a final group. The one-line purpose for each
module is **cited to** 004's `guide.md` Part 3 rather than rewritten.

**Rationale**: 004 already has a correct alphabetical inventory. A second alphabetical
inventory is the duplication FR-032 forbids, and two lists that must agree will eventually
not. Re-cutting by flow position adds the thing 004 does not have — *where in a review does
this file get used* — which is what a developer about to change something actually asks.

**Alternatives considered**: *Copy 004's table and extend it with a stage column* — rejected;
copying is what creates the second source of truth. A cited reference does not drift.

---

### D6 — The context boundary is documented by description, never by a pasted prompt

**Decision**: US4 explains what the model receives by describing each section of the assembled
prompt and quoting only the **fixed instructional text** (`SYSTEM_ROLE`, the chunk warning).
No assembled prompt from a real run is reproduced.

**Rationale**: This is where the fifth principle was nearly lost. The natural, most convincing
way to answer "what can it see" is to paste one real prompt — which would carry a project
identifier, a branch name, a story's contents and an excerpt of the team's checklist out of the
repository and into a document made for circulation. The offline demo's fixtures are the safe
substitute where an example is genuinely needed.

**Alternatives considered**: *Paste a demo-run prompt* — acceptable in principle since the
demo's inputs are synthetic, and left available to the implementer for a single illustrative
excerpt; but the default is description, so the habit does not transfer to a real run.

---

### D7 — The three unobservable failure rows stay `[read]`, with a stated closing condition

**Decision**: **B3.3**, **B3.4** and **B3.6** are marked `[read]` in the deliverable, with the
observation that would close each one written next to it:

- **B3.3 / B3.4** close when one live run sends a request the provider rejects as too large
  and the run is seen to print `phase=llm outcome=degraded`, post the notice, and exit `0`
  with the findings of any earlier chunk absent.
- **B3.6** closes when one live run receives a truncated answer and is seen to retry exactly
  once before degrading.

**Rationale**: The project's most expensive documentation error to date — gap G4 — was a claim
closed by reasoning about a function's inputs without running it twice. The repair contract
for it (`003/contracts/finding-identity.md`) refuses to consider the fix closed until a live
run is observed. A feature whose subject is "what happens when things go wrong" cannot adopt a
weaker standard than the project already applies elsewhere.

**Alternatives considered**: *Simulate the rejection with a stub provider* — this would prove
the code path, and is worth doing; but it proves what the code does when handed a 400, not
that a real provider returns 400 for an oversized request. The distinction is recorded so a
later reader is not misled about which was shown.

---

### D8 — Size limits are documented as an ordered pipeline, not a list of settings

**Decision**: US5 presents the six reductions in **application order** with what each one
bounds and where it is reported, rather than as an alphabetical table of environment
variables.

**Rationale**: The order is the load-bearing fact and the one a settings table destroys.
Exclusions run before ranking, so an excluded file never competes for the bound; ranking runs
before the bound, so *which* files survive is determined by relevance and not by the order the
server returned them; the rule budget applies to a corpus already narrowed against the files
that survived. A reader given only names and defaults cannot predict any of that.

**Alternatives considered**: *Document each setting where it is configured* — rejected; that
is 004's Part 3 table, which already exists and is the thing this section must add to.

---

### D9 — "Reported, not dropped" is stated once and then shown per reduction

**Decision**: Every reduction row names the exact output that reveals it — the
`### Not sent for review` table, a `RunInventory.reductions` line, or the `chunks=N` count.

**Rationale**: The project's seventh reconstructed principle is *every skipped or degraded
outcome carries a stated reason; silence is a defect*, and `RunInventory.reductions` derives
its list from the fields rather than accepting one from a caller, precisely so a new way to
cover less cannot be added without surfacing. A document that says "some files may not be
reviewed" without showing where that appears leaves a reader unable to tell a bound from a
bug.

**Alternatives considered**: *One general statement that nothing is silent* — rejected as
unfalsifiable by a reader, which is the property FR-030 exists to prevent.

---

### D10 — `CLAUDE.md` gets one pointer line and no rewrite

**Decision**: Promote 005 to the active-feature block inside the existing SPECKIT markers and
demote 004 to a prior-feature entry. Correct the one stale line found (**E18**). Do not
restructure anything else, and do not revise 004's substantive entries.

**Rationale**: `CLAUDE.md` is read at the start of every session, so churn there is expensive
and a stale line costs more than anywhere else — which is also why the one stale line found
is corrected rather than left for a sixth feature to trip over. 004 corrected this file in
four places as part of its own Correction Register; beyond **E18** nothing else here
disagrees with the code, so there is no licence to tidy further.

**The correction (005-C1)**: the active-feature block described
`specs/004-agent-docs-runbook/guide.md` as "not yet written". It **is** written — 623 lines,
four parts, with its own Verification Record. Left alone, this line would have sent the next
reader to write 004's deliverable a second time, which is the precise duplication FR-032
exists to prevent. Recorded here rather than silently overwritten, per FR-033.

---

## Evidence

| # | Evidence | How |
|---|---|---|
| **E1** | `python -m pytest tests` → **532 passed in 7.64s** | `[executed]` 2026-09-17. Confirms CLAUDE.md's count and G1's baseline |
| **E2** | `python -m tests.demo.run` produces eight phase lines beginning at `pullrequest`, then a full dry-run summary | `[executed]`. Source of every log line quoted in the Ledger, and of the `### Not sent for review` and inventory renderings |
| **E3** | `java -version` → `1.8.0_461` | `[executed]` |
| **E4** | `dot -V` → not found; no `plantuml` on PATH; no `.puml` existed anywhere in the repository | `[executed]`. Drives **D2**. Graphviz is still absent, which is why the modern activity syntax was required — the render at **E19** confirms it renders without it |
| **E5** | The `plantuml` Python package imports, and is a client for a remote render server — so it was **not** used | `[executed]` import; `[read]` for what it does |
| **E6** | `diff_builder.py:14` — `CONTEXT_LINES = 3`, passed as `n=` to `difflib.unified_diff` | `[read]` |
| **E7** | `build_change_set` sets `before = ""` for `change_type == "add"` | `[read]` |
| **E8** | `build_change_set` iterates `changeEntries` only; no other path retrieves file content for review | `[read]` |
| **E9** | Both blobs are fetched via `client.get_file_content`; only `ChangedFile.diff` is rendered by `prompt_builder._diff_section` | `[read]` |
| **E10** | `grep -rn estimated_size` over the repository returns **one** line — its own definition at `prompt_builder.py:192` | `[executed]`. The anchor for **B3.1** |
| **E11** | `build_prompts` re-emits `story`, `scope` and `rules_block` inside the per-chunk loop | `[read]`. The anchor for **B3.2** |
| **E12** | In `run_review`, `except DegradedReview` encloses the entire `for prompt in prompts` loop; `results` is discarded on the exception | `[read]`. The anchor for **B3.3** |
| **E13** | `llm_adapter._request_for` sets `max_tokens: DEFAULT_MAX_TOKENS` (4096) in the **claude** branch only; the openai/azure and ollama bodies set no answer cap | `[read]`. The anchor for **B3.5** |
| **E14** | `parse_with_retry` loops `for attempt in (1, 2)` — one stricter retry, then `DegradedReview` | `[read]` |
| **E15** | `call_llm`: `RETRY_STATUSES = (429, 500, 502, 503, 504)`, 3 attempts, backoff `(1, 2, 4)`, `Retry-After` capped at 30 s; 401/403 and 404 raise `SetupFailure` | `[read]` |
| **E16** | Defaults: `checklist_max_chars=60000` (`config.py:233`), `review_max_files=40`, `review_max_diff_lines=3000`, `llm_max_chunk_lines=1200` (`config.py:245-247`) | `[read]` |
| **E17** | `output_layer.render_summary` emits `### Not sent for review` from `report.skipped + report.unreviewed`, each with reason and detail, above a `N of M changed files` headline | `[read]`, rendering `[executed]` via E2 |
| **E18** | `CLAUDE.md` re-read on 2026-09-17. **One stale line found** (`005-C1`): it called 004's `guide.md` "not yet written"; the file exists at 623 lines with four parts and a Verification Record. Corrected during Phase 1. No other disagreement beyond the four 004 already fixed | `[executed]` — `wc -l` and a heading listing of the file. Drives **D10** |

| **E19** | *(added at implementation)* `plantuml.jar` v1.2024.7 fetched to the scratchpad; `java -jar plantuml.jar -tsvg docs/local-mode-pr-review-activity.puml` → **renders clean, no errors**, 858 × 4179, full content including the final exit node and the legend. Graphviz absent throughout | `[executed]` 2026-09-17. **Closes G4.** Supersedes **D3**'s planned `[unobserved]` |
| **E20** | *(added at implementation)* Rendering to PNG at PlantUML's defaults truncates at 4096 px, silently. Confirmed by comparing default output (857 × 4096) against `-DPLANTUML_LIMIT_SIZE=16384` (857 × 4178) | `[executed]`. Correction **005-C2** |
| **E21** | *(added at implementation)* 93 `file.method` references extracted from `docs/developer-guide.md` and checked against the tree; all resolve. 14 referenced repository paths all exist | `[executed]`. Gate **G3** |

---

## What this research did **not** establish

Stated so a later reader does not mistake absence for confirmation.

- ~~**That the `.puml` renders.**~~ **Superseded** — it was rendered at implementation
  (**E19**). G4 is closed.
- **That a provider rejects an oversized request with a 4xx that reaches `call_llm`'s
  `>= 400` branch.** Only the handling of such a status was read (**D7**). Still open.
- **That the fetched (non-`--local`) path behaves as the Ledger's stage 0 describes.** It was
  read, not executed; running it needs a reachable agent repository.
- **Anything about a live server.** No network call was made during planning. Every executed
  observation came from the test suite or the offline demo.
