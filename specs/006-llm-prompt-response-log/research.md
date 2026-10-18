# Research: LLM Prompt and Response Log

**Feature**: `006-llm-prompt-response-log` | **Date**: 2026-09-17
**Method**: read the code, run the suite, decide. Nothing here is closed by reasoning alone
— that rule is the one 001 broke on gap G4 and 002 paid for.

## Evidence

Every decision below cites these. Line numbers are as of commit `e93d157`.

| # | Evidence | Where |
|---|---|---|
| **E1** | **No logging facility exists.** `grep -rn "log_file\|logfile\|LOG_FILE\|log_dir\|logging\.\|import logging\|debug_log\|transcript\|audit" review_agent/` returns **zero matches** across 5,503 lines | `review_agent/` |
| **E2** | The only output path is `emit`, which redacts then prints | `config.py:80-91` |
| **E3** | `call_llm(prompt, config, session=None, sleep=time.sleep)` returns raw model text; raises `DegradedReview` (unreachable, HTTP ≥400, non-JSON, empty) or `SetupFailure` (401/403/404) | `llm_adapter.py:120-175` |
| **E4** | `call_llm` retries the **same** prompt up to 3 times on connection errors and on 429/500/502/503/504, sleeping between | `llm_adapter.py:18-21, 130-142` |
| **E5** | `parse_with_retry(prompt, config, call, retry_instruction)` calls `call()` **twice** — the second with `f"{prompt}\n\n{retry_instruction}"`. Both go through the caller's callable | `parser.py:550-569` |
| **E6** | The call site is a lambda in `run_review`: `lambda text: call_llm(text, config)`, inside `for prompt in prompts` | `main.py:290-300` |
| **E7** | `build_prompts` → "One prompt per chunk. Story, scope, and checklist repeat in every one." | `prompt_builder.py:153-190` |
| **E8** | Checklist corpus budget defaults to 60,000 chars; the comment records the five real documents measuring **48,485** characters of rule items (165 rules) | `config.py` `checklist_max_chars` |
| **E9** | `run_id` is `f"{self.pr_id}.{self.iteration_id}"` — **repeats across re-runs** of an unchanged PR | `models.py:86-88` |
| **E10** | `log.set_run_id(pr_context.run_id)` happens **after** the PR context is fetched; `config.tfs_pr_id` is known much earlier, at `load_config` | `main.py:228`; `config.py` `Config.tfs_pr_id` |
| **E11** | The child that performs the review runs with `cwd=os.path.dirname(cloned.path)` — a temp clone's parent, **not** the operator's directory | `bootstrap.py:70-77` |
| **E12** | The child re-loads its own config from the environment; the parent shapes that environment through `_child_env` → `child_environment(overrides)` | `bootstrap.py:58-68`; `config.py:277-297` |
| **E13** | `test_environment_is_read_only_in_config` fails any module other than `config.py`/`main.py` containing `os.environ`, `os.getenv`, or `getenv(` | `tests/contract/test_import_boundaries.py` |
| **E14** | `test_git_is_invoked_from_one_module_only` fails any module other than `source_fetch.py`/`bootstrap.py` matching `["']git["']` **or** `subprocess\.(run\|Popen\|check_)` | `tests/contract/test_import_boundaries.py` |
| **E15** | Deletion exists in exactly one place today: `source_fetch.cleanup` → `shutil.rmtree(parent, ignore_errors=True)` | `source_fetch.py:273-278` |
| **E16** | `conftest._isolate_env` strips every `LLM_*` variable before each test, so new `LLM_LOG*` settings are isolated for free | `tests/conftest.py` |
| **E17** | Tests monkeypatch `main_module.call_llm` (7 call sites across contract, integration and the demo runner), so anything wrapping it in `main.py` must compose with a patched attribute, not a captured reference | `tests/contract/test_excluded_files_never_sent.py:25`, `test_preview_makes_no_writes.py:36,78`, `tests/integration/*`, `tests/demo/run.py:313` |
| **E18** | Baseline measured, not assumed: `python -m pytest tests` → **532 passed in 16.01s**, exit 0, on 2026-09-17 | this machine |
| **E19** | `.gitignore` has no entry that would cover a log directory | `.gitignore` |
| **E20** | `preview makes no writes` asserts on the **TFS client**, not the filesystem: it raises on `create_thread`/`add_comment`/`update_comment` and checks `tfs.write_count == 0` | `tests/contract/test_preview_makes_no_writes.py:17-27` |

