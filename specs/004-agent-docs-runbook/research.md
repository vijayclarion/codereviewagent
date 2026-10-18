# Research: Agent Documentation and Manual Run Runbook

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-16
**Verified against**: branch `004-agent-docs-runbook`, commit `33535f0`, Python 3.13.14,
pytest 9.1.1, Windows 11 / PowerShell.

Two halves. **Decisions D1-D8** settle the shape of the deliverable. The **Verification
Record C1-C15** is the evidence behind the Correction Register in the plan — one entry per
row, each saying what was executed or read, and what is still unobserved.

The C-numbering here and in `plan.md` is the same numbering. There is no second scheme.

---

## Part 1 — Decisions

### D1. The deliverable is one file with four parts

**Decision**: `specs/004-agent-docs-runbook/guide.md`, four parts, one document.

**Rationale**: it is the form the previous two documentation features used
(`walkthrough.md`, `demo.md`), so a reader who has met one has met all three. Every claim
in it carries a `module.symbol` anchor, and the way a reader checks an anchor is to search
the document for the module name — which works within a file and stops working across
five. Four files would also need a fifth to index them, and the index is the file that
goes stale first.

**Alternatives considered**:

- *Four separate documents.* Rejected: each part is between 4 and 9 KB; splitting produces
  five files where one serves, and an index that duplicates the contents of all four.
- *Fold everything into `review_agent/README.md`.* Rejected: it is a front door, and a
  front door that takes twenty minutes to read is a wall. The README keeps its summaries
  and gains a link — plus six corrections (C3-C6, C11, C15).
- *A generated documentation site.* Rejected outright by the spec's Out of Scope. It would
  add a build step to a repository that currently has none, and generated module docs
  answer none of the four questions asked.

### D2. Part order is Run, What, Where, Flow

**Decision**: *1. Run it by hand* → *2. What it does and will not do* → *3. Where things
live* → *4. How one review flows*.

**Rationale**: this is not the spec's priority order rearranged; it is the order in which a
reader's questions arrive. P1 is first because the person who opens this document is
usually mid-task with a pull request waiting. The second question, invariably, is "what is
it about to do to that pull request" — the capability statement, P4 by priority but second
by need. The two reference parts follow, because nobody reads a structure map first.

**Alternatives considered**: the spec's literal P1-P4 order puts the structure map in front
of the capability statement — rejected, it front-loads reference material. Code-flow-first
(the classic architecture document) was rejected for the same reason: it is the part most
readers never need.

### D3. Anchors are `module.symbol`, line numbers only where they are pinned

**Decision**: a claim in `guide.md` cites `output_layer.build_inline_comments`, not
`output_layer.py:96-160`. Line numbers appear only inside the Verification Record and the
Correction Register, both of which are stamped with the commit they were read at.

