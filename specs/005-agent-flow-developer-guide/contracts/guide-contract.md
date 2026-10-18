# Contract: `docs/developer-guide.md`

**Feature**: `005-agent-flow-developer-guide` | **Date**: 2026-09-17
**Satisfies**: FR-009 – FR-028, FR-030 – FR-035 | **Verified by**: gates G3 and G5, plus the
section checklist below

The companion document. Its reader is a developer on day one who can already run the tool
(spec Assumption) and now needs to know what happens inside it.

---

## S1 — Required sections, in order

| § | Section | Carries | Requirements |
|---|---|---|---|
| **0** | What this is, and what it is not | Audience; the one-sentence answer to "changes only or whole project"; what to read in 004 instead | FR-009, FR-021 |
| **1** | The flow at a glance | The diagram, how to render it, the twelve stages as a table | FR-003, FR-008 |
| **2** | The flow, stage by stage | One subsection per `Stage`: methods in call order, roles, in → out, log line | FR-010 – FR-012 |
| **3** | Where the path forks | The fourteen `DecisionPoint`s: condition, signal, destination, 004 cross-reference | FR-013 |
| **4** | What the reviewer can see | The four `ContextSource`s, fetched-vs-sent, the five `ReviewBlindSpot`s, why the boundary is deliberate | FR-021 – FR-028 |
| **5** | A very large change | The seven `SizeLimit`s in application order, with where each is reported | FR-016, FR-017 |
| **6** | When a model limit is exceeded | The seven `FailureMode`s; request limits vs answer limits; the levers that exist | FR-018 – FR-020 |
| **7** | Where everything lives | The `FileEntry` inventory, grouped by stage, with the five invariants bound to stages | FR-014, FR-015 |
| **8** | Verification Record | What was executed, what was read, what is unobserved and how each closes | FR-031 |

**S1.1** — Sections 4, 5 and 6 are the ones nothing else in the project answers. If the budget
runs short, section 7 shrinks to a pointer at 004 and these do not.

---

## S2 — The delegation rule

**S2.1** Before writing any paragraph, check the Delegation Map in
[plan.md](../plan.md#delegation-map). Where the row says *link*, the paragraph is a link.

**S2.2** A linked claim anchors to 004's section, **not** to the code — so a later reader
fixing the code knows both documents are downstream of it (`ClaimAnchor.basis`, data model).

**S2.3** Stage names and log lines are copied from 004 verbatim. A reader moving between the
two documents must never have to translate.

**S2.4** If 004 and the code disagree anywhere this feature looks, the disagreement is
**recorded** in section 8 and the code wins. It is not silently overwritten (FR-033). One was
found during planning — **005-C1**, `CLAUDE.md` calling 004's `guide.md` "not yet written"
when it is written (**E18**) — and it is already corrected; carry it into section 8 as the
first row and add any you find.

---

## S3 — Claim discipline

| Clause | Requirement |
|---|---|
| **S3.1** | Every behavioural statement carries a `ClaimAnchor`: `file.py:line`, `file.method`, or a 004 section | FR-030 |
| **S3.2** | Every claim is marked `[executed]`, `[read]` or `[unobserved]` | FR-031 |
| **S3.3** | Every `[unobserved]` claim states what observation would close it. **No exceptions** — this is the shape of gap G4, which this project has already paid for once | FR-031, **D7** |
| **S3.4** | Where a safeguard a reader would expect does not exist, say so outright. The three that matter: no run report is written; there is no severity threshold; **nothing measures a request against the model's token limit** | FR-020 |
| **S3.5** | Every method named resolves in the tree at the stated commit. Gate **G3** | FR-010 |

---

## S4 — Section 4 specifics (the context boundary)

The section most likely to be written comfortably and wrongly.

| Clause | Requirement |
|---|---|
| **S4.1** | Opens with the answer in **one sentence**, before any elaboration | FR-021 |
| **S4.2** | States the diff context width as a **number** — three lines each side of a hunk — not "some surrounding lines" | FR-022 |
| **S4.3** | States how an **added** file differs: it diffs against empty, so effectively all of it is shown | FR-022 |
| **S4.4** | States that an untouched file is **neither fetched nor sent** | FR-023 |
| **S4.5** | States that both complete blobs **are** fetched and then withheld — the fetched/sent distinction | FR-025 |
| **S4.6** | States what one pass of a split review sees of the others, and quotes the warning the prompt carries | FR-026 |
| **S4.7** | Names concrete blind spots — an unchanged caller, a base class, a project-wide convention — and says what to do instead | FR-027 |
| **S4.8** | States that an unanchorable finding is **routed to the summary, not dropped** | FR-027 |
| **S4.9** | Gives the reasons the boundary is deliberate, so it reads as a boundary and not a bug | FR-028 |
| **S4.10** | **No assembled prompt from a real run is reproduced.** Only the fixed instructional text is quoted (**D6**) | FR-035 |

---

## S5 — Section 6 specifics (model limits)

| Clause | Requirement |
|---|---|
| **S5.1** | States plainly that **no request is measured against the model's limit** before sending, and that the only token estimator in the package is called from nowhere | FR-020, **B3.1** |
| **S5.2** | States that splitting bounds **changed diff lines**, and that story, scope and rules repeat in **every** chunk — so splitting shrinks the variable part of a request, not the fixed part | FR-017, **B3.2** |
| **S5.3** | States that a provider rejection degrades the **whole run**, discarding findings from chunks already parsed | FR-018, **B3.3** |
| **S5.4** | States the outcome of S5.3: notice on the pull request, `phase=llm outcome=degraded`, **exit 0** | FR-018 |
| **S5.5** | Separates **request** limits from the **answer** cap, and notes the answer cap applies to one provider only | FR-019, **B3.5** |
| **S5.6** | States the truncated-answer path: invalid JSON → **one** stricter retry → degraded | FR-018, **B3.6** |
| **S5.7** | Distinguishes retried statuses from fatal ones, with attempt counts and exit codes | FR-018 |
| **S5.8** | Names the settings that actually reduce request size, and does not imply a token budget exists | FR-020 |

---

## S6 — Forbidden content

| Clause | Requirement |
|---|---|
| **S6.1** | No credential, token, host, collection URL, project name, repository name or pull-request id. Variable **names** only | FR-035, gate G5 |
| **S6.2** | No transcript from a live run. Every quoted output comes from `python -m tests.demo.run` or from the suite | FR-035 |
| **S6.3** | No claim presented as observed that was not | FR-031 |
| **S6.4** | No edit to `review_agent/**` or `tests/**` in the same change | FR-034, gate G2 |

---

## Acceptance

The guide is done when, in one sitting:

1. **G1** `python -m pytest tests` → `532 passed` (not `-q`).
2. **G2** `git status --short` shows no entry under `review_agent/` or `tests/`.
3. **G3** every `file.method` in the guide resolves — checked by extraction, not by eye.
4. **G4** the diagram's structural self-check passes; rendering recorded `[unobserved]` with
   its closing condition.
5. **G5** no `.env` value appears in either deliverable, tested without printing any.
6. Sections 0–8 all present; sections 4, 5 and 6 each answer their question in the **first
   sentence**, before elaborating.
7. Every `[unobserved]` claim has a closing condition (**S3.3**).