## Decisions

### D1 — The log is written at the call site in `main.py`, not inside `llm_adapter.py`

**Decision**: a wrapper around the existing `lambda text: call_llm(text, config)` (E6)
records each exchange. `llm_adapter.py` is not touched.

**Rationale**: three reasons, in order of weight.

1. **The retry prompt only exists at the call site.** `parse_with_retry` builds the second
   prompt itself and passes it to the caller's callable (E5). Logging inside `call_llm`
   would still see it — but logging at the call site sees it *with the knowledge that it is
   attempt 2*, which `call_llm` does not have.
2. **The wire-format boundary stays a wire-format boundary.** `llm_adapter.py` is the only
   module allowed to know a provider's request shape. Giving it a file handle and a
   retention policy makes it the module that knows the provider format *and* the
   filesystem, which is exactly the coupling `test_import_boundaries.py` exists to prevent.
3. **`call_llm`'s internal retries are not separate exchanges.** It re-sends the *same*
   prompt up to three times on a timeout or a 5xx (E4). The spec counts that as one
   exchange. Logging inside `call_llm` would naturally produce three entries with identical
   prompts; logging outside produces one, which is what was specified.

**Alternatives rejected**: (a) log inside `call_llm` — breaks 2 and 3 above; (b) log inside
`parse_with_retry` — `parser.py` is the response-shape module and has no business holding a
file; (c) a decorator applied at import time — invisible at the call site, and E17 shows
seven tests replace `main_module.call_llm` wholesale, which a decorator would silently drop.

**Consequence for E17**: the wrapper must call `call_llm` by attribute lookup at call time
(`main.call_llm(...)` resolved when invoked), so a monkeypatched fake is still what runs.
The existing lambda already does this. Seven tests depend on it.

### D2 — One new module, `review_agent/llm_log.py`, and a new boundary to go with it

**Decision**: all file creation, writing, naming, pruning and deletion live in one new
module. It imports `config.redact` and nothing else from the package.

**Rationale**: "one responsibility per module" is the convention the boundary test protects.
This module's responsibility is *a durable record of provider exchanges*. It also becomes
the second module in the package permitted to delete a file (E15), which is worth naming in
the boundary test rather than leaving as folklore.

**New invariant, enforced**: `llm_log.py` and `source_fetch.py` are the only modules that
delete a path. See contract `contracts/module-boundary.md`.

**Trap found while reading E14**: the boundary test greps source text for `["']git["']`
and `subprocess\.`. A log module has no reason to contain either, but a docstring that
quotes a shell command would fail the suite in a way whose message names git. Noted so the
implementer does not spend the afternoon 004 warns about.

### D3 — Three settings, one flag

| Setting | Type | Default | Purpose |
|---|---|---|---|
| `LLM_LOG` | bool | `false` | The switch (FR-002) |
| `LLM_LOG_DIR` | path | `.llm-logs` | Where (FR-001) |
| `LLM_LOG_KEEP` | int ≥ 1 | `10` | Retention count (FR-014b) |
| `--log-llm` | CLI flag | — | Turns it on for one run, overriding `LLM_LOG` |

**Rationale**: `_parse_bool` and `_parse_int` already exist and already report a bad value
through `_Problems` alongside every other configuration error. The CLI flag matters because
the primary use is a single investigation run — `--local` and `--pr` set the precedent that
a per-run decision gets a flag rather than an environment edit.

**Why a separate `LLM_LOG` rather than "`LLM_LOG_DIR` being set means on"**: an operator who
configures a directory once and toggles the feature would otherwise have to delete and
restore the path. The two-setting split also makes FR-002 directly testable: unset
`LLM_LOG`, assert zero files.

**Rejected**: `--log-llm=<dir>` taking the path inline. It puts a filesystem path into the
command line of a pipeline task where the directory should be configured once.

### D4 — The path is resolved in the launching process and handed down

