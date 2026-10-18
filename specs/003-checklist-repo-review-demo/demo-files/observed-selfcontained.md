# Observed: the self-contained run

**Feature**: [../spec.md](../spec.md) | **Task**: T052 | **Captured**: 2026-09-16

Verbatim output of:

```powershell
python -m tests.demo.run
```

No server, no credential, no provider. Reproducible from a clean checkout by
anyone, which is what makes SC-006 checkable — `tests/integration/test_us3_demo.py`
runs this twice and compares the finding sets.

**What this run proves**: that both document formats are read, that every document
found is accounted for, that a rule with its own identifier is cited verbatim and
one without is still citable, that every acceptance criterion receives a verdict,
that an invented citation is reported rather than posted, and that every reduction
in coverage states itself.

**What it does not prove**: that a real provider finds these faults. The provider is
scripted here — the response cites identifiers read out of the generated documents,
so resolution is exercised for real, but judgement is not. Judgement is what the
live half of the demonstration is for.

---

```text
ai-review run=- phase=pullrequest outcome=ok ms=0 source=feature/demo-003-add-to-cart target=master scope=parsed
ai-review run=- phase=workitems outcome=ok ms=0 count=1 criteria=6
ai-review run=- phase=checklists outcome=ok ms=8 documents=4 rules=7 skipped=1
ai-review run=4242.1 phase=rules outcome=ok ms=2 applied=7 omitted=0
ai-review run=4242.1 phase=changes outcome=ok ms=0 changed=2 reviewed=1 excluded=1 unreviewed=0 lines=65
ai-review run=4242.1 phase=prior outcome=ok ms=0 posted=0 summary=False
ai-review run=4242.1 phase=llm outcome=ok ms=0 chunks=1 retries=0
ai-review run=4242.1 phase=parse outcome=ok ms=1 coverage=6 violations=4 issues=1 false_claims=1

==============================================================================
DRY RUN - the following would be posted to the pull request
==============================================================================

--- summary discussion (create summary) ---

## 🤖 AI Code Review

**Reviewed**: PR #4242, iteration 1 · 1 of 2 changed files · story #4101

### What this review applied

**Checklist**: CodeReviewChecklist@master (d3m0003)

| Document | Outcome |
|---|---|
| `Najm-API-Checklist.xlsx` | read, 3 rules |
| `Najm-Legacy-Standard.docx` | skipped - not a readable document (corrupt or encrypted file) |
| `Najm-NFR-Checklist.xlsx` | read, 2 rules |
| `Najm-Secure-Coding-Standard.docx` | read, 2 rules |

**Rules applied**: 7 of 7

**Story**: #4101 - 6 acceptance criteria judged

1 citation(s) matched no applied rule and were not reported as findings:
- `SEC-WEB-99`

### ⚠️ False coverage claim

The PR description lists **"Stock limit enforced when adding to cart"** as covered, but the diff does not implement it.

> Acceptance criterion — *"The system must not allow adding more items than are available in stock; a request exceeding available stock is rejected."* — status: `not_addressed`

### Story coverage

| # | Acceptance criterion | Status | Evidence |
|---|---|---|---|
| 1 | Quantity must be a positive integer; a request with zero or a negative quantity is rejected with a validation error. | ✅ appears addressed | AddItem returns BadRequest when request.Quantity <= 0. |
| 2 | Adding an unknown product returns a not-found response and does not change the cart. | ✅ appears addressed | A null product returns NotFound before the cart is loaded. |
| 3 | Adding a product already in the cart increments the quantity of the existing line instead of appending a second line. | ✅ appears addressed | The existing-line branch increments existing.Quantity. |
| 4 | The system must not allow adding more items than are available in stock; a request exceeding available stock is rejected. | ⬜ not addressed | Nothing in the diff reads product.Stock; no quantity is compared against it. |
| 5 | The cart total is recalculated after a successful add, before the cart is saved. | ✅ appears addressed | cart.Recalculate() is called before _carts.Save(cart). |
| 6 | A shopper can remove a single line from the cart without emptying it. | ⬜ not addressed | This change adds an endpoint only; removal is untouched. |

⬜ *Not addressed* is neutral — a pull request routinely implements only part of a story, and these are not defects.

### Checklist violations (4)

- **Never build a SQL statement by concatenating user input** — `Najm-Secure-Coding-Standard.docx`
  request.ProductId is concatenated into the product lookup, so a crafted identifier changes the statement.
  → `/src/eShop.Api/Controllers/CartController.cs:43`
- **Never write a credential or token value to a log** — `Najm-Secure-Coding-Standard.docx`
  The bearer token is written to the information log on every call.
  → `/src/eShop.Api/Controllers/CartController.cs:40`
- **No credential, token or personal identifier is written to a log** — `Najm-NFR-Checklist.xlsx`
  The same call writes the caller's token into the application log.
  → `/src/eShop.Api/Controllers/CartController.cs:40`
- **Business rules stated in the linked story are enforced in code** — `Najm-API-Checklist.xlsx`
  The stock limit required by acceptance criterion 4 is never enforced.
  → `/src/eShop.Api/Controllers/CartController.cs:54`

### Code issues (1)

- **medium** — User.Identity.Name is dereferenced without checking that the caller is authenticated. — `/src/eShop.Api/Controllers/CartController.cs:51`

### Not sent for review

| File | Reason |
|---|---|
| `/src/eShop.Api/appsettings.json` | excluded — matched appsettings*.json |

---
*This is an automated reviewer aid, not a merge gate. It reasons over diff text and cannot verify runtime behaviour — a human decides the merge.*

---
🤖 *AI code review* · `ai-review:summary`

--- inline comment: /src/eShop.Api/Controllers/CartController.cs:54 ---

**⚠️ False coverage claim — criterion 4**

The pull request description claims **"Stock limit enforced when adding to cart"** is covered, but the diff does not implement it.

> Acceptance criterion — *"The system must not allow adding more items than are available in stock; a request exceeding available stock is rejected."* — status: `not_addressed`

Nothing in the diff reads product.Stock; no quantity is compared against it.

---
🤖 *AI code review* · `ai-review:false-coverage:7f6a097e710b`

--- inline comment: /src/eShop.Api/Controllers/CartController.cs:43 ---

**📋 Checklist: Never build a SQL statement by concatenating user input**

request.ProductId is concatenated into the product lookup, so a crafted identifier changes the statement.

*Source*: `Najm-Secure-Coding-Standard.docx`

---
🤖 *AI code review* · `ai-review:checklist:e06e09709d8b`

--- inline comment: /src/eShop.Api/Controllers/CartController.cs:40 ---

**📋 Checklist: Never write a credential or token value to a log**

The bearer token is written to the information log on every call.

*Source*: `Najm-Secure-Coding-Standard.docx`

---
🤖 *AI code review* · `ai-review:checklist:b7e912f325a2`

--- inline comment: /src/eShop.Api/Controllers/CartController.cs:40 ---

**📋 Checklist: No credential, token or personal identifier is written to a log**

The same call writes the caller's token into the application log.

*Source*: `Najm-NFR-Checklist.xlsx`

---
🤖 *AI code review* · `ai-review:checklist:20ab4bdfaf14`

--- inline comment: /src/eShop.Api/Controllers/CartController.cs:54 ---

**📋 Checklist: Business rules stated in the linked story are enforced in code**

The stock limit required by acceptance criterion 4 is never enforced.

*Source*: `Najm-API-Checklist.xlsx`

---
🤖 *AI code review* · `ai-review:checklist:d83a38a3fbc5`

--- inline comment: /src/eShop.Api/Controllers/CartController.cs:51 ---

**🟡 Code issue (medium)**

User.Identity.Name is dereferenced without checking that the caller is authenticated.

---
🤖 *AI code review* · `ai-review:code:13a5d73b4dbe`

==============================================================================
ai-review run=4242.1 phase=post outcome=dry-run ms=0 inline=6 suppressed=0 summary=create

==============================================================================
SELF-CONTAINED DEMONSTRATION - no server, no credential, no provider
==============================================================================
  reduction: Najm-Legacy-Standard.docx was not read: not a readable document (corrupt or encrypted file)
  reduction: 1 citation(s) matched no applied rule and were not reported as findings

  documents found      4
  rules applied        7
  criteria judged      6
  checklist findings   4
  dropped citations    1
  false coverage claim 1
```
