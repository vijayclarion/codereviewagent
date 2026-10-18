# Implementer Quickstart

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-16

How to execute this plan. This is not the operator's document — that is `guide.md`, which
this feature delivers and which does not exist yet.

---

## Read first, in this order

1. [plan.md](./plan.md) — the **Documentation Inventory** and the **Correction Register**
   are the spine. Fifteen rows; three of them block a first manual run
2. [research.md](./research.md) — D1-D8 decide the document's shape, C1-C15 carry the
   evidence
3. [data-model.md](./data-model.md) — ten entities, each with its *source*. Most are
   transcription with verification, not authorship
4. `contracts/` — two files. `documentation-contract.md` is the done-list;
   `verification-record.md` holds the redaction gate

Then, before writing a line of `guide.md`, read `review_agent/README.md` end to end. Most of
what a task in this feature asks for is already written there — 14 module rows, the routing
table, the exit codes, the security section. **Your job is to verify and extend it, not to
write it again.** The expensive mistake available here is drafting a fresh architecture
document beside a correct one and leaving the reader two.

---

## The gate: the suite must pass before and after

```powershell
python -m pytest tests
```

**532 passed**, no live network, about 3 seconds.

Note the command. **Do not add `-q`** — `pytest.ini` already sets it, and the documented
`python -m pytest tests -q` runs at `-qq`, which prints no summary line at all. That is
correction **C2**, and it is why every document in this repository still says 401.

This feature edits no Python. If the number moves, you have left the feature.

---

## What you may edit

| Path | Permitted | Why |
|---|---|---|
| `specs/004-agent-docs-runbook/**` | Yes | This is the feature |
| `review_agent/README.md` | Yes — corrections C3, C4, C5, C6, C11, C15 only | Six of the fifteen live here, three blocking |
| `CLAUDE.md` | Yes — corrections C1, C8, C9, C13 only | It is loaded every session; stale lines there mislead the next agent too |
| `specs/001-.../quickstart.md` | One superseding pointer at the top | Its setup section is stale (I4) |
| `review_agent/*.py` | **No** | Editing one means you have left the feature |
| `tests/**` | **No** | 532 before, 532 after |
| `specs/002/**`, `specs/003/**` | **No** | Both are current; link them |

No test asserts anything about this project's README or `CLAUDE.md` — that was checked, not
assumed (research D8). The four test files matching "README" use it as fixture data.

---

## Order of work

The parts are independently deliverable, and that is the point of the priorities.

| Order | Part | Delivers on its own? | Contract clauses |
|---|---|---|---|
| 1 | **Run it by hand** | Yes. Someone can run the agent | R1-R10 |
| 2 | **What it does and will not do** | Yes. Someone can decide whether to adopt it | C1-C6 |
| 3 | **Where things live** | Yes. Someone can find the owner of a behaviour | S1-S5 |
| 4 | **How a review flows** | Yes, for a reader who has the first three | F1-F5 |
| 5 | The corrections to README, `CLAUDE.md`, the 001 pointer | — | A1-A4 |
| 6 | The Verification Record | — | V1-V7 |

Write part 1 first even though part 3 is easier. The runbook is where the three blocking
corrections land (C3, C7, C13), and writing it is what forces you to run the commands — which
is the only thing that finds the next C2.

---

## How to write a claim

Two marks, on every claim a reader might act on:

```
`--local` reviews with the working copy and says so on the first line
(`bootstrap.main`) [read]

python -m pytest tests  ->  532 passed in 2.76s  [executed]

A second posting run adds no comment [unobserved — closes when a second live
--post run against the same pull request reports suppressed > 0]
```

- **Anchor** is `module.symbol`, not `file.py:120`. Line numbers rot: `CLAUDE.md` cites
  `config.py:425` for a value that now lives at `config.py:473`, and the claim it supports
  is still true (research D3).
- **Marker** is one of three, and `[unobserved]` without a closing observation is invalid
  (`contracts/verification-record.md` §1).

---

## The gate that stops a commit

Before any `git add`, read `contracts/verification-record.md` §3.

`.env` is surveyed **by key name only**. No value is read, printed, or pasted — not into
the guide, not into a scratch file, not into a terminal that scrolls into a transcript. The
key-name survey that established C13 looked like this, and it is the only form permitted:

```bash
grep -oE "^[A-Za-z_][A-Za-z0-9_]*=" .env | tr -d '=' | sort
```

Transcripts come from `python -m tests.demo.run`, which contacts nothing. Hosts, projects,
repositories and PR ids are placeholders.

A secret removed by a later edit is still in the history. The gate runs before the commit.

---

## When you are done

- Every clause in `contracts/documentation-contract.md` passes
- `python -m pytest tests` still reports **532 passed**
- `git ls-files` and the structure map agree (clause S1, SC-010)
- The Verification Record's `unobserved` list is **not empty**, and every entry says what
  would close it
- `review_agent/README.md` links `guide.md`

If you are reading this before `tasks.md` exists, `/speckit.tasks` is your next command —
it generates the task list this quickstart describes how to execute.
