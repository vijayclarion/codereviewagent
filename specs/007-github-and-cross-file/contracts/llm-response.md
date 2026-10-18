# Contract: Review and Synthesis Responses

**Modules**: `prompt_builder.py` (states it), `parser.py` (enforces it)
**Research**: D12, D13 — extends the 003 contract; nothing existing is removed or renamed.

## Review response (one per chunk)

```json
{
  "coverage": [{"criterion": "...", "status": "appears_addressed|not_addressed|possible_contradiction", "evidence": "..."}],
  "checklist_violations": [{"rule_id": "...", "item": "...", "issue": "...", "file": "...", "line": 0}],
  "code_issues": [{"severity": "high|medium|low", "issue": "...", "file": "...", "line": 0}],
  "cross_file_issues": [{"severity": "high|medium|low", "issue": "...", "files": ["a", "b"], "file": "...", "line": 0}],
  "change_notes": "...",
  "summary": "..."
}
```

| Key | Required | Validation |
|---|---|---|
| `coverage`, `checklist_violations`, `code_issues`, `summary` | yes | unchanged (`parser.py:111-178`) |
| `cross_file_issues` | **no** (absent → `[]`) | object; `severity` in the set; `issue` non-empty; `files` a list of strings. < 2 distinct files → **demoted to a code issue** at `file`/`line` |
| `change_notes` | **no** (absent → `""`) | string ≤ 2,000 chars, truncated beyond; used only as synthesis input |

The prompt adds to `RULES`: *"You may see only part of the pull request. The outline lists
every changed file and its declarations. Report a cross-file issue when a change in a file
you can see is inconsistent with a declaration, signature, registration, configuration key,
migration or test listed for another file — name every file involved. In `change_notes`,
state in two or three sentences what changed in the files you saw, including any signature
change, for a later pass that sees only notes."*

Examples the rule names: signature changed with callers not updated; interface and
implementation disagree; new dependency not registered for injection; new configuration key
not added to configuration files; model change without a migration; behaviour changed
without its tests being updated.

## Synthesis response (one per multi-chunk run)

```json
{
  "summary": "...",
  "coverage": [{"criterion": "...", "status": "...", "evidence": "..."}],
  "cross_file_issues": [ ... same shape ... ]
}
```

| Key | Required | Validation |
|---|---|---|
| `summary` | yes | non-empty |
| `coverage` | no (absent → keep merged verdicts) | same rules as the review response |
| `cross_file_issues` | no | same rules |
| any other key | ignored | — synthesis cannot add code issues or checklist violations |

Synthesis prompt sections, in order: SYSTEM_ROLE; synthesis rules; the contract above; the
acceptance criteria (enumerated); the PR outline; the merged findings as compact JSON; each
chunk's `change_notes` labelled `part i of n`.

## Merge rules

1. Chunk results merge as today (`merge_results`), plus `cross_file_issues` unioned by
   `cross_file_key` (first wins) and `change_notes` collected in chunk order.
2. Synthesis `coverage` replaces merged entries whose criterion matches
   (`normalise(criterion)`); unmatched merged entries are kept.
3. Synthesis `summary` replaces the joined summaries.
4. Synthesis `cross_file_issues` are unioned with the merged ones (synthesis wins a key
   collision, being the one that saw everything).
5. Parse failure of synthesis after its retry → `ReviewReport.synthesis = "failed: <reason>"`
   and a note; merged results stand.
