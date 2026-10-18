# Developer Guide: how a review actually runs

**For**: someone who has just cloned this repository and needs to change something in it.
**Companion to**: [`local-mode-pr-review-activity.puml`](./local-mode-pr-review-activity.puml)
— the same flow as a picture.
**Written**: 2026-09-17, against commit `1aab763`.

---

## 0. What this is

This document follows one review from the moment you run the tool to the moment it produces
feedback, naming every method that runs and the file it lives in. It then answers three
questions that come up the first time anyone points this at a real pull request:

- **[What can the reviewer actually see?](#4-what-the-reviewer-can-see)**
- **[What happens to a very large change?](#5-a-very-large-change)**
- **[What happens when a model limit is exceeded?](#6-when-a-model-limit-is-exceeded)**

**The short answer to the first one, because it changes how you read every finding: a review
sees only the diff.** Each changed file arrives as a unified diff with three lines of context
around each hunk. A file the pull request did not touch is never fetched and never shown.
Section 4 has the detail and the consequences.

### What this is *not*

| You want | Read instead |
|---|---|
| To configure and run the tool for the first time | `specs/004-agent-docs-runbook/guide.md` **Part 1** — a nine-step runbook, verified end to end |
| To know which findings become inline comments, and the exit codes | 004 **Part 2** |
| A worked example against a real pull request | `specs/002-pr-review-walkthrough/walkthrough.md` |
| A worked example with `.xlsx`/`.docx` checklists, runnable with no server | `specs/003-checklist-repo-review-demo/demo.md` |

This guide assumes you can already run the tool. It is about what happens inside.

### How to read a claim

Every statement about behaviour carries an anchor — `file.py:line` or `file.method` — so you
can check it instead of trusting it. Each is also marked:

- **`[executed]`** — observed by running something on 2026-09-17. Listed in
  [section 8](#8-verification-record).
- **`[read]`** — established from the source, not run.
- **`[unobserved]`** — neither, with the observation that would close it stated.

That distinction is not pedantry. This project once recorded a defect as "no gap" by reasoning
about a function's inputs without running it twice; the defect was real and survived three
features. Reasoning is not observation, and this document says which it has.

---

## 1. The flow at a glance

### Render the diagram

```bash
java -jar plantuml.jar -tsvg docs/local-mode-pr-review-activity.puml
```

Any PlantUML-capable viewer opens it directly — the VS Code extension, the IntelliJ plugin.
Two things worth knowing:

- **Graphviz is not required.** The diagram uses PlantUML's modern activity syntax
  specifically so that `dot` need not be installed. If you have hit that requirement with
  other diagrams, it does not apply here.
- **Use SVG, not PNG.** The diagram is about 4180 pixels tall and PlantUML's PNG writer
  **silently truncates at 4096** — you lose the last two stages and the legend with no
  warning. If you must have a PNG, pass `-DPLANTUML_LIMIT_SIZE=8192`. `[executed]`

### The twelve stages

Every stage prints one line, so a console log answers "what happened" on its own. Stage names
and log lines are the same as 004 Part 4 uses, so you can move between the two documents
without translating.

| # | Stage | Owning file | What it does | Log line |
|---|---|---|---|---|
| 0 | **logic** | `bootstrap.py` | Decides *which copy* of the review logic runs | `review logic: LOCAL WORKING COPY (--local)` |
| 1 | **config** | `config.py` | Builds one frozen `Config` from `.env` + environment + flags | `phase=config mode=dry-run auth=basic` |
| 2 | **pullrequest** | `tfs_client.py`, `models.py` | Branches, description, the author's declared scope | `phase=pullrequest source=… target=… scope=parsed` |
| 3 | **workitems** | `main.py`, `textutil.py` | The linked story and its enumerated criteria | `phase=workitems count=1 criteria=6` |
| 4 | **checklists** | `checklist.py`, `checklist_docs.py` | The team's rules, as citable items | `phase=checklists documents=4 rules=7 skipped=1` |
| 5 | **iteration** | `diff_builder.py` | Which iteration, and which commit to diff against | *(folded into `changes`; the run id appears from here)* |
| 6 | **changes** | `diff_builder.py` | Blobs → unified diffs + the line map anchoring needs | `phase=changes changed=2 reviewed=1 excluded=1 unreviewed=0 lines=65` |
| 7 | **selection** | `selection.py` | Exclusions, bounds, relevance — what survives to be reviewed | `phase=rules applied=7 omitted=0` |
| 8 | **prior** | `dedupe.py` | What this agent already said on this pull request | `phase=prior posted=0 summary=False` |
| 9 | **llm** | `prompt_builder.py`, `llm_adapter.py`, `parser.py` | Assemble the request, send it, validate the answer | `phase=llm chunks=1 retries=0` |
| 10 | **parse** | `parser.py` | One `ReviewReport` from the answers | `phase=parse coverage=6 violations=4 issues=1 false_claims=1` |
| 11 | **post** | `output_layer.py` | Route findings, render, print or post | `phase=post outcome=dry-run inline=6 suppressed=0 summary=create` |
| 12 | **done** | `main.py` | The exit code | `phase=done outcome=… exit=0` |

All log lines above are `[executed]` — captured from `python -m tests.demo.run`, which starts
at stage 2 because it drives the pipeline directly. A real run prints all thirteen.

---

## 2. The flow, stage by stage

Each stage lists its methods **in call order**. A role that merely re-spells the method's name
would tell you nothing, so each says what the method is *for*.

### Stage 0 — logic (`bootstrap.py`)

**In**: `argv`. **Out**: a decision about which copy of the code reviews. **Log**:
`review logic: LOCAL WORKING COPY (--local)`

| Method | Role |
|---|---|
| `__main__` | Two lines. All `python -m review_agent` does is hand `argv` to `bootstrap.main` |
| `bootstrap.main` | Decides which copy of the review logic runs, and says so **before** running it |
| `main.build_parser` | Parses `argv` here as well as in stage 1 — bootstrap needs `--local` and `--pr` before a `Config` exists |
| `bootstrap.already_bootstrapped` | Stops a fetched child re-fetching itself forever |
| `config.bootstrap_marker` | Reads the marker environment variables, so even this stays inside the one module allowed to touch the environment |
| `bootstrap.local_source` | Builds the `AgentSource` that makes the run's provenance reportable |
| `bootstrap.run_fetched` | *(default path only)* Re-executes the review as a child process inside the clone |
| `run.main` | The reviewing entry point with no bootstrapping |

**Why re-exec rather than a `sys.path` insert**: by the time `bootstrap` runs, this copy's
modules are already imported. Injecting a path would review with a *mixture* of two copies —
exactly the ambiguity the design was asked to remove. `[read]` `bootstrap.py` module docstring

**Why `run.py` exists at all**: it is the target the child invokes. Keeping it separate from
`__main__` is what stops the child re-fetching. `[read]`

### Stage 1 — config (`config.py`)

**In**: the environment, `.env`, and the parsed flags. **Out**: one frozen `Config`.
**Log**: `phase=config mode=dry-run auth=basic`

| Method | Role |
|---|---|
| `main.main` | Orchestrates: parse, log, load config, review, choose the exit code |
| `main.resolve_dry_run` | Turns `--dry-run`/`--post` into `True`/`False`/`None`, where `None` means "fall through to `DRY_RUN`" |
| `config.load_config` | Builds the `Config`, collecting **every** problem before raising rather than failing on the first |
| `config.load_dotenv_if_present` | Reads `.env` for manual runs. Pipeline variables win over it |
| `config._env` | The single point of environment access |
| `config.register_secret` | Registers each token with the redactor, so `emit` cannot print it later |
| `config._resolve_checklist_repo` | Picks the checklist repository and remembers *which setting* supplied it, so an error can name the one to correct |
| `config._parse_int` / `_parse_bool` | Parse with a default and a minimum, adding to the problem list rather than raising |

**The rule this stage carries**: `config.py` is the only module that reads the environment,
enforced by `tests/contract/test_import_boundaries.py`. Reading `os.environ` anywhere else
breaks a test by design. `[read]`

### Stage 2 — pullrequest (`tfs_client.py`, `models.py`)

**In**: the PR id from `Config`. **Out**: branches, description, declared scope.
**Log**: `phase=pullrequest source=… target=… scope=parsed`

| Method | Role |
|---|---|
| `TfsClient.__init__` | The only object that speaks TFS REST. `purpose="read"` selects which of the two tokens it carries |
| `TfsClient.get_pull_request` | One GET. Everything about branches and description comes from this payload |
| `PullRequestContext.from_payload` | Extracts the branches and description, and derives the run id |
| `DeclaredScope.from_description` | Parses the author's own "Covered / Not in this PR" section — the claims the review later checks against the diff |

### Stage 3 — workitems (`main.py`, `textutil.py`)

**In**: the client. **Out**: work items with numbered criteria, **or a stated reason there are
none**. **Log**: `phase=workitems count=1 criteria=6`

| Method | Role |
|---|---|
| `main._fetch_story` | Recovers the linked work items **and the reason when there are none**, so a token without Work Items access loses the story half loudly instead of failing the whole run |
| `TfsClient.get_linked_work_item_ids` | The PR's work-item relations |
| `TfsClient.get_work_item` | One GET per linked item |
| `WorkItem.from_payload` | Builds the entity and **numbers** its criteria, so a finding can cite "criterion 4" stably across runs |
| `textutil.html_to_text` | TFS returns descriptions as HTML; the model gets text |
| `textutil.split_criteria` | Splits one acceptance-criteria blob into individually judgeable criteria |

**Worth knowing**: a credential scoped to Code only used to raise out of here and exit 2,
taking the checklist half of the review with it. It now degrades instead. `[read]`
`main._fetch_story` docstring

### Stage 4 — checklists (`checklist.py`, `checklist_docs.py`)

**In**: the config and client. **Out**: citable rules, or a stated reason there are none.
**Log**: `phase=checklists documents=4 rules=7 skipped=1`

| Method | Role |
|---|---|
| `main._fetch_checklist` | Runs the document path first, falls back to the markdown path, and **never raises** — a missing checklist degrades the review, it does not end it |
| `checklist.obtain_corpus` | Every rule the review measures against. Cleans up the working copy on **every** path, including the one where reading raised |
| `checklist._acquire` | Distinguishes the four acquisition failures — unconfigured, not found, not permitted, unreachable — because each has a different correction |
| `source_fetch.clone` | Clones the checklist repository, presenting the token as an `Authorization` header because this collection never prompts for a password |
| `checklist.matching_files` | Walks the working copy for `.xlsx`/`.docx` matching the configured pattern |
| `checklist._read_corpus` → `checklist_docs.read` | The only module that knows the document formats. One unreadable document is recorded and skipped, not fatal |
| `checklist._fold_duplicates` | Merges rules that say the same thing in two documents, keeping both sources |
| `checklist.fetch_checklist` | The markdown fallback |

**The rule this stage carries**: `checklist_docs.py` is the only module that knows `.xlsx` and
`.docx`. `checklist.py` never opens a document itself. `[read]`
`tests/contract/test_import_boundaries.py`

### Stage 5 — iteration (`diff_builder.py`)

**In**: the client and PR payload. **Out**: head and base commits. **Log**: none of its own;
the run id appears on every line from here.

| Method | Role |
|---|---|
| `TfsClient.get_iterations` | The PR's iterations. **No iterations is a degraded review**, not an error |
| `diff_builder.resolve_iteration` | Picks the latest iteration and the commit to diff against, falling back through `commonRefCommit` → `lastMergeTargetCommit` for older servers |
| `PullRequestContext.with_iteration` | Returns a **new** context carrying the commits — the entity is frozen, so this is a replacement, not a mutation |
| `PhaseLog.set_run_id` | From here every line carries `run=<pr>.<iteration>` |

### Stage 6 — changes (`diff_builder.py`)

**In**: the iteration id. **Out**: a `ChangeSet` of diffs plus a list of skipped files.
**Log**: `phase=changes changed=2 reviewed=1 excluded=1 unreviewed=0 lines=65`

| Method | Role |
|---|---|
| `TfsClient.get_iteration_changes` | Returns change **entries** — a path and a change type — **not** patch text |
| `diff_builder.build_change_set` | Turns entries into diffs. **This is where the context boundary is set** |
| `diff_builder._normalise_change_type` | TFS reports composites like `edit, rename`; takes the meaningful part |
| `diff_builder.looks_binary` | By extension first, then by a NUL byte in the content |
| `TfsClient.get_file_content` | Called **twice per file** — the blob at the iteration commit and the blob at the base commit |
| `diff_builder.build_file_diff` | Computes the unified diff with **three context lines**, and builds the diff-line → file-line map *while emitting*, because reparsing hunk headers is where off-by-one anchoring bugs live |

**Why the diff is computed here rather than fetched**: the `changes` endpoint returns entries,
not patches, and no on-prem endpoint reliably returns unified diff across TFS versions.
Computing it locally also produces the line map that inline anchoring needs. `[read]`
`diff_builder.py` module docstring

### Stage 7 — selection (`selection.py`)

**In**: the `ChangeSet` and the rule corpus. **Out**: a `ReviewableSet` — reviewed, excluded,
unreviewed. **Log**: `phase=rules applied=7 omitted=0`

| Method | Role |
|---|---|
| `selection.select_reviewable` | Applies exclusions, **then** ranks, **then** bounds — in that order, which is the fact a settings table destroys |
| `selection.match_exclusion` | Path matching only. A safety net against a certificate or an environment file leaving the building, not secret scanning |
| `selection._keywords` | The words the story and the checklist are *about*, stopwords removed |
| `selection.score_relevance` | Story words ×3, checklist words ×2, source file +1 |
| `selection.select_rules` | The same job one level down: ranks rules against the files that survived |
| `selection.rule_relevance` / `rule_cost` | Rank and price each rule against the changed paths and extensions, within `CHECKLIST_MAX_CHARS` |

Full detail in [section 5](#5-a-very-large-change).

**The rule this stage carries**: excluded files are never sent to the provider, enforced by
`tests/contract/test_excluded_files_never_sent.py`. `[read]`

### Stage 8 — prior (`dedupe.py`)

**In**: the client. **Out**: fingerprints and texts of what was already said.
**Log**: `phase=prior posted=0 summary=False`

| Method | Role |
|---|---|
| `dedupe.read_prior_feedback` | Recovers what this agent already said, by reading the pull request's own threads. **Best-effort**: unreadable threads mean a duplicate comment, which beats refusing to review |
| `TfsClient.get_threads` | All threads on the pull request |
| `dedupe.parse_markers` | Finds the `ai-review:` markers — keyed on the comment **text**, not the author id, because a manual run and a pipeline run post under different identities |
| `dedupe.strip_footer` | The comment without the marker footer, so prose can be compared |

**Note the discontinuity**: this stage's input comes from the *pull request*, not from stage 7.
The agent is stateless; its memory is the pull request it is reviewing. `[read]`

### Stage 9 — llm (`prompt_builder.py`, `llm_adapter.py`, `parser.py`)

**In**: everything gathered so far. **Out**: validated results, one per pass.
**Log**: `phase=llm chunks=1 retries=0`

| Method | Role |
|---|---|
| `prompt_builder.build_prompts` | One prompt per chunk. **Story, scope and checklist repeat in every one** |
| `prompt_builder.chunk_files` | Splits on file boundaries so a file is never judged from half of itself |
| `prompt_builder._story_section` | The linked story and its enumerated criteria, or the instruction to return empty coverage |
| `prompt_builder._scope_section` | The description and declared scope — what to verify, and what never to report |
| `prompt_builder._checklist_section` | The selected rules, each as `[IDENTIFIER] rule text` so a finding can be traced to its document |
| `prompt_builder._diff_section` | **The only place changed code enters the request.** Adds the part-of-N warning when the review is split |
| `parser.parse_with_retry` | One stricter retry, then degrade. Never returns partial findings: a shape we cannot trust is content we cannot trust |
| `llm_adapter.call_llm` | Sends one prompt, returns raw text. A provider that cannot be reached is a **degraded review, not a setup failure** |
| `llm_adapter._request_for` | The only place a provider's wire format is known. Four branches, one per provider |
| `llm_adapter._extract_anthropic` / `_extract_openai` / `_extract_ollama` | Pull the text out of each provider's envelope, so everything downstream is provider-blind |
| `parser.parse_response` → `extract_json` → `validate_payload` | Find the JSON, then reject anything not matching the contract shape |

**The rule this stage carries**: `llm_adapter.py` is the only module that knows a provider's
wire format. Switching provider is a configuration change plus one branch here — never a change
to the reviewing logic. `[read]` `tests/contract/test_import_boundaries.py`

### Stage 10 — parse (`parser.py`)

**In**: the per-pass results. **Out**: one `ReviewReport`.
**Log**: `phase=parse coverage=6 violations=4 issues=1 false_claims=1`

| Method | Role |
|---|---|
| `parser.merge_results` | Folds the per-chunk results into one, de-duplicating across chunks |
| `parser.build_report` | Assembles the `ReviewReport` every downstream stage renders |
| `parser.resolve_citations` | Matches each cited rule identifier to an applied rule; a citation matching nothing is **dropped and counted**, never reported as a finding |
| `parser._assign_ordinals` | Numbers each judged criterion against its story |
| `parser.match_claim` | Matches a declared-scope claim to the criterion it concerns, by distinctiveness rather than position |
| `parser.derive_false_coverage_claims` | The headline finding: the description claims an item is covered and the diff does not implement it |
| `main._build_inventory` | Builds `RunInventory`, whose `reductions` are **derived** from its fields — so a new way to cover less cannot be added without appearing in the summary |

### Stage 11 — post (`output_layer.py`)

**In**: the report and prior feedback. **Out**: printed or posted feedback.
**Log**: `phase=post outcome=dry-run inline=6 suppressed=0 summary=create`

| Method | Role |
|---|---|
| `main._deliver` | Builds the plan, then prints it or posts it |
| `output_layer.build_plan` | Splits located findings from summary-only ones and drops what was already said |
| `output_layer.build_inline_comments` | Routes each finding. Keys on an **identity** — rule id, criterion number, or severity and line — never on the provider's prose, which is regenerated every run |
| `diff_builder.map_line` | Validates a model-reported line against the file's real changed lines; `None` sends the finding to the summary rather than anchoring it to unrelated code |
| `output_layer.render_summary` | The one summary discussion: what was applied, the findings, and the `### Not sent for review` table |
| `output_layer.render_inventory` | What the run actually applied, **before** any finding — so a reader seeing no violations knows whether that means "none" or "none looked for" |
| `output_layer._already_said` | Prose-level suppression on top of fingerprint matching |
| `output_layer.print_plan` | Preview. Exactly the text that would be posted |
| `output_layer.post_plan` | Creates **active** threads; never resolves or deletes |

**Why identity, not prose**: keying a fingerprint on the provider's wording meant nothing
matched what had already been posted, so a second posting run repeated everything. See
`specs/003-checklist-repo-review-demo/contracts/finding-identity.md`. `[read]`

**The rule this stage carries**: preview mode issues no write, enforced by
`tests/contract/test_preview_makes_no_writes.py`. `[read]`

### Stage 12 — done (`main.py`)

| Method | Role |
|---|---|
| `PhaseLog.done` | The last line: outcome and exit code |
| `ReviewReport.has_blocking_findings` | Consulted **only** when `FAIL_ON_CONTRADICTION=true` — the sole route to exit 1 |

Exit codes are documented in 004 Part 2. The one that surprises people: **a degraded review
exits 0**, because a provider outage must not gate anyone's merge.

---

## 3. Where the path forks

Fourteen places the run can diverge. `Ref` cites 004 Part 4's fork identifier where the same
fork is recorded there; **the five marked *new* are documented here for the first time** — do
not go looking for them in 004.

| # | Stage | Condition | What happens | How you can tell | Ref |
|---|---|---|---|---|---|
| **D-A** | 0 | Which copy reviews? | `--local` or an already-bootstrapped child → straight on. Otherwise fetch and re-exec. **A failed fetch is exit 2** — never a silent fall back to local | The `review logic:` line, or its absence | A1 |
| **D-B** | 3 | Story linked and readable? | Readable → criteria judged. None linked, or 401/403 → checklist-only review, reason stated | `phase=workitems count=N outcome=` | A3, A4 |
| **D-C** | 4 | Which checklist path? | Documents → citable rules. Unreadable or unresolved → markdown fallback. Neither → coverage-only review | `documents=`/`rules=` vs `files=` vs `outcome=degraded` | A2 |
| **D-D** | 5 | Any iterations? | None → degraded, said on the PR, **exit 0** | Run stops after `phase=pullrequest` | A5 |
| **D-E** | 6 | Per file: reviewable? | Deleted, binary, or unretrievable → skipped and listed | `### Not sent for review` row | *new* |
| **D-F** | 7 | Path matches an exclusion? | Excluded, never sent to the provider | Same table, reason `excluded — matched <pattern>` | *new* |
| **D-G** | 7 | A bound already reached? | Over `REVIEW_MAX_FILES` or `REVIEW_MAX_DIFF_LINES` → unreviewed and listed | Same table, reason `bound` | *new* |
| **D-H** | 7 | Anything reviewable left? | Nothing → "There was nothing to review…", delivered like any other answer, **exit 0** | `phase=llm outcome=skipped chunks=0` | A6 |
| **D-I** | 9 | One pass or many? | Over `LLM_MAX_CHUNK_LINES` → N passes, each told it sees only part | `chunks=N` | *new* |
| **D-J** | 9 | Response usable? | Unusable → **one** stricter retry → still unusable → degraded, **exit 0** | `retries=1`, or `outcome=degraded` | A7 |
| **D-K** | 11 | Finding anchors to a changed line? | Anchors → inline comment. Does not → summary only. **Never dropped** | `inline=N` vs the summary's own list | *new* |
| **D-L** | 11 | Coverage entry is `not_addressed`? | **Never a comment.** It is neutral — a PR routinely implements part of a story | Absent from comments; present in the coverage table | — |
| **D-M** | 11 | Already said on this PR? | Suppressed; the summary is edited in place rather than duplicated | `suppressed=N`, `summary=update` | A9 |
| **D-N** | 11 | Preview or post? | `DRY_RUN` → printed. `--post` → active threads created | `outcome=dry-run`, or its absence | A8 |

**D-L is the one invariant not under `tests/contract/`** — it is asserted by
`tests/unit/test_routing_not_addressed.py`. It is also the rule that stops this tool being
noise on every partial pull request, which is the normal case. `[read]`

**The pattern across D-B, D-C, D-D, D-H and D-J**: every one ends with something written where
a person will see it. That is deliberate — *every skipped or degraded outcome carries a stated
reason; silence is a defect.*

---

## 4. What the reviewer can see

**A review judges a pull request from the change alone, not from the surrounding project.**

### What arrives for each changed file

A unified diff with **three lines of context** each side of every hunk — not the whole file.
`[read]` `diff_builder.py:14` (`CONTEXT_LINES = 3`), passed as `n=` to `difflib.unified_diff`.

Two exceptions to know:

- **A newly added file** is diffed against empty, so in practice the model sees **all of it**.
  `[read]` `build_change_set` sets `before = ""` when the change type is `add`.
- **A deleted file** is skipped entirely — there is nothing in the post-change file to comment
  on. It still appears in `### Not sent for review`. `[read]`

### Files the pull request did not touch

**Never fetched, and never shown.** `build_change_set` iterates the change entries the server
returned and nothing else; no other code path retrieves file content for review. `[read]`

### Fetched, then withheld — the distinction that matters

The tool **does** retrieve both complete versions of every changed file: the blob at the
iteration commit and the blob at the base commit. It needs them to compute the diff locally.
But only `ChangedFile.diff` is ever rendered into the request. `[read]`
`build_change_set` → `client.get_file_content` ×2; `prompt_builder._diff_section`

So "the tool has the whole file" and "the model sees the whole file" are different statements,
and only the first is true.

### What else is in front of the model

Four things, and nothing more:

| Source | What it makes possible | When it is missing |
|---|---|---|
| **The diff** | Every judgement about code | An empty one ends the run before this stage (D-H) |
| **The linked story** | Judging coverage, criterion by criterion | "No story coverage was assessed: …" — a checklist-only review |
| **PR description + declared scope** | Verifying the author's own "Covered" claims against the diff | "The description has no Covered / Not-in-this-PR section, so no coverage claim can be verified" |
| **The selected checklist rules** | Reporting violations against a citable rule | "No checklist was applied (…)" — a coverage-only review |

The boundary is also stated to the model itself, in `prompt_builder.SYSTEM_ROLE`: *"You reason
only over the diff text you are shown; you cannot run or test the code."* `[read]`

### When the review is split

If a change is large enough to need more than one pass, **each pass sees only its own files**
and is told so in as many words: *"you are seeing only some of the changed files; do not
conclude anything about files not shown."* `[read]` `prompt_builder._diff_section` when
`chunk_total > 1`

So a split review knows less than an unsplit one, even about the same change. See
[section 5](#5-a-very-large-change).

### What this tool structurally cannot judge

These are consequences of the boundary above, not defects. If you need one of them, this is not
the tool that will give it to you.

| It cannot tell you | Because | Do this instead |
|---|---|---|
| Whether a **caller elsewhere** is broken by the change | The caller's file is unchanged, so it is never fetched | A human reviewer; a compiler or test run |
| Whether an override honours its **base class** contract | The base class is unchanged | A human reviewer |
| Whether the change follows a **project convention** not written down | Only the changed region and the checklist rules are shown | Write the convention into a checklist document — then it *can* |
| Whether a **test exists** for the new behaviour | Unchanged test files are invisible | A coverage gate |
| Whether the changed code is **reachable at all** | Reachability is a whole-program property | A human reviewer; static analysis |
| Whether two changed files are **consistent with each other**, on a split run | Each pass sees only its own chunk | Narrow the scope, or review the pair by hand |

**Practical consequence for anyone writing checklist rules**: a rule that can only be judged by
looking at unchanged code will never be judged correctly. "Controller actions validate their
input" works — the controller is in the diff. "No two controllers register the same route" does
not — the other controller is not.

### A finding that cannot be anchored is not dropped

If the model reports a file and line that do not correspond to a changed line, `map_line`
returns `None` and the finding is routed to the **summary** instead of becoming an inline
comment. It is still reported; it just does not get attached to a line it might not belong to.
`[executed]` `diff_builder.map_line`, `output_layer._locate`

### Why the boundary is deliberate

Three reasons, all of them recorded in the code rather than inferred:

1. **A diff is what a reviewer reviews.** The tool's stated purpose is to judge a change
   against a story and a checklist, not to audit a codebase.
2. **Cost and latency.** Sending the surrounding project would multiply every request for
   context that is mostly irrelevant to the change.
3. **Anchoring.** Inline comments need a diff-line → file-line map, which only exists because
   the diff is computed locally. Whole-file context would not produce it.

If your team decides it wants broader context, that is a change to the tool — a separate piece
of work. This section exists so that decision can be taken deliberately rather than discovered
by surprise.

---

## 5. A very large change

**A large pull request is reduced, in a fixed order, and everything removed is reported.**

### The seven reductions, in the order they apply

| # | What it removes | Default | Setting |
|---|---|---|---|
| 1 | Files with nothing reviewable: deleted, binary by extension, binary by content, unretrievable | — | — |
| 2 | Files whose path matches an exclusion pattern | — | `REVIEW_EXCLUDE_PATTERNS`, `REVIEW_EXCLUDE_MODE` |
| 3 | *(ranking, not a cut — decides who survives 4 and 5)* | — | — |
| 4 | Files beyond the count bound | **40** | `REVIEW_MAX_FILES` |
| 5 | Files beyond the total diff-line bound | **3000** | `REVIEW_MAX_DIFF_LINES` |
| 6 | Checklist rules beyond the corpus budget | **60000** chars | `CHECKLIST_MAX_CHARS` |
| 7 | *(split, not a cut)* Changed lines per provider request | **1200** | `LLM_MAX_CHUNK_LINES` |

`[read]` `config.py:233` and `config.py:245-247`; `selection.select_reviewable`,
`selection.select_rules`; `prompt_builder.chunk_files`

The order is the part a settings table would lose. Exclusions run **before** ranking, so an
excluded file never competes for a slot. Ranking runs **before** the bounds, so which files
survive is decided by relevance and not by the order the server happened to return them. The
rule budget applies to a corpus **already narrowed** against the files that survived.

### How the survivors are chosen (step 3)

Each file scores: **story words ×3 + checklist words ×2 + 1 if it is a source file**, matched
against path tokens. Ties break **smallest change first**, deliberately — so the bound covers
more files rather than being eaten by one large one. `[read]` `selection.score_relevance`,
`selection.select_reviewable`

"Relevance" here means *related to the story or the checklist*, because those are the only two
things the review measures against.

### Nothing is dropped silently

Every reduction surfaces somewhere a person will see it:

| Reduction | Where it appears |
|---|---|
| 1, 2, 4, 5 | The `### Not sent for review` table in the summary, one row per file with its reason and detail |
| — | The summary headline: `Reviewed: PR #4242, iteration 1 · 1 of 2 changed files · story #4101` |
| 6 | `RunInventory.reductions` — "N of M rules were not applied, selected by …" |
| 7 | `phase=llm chunks=N` |

`[executed]` — from `python -m tests.demo.run`:

```text
### Not sent for review

| File | Reason |
|---|---|
| `/src/eShop.Api/appsettings.json` | excluded — matched appsettings*.json |
```

`RunInventory.reductions` **derives** its list from the inventory's fields rather than
accepting one from a caller, so a new way for a review to cover less than it appears to cannot
be added without showing up in the summary. `[read]` `models.RunInventory`

### How the split works (step 7)

`chunk_files` splits on **file boundaries**, so a file is never judged from half of itself.
Each pass carries the story, the scope and the whole rule corpus again, plus its own files, and
is told it is seeing only part of the change.

**The case worth knowing**: a *single file* larger than `LLM_MAX_CHUNK_LINES` on its own goes
into a pass alone, **oversized**, rather than being cut mid-hunk. That keeps the common case
clean at the cost of one over-large request — and it is the situation most likely to produce
the failure in the next section. `[read]` `prompt_builder.chunk_files` docstring

---

## 6. When a model limit is exceeded

**Nothing checks the size of a request before sending it, and a request the provider rejects
degrades the entire run — not just the pass that failed — reporting it and exiting 0.**

### Nothing measures a request against the model's limit

There is no token budget, no pre-flight size check, and no truncation. `prompt_builder` does
contain `estimated_size`, a chars÷4 approximation — and **it is called from nowhere**.

`[executed]` — `grep -rn estimated_size` over the whole repository returns exactly one line:
its own definition at `prompt_builder.py:192`.

Do not let the presence of chunking suggest otherwise. Which brings us to:

### Splitting counts changed lines, not tokens

`LLM_MAX_CHUNK_LINES` bounds **changed diff lines per pass**. But `build_prompts` re-emits the
story, the declared scope and the entire selected rule corpus inside the per-chunk loop — so
every pass carries the same fixed overhead. `[read]` `prompt_builder.build_prompts`

Splitting therefore shrinks the *variable* part of a request and not the *fixed* part. A corpus
near the 60000-character budget is in every single pass.

### Request limits vs the answer cap — not the same thing

| | Limit | Applies to |
|---|---|---|
| **Request** | None enforced by this tool | — |
| **Answer** | `max_tokens: 4096` | **`claude` only** |

`llm_adapter._request_for` sets `max_tokens` in the claude branch. The openai/azure body sends
`model`, `messages` and `temperature`; the ollama body sends `model`, `prompt` and `stream`.
Neither caps the answer. `[read]` `llm_adapter.DEFAULT_MAX_TOKENS`

Confusing the two sends people looking for the wrong setting.

### If the provider rejects the request

Any status ≥ 400 that is not retried raises `DegradedReview`. And here is the part worth
sitting with:

> **The whole run degrades, not the failed pass.** In `run_review`, the `except DegradedReview`
> encloses the *entire* `for prompt in prompts` loop, so the results of every pass already sent
> and parsed are discarded along with the one that failed.

`[read]` `main.run_review`

What you get: a notice on the pull request — "The review could not be completed: …" —
`phase=llm outcome=degraded`, and **exit 0**. A provider outage must not gate anyone's merge.
`[read]` `main._report_degraded`, `main.main`

### If the answer comes back truncated

A truncated answer is invalid JSON, so it fails as a *shape* problem rather than a size one:
`ContractViolation` → **exactly one** stricter retry, with an added instruction to emit only the
JSON object → if that also fails, `DegradedReview`. `[read]` `parser.parse_with_retry` loops
`for attempt in (1, 2)`

The retry never returns partial findings. A response whose shape cannot be trusted is a
response whose content cannot be trusted.

### Which failures are retried, and which are fatal

| Response | Behaviour | Exit |
|---|---|---|
| 429, 500, 502, 503, 504 | **3 attempts**, backoff 1 / 2 / 4 s, `Retry-After` honoured and capped at 30 s | 0 if all fail (degraded) |
| Connection error | Same 3 attempts, then degraded | 0 |
| **401, 403** | **Not retried** — "the AI provider rejected the credential" | **2** |
| **404** | **Not retried** — "no such model or endpoint" | **2** |
| Any other ≥ 400 | Not retried → degraded | 0 |
| Empty or non-JSON body | Degraded | 0 |

`[read]` `llm_adapter.call_llm`, `llm_adapter._retry_after`

### What you can actually change

There is no token setting to raise. The levers that genuinely reduce request size are the ones
from [section 5](#5-a-very-large-change):

- `REVIEW_EXCLUDE_PATTERNS` — keep irrelevant files out entirely
- `REVIEW_MAX_FILES` / `REVIEW_MAX_DIFF_LINES` — review less of a huge change
- `CHECKLIST_MAX_CHARS` — carry fewer rules, which shrinks **every** pass
- `LLM_MAX_CHUNK_LINES` — smaller passes, though the fixed overhead repeats in each

If one enormous file is the problem, the file bound will not help — it goes into a pass alone
regardless. Excluding it will.

---

## 7. Where everything lives

**004 Part 3 has the authoritative inventory**, one line per module, plus the invariants table
and the test grouping. This section does not repeat it. It re-cuts the same set by a different
question: *where in a review does this file get used?*

| Stage | Files |
|---|---|
| 0 — logic | `__main__.py`, `bootstrap.py`, `run.py`, `source_fetch.py` |
| 1 — config | `config.py`, `errors.py` |
| 2 — pullrequest | `tfs_client.py`, `models.py` |
| 3 — workitems | `main.py`, `textutil.py` |
| 4 — checklists | `checklist.py`, `checklist_docs.py`, `source_fetch.py` |
| 5, 6 — iteration, changes | `diff_builder.py` |
| 7 — selection | `selection.py` |
| 8 — prior | `dedupe.py` |
| 9 — llm | `prompt_builder.py`, `llm_adapter.py`, `parser.py` |
| 10 — parse | `parser.py`, `models.py` |
| 11 — post | `output_layer.py` |
| 0–12 — throughout | `main.py` (orchestration, phase log, exit codes), `config.py` (`emit`, redaction) |
| **No stage** | `__init__.py` (version and docstring), `README.md`, `.env.example`, `requirements.txt`, `requirements-dev.txt` |

`models.py` is listed twice on purpose: it is the frozen-dataclass layer every stage passes
data through, and only its most prominent uses are shown.

### Which files a rule constrains, and at which stage

| Stage | File | Rule | Enforced by |
|---|---|---|---|
| 1 | `config.py` | The only module that reads the environment | `tests/contract/test_import_boundaries.py` |
| 2, 8, 11 | `tfs_client.py` | The only module that speaks TFS REST | same |
| 9 | `llm_adapter.py` | The only module that knows a provider's wire format | same |
| 4 | `checklist_docs.py` | The only module that knows `.xlsx`/`.docx` | same |
| 0, 4 | `source_fetch.py` | The only module that invokes git | same (greps for the literal string) |
| 7 | `selection.py` | Excluded files are never sent to the provider | `tests/contract/test_excluded_files_never_sent.py` |
| 11 | `output_layer.py` | Preview mode issues no write | `tests/contract/test_preview_makes_no_writes.py` |
| all | `config.emit` | No secret reaches stdout, logs, the prompt, or posted feedback | `tests/contract/test_no_secrets_leak.py` |
| 2, 9 | *(any HTTP)* | TLS verification is never disabled | `tests/contract/test_tls_never_disabled.py` |
| 11 | `output_layer.py` | `not_addressed` never produces a comment | `tests/unit/test_routing_not_addressed.py` — note the directory |

**If you add an output destination**, route it through `config.emit`. A file writer calling
`json.dump` directly bypasses the only thing stopping a token escaping.

### Everything outside the package

See 004 Part 3, "Everything else" and "Things that look broken and are not". The short version
of the second: `specs/002-pr-review-walkthrough/example-files/` and
`specs/003-checklist-repo-review-demo/demo-files/` contain deliberately faulty inputs,
including a document that is *meant* to be unreadable — the demo's "skipped" row depends on
it. Never "fix" them.

---

## 8. Verification Record

### Executed on 2026-09-17, at commit `1aab763`

| What | Result |
|---|---|
| `python -m pytest tests` | **532 passed** in 5.92 s. Note: not `-q` — `pytest.ini` already sets it, and a second `-q` prints no summary at all |
| `python -m tests.demo.run` | Full offline review, no server and no provider. Source of every log line and rendered excerpt quoted above |
| `grep -rn estimated_size` | **One** hit — its own definition. The anchor for section 6's opening claim |
| Ledger method resolution | **91** `file.method` references extracted from the flow ledger and checked against the tree; all resolve |
| Diagram render | `java -jar plantuml.jar -tsvg …` → **renders clean, no errors**, 858 × 4179. Full content present including the final exit node and the legend |
| Diagram structural check | `@startuml`/`@enduml` 1/1 · `if`/`endif` 16/16 · `note`/`end note` 2/2 · `legend`/`endlegend` 1/1 · every `if` has a negative branch · 13/13 stage labels · 7 terminals · no non-ASCII · no remote references |
| Redaction | Every `.env` value tested for presence in both deliverables, without printing any. No sensitive value appears |

### Established by reading, not running

Everything marked `[read]` above. The largest group is section 6: **the behaviour when a
provider rejects an oversized request has not been observed here**, only traced through the
code.

### Unobserved, and what would close it

| Claim | Closes when |
|---|---|
| A provider rejects an oversized request with a status that reaches the `>= 400` branch, degrading the whole run and discarding parsed passes (section 6) | One live run is seen to print `phase=llm outcome=degraded`, post the notice, exit `0`, **and** show no findings from the passes that had already succeeded |
| A truncated answer is retried exactly once before degrading (section 6) | One live run is seen to log `retries=1` after a truncated response |
| The fetched (non-`--local`) path behaves as stage 0 describes | One run without `--local` against a reachable agent repository |

These are marked rather than asserted for a specific reason. This project once closed a defect
report by reasoning about a function's inputs; the defect was real, survived three features,
and was found by running the thing twice. Reasoning is not observation.

### A contract clause this deliverable does not meet

The diagram contract asked for a diagram "readable on one screen at 100%". The rendered
diagram is 858 × 4179 px and is **not**. Compacting it was tried and abandoned — two rounds of
trimming moved the height by under 2%, because it is driven by thirteen stages and sixteen
decisions, not by wording. Meeting the clause would mean dropping stages or decisions, or
splitting into a second diagram; both are forbidden elsewhere in the same specification.

It reads top-to-bottom in one column, so scrolling is the only cost. Recorded rather than
quietly passed: the clause was the wrong shape for an activity diagram of a pipeline this long.

### Corrections found while writing

| # | What was wrong | Where | Action |
|---|---|---|---|
| **005-C1** | `CLAUDE.md` described `specs/004-agent-docs-runbook/guide.md` as "not yet written". It is written — 623 lines, four parts, with its own verification record | `CLAUDE.md`, active-feature block | Corrected 2026-09-17. Left alone it would have sent the next reader to write 004's deliverable a second time |
| **005-C2** | The diagram, rendered to PNG at PlantUML's defaults, is silently truncated at 4096 px — losing stages 11 and 12 and the legend with no warning | This feature's own deliverable | Render instruction changed to `-tsvg`, and the reason stated in [section 1](#1-the-flow-at-a-glance) and in the `.puml` header |

No disagreement was found between this guide and 004, 003, 002 or 001.

### Keeping this true

The diagram and section 2 are two renderings of one description — the Flow Ledger in
`specs/005-agent-flow-developer-guide/plan.md`. **Change the Ledger, then both.** Editing one
alone is how two documents describing one system start to disagree, which this project has
already repaired once across seven documents.

The cheapest check that this document is still true:

```bash
python -m pytest tests        # 532 passed, and not -q
python -m tests.demo.run      # the log lines in section 1 should still match
```
