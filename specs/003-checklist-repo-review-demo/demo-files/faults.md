# Expected results: every deliberate fault and the finding it produces

**Feature**: [../spec.md](../spec.md) | **Task**: T047, T061 | **Contract**: [../contracts/demonstration.md](../contracts/demonstration.md) §2

One row per planted fault. The **Availability** column is the point: a finding the
demonstration expects but the agent cannot produce is recorded here as
`expected-absent` with its reason, rather than quietly left out. Feature 002's
walkthrough listed checklist findings that its checklist path could not produce,
and their absence read as "no violations found" — which is the failure this
column exists to prevent.

**Observed in** says which execution produced the row. `self-contained` results
come from [observed-selfcontained.md](./observed-selfcontained.md); `live` results
come from `observed-live.md`, which is written by the live run.

---

## The faults

| Fault | Trips | Finding kind | Appears | Availability | Observed in |
|---|---|---|---|---|---|
| **F1** SQL built by concatenating `request.ProductId` — `src/CartController.cs:43` | `SEC-WEB-01` (Najm-Secure-Coding-Standard.docx) | `checklist` | inline at `CartController.cs:43` — the line is in the diff, so it anchors | present | self-contained |
| **F2** The bearer token is written to the log — `src/CartController.cs:40` | `SEC-WEB-02` (Najm-Secure-Coding-Standard.docx) | `checklist` | inline at `CartController.cs:40` | present | self-contained |
| **F2a** The same line, judged against the spreadsheet rule that has **no identifier of its own** | `Najm-NFR-Checklist:Quality Attributes:<digest>` (Najm-NFR-Checklist.xlsx) | `checklist` | inline at `CartController.cs:40` | present | self-contained |
| **F3** No stock check anywhere in `AddItem` — `src/CartController.cs:54` | `API-02` (Najm-API-Checklist.xlsx) **and** acceptance criterion 4 | `checklist` + `false-coverage` | both inline at `CartController.cs:54`; the claim borrows its location from the violation | present | self-contained |
| **F4** The pull request description claims the stock limit is covered | acceptance criterion 4 | `false-coverage` | inline — see F3. It would be summary-only if no violation shared its subject | present | self-contained |
| **F5** `User.Identity.Name` dereferenced without an authentication check — `src/CartController.cs:51` | no rule — a code issue | `code` | inline at `CartController.cs:51` | present | self-contained |
| **F6** A connection-string password in `appsettings.json` | — | none | — | **expected-absent** — the file matches `appsettings*.json` in the exclusion list and is never sent to the provider. It appears under "Not sent for review" | self-contained |
| **F7** `Najm-Legacy-Standard.docx` cannot be read | — | none | inventory row: `skipped — not a readable document` | present, as an inventory row rather than a finding | self-contained |
| **F8** The provider cites `SEC-WEB-99`, which no applied rule matches | — | none | summary: "1 citation(s) matched no applied rule" | present, as a reported non-finding | self-contained |
| **F9** Acceptance criterion 6 (removing a cart line) is not implemented and not claimed | acceptance criterion 6 | `coverage` | summary only, as `not addressed` | present — and **never a defect**, which is the behaviour being demonstrated | self-contained |

## What a correct run totals

From [observed-selfcontained.md](./observed-selfcontained.md):

| Count | Value |
|---|---|
| documents found | 4 |
| documents read | 3 (one skipped, with its reason) |
| rules applied | 7 of 7 |
| acceptance criteria judged | 6 |
| checklist violations | 4 |
| false coverage claims | 1 |
| code issues | 1 |
| dropped citations | 1 |
| inline comments | 6 |
| summary discussions | 1 |

## Two findings that are easy to misread

**F9 is not a bug.** An acceptance criterion the change does not implement is
neutral — pull requests routinely implement part of a story. It becomes the
headline finding only when the description *claims* it (F4). If your run reports
criterion 6 as a problem, something has changed in the routing rules and that is
worth investigating.

**F6 produces nothing, on purpose.** An excluded file is not reviewed, so no
finding about it can exist. What you should see is its name under "Not sent for
review" with the pattern that excluded it. A review that reported a finding
*inside* `appsettings.json` would mean a secret-bearing file had been sent to an
external provider.
