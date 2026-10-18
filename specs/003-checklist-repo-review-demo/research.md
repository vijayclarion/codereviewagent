# Phase 0 Research: Checklist-Document Reviews from a Cloned Checklist Repository

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-16

Twelve items. Eleven are answered from the repository as it stands on this branch;
one (**R10**) has a half that requires the live collection and is scheduled as an
implementation action rather than resolved here.

Every "the agent does X" claim below was read out of the code, not inferred from a
prior feature's document. Where a 001 or 002 artifact says otherwise, the code wins —
that is the standing rule in `CLAUDE.md` and it cost this feature two of its findings.

---

## Baseline (T001)

`python -m pytest tests -q` on this branch before the first edit: **401 passed in 3.66s**,
no network. That is the number this feature may only increase.

## R1 — Which configuration name identifies the checklist repository

**Decision**: Resolve in this order, first non-empty wins:

1. `TFS_REPO_CODE_REVIEW_CodeReviewChecklist` — the operator's spelling, now canonical
2. `TFS_REPO_CODE_REVIEW_CodeReviewChecklistT` — the brief's spelling, retained
3. `CHECKLIST_REPO`
4. the `_git/{name}` segment of `CHECKLIST_REPO_URL`, via the existing `derive_repo_name`

When all four are empty, the run states **which name to set**, naming (1) only. Offering
an operator four names to choose from is not help.

**Rationale**: `config.py:380` reads `TFS_REPO_CODE_REVIEW_CodeReviewChecklistT`; `.env`
supplies `TFS_REPO_CODE_REVIEW_CodeReviewChecklist`. One trailing `T` is the entire
reason no checklist has ever been applied on this machine. The trailing `T` is a typo in
`Req.md` that propagated into the code; the operator's `.env` is the working
configuration and does not get to be wrong. This is the same precedence pattern
`config.py:318-322` already uses for `TFS_REPO_CODE_SAMPLE` / `TFS_REPO`, and R10 of
feature 002 records the reasoning: "renaming would have broken the only working
configuration on the developer's machine."

**Alternatives considered**:
- *Rename the `.env` variable.* Rejected — FR-001 forbids it, and the spec's Assumptions
  call the mismatch a defect in the agent.
- *Accept only the new name.* Rejected — silently breaks any pipeline configured to 001's
  spelling, which is exactly the class of failure this feature exists to make visible.

---

## R2 — How the documents are obtained

**Decision**: Shallow `git clone` through the **existing** `source_fetch.clone`, into a
temp directory removed by `source_fetch.cleanup` in a `finally`. No new acquisition code,
no new credential handling.

Two small changes inside `source_fetch.py`, which is the module that owns this:

- `clone(..., ref=None)` currently defaults `ref` to `"master"`. Make an unset ref omit
  `--branch` entirely so the remote's own default branch is taken. The checklist
  repository's default branch is not knowable from here, and guessing wrong produces
  "could not obtain X at master", which reads as a missing repository.
- Expose the resolved commit (already returned as `ClonedSource.commit`) to the caller so
  the run can state the reference the corpus was read at.

**Rationale**: `source_fetch.py:1-30` was written for exactly this: its own docstring says
"Two repositories are obtained at run time: the agent repository … and **the checklist
repository, whose documents it reviews against (FR-013)**". Only the first half was ever
wired — `grep` finds `source_fetch` imported by `bootstrap.py` alone. The credential
discipline is already solved and already tested: `GIT_ASKPASS` with the token in the child
environment only, `credential.helper=` disabled, origin scrubbed after clone, never in
argv, never on disk (`tests/contract/test_no_secrets_leak.py`, `tests/unit/test_source_fetch.py`).
Rebuilding any of that would be a downgrade.

Satisfies FR-002 (binary-capable), FR-003 (`--depth 1`), FR-004 (no credential on disk),
FR-005 (cleanup).

**Alternatives considered**:
- *Keep the REST item-fetch path (`tfs_client.get_file_on_branch`).* Rejected on the
  evidence: it returns `data.get("content", "")` — a `str`. A `.xlsx` is a zip container;
  what arrives after a JSON round-trip through a text field is not the file. This is the
  root of gap **G1** and the reason the spec states the acquisition path as a capability.
- *A sparse checkout or archive export.* Rejected — more git surface for a corpus of five
  documents totalling ~250 KB.

