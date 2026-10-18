<!-- SPECKIT START -->
# CodeReviewAgent

**Active feature**: `006-llm-prompt-response-log` — LLM Prompt and Response Log. An
opt-in setting writes every prompt sent to the provider and every response received to a
plain text file: one file per run, each entry flushed as it happens, everything redacted on
the way out, old logs pruned to a configured count.
**This feature writes agent code** — the first since 003. `review_agent/` and `tests/` are
in scope, and the suite is the contract: **532 passing at `e93d157`, measured**.

- Plan: `specs/006-llm-prompt-response-log/plan.md` — **start here**; the Call Site Ledger
  and the Safety Register are the spine
- Spec: `specs/006-llm-prompt-response-log/spec.md` — 31 requirements, five recorded
  clarifications
- Research: `specs/006-llm-prompt-response-log/research.md` — decisions D1-D12,
  evidence E1-E20
- Data model: `specs/006-llm-prompt-response-log/data-model.md`
- Contracts: `specs/006-llm-prompt-response-log/contracts/` — log format, configuration,
  **retention**, module boundary
- Implementer quickstart: `specs/006-llm-prompt-response-log/quickstart.md`
- **The deliverable**: `review_agent/llm_log.py` plus edits to `config.py`, `main.py`,
  `bootstrap.py` — not written yet

**The whole feature is one new module and a wrapper around one existing lambda**
(`main.py:296`). `llm_adapter.py`, `prompt_builder.py` and `parser.py` are **not touched** —
research D1 explains why logging inside `call_llm` is the obvious choice and the wrong one:
it would couple the wire-format module to the filesystem and emit three identical entries
whenever the provider timed out. Three traps the survey found, each an afternoon:
the wrapper must resolve `call_llm` **at call time** (seven tests monkeypatch
`main_module.call_llm`); a relative log path must be resolved in the **launching** process,
because the child reviews from a temp clone that is then deleted (`bootstrap.py:76`); and
the boundary test greps source text for `"git"` and `subprocess.`, so a docstring can fail
the suite with a message about git.

**Pruning is the only destructive operation this repository has ever had that touches a
directory the operator chose.** `source_fetch.cleanup` removes a temp tree it made itself;
`LLM_LOG_KEEP` deletes inside a configured path. Two guards, both in
`contracts/retention.md`: a filename pattern that proves authorship, and a timestamp
comparison that never deletes a file newer than the running process. Read that contract
before writing the sweep.

**Prior feature** — `005-agent-flow-developer-guide`, Local-Mode Call Flow Diagram and
Developer Onboarding Guide:

- Plan: `specs/005-agent-flow-developer-guide/plan.md` — the Flow Ledger, the Boundary
  Register and the Delegation Map
- **Its deliverables**: `docs/local-mode-pr-review-activity.puml` and
  `docs/developer-guide.md`
- Research: `specs/005-agent-flow-developer-guide/research.md` — decisions D1-D10,
  evidence E1-E18

Three facts it established that a reader will otherwise guess wrongly, all still true and
all relevant to 006: the reviewer sees **only the diff**, three context lines each side of a
hunk, and never an untouched file; **nothing measures a request against the model's token
limit** (`prompt_builder.estimated_size` is called from nowhere — 006 does not change this);
and a provider rejection degrades the **whole run**, discarding the findings of chunks
already parsed — which is exactly the work 006's log makes recoverable.

**Prior feature** — `004-agent-docs-runbook`, Agent Documentation and Manual Run Runbook:

- Plan: `specs/004-agent-docs-runbook/plan.md` — the Documentation Inventory and the
  Correction Register
- **Its deliverable**: `specs/004-agent-docs-runbook/guide.md` — **written**, 623 lines,
  four parts. The operator runbook, comment routing, exit codes, the file inventory and
  the stage-level flow table. Still the authority on all five; 005 links rather than
  restates. *(The line that used to stand here saying it was "not yet written" was stale.)*
- Research: `specs/004-agent-docs-runbook/research.md` — decisions D1-D8, evidence C1-C15

