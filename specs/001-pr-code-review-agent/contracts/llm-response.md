# Contract: Provider Response

**Feature**: [../spec.md](../spec.md) | **Enforced in**: `review_agent/parser.py` (`validate_payload`, `parse_with_retry`)

The JSON the analysis service must return. `parser.py` opens by citing `contracts/llm-response.schema.json` — **a path that exists nowhere in the repository**, because the earlier cycle's `specs/` directory was removed and took its contracts with it (research R10). This file restores the reference.

The validator is the authoritative specification; this document describes what it enforces. Where the two disagree, the validator wins.

## Shape

```json
{
  "coverage": [
    {
      "criterion": "string, required, non-empty",
      "status":    "appears_addressed | not_addressed | possible_contradiction",
      "evidence":  "string, optional"
    }
  ],
  "checklist_violations": [
    {
      "item":   "string, required, non-empty — the rule being cited",
      "source": "string, optional — which document the rule came from",
      "issue":  "string, optional — what is wrong",
      "file":   "string, optional",
      "line":   "integer, optional"
    }
  ],
  "code_issues": [
    {
      "severity": "high | medium | low",
      "issue":    "string, required, non-empty",
      "file":     "string, optional",
      "line":     "integer, optional"
    }
  ],
  "summary": "string, required, non-empty"
}
```

All four top-level keys are required. The three arrays may be empty; `summary` may not.

## Validation rules

| Rule | Violation raises |
|---|---|
| `coverage`, `checklist_violations`, `code_issues` must be lists | `ContractViolation` |
| Every array entry must be an object | `ContractViolation` |
| `coverage[].status` ∈ `appears_addressed`, `not_addressed`, `possible_contradiction` | `ContractViolation` naming the expected set |
| `coverage[].criterion` non-empty | `ContractViolation` |
| `checklist_violations[].item` non-empty | `ContractViolation` |
| `code_issues[].severity` ∈ `high`, `medium`, `low` | `ContractViolation` naming the expected set |
| `code_issues[].issue` non-empty | `ContractViolation` |
| `summary` non-empty | `ContractViolation` |

`line` is coerced by `_line()`; a non-numeric value becomes `0`, meaning "not locatable", which routes the finding to the summary rather than anchoring it wrongly. This is what protects SC-003's "100% of inline comments land on a changed line."

## Retry and degradation

`parse_with_retry` allows **exactly one** stricter retry. If the second response also fails the contract, the run **degrades** — it does not post partial or invented feedback.

This is the right trade. A response that fails validation twice is one whose findings cannot be trusted to point at real lines, and posting it would put wrong comments on someone's code. `errors.DegradedReview` exits `0` in a pipeline so a provider having a bad minute never gates a merge, and the summary discussion says what happened.

## Severity vocabulary — deliberately unchanged

FR-016 introduces Blocker / Major / Minor, and **this contract keeps `high`/`medium`/`low`** (research R2, G3).

The reason: this vocabulary is what the prompt asks the model to emit and what the validator enforces. Renaming it would invalidate the prompt, this contract, and the parser simultaneously, for a change no reader ever sees — the user-facing severity is derived at routing time by `ReviewReport.severity_of()`. Keeping the wire format stable is what lets the presentation change without a provider round-trip regression.

## Extraction

`extract_json` tolerates a response wrapped in prose or a fenced code block, because providers do that regardless of instruction. It extracts the first balanced JSON object; anything unparseable raises and triggers the single retry.

## Multi-chunk runs

A pull request exceeding `LLM_MAX_CHUNK_LINES` (default 1200) is split on file boundaries and sent as several prompts. `parser.merge_results` combines the responses: coverage entries are merged by criterion with the most severe status winning (`_coverage_rank`), and violations and issues are concatenated.

**Consequence worth stating**: a criterion marked `appears_addressed` in one chunk and `possible_contradiction` in another resolves to `possible_contradiction`. Severity ratchets upward across chunks and never down — a contradiction seen anywhere is a contradiction.

## Derived findings

`derive_false_coverage_claims` produces the agent's headline finding by cross-referencing `DeclaredScope.covered` (the author's claim, parsed from the pull request description) against the returned coverage map. **The provider never emits a false coverage claim directly** — it is derived locally from a claim the author made and a status the model assessed independently.

That separation is what makes the finding credible: the model is never told what the author claimed, so it cannot be led into agreeing.
