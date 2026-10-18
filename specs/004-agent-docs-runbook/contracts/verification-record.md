# Contract: What "Verified" May Mean Here

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md) | **Date**: 2026-09-16

A documentation deliverable has no failing test to stop it shipping wrong. This contract is
what stops it instead: the vocabulary an author may use about their own evidence, and the
one gate that is not negotiable.

The rule it enforces is the project's, not this feature's. 001 closed gap G4 by reasoning
about `fingerprint`'s inputs and was wrong; 002 found the defect by running the thing
twice; 003 wrote into its own contract that the repair "is not considered closed" until a
second live posting run is seen. **A claim closed by reasoning alone is not closed.**

---

## 1. The three markers

Every claim in `guide.md` that a reader might act on carries exactly one.

| Marker | May be used when | Must carry |
|---|---|---|
| `[executed]` | A command was run in the authoring environment and the document shows what it printed | The command, and its output or a faithful excerpt |
| `[read]` | The claim was read out of the code and not exercised | A `module.symbol` anchor |
| `[unobserved]` | The claim cannot be checked in the authoring environment | **The observation that would close it**, phrased as something a person could do |

### Rules

1. **`[read]` is not a weaker `[executed]`.** It is the correct marker for a claim about
   code that no reasonable run would exercise — that `EXIT_DEGRADED` is defined and unused,
   that `not_addressed` hits a `continue`. Marking such a claim `[executed]` because the
   suite passes is false: the suite exercised the code, the author did not observe the
   claim.
2. **`[unobserved]` without a closing observation is invalid.** "Not verified" is a shrug.
   "Closes when a second `--post` run against the same pull request reports `suppressed`
   greater than zero and adds no comment" is a task.
3. **A marker may not be upgraded without a new observation.** Re-reading the code does not
   turn `[read]` into `[executed]`, and reasoning does not turn `[unobserved]` into
   anything at all.
4. **A downgrade is always allowed and never apologised for.** If a command that was
   `[executed]` stops reproducing, it becomes `[unobserved]` with the closing observation
   attached.

---

## 2. The Verification Record

One section at the end of `guide.md`. Six fields:

| Field | Content |
|---|---|
| `commit` | What was verified — a short SHA |
| `date` | When |
| `environment` | Platform, Python version, pytest version |
| `executed` | Each command with its result |
| `read` | Claims taken from the code without exercising them, grouped by area |
| `unobserved` | Each with its closing observation |

**`unobserved` may not be empty.** On today's evidence it has at least three members:

| Claim | Closes when |
|---|---|
| Both TFS tokens can be the same value in practice (C3) | A manual run with `TFS_PAT_FOR_PR` equal to `TFS_PAT` reaches a posted comment |
| `TFS_API_VERSION=6.0` returns 404 against this collection (C12) | One live run at `6.0` produces the 404 and the same run at `5.0` succeeds |
| A second posting run adds nothing (003's open item, G-D) | A second live `--post` run reports `suppressed` greater than zero and adds no comment |

An author who empties this list has either run a live posting cycle — which deserves a
paragraph of its own, since 003 has been waiting on it — or has quietly upgraded a marker,
which rule 3 forbids.

---

## 3. The redaction gate

**This gate is not a clause. Failing it stops the commit.**

| # | Rule |
|---|---|
| **G1** | `.env` is surveyed by **key name only**. No value is read, printed, echoed to a scratch file, or pasted into any artifact |
| **G2** | Hosts, collections, projects, repositories and pull request identifiers appear as placeholders. The one exception is a repository *variable name* such as `TFS_REPO_CODE_SAMPLE`, which is a name, not a value |
| **G3** | Transcripts come from `python -m tests.demo.run`, which contacts nothing, or from agent output that already passed through `config.emit` and its redaction |
| **G4** | No token, key, or 40-plus-character opaque string appears anywhere, in any form, including inside a quoted error message |
| **G5** | The gate runs **before** the commit, not before the review. A secret removed by a later edit is still in the history |

**Why G5 is stated so bluntly**: the natural way to write a runbook is to paste the working
configuration and a real transcript, then clean up. That ordering has already put the
document into git with the secret in it. The discipline is to write with placeholders from
the first keystroke — which is how this feature's own planning was done, and why C13 was
established from ten key names and no values.

### The check

```
git diff --cached
```

Read it. Every value that could be a credential, a host, or an internal identifier is
either a placeholder or does not belong in the commit. This is a human check; there is no
tool here that does it, and `tests/contract/test_no_secrets_leak.py` guards the agent's
output, not this feature's markdown.

---

## 4. Applies to the corrections too

The edits this feature makes to `review_agent/README.md`, `CLAUDE.md` and
`specs/001-.../quickstart.md` are claims like any other.

| Rule | Meaning |
|---|---|
| **A1** | Each edit cites its `C`-row from the Correction Register |
| **A2** | Each edit's new claim carries the same evidence standard as the guide's — an anchor, or an executed command |
| **A3** | No edit touches `review_agent/*.py` or `tests/**`. `python -m pytest tests` reports **532 passed** before the first edit and after the last |
| **A4** | An edit that removes a wrong claim without replacing it must say what is true instead. Deleting `"401 passing"` and leaving no number repeats the failure at one remove |

A4 is the one worth restating: three of this feature's fifteen corrections exist because a
previous author knew a claim was doubtful and left it standing rather than replacing it.