**Read 004's Correction Register before writing anything.** Surveying the seven existing
documents against the code found fifteen disagreements, three of which stop a first manual
run: posting needs a second token the README never names (**C3**), the README's quick start
bypasses the default entry point (**C5**), and the test command every document prescribes
prints no result at all (**C2**). Re-documenting what `review_agent/README.md` already
carries correctly is the expensive mistake available here.

**Prior feature** — `003-checklist-repo-review-demo`, feature 001's gap G1:

- Plan: `specs/003-checklist-repo-review-demo/plan.md` — the Survey Findings table
- **Its deliverable**: `specs/003-checklist-repo-review-demo/demo.md` — `.xlsx` and
  `.docx` checklists, a linked story judged criterion by criterion, and a second run that
  adds nothing. Its self-contained half runs with no server: `python -m tests.demo.run`.
- Demo files: `specs/003-checklist-repo-review-demo/demo-files/` — deliberate inputs,
  including a document that is meant to be unreadable. Never to be "fixed".

**Prior feature** — `002-pr-review-walkthrough`, feature 001's gap G7:

- Plan: `specs/002-pr-review-walkthrough/plan.md` — the Reality Reconciliation table
- **Its deliverable**: `specs/002-pr-review-walkthrough/walkthrough.md` — the operator's
  end-to-end example for the **markdown** checklist path. **Verified end to end on
  2026-09-15** against a real pull request. Still valid; 003 does not replace it.
- Example files: `specs/002-pr-review-walkthrough/example-files/` — deliberately faulty
  sample code. Never imported, never collected by `pytest`, never to be "fixed".

## Running the agent against this server

Two settings the agent's defaults get wrong here. Both cost an afternoon if missed:

- **`TFS_API_VERSION=5.0`.** The default `6.0` (`config.py:425`) returns HTTP 404 on
  every endpoint. The error says "check TFS_PROJECT, TFS_REPO, and TFS_PR_ID" — all
  three can be correct. `5.0` and below work.
- **git needs an `Authorization` header, not a password prompt.** This collection
  challenges with Negotiate and NTLM only, so `GIT_ASKPASS` is never asked and a clone
  fails with "Authentication failed" while the same token reads the same repository over
  REST. `source_fetch.py` now presents the header through git's environment config. If
  you see a clone fail on a credential that demonstrably works, this is why
  (`003.../research.md` R13).
- **`TFS_PAT` needs Work Items (read)**, not just Code. The agent reads the linked
  story with the *read* token. Scoped to Code alone, feature 003 makes the run say so
  and review against the checklist anyway; before 003 it raised out of `_fetch_story`
  and exited **2**, losing the whole review. The note that used to stand here — "the
  review silently loses every requirement finding" — was wrong in both directions.

## Known defect found by the 002 verification run

**Re-running `--post` duplicates inline comments.** `fingerprint(kind, path, text)`
(`parser.py:194-205`) keys on the provider's prose, which is regenerated every run, so
nothing matches what was already posted. Observed: two posting runs, `suppressed=0`,
9 inline comments where 5 were expected. The summary comment *is* deduplicated
correctly. Feature 001's gap G4 recorded "no gap" by reasoning about the fingerprint's
inputs without running it twice against a live provider. See `002.../research.md` R8.
**Repaired by 003.** Each finding kind now keys on an identity that does not change
between runs — the rule identifier, the criterion number within its story, or (for a
code issue, which has no natural identifier) severity and line. Asserted by
`tests/integration/test_us3_posting.py` and `tests/integration/test_us3_demo.py`.
**Still to observe**: a second *live* posting run reporting `suppressed=6` and adding
no comment. Per `003.../contracts/finding-identity.md` the repair is not considered
closed until that is seen, because 001 closed it once by reasoning alone.

**Feature 001** — still the authority on the agent itself:

- Plan: `specs/001-pr-code-review-agent/plan.md` — the Gap Analysis is the spine
- Spec: `specs/001-pr-code-review-agent/spec.md`
- Research: `specs/001-pr-code-review-agent/research.md`
- Data model: `specs/001-pr-code-review-agent/data-model.md`
- Contracts: `specs/001-pr-code-review-agent/contracts/`
- Operator setup: `specs/001-pr-code-review-agent/quickstart.md` Part 1

