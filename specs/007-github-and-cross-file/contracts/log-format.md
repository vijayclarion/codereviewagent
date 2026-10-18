# Contract: Log Format — extension of 006

**Module**: `review_agent/llm_log.py` | **Base**: `specs/006-llm-prompt-response-log/contracts/log-format.md`
**Research**: D14-D16

**Rule zero**: every line 006's contract defines, and every string the existing tests assert
(research E9), keeps its exact text. New information goes on **new lines**.

## Entry

```text
--- exchange 3 of 2 | chunk 2 of 2 | attempt 1 ------------------------------------------
sent     : 2026-10-18 14:02:11
model    : claude / <model id>
prompt   : 41,233 characters
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
<prompt, verbatim, redacted>
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
outcome  : ok in 8,431 ms | response 3,112 characters
tokens   : input 11,902 | output 1,044 (reported by provider)
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
<response, verbatim, redacted>
```

| Situation | Header suffix | `tokens` line |
|---|---|---|
| first send of a parse attempt | `\| attempt A ---` (unchanged) | as reported |
| transport resend | `\| attempt A \| send k of 3 ---` | as reported, usually absent |
| synthesis | `--- exchange N \| synthesis \| attempt A ---` | as reported |
| provider reported no usage | — | `tokens   : not reported` |
| failed send | — | `outcome  : failed in N ms` (unchanged), then the reason |

A failed transport send that was then retried is an entry of its own, with outcome
`failed in N ms` and the reason `HTTP 429 - retried` (or the exception name).

## Foot

```text
usage    : input 23,804 · output 2,118 · cost 0.1032 USD
=== end | 3 exchanges | outcome complete =============================================
```

The `usage` line precedes the unchanged `=== end` line. Variants:
`cost not estimated (no LLM_PRICE_* set)`; `· partial — 2 of 3 calls reported usage`;
`usage    : no exchange` for a run that sent nothing.

## Console

- The `phase=llm` line gains `tokens_in=`, `tokens_out=`, and `cost=` extras (omitted when
  zero calls).
- One line `llm usage: <RunUsage.describe()>`, printed **whether or not logging is on** —
  cost visibility is not opt-in (FR-023).

## Failure isolation

`LogSession._guarded` catches `Exception`. Record construction happens inside the guard.
The first failure prints `llm log: could not <what> - <type>: <message>` once and disables
the session; the review continues with the same result it would have had with logging off.
