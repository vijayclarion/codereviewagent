# Observed: the live run

**Feature**: [../spec.md](../spec.md) | **Tasks**: T053, T055, T056, T057 | **Performed**: 2026-09-16

Against the real collection, the real checklist repository, and the sample pull request
feature 002 left in place. Identifiers are replaced with placeholders throughout, per the
redaction rule this feature inherits from 002 — `<sample-pr-id>`, `<story-id>`, and the
collection host, which appears nowhere.

Run with `--local`, so the logic under test is this branch's working copy rather than the
committed agent (see `demo.md` §3). The credential used for both reading and posting was
the one in `TFS_PAT_FOR_PR`.

---

## 1. The checklist corpus, live

The thing this feature exists to make work, against the team's actual documents:

```text
ai-review phase=checklists outcome=ok ms=3562 documents=5 rules=140 skipped=0
ai-review phase=rules      outcome=ok ms=834  applied=140 omitted=0
```

| Document | Outcome |
|---|---|
| `API Integration Checklist v3.0.xlsx` | read, 30 rules, 2 sheets ignored |
| `API Security Checklist_v3.0.xlsx` | read, 27 rules, 2 sheets ignored |
| `Najm_Application_Security_Guidelines v1.0.docx` | read, 20 rules |
| `Najm_Coding_Standards v1.1.docx` | read, 22 rules |
| `Non Functional Requirements Checklist v2.0.xlsx` | read, 66 rules, 1 sheet ignored |

- **140 rules**, 73 carrying their own identifier and 67 carrying a derived one.
- **37,477 characters** of rule text against a 60,000 budget, so nothing was omitted and
  the budget path was not exercised live. (The earlier measurement of 48,485 characters
  in `research.md` R5 counted rule detail this reader now drops as commentary.)
- Working copy taken at `CodeReviewChecklist@master`, commit recorded in the summary.
- Acquisition: **3.3–5.5 seconds**, shallow, removed at the end of the run.

**This is gap G1 closed against the real corpus** — not against a fixture.

## 2. The linked story, live

```text
ai-review phase=workitems outcome=ok ms=503 count=1 criteria=4
```

Story `<story-id>` was read with the nominated credential and all four acceptance criteria
received a verdict: two `appears_addressed`, one `possible_contradiction`, one
`not_addressed`. Two of the description's "Covered" claims were contradicted by the diff
and became false coverage claims.

## 3. A finding that cites a real rule

From the posted summary, verbatim except for the redactions:

> **Exception Handling & Error Contracts** — `Najm_Coding_Standards v1.1.docx`
> A bare `except Exception` silently swallows all errors and returns the untouched order
> total with no message, error type, or logging…
> → `/discount.py:51`

The rule identifier and the filename both came from the corpus, not from the provider
(FR-017). **SC-001 is satisfied live.**

## 4. The second-run observation — what this was all for

Five posting runs against the unchanged pull request, in order:

| Run | `inline=` | `suppressed=` | What it shows |
|---|---|---|---|
| 1 | 5 | 0 | First post under the new identity scheme. The 9 comments feature 002 left carry prose-derived fingerprints that cannot be recomputed, so they do not match — the documented one-time migration cost (contract B6) |
| 2 | **3** | **2** | **The fix was incomplete.** Checklist and criterion findings suppressed; code issues did not |
| 3 | 1 | 4 | After the R14 repair |
| 4 | **0** | **5** | ✅ |
| 5 | **0** | **4** | ✅ confirmed |

**Runs 4 and 5 added no comment.** That is the observation
[contracts/finding-identity.md](../contracts/finding-identity.md) refuses to accept a unit
test for, and it is now made.

The pull request settled at 19 threads: 1 summary (updated in place, never duplicated),
1 checklist finding, 17 code comments — 9 of them feature 002's, the rest this session's
convergence.

## 5. Two defects this run found

Neither was visible to any test, because both live in the space between the agent and a
real server.

### R13 — the clone could not authenticate, while REST could

`git clone` failed with `fatal: Authentication failed` against a repository the *same
token* read over REST seconds earlier. The cause: `GIT_ASKPASS` answers a challenge, and
this collection challenges with Negotiate and NTLM only, so git never asks. The
credential is now presented unasked, as an `Authorization` header delivered through git's
environment config — never through `-c`, which would put it in the argument list.

Had this feature shipped on its test suite alone, the checklist corpus would have failed
to load on the first real run, with a message pointing at the token's scopes — which were
fine.

### R14 — a code issue has no stable identity, and the provider proves it

Between two posting runs minutes apart, against an **unchanged** pull request, the
provider reworded every code issue *and* moved the line it attributed each one to, *and*
re-rated one of their severities. Identity keyed on severity and line was therefore
unstable in three ways at once.

Code issues are now additionally matched against the text already posted on the same file.
The measured separation: the reworded pair overlapped at **0.40**, the most similar
genuinely different pair at **0.00**; the threshold sits at 0.3.

## 6. What remains unobserved

| Task | Why |
|---|---|
| T054 | A fresh sample pull request was not created — feature 002's was reused, by the operator's choice |
| T058 | The Code-only credential path was not exercised; both available tokens carry Work Items (read) |
| T059 | A document was not added to the live checklist repository, so SC-010 remains asserted only self-contained |
| T063 | Nothing was created, so nothing was torn down. The comments posted during convergence remain on the pull request |
