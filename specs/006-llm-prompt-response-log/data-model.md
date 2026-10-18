# Data Model: LLM Prompt and Response Log

**Feature**: `006-llm-prompt-response-log` | **Date**: 2026-09-17

Three things exist. Two are values; one is the only object in the feature that holds state,
because a file handle and a "have I already complained" flag cannot be frozen.

The package convention is frozen dataclasses with invariants in `__post_init__`. It is
followed for the two values and deliberately not for the session — noted below with the
reason, because an unexplained departure from a convention is how the next reader loses an
hour.

---

## 1. `LogDestination` (frozen dataclass)

Where logs go and how many are kept. Built once, from `Config`, and never mutated.

| Field | Type | Notes |
|---|---|---|
| `directory` | `str` | **Always absolute** — resolved in the launching process (research D4) |
| `keep` | `int` | ≥ 1. How many of the agent's own logs survive a prune |

**Invariants** (`__post_init__`):

- `directory` is absolute. A relative value here means D4 was bypassed and the child would
  write into a temp clone — raise rather than write to the wrong place.
- `keep >= 1`. Zero would mean deleting the file the run is about to write.

**Derived**:

- `path_for(pr_id, started)` → the file path, applying the naming rule and the collision
  suffix. See `contracts/log-format.md`.

---

## 2. `ExchangeRecord` (frozen dataclass)

One request to the provider and its outcome. Created after the call returns or raises;
written immediately and then discarded (research D6 — nothing accumulates in memory).

| Field | Type | Notes |
|---|---|---|
| `index` | `int` | 1-based, counts every exchange in the run including retries |
| `chunk` | `int` | Which diff chunk, 1-based |
| `chunk_total` | `int` | How many chunks the run built |
| `attempt` | `int` | `1` = first send, `2` = the stricter retry (`parser.py:550-569`) |
| `sent_at` | `str` | Local time, `YYYY-MM-DD HH:MM:SS` |
| `elapsed_ms` | `int` | Wall time around the call, including `call_llm`'s internal retries |
| `prompt` | `str` | **Verbatim, complete, after chunking, including the appended retry instruction** |
| `outcome` | `str` | `ok` \| `failed` |
| `response` | `str` | The model's raw text. Empty when `outcome` is `failed` |
| `failure` | `str` | The stated reason. Empty when `outcome` is `ok` |

**Invariants** (`__post_init__`):

- `outcome` is one of `ok`, `failed`.
- `ok` ⇒ `failure` is empty. `failed` ⇒ `failure` is **non-empty**. A failure with no stated
  reason is the silence the conventions forbid.
- `attempt` in `(1, 2)`. `parse_with_retry` sends at most two.
- `chunk <= chunk_total`, both ≥ 1.

**Not fields, deliberately**:

- *Token counts.* Nothing in the agent measures a request against a model's token limit —
  `prompt_builder.estimated_size` is called from nowhere. A count here would imply a budget
  that does not exist. Character counts are what the header carries (FR-015b).
- *The parsed result.* The log records the conversation, not the review's conclusions.
- *The HTTP status.* That lives behind the wire-format boundary (research D1). What escapes
  it is the stated reason, which is what `DegradedReview` already carries.

---

## 3. `LogSession` (stateful — and here is why)

The lifetime of one run's log. Opened at L4, written at L5, closed at L6/L7/L8, and
deliberately never closed at L9.

| Field | Type | Notes |
|---|---|---|
| `path` | `str` | The resolved file path |
| `pr_id` | `int` | From `Config` — known at `load_config`, unlike `run_id` (research D5, E10) |
| `started` | `datetime` | Also the prune guard: nothing at or after this instant is deleted |
| `enabled` | `bool` | Flips to `False` on the first write failure and stays there |
| `count` | `int` | Exchanges written so far; becomes the foot's total |

**Why not frozen**: `enabled` and `count` both change during a run, and `enabled` must stay
flipped so that a broken destination produces one stated line rather than one per chunk
(research D9). A frozen session would mean rebuilding and rethreading it through
`run_review` at every exchange — more moving parts guarding less.

### Lifecycle

```
open(config, pr_id)
  ├─ disabled?            → return a no-op session. Nothing is created. (FR-002)
  ├─ prune()              → contracts/retention.md
  ├─ write head block     → run identity (FR-010)
  └─ emit one line        → "llm log: <path>" (FR-004)

record(ExchangeRecord)    → append, flush, close. count += 1   (FR-005, FR-010a)

close(outcome)            → append foot: count + outcome       (FR-010)
```

**Every method is total.** None raises. A failure inside any of them emits one line, sets
`enabled = False`, and returns. The review never learns that logging failed (FR-018,
FR-014f) — only the operator does.

**The no-op session is the default path.** With logging off, `open` returns a session whose
methods do nothing, so `run_review` has no conditional branches around logging and the
disabled path is exercised by all 532 existing tests rather than by a special case.

### State transitions

| From | Event | To | Visible effect |
|---|---|---|---|
| — | `open`, logging off | `no-op` | None. No directory, no file (SC-003) |
| — | `open`, logging on | `active` | Directory ensured, prune, head written, one emitted line |
| — | `open`, destination unwritable | `disabled` | One stated line. Review continues (FR-018) |
| `active` | `record` | `active` | One entry, on disk before the next call (FR-010a) |
| `active` | write fails | `disabled` | One stated line. No further attempts (D9) |
| `active` | `close(outcome)` | `closed` | Foot written |
| `active` | process killed | `active` | **No foot.** The file is complete to its last entry (FR-010b) |

---

## Relationships

```
Config ──> LogDestination ──> LogSession ──> ExchangeRecord (many, written and discarded)
   │                               │
   │                               └── one file on disk
   └── redact() ─────────────────────── every byte passes through (FR-016, D7)
```

`Config` is the only thing the session needs from the rest of the package. The session never
sees a `TfsClient`, a `ReviewReport`, or a finding — it records a conversation with a
provider, nothing more.

---

## Configuration fields added to `Config`

Three, appended to the existing frozen dataclass (research D3):

| Field | Type | Default | Source |
|---|---|---|---|
| `llm_log` | `bool` | `False` | `LLM_LOG`, overridden by `--log-llm` |
| `llm_log_dir` | `str` | `.llm-logs` → **stored absolute** | `LLM_LOG_DIR` |
| `llm_log_keep` | `int` | `10` | `LLM_LOG_KEEP`, minimum 1 |

None is a secret, so none joins `SECRET_FIELDS` and none is registered with
`register_secret`. `Config.__repr__` prints all three in full — which is wanted: a path in a
log line is how an operator finds their file.
