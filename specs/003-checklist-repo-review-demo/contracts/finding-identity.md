# Contract: Finding Identity and Re-post Suppression

**Feature**: [../spec.md](../spec.md) | **Research**: [../research.md](../research.md) R7

Fixes the defect recorded in `CLAUDE.md`: two posting runs against an unchanged pull
request produced `suppressed=0` and 9 inline comments where 5 were expected.

---

## The defect, precisely

`fingerprint(kind, path, text)` (`parser.py:194-205`) is stable. What is handed to it is
not. All four call sites in `output_layer.py` pass regenerated provider prose:

| Line | Call site | `text` passed |
|---|---|---|
| `:113` | false coverage claim | `claim.criterion` — the model's echo of the criterion |
| `:123` | coverage contradiction | `entry.criterion` — same |
| `:130` | checklist violation | `f"{violation.item} {violation.issue}"` — model prose |
| `:135` | code issue | `issue.issue` — model prose |

The model rewords between runs, so nothing matches what was posted, so nothing is
suppressed. The summary comment deduplicates correctly because it is keyed on the
`ai-review:summary` marker, not on a fingerprint.

## The identity each kind uses

`fingerprint`'s signature, hashing, and the marker format are unchanged. Only the third
argument changes.

| Kind | Identity key | Line participates? |
|---|---|---|
| `checklist` | resolved `rule_id` | no |
| `coverage` | `wi{work_item_id}:c{ordinal}` | no |
| `false-coverage` | `wi{work_item_id}:c{ordinal}` | no |
| `code` | the text already posted on that file (see I2) | n/a — text, not position |

**Clause I1**: a finding with a natural identifier keys on that identifier alone. Its
identity survives rewording, reordering of the source document, and a line shift caused by
an unrelated edit above it.

**Clause I2** *(amended 2026-09-16 by the live run — research R14)*: a code issue has no
natural identifier, and **severity and line are not one either**. Observed live: between
two runs minutes apart against an unchanged pull request, the provider reworded every code
issue, moved the line it attributed each to, and re-rated one severity. So a code issue is
matched against the **text already posted on the same file** — token overlap on the prose
alone, threshold 0.3, measured against the pair that actually occurred (0.40 for the
reworded pair, 0.00 for the most similar different pair). Severity does not participate:
a reviewer who has read a finding has read it whichever label it now carries.

**Clause I3**: `ordinal` is the criterion's number within its story, as assigned by
`WorkItem.from_payload` — not the position of the entry in the model's coverage array,
which varies per run. A coverage entry whose ordinal could not be resolved (`ordinal == 0`)
has no stable identity and is **summary-only**; it is never posted inline.

**Clause I4**: a checklist violation whose citation resolves to no applied rule is not a
finding (see [llm-response.md](./llm-response.md)). It never reaches `fingerprint`.

## Behaviour this must produce

| # | Given | When | Then |
|---|---|---|---|
| B1 | a posted review | the same review is run again, unchanged | zero new inline comments; `suppressed` equals the number posted |
| B2 | a posted review | run again with the model rewording every finding | still zero new inline comments |
| B3 | a posted review | a row is inserted above a rule in a checklist document | that rule's findings are still suppressed |
| B4 | a posted review | a new iteration adds lines above a checklist violation | that violation is still suppressed |
| B5 | a posted review | a genuinely new violation appears | exactly that one is posted |
| B6 | comments posted by an **older** version of the agent | a new run reads them back | they parse; their fingerprints no longer match, so they re-post **once**, and the demonstration says so |

B6 is the migration cost and it is unavoidable: old comments carry prose-derived
fingerprints that cannot be recomputed. It happens once per pull request that already has
feedback, and only for pull requests reviewed before this feature.

## What must not change

- The marker format `ai-review:{kind}:{fp}` and `ai-review:summary`. `dedupe.parse_markers`
  reads comments posted by every previous version; changing the format orphans them.
- The 12-character fingerprint width, for the same reason.
- `fingerprint`'s exclusion of the line from its own hashing. The line, where it
  participates at all, arrives inside the key its caller builds.
- Exactly one summary discussion per pull request, updated rather than appended
  (`output_layer.post_plan`).

## How this is verified

Unit tests pin each identity function. But the defect being fixed **was already believed
fixed** — feature 001's gap G4 recorded "no gap" by reasoning about `fingerprint`'s inputs
without running it twice against a live provider.

So: **this contract is not considered satisfied until the live run has posted twice and the
second run reports `suppressed` equal to the first run's `inline` and added no comment.**
That observation is a required row in the demonstration's evidence table
([demonstration.md](./demonstration.md) §4), not a unit test result.

**Satisfied 2026-09-16.** Five posting runs against an unchanged pull request: the second
reported `inline=3 suppressed=2` and **failed this contract**, which is how R14 was found;
runs 4 and 5 reported `inline=0` with `suppressed=5` and `suppressed=4`. Evidence in
[../demo-files/observed-live.md](../demo-files/observed-live.md) §4. Had this contract
accepted the passing unit tests, the feature would have shipped with the defect it was
written to close — for the second time.
