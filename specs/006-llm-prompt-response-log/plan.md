# Implementation Plan: LLM Prompt and Response Log

**Branch**: `006-llm-prompt-response-log` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-llm-prompt-response-log/spec.md`

## Summary

An opt-in setting writes every prompt sent to the provider, and every response received, to
a plain text file — one file per run, each entry flushed as it happens, everything redacted
on the way out, and old logs pruned to a configured count.

The technical approach in one sentence: **one new module (`review_agent/llm_log.py`) and a
wrapper around one existing lambda (`main.py:296`)**. Nothing else in the review path
changes. `llm_adapter.py`, `prompt_builder.py` and `parser.py` are not touched — research
**D1** explains why that is a design decision and not an accident.

**This is the first feature since 003 that writes agent code.** 002, 004 and 005 were
document features. The suite is the contract: **532 passing at `e93d157`, measured, not
assumed** (research E18).

## Technical Context

**Language/Version**: Python 3 (3.13 on this machine; the package uses no version-specific syntax)
**Primary Dependencies**: none new. `os`, `re`, `datetime` from the standard library
**Storage**: plain UTF-8 text files in an operator-chosen directory, default `.llm-logs/`
**Testing**: pytest — `python -m pytest tests` (**never `-q`**; `pytest.ini` already sets it, and `-qq` prints no summary at all — `004.../research.md` C2)
**Target Platform**: Windows self-hosted build agent, and developer workstations. Paths, file locking and cp1252 consoles all matter here
**Project Type**: single-package CLI tool
**Performance Goals**: not a factor. One file append per provider call, against a call whose timeout is 180 s
**Constraints**: no new dependency (the self-hosted agent installs compiled extensions unreliably — 001 R1); no module may read the environment except `config.py`; nothing may bypass `redact`
**Scale/Scope**: ~150 KB per three-chunk run (research E7, E8); bounded by `LLM_LOG_KEEP`, default 10 runs

No NEEDS CLARIFICATION remains. The five that existed were resolved by `/speckit.clarify`
and are recorded in the spec's Clarifications section.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is still an unfilled template. The formal gate passes
vacuously for the **fifth** feature running.

Unlike 004 and 005, this feature writes code, so the five principles 001 reconstructed
are live rather than descriptive. Every one of them is reachable from this feature:

| Reconstructed principle | Enforced by | Exposure here | How the plan holds it |
|---|---|---|---|
| **I — One module reads the environment** | `test_import_boundaries.py` | **Real.** Three new settings. The natural implementation reads `os.environ` in the log module | All three parse in `load_config` and arrive on the frozen `Config` (**D3**). The boundary test already greps for `os.environ` in any other module and will fail the suite if this slips |
| **II — One responsibility per module** | convention + boundary test | **Real.** Logging could be smeared across `llm_adapter`, `parser` and `main` | One module. **D1** and **D2** are the argument; `contracts/module-boundary.md` is the enforcement |
| **III — Format knowledge is isolated** | `test_import_boundaries.py` | Moderate. Logging inside `call_llm` would put filesystem concerns in the wire-format module | **D1** keeps the writer at the call site. `llm_adapter.py` is not edited |
| **VII — No silent outcome** | `models.py` invariants, `PhaseLog` | **Real.** A log that silently failed to write, or silently deleted a file, is the defect this principle names | **D9**: one stated line on failure. **FR-014e**: the run says what it deleted, or that it deleted nothing |
| **Secrets never escape** | `test_no_secrets_leak.py` | **Highest in the feature.** A new output destination carrying the full diff and the full checklist corpus | **D7**: a single write path, `redact` inside it, no second way to write. A contract test is the gate |

**The one that is not a principle but should be**: *the only destructive operation in this
feature is pruning.* Nothing in the existing agent deletes a file the operator might own —
`source_fetch.cleanup` removes a temp directory it created itself (E15). `LLM_LOG_KEEP` is
the first setting whose misbehaviour costs an operator data rather than a review. **D8**
gives it two independent guards (name pattern, timestamp comparison) and a contract test,
which is disproportionate to its size and proportionate to its consequence.

**Post-Phase-1 re-check**: the design holds all five. The place it was nearly lost is **D1**
— the obvious place to log is inside `call_llm`, where the prompt and the response are both
in scope, and that single obvious choice would have broken III, coupled the wire-format
module to the filesystem, and produced three identical entries for one exchange whenever
the provider timed out (E4).

**Unchanged recommendation from 001, 002, 003 and 004**: run `/speckit.constitution` and
ratify these five in writing. Five features have now passed this gate vacuously, and this
is the first one where a live principle had to be defended in review notes instead of by a
document.

## The Call Site Ledger

The spine of this plan. Every point where an exchange happens or a log decision is made,
what is true there today, and what changes. **Read this before writing code.**

| # | Point | Today | After | Requirement |
|---|---|---|---|---|
| **L1** | `load_config` (`config.py`) | 20 settings parsed, secrets registered | +3 settings; `llm_log_dir` stored **absolute** | FR-001, FR-002, FR-003, FR-003a |
| **L2** | `build_parser` (`main.py:367`) | `--dry-run/--post/--pr/--local/--quiet/--version` | `+--log-llm` | FR-001 |
| **L3** | `bootstrap._child_env` (`bootstrap.py:58`) | 3 marker overrides + `PYTHONPATH` | `+LLM_LOG_DIR` (resolved) and `+LLM_LOG` | FR-003a |
| **L4** | `run_review` start (`main.py:205`) | phase log begins | Session opens: prune, write head, emit one line | FR-004, FR-011, FR-014b–f |
| **L5** | The prompt loop (`main.py:290-300`) | `lambda text: call_llm(text, config)` | Wrapper records prompt, outcome, response or failure — **per attempt** | FR-005, FR-006, FR-007, FR-008, FR-009 |
| **L6** | `DegradedReview` catch (`main.py:301`) | degraded report built | Session foot written with outcome `degraded` | FR-010 |
| **L7** | Nothing-reviewable branch (`main.py:271`) | `log.phase("llm", outcome="skipped", chunks=0)` | Foot written stating no exchange occurred | FR-011 |
| **L8** | Normal completion (`main.py:334`) | report delivered | Foot written with the exchange count | FR-010 |
| **L9** | Killed / unhandled failure | — | **Nothing.** No foot. That absence is the signal | FR-010b |

**L5 is the whole feature.** Everything else is scaffolding around it. Note that
`parse_with_retry` calls the wrapper **twice** for a chunk that needs a stricter retry
(E5), and that the wrapper must resolve `call_llm` by attribute at call time or it will
break the seven tests that monkeypatch it (E17).

## The Safety Register

Two requirements in this feature can cause damage that a re-run does not repair. They get
their own table, their own contract, and their own gate tests.

| Risk | What it would look like | Mechanism | Proof |
|---|---|---|---|
| **A credential reaches the file** | A PAT inside a diff hunk of a config file, written verbatim | One write helper; `redact()` inside it; no other path to the file (**D7**) | `tests/contract/test_llm_log_is_redacted.py` — the gate. All three credentials |
| **Pruning deletes an operator's file** | `LLM_LOG_DIR=.` and a retention sweep of `*.log`, or `rmtree` of a chosen directory | Name pattern proves authorship; timestamp guard protects a concurrent run; delete-before-write keeps the count exact (**D8**) | `tests/contract/test_llm_log_prunes_only_its_own.py` |

Neither test is optional and neither is a unit test by accident — both live in
`tests/contract/` because they encode a promise, not a behaviour.

## Project Structure

### Documentation (this feature)

```text
specs/006-llm-prompt-response-log/
├── plan.md              # This file
├── spec.md              # With the five recorded clarifications
├── research.md          # D1-D12, evidence E1-E20
├── data-model.md        # LogSession, ExchangeRecord, LogDestination
├── quickstart.md        # Implementer's order of work
├── checklists/
│   └── requirements.md  # Spec quality, 16/16
├── contracts/
│   ├── log-format.md       # The text format, byte for byte
│   ├── configuration.md    # The three settings and the flag
│   ├── retention.md        # What may be deleted, and what may never be
│   └── module-boundary.md  # The new invariant and its test
└── tasks.md             # NOT created by /speckit.plan
```

### Source code (repository root)

```text
review_agent/
├── llm_log.py           # NEW - the only module that writes or deletes a log
├── config.py            # EDIT - 3 settings, absolute path resolution
├── main.py              # EDIT - --log-llm, session lifecycle, the L5 wrapper
├── bootstrap.py         # EDIT - carry the resolved path to the child
├── README.md            # EDIT - Optional settings table, Security section
└── (everything else unchanged)

