# Implementer Quickstart

**Feature**: `006-llm-prompt-response-log` | **Date**: 2026-09-17

Read `plan.md`'s **Call Site Ledger** and **Safety Register** first. This file is the order
of work and the checkpoints.

---

## Before the first edit

```bash
python -m pytest tests            # expect: 532 passed
```

**Not `-q`.** `pytest.ini` already sets it; `-q` again means `-qq`, which prints no summary
line at all. That is how "401" survived three features unchallenged
(`004.../research.md` C2). If you do not see `532 passed`, stop — the baseline is wrong
before you have changed anything.

---

## Order of work

Each step ends green. Nothing here requires a network, a credential, or a provider.

### 1 — `review_agent/llm_log.py`, alone, with its unit test

Build the module before wiring it. It is the only piece with real logic, and it is fully
testable against `tmp_path`.

- `LogDestination`, `ExchangeRecord` — frozen, invariants in `__post_init__`
  (`data-model.md`)
- `LogSession` — stateful, every method total, nothing raises
- One `_write` helper. `redact()` inside it. **No second way to write**
  (`contracts/module-boundary.md`)
- Naming, collision suffix, head/entry/foot (`contracts/log-format.md`)
- Pruning with both guards (`contracts/retention.md`)

**Checkpoint**: `tests/unit/test_llm_log.py` covers format, naming, the `-2` suffix,
retention count, the timestamp guard, and a destination that cannot be written. All
against `tmp_path`, never beside the suite.

### 2 — The two gate tests

Write them now, while the module is fresh and before wiring makes failures ambiguous.

- `tests/contract/test_llm_log_is_redacted.py` — all three credentials, real write path
- `tests/contract/test_llm_log_prunes_only_its_own.py` — a foreign file survives; a newer
  log is never deleted

**Checkpoint**: both fail for the right reason if you temporarily remove `redact()` or
loosen the name pattern. A gate test that passes when the guard is gone is not a gate.

### 3 — `config.py`: three settings

`llm_log`, `llm_log_dir` (**stored absolute**), `llm_log_keep`. Existing `_parse_bool` and
`_parse_int`, existing `_Problems`. None is a secret; none joins `SECRET_FIELDS`.

**Checkpoint**: `tests/unit/test_config.py` — defaults, a bad integer reported with every
other problem, and a relative path arriving absolute.

### 4 — `main.py`: the flag, the session, the wrapper

- `--log-llm` in `build_parser`, threaded into `load_config` like `--local`
- Session opened at L4, closed at L6 / L7 / L8, **not** closed at L9
- The wrapper at L5 — the whole feature

> **The one mistake to avoid.** The wrapper must resolve `call_llm` **at call time**, not
> capture it. Seven tests monkeypatch `main_module.call_llm`; a captured reference ignores
> the fake and the failures land nowhere near the cause (research E17).

Track the attempt inside the per-chunk closure: `parse_with_retry` calls your wrapper once,
or twice when the first response will not parse (`parser.py:550-569`).

**Checkpoint**: `python -m pytest tests` — 532 still pass. If anything in
`tests/contract/test_preview_makes_no_writes.py` or
`tests/contract/test_excluded_files_never_sent.py` breaks, it is the capture mistake above.

### 5 — `bootstrap.py`: carry the path to the child

Two entries added to the dictionary `_child_env` already builds. Nothing new invented.

**Checkpoint**: `tests/unit/test_bootstrap.py` asserts the child's environment carries an
**absolute** `LLM_LOG_DIR`. Without this the operator gets no file and no error, because the
child writes into a temp clone that is deleted moments later (research D4, E11).

### 6 — Integration

`tests/integration/test_llm_log_run.py`:

- three chunks → three entries, in order
- a response that will not parse → two entries for that chunk, `attempt 1` and `attempt 2`
- a degraded run on chunk 3 → chunks 1 and 2 still fully present (SC-007)
- logging on vs off → identical findings, identical exit code (SC-004)

### 7 — Documentation

- `review_agent/README.md`: three rows in the **Optional** settings table, `--log-llm` in
  the CLI section, and a line in **Security** saying plainly that a log contains the pull
  request's full source diff
- `.gitignore`: `.llm-logs/`
- `CLAUDE.md`: the new invariant row; the pointer block is updated by `/speckit.plan`

---

## Done when

```bash
python -m pytest tests            # 532 + the new tests, all passing
```

and, with a real configuration:

```bash
python -m review_agent --local --pr <id> --log-llm
```

writes a file you can open and read top to bottom, containing no credential, and reports
its path and what it pruned.

---

## Things that are not this feature

- **No run report.** Gap G2 stays open. Nothing goes in `.review-reports/`.
- **No token counting.** `prompt_builder.estimated_size` is still called from nowhere.
  Feature 005 documents that gap; adding a token budget here would quietly close a gap the
  documentation says is open.
- **No change to `llm_adapter.py`, `prompt_builder.py`, or `parser.py`.** A diff against any
  of the three means research D1 was abandoned.
- **No new dependency.** Standard library only — the self-hosted build agent is the reason
  (001 R1).
