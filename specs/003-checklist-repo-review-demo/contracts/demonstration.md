# Contract: The Demonstration

**Feature**: [../spec.md](../spec.md) | **Delivered as**: `specs/003-checklist-repo-review-demo/demo.md`

The acceptance surface for the deliverable. A section missing, or present without its
required content, is a failed contract.

Feature 002 delivered `walkthrough.md` for the markdown path against a real pull request.
This document does not replace it: it covers the document path, the story path, and the
second run, and links to 002 for anything it does not repeat.

---

## 1. Required sections, in execution order

| # | Section | Must contain | Satisfies |
|---|---|---|---|
| 1 | **What this demonstrates** | The three things proven: spreadsheet and Word rules applied, linked story judged, a second run adding nothing. That the agent is a reviewer aid, not a merge gate. The per-step time budget, summing under 45 minutes | SC-005 |
| 2 | **Before you start** | Every required variable; `TFS_API_VERSION=5.0`; that `TFS_PAT` needs **Work Items (read)** as well as Code; the outstanding `.env` corrections; one command that confirms all of it at once | FR-030, R10 |
| 3 | **Which copy of the agent will run** | That the default entry point re-fetches the agent's logic from its own repository, so this feature's code must be pushed first **or** `--local` used; which this demonstration uses and why | R10 |
| 4 | **What leaves your network** | That source code, work-item content and checklist rule text are sent to an external analysis service, stated before anything is created | — |
| 5 | **The sample checklist documents** | The generator command; what each document contains; that one spreadsheet deliberately has an empty identifier column; where to put them in the checklist repository | FR-031 |
| 6 | **The sample work item** | Title, description, acceptance criteria verbatim; which criterion the change satisfies, which it contradicts, which lies outside its scope | FR-032 |
| 7 | **The sample change** | Where the example files are; every fault labelled with the rule identifier or criterion number it should trip | FR-033 |
| 8 | **Run it self-contained** | The command; that it needs no server and no credential; the observed output | FR-037, SC-006 |
| 9 | **Create the pull request** | Branch, commit, open, link — in order; that the work-item link is required and what its absence costs | FR-034 |
| 10 | **Preview the review** | The exact command; the expected exit status; the checkpoint of §3 below | FR-034, FR-035 |
| 11 | **What you should see** | The expected-results reference (§2 below) | FR-033, FR-038 |
| 12 | **Post the review** | The exact command; which comments land on which file and line; that exactly one summary is expected | FR-034 |
| 13 | **Run it again** | The repeat run as a required step; that it must add no comment; how to confirm from `suppressed` | FR-034, SC-007 |
| 14 | **Add a document, re-run** | Generating a third document and re-running with no configuration change | SC-010 |
| 15 | **When it does not match** | Symptom reference, including the four distinguishable checklist misconfigurations | US4 |
| 16 | **Clean up** | Teardown of remote and local artifacts; this run's naming scheme; explicit merge prohibition | FR-036 |
| 17 | **Provenance** | Date verified; agent commit; and for **every** observed result, whether it came from the self-contained run or the live run | FR-037 |

## 2. Expected-results format

One row per deliberate fault. Every column is mandatory.

| Column | Content |
|---|---|
| Fault | The planted defect, and the file and line it sits on |
| Trips | The rule identifier, or the criterion number |
| Finding kind | `checklist` / `coverage` / `false-coverage` / `code` |
| Appears | `inline at <file>:<line>` or `summary only`, with the reason it is one and not the other |
| Availability | `present` / `expected-absent — <reason>` |
| Observed in | `self-contained` / `live` / `both` |

**The Availability column is the whole point.** A finding the demonstration expects but
that today's agent cannot produce is recorded as `expected-absent` with its reason
(FR-038). Omitting it silently is the failure mode this project has already had once:
002's walkthrough was written against a checklist path that resolved nothing, and the
absence read as "no violations found".

**Coverage requirement**: the table must include at least one rule taken from a
spreadsheet, at least one from a Word document, one criterion the change satisfies, one it
contradicts, one outside its scope, and at least one finding that is summary-only. A
`possible_contradiction` coverage entry is routed with `path=""` (`output_layer.py:123`)
and so is **always** summary-only — that is the reliable way to exercise the distinction,
since there is no severity threshold.

## 3. The checkpoint

Before posting, the operator confirms all five. Each is answerable from the preview's own
inventory block; none requires reading code:

1. A checklist repository was obtained, and the reference it was read at is stated.
2. At least one `.xlsx` and one `.docx` are listed as `read` with a rule count.
3. Every document found is accounted for — a count or a reason, none passed over.
4. The linked work item is listed, with the number of criteria judged.
5. At least one finding cites a rule identifier and a document filename.

**If any fails, the run is not the review it appears to be.** A review against an empty
checklist prints a clean-looking summary; this checkpoint is what makes that
distinguishable, and it exists because the project has already mistaken one for the other.

## 4. Execution protocol and evidence

Two executions, distinct jobs (clarification Q2).

### Self-contained — proves, repeatably, with no server

| Evidence | How captured |
|---|---|
| Rules extracted from both formats | document inventory, rule counts per document |
| Per-document outcome for every file | inventory block, including a deliberately corrupt document |
| Every acceptance criterion judged | coverage table, one row per criterion |
| Every degradation statement | one run per condition in US4, output captured |
| Determinism (SC-006) | the run performed twice from a clean checkout, finding sets compared |

### Live — proves what fixtures cannot

| Evidence | How captured |
|---|---|
| Working copy obtained from the real repository | inventory naming repository, reference, commit |
| Work item read with a correctly scoped credential | criteria count > 0 |
| Story coverage lost with a Code-only credential | one run with the narrower token; the statement it produces |
| Comments posted | the pull request; comment count by file and line |
| **Second run suppresses** | `suppressed` equals the first run's `inline`; **zero** comments added |

The second-run row is the one that closes the defect in `CLAUDE.md`, and per
[finding-identity.md](./finding-identity.md) §"How this is verified" it is **not**
satisfied by a unit test.

### Redaction gate

Before the document is considered delivered, it is scanned for: token values, the real
collection host, real project or repository identifiers beyond those already public in this
repository, and real work-item content. The live run's output contains all of these and is
the tempting thing to paste. This is a task-level gate, not a review-time suggestion.

## 5. Repeatability

- Every artifact this demonstration creates carries a run tag — the branch, the work item
  title, and the pull request title all end in the same suffix — so two runs never collide,
  and 002's artifacts are never touched.
- The cleanup section removes remote artifacts and local artifacts, and names the merge
  prohibition explicitly.
- The self-contained run creates nothing outside a temp directory and needs no cleanup;
  the document says so, so an operator does not go looking.
