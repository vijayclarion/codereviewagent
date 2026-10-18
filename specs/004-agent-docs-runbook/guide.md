# The Agent: Structure, Flow, Capabilities, and How to Run It

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Verified against**: commit `33535f0`, 2026-09-16 — see [Verification Record](#verification-record)

---

## What this document is

Four questions, answered once, with every claim anchored to the code that proves it:

1. **[Run it by hand](#part-1--run-it-by-hand)** — from a clean checkout to a posted review
2. **[What it does and will not do](#part-2--what-it-does-and-will-not-do)** — findings, exits, limits
3. **[Where things live](#part-3--where-things-live)** — every file, and what owns which behaviour
4. **[How one review flows](#part-4--how-one-review-flows)** — stage by stage, including where it forks

**It is for the team's own operators and developers.** It assumes you can reach the TFS
collection and have a pull request in mind.

### What this document is not

| Go here instead | For |
|---|---|
| [`review_agent/README.md`](../../review_agent/README.md) | The front door. Shorter, and enough for someone who has run it before |
| [`002 walkthrough`](../002-pr-review-walkthrough/walkthrough.md) | One *executed* example against a real pull request, using **markdown** checklists. Verified end to end 2026-09-15 |
| [`003 demonstration`](../003-checklist-repo-review-demo/demo.md) | One *executed* example using **`.xlsx` / `.docx`** checklists, plus the offline demonstration |
| [`001 quickstart`](../001-pr-code-review-agent/quickstart.md) | History. Its setup section is superseded by Part 1 below |

The two worked examples are instances. This document is the general case: the procedure,
the map, and the rules.

### How to read a claim

Every claim you might act on carries two marks.

**An anchor** — `module.symbol`, not `file.py:120`. Line numbers rot: `CLAUDE.md` cites
`config.py:425` for a value that now lives 48 lines lower, and the claim it supports is
still true. Symbols survive everything but a rename.

**A marker** — one of three:

| Marker | Means |
|---|---|
| `[executed]` | A command was run on 2026-09-16 and this is what it printed |
| `[read]` | Read out of the code at `33535f0`, not exercised |
| `[unobserved]` | Could not be checked here — **and it says what would close it** |

`[unobserved]` is not a shrug. This project has twice believed something it had only
reasoned about, so an unverified claim must name the observation that would settle it.

---

# Part 1 — Run it by hand

Commands are **PowerShell, from the repository root**. Git Bash works identically except
for environment variables: `$env:TFS_API_VERSION='5.0'` in PowerShell,
`TFS_API_VERSION=5.0` in Bash. Every `python ...` command is the same in both.

## The four ways in, and which one you want

`[read]` — `bootstrap.main`, `run.main`, `main.main`

| Command | What reviews | Announces which copy ran? | Needs |
|---|---|---|---|
| `python -m review_agent` | Clones the agent repository and re-executes the review **inside the clone** | Yes — `review logic: fetched ...` | `TFS_REPO_CODE_REVIEW_CodeReviewAgent`, reachable |
| **`python -m review_agent --local`** | This working copy | Yes — `review logic: LOCAL WORKING COPY (--local)` | nothing extra |
| `python -m review_agent.run` | This working copy | Only when a bootstrap marker is set | nothing extra — it is the child's entry point |
| `python review_agent/main.py` | This working copy | **No.** `agent_source` is `None`, so nothing is printed | nothing extra |

**Use `--local`.** You have a checkout in front of you and you want *that* checkout to
review, and `--local` says so out loud on its first line.

The bootstrap (no flag) exists for the build agent, where a review must reflect committed
logic no matter what is on the machine — `bootstrap.main` re-executes rather than
manipulating `sys.path`, because by then the local modules are already imported and a path
trick would review with a mixture of two copies.

`python review_agent/main.py` — what the README's quick start shows — works, but it is the
only form that tells you nothing about which logic produced the review. That is the one
guarantee the design went out of its way to make.

---

## Step 1 — Stand in the right directory

```powershell
cd <your checkout>
git rev-parse --show-toplevel   # should print the same path you are in
```

**Why this is step 1**: `.env` is read from the **current working directory**
(`config.load_dotenv_if_present`, `root = repo_root or os.getcwd()`). Run from anywhere
else and every setting silently disappears. `[read]`

| Symptom | Cause | Fix |
|---|---|---|
| `missing required configuration: TFS_BASE_URL, ...` listing things you know are set | You are not in the repository root | `cd` to it and re-run |

That message names the variables and says nothing about the directory, which is why this is
worth its own step.

## Step 2 — Install

```powershell
python -m pip install -r review_agent/requirements.txt
python -m pip install -r review_agent/requirements-dev.txt   # to run the tests
```

Python 3.13 is what this was verified on; the code needs no version-specific features.

| Symptom | Cause | Fix |
|---|---|---|
| `SSLCertVerificationError` on any TFS call, later | A private internal CA that `certifi` does not trust | `pip install truststore`, or set `REQUESTS_CA_BUNDLE`. TLS verification is never disabled — a contract test forbids it |

## Step 3 — Preflight, before you spend a provider call

```powershell
python -m pytest tests
```

Expected: **`532 passed`** — the count recorded in the [Verification Record](#verification-record)
— in about three seconds, with no network. `[executed]`

**Do not add `-q`.** `pytest.ini` already sets `addopts = -q`, so `python -m pytest tests -q`
runs at `-qq` and prints **no summary line at all** — the output ends at `[100%]` and you
cannot see the number you came for. Every document in this repository prescribed the `-q`
form until this feature corrected them (C2) — which is how a stale count ("401") survived
four features. `[executed]`

| Symptom | Cause | Fix |
|---|---|---|
| Output ends at `[100%]` with no count | You used `-q` | Drop it |
| Any failure | Your checkout is not sound | Stop. Fix this before reviewing anything — a review from a broken tree proves nothing |

## Step 4 — Configure

`.env` sits in the repository root, is gitignored, and holds live credentials. **Never
commit it, never print it.** If it already exists on your machine, do not regenerate it —
add what is missing.

Settings, with placeholders standing in for real values:

| Setting | Example | Note |
|---|---|---|
| `TFS_BASE_URL` | `https://tfs.example.local/tfs/DefaultCollection` | |
| `TFS_PROJECT` | `ExampleProject` | |
| `TFS_REPO_CODE_SAMPLE` | `ExampleRepo` | **Canonical name.** `TFS_REPO` is accepted as an alias (`config` resolves `TFS_REPO_CODE_SAMPLE or TFS_REPO`); the failure message names the canonical one. The README listed only `TFS_REPO` until this feature corrected it (C4) `[read]` |
| `TFS_PAT` | *(a token)* | The **read** credential. Needs **Code (read)** and, to judge story coverage, **Work Items (read)** |
| `TFS_PAT_FOR_PR` | *(a token)* | The **write** credential — see step 7. Not needed for a preview |
| `LLM_PROVIDER` / `LLM_MODEL` | `claude` / `claude-sonnet-5` | |
| `LLM_API_KEY` | *(a key)* | Unless `ollama` |
| `TFS_REPO_CODE_REVIEW_CodeReviewChecklist` | `CodeReviewChecklist` | The checklist repository. Three older spellings are still accepted |
| **`TFS_API_VERSION`** | **`5.0`** | **Set this.** See below |

| Symptom | Cause | Fix |
|---|---|---|
| `TFS_REPO_CODE_SAMPLE is required (alias: TFS_REPO)` | Neither name is set | Set either; the message names the canonical one |
| `missing required configuration: LLM_PROVIDER, ...` | An incomplete `.env` | Set every variable the message lists |

### The two the defaults get wrong here

**`TFS_API_VERSION=5.0`.** The default is `6.0` (`config.load_config`), and against this
collection `6.0` returns **HTTP 404 on every endpoint**. The error says to check
`TFS_PROJECT`, `TFS_REPO` and `TFS_PR_ID` — all three can be perfectly correct. `5.0` and
below work. `.env` does not carry this setting, so every manual run gets `6.0` unless you
add it. `[unobserved — closes when one live run at 6.0 produces the 404 and the same run at
5.0 succeeds; carried on CLAUDE.md's record of an afternoon already spent]`

**`TFS_PR_ID` is not in `.env` either**, so pass `--pr ID` on every run. `[executed — .env
surveyed by key name only: ten names, no values read]`

## Step 5 — What your token must be allowed to do

`[read]` — `config.load_config`, `main._fetch_story`, `tfs_client`

| Scope | On | Missing it |
|---|---|---|
| **Code (read)** | `TFS_PAT` | Nothing works. Setup failure, exit 2 |
| **Work Items (read)** | `TFS_PAT` | **Degrades, does not fail.** The run says "No story coverage was assessed: ..." and reviews against the checklist anyway. Before feature 003 this raised and exited 2, losing the whole review |
| **Code (write)** | `TFS_PAT_FOR_PR` | Preview works; `--post` fails at configuration time |

The Work Items row is the one worth knowing. A checklist-only review is a real review, and
the run says so in its summary rather than going quiet — "every degraded outcome carries a
stated reason" is a project rule, not a courtesy.

## Step 6 — Preview

```powershell
python -m review_agent --local --dry-run --pr 1234
```

Preview is the default (`DRY_RUN` defaults to `true`), and preview issues **no write of any
kind** — a contract test enforces it. You should see the phase log, then the comments that
*would* be posted:

```
review logic: LOCAL WORKING COPY (--local)
ai-review run=- phase=config outcome=ok mode=dry-run auth=basic
ai-review run=- phase=pullrequest outcome=ok source=... target=... scope=parsed
ai-review run=- phase=workitems outcome=ok count=1 criteria=6
ai-review run=- phase=checklists outcome=ok documents=4 rules=7 skipped=1
ai-review run=1234.1 phase=rules outcome=ok applied=7 omitted=0
ai-review run=1234.1 phase=changes outcome=ok changed=2 reviewed=1 excluded=1 lines=65
ai-review run=1234.1 phase=prior outcome=ok posted=0 summary=False
ai-review run=1234.1 phase=llm outcome=ok chunks=1 retries=0
ai-review run=1234.1 phase=parse outcome=ok coverage=6 violations=4 issues=1 false_claims=1
ai-review run=1234.1 phase=post outcome=dry-run inline=6 suppressed=0 summary=create
```

Each line is a stage; [Part 4](#part-4--how-one-review-flows) maps them one to one.

| Symptom | Cause | Fix |
|---|---|---|
| Exit 2, `not found` | Wrong repository or PR id — **or** `TFS_API_VERSION` is still `6.0` | Check both. The 404 message blames the former and is often the latter |
| `phase=checklists outcome=degraded` | No checklist repository resolved, or nothing matched | The summary names which. It is a coverage-only review, not a failure |
| `authentication failed ... sign-in page` | Bad or expired credential | Reissue the PAT |

## Step 7 — Read the preview before you post

Two things in the preview tell you what will happen:

- **`inline=N`** — comments that will be attached to a line of code
- **`suppressed=N`** — comments this agent has already posted and will not repeat

Not every finding becomes an inline comment. Which ones do, and why, is
[Part 2](#what-becomes-a-comment). Read that once; it is the difference between expecting
nine comments and getting six.

## Step 8 — Post

```powershell
python -m review_agent --local --post --pr 1234
```

**Posting needs a second token.** `TFS_PAT_FOR_PR` is a *different variable* from
`TFS_PAT`. The README's authentication table did not mention it until this feature
corrected it (C3), which is why the usual first experience of `--post` was this:
`[read]` — `config.load_config`

```
ai-review setup failure: TFS_PAT_FOR_PR is required to post (omit --post for a dry run)
```

| Symptom | Cause | Fix |
|---|---|---|
| `TFS_PAT_FOR_PR is required to post` | The write credential is not set | Set it. It may be the same PAT as `TFS_PAT` if that token has Code (write) `[unobserved — closes when a run with both set to one token posts successfully]` |
| `not permitted to write ...` | The identity cannot comment on this repository | Grant **Contribute to pull requests** |
| Exit 0, no comment appears | You are still in preview | You passed `--dry-run`, or `DRY_RUN` is unset and defaulting to `true` — pass `--post` |

Comments are posted as **active** threads, so they appear in the normal review flow.

## Step 9 — Confirm, then run it again

On the pull request you should see the inline comments plus **one** summary discussion.

Now run the same command again, unchanged. **Expected**: the same comments are recognised
and not repeated —

```
ai-review run=1234.2 phase=post inline=0 suppressed=6 summary=update
```

Each finding is recognised by an identity that does not change between runs: a rule
identifier for a checklist violation, the criterion's number within its story for a
coverage finding, severity-and-line for a code issue. The summary is updated in place, not
duplicated.

**If more comments appear instead, that is the defect feature 003 repaired and you are the
first to see it recur.** `[unobserved — the repair is asserted by
tests/integration/test_us3_posting.py and test_us3_demo.py, and has never been observed
against a live pull request. Closes when a second live --post run reports suppressed
greater than zero and adds no comment]`

That wording is deliberate. Feature 001 closed this same defect by reasoning about the
fingerprint's inputs, and was wrong; 002 found it by running the thing twice.

## If you have no server at all

```powershell
python -m tests.demo.run
```

Exit 0, no network, no credential, no provider. It drives the whole pipeline against fixed
fixtures: four checklist documents (one deliberately unreadable), a linked story with six
acceptance criteria, two changed files, and a dry-run output showing six inline comments and
one summary. `[executed]`

**What it proves**: the review pipeline, document reading, rule selection, routing,
identity, and the summary's inventory.

**What it does not prove**: any TFS call, any provider call, any posting, and none of the
three things that actually block a first manual run — the second token, the working
directory, the API version. Those live on the far side of a real server.

---

# Part 2 — What it does and will not do

**A reviewer aid, not a merge gate.** It reasons over diff text and cannot run anything, so
a human always decides the merge. Defaults are preview and non-blocking.

The headline case is a **false coverage claim**: the pull request description says an
acceptance criterion is covered, and the diff does not implement it.

## What becomes a comment

`[read]` — `output_layer.build_inline_comments`

| Finding | Inline? | Summary | Can block? |
|---|---|---|---|
| False coverage claim | if identified **and** located | yes | yes |
| `possible_contradiction` with a criterion | if identified **and** located | yes | yes |
| Checklist violation | if identified **and** located | yes | no |
| `code_issue`, severity high | if located | yes | yes |
| `code_issue`, medium / low | if located | yes | no |
| `appears_addressed` | no | yes | no |
| `not_addressed` | **never** | counted | **never** |

"Can block" means: exit 1, and only when `FAIL_ON_CONTRADICTION=true`.

### The inline rule has two conditions, not one

A finding is posted inline only when **both** hold:

1. it has a **stable identity** — something that will still be the same string next run, and
2. its file and line **resolve to a line the pull request changed**.

Fail either and it goes to the summary. In particular, a finding with no identity reaches
the summary *even when its line resolves perfectly*, because a comment that cannot be
recognised on the next run would be re-posted forever. The README's table said "yes, if
located" — the whole rule before feature 003, and half of it since. Corrected by this
feature (C15).

### `not_addressed` never comments

Not "rarely" — never, by a `continue` in the coverage loop, guarded by
`tests/unit/test_routing_not_addressed.py`. A pull request routinely implements part of a
story; treating that as a defect would make the agent noise on most pull requests.

### How a finding is recognised next run

`[read]` — `parser.checklist_key`, `parser.criterion_key`, `parser.code_issue_key`

| Finding | Identity |
|---|---|
| Checklist violation | the rule identifier, or the normalised rule text |
| Coverage / false claim | `wi{work item id}:c{ordinal}` — the criterion's number **within its story** |
| Code issue | `{severity}@{line}` |

The third is the weak one, and deliberately so: a code issue has no natural identifier, so
severity-and-line is the best available. **A code issue whose line moves is a new comment.**
The README's standing note that "fingerprints exclude the line number" was true of the
first two kinds and false of this one; corrected by this feature (C11).

## Exit codes

`[read]` — `errors`, `main.main`

| Code | Meaning | What to do |
|---|---|---|
| **0** | Reviewed — **or degraded**. Findings or not | Read the summary. This is the normal outcome |
| **1** | Blocking findings, only with `FAIL_ON_CONTRADICTION=true` | Address the contradiction, or turn the setting off |
| **2** | Setup failure: configuration, credential, unreachable PR, no permission to post | Something must change before a review will *ever* work |
| **3** | **Defined and never returned.** `EXIT_DEGRADED` exists in `errors`; every return in `main.main` is 0, 1 or 2 | Nothing. Do not "fix" this — gap G3 is open on purpose, and returning it would change the merge behaviour of every consumer |

`0` covering both "reviewed fine" and "could not review" is deliberate: a provider outage
must not gate anyone's merge. What tells them apart is the summary and the phase log.

## What it will not do

| Limit | Value | What you see |
|---|---|---|
| Files reviewed | `REVIEW_MAX_FILES`, default **40** | The rest are listed as `unreviewed`, with the bound named |
| Diff lines | `REVIEW_MAX_DIFF_LINES`, default **3000** | Truncation is reported, not silent |
| Prompt size | `LLM_MAX_CHUNK_LINES`, default **1200** | Split into another provider pass, on file boundaries |
| Checklist text | `CHECKLIST_MAX_CHARS`, default **60000** | Lowest-ranked rules dropped; the count is in the summary |
| Excluded files | `REVIEW_EXCLUDE_PATTERNS` — env files, keys, certificates, lock files, generated and binary content | Never sent to the provider, and every skipped file is named |
| Runtime behaviour | — | It reads diff text. It cannot run your code, your tests, or your database |
| A run report on disk | **none is written** (gap G2) | Output is console and pull request only. 001's quickstart asks for `.review-reports/`; nothing produces it |
| A severity threshold | **none exists** (gap G3) | Inline versus summary is decided by identity and anchoring, not severity. `--inline-threshold` and `--report-dir` are not in `build_parser` |

The exclusion list is a safety net against an accidental commit, **not** secret scanning: it
matches on path only and will not spot a credential pasted into ordinary source.

Reviewing sends story text, checklist text, the pull request description, and non-excluded
diff text to the configured provider.

---

# Part 3 — Where things live

**Granularity**: files are listed individually where a reader chooses between them —
`review_agent/` and the repository root. `specs/` and `.specify/` are listed by directory,
because their contents are per-feature artifacts of a known shape. 159 files are tracked in
total.

## The package — `review_agent/` (20 modules)

| Module | Owns | Rule it carries |
|---|---|---|
| `__init__.py` | Version, package docstring | — |
| `__main__.py` | `python -m review_agent` — fetch, then review | — |
| `bootstrap.py` | Which copy of the logic reviews; re-executes inside the clone | Never falls back to local silently |
| `run.py` | `python -m review_agent.run` — review with no bootstrapping | Keeps the child from re-fetching itself |
| `main.py` | CLI, orchestration, phase log, exit codes | Exit codes are the contract |
| `config.py` | **The only module that reads the environment.** Secret registry, `emit`, redaction, console encoding | `test_import_boundaries.py` |
| `errors.py` | `SetupFailure` (exit 2) vs `DegradedReview` (exit 0) | — |
| `models.py` | Frozen dataclasses for every entity; invariants in `__post_init__` | A degraded state cannot exist without a stated reason |
| `tfs_client.py` | **The only module that speaks TFS REST** | `test_import_boundaries.py` |
| `source_fetch.py` | **The only module that invokes git.** Credential-safe shallow clone, scrubbed origin, cleanup | `test_import_boundaries.py` |
| `checklist.py` | Obtain a working copy of the checklist repository; turn documents into citable rules; fall back to the text path | Never opens a document itself |
| `checklist_docs.py` | **The only module that knows `.xlsx` / `.docx`** | `test_import_boundaries.py` |
| `diff_builder.py` | Blobs → unified diff, plus the line map inline anchoring needs | Diffs are computed locally, on purpose |
| `selection.py` | Exclusion list, review bounds, relevance ordering of files and rules | `test_excluded_files_never_sent.py` |
| `prompt_builder.py` | Assemble the prompt; chunk on file boundaries | |
| `llm_adapter.py` | **The only module that knows a provider's wire format** | `test_import_boundaries.py` |
| `parser.py` | Contract validation, one strict retry, false-claim derivation, finding identities | |
| `dedupe.py` | Recover prior feedback from the pull request; fingerprints | State lives on the pull request; the agent is stateless |
| `output_layer.py` | Render, route, print, post | `test_preview_makes_no_writes.py` |
| `textutil.py` | HTML → plain text, standard library only | |

Also in the package: `README.md`, `.env.example`, `requirements.txt`,
`requirements-dev.txt`.

### The five invariants

Enforced by `tests/`. Breaking one breaks a test, by design.

| Invariant | Test |
|---|---|
| `config.py` is the only module that reads the environment | `tests/contract/test_import_boundaries.py` |
| `tfs_client.py` is the only module that speaks TFS REST | `tests/contract/test_import_boundaries.py` |
| `llm_adapter.py` is the only module that knows a provider's wire format | `tests/contract/test_import_boundaries.py` |
| `checklist_docs.py` is the only module that knows `.xlsx`/`.docx` | `tests/contract/test_import_boundaries.py` |
| `source_fetch.py` is the only module that invokes git | `tests/contract/test_import_boundaries.py` (greps for the literal string) |
| No secret reaches stdout, logs, the prompt, or posted feedback | `tests/contract/test_no_secrets_leak.py` |
| Preview mode issues no write | `tests/contract/test_preview_makes_no_writes.py` |
| Excluded files are never sent to the provider | `tests/contract/test_excluded_files_never_sent.py` |
| TLS verification is never disabled | `tests/contract/test_tls_never_disabled.py` |
| `not_addressed` never produces a comment | **`tests/unit/test_routing_not_addressed.py`** — note the directory; `CLAUDE.md` files this row under `tests/contract/`, where it is not |

Any new output destination must route through `config.emit`, which redacts. A file writer
that calls `json.dump` directly bypasses the only thing stopping a token escaping.

## The tests — 532, grouped by what they prove

| Group | Proves | Files |
|---|---|---|
| `tests/contract/` (7) | The invariants above, plus that every matched checklist document is accounted for (`test_checklist_inventory.py`) and that preview survives a non-UTF-8 console (`test_output_encoding.py`) | A failure here means a design rule has been broken, not a bug introduced |
| `tests/integration/` (7) | The user stories end to end against fakes: reviewing a corpus, combining checklists, posting and re-reviewing, the demonstration, and four misconfigurations producing four different messages | A failure means the pipeline changed behaviour |
| `tests/unit/` (14) | One module each: config, parser, selection, dedupe, diff builder, LLM adapter, both document readers, source fetch, bootstrap, auth modes, models, text util, and `not_addressed` routing | A failure is local |
| `tests/demo/` | `run.py` — the self-contained demonstration, also driven by an integration test | |
| `tests/fixtures/` | The fake TFS client, the pull request fixture package, and `docs_builder.py`, which builds real `.xlsx` and `.docx` bytes in memory | Fixture data, not assertions |

No test touches the network.

## Everything else

| Path | What it is |
|---|---|
| `CLAUDE.md` | Standing context loaded every session: active feature, the settings this server needs, known defects, invariants |
| `Req.md` | The original brief, in the operator's own words. It is where `TFS_REPO_CODE_SAMPLE` and `TFS_PAT_FOR_PR` come from |
| `pytest.ini` | `testpaths = tests`, `addopts = -q` — the reason step 3 drops `-q` |
| `.gitignore` | `.env` and keys first. Keep it that way |
| `specs/001-pr-code-review-agent/` | The agent itself: spec, plan (Gap Analysis), research, data model, contracts, quickstart |
| `specs/002-pr-review-walkthrough/` | The markdown-path walkthrough |
| `specs/003-checklist-repo-review-demo/` | The document-path demonstration |
| `specs/004-agent-docs-runbook/` | This document and its planning artifacts |
| `.specify/` | Spec-kit machinery: templates, scripts, the git extension, `memory/constitution.md` |

### Things that look broken and are not

| Path | Why it is like that |
|---|---|
| `specs/002-.../example-files/` | **Deliberately faulty sample code.** Never imported, never collected by pytest, never to be "fixed" |
| `specs/003-.../demo-files/` | Demonstration inputs, including a document that is **meant** to be unreadable — the demo's "skipped" row depends on it |
| `.specify/memory/constitution.md` | An unfilled template. Four features have passed the constitution gate vacuously; the five principles the code enforces are reconstructed in each plan |
| `tests/fixtures/pr_demo/` | A `README.txt` blob and other odd filenames — fixture data for selection and exclusion tests |

---

# Part 4 — How one review flows

## The straight-through path

Each row is one stage, and one line in the run log. `[read]` + `[executed]` — the signals
below were captured from `python -m tests.demo.run`.

| # | Stage | In → Out | Log line | Anchor |
|---|---|---|---|---|
| 0 | **logic** | argv → which copy reviews | `review logic: LOCAL WORKING COPY (--local)` | `bootstrap.main` |
| 1 | **config** | environment + `.env` + flags → frozen `Config` | `phase=config mode=dry-run auth=basic` | `config.load_config`, `main.main` |
| 2 | **pullrequest** | PR id → branches, description, declared scope | `phase=pullrequest source=... target=... scope=parsed` | `models.PullRequestContext.from_payload`, `models.DeclaredScope` |
| 3 | **workitems** | linked ids → stories and acceptance criteria | `phase=workitems count=1 criteria=6` | `main._fetch_story` |
| 4 | **checklists** | checklist repository → citable rules | `phase=checklists documents=4 rules=7 skipped=1` | `main._fetch_checklist`, `checklist.obtain_corpus` |
| 5 | **rules** | rules + changed files → the rules that relate to this change | `phase=rules applied=7 omitted=0` | `selection.select_rules` |
| 6 | **changes** | iteration → diffs, line maps, exclusions, bounds | `phase=changes changed=2 reviewed=1 excluded=1 lines=65` | `diff_builder.build_change_set`, `selection.select_reviewable` |
| 7 | **prior** | the pull request's own threads → what was already said | `phase=prior posted=0 summary=False` | `dedupe.read_prior_feedback` |
| 8 | **llm** | prompt(s) → validated response | `phase=llm chunks=1 retries=0` | `prompt_builder.build_prompts`, `parser.parse_with_retry`, `llm_adapter.call_llm` |
| 9 | **parse** | response → a `ReviewReport` | `phase=parse coverage=6 violations=4 issues=1 false_claims=1` | `parser.merge_results`, `parser.build_report` |
| 10 | **post** | report → comments printed or posted | `phase=post outcome=dry-run inline=6 suppressed=0 summary=create` | `main._deliver`, `output_layer.build_plan` |
| 11 | **done** | outcome → exit code | `phase=done outcome=... exit=0` | `main.main`, `PhaseLog.done` |

The demonstration transcript starts at **pullrequest**: it drives `run_review` directly,
so stages 0 and 1 — which belong to `bootstrap.main` and `main.main` — have no line there.
A real run prints all eleven.

Three things are less obvious than they look:

- **Diffs are computed locally.** The `changes` endpoint returns change *entries*, not patch
  text, and no on-prem endpoint reliably returns unified diff across TFS versions. Computing
  it from two blobs also produces the line map inline anchoring needs.
- **State lives on the pull request.** The agent is stateless; it recovers what it already
  said by reading its own threads, keyed on the `ai-review:` marker in the comment text
  rather than the author id — a manual run and a pipeline run post under different
  identities.
- **Rules are ranked against the files that survived selection**, so the corpus the model
  sees is the part that relates to what actually changed.

## Where the path forks

Nine departures. Each says what selects it, how you can tell, and where the run ends up.

| # | Condition | You can tell by | Outcome |
|---|---|---|---|
| **A1** | Bootstrap vs `--local` vs `main.py` direct | The `review logic:` line — or its absence | Same review, different provenance. A failed fetch is a setup failure, never a silent fall back to local (`bootstrap.main`) |
| **A2** | Documents unreadable or repository unresolved → the **markdown fallback** | `phase=checklists` reports `files=` instead of `documents=`/`rules=`, or `outcome=degraded` | The text path runs. If it also finds nothing: a coverage-only review, and the summary says which (`main._fetch_checklist`) |
| **A3** | No work item linked to the pull request | `phase=workitems count=0` | Checklist-only review. Summary: "No story coverage was assessed: ..." (`main._fetch_story`) |
| **A4** | Token cannot read work items (401/403) | `phase=workitems outcome=degraded count=0` | Checklist-only review, the missing access named. Before 003 this exited 2 and lost everything (`errors.WorkItemAccessDenied`) |
| **A5** | The pull request has no iterations | Run stops after `phase=pullrequest` | `DegradedReview` → said on the PR, **exit 0** (`main.run_review`) |
| **A6** | Nothing reviewable after exclusions and bounds | `phase=llm outcome=skipped chunks=0` | A real answer, not a failure: "There was nothing to review in this pull request: no reviewable text changes remained after exclusions" (`reviewable.is_empty`) |
| **A7** | Provider unreachable, or unusable after one strict retry | `phase=llm outcome=degraded retries=1` | Said on the pull request — "The review could not be completed: ..." — and **exit 0**. An outage must not gate a merge (`main._report_degraded`) |
| **A8** | Preview vs posting | `phase=post outcome=dry-run` vs no `outcome=` | Printed, or posted as active threads (`output_layer.print_plan` / `post_plan`) |
| **A9** | A repeat run finds its own earlier comments | `suppressed=N`, `summary=update` | Only new findings are added; the summary is edited in place (`dedupe.read_prior_feedback`, `output_layer.build_plan`) |

A4, A6 and A7 all end with something written where a person will see it. That is the rule:
**every skipped or degraded outcome carries a stated reason; silence is a defect.**

---

# Appendix

## Correction Register

Seventeen disagreements between an existing document and the code, found by survey on
2026-09-16 and recorded here so the next reader does not re-find them. Evidence and method:
[research.md](./research.md).

| # | Document | Said | Actually | Applied? |
|---|---|---|---|---|
| C1 | `CLAUDE.md`, 003 quickstart | "401 passing tests" | **532 passed** | ✅ `CLAUDE.md` |
| C2 | every document | `python -m pytest tests -q` | `-q` twice ⇒ no summary line printed at all | ✅ `CLAUDE.md`, here |
| C3 | README | Auth: "exactly one" of two variables | Posting also requires `TFS_PAT_FOR_PR` | ✅ README |
| C4 | README | `TFS_REPO` required | `TFS_REPO_CODE_SAMPLE` canonical, `TFS_REPO` alias | ✅ README |
| C5 | README | Quick start is `python review_agent/main.py` | That bypasses the bootstrap, the design's default path | ✅ README |
| C6 | README | Four CLI flags | Five — `--local` is undocumented | ✅ README |
| C7 | *(nothing)* | — | `.env` is read from the current working directory | ✅ here |
| C8 | `CLAUDE.md` | "`demo.md` — not yet written" | It exists | ✅ (during planning) |
| C9 | `CLAUDE.md` | Header describes 003 as unfinished | Its own known-state section says G1 is closed | ✅ (during planning) |
| C10 | README | Three exit codes | Correct. `EXIT_DEGRADED` is defined and never returned — recorded so nobody "fixes" it | ❌ by design |
| C11 | README | "Fingerprints exclude the line number" | True of two finding kinds, false for code issues (`severity@line`) | ✅ README |
| C12 | README | `5.0` is for "an older server" | It is this collection's requirement; the `6.0` default 404s | ❌ correct already; moved to where an operator meets it |
| C13 | *(nothing)* | — | `.env` carries no `TFS_PR_ID`, no `TFS_API_VERSION` | ✅ `CLAUDE.md`, here |
| C14 | — | — | The offline demonstration runs, exit 0 | ❌ correct already |
| C15 | README | Inline: "yes, if located" | Two conditions — identity **and** location | ✅ README |
| C16 | `main.py` `--help` epilog | "Required: ... `TFS_REPO`"; "Auth: ... exactly one" | Repeats C3, C4 and C5 **inside the program's own help text** | ❌ **it is code** — this feature may not edit `review_agent/*.py`. Left for a future feature |
| C17 | `CLAUDE.md` invariant table | `not_addressed` guarded from `tests/contract/` | The test lives in `tests/unit/` | ✅ here |

## Keeping this document true

When the code changes, this is what goes stale, and where:

| Change | Update |
|---|---|
| A module added, removed or renamed | Part 3's package table; the module count |
| An entry point added | Part 1's "four ways in"; Part 4 stage 0 |
| A `log.phase(...)` call added, removed or renamed | Part 4's stage table — **the one-to-one mapping is the point** |
| A configuration setting added | Part 1 step 4, or Part 2's limits table |
| A finding kind, or a change to routing or identity | Part 2's three tables |
| A contract test added | Part 3's invariant table and test groups |
| The test count moves | **The Verification Record below — and nowhere else.** Part 1 step 3 points at it rather than restating it. A number repeated in seven documents is how C1 happened |

If you correct something here, check whether `review_agent/README.md` says it too.

## Verification Record

**Commit**: `33535f0` · **Date**: 2026-09-16 · **Environment**: Windows 11, PowerShell,
Python 3.13.14, pytest 9.1.1

**Executed**

| Command | Result |
|---|---|
| `python -m pytest tests` | `532 passed in 2.76s` |
| `python -m pytest tests --collect-only` | `532 tests collected` |
| `python -m pytest tests -q` | Output ends at `[100%]`; **no summary line** (C2) |
| `python -m tests.demo.run` | Exit 0; ten phase lines; six inline comments, one summary, four documents, one skipped |
| `python -m review_agent --help` | Five flags including `--local`; the epilog carries C3/C4/C5 (→ C16) |
| `grep -oE "^[A-Za-z_]+=" .env` | Ten key **names**; no value read at any point |
| `git ls-files` | 159 tracked files, reconciled against Part 3 |
| Redaction gate — every `.env` value tested for presence in every document this feature touched, without printing any of them | **Pass.** The six sensitive values — base URL, project, both tokens, the sample repository, the provider key — appear nowhere. Four matched: two are repository names that are substrings of their own documented variable names, and two are the public provider and model identifiers |

**Read, not exercised**: every routing, identity, exit-code and limit claim in Part 2; the
stage anchors in Part 4; the entry-point table in Part 1; the invariant table in Part 3.
Each carries its `module.symbol`.

**Unobserved** — nothing here has been seen, and each says what would settle it:

| Claim | Closes when |
|---|---|
| `TFS_API_VERSION=6.0` returns 404 against this collection (C12) | One live run at `6.0` produces the 404 and the same run at `5.0` succeeds |
| `TFS_PAT` and `TFS_PAT_FOR_PR` may be the same token (C3) | One live `--post` run with both set to one PAT reaches a posted comment |
| A second posting run adds nothing | A second live `--post` run reports `suppressed` greater than zero and adds no comment |
| Git needs an `Authorization` header here rather than a prompt | One live checklist clone succeeds where `GIT_ASKPASS` would have been asked |

The third is feature 003's own open item, inherited verbatim. **No part of this document
claims it is closed.**

**Not verified at all**: every step of Part 1 from step 4 onward requires a live collection
and credentials that were deliberately not read during authoring. Steps 1, 2, 3 and the
no-server path are `[executed]`. The first person to run Part 1 against a real pull request
should update this record — and when they do, the first three rows above are what they are
in a position to close.
