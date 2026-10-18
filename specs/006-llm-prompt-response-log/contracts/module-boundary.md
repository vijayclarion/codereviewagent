# Contract: Module boundary

**Feature**: `006-llm-prompt-response-log`
**Governs**: FR-003, FR-016, FR-014c
**Enforced by**: `tests/contract/test_import_boundaries.py` (extended),
`tests/contract/test_llm_log_is_redacted.py` (new)

---

## The new invariant

Added to the table in `CLAUDE.md`:

| Invariant | Where |
|---|---|
| `llm_log.py` and `source_fetch.py` are the only modules that delete a path | `test_import_boundaries.py` |

Today exactly one module deletes anything: `source_fetch.cleanup` removes a temp tree it
created itself. This feature introduces the second, and the second is different in kind —
it deletes inside a directory the **operator** chose. That difference is worth a test.

**The test**: no module other than `source_fetch.py` and `llm_log.py` may contain
`os.remove`, `os.unlink`, `os.rmdir`, `shutil.rmtree`, or `Path.unlink`.

---

## What `llm_log.py` may and may not do

| May | May not |
|---|---|
| Write and delete files under `LLM_LOG_DIR` | Read the environment — `os.environ`, `os.getenv`, `getenv(` are all caught by the existing boundary test |
| Import `config.redact` | Import `requests`, `subprocess`, `openpyxl` |
| Know the log's text format | Know a provider's wire format, a TFS payload, or a document format |
| Receive a `Config` | Reach into `main`, `parser`, `tfs_client`, or `output_layer` |
| Delete files matching its own naming pattern | Delete anything else, anywhere (`retention.md`) |
| Raise nothing | — |

**"Raise nothing" is a boundary too.** Every public function is total: a failure emits one
line, disables the session, and returns. The review must be unable to tell that logging
exists (FR-018).

---

## The redaction gate

**The single most important line in this feature**: the module has exactly one function that
touches the file, and `redact()` is called inside it. There is no second way to write.

```
_write(path, text)  ->  file.write(redact(text))
```

Head, entries, foot, prompt bodies, response bodies, failure reasons — all of them go
through it. A future contributor adding a new section cannot forget, because there is no
other door.

`CLAUDE.md` already carries the warning this implements:

> A new output destination must route through `redact` too — a file writer that calls
> `json.dump` directly bypasses the only thing stopping a token escaping.

This feature is that new output destination. The warning was written for it.

**The test** (`test_llm_log_is_redacted.py`) registers all three credential values, drives a
run through the real write path, and asserts none appears in the file. It asserts on the
**values**, through the real path — the same shape as `test_no_secrets_leak.py`, for the same
reason: the realistic leak is never a deliberate print.

---

## Traps found while surveying, recorded so nobody loses an afternoon

| Trap | Why it bites | Evidence |
|---|---|---|
| A docstring containing `"git"` or the text `subprocess.` | `test_git_is_invoked_from_one_module_only` greps **source text**, not imports. The failure message talks about git, in a module that has nothing to do with git | research E14 |
| Capturing `call_llm` by value in the wrapper | Seven tests monkeypatch `main_module.call_llm`. A captured reference silently ignores the fake and the suite fails in confusing places | research E17 |
| Adding the module to `MAY_READ_ENVIRONMENT` to make a test pass | That set exists to be small. The settings belong in `load_config` | research E13 |
| A log file under a path `pytest` collects | `tests/` is `testpaths`. Tests must write logs to `tmp_path`, never beside the suite | `pytest.ini` |
