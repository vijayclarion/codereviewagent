# Demonstration: review a pull request against the team's checklist documents and its linked story

**Feature**: [spec.md](./spec.md) | **Contract**: [contracts/demonstration.md](./contracts/demonstration.md)
**Both halves verified 2026-09-16** — self-contained and live. See §17 for what each proved.

> **Status.** The self-contained run is in
> [demo-files/observed-selfcontained.md](./demo-files/observed-selfcontained.md); the live
> run, against the real checklist corpus and a real pull request, is in
> [demo-files/observed-live.md](./demo-files/observed-live.md). Three steps remain
> unobserved and are marked ⏳ — they are listed in §17 with the reason. Do not treat a ⏳
> row as verified; that distinction is the entire reason feature 002's checklist findings
> went missing unnoticed.

---

## 1. What this demonstrates

Three things, in one review:

1. **Spreadsheet and Word checklists are actually applied.** Not markdown — the team's
   real `.xlsx` and `.docx` documents, read into individually citable rules, each
   violation naming the rule and the document it came from.
2. **The linked user story is judged, criterion by criterion**, with the three verdicts
   kept apart: satisfied, contradicted-by-a-claim, and simply outside this change's
   scope. The third is never a defect.
3. **A second run adds nothing.** Running the review twice against an unchanged pull
   request must not repeat a single comment the reviewer has already read.

The agent is a **reviewer's aid, not a merge gate**. Preview is the default, posting is
explicit, and no exit status here blocks anything.

**Time budget** — 42 minutes, if nothing needs fixing:

| § | Step | Budget |
|---|---|---|
| 2 | Prerequisites | 8 min |
| 3–4 | Which agent runs; what leaves your network | 2 min |
| 5 | Generate and push the sample checklist documents | 5 min |
| 6–7 | Create the work item and the branch | 6 min |
| 8 | Run it self-contained | 2 min |
| 9 | Create the pull request and link the story | 4 min |
| 10–11 | Preview, and check against the expected results | 7 min |
| 12–13 | Post, then run again | 5 min |
| 16 | Clean up | 3 min |

## 2. Before you start

Work through [demo-files/preflight.md](./demo-files/preflight.md) first. It covers all
four prerequisites in one pass. The two that cost an afternoon each if missed:

- **`TFS_API_VERSION=5.0`.** The default `6.0` returns HTTP 404 on *every* endpoint, and
  the error says "check TFS_PROJECT, TFS_REPO, and TFS_PR_ID" — all three of which can be
  perfectly correct.
- **`TFS_PAT` needs Work Items (read)**, not only Code. Without it you lose the story half
  of the review. After this feature you lose it *loudly*; before it, the whole run exited 2.

**Feature 001's gap G5 is closed.** `.env` now carries `LLM_PROVIDER=claude` and a model
identifier that exists, and `load_config` succeeds against it — checked on 2026-09-16.
Two things it still does not carry, both expected:

- **`TFS_API_VERSION`** — absent, so it defaults to `6.0` and every endpoint answers 404.
  Set it to `5.0` in your shell or in `.env`.
- **`TFS_PR_ID`** — absent, so pass `--pr <ID>` on the command line. That is the normal way
  to run this by hand; the variable exists for pipelines.

`.env` is gitignored and holds live credentials. No task in this feature touches it.

## 3. Which copy of the agent will run

`python -m review_agent` **re-fetches the agent's own logic from its repository and
re-executes it.** So a live run started that way reviews with the *committed* logic, not
with your working copy.

| Command | Reviews with |
|---|---|
| `python -m review_agent` | the committed logic in `TFS_REPO_CODE_REVIEW_CodeReviewAgent` |
| `python -m review_agent --local` | this working copy |

**This demonstration uses `--local`**, so that what you see is the code you have.
If you use the default without pushing this branch first, the checklist section of your
output will be empty — and it will look exactly like the feature having failed.

The first line of every run says which copy ran. Read it.

## 4. What leaves your network

The diff of every reviewed file, the linked work item's text, and the checklist rule text
are all sent to the configured analysis provider. The sample documents here are invented;
if you substitute your team's real standards, their contents go too.

Excluded files are never sent — `appsettings.json` in the sample is one, and §11 shows it
being excluded rather than reviewed.

Whether this exposure is acceptable is a policy decision, and it is not one this
repository can make for you. Decide it before §5, not after §12.

## 5. The sample checklist documents

Generate them:

```powershell
python specs/003-checklist-repo-review-demo/demo-files/generate_checklists.py C:\temp\checklist-demo
```

Four documents, each exercising a different path through the reader:

| Document | What it is for |
|---|---|
| `Najm-API-Checklist.xlsx` | A populated `#` column — identifiers used verbatim. Also carries a `Document Control` sheet, which holds no rules and is reported as ignored |
| `Najm-NFR-Checklist.xlsx` | A `#` column that is **present and empty in every row** — the derived-identifier path. This shape is real; one of the team's three spreadsheets is exactly this |
| `Najm-Secure-Coding-Standard.docx` | `SEC-WEB-nn` identifiers in single-row tables, the shape both real Word standards use |
| `Najm-Legacy-Standard.docx` | Deliberately unreadable. One document that cannot be read must cost that document and nothing else |

