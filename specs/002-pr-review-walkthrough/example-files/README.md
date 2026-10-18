# Example files — deliberately faulty

These files are **reference material for the walkthrough**, not part of the agent.
They are copied into the sample repository to create a pull request with known
defects, so the review agent has something predictable to find.

**Do not import them. Do not fix them.** Every fault here is load-bearing: the
walkthrough's expected results are built on them, and repairing one silently
removes a finding the reader is told to look for.

`pytest` does not collect this directory (`pytest.ini` sets `testpaths = tests`),
and the import-boundary contract test scans only `review_agent/`, so nothing here
reaches the agent's test suite.

## Language

**Python.** Chosen by the fallback branch of the rule in `research.md` R1: the
sample repository could not be inspected, because the access tokens in `.env` are
rejected by the server (observed 2026-09-15). The rule says that where inspection
is not possible the agent's own language applies, and that the walkthrough records
the choice was made without inspection — which this note is.

**If the sample repository turns out to be predominantly another language**, these
files should be rewritten in it before the walkthrough is verified. The faults
below are language-independent; only their expression here is Python.

## The planted faults

| Fault | File | What is wrong | Expected finding | Placement |
|---|---|---|---|---|
| **F1** | `discount.py` | No expiry check anywhere. Acceptance criterion 4 is not implemented, yet the pull request description lists it as covered | `false-coverage` | `either` |
| **F2** | `discount.py` | The invalid-code message is `"Invalid code."`, but criterion 3 states the message must be `"That code is not valid."` | `coverage` / `possible_contradiction` | **`summary-only`** |
| **F3** | `discount.py` | A bare `except Exception` swallows every failure and returns the order unchanged, so a broken discount looks like a successful one | `code` | `either` |
| **F4** | `discount.py` | Unused import retained | `code`, low severity | `either` |

**F2 is the one that must not be edited casually.** It is the only fault
guaranteed to appear in the summary rather than inline: `possible_contradiction`
findings are routed with an empty path (`review_agent/output_layer.py:126`), so
they can never anchor to a line. It is what satisfies FR-011 as amended — the
agent has no severity threshold, so a "low-severity nit" would not reliably
demonstrate summary-only placement.

**F3 exists so the demonstration has a reliable inline finding** that does not
depend on the checklist corpus, which currently yields nothing (gap G1).

## Criteria coverage

| Criterion | Implemented? | Correct? |
|---|---|---|
| 1 — customer can enter a discount code | Yes | Yes |
| 2 — valid code reduces the total | Yes | Yes |
| 3 — invalid code shows "That code is not valid." | Yes | **No — wrong message (F2)** |
| 4 — expired code shows "That code has expired." | **No (F1)** | — |