**Rationale**: this repository has already proved the failure mode. `CLAUDE.md` cites
`config.py:425` for the API-version default, which today lives at `config.py:473` — the
citation is 48 lines stale and the claim it supports is still true. A symbol survives every
edit that does not rename it; a line number survives the next insertion above it. Where a
line number genuinely helps (the register's evidence column), it is pinned to `33535f0` so
a reader knows what it was true of.

**Alternatives considered**: line numbers everywhere (rejected — demonstrably rots);
no anchors at all, "trust the prose" (rejected — that is precisely how fifteen corrections
accumulated).

### D4. Nothing real gets into the document

**Decision**: `.env` is surveyed **by key name only**; no value is read, printed, echoed
into a scratch file, or quoted. Every host, project, repository and identifier in the
deliverable is a placeholder. Every transcript is produced by `python -m tests.demo.run`,
which contacts nothing, or is redacted output already produced by `config.emit`.

**Rationale**: this is the near-loss the Constitution Check names. A runbook's whole
subject is credentials, and the most helpful thing an author can do — paste the working
`.env` and a real transcript — is the one thing that breaches Principle V in the artifact
most likely to be copied into a chat window. The discipline has to be a decision taken
before writing, not a review step afterwards, because a redaction pass over a document that
was written with real values still leaves them in the git history.

**How it was held during planning**: the only `.env` command run was a key-name extraction
(`grep -oE '^[A-Za-z_][A-Za-z0-9_]*='` piped to `sort`). Its output — ten names, no values
— is what C13 and C3 are built on.

**Alternatives considered**: "use real values and redact before commit" — rejected on the
history argument above. "Skip `.env` entirely" — rejected, C13 is one of the three blocking
findings and could not have been found any other way.

### D5. Three verification words, used literally

**Decision**: every claim in `guide.md` that a reader might act on carries one of:

| Marker | Means | Obligation |
|---|---|---|
| `[executed]` | A command was run on 2026-09-16 and its output is what the document shows | Quote the output, or a faithful excerpt |
| `[read]` | Read out of the code at `33535f0`; not exercised | Carry the `module.symbol` anchor |
| `[unobserved]` | Cannot be checked in the authoring environment | **Name the observation that would close it** |

**Rationale**: adopted wholesale from 003's standing note that its re-posting repair "is not
considered closed until a second live posting run reports `suppressed=6`". That convention
exists because 001 closed the same defect by reasoning and was wrong. A documentation
feature is nothing but claims, so it inherits the rule rather than re-learning it.

The obligation attached to `[unobserved]` is the part that matters. "Not verified" is a
shrug; "not verified — closes when a second `--post` run against the same pull request
reports `suppressed=N` and adds no comment" is a task someone can pick up.

**Alternatives considered**: verify everything before shipping (rejected — it would block
the deliverable on a live pull request, a live provider key, and a second posting run that
003 has been waiting on for a day); mark nothing (rejected — that is C1's whole lineage).

### D6. The runbook's primary command is `python -m review_agent --local`

**Decision**: the manual runbook's main path uses `python -m review_agent --local`. The
bootstrapping path (`python -m review_agent`, no flag) is documented immediately after it,
with the reason to prefer each. `python review_agent/main.py` — today's README quick start —
is documented as the third form, with its one real drawback stated.

**Rationale**: three entry points behave differently and the difference is invisible unless
someone says so.

| Command | What runs | Says which copy ran? | Needs |
|---|---|---|---|
| `python -m review_agent` | Clones `TFS_REPO_CODE_REVIEW_CodeReviewAgent`, re-executes the review **inside the clone** | Yes — `review logic: fetched ...` | The agent repository to be reachable and configured |
| `python -m review_agent --local` | The working copy, no fetch | Yes — `review logic: LOCAL WORKING COPY (--local)` | Nothing extra |
| `python -m review_agent.run` | The working copy, no fetch, no flag parsing of its own | Only when a bootstrap marker is set | Nothing extra; it is the child's entry point |
| `python review_agent/main.py` | The working copy | **No** — `agent_source` is `None`, so no provenance line is printed at all | Nothing extra |

A person running by hand has a checkout in front of them and wants *that* checkout to
review. `--local` does that and says so out loud. The bootstrap exists so a pipeline run
always reflects committed logic — a guarantee that matters on the build agent and costs a
clone on a laptop. `main.py` direct works, but it is the only form that reports nothing
about which logic ran, which is the one thing the design went out of its way to guarantee.

**Alternatives considered**: keep the README's `python review_agent/main.py` as the primary
(rejected — silent provenance, and it makes the bootstrap look optional when it is the
default); make the bootstrap primary (rejected — it fails on a machine that has not been
given the agent repository, which is a poor first step for a first-time operator).

### D7. PowerShell is the runbook's shell; Git Bash is the stated alternative

**Decision**: commands are written for PowerShell from the repository root. Where the two
shells differ the runbook gives both, inline, not in an appendix.

**Rationale**: the platform is Windows 11, the project's own automation is `.ps1`
(`.specify/init-options.json` sets `"script": "ps"`), and Git Bash is present. The
differences that actually bite are few and all environmental: `$env:TFS_API_VERSION='5.0'`
against `TFS_API_VERSION=5.0`, and path separators in anything the operator types by hand.
The Python commands are identical in both, which is worth saying once so a reader stops
looking for a second set.

### D8. Only two documents are edited; no module, no test

**Decision**: `review_agent/README.md` and `CLAUDE.md` are corrected in place. Nothing in
`review_agent/*.py` or `tests/**` is touched.

**Checked, not assumed**: no test asserts anything about this project's own README or
`CLAUDE.md`. The four test files that match "README" use it as **fixture data** — a
`README.txt` blob in the fake repository listing, a `README.md` in a checklist working copy
asserted *not* to be read as a checklist, and a filename in a selection-ordering case.
Correcting the real README therefore cannot move the suite, and SC-009's "532 before, 532
after" is a genuine guard rather than a coincidence.

**Rationale for editing them at all**: six of the fifteen corrections live in the README and
three of those are blocking. A correct guide sitting beside an uncorrected front door still
sends the first-time reader at the wrong token. `CLAUDE.md` is loaded into every session,
so a stale line there misleads the next agent as well as the next person.

---

## Part 2 — Verification Record

One entry per Correction Register row. Method, evidence, and status.

### C1 — The suite is 532 tests, not 401 `[executed]`

```
python -m pytest tests            -> 532 passed in 2.76s
python -m pytest tests --collect-only -> 532 tests collected in 0.49s
```

`CLAUDE.md` says "401 passing tests" twice; `specs/003-.../quickstart.md` says "401
passing, no live network" and calls the number "the one thing this feature cannot move
backwards". 003 moved it forwards by 131, which is the intended direction; the documents
simply were not updated after its own tasks landed.

**Correction**: both documents take 532. The guide states the count *and* the command that
shows it, because of C2.

### C2 — The documented test command prints no result `[executed]`

`pytest.ini` contains `addopts = -q`. The command every document prescribes,
`python -m pytest tests -q`, therefore runs pytest at **`-qq`**, which suppresses the
summary line entirely. Captured output ends:

```
............................                                             [100%]
```

No "N passed". The exit status is still 0, so the run is fine — but the operator asked to
confirm "401 passing" is given a command that cannot show them any number at all. This is
how a stale count survives four features: nobody ever sees the real one.

**Correction**: every document that gives this command drops the `-q`. The runbook's
install-check step (FR-024) uses `python -m pytest tests` and states `532 passed` as the
passing result.

### C3 — Posting requires a second token the README never names `[read]`

`config.py:463-466`:

```python
post_token = _env("TFS_PAT_FOR_PR") or ""
...
    problems.add("TFS_PAT_FOR_PR is required to post (omit --post for a dry run)")
```

The README's *Authentication — exactly one* table offers `SYSTEM_ACCESSTOKEN` **or**
`TFS_PAT` and stops there. An operator who configures exactly one, as instructed, completes
a dry run and then fails at `--post` with a message naming a variable that appears in no
table in the document they followed. `TFS_PAT_FOR_PR` is registered as a secret
(`config.SECRET_ENV_NAMES`) and is present in `.env`; it originates in `Req.md`, the
operator's own brief.

**Correction**: the README's authentication section gains the read/post distinction. The
runbook states it at the step where posting first happens, not in a configuration table
(FR-019).

**`[unobserved]`**: that the two tokens may be the same value in practice. Closes by a
manual run with `TFS_PAT_FOR_PR` set to the same PAT as `TFS_PAT` reaching a posted
comment.

### C4 — The repository variable is `TFS_REPO_CODE_SAMPLE` `[read]`

`config.py:373-374` resolves `_env("TFS_REPO_CODE_SAMPLE") or _env("TFS_REPO")`, and the
failure message at `:386` reads `TFS_REPO_CODE_SAMPLE is required (alias: TFS_REPO)`. The
README's *Always required* table lists only `TFS_REPO`; `.env` carries only
`TFS_REPO_CODE_SAMPLE`; `.env.example` carries only `TFS_REPO`. Three documents, three
different answers, both of which work.

**Correction**: canonical name plus alias, stated once, in all three places.

### C5 — The README's quick start bypasses the default entry point `[read]`

`__main__.py`: "The default path goes through the bootstrap so that a review always
reflects the latest committed logic (FR-012)". `bootstrap.main` clones
`config.agent_repo` and re-executes `python -m review_agent.run` inside the clone with
`PYTHONPATH` pointed at it; `config.py:437-441` makes
`TFS_REPO_CODE_REVIEW_CodeReviewAgent` **required** unless `--local` is passed or a
bootstrap marker is already set.

The README never mentions any of this. Its quick start and its CLI section both use
`python review_agent/main.py`, which reaches the review directly and skips the mechanism
the design considers the default — including the provenance line, which `main.main` only
prints when `agent_source is not None`.

**Correction**: G-A in the plan — the entry-point table (D6) is new material in the guide,
and the README's quick start gains the two forms it is missing.

### C6 — `--local` is undocumented `[read]`

`main.py:387-391` defines `--local`, "review with this working copy instead of the fetched
agent source". It appears in no README table, in no quickstart, and in `CLAUDE.md` zero
times. It is the flag a developer working on the agent needs on every single run, and the
flag the runbook makes primary (D6).

### C7 — `.env` is read from the current working directory `[read]`

`config.load_dotenv_if_present`: `root = repo_root or os.getcwd()`, then
`load_dotenv(os.path.join(root, ".env"), override=False)`. Run the agent from any directory
other than the repository root and every setting vanishes — into `missing required
configuration: ...`, a message that names the variables and says nothing about the working
directory. No document states this precondition.

**Correction**: the runbook's first step is where you stand, not what you install.

### C8 — `demo.md` exists `[read]`

`CLAUDE.md` says "**The deliverable**: `specs/003-checklist-repo-review-demo/demo.md` — not
yet written". The file is 16.6 KB, dated 2026-09-16, and `review_agent/README.md` already
links it under *Worked examples*.

### C9 — 003's header contradicts 003's own known-state section `[read]`

`CLAUDE.md`'s header calls 003 the active feature and describes G1 — "`checklist_docs.py`
imported by nothing" — as the gap it will close. Sixty lines later its Known-state section
says "`checklist_docs.py` **is wired in** — gap G1 is closed". The suite is green at 532 and
the offline demonstration prints a four-document inventory (C14). The header is describing
the plan; the body is describing the result.

**Correction**: 004 becomes the active feature; 003's entry moves to the prior-feature
section in the same shape 002's has.

### C10 — Exit 3 is defined and never returned `[read]` *(document is right)*

`errors.py:19-26` defines `EXIT_OK = 0`, `EXIT_BLOCKING_FINDINGS = 1`,
`EXIT_SETUP_FAILURE = 2`, `EXIT_DEGRADED = 3`. Every return in `main.main` (`:424-446`) is
0, 1 or 2 — a degraded review takes `log.done("degraded", EXIT_OK)` and returns 0. The
README's exit table correctly lists only three codes and explains why 0 covers both
outcomes.

Recorded so that a later reader does not "discover" `EXIT_DEGRADED` and wire it up as a
tidy-up: 001's gap G3 is deliberately open, and changing it would change the merge
behaviour of every consumer.

### C11 — Fingerprints no longer exclude the line number `[read]`

The README's *How it works* section states as a design note: "**Fingerprints exclude the
line number.** Between iterations an unrelated edit shifts a finding's line; a
line-sensitive fingerprint would re-post the same comment on every push."

`parser.py:302-303`:

```python
def code_issue_key(issue, line):
    return f"{issue.severity}@{line or issue.line}"
```

003 gave code issues the identity `severity@line` **because** they are the one finding kind
with no natural identifier — a rule identifier for a checklist violation
(`checklist_key`), `wi{id}:c{ordinal}` for a criterion (`criterion_key`), and severity plus
line for everything else. The README's note is still true of the other kinds and false of
this one, which is worse than being wrong everywhere: it reads as a guarantee.

**Correction**: the README's note takes the per-kind form. The guide's flow part states all
three identity schemes, and the residual risk — a code issue whose line moves is a new
comment — with G-D's unobserved status attached.

### C12 — `TFS_API_VERSION` defaults to 6.0, which 404s here `[read]` *(CLAUDE.md is right)*

`config.py:473`: `tfs_api_version=_env("TFS_API_VERSION") or "6.0"`. `CLAUDE.md` records
that 6.0 returns HTTP 404 on every endpoint against this collection and that the error
message misleadingly blames project, repo and PR id. The README frames `5.0` as something
to "try ... on an older server" — a contingency rather than this server's requirement, and
`.env` does not set it, so every manual run on this machine gets 6.0 unless the operator
intervenes.

**Correction**: the runbook sets `TFS_API_VERSION=5.0` at the configuration step, with the
404 symptom named next to it so the reader recognises it if they skipped ahead.

**`[unobserved]`**: the 404 itself was not reproduced during planning — no live call was
made. It is carried on `CLAUDE.md`'s authority, which records it as an afternoon already
spent. Closes by one live run at `6.0` producing the 404 and the same run at `5.0`
succeeding.

### C13 — `.env` does not carry three things a manual run needs `[executed, names only]`

Key names present, no value read:

```
LLM_API_KEY, LLM_MODEL, LLM_PROVIDER, TFS_BASE_URL, TFS_PAT, TFS_PAT_FOR_PR,
TFS_PROJECT, TFS_REPO_CODE_REVIEW_CodeReviewAgent,
TFS_REPO_CODE_REVIEW_CodeReviewChecklist, TFS_REPO_CODE_SAMPLE
```

Absent: `TFS_PR_ID` (so every manual run needs `--pr ID`), `TFS_API_VERSION` (so every
manual run gets the 6.0 that 404s — C12), and `DRY_RUN` (so preview is the default, which
is the safe direction).

Present and worth noting: `TFS_REPO_CODE_REVIEW_CodeReviewChecklist` in 003's corrected
spelling — the one-character defect S6 is fixed in both directions — and
`TFS_REPO_CODE_REVIEW_CodeReviewAgent`, which means the bootstrapping path (D6) is
configured on this machine even though nothing documents it.

`CLAUDE.md` gets this half right: it names `TFS_API_VERSION` and `TFS_PR_ID` as the two
values `.env` does not carry. It omits that a `--post` run also needs `TFS_PAT_FOR_PR` to
be more than present — it must be a token with write scope (C3).

### C14 — The offline demonstration runs `[executed]`

```
python -m tests.demo.run     -> exit 0
```

Eight phase lines (`pullrequest`, `workitems`, `checklists`, `rules`, `changes`, `prior`,
`llm`, `parse`), then a dry-run block whose summary names four checklist documents, one of
them skipped as unreadable, and reports six criteria, four violations, one code issue and
one false coverage claim. No network, no credential, no server.

This is the runbook's answer to FR-022, and it is the only transcript source the deliverable
is allowed to quote from (D4). What it does **not** demonstrate, and the guide must say so:
any TFS call, any provider call, any posting, and any of the three blocking corrections —
all of which live on the far side of a real server.

### C15 — Inline placement has two conditions, not one `[read]`

`output_layer.build_inline_comments` routes every finding through one closure:

```python
def route(kind, path, line, identity, body):
    resolved_path, resolved_line = _locate(path, line, reviewable, mapper)
    if not identity:
        ...  # summary_only, always
    fp = fingerprint(kind, path, identity)
    if resolved_path and resolved_line:
        inline.append(...)
    else:
        summary_only.append(...)
```

A finding is posted inline only if it has a **stable identity** *and* anchors to a changed
line. The README's routing table says "yes, if located" for five finding kinds, which was
true before 003 and is now incomplete: a finding with no identity goes to the summary even
when its line resolves perfectly, because a comment that cannot be recognised next run
would be re-posted forever.

`not_addressed` remains absolutely excluded, by a `continue` in the coverage loop
(`# not_addressed never comments (FR-016)`), guarded by
`tests/contract/test_routing_not_addressed.py`. That part of the README's table is right.

**Correction**: the routing table gains the identity condition. The guide's capability part
states the rule in the form FR-013 asks for — the rule the code applies, not the rule a
reader would guess.

---

## What this research did not establish

Three things are carried on someone else's authority or on none, and the guide will mark
each `[unobserved]` with its closing observation:

| Claim | Source | Closes when |
|---|---|---|
| 6.0 returns 404 against this collection | `CLAUDE.md` | One live run at 6.0 and one at 5.0 |
| Git needs an `Authorization` header here, not a prompt | `CLAUDE.md`, `003/research.md` R13 | One live checklist clone succeeding where `GIT_ASKPASS` would have been asked |
| A second posting run adds nothing (`suppressed=N`) | 003's tests only | A second live `--post` run against the same pull request reporting `suppressed` greater than zero and adding no comment |

The third is 003's own open item, inherited verbatim. This feature does not close it; it
makes sure the guide never claims it is closed.
