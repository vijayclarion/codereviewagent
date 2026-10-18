# Contract: Command-Line Surface

**Feature**: [../spec.md](../spec.md) | **Implemented in**: `review_agent/main.py` (`build_parser`, `resolve_dry_run`, `main`)

The agent's only user-facing interface. Text in, text out; no interactive prompting, so it can be driven from a script (FR-006).

## Invocation

```bash
python review_agent/main.py [--dry-run | --post] [--pr ID] [--local] [--quiet] [--version] [--help]
```

`python -m review_agent` is equivalent — `__main__.py` delegates to the same entry point.

## Flags

| Flag | Status | Effect |
|---|---|---|
| `--dry-run` | ✅ exists | Review and print; post nothing. Overrides `DRY_RUN`. Satisfies FR-023. |
| `--post` | ✅ exists | Post to the pull request. Overrides `DRY_RUN`. Mutually exclusive with `--dry-run`. |
| `--pr ID` | ✅ exists | Override `TFS_PR_ID` for one run (FR-002). |
| `--local` | ✅ exists | Review with this working copy instead of the fetched agent source (Feature 002). |
| `--quiet` | ✅ exists | Suppress the phase log. Does not suppress findings. |
| `--version` | ✅ exists | Print version and exit. |
| `--help` | ✅ exists | Print usage and exit. |
| `--inline-threshold {blocker,major,minor}` | 🆕 **G3** | Override `INLINE_SEVERITY_THRESHOLD` for one run (FR-019a). |
| `--report-dir PATH` | 🆕 **G2** | Override `REVIEW_REPORT_DIR` for one run (FR-033). |

**Invariant — no flag accepts a credential.** Every secret arrives through the environment or `.env`, never through `argv`, so none can leak into shell history or a process list. Any future flag must preserve this.

**Mode resolution** (`resolve_dry_run`): `--dry-run` → preview; `--post` → posting; neither → fall through to `DRY_RUN`, which defaults to `true`. **Preview is the default at every level**, so a run started by accident cannot write to a pull request.

## Exit codes

| Code | Meaning | Constant |
|---|---|---|
| `0` | Review completed, findings or not | `EXIT_OK` |
| `1` | Blocking findings present — only when `FAIL_ON_CONTRADICTION=true` | `EXIT_BLOCKING_FINDINGS` |
| `2` | Setup failure: configuration, credential, unreachable PR, no permission to post | `EXIT_SETUP_FAILURE` |
| `3` | Degraded manual run — the agent ran but could not produce a full review | `EXIT_DEGRADED` |

This satisfies FR-006's "distinct failure status" with more resolution than the spec asks for. The distinction that matters: `2` means *nothing will work until someone changes a setting*; `3` means *nothing needs fixing here, try again*. A provider outage must never look like a misconfiguration.

Note the deliberate asymmetry — `DegradedReview.exit_code` is `0` so a pipeline is never gated by a transient outage, while a **manual** degraded run exits `3` because a human is reading the terminal and "no review happened" must not be reported with the same code as "reviewed, found nothing."

## Output

All user-visible bytes pass through `config.emit`, which redacts every registered secret and handles console encoding — the feedback contains emoji and en dashes, and a Windows console defaults to cp1252, which would otherwise kill preview mode partway through printing.

| Stream | Carries |
|---|---|
| stdout | Phase log (unless `--quiet`), the rendered feedback, the summary |
| stderr | Setup failures, degraded-review notices |
| `<report-dir>/<run-id>.<timestamp>.json` | 🆕 **G2** — the machine-readable run report |

🆕 **FR-030**: startup must state which analysis service will receive content, alongside the existing `review logic: …` line. Endpoint and model only — never the key.

## Behavioural guarantees

Each is asserted by a contract test; these are properties, not intentions.

| Guarantee | Requirement | Test |
|---|---|---|
| Preview mode issues no write to the pull request | FR-023 | `test_preview_makes_no_writes.py` |
| No secret reaches stdout, logs, prompt, or posted feedback | FR-005, SC-011 | `test_no_secrets_leak.py` (🆕 extend to the run report) |
| Excluded files are never sent to the provider | FR-028, SC-012 | `test_excluded_files_never_sent.py` |
| TLS verification is never disabled | — | `test_tls_never_disabled.py` |
| `not_addressed` never produces a comment | FR-014 | `test_routing_not_addressed.py` |
| Module boundaries hold | Principles I, IV | `test_import_boundaries.py` |
| Output survives a cp1252 console | — | `test_output_encoding.py` |
