# Contract: Provider Response — Delta and Citation Resolution

**Feature**: [../spec.md](../spec.md) | **Supersedes**: [001 contracts/llm-response.md](../../001-pr-code-review-agent/contracts/llm-response.md)

One additive change to the response shape, and the resolution rules that turn a model's
citation into a finding that can be trusted and re-recognised.

---

## 1. The shape

Unchanged except for one optional field:

```json
{
  "coverage": [
    {"criterion": "...", "status": "appears_addressed|not_addressed|possible_contradiction", "evidence": "..."}
  ],
  "checklist_violations": [
    {"rule_id": "SEC-WEB-01", "item": "...", "source": "...", "issue": "...", "file": "...", "line": 0}
  ],
  "code_issues": [{"severity": "high|medium|low", "issue": "...", "file": "...", "line": 0}],
  "summary": "..."
}
```

**`rule_id`** — optional, string. The identifier of the rule as it was shown in the prompt.

**Compatibility**: a response without `rule_id` is valid and must not degrade the review.
Provider contracts are the wrong place to be strict about a field that has a working
fallback — a hard requirement here would degrade every review the first time a provider
dropped one field.

**`source`** — still accepted, still validated as a string, and **no longer used**. The
document filename on a posted finding comes from the corpus, not from the response. It is
retained in the contract only so that a response carrying it remains valid.

## 2. How rules are presented

Each rule appears once, under its document, identifier first:

```
## From: Secure-Coding-Standard.docx

- [SEC-WEB-01] Never concatenate user input into a SQL statement — parameterise every query.
```

The prompt instructs: *"When you report a checklist violation, set `rule_id` to the
bracketed identifier of the rule you are citing, exactly as shown."*

## 3. Resolution

Applied in `parser`, against the **applied** corpus — not the full corpus, since a rule
omitted for budget was never shown to the model and a citation of it is a hallucination.

| # | Condition | Result |
|---|---|---|
| R1 | `rule_id` present and in the applied corpus | finding; `source` ← that rule's document filename |
| R2 | no `rule_id`; `item` normalises to a rule's identifier or title | finding; `rule_id` and `source` ← that rule |
| R3 | neither matches | **not a finding** — recorded on `ReviewReport.dropped_citations` |
| R4 | no checklist was applied at all | every `checklist_violations` entry falls to R3 |

Normalisation for R2 is `parser.normalise` — whitespace collapsed, case folded, trailing
punctuation stripped. No fuzzy matching: a citation that needs a similarity threshold to
resolve is a citation the reader cannot look up, which defeats FR-017.

**R3 is not a tidiness rule.** An unresolvable citation has no stable identity, so under
[finding-identity.md](./finding-identity.md) it would re-post on every run. Dropping it is
the only behaviour consistent with FR-028.

**R4 matters more than it looks**: today, a review with no checklist still asks the model
for `checklist_violations` and the model sometimes obliges from general knowledge. Those
findings currently post, cite `checklist`, and are indistinguishable from real ones. After
R4 they are reported as citations matching no applied rule.

## 4. What the run says about dropped citations

In the summary's inventory block:

```
  2 citations matched no applied rule and were not reported:
    "SEC-WEB-99" — no such rule in the applied corpus
    "Avoid magic numbers" — no rule with that identifier or title
```

Silently discarding them would be the same defect in the opposite direction: the reader
could not tell a clean review from one whose citations all failed to resolve.

## 5. Unchanged from 001

- Unknown extra keys are ignored.
- One stricter retry, then `DegradedReview` — never partial findings.
- `not_addressed` is neutral and never produces a comment
  (`tests/contract/test_routing_not_addressed.py`).
- The provider's wire format stays inside `llm_adapter.py`; nothing in this contract
  reaches it.
