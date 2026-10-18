# Contract: Retention and deletion

**Feature**: `006-llm-prompt-response-log`
**Governs**: FR-014b, FR-014c, FR-014d, FR-014e, FR-014f, SC-008, SC-009

**This is the only operation in the feature that destroys data.** Everything else can be
corrected by running again. A deleted file cannot.

The operator asked for bounded retention in preference to keeping everything
(`/speckit.clarify` Q5, answered against the recommendation). This contract is the shape
that answer takes, with the guards that make it safe.

---

## The rule

At session open, before the run's own file is written:

1. List `LLM_LOG_DIR`. **Non-recursive.** Subdirectories are never entered and never touched.
2. Keep only entries whose filename matches, exactly:

   ```
   ^llm-pr\d+-\d{8}-\d{6}(-\d+)?\.log$
   ```

3. Discard any candidate whose embedded timestamp is **≥ this run's start timestamp**.
4. Sort the survivors by embedded timestamp, oldest first.
5. Delete the oldest until at most `LLM_LOG_KEEP - 1` remain.
6. State what was deleted, or that nothing was.

The run's own file is then created, bringing the directory to `LLM_LOG_KEEP` (SC-008).

---

## The guards, and what each one is for

| Guard | Stops | Requirement |
|---|---|---|
| **The name pattern** (step 2) | Deleting a file the agent did not write. An operator's notes, an unrelated `.log`, a `.env` someone parked there | FR-014c, SC-009 |
| **The timestamp comparison** (step 3) | Deleting the file a concurrent run is writing right now | FR-014d |
| **Non-recursive listing** (step 1) | A nested directory becoming collateral | FR-014c |
| **Prune before write** (ordering) | An off-by-one that keeps `KEEP + 1` or deletes the file just created | SC-008 |
| **`keep >= 1`** (data model invariant) | `LLM_LOG_KEEP=0` deleting the run's own log | FR-014b |

**Why an embedded timestamp rather than mtime**: mtime is not a property of the run. A file
copied, restored from a backup, or touched by a sync tool carries a misleading one. The
timestamp in the name was written by the run that created the file and cannot drift. It also
makes step 3 an exact comparison rather than a tolerance window, which is what makes
FR-014d testable rather than probabilistic.

**Why deletion is confined to a directory the operator chose**: because they chose it, they
may keep other things in it. `LLM_LOG_DIR=.` is a configuration an operator will eventually
try. Under this contract it deletes nothing but this agent's own logs. Under a `*.log` sweep
it would be a bad afternoon.

---

## Failure handling

Every step is best-effort and total:

- A file that cannot be deleted (locked, permission denied) is **skipped**, not retried, not
  escalated.
- A directory that cannot be listed **skips pruning entirely** and still allows the run's own
  log to be written.
- Any failure emits **one** line stating what could not be done and why, then pruning is
  finished with. The review is untouched — same findings, same exit code (FR-014f).

A pruning failure never prevents the current run's log from being written. The current run's
evidence matters more than the tidiness of the directory.

---

## Reporting

One line, always, when logging is on (FR-014e):

```
llm log: <path>
llm log: removed 3 older logs (keeping 10)
```

or, when nothing was removed:

```
llm log: removed no older logs (keeping 10)
```

Silence about a deletion is indistinguishable from a file that was never written, which is
the failure mode the "no silent outcome" convention exists to prevent.

---

## What is out of scope

- **Age-based expiry.** The clarification chose count. An investigation's ten runs may all
  happen within an hour, and a day-based rule would delete them mid-investigation.
- **Size caps.** A single run's log is bounded by the review's own limits
  (`REVIEW_MAX_DIFF_LINES`, `CHECKLIST_MAX_CHARS`); the directory is bounded by the count.
- **Compression or archiving.** Plain text is the deliverable.
- **Deleting anything outside `LLM_LOG_DIR`.** The module has no reason to know any other
  path exists.
