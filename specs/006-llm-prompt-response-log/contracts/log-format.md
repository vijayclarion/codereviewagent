# Contract: The log file format

**Feature**: `006-llm-prompt-response-log`
**Governs**: FR-009, FR-010, FR-010b, FR-012, FR-013, FR-014, FR-014a, FR-015, FR-015a, FR-015b

The user's instruction was "keep the file simple and easy to understand". This contract is
what that sentence means in bytes. Two rules sit above the rest:

1. **A prompt body can be lifted out of the file and replayed against the provider
   unchanged.** Nothing is escaped, quoted, wrapped, indented, or truncated.
2. **A reader finds their way with `grep` and their eyes, not with a parser.**

---

## File

- Encoding **UTF-8**, newline `\n`, written with `errors="replace"`.
- Extension `.log`. Plain text; no JSON, no YAML, no CSV.
- One file per run. Never appended to by a later run, never overwritten (FR-014a).

### Name

```
llm-pr<pr_id>-<YYYYmmdd>-<HHMMSS>.log
llm-pr<pr_id>-<YYYYmmdd>-<HHMMSS>-<n>.log      # only when the first is taken
```

Examples: `llm-pr1234-20260917-143022.log`, `llm-pr1234-20260917-143022-2.log`.

- `pr_id` comes from `Config`, available at `load_config` — unlike `run_id`, which needs the
  PR context (research E10). The full `run_id` goes in the head block instead.
- The timestamp is the moment the run started, local time. It is what makes two reviews of
  the same pull request distinct, since `run_id` (`pr.iteration`) does not (research E9).
- The `-<n>` suffix counts up from `2` until a free name is found. Two runs starting in the
  same second must not share a file.
- **This exact pattern is what pruning uses as proof of authorship.** See
  `retention.md`. Changing the name changes what may be deleted — the two must be edited
  together.

---

## Structure

```
<head block>
<blank line>
<entry> * N
<foot block>
```

### Head — written when the session opens

```
=== ai-review llm log ===============================================
run          : 1234.7
pull request : 1234
provider     : claude / <model>
started      : 2026-09-17 14:30:22
agent source : fetched a1b2c3d
---------------------------------------------------------------------
```

- `run` is `pr_id.iteration_id`. It is not known at open (research E10), so it is written as
  `pending` and the head is completed once the PR context arrives — or left as `pending` if
  the run never gets that far. A file whose head says `pending` is itself information: the
  run failed before it reached the pull request.
- `agent source` is `fetched <sha>`, `local working copy`, or `unknown`.
- Nothing here is a secret. The model identifier is configuration, not a credential.

### Entry — written and flushed as its exchange completes (FR-010a)

```
--- exchange 1 of 3 | chunk 1 of 3 | attempt 1 ----------------------
sent     : 2026-09-17 14:30:23
prompt   : 51,204 characters
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
<the prompt, verbatim, however many lines it runs to>
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
outcome  : ok in 8,431 ms | response 2,118 characters
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
<the response, verbatim>

```

- `exchange N of M` — `M` is the number of **chunks**, so a run with a retry shows
  `exchange 2 of 3` and `exchange 3 of 3` both carrying `chunk 2 of 3`. The exchange number
  counts sends; the chunk number counts work. They are different things and both are needed.
- `attempt 1` is the first send; `attempt 2` is the stricter retry, whose prompt ends with
  the appended retry instruction — visible in the body, because the body is what was sent.
- Counts are thousands-separated. They are for a human estimating scroll distance (FR-015b),
  not for a parser.
- A failed exchange replaces the outcome line and the response body:

```
outcome  : failed in 184,003 ms
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
the AI provider was unreachable after 3 attempts (ConnectionError)
```

  The reason is the text `DegradedReview` already carries. An entry marked `failed` always
  has one (data model invariant).

### Foot — written when the run ends normally or degrades

```
=== end | 3 exchanges | outcome complete ============================
```

`outcome` is `complete`, `degraded`, or `no exchange` (FR-011, the nothing-reviewable case).

**A run that is killed writes no foot.** That absence is the documented signal that the run
did not finish (FR-010b). It is the reason entries are flushed individually rather than
buffered — see research D6 and D11.

---

## What is forbidden

| Forbidden | Why |
|---|---|
| Truncating, eliding, or `...`-ing a prompt or response | FR-015. A truncated prompt cannot answer the question the log exists for |
| Recording the repeated preamble once and referencing it | FR-015a. Every entry must stand alone and be replayable |
| Escaping, quoting, or indenting a body | Rule 1. It would stop a prompt being copied out and replayed |
| JSON, or any structured encoding, for the bodies | FR-012, and the user's instruction |
| Writing anything that has not passed `config.redact` | FR-016. See `module-boundary.md` |
| Sorting, deduplicating, or reordering entries | FR-005. The order sent is the information |

## On a delimiter appearing inside a body

A diff can legitimately contain a line of `=` or `-` characters. This is accepted, not
escaped: every rule is anchored and keyed (`=== ai-review llm log`, `--- exchange N of M`,
`=== end |`), so a collision requires a diff line that reproduces a key as well as a rule.
Escaping would buy protection against a pathological case at the cost of rule 1, which is
the wrong trade. A reader who needs certainty greps for `^--- exchange `.