---

## R3 — Which files in the working copy are considered

**Decision**: Walk the clone recursively from `CHECKLIST_PATH` (default the repository
root) and match each **filename** against a comma-separated pattern list,
`CHECKLIST_FILE_PATTERN`. Matching is case-insensitive; `~$`-prefixed files (Office lock
files) are skipped without comment because they are not documents.

**Amended during implementation**: the default is `*.xlsx,*.docx` — **not**
`*.xlsx,*.docx,*.md` as first planned. Handing a markdown file to the document reader
produces a document reported as *skipped*, which would put a permanent, meaningless
"skipped" row in the inventory of anyone whose repository contains a README. Markdown is
not lost: when the document path yields nothing, the run falls back to the text path with
`*.md`, so an operator configured exactly as feature 002 left them keeps their checklist
with no change. Setting the pattern to `*.md` selects the text path outright. The deeper
reason markdown is not in the *default*: it yields no individually citable rule, and FR-017
requires every violation to cite one.

**Rationale**: FR-007 wants both formats by default, the operator able to adjust without a
code change, and **no configuration change when a document is added** — a filename
pattern gives all three, and a recursive walk means a new subfolder needs nothing either.
The existing default `*.md` (`config.py:434`) is a single pattern; splitting on commas is
backwards-compatible with every value anyone can currently have set. Markdown stays in the
default list because the spec's Assumptions retain the plain-text path.

**Alternatives considered**:
- *Hard-code the extension set, per 001's clarification that discovery be unconfigurable.*
  Rejected — FR-007 explicitly requires it to stay adjustable. Recorded here because 001's
  gap table (G1) says the opposite; this feature's spec supersedes it.
- *Match on full path rather than filename.* Rejected — `*.xlsx` matching
  `standards/api/Security.xlsx` is the behaviour an operator expects, and `selection._matches`
  already demonstrates the pain of getting this half-right.

---

## R4 — How a document becomes rules

**Decision**: Call `checklist_docs.read(filename, data)` unchanged. It is complete,
unit-tested (`tests/unit/test_checklist_docs_xlsx.py`, `..._docx.py`), and written against
the real corpus. This feature imports it and adds nothing to it.

What it already delivers, mapped to requirements:

| Requirement | Already satisfied by |
|---|---|
| FR-008 rules carry text, document, section | `ChecklistItem(title, detail, section, documents)` |
| FR-009 native id verbatim, else derived and marked | `checklist_docs.py:238-240`, `derived_id` flag |
| FR-010 severity carried when stated, absent otherwise | `:241`, `severity if severity in SEVERITIES else ""` |
| FR-011 commentary not carried into the review | `COMMENTARY_MARKERS`, `_is_commentary` (`:270-279`) |
| FR-012 unreadable document reported, run continues | `read()` returns `status="skipped"` with a reason; never raises |
| FR-013 read-but-empty distinct from unreadable | `status="no_rules"` vs `"skipped"` |
| Edge: multi-sheet workbook | `sheets_ignored` on `ChecklistDocument` |

The one gap: **FR-009's stability requirement is not met for spreadsheets.** A derived id
is `f"{stem}:{sheet}:{offset}"` (`checklist_docs.py:240`) where `offset` is the row number.
Insert a row and every id below it changes — which, once finding identity keys on the rule
id (R7), silently re-posts every comment below the insertion. Clarification Q5 chose
content-derived identifiers, so the derived form becomes
`f"{stem}:{sheet}:{digest}"` where `digest` is the first 8 hex characters of
`sha256(filename|section|title)`. The docx tolerant path's `f"{stem}:{ordinal}"`
(`:422`) changes the same way.

**Rationale**: content-derived survives insertion, deletion and reordering, and changes
only when the rule's own wording changes — at which point it *is* a different rule.
`hashlib` is already imported in `parser.py`; adding it to `checklist_docs.py` introduces
no dependency.

**Alternatives considered**:
- *Positional ids, human-readable (`Security.xlsx!Rules:12`).* Rejected by Q5; it is the
  current behaviour and it is fragile in exactly the way that matters now.
- *Position for display, content for identity.* Rejected by Q5 — two identifiers per rule,
  and the display half still drifts from what a finding cites.
- *Leave `checklist_docs.py` alone and derive elsewhere.* Rejected — it would put format
  knowledge in a second module and break `test_document_format_libraries_stay_in_one_module`
  in spirit if not in letter.

