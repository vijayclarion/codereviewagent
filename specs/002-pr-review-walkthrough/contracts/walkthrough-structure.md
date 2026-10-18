# Contract: Walkthrough Structure

**Feature**: [../spec.md](../spec.md) | **Delivered as**: `specs/002-pr-review-walkthrough/walkthrough.md`

The acceptance surface for the deliverable. A section missing, or present without its required content, is a failed contract — the same way a missing flag fails the CLI contract in feature 001.

Sections appear in this order, because the order is the execution order. A reader who works top to bottom has done the walkthrough.

## Required sections

| # | Section | Must contain | Satisfies |
|---|---|---|---|
| 1 | **What this is** | What the walkthrough demonstrates; that the agent is a reviewer aid, not a merge gate; the time to budget | SC-001 |
| 2 | **Before you start** | Access needed on the sample repository and on work items; local tooling; the full required-variable set; the outstanding `.env` corrections; a single command that confirms all of it at once | FR-004, FR-005 |
| 3 | **What leaves your network** | That source code and work-item content are sent to an external analysis service, stated before anything is created | FR-006 |
| 4 | **The sample work item** | Title, description and acceptance criteria verbatim; which criterion is left unimplemented and why; which is contradicted and why | FR-007, FR-008 |
| 5 | **The sample change** | Where the example files are; what each fault is; the fault-to-finding table | FR-009, FR-009a, FR-010 |
| 6 | **Create the pull request** | Branch, commit, open, link — in order; the screen and control for each web step; what success looks like at each step; that the work-item link is required and what its absence costs | FR-015, FR-016, FR-017, FR-018 |
| 7 | **Preview the review** | The exact command; what the output confirms; the expected exit status; the checkpoint list | FR-019, FR-022, FR-023 |
| 8 | **What you should see** | The expected-results reference | FR-021, FR-026 |
| 9 | **Post the review** | The exact command; what becomes visible to others; where to look in the pull request; that exactly one summary comment is expected | FR-020, FR-025 |
| 10 | **Run it again** | The repeat run as a required step; that it must add no comments; how to confirm | FR-024 |
| 11 | **When it does not match** | The symptom reference | FR-027, FR-028 |
| 12 | **Clean up** | Teardown for remote and local artifacts; explicit merge prohibition | FR-029, FR-030 |
| 13 | **Provenance** | Date last verified; agent version; where each quoted command and message comes from | FR-032, FR-033 |

## Placement rules

Order is not cosmetic here. Three constraints are load-bearing:

- **Section 3 precedes section 4.** The reader is told what leaves the network before they create the first artifact, not after (FR-006).
- **Section 7 precedes section 9.** Preview precedes posting, always. Posting is visible to the team and awkward to retract (FR-019).
- **Section 2's confirmation precedes every remote call.** The prerequisite check costs nothing and reports every missing setting at once; it runs before anything spends an analysis call (FR-005).

## Content rules

Each is checkable against the finished document.

| Rule | Requirement | How it fails |
|---|---|---|
| No secret, real host, real project or repository name, real identifier | FR-031 | Copy-paste from the verification run's output. The most likely defect in this document |
| Placeholders visibly distinguishable from literal values | FR-031 | A reader types `<your-pr-id>` literally, or worse, treats a real leftover value as a placeholder |
| Example files referenced, never restated | FR-009b | Two copies of the faulty code drift; the reader trips the wrong fault |
| No checkpoint the reader cannot satisfy | FR-026a | 001's Part 2 currently fails this — it asks for a run report nothing writes |
| No behaviour described that the agent does not have | FR-035, FR-036 | The severity-threshold trap: it does not exist (see the routing table in `expected-results.md`) |
| Operator setup referenced, not restated | FR-003 | Two sources of truth for installation; they drift |
| Every quoted command, message and exit status attributable | FR-032 | The agent changes and nobody can tell what in the document went stale |

## Discoverability

Reachable by a link from both (FR-002):

- `CLAUDE.md` — the project's context file
- `review_agent/README.md` — the agent's own documentation

And, per clarification Q5, `specs/001-pr-code-review-agent/quickstart.md` Part 2 is replaced by a pointer to this document. Part 1 stays where it is and remains the authority on operator setup (FR-003a).

## Quoted-value sources

Section 13 makes each of these traceable. They are the values most likely to go stale, with where they come from:

| Quoted in the walkthrough | Defined at |
|---|---|
| `--dry-run`, `--post`, `--pr`, `--local`, `--quiet`, `--version` | `review_agent/main.py:286-303` |
| Exit statuses `0`, `1`, `2` | `review_agent/main.py:334-356`; `review_agent/errors.py:19-21` |
| Required configuration variables | `review_agent/config.py:313-395` |
| `configuration is incomplete or invalid: …` | `review_agent/config.py` validation accumulator |
| The checklist-source warning | `review_agent/main.py:153` |
| Comment body shapes and the automated-comment footer | `review_agent/output_layer.py:87-137`, `:39` |

**There is no `--inline-threshold` and no `--report-dir`.** Feature 001's `contracts/cli.md` marks both 🆕 as planned; neither exists in `build_parser`. The walkthrough must not quote them.