tests/
├── contract/
│   ├── test_llm_log_is_redacted.py          # NEW - the gate
│   ├── test_llm_log_prunes_only_its_own.py  # NEW
│   └── test_import_boundaries.py            # EDIT - the deletion invariant
├── unit/
│   ├── test_llm_log.py                      # NEW - format, naming, retention, off-by-default
│   ├── test_config.py                       # EDIT - the three settings
│   └── test_bootstrap.py                    # EDIT - the child's resolved path
└── integration/
    └── test_llm_log_run.py                  # NEW - end to end, retry, degraded, no-behaviour-change

.gitignore               # EDIT - .llm-logs/
```

**Structure Decision**: the existing flat package. `review_agent/` is 20 modules with one
responsibility each and no sub-packages; a `logging/` directory for one file would be the
organisational-only grouping the conventions warn against. The test layout mirrors the
existing three-way split, and the two gate tests go in `tests/contract/` because that
directory is where promises live.

## Phase sequence

| Phase | Output | State |
|---|---|---|
| 0 | `research.md` — D1–D12, E1–E20 | **Done** |
| 1 | `data-model.md`, `contracts/*`, `quickstart.md`, CLAUDE.md pointer | **Done** |
| 2 | `tasks.md` | Not started — `/speckit.tasks` |

## Complexity Tracking

No constitution violation requires justification. One deliberate addition is worth naming
so that `/speckit.tasks` does not treat it as scope creep:

| Addition | Why needed | Simpler alternative rejected because |
|---|---|---|
| A **third** setting (`LLM_LOG_KEEP`) beyond the switch and the path | FR-014b requires retention to be operator-configurable | Hard-coding 10 makes the one destructive behaviour in the feature unadjustable, and "nothing hard-coded" is a reconstructed principle with a test behind it |
| A **new contract test file** for pruning, rather than a unit test | It encodes "the agent never deletes your files", which is a promise | A unit test in `tests/unit/` would be equally green and would not say why it exists |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| The wrapper captures `call_llm` by value and breaks 7 monkeypatching tests | Medium — it is the natural way to write it | Called out in **D1**, **L5**, and the quickstart's first checkpoint. The suite catches it immediately |
| A relative path resolved in the child, landing in a temp clone that is then deleted | Medium — invisible, no error | **D4**; asserted in `test_bootstrap.py` and by SC-005a |
| Log files committed to the repository | Low | `.gitignore` entry, FR-020 |
| The log module's docstring contains `"git"` or `subprocess.`, failing the boundary test with a message about git | Low, but an afternoon when it happens | Noted in **D2** |
| Feature drifts into writing a run report (gap G2) | Low | Named out of scope in the spec, research, and this plan. G2 stays open |
