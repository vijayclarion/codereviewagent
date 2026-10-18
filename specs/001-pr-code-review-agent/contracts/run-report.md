# Contract: Run Report

**Feature**: [../spec.md](../spec.md) | **Requirements**: FR-033–FR-037, SC-011, SC-013 | **Gap**: G2 | **To be implemented in**: `review_agent/run_report.py` (new)

The one genuinely new contract in this plan. **Nothing in the package writes a report file today** — the only `write()` in `review_agent/` is in `source_fetch.py`, and all output goes to the console and the pull request.

## Location and naming

```
<report-dir>/<pr-id>.<iteration-id>.<utc-timestamp>.json
```

Example: `.review-reports/42.3.20260915T184230Z.json`

- `report_dir` defaults to `.review-reports`, overridable by `REVIEW_REPORT_DIR` or `--report-dir`.
- `<pr-id>.<iteration-id>` is `PullRequestContext.run_id`, which already exists — no new concept.
- The timestamp distinguishes repeated runs against an unchanged iteration, which is precisely the SC-006 re-run scenario.

**The folder must be added to `.gitignore`.** Reports embed source-code excerpts inside findings.

## Schema

```json
{
  "schema_version": 1,
  "run_id": "42.3",
  "started_at": "2026-09-15T18:42:11Z",
  "finished_at": "2026-09-15T18:44:02Z",
  "outcome": "complete | degraded | aborted",
  "dry_run": true,

  "target": {
    "base_url": "https://devops.example.com/tfs/Collection",
    "project": "Your-Project",
    "repository": "YourRepo",
    "pr_id": 42,
    "iteration_id": 3,
    "base_commit": "abc123…",
    "iteration_commit": "def456…"
  },

  "agent_source": { "mode": "fetched | local", "commit": "…", "ref": "master", "repo": "…" },

  "analysis_service": { "provider": "claude", "model": "claude-sonnet-5", "endpoint": "https://api.anthropic.com" },

  "checklist": {
    "documents": [
      { "filename": "SecurityChecklist.xlsx", "format": "xlsx", "status": "read",
        "rule_count": 62, "sheets_ignored": ["Revision History"], "skip_reason": "" },
      { "filename": "Draft-Notes.docx", "format": "docx", "status": "skipped",
        "rule_count": 0, "sheets_ignored": [], "skip_reason": "could not be read (BadZipFile)" }
    ],
    "rule_count": 165,
    "dropped_for_budget": []
  },

  "work_items": [
    { "id": 1234, "title": "…", "type": "User Story", "state": "Active", "criteria_count": 4,
      "retrieved": true, "failure": "" }
  ],

  "findings": [
    { "severity": "blocker | major | minor",
      "kind": "false-coverage | contradiction | code-issue | checklist-violation",
      "file": "src/Payments/Processor.cs",
      "line": 88,
      "text": "…",
      "cited_rule": "SEC-WEB-01",
      "cited_source": "SecurityChecklist.xlsx",
      "fingerprint": "a1b2c3",
      "disposition": "posted_inline | in_summary | suppressed_duplicate | post_failed",
      "disposition_detail": "" }
  ],

  "coverage": [ { "criterion": "…", "status": "appears_addressed", "ordinal": 1, "evidence": "…" } ],

  "files": {
    "reviewed":   [ { "path": "…", "changed_lines": 42 } ],
    "excluded":   [ { "path": ".env", "reason": "excluded", "detail": "matches .env" } ],
    "unreviewed": [ { "path": "…", "reason": "bound", "detail": "REVIEW_MAX_FILES=40" } ]
  },

  "failures": [ { "stage": "checklist", "message": "…", "remedy": "…" } ],

  "counts": { "posted": 7, "failed_to_post": 0, "suppressed_duplicates": 2, "summary_only": 5 }
}
```

## Field rules

| Field | Rule | Requirement |
|---|---|---|
| `outcome` | Closed vocabulary. `aborted` means the run did not finish | FR-035 |
| `dry_run` | `true` ⇒ every finding's disposition is `in_summary`; none may be `posted_inline` | FR-037 |
| `analysis_service` | Provider, model, endpoint. **Never the API key** | FR-030, FR-036 |
| `checklist.documents` | Every document found, read or not. A `skipped` entry must carry a `skip_reason` | FR-008a |
| `work_items[].retrieved` | `false` with a `failure` when a linked item could not be read | FR-011 |
| `findings[].disposition` | Closed vocabulary. Every finding carries one | FR-021 |
| `findings[].cited_rule` | The rule or criterion behind the finding | FR-015, SC-004 |
| `counts` | Must reconcile with `findings` dispositions | FR-021 |

## Invariants

**1. Redaction happens on the serialised string, not field by field.**

```python
payload = json.dumps(report_dict, indent=2, ensure_ascii=False)
handle.write(redact(payload))
```

Field-level redaction misses a secret embedded in an exception message inside `failures[].message` — which is exactly how one would realistically escape. Redacting the whole serialised string catches it wherever it landed (research R5).

**2. Written from a `finally`.** `errors.py` defines three abort paths (`SetupFailure`, `DegradedReview`, and an unexpected exception reported as a setup failure). Writing only on success would leave exactly the runs a reader most needs to diagnose without evidence (FR-035, research R7).

**3. A `MissingConfiguration` failure produces a minimal report.** That failure occurs before a `Config` exists, so `report_dir` is unknown; the report falls back to the default folder and records only the configuration problems. Named here rather than hidden, because pretending otherwise would be worse than the limitation.

**4. A failure to write the report never fails the review.** The agent warns and completes (spec edge case: "report folder missing or not writable"). Discarding a finished review over a logging failure would be the wrong trade.

**5. `run_report.py` reads no environment directly.** It takes a `Config`, preserving the reconstructed Principle I and keeping `test_import_boundaries.py` passing.

## Required test additions

| Assertion | Requirement |
|---|---|
| No registered secret appears in a written report — extend `test_no_secrets_leak.py` | FR-036, SC-011 |
| A dry run writes a report with zero `posted_inline` dispositions | FR-037, SC-008 |
| An aborted run still writes a report naming the failure | FR-035, SC-013 |
| `counts` reconcile with `findings` dispositions | FR-021 |
| An unwritable report folder warns but exits with the review's own code | edge case |

Without the first of these, FR-036 and SC-011 are promises rather than properties — the existing secret-leak test watches stdout and would not see a file.