---

## R5 — What happens when the corpus is larger than one pass

**Decision**: Rank rules by relevance to the changed files, apply in rank order until
`CHECKLIST_MAX_CHARS` (default 60,000) is reached, and record every omitted rule on
`CombinedChecklist.dropped_for_budget`. Ranking lives in `selection.py` as
`select_rules(corpus, reviewable, budget)` and reuses the existing `_keywords` /
`_path_tokens` machinery.

The score for one rule, mirroring `score_relevance`'s shape so both halves of "what gets
sent" read alike:

```
score = 3.0 * |rule_tokens ∩ changed_path_tokens|
      + 2.0 * |rule_tokens ∩ changed_extension_tokens|   (cs, py, sql, …)
      + 1.0  if the rule states a severity
```

Ties break on `(-score, document_filename, item_id)` — **not** on corpus order, so the
result does not depend on the order the filesystem walk returned documents in.

**Determinism is the load-bearing property**, not the ranking quality. The same change
against the same corpus must select the same rules on every run and for every operator
(FR-016, SC-006). The tie-break is what delivers that; the scoring function only decides
which rules are worth keeping.

**Rationale**: clarification Q3. The corpus measured on 2026-09-15 was 165 rules /
48,485 characters against a 60,000 cap — so on today's corpus **nothing is dropped**, and
this path is exercised by tests rather than by the demonstration. That is worth saying out
loud: the budget code is not speculative (the cap is real and `config.py:436-439` records
a previous miscalculation that would have dropped a third of the corpus), but neither is
it on the demonstration's happy path.

**Alternatives considered**:
- *Severity first, then document order (recommended, not chosen).* Q3 chose relevance.
- *Document order only.* Simplest and fully deterministic, but a 200-rule corpus would
  apply whichever document sorts first, regardless of what the pull request touches.
- *Never omit — split across passes.* Rejected: multiplies provider calls and cost for a
  case the measured corpus does not reach, and complicates cross-chunk merging.

---

## R6 — How a violation cites a rule

**Decision**: Rules are rendered into the prompt as `- [SEC-WEB-01] <title> — <detail>`,
the response contract gains an optional `rule_id` on each checklist violation, and the
**filename is resolved from the corpus, never taken from the model**. A violation whose
`rule_id` (or, failing that, whose `item` text) matches no rule in the applied corpus is
recorded on `ReviewReport.dropped_citations` and reported in the summary, not posted as a
finding.

**Rationale**: FR-017 requires every violation to cite the rule identifier *and* the source
document's filename. The model is a poor source for the filename — `_checklist_section`
currently labels sections `## From: <filename>` and the model copies it into `source` with
whatever fidelity it feels like. The corpus already knows the authoritative answer:
`CombinedChecklist.by_id(item_id)` exists in `models.py:333` and is currently called by
nothing. `ReviewReport.dropped_citations` (`models.py:457`) likewise exists unused — both
were built for this and never wired.

Resolution is also what makes R7 work: an unresolvable citation has no stable identity, so
it must not become a durable inline comment.

**Alternatives considered**:
- *Trust `source` as returned.* Rejected — FR-017 becomes a hope, and a hallucinated
  filename is worse than no citation because it looks authoritative.
- *Require `rule_id`, degrade the response without it.* Rejected — a contract change that
  hard-fails would degrade every review the moment a provider omits one field. Optional
  with a text-match fallback keeps a wrong-shaped response cheap.

---

## R7 — Finding identity, so a second posting run suppresses what it already posted

**Decision**: Replace the free-text third argument of `fingerprint(kind, path, text)` at
its four call sites with a **stable key** chosen per finding kind:

| Finding kind | Identity key | Stable because |
|---|---|---|
| `checklist` | resolved `rule_id` (R6) | the rule id is content-derived (R4), not prose |
| `coverage` | `wi{work_item_id}:c{ordinal}` | the criterion's number within its story |
| `false-coverage` | `wi{work_item_id}:c{ordinal}` | same |
| `code` | `{severity}@{resolved_line}` | no natural identifier exists — see below |

`fingerprint`'s own signature and hashing do not change; what is handed to it does. The
marker written into the comment footer and read back by `dedupe.parse_markers` is
untouched, so comments posted by earlier runs remain parseable.