**Decision**: `load_config` stores `llm_log_dir` as an **absolute** path. `bootstrap._child_env`
adds `LLM_LOG_DIR=<already absolute>` (and `LLM_LOG`, since `--log-llm` is a CLI flag the
child's `argv` also carries) to the child's environment.

**Rationale**: E11 is the whole problem. The parent runs where the operator stands; the
child runs in a temp clone's parent, which `source_fetch.cleanup` then removes (E15). A
relative `.llm-logs` resolved in the child would be created inside a directory that is
deleted moments later — the operator sees no file and no error, which is precisely the
class of failure 004's Correction Register catalogues. Resolving in the parent (E12 shows
the override mechanism already exists and is already used for three marker variables) makes
`abspath` a no-op in the child.

**`--local` and the already-bootstrapped child**: both reach `load_config` directly with the
operator's cwd, so `abspath` resolves correctly with no override. SC-005a is the assertion.

**Alternatives rejected**: requiring an absolute path (hostile for the common case of
`--log-llm` from a checkout); resolving against the repository root (the operator may run
from anywhere and expects their own cwd).

### D5 — The file is named from the PR id and the process start time, not from `run_id`

**Decision**: `llm-pr<pr_id>-<YYYYmmdd-HHMMSS>.log`. The full `run_id` (`pr.iteration`) goes
*inside* the file, in the head block.

**Rationale**: two independent problems solved at once.

- **`run_id` repeats** (E9). `pr.iteration` is identical for every re-review of an unchanged
  pull request, which is the normal shape of an investigation. The timestamp is what makes
  FR-014a satisfiable.
- **`run_id` is not known early enough** (E10). It needs the PR context. But FR-011 requires
  a file even when the run makes no provider call, and the most interesting no-call runs are
  the ones that failed *before* the review stage. `config.tfs_pr_id` is available at
  `load_config`, so the file can be opened at the start of the run and always exists.

**Collision within one second**: two runs of the same PR starting in the same second get the
same name. The writer appends `-2`, `-3`, … until the name is free rather than opening an
existing file. FR-014a says never clobber, and "unlikely" is not "never".

### D6 — Append-and-close per entry, not a handle held open

**Decision**: each entry opens the file in append mode, writes, and closes.

**Rationale**: FR-010a wants the entry durable before the next call begins. Both a held
handle with `flush()` and open-append-close satisfy that. Open-append-close wins on three
secondary points: no handle to leak if the run dies, no Windows file lock that would make
another run's pruning fail, and no partially-written state to reason about. The cost is
microseconds against a call whose timeout is 180 seconds (E3).

**Rejected**: buffering with an atexit flush — an `atexit` hook does not run when the
process is killed, which is the case FR-010a exists for.

### D7 — Every write goes through `config.redact`

**Decision**: the module's single write helper calls `redact()` on the full text before it
reaches the file. There is no other way to write.

**Rationale**: E2, and the standing warning in `CLAUDE.md` that a file writer bypassing
`redact` "is the only thing stopping a token escaping". A prompt legitimately contains the
diff; a diff of a configuration file could contain a value the registry knows. Making
redaction a property of the *only* write path, rather than a call the author remembers,
is the difference between a rule and a hope.

**Verified, not assumed**: the redaction registry is populated by `load_config` before any
exchange happens, for all three credentials — `tfs_token`, `llm_api_key`, `post_token`.

### D8 — Pruning deletes only files it can prove it wrote, and never one newer than itself

**Decision**: at session open, list the destination, keep only names matching
`^llm-pr\d+-\d{8}-\d{6}(-\d+)?\.log$`, sort by the embedded timestamp, and delete the
oldest beyond `LLM_LOG_KEEP - 1` (leaving room for the file about to be written). A file
whose embedded timestamp is **greater than or equal to this run's own start timestamp** is
never a deletion candidate.

**Rationale**: this is the only destructive operation in the feature and the one requirement
whose failure damages the operator rather than the review.

- The name pattern is the proof of authorship (FR-014c). A directory the operator chose may
  hold their notes; `*.log` would eat them.
- The timestamp guard is a deterministic answer to FR-014d. A concurrent run's file is newer
  than ours, so it is excluded by comparison of embedded timestamps — no clock fuzz, no
  mtime heuristics, no lock.
- Deleting *before* writing keeps the destination at `LLM_LOG_KEEP` after the run, which is
  what SC-008 asserts.

