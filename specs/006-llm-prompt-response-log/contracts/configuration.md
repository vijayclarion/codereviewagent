# Contract: Configuration surface

**Feature**: `006-llm-prompt-response-log`
**Governs**: FR-001, FR-002, FR-003, FR-003a, FR-004, FR-017, FR-020, SC-003, SC-005a

---

## The settings

| Name | Type | Default | Meaning |
|---|---|---|---|
| `LLM_LOG` | bool | `false` | Write a prompt/response log for this run |
| `LLM_LOG_DIR` | path | `.llm-logs` | Where. Relative values resolve against the **launching** directory |
| `LLM_LOG_KEEP` | int ≥ 1 | `10` | How many of the agent's own logs survive a prune |

| Flag | Meaning |
|---|---|
| `--log-llm` | Turns logging on for this run, overriding `LLM_LOG` |

Parsed in `load_config` with the existing `_parse_bool` and `_parse_int` helpers, so a bad
value is reported alongside every other configuration problem rather than on its own. The
same `_Problems` accumulation, the same message style.

`--log-llm` follows the `--local` pattern: an override argument threaded into `load_config`.
It only ever turns logging **on**; there is no `--no-log-llm`, because `LLM_LOG` already
defaults to off and a flag to disable a disabled thing is noise.

---

## Off by default (FR-002, SC-003)

With no `LLM_LOG` and no `--log-llm`:

- No directory is created — not even an empty `.llm-logs`.
- No file is opened, written, or deleted.
- Nothing is emitted about logging.
- `load_config` still parses `LLM_LOG_DIR` and `LLM_LOG_KEEP`, so a bad value is reported
  even when logging is off. A configuration error that only appears the day you need the
  feature is a configuration error found at the worst possible moment.

The disabled path is a no-op session object rather than a conditional at every call site
(data model), so all 532 existing tests exercise it.

---

## Path resolution (FR-003a, SC-005a)

**The rule**: `Config.llm_log_dir` is **always absolute**, resolved once, in the process the
operator launched.

Why this needs a rule at all: the default entry point clones the agent repository and
re-executes the review as a child process with `cwd=os.path.dirname(cloned.path)`
(`bootstrap.py:70-77`) — a temp directory that `source_fetch.cleanup` deletes when the run
ends. A relative `.llm-logs` resolved inside that child is created in a directory that is
removed moments later. The operator sees no file and no error.

**The mechanism**, per entry path:

| Entry | Who resolves | How the child gets it |
|---|---|---|
| `python -m review_agent` (default, bootstraps) | The parent's `load_config` | `bootstrap._child_env` adds `LLM_LOG_DIR=<absolute>` and `LLM_LOG` to the child's environment |
| `python -m review_agent --local` | That process's `load_config` | No child |
| `python -m review_agent.run` (the child, or a direct run) | That process's `load_config` | `abspath` on an already-absolute path is a no-op |

`bootstrap._child_env` already exists and already injects three marker variables through
`config.child_environment(overrides)`. This adds two more to the same dictionary — no new
mechanism, and the environment is still read in exactly one module.

`--log-llm` needs no override: the child receives the same `argv`.

---

## The announcement (FR-004)

When logging is on, the run emits — through `config.emit`, like everything else — one line
naming the file, and one naming what pruning did:

```
llm log: D:\work\CodeReviewAgent\.llm-logs\llm-pr1234-20260917-143022.log
llm log: removed 3 older logs (keeping 10)
```

An operator must never have to guess where the file went, and must never discover a deletion
by noticing something missing.

---

## No behaviour change (FR-017, SC-004)

Enabling logging must not alter:

- the text sent to the provider,
- the findings produced,
- what is posted to the pull request,
- the exit code,
- the phase log's own lines.

The wrapper at the call site records; it does not transform. It returns exactly what
`call_llm` returned and re-raises exactly what `call_llm` raised, with the same type and the
same message. The integration test asserts identical findings and exit code across a
logging-on and a logging-off run of the same fixture.

---

## Version control (FR-020)

`.gitignore` gains `.llm-logs/`. A log holds a pull request's full source diff; the default
destination sits inside a developer's checkout, and `git add -A` is a reflex.

This covers the default only. An operator who points `LLM_LOG_DIR` at a tracked directory
has made a choice the agent cannot second-guess — but the README's Security section says
plainly what these files contain.

---

## Interaction with existing settings

| Setting | Interaction |
|---|---|
| `DRY_RUN` / `--post` | None. The log is written in both modes (FR-019). Preview's read-only guarantee is about the TFS client, not the filesystem — `test_preview_makes_no_writes.py` asserts on `write_count` and on non-GET calls |
| `LLM_MAX_CHUNK_LINES` | Determines how many chunks, and therefore how many exchanges |
| `CHECKLIST_MAX_CHARS` | The corpus repeats in every chunk prompt, so this is the largest single contributor to file size |
| `REVIEW_EXCLUDE_PATTERNS` | An excluded file never reaches a prompt, so it never reaches the log. The exclusion contract is upheld by construction, not by a second filter |