**The line question, stated plainly.** The clarification's wording for FR-028 is "the rule
identifier or criterion number … together with the file and line". Including the line for
*every* kind would regress feature 001's FR-030: `parser.py:194-205` excludes the line
deliberately, because an unrelated edit above a finding shifts it and a line-sensitive
identity re-posts the same comment on every push. So the line participates in identity
**only for code issues**, which have no identifier to key on and would otherwise fall back
to the provider's prose — the exact defect this item exists to fix. Everything with a
natural identifier stays line-independent. This satisfies FR-028's requirement (a second
run against an unchanged pull request recognises what it posted) and preserves FR-030's
(a later iteration does not re-post unmoved findings) for three of the four kinds.

The residual: two code issues of the same severity on the same line collapse into one
comment, and a code issue whose line moves between iterations re-posts once. Both are
narrower than today's behaviour, where **every** finding re-posts on **every** run.

**Rationale**: the defect recorded in `CLAUDE.md` — "two posting runs, `suppressed=0`,
9 inline comments where 5 were expected" — is fully explained by the four call sites in
`output_layer.py:113,123,130-131,135`, each of which passes regenerated provider prose.
Nothing else needs to change: `build_plan` already partitions on
`prior.posted_fingerprints` (`output_layer.py:303-305`) and the summary is already
deduplicated correctly.

Feature 001's gap **G4** recorded "no gap" here by reasoning about the fingerprint's
inputs — `fingerprint` excludes the line, therefore it is stable — without noticing that
its `text` argument is regenerated every run. The lesson is recorded in the plan's
Sequencing: this fix is not believed until the live run has posted twice.

**Alternatives considered**:
- *Include the line for every kind.* Rejected — regresses FR-030 for the three kinds that
  do not need it, with no gain: a rule id is already stable.
- *Ask the model to return a stable id for code issues.* Rejected — asking a generator for
  a stable identity across runs is asking it for the one thing it cannot give.
- *Record the fingerprint set in a run report instead of on the pull request.* Rejected —
  `dedupe.py:1-11` explains why the pull request is the only durable store: the agent is
  stateless and a build agent's working directory does not survive.

---

## R8 — When the credential cannot read work items

**Decision**: Add `errors.WorkItemAccessDenied(SetupFailure)`, raised by `tfs_client` when
a 401/403 comes back from a work-item endpoint. `main._fetch_story` catches it, returns no
work items plus a stated reason, and the review continues as a checklist-only review with
that reason in the notes, in the summary, and in the phase log.

The reason names the access: *"the credential cannot read work items (HTTP 403). Story
coverage was not assessed. Grant Work Items (read) to the token in TFS_PAT."*

**Rationale**: FR-023. Today `_fetch_story` (`main.py:97-108`) has no exception handling,
so a refused work-item read raises `SetupFailure` out of `run_review` and `main` exits 2 —
the whole review is lost, including the checklist half that would have worked. That is
neither what `CLAUDE.md` describes ("the review silently loses every requirement finding")
nor what FR-023 requires; both the code and the note were wrong, in different directions.
The client is the right place to classify, because it is the only module that knows which
endpoint answered (Principle IV).

SC-009's other half — a review whose checklist is unavailable still delivers story
coverage — already holds: `checklist.fetch_checklist` catches both error kinds and returns
an unavailable `Checklist` (`checklist.py:59-64`). The corpus path must keep that property.

**Alternatives considered**:
- *Catch bare `SetupFailure` in `_fetch_story`.* Rejected — it would also swallow a
  collection that is down, which is a genuinely different condition and should not be
  reported as a credential scope problem.
- *Pre-flight the scope before reviewing.* Rejected — an extra call that answers a question
  the first real call answers anyway.

---

## R9 — Two corpus shapes, one prompt builder

**Decision**: Give `Checklist` (markdown) and `CombinedChecklist` (documents) the same
three members — `available`, `unavailable_reason`, `prompt_text` — and have
`prompt_builder._checklist_section` and `selection.select_reviewable` depend only on those.
`main` builds the document corpus first and falls back to the markdown path only when the
checklist repository yields no documents at all.

`CombinedChecklist` gains `unavailable_reason` (it has none today) and renders
`prompt_text` from its applied items, grouped by document, with each rule prefixed by its
identifier per R6.