**Rejected**: `shutil.rmtree` of the directory (would destroy an operator's files); deleting
by mtime (a copied or restored file has a misleading mtime); deleting by age in days (the
clarification chose count, and an investigation's ten runs may all be in one hour).

### D9 — A logging failure is stated once and then the session goes quiet

**Decision**: every filesystem operation is wrapped. The first failure emits one line
naming what failed and why, sets the session to disabled, and the run continues untouched.
Subsequent operations are no-ops. Nothing in the module ever raises into the review.

**Rationale**: FR-018 and FR-014f. The convention — "every skipped or degraded outcome
carries a stated reason; silence is a defect" — is why it is one line rather than none, and
"once" is why a per-chunk failure does not print forty times.

### D10 — Plain text, fixed-width rules, keys the reader does not have to decode

The format contract is `contracts/log-format.md`. The shape:

```
=== ai-review llm log ===============================================
run          : 1234.7
pull request : 1234
provider     : claude / <model>
started      : 2026-09-17 14:30:22
agent source : fetched a1b2c3d
---------------------------------------------------------------------

--- exchange 1 of 3 | chunk 1 of 3 | attempt 1 ----------------------
sent     : 2026-09-17 14:30:23
prompt   : 51,204 characters
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
<the prompt, verbatim>
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
outcome  : ok in 8,431 ms | response 2,118 characters
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
<the response, verbatim>

=== end | 3 exchanges | outcome complete ============================
```

**Rationale**: `=`, `-` and `- - -` at three levels let a reader (and `grep`) find a
boundary without counting. Aligned `key : value` needs no legend. Nothing is escaped or
quoted, so a prompt can be lifted out of the file and replayed (FR-015a). The character
count before each body (FR-015b) tells the reader how far to scroll.

**On the delimiter appearing inside a prompt**: a diff containing a line of `=` signs cannot
be mistaken for a section rule, because the rules are anchored and keyed
(`=== ai-review llm log`, `--- exchange N of M`). No escaping is introduced — escaping would
break replayability, which matters more than a pathological diff.

### D11 — The head is written at open; the foot only if the run finishes

**Decision**: the head block is written when the session opens. The foot is written when the
run ends normally or degrades. A killed run leaves a file with a head, N complete exchanges,
and no foot.

**Rationale**: FR-010b makes the missing foot the signal, which is only meaningful if the
foot is genuinely never written by a run that died. This is also why D6 rejects buffering.

### D12 — Tests, and the one that is a gate

| Test | File | Asserts |
|---|---|---|
| Redaction | `tests/contract/test_llm_log_is_redacted.py` | No registered secret reaches the file, through the real write path, for all three credentials |
| Retention safety | `tests/contract/test_llm_log_prunes_only_its_own.py` | A foreign file in the destination survives any number of runs; a newer log is never deleted |
| Boundary | `tests/contract/test_import_boundaries.py` (extended) | Only `source_fetch.py` and `llm_log.py` delete a path; `llm_log.py` reads no environment |
| Off by default | `tests/unit/test_llm_log.py` | No configuration → no directory, no file |
| Format & naming | `tests/unit/test_llm_log.py` | Head/foot/entry shape, collision suffix, timestamp guard |
| Path resolution | `tests/unit/test_bootstrap.py` (extended) | The child's environment carries an absolute `LLM_LOG_DIR` |
| End to end | `tests/integration/test_llm_log_run.py` | Three chunks → three entries in order; a retry → two entries for one chunk; a degraded run → earlier responses still present |
| No behaviour change | `tests/integration/test_llm_log_run.py` | Same findings and exit code with logging on and off |

**The gate**: the redaction test. Everything else can be fixed in a follow-up; a token in a
file cannot be un-written.

## What this feature deliberately does not do

- **It does not close gap G2.** No run report, nothing in `.review-reports/`, no change to
  what the console or the pull request receives.
- **It does not touch `llm_adapter.py`, `prompt_builder.py`, or `parser.py`.** If a diff
  against those appears, D1 was abandoned and the boundary went with it.
- **It does not call `prompt_builder.estimated_size`.** That function is still called from
  nowhere, and nothing here measures a request against a model's token limit. Feature 005
  documents that gap; this feature does not close it and must not appear to.