Commit all four to the repository named by
`TFS_REPO_CODE_REVIEW_CodeReviewChecklist`, at its default branch. They can sit at the
root or in any folder — the walk is recursive and needs no configuration either way.

## 6. The sample work item

Create a User Story from [demo-files/work-item.json](./demo-files/work-item.json), copying
its title, description and six acceptance criteria verbatim. Suffix the title with your
run tag (§16) so it never collides with feature 002's artifacts.

The six criteria are chosen so the review has all three verdicts to give:

| Criterion | The change | Expected verdict |
|---|---|---|
| 1, 2, 3, 5 | implements | `appears_addressed` |
| 4 — the stock limit | does **not** implement, and the description claims it does | the headline **false coverage claim** |
| 6 — removing a line | does not touch, and nobody claims it does | `not_addressed` — neutral, never a defect |

## 7. The sample change

The files are in [demo-files/src/](./demo-files/src/). `CartController.before.cs` is the
starting state; `CartController.cs` is what you commit.

Every fault is labelled in a comment with the rule identifier or criterion number it
should trip, and [demo-files/faults.md](./demo-files/faults.md) is the full mapping.

**Do not fix the faults.** They are the demonstration.

Branch, add the file as `src/eShop.Api/Controllers/CartController.cs`, and commit. Add the
sample `appsettings.json` too — its contrived password is how §11 shows the exclusion list
keeping a secret-bearing file away from the provider.

## 8. Run it self-contained

Before touching the collection, run the whole review with no server, no credential and no
provider:

```powershell
python -m tests.demo.run
```

Verified 2026-09-16. The output is transcribed verbatim in
[demo-files/observed-selfcontained.md](./demo-files/observed-selfcontained.md), and these
totals are what you should see:

```
  reduction: Najm-Legacy-Standard.docx was not read: not a readable document (corrupt or encrypted file)
  reduction: 1 citation(s) matched no applied rule and were not reported as findings

  documents found      4
  rules applied        7
  criteria judged      6
  checklist findings   4
  dropped citations    1
  false coverage claim 1
```

This run is **repeatable**: `tests/integration/test_us3_demo.py` performs it twice from a
clean start and compares the finding sets, so two operators get the same answer.

What it does **not** prove: that a real provider finds these faults. The provider is
scripted here — the response cites identifiers read out of the documents that were
actually generated, so citation resolution is exercised for real, but judgement is not.
Judgement is what the live half is for.

## 9. Create the pull request

1. Push your branch.
2. Open a pull request into `master`. Title it with your run tag.
3. Paste the description from `tests/demo/run.py` (`PR_DESCRIPTION`) — the "Covered" list
   must include **"Stock limit enforced when adding to cart"**, because that claim is
   fault F4.
4. **Link the work item.** Without the link there is no story half at all, and the review
   will say so rather than failing — which is correct behaviour and a wasted run.

## 10. Preview the review

```powershell
python -m review_agent --local --dry-run --pr <ID>
```

Preview is the default and writes nothing. Expected exit status: **0**.

Before you post, work the five checkpoint questions. Every one is answerable from the run's
own "What this review applied" block:

1. Was a checklist repository obtained, and is the reference it was read at stated?
2. Are at least one `.xlsx` and one `.docx` listed as read, with rule counts?
3. Is **every** document found accounted for — a count or a reason, none passed over?
4. Is the linked work item listed, with the number of criteria judged?
5. Does at least one finding cite a rule identifier and a document filename?

**If any of the five fails, the run is not the review it appears to be.** A review against
an empty checklist prints a clean-looking summary; this checkpoint is the only thing that
tells the two apart, and it exists because this project mistook one for the other for two
features running.

## 11. What you should see

The fault-to-finding reference is [demo-files/faults.md](./demo-files/faults.md) — one row
per fault, each carrying the rule or criterion it trips, where its finding appears, and
whether it is available at all.

Two rows deserve reading before you compare anything:

- **F6 produces nothing on purpose.** `appsettings.json` matches the exclusion list, so it
  is never sent to the provider. It appears under "Not sent for review" with the pattern
  that excluded it. A finding *inside* that file would mean a secret-bearing file had been
  sent to an external service.
- **F9 is not a bug.** Criterion 6 is unimplemented and unclaimed, so it is reported as
  `not addressed` and is explicitly neutral.

## 12. Post the review

```powershell
python -m review_agent --local --post --pr <ID>
```

Observed live, 2026-09-16, against the sample pull request:

| What | Observed |
|---|---|
| Summary discussions | exactly **1**, updated in place on every subsequent run |
| Inline comments | **5** — 1 checklist violation, 4 code issues |
| Exit status | **0** |