**Rationale**: the spec's Assumptions retain the markdown path, and 002's walkthrough is
still valid against it. Two acquisition paths and one consumer means the consumer must not
care which ran. Duck-typing on three members rather than a shared base class matches how
the rest of the package is written (frozen dataclasses, no inheritance anywhere except the
error taxonomy).

**Alternatives considered**:
- *Convert markdown files into `ChecklistItem`s too, one corpus type.* Attractive, and
  genuinely better — but it means parsing markdown into rules, which is a new parser, a new
  set of identifier rules, and a behaviour change for the 002 walkthrough. Out of scope;
  recorded here as the obvious next simplification.

---

## R10 — Executing the demonstration

**Decision**: Two executions with distinct jobs, per clarification Q2.

**Self-contained** — `tests/demo/` (a package, not a test module; `pytest.ini` collects
only `test_*.py`, so nothing in it is collected unless it is named that way). It builds
the sample documents with `tests/fixtures/docs_builder.py`, serves a sample pull request,
work item and diff through the existing `tests/fakes.FakeTfsClient`, drives
`main.run_review` in preview, and prints the observed output. Run by the operator as
`python -m tests.demo.run`, and asserted by one collected test
(`tests/integration/test_us3_demo.py`) that runs it twice and compares the finding sets —
which is SC-006 in executable form.

**Live** — one run against the collection and a real pull request in the sample
repository, proving working-copy acquisition, the work-item read, posting, and second-run
suppression. Its observed output is transcribed into the deliverable with each result
labelled as live.

**Two operational facts the live run depends on**, both discovered in the survey:

1. **The default entry point re-fetches the agent's own logic and re-executes it**
   (`bootstrap.py:1-18`). A live run started as `python -m review_agent` will review with
   the **committed** logic from `TFS_REPO_CODE_REVIEW_CodeReviewAgent`, not with this
   branch's working copy. So the live run either pushes this feature's code first or uses
   `--local`. The demonstration must say which, and say why, or the operator will conclude
   the checklist work never landed.
2. **`TFS_API_VERSION=5.0`** and **`TFS_PAT` with Work Items (read)** are both required and
   both default wrong — `CLAUDE.md` records that each costs an afternoon. They are
   prerequisites in the demonstration's gate, not troubleshooting entries.

**Open, requires the live environment** (scheduled as the first implementation action, as
002 did with its R1/R6): the checklist repository's default branch, its folder layout, and
whether the sample repository already holds artifacts from 002's demonstration that this
one's naming must avoid colliding with.

**Alternatives considered**:
- *Self-contained only.* Rejected by Q2 — it cannot prove acquisition, posting, or
  suppression, which are three of the four things this feature changes.
- *Live only.* Rejected by Q2 — nothing would be reproducible without credentials, and
  SC-006 would have no mechanism.
- *Put the harness under `specs/`.* Rejected — it must import `tests.fakes` and
  `tests.fixtures`, and a `specs/` import path that only works from the repository root is
  a trap. The deliberately faulty **sample code** still lives under `specs/`, as 002's does.

---

## R11 — Making every reduction in coverage visible

**Decision**: One "What this review applied" block, rendered by `output_layer` into both
the console preview and the posted summary, listing:

- the checklist repository and the reference its working copy was taken at, or the reason
  there is none;
- one line per document: `read (N rules)`, `read, no rules`, or `skipped — <reason>`;
- rules applied of rules read, and the omitted count when the budget bound;
- work items read and criteria judged, or the reason story coverage is absent;
- any citation the model produced that matched no applied rule.

Backed by `ReviewReport.documents`, `.dropped_for_budget`, `.dropped_citations` and
`.notes` — all four fields already exist (`models.py:452-458`) and three are never
populated.

**Rationale**: FR-014, FR-026, and SC-004's "zero such conditions produce a run that reads
as clean". This is Principle VII in its most literal form, and it is the single thing that
distinguishes this feature's output from today's, where a review against no checklist at
all prints a clean-looking summary.

**Alternatives considered**:
- *Log the inventory to the phase log only.* Rejected — the phase log is not posted, so a
  reader on the pull request would see the clean-looking summary and nothing else.
