# Walkthrough: Create a Pull Request and Run the Review Agent

> **Verified end to end on 2026-09-15** against `review_agent 0.1.0`, on a real pull
> request in the sample repository. Sections 8, 9 and 10 record what actually happened,
> not what was expected — and in section 10 those differ.

A complete worked example: create a sample pull request with known defects, run the
review agent against it, confirm the findings, and clean up. About 30 minutes the
first time.

The agent is **a reviewer aid, not a merge gate.** It reasons over diff text and
cannot verify runtime behaviour, so a human always decides the merge. Its defaults
are preview mode and never blocking.

---

## 1. What this is

You will create, in the sample repository, a small change that is wrong in four
specific ways, and a user story it is supposed to satisfy. Then you will run the
agent and check that it finds what it should.

Everything you need is supplied. You should not have to invent any code, any text,
or any decision. If you do, that is a defect in this document — please record it.

**The headline finding** is the one the agent exists for: the pull request
description claims an acceptance criterion is covered, and the diff does not
implement it. Everything else is supporting detail.

**What you need**

| | |
|---|---|
| Time | ~30 minutes |
| Access | Contribute on the sample repository; permission to create and link work items |
| Tooling | Python 3.9+, `git`, a browser |
| Cost | One analysis call against a third-party provider — see section 3 |

---

## 2. Before you start

### Access

| You need | Where | Without it |
|---|---|---|
| **Contribute** on the sample repository | The repository's Security settings | You cannot push the branch or open the pull request |
| Permission to create and link work items | The project's work-item board | The agent finds no linked story, and the requirement findings — the entire point of this demonstration — never appear |
| **Code (read & write)** on the token used to post | The token's scopes | Section 9 fails; sections 1–8 still work |

Check these first. Every one of them fails late otherwise — at the point where you
have already done the work.

### Install

```bash
python -m pip install -r review_agent/requirements.txt
python -m pip install -r review_agent/requirements-dev.txt   # only to run the tests
```

### Configuration

`.env` holds live credentials and is gitignored. **Never commit it, never print it.**