## Three things 001's artifacts get wrong about today's agent

Found by survey during 002's planning. Trust the code over the document:

- **There is no severity threshold.** Inline versus summary-only is decided by whether a
  finding anchors to a changed line (`output_layer.py`), not by severity.
  `--inline-threshold` and `--report-dir` do not exist in `build_parser`. Unchanged by
  003: gap G3 is still open.
- **Exit `3` is never returned.** `EXIT_DEGRADED` is defined (`errors.py:26`) and unused;
  a degraded review exits `0` (`main.py:343-346`).
- **Nothing writes a run report.** Gap G2 is open, so 001's quickstart checkpoint asking
  for `.review-reports/` cannot be satisfied.

## Read before changing code

**This is not a greenfield project.** `review_agent/` is ~9,000 committed lines
with 532 passing tests, built by an earlier spec-kit cycle whose spec artifacts
were lost. Survey before you build — most of what a task asks for already exists.

**Verify the suite still passes after every change:**

```bash
python -m pytest tests             # 532 passing, no live network
```

**Not `-q`.** `pytest.ini` already sets it, so `-q` again runs at `-qq` and prints no
summary line at all — which is how "401" survived three features unchallenged
(`004.../research.md` C2).

## Architecture invariants

Enforced by `tests/contract/`. Breaking one breaks a test — by design.

| Invariant | Where |
|---|---|
| `config.py` is the only module that reads the environment | `test_import_boundaries.py` |
| `tfs_client.py` is the only module that speaks TFS REST | `test_import_boundaries.py` |
| `llm_adapter.py` is the only module that knows a provider's wire format | `test_import_boundaries.py` |
| `checklist_docs.py` is the only module that knows `.xlsx`/`.docx` | `test_import_boundaries.py` |
| No secret reaches stdout, logs, the prompt, or posted feedback | `test_no_secrets_leak.py` |
| Preview mode issues no write | `test_preview_makes_no_writes.py` |
| Excluded files are never sent to the provider | `test_excluded_files_never_sent.py` |
| TLS verification is never disabled | `test_tls_never_disabled.py` |
| `source_fetch.py` and `llm_log.py` are the only modules that delete a path | `test_import_boundaries.py` |
| No credential reaches a prompt/response log file | `test_llm_log_is_redacted.py` |
| Log retention deletes only the agent's own log files | `test_llm_log_prunes_only_its_own.py` |
| `not_addressed` never produces a comment | `tests/unit/test_routing_not_addressed.py` — the one row not under `tests/contract/` |

Output goes through `config.emit`, which redacts and handles cp1252 consoles.
A new output destination must route through `redact` too — a file writer that
calls `json.dump` directly bypasses the only thing stopping a token escaping.

## Known state

- **`checklist_docs.py` is wired in** — gap G1 is closed. `checklist.py` obtains a
  working copy of the checklist repository through `source_fetch.clone`, reads every
  `.xlsx`/`.docx` in it, and every run reports a per-document inventory. The
  markdown path is retained as the fallback.
- **No run report is written** — output is console and pull request only. Gap G2.
- **`.env` works** — gap G5 is closed. Checked 2026-09-16: `LLM_PROVIDER=claude`,
  the model identifier exists, and `load_config` succeeds. Two values it does not
  carry, both expected: `TFS_API_VERSION` (defaults to 6.0, which 404s here — set
  `5.0`) and `TFS_PR_ID` (pass `--pr`). It *does* carry `TFS_PAT_FOR_PR`, which is a
  **second** token, required before `--post` will run at all and needing Code (write);
  `TFS_PAT` alone gets you a preview and nothing else.
- `.specify/memory/constitution.md` is an unfilled template. The five principles
  the code cites are reconstructed in `plan.md` under Constitution Check.

## Conventions

- Frozen dataclasses for entities; invariants in `__post_init__`
- One responsibility per module — that is what the boundary test protects
- Every skipped or degraded outcome carries a stated reason; silence is a defect
- `.env` holds live credentials and is gitignored. Never commit it, never print it
<!-- SPECKIT END -->
