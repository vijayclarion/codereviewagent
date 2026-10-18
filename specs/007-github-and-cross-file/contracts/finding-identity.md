# Contract: Finding Identity — extension of 003

**Base**: `specs/003-checklist-repo-review-demo/contracts/finding-identity.md`
**Research**: D2, D13

Every inline comment carries the footer marker `ai-review:<kind>:<fingerprint>`; the summary
carries `ai-review:summary`. This is unchanged, and it is the **same on both platforms** —
dedupe reads markers, never authors, so a local run and a workflow run on the same GitHub PR
recognise each other's comments.

| Kind | Identity passed to `fingerprint(kind, path, identity)` | Source |
|---|---|---|
| `checklist` | `rule_id` | 003 |
| `coverage`, `false-coverage` | `wi<story>:c<ordinal>` | 003 — on GitHub `<story>` is the issue number |
| `code` | `<severity>@<line>`, plus prose overlap ≥ 0.3 | 003 |
| **`cross-file`** | `"\|".join(sorted(normalized files))` | **new** |

`path` for `cross-file` is the anchor file, or `""` when summary-only.

Consequences, accepted deliberately:
- Rewording a cross-file issue between runs does not re-post it.
- Two distinct cross-file issues over the same file set collapse into one comment — the same
  "cheaper error" 003 chose for two identical issues in one file.

**Not considered closed by reasoning.** As 003 required for its own repair, the GitHub path is
closed only when a second **live** posting run on the demo PR reports `suppressed=N` with
`inline=0` and the summary edited in place (SC-004).