Installation and the meaning of each variable are covered in
[feature 001's quickstart, Part 1](../001-pr-code-review-agent/quickstart.md) —
that document remains the authority and this one does not restate it. What matters
here is that these are set:

**Always required**

`TFS_BASE_URL`, `TFS_PROJECT`, `TFS_REPO_CODE_SAMPLE`, `TFS_PAT`,
`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, and either
`TFS_REPO_CODE_REVIEW_CodeReviewAgent` or the `--local` flag.

**Required for what you are doing**

| Variable | When |
|---|---|
| `TFS_PR_ID` | Unless you pass `--pr ID` on every run, which this walkthrough does |
| `TFS_PAT_FOR_PR` | To post (section 9). Needs Code (read & write) |
| `LLM_BASE_URL` | Only if `LLM_PROVIDER` is `azure` or `ollama`. **Not needed for `claude`** |
| `TFS_API_VERSION` | **Set it to `5.0` on this server.** See below — this one will waste an hour if you miss it |
| `TFS_PAT` scopes | Needs **Work Items (read)** as well as Code. See below |

### Known-outstanding corrections

As shipped, **the agent cannot start.** Two corrections are outstanding and a human
must apply them to `.env` by hand — do not regenerate the file, it holds live
credentials:

| Change | From | To | Why |
|---|---|---|---|
| **Add** `LLM_PROVIDER` | absent | `claude` | Required unconditionally (`config.py:359-361`). Without it the agent stops before contacting anything |
| **Correct** `LLM_MODEL` | `claude-sonnet-4-6` | `claude-sonnet-5` | Not a current model identifier. The adapter passes it straight through, so a 404 surfaces as "no such model or endpoint" — a misleading cause |

Current Claude model identifiers: `claude-opus-5`, `claude-sonnet-5`,
`claude-fable-5-1`, `claude-haiku-4-5-20251001`. Use `claude-sonnet-5` for the
default balance, `claude-opus-5` where review quality matters more than throughput.

### Two more that cost an afternoon if you miss them

**`TFS_API_VERSION=5.0`.** The agent defaults to `6.0` (`config.py:425`) and this
server rejects it. Observed: `6.0` → HTTP 404; `5.0`, `4.1`, `4.0`, `3.2`, `3.0`,
`2.0`, `1.0` → all `200`.

What makes this expensive is the error message. The agent reports:

```
not found: .../pullRequests/<id> (HTTP 404)
  -> check TFS_PROJECT, TFS_REPO, and TFS_PR_ID
```

All three of those can be perfectly correct. The API version is not mentioned.

**`TFS_PAT` needs Work Items (read).** The agent reads the linked story with the
*read* token, not the posting token. A `TFS_PAT` scoped to Code only returns `401`
on every work-item endpoint, and the run degrades to a review with no requirement
findings at all — which, with the checklist source also yielding nothing, means a
review that finds almost nothing and looks like it worked.

Quick check — Code scope alone gives `200` on the first and `401` on the second:

```
GET <base>/<project>/_apis/git/repositories/<repo>?api-version=5.0
GET <base>/<project>/_apis/wit/workitemtypes?api-version=5.0
```

### Confirm before you spend anything

```bash
python -m pytest tests -q                     # expect 401 passing, no network
python review_agent/main.py --dry-run --pr 1  # expect it to get past configuration
```

The second command validates configuration before contacting anything, so it costs
nothing.

> **It reports problems in rounds, not all at once.** Several checks are skipped
> while `LLM_PROVIDER` is unset (`config.py:369-376`), so fixing one thing can
> reveal the next. Run it again after each fix until it stops complaining about
> configuration. This is the single most confusing thing about first-time setup.

---

## 3. What leaves your network

**This demonstration sends your code to a third party.** Before you create anything,
be clear about what that means:

- The **diff** of the sample change — every changed line.
- The **acceptance criteria and description** of the linked work item.
- The **pull request description**.

These are sent to the analysis provider named in `LLM_PROVIDER`, over the internet,
outside your corporate network. The agent states which service will receive content
at startup.

Files matching the exclusion patterns are never transmitted — that is enforced by a
contract test, not a convention (`tests/contract/test_excluded_files_never_sent.py`).
No credential is ever sent: every secret is redacted on the way out
(`tests/contract/test_no_secrets_leak.py`).

For this walkthrough that exposure is trivial — the sample code is invented and
carries nothing real. **On a production pull request it is not trivial**, and
whether it is acceptable is a policy decision for your organisation, not something
this document can answer for you.

---

## 4. The sample work item

Create a **User Story** on the project's work-item board. Copy these exactly.

**Title**

```
Sample: validate discount code at checkout (pr-review-walkthrough-YYYYMMDD)
```

Replace `YYYYMMDD` with today's date. That suffix is what stops repeated
demonstrations colliding with each other — yours and other people's.

**Description**

```
Customers can enter a discount code during checkout. Valid codes reduce the order
total. Invalid and expired codes are rejected with a clear, specific message.
```

**Acceptance criteria** — four, of which the change will correctly implement two:

```
1. A customer can enter a discount code on the checkout page.
2. A valid code reduces the order total by the stated amount.
3. An invalid code shows the message "That code is not valid."
4. An expired code shows the message "That code has expired."
```

Note the work item id. You need it in section 6.

### What each criterion is doing here

| Criterion | In the change? | Purpose |
|---|---|---|
| 1 | Implemented correctly | A review that flags everything teaches you nothing. These are the control |
| 2 | Implemented correctly | As above |
| 3 | Implemented, **wrong message** | Produces a contradiction finding — the one that lands in the summary rather than on a line |
| 4 | **Not implemented**, but claimed as covered | The headline: a false coverage claim |

Criteria 3 and 4 are different kinds of wrong, deliberately. Criterion 4 is absent;
criterion 3 is present and contradicts what was asked for. The agent reports them
differently, and seeing both is how you learn to read its output.

---

## 5. The sample change

The files are in [`example-files/`](./example-files/), next to this document. Copy
them into the sample repository — do not retype them. A typo in a deliberately
faulty line silently changes which finding appears, and you would have no way to
tell.

[`example-files/README.md`](./example-files/README.md) lists every planted fault
with the finding it should produce. Read it before you commit, so you know what you
are looking for.

Summary of what is wrong, and why each fault is there:

| Fault | Where | Expected finding | Placement | Why it is in the sample |
|---|---|---|---|---|
| **F1** | `discount.py` — no expiry check at all | `false-coverage` | either | The headline. Criterion 4 claimed covered, not implemented |
| **F2** | `discount.py` — invalid-code message is `"Invalid code."` not `"That code is not valid."` | `coverage` / `possible_contradiction` | **summary only** | The only finding guaranteed not to anchor to a line |
| **F3** | `discount.py` — bare `except Exception` swallowing every failure | `code` | either | A reliable inline finding that does not need the checklist corpus |
| **F4** | `discount.py` — unused import | `code`, low severity | either | Shows that severity does not control placement |

### Why placement is what it is

The agent decides inline-versus-summary by **whether a finding can be anchored to a
changed line**, not by how severe it is (`review_agent/output_layer.py:87-137`).
There is no severity threshold.

F2 is guaranteed to be summary-only because contradiction findings are routed with
an empty file path (`output_layer.py:126`), so they can never resolve to a line.
F4 is low severity and may well appear *inline* — that is not a bug, and if you
expected severity to keep it out of the diff, this is the thing to unlearn.

---

## 6. Create the pull request

Do these in order. The link in step 5 is not optional.

### 1. Branch and commit

```bash
git checkout -b sample/pr-review-walkthrough-YYYYMMDD
# copy example-files/discount.py into the sample repository
git add discount.py
git commit -m "Sample: apply discount code at checkout"
git push -u origin sample/pr-review-walkthrough-YYYYMMDD
```

**Confirm**: the branch appears under **Repos → Branches**.

### 2. Open the pull request

**Repos → Pull requests → New pull request**. Source is your sample branch; target
is **the repository's default branch** — whatever it is called here; do not assume a
name.

### 3. Title

```
Sample: apply discount code at checkout (pr-review-walkthrough-YYYYMMDD)
```

### 4. Description

Copy this exactly. It is parsed, and it drives the headline finding:

```markdown
Implements the discount code story.

## Covered
- Customer can enter a discount code
- Valid code reduces the total
- Invalid code shows a message
- Expired code shows a message

## Not in this PR
- Analytics for code usage
```

The fourth "Covered" line is **false** — the branch implements no expiry check. That
is the claim the agent exists to catch. The "Not in this PR" list is never flagged;
declaring something out of scope is not a defect.

**Confirm**: the pull request is **Active**. The agent will not post to a completed
or abandoned pull request.

### 5. Link the work item

**Overview → Work Items → Add**, then select the story from section 4.

**Confirm**: the story is listed on the pull request's Overview tab.

> **Do not skip this.** Without the link the agent retrieves no work item, and
> findings F1 and F2 — three quarters of what this walkthrough demonstrates — never
> appear. The run still completes and reports that no user stories were linked,
> which looks like a working run producing little.

Note the pull request id. Every command below needs it.

---

## 7. Preview the review

Preview performs the identical review and prints the findings locally. It cannot
write to the pull request — the run never constructs a client holding the posting
credential, and a contract test enforces it
(`tests/contract/test_preview_makes_no_writes.py`).

```bash
python review_agent/main.py --dry-run --pr <sample-pr-id>
```

Preview is the default at every level, so a run started by accident cannot post.

### Exit statuses

| Status | Meaning | Here |
|---|---|---|
| `0` | Review completed — **including a degraded run** | Expected |
| `1` | Blocking findings present. Only when `FAIL_ON_CONTRADICTION=true` | Only if you set that flag; the false coverage claim would trigger it |
| `2` | Setup failure — nothing works until you change a setting | Go to section 11 |

> **There is no exit status 3.** `EXIT_DEGRADED` is defined in the code and never
> returned (`errors.py:26`; `main.py:343-346`). A degraded review — including one
> where the checklist source yielded nothing — exits `0`. Some older documents say
> otherwise; they are wrong, and believing them would make a healthy run look failed.

### Expect a checklist warning

Your run will very likely report that the checklist source was unavailable and
continue with a degraded review. **Nothing is broken.** The agent currently searches
for `*.md` on branch `main` (`config.py:434-435`) while the checklist repository
holds `.xlsx` and `.docx` files. It finds nothing.

The reader for those formats exists and is fully tested; it is simply not wired in
yet (feature 001, gap G1). Until it is, **no checklist findings will appear at all**,
and this demonstration rests entirely on the requirement findings from your linked
work item. That is why section 4's criteria are designed the way they are.

---

## 8. What you should see

Observed on a real run, 2026-09-15, against `review_agent 0.1.0`. See section 13.

**Read for the finding, not the sentence.** The wording comes from a language model
and differs every run. What is stable is *which* findings appear and *where*.

### Run log

```
phase=pullrequest  outcome=ok        source=sample/... target=master scope=parsed
phase=workitems    outcome=ok        count=1 criteria=4
phase=checklists   outcome=degraded  files=0
phase=changes      outcome=ok        changed=1 reviewed=1 excluded=0 lines=55
phase=llm          outcome=ok        chunks=1 retries=0
phase=parse        outcome=ok        coverage=4 violations=0 issues=4 false_claims=2
phase=post         outcome=dry-run   inline=4 suppressed=0 summary=create
phase=done         outcome=complete  exit=0
```

`checklists outcome=degraded files=0` is expected — section 7 explains it. The run
still completes and exits `0`.

### Findings per planted fault

| Fault | Traces to | Finding | Severity | Placement | Observed |
|---|---|---|---|---|---|
| **F1** no expiry check | Criterion 4 | Coverage status `not_addressed`, plus a **false coverage claim** for "Expired code shows a message" | n/a | summary | ✅ |
| **F1** | Criterion 4 | Code issue — "no expiry logic whatsoever … This is a false coverage claim" | `high` | **inline** `/discount.py:12` | ✅ |
| **F2** wrong message | Criterion 3 | Coverage status **`possible_contradiction`**, plus a false coverage claim | n/a | **summary only** | ✅ |
| **F2** | Criterion 3 | Code issue — message text does not match the required wording | `high` | **inline** `/discount.py:39` | ✅ |
| **F3** bare `except` | — | Code issue — swallows all errors, hides failures from callers | `medium` | **inline** `/discount.py:50` | ✅ |
| **F4** unused import | — | Code issue — "Unused import 'json'" | `low` | **inline** `/discount.py:6` | ✅ |
| Checklist rules | — | — | — | — | ❌ **expected-absent**: 0 documents found (gap G1) |

### The two things worth learning from this table

**The `low`-severity finding was posted inline.** F4 is the least important thing in
the file and it got a line comment, while F2 — a direct contradiction of a stated
requirement — went to the summary. That is not a bug. Placement is decided by whether
the finding can be anchored to a changed line, never by severity. If you expected a
threshold to keep trivia out of the diff, there isn't one.

**Every finding traced back to a criterion or to the code.** Four faults planted, four
found, none invented. The agent also correctly left criteria 1 and 2 alone.

### The summary comment

One comment, containing: the coverage table for all four criteria with evidence
quoted from the diff; the false coverage claims; the code issues; a "Findings without
a specific location" section holding everything that could not be anchored; and an
explicit note that no checklist was applied.

It states plainly that `not addressed` is neutral — *"a pull request routinely
implements only part of a story, and these are not defects"* — and closes by
identifying itself as an automated aid, not a merge gate.

---

## 9. Post the review

Verified 2026-09-15.

```bash
python review_agent/main.py --post --pr <sample-pr-id>
```

Requires `TFS_PAT_FOR_PR` with **Code (read & write)**.

**This is visible to everyone who can see the pull request.** Comments arrive under
the posting identity and each one identifies itself as automated. Preview first —
this is the step that is awkward to retract.

### What was observed

```
phase=post  outcome=ok  inline=5 suppressed=0 summary=create
phase=done  outcome=complete  exit=0
```

On the pull request afterwards:

- **Exactly one summary comment**, carrying the `ai-review:summary` marker.
- **Inline comments on the correct file and lines** — each anchored inside the diff.
- Each comment ends with an automated-review footer and a fingerprint, e.g.
  `🤖 AI code review · ai-review:code:7ef662b5ba71`.
- No secret anywhere in any comment.

> **The count moved between runs.** Preview reported `issues=4`; this posting run
> reported `issues=5`. Same code, same criteria — the provider simply returned one
> more observation. Expect the exact count to vary by one or two. This matters in
> section 10.

Check under **Files** for the inline comments and **Overview** for the summary.

---

## 10. Run it again

Verified 2026-09-15 — **and this is where the agent does not do what you would expect.**

```bash
python review_agent/main.py --post --pr <sample-pr-id>
```

### What was observed

```
phase=prior  outcome=ok  posted=5 summary=True
phase=post   outcome=ok  inline=4 suppressed=0 summary=update
```

| | Expected | Observed |
|---|---|---|
| Summary comments | 1, updated in place | **1, updated in place ✅** |
| New inline comments | 0 | **4 ❌** |
| Total inline on the PR after two posting runs | 5 | **9** |

The agent **did** recover its prior state — `posted=5 summary=True` shows it read
back its own five comments — and it **did** update the summary rather than adding a
second one. But `suppressed=0`: it recognised none of the inline findings as ones it
had already posted, and posted four duplicates.

### Why

A finding's identity is `fingerprint(kind, path, text)` — kind, file path, and the
**text of the finding** (`review_agent/parser.py:194-205`). The line number is
deliberately excluded so that a finding survives line drift, which works.

But `text` is the language model's prose, regenerated on every run. It is never
byte-identical twice. Different text → different fingerprint → not recognised as
already posted.

The duplicates on the pull request show it plainly: the same defect appears at
`/discount.py:6` twice under two fingerprints, and the bare-`except` issue appears at
lines 47, 50 and 51 — the same problem, described three ways.

### What this means for you

**Do not run `--post` repeatedly against the same pull request.** Each run adds a
fresh set of comments. Deduplication protects the summary comment, and in practice
does not protect inline comments.

Preview (`--dry-run`) as often as you like — it writes nothing.

> This is a genuine defect, not a documentation gap. Line-insensitive fingerprinting
> was designed to survive line drift between iterations; it does not survive
> non-deterministic finding text, which is what a language model produces. The
> whitespace-only line-drift test that feature 001 describes cannot be meaningfully
> run until identity stops depending on provider wording.

---

## 11. When it does not match

### Conditions that need a setting changed

| Symptom | Cause | Fix | Resume at |
|---|---|---|---|
| `configuration is incomplete or invalid: LLM_PROVIDER is required`, exit `2` | The `.env` corrections were not applied | Add `LLM_PROVIDER=claude` | Section 2 |
| Another `configuration is incomplete or invalid: …`, exit `2` | Validation runs in rounds; fixing one thing revealed the next | Set what it names, run again | Section 2 |
| `the AI provider has no such model or endpoint (HTTP 404)` | `LLM_MODEL` names a model that does not exist | Set `claude-sonnet-5` | Section 2 |
| `authentication failed … sign-in page`, or a `401` | The token is expired, revoked, or not accepted by the server | Reissue the PAT and update `.env` | Section 2 |
| `not permitted to write …` | The posting token lacks write scope | Grant **Code (read & write)** on `TFS_PAT_FOR_PR` | Section 9 |
| `not found: .../pullRequests/<id> (HTTP 404)` → *"check TFS_PROJECT, TFS_REPO, and TFS_PR_ID"* | **Usually none of those.** The server rejects `api-version 6.0`, the agent's default | Set `TFS_API_VERSION=5.0` | Section 7 |
| `401` on work items; run completes with no requirement findings | `TFS_PAT` lacks **Work Items (read)**. The agent reads the story with the read token | Reissue `TFS_PAT` with Work Items (read), or point it at a token that has it | Section 2 |
| `SSLCertVerificationError` | A private CA is not in the trust bundle | `pip install truststore`, or set `REQUESTS_CA_BUNDLE`. **Never disable TLS verification** — a contract test forbids it | Section 2 |

### Conditions that are expected today — no action needed

| Symptom | Why | Do |
|---|---|---|
| `checklist source unavailable`, review continues, exit `0` | Gap G1: the agent looks for `*.md` on `main`; the corpus is `.xlsx`/`.docx` | **Nothing.** Expect no checklist findings at all. Section 7 explains this |
| A degraded review that still exits `0` | Degraded runs are deliberately not a merge gate | **Nothing.** There is no exit `3` |
| A low-severity finding posted *inline* | Placement is by locatability, not severity. There is no threshold | **Nothing.** Section 5 explains this |
| No comment for a criterion the change simply did not address | `not_addressed` never produces a comment, by design | **Nothing** |
| No run report written anywhere | Gap G2: nothing writes one yet. Ignore any older document that tells you to check `.review-reports/` | **Nothing** |
| The number of code issues differs between two runs | Provider judgement is not deterministic. Observed 4, then 5, then 4 on identical input | **Nothing.** Check the finding appeared, not the count |

### Conditions worth retrying

| Symptom | Why | Do |
|---|---|---|
| Analysis service unreachable, throttled, or timed out | Transient. The run aborts and posts nothing rather than posting a partial review that reads as clean | Run again |
| Network interruption mid-run | The pull request is left in a state a re-run recovers from | Run again. Section 10's deduplication is what makes that safe |

### Findings do not match section 8

| Symptom | Likely cause | Fix |
|---|---|---|
| No requirement findings at all | The work item is not linked | Link it (section 6, step 5), run again |
| F1 missing | The pull request description was edited, or the fourth "Covered" line was dropped | Restore the description from section 6 exactly |
| F2 missing | The invalid-code message was corrected while copying | Re-copy `discount.py` from `example-files/` unmodified |
| Wording differs from section 8 | Normal. Findings come from provider judgement | Check that the *finding* appeared, not that the sentence matched |
| Duplicate inline comments after a second `--post` | **Known defect**, not your mistake. Identity depends on the provider's wording, which changes every run — section 10 | Do not re-post to the same pull request. Delete the duplicate threads by hand |
| No requirement findings, and `phase=workitems` shows `401` | `TFS_PAT` lacks Work Items (read) | Section 2 |

---

## 12. Clean up

Do all of it. The sample repository is shared, and leftovers collide with the next
person's demonstration.

1. **Abandon** the pull request. **Do not complete it** — nothing from this sample
   is ever merged.
2. Delete the sample branch.
3. Set the sample user story to **Removed**, or delete it.
4. Delete any local files the run produced that contain copied source. Today the
   agent writes none; check anyway, because gap G2 will change that.

Teardown affects nothing outside the sample repository.

If you found artifacts from an **earlier** demonstration while working through this,
leave them. They are not yours to remove, and the dated naming in section 4 is what
keeps yours distinct from theirs.

---

## 13. Provenance

**Last verified against a real run**: **2026-09-15**
**Agent version**: `review_agent 0.1.0`
**How**: a real user story and pull request created in the sample repository, the agent
run in preview, then posting, then posting again, with output captured at each stage.

### What was verified, and what it changed

| Section | State |
|---|---|
| 1–7, 11, 12 | Written from the agent's source; commands and messages confirmed during the run |
| **8** | **Observed.** Every row came from captured preview output |
| **9** | **Observed.** One summary comment, inline comments on the expected lines |
| **10** | **Observed — and it contradicted the expectation.** The repeat run duplicated inline comments. Recorded as observed, per the rule that the document reports what happened rather than what was designed |

Three things the run corrected in this document:

1. `TFS_API_VERSION=5.0` is **required** on this server, and its absence produces a
   404 whose message points at three settings that are all correct.
2. `TFS_PAT` needs **Work Items (read)**, not just Code. Without it the demonstration
   silently loses every requirement finding.
3. **Re-running `--post` duplicates inline comments.** The design intent was zero new
   comments; the observed result was four.

### Still unverified

The whitespace-only line-drift re-run. It could not produce a meaningful result while
finding identity still depends on provider wording (section 10), so it was not run
rather than reported as passing.

### Where the quoted values come from

Every command, message and status in this document is traceable, so a change to the
agent has a findable effect here:

| Quoted | Defined at |
|---|---|
| `--dry-run`, `--post`, `--pr`, `--local`, `--quiet`, `--version` | `review_agent/main.py:286-303` |
| Exit statuses `0`, `1`, `2` | `review_agent/main.py:334-356`, `review_agent/errors.py:19-21` |
| Absence of exit `3` | `review_agent/errors.py:26` (defined, never returned) |
| Required configuration variables | `review_agent/config.py:313-395` |
| `LLM_BASE_URL` needed only for `azure`/`ollama` | `review_agent/config.py:107` |
| Validation reported in rounds | `review_agent/config.py:369-376` |
| Checklist defaults `*.md` on `main` | `review_agent/config.py:434-435` |
| Checklist-unavailable degradation | `review_agent/main.py:153` |
| Inline-versus-summary routing | `review_agent/output_layer.py:87-137` |
| Contradictions always summary-only | `review_agent/output_layer.py:126` |
| `not_addressed` never comments | `review_agent/output_layer.py:117` |

**There is no `--inline-threshold` and no `--report-dir`.** Some planning documents
list them as forthcoming; `build_parser` has neither.