The counts differ from the self-contained run's because the sample change differs: the
live pull request is feature 002's, and the provider judges it on its own merits. What
transfers is the *shape* — one summary, findings anchored to changed lines, a checklist
violation citing a real rule from a real document.

The comments land on `CartController.cs` at the lines in `faults.md`. Everything without an
anchorable location goes to the summary instead; there is no severity threshold involved.

## 13. Run it again

This is a required step, not a curiosity:

```powershell
python -m review_agent --local --post --pr <ID>
```

| What | Observed (runs 4 and 5) |
|---|---|
| New inline comments | **0**, twice in a row |
| `suppressed=` in the phase log | **5**, then **4** — every finding already posted |
| Summary discussions | still **1**, updated rather than repeated |

**The first attempt failed, and that is the useful part.** Run 2 reported
`inline=3 suppressed=2`: findings with a natural identifier suppressed, code issues did
not. The provider had reworded every code issue, moved the line it attributed each to, and
re-rated one severity — between two runs minutes apart against an unchanged pull request.
The repair, and the measurement behind its threshold, are research **R14**.

**This is the step that closes a known defect.** Until this feature, a second posting run
repeated every inline comment, because a finding's identity was the provider's prose and
the provider rewords. Feature 001 recorded this as "no gap" by reasoning about the
fingerprint function without noticing what was handed to it, and feature 002 found it the
only way it can be found: by running it twice against a live pull request.

So: `suppressed=6` and zero new comments is the observation. It is asserted in the
self-contained run too, but a passing test is not what closes this — the live second run is.

## 14. Add a document, re-run ⏳

Generate a third spreadsheet, commit it to the checklist repository, and re-run the
preview. **Change no configuration.** The new document should appear in the inventory with
its rule count on the next run — that is SC-010, and it is what makes the checklist
something quality leads can maintain without a release.

## 15. When it does not match

| Symptom | Cause | Fix |
|---|---|---|
| "no checklist repository is configured" | none of the four accepted names is set | set `TFS_REPO_CODE_REVIEW_CodeReviewChecklist` |
| "no checklist repository named X was found" | the name or the branch is wrong | check the name and `CHECKLIST_BRANCH` |
| "could not be read with this credential" | the repository exists; the token cannot see it | grant Code (read) on **that** repository |
| "was reached, but no file matched" | the repository and branch are right, the selection is not | check `CHECKLIST_FILE_PATTERN` and `CHECKLIST_PATH` |
| Story section says coverage was not assessed | the token lacks Work Items (read), or nothing is linked | the message says which |
| Checklist section is empty and you are running live | the default entry point reviewed with committed logic | use `--local`, or push first (§3) |
| HTTP 404 on every endpoint | `TFS_API_VERSION` | set it to `5.0` |

These four checklist messages are deliberately different from one another. If two of your
runs produce the same one for different causes, that is a defect worth reporting.

## 16. Clean up

- Name every artifact with the same run tag — the branch, the work item title and the pull
  request title — so two runs never collide and feature 002's artifacts are never touched.
- **Abandon** the pull request. Do not merge it: the sample code is deliberately faulty.
- Delete the branch, the work item, and the sample documents from the checklist repository.
- The self-contained run creates nothing outside a temp directory and needs no cleanup.

## 17. Provenance

| Section | Status |
|---|---|
| §1–§8, §11, §15, §16 | **Executed and transcribed**, 2026-09-16 — [demo-files/observed-selfcontained.md](./demo-files/observed-selfcontained.md) |
| §10, §12, §13 | **Executed live**, 2026-09-16 — [demo-files/observed-live.md](./demo-files/observed-live.md) |
| §9 | ⏳ A fresh pull request was **not** created; feature 002's sample pull request was reused, by the operator's choice. The steps are written from the design |
| §14 | ⏳ A document was not added to the live checklist repository. SC-010 is asserted self-contained only |
| §2, "Work Items (read)" | ⏳ The Code-only credential path was not exercised live: both available tokens carry the scope. Asserted by test |

Agent version: the working copy of branch `003-checklist-repo-review-demo`.
Test suite: **532 passing**, no live network.

**What the live run proved that no test could:**

- a working copy of the real checklist repository is obtained, and **140 rules across 5
  real documents** reach the review;
- the linked work item is read at `TFS_API_VERSION=5.0` and every criterion is judged;
- a posted finding cites a real rule identifier and the real document it came from;
- **a second posting run adds no comment** — observed twice.

**And two defects no test could have found**, both in the space between the agent and a
real server: the clone could not authenticate where REST could (**R13**), and a code issue
has no stable identity because the provider regenerates every part of one (**R14**). Both
are repaired, and both are why clarification Q2 asked for two kinds of execution rather
than one.

Feature 002's walkthrough ([../002-pr-review-walkthrough/walkthrough.md](../002-pr-review-walkthrough/walkthrough.md))
remains valid for the plain-text checklist path and is not replaced by this document.