- *A written run report (001's gap G2).* Out of scope by the spec's own scope boundary.

---

## R12 — The demonstration's sample checklist documents

**Decision**: Generate them with `tests/fixtures/docs_builder.py`, committing a small
script under the feature directory that writes the two sample documents, rather than
committing the `.xlsx`/`.docx` binaries themselves.

The samples reproduce the two shapes that matter: a spreadsheet with a banner row, a real
header on row 2, and an **empty** `#` column (so the derived-identifier path of R4 is
exercised on the demonstration's happy path), and a Word document carrying `SEC-WEB-01`
style identifiers (so FR-017's verbatim-citation path is exercised).

**Rationale**: `docs_builder` exists, is tested, and its docstring already records why
generation beats committing: the real corpus is internal Najm standards and this
repository is cloned onto developer machines on every run. The same reasoning applies to
the demonstration. It also makes SC-010 ("adding a document causes it to be applied with
no configuration change") demonstrable — the operator generates a third document and
re-runs.

**Alternatives considered**:
- *Commit two small `.xlsx`/`.docx` files.* Simpler for the operator, but binaries in a
  repository that is cloned on every review, and a reviewer cannot read a diff of them.
- *Use the real corpus.* Rejected by the spec's Assumptions — internal, not committed here.

---

## R13 — the clone cannot authenticate the way `source_fetch` assumed

*Added 2026-09-16, from the live run. Not knowable from the repository.*

**Observation**: `git clone` against the checklist repository failed with
`fatal: Authentication failed`, while the *same* token read the *same* repository over
REST seconds earlier and listed every file in it.

**Cause**: `GIT_ASKPASS` answers git's password *prompt*, which only happens when the
server challenges with Basic. This collection challenges with Negotiate and NTLM only, so
git never asks, never sends the PAT, and reports the failure as though the credential were
wrong. The agent's own error text then compounded it by naming the token's scopes — which
were correct.

**Decision**: present the credential unasked, as an `Authorization: Basic` header, through
git's **environment config** (`GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_n` / `GIT_CONFIG_VALUE_n`,
git ≥ 2.31). `GIT_ASKPASS` is retained for servers that do challenge properly.

**Why not `-c http.extraHeader=...`**: it puts the credential in the process argument list,
where any other process on the machine can read it — the exact leak `source_fetch`'s
docstring already rejects. The environment route keeps the credential where it always was:
in the git child's environment, never in argv, never on disk.

**Consequence for the security story**: the credential now travels in **two** variables and
two forms — the raw token for askpass, the base64 Basic encoding for the header. Both are
registered as unprintable, and `tests/contract/test_no_secrets_leak.py` asserts argv, disk
and output for **both** forms. The module docstring was updated rather than left saying
"exactly one place".

---

## R14 — a code issue has no stable identity, and the provider demonstrates it

*Added 2026-09-16, from the live run. The self-contained run could not have found this.*

**Observation**: after R7's identity work, a second posting run against an unchanged pull
request reported `inline=3 suppressed=2`, not `inline=0`. Checklist findings and criterion
findings suppressed correctly. Code issues did not.

**Cause**: R7 keyed a code issue on `{severity}@{line}` for want of a natural identifier.
Between two runs minutes apart the provider changed all three inputs — it reworded each
issue, attributed it to a different line, and re-rated one severity. The identity was
built entirely from things the provider regenerates.

The self-contained run uses a fixed scripted response, so none of this could appear there.
This is precisely the class of defect clarification Q2 split the execution to catch.

**Decision**: match a code issue additionally against the **text already posted on the same
file**, which is readable back from the pull request and does not depend on the provider
saying the same thing twice. Token overlap on the prose alone, threshold **0.3**, measured
against the live pair: the reworded pair overlapped at 0.40, the most similar genuinely
different pair at 0.00.

Severity is deliberately excluded from the comparison — a reviewer who has read a finding
has read it whether it is now labelled medium or high.

**Alternatives considered**:
- *Key on `(path, severity)` alone.* Deterministic and simple, but it collapses two
  genuinely different findings of the same severity in one file into one comment. Withholding
  a real defect is the more expensive of the two available errors.
- *Ask the provider for a stable identifier.* Asking a generator for the one thing it
  cannot give — R7 rejected this already, and the live run is the evidence.

**Residual, stated rather than hidden**: two findings about the same file that overlap above
0.3 collapse into one comment. The threshold is measured, not guessed, but it is a
threshold.

**Result**: runs 4 and 5 both reported zero new comments. See
[demo-files/observed-live.md](./demo-files/observed-live.md) §4.
