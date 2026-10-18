# Preflight — confirm the environment before the demonstration

**Feature**: [../spec.md](../spec.md) | **Task**: T004

Four things have to be true before a live run can work, and three of them fail in ways
that point at the wrong cause. Confirm all four in one pass, before creating anything.

Read-only: nothing here writes to the collection or to `.env`.

---

## 1. The variables the agent requires

```powershell
python -m review_agent --local --dry-run --pr 1 --quiet
```

A configuration problem exits **2** and lists **every** missing value at once, so one run
tells you everything to fix. What you are looking for is the absence of
`ai-review setup failure: configuration is incomplete`.

**Gap G5 is closed.** Checked on 2026-09-16: `.env` carries `LLM_PROVIDER=claude` and a
model identifier that exists, and `load_config` succeeds against it. What 001 and 002 both
recorded as a blocker is no longer one.

Two values it still does not carry, both expected rather than broken:

| Variable | State | What to do |
|---|---|---|
| `TFS_API_VERSION` | absent, so it defaults to `6.0` | set `5.0` — see §2 below |
| `TFS_PR_ID` | absent | pass `--pr <ID>`; the variable is for pipelines |

`.env` holds live credentials and is gitignored. Correcting it is yours, not the agent's.

## 2. The interface version

```powershell
$env:TFS_API_VERSION = "5.0"
```

The default is `6.0`, and this collection answers **HTTP 404 on every endpoint** at that
version. The error says *"check TFS_PROJECT, TFS_REPO, and TFS_PR_ID"* — and all three can
be correct while the review still fails. `5.0` and below work.

## 3. The credential's scopes

The reading token needs **two** scopes, and the second is the one that is usually missing:

| Scope | Needed for | Symptom when absent |
|---|---|---|
| Code (read) | the pull request, the diff, the checklist repository | the review cannot start |
| **Work Items (read)** | the linked story and its acceptance criteria | story coverage is lost |

After this feature a refused work-item read reports itself and the checklist half of the
review still runs (FR-023). Before it, the whole run exited 2. Either way, the review you
get without this scope is not the review you think you got.

Confirm both at once:

```powershell
python -m review_agent --local --dry-run --quiet
```

Look for `phase=workitems count=N criteria=M` with `N` and `M` non-zero, and
`phase=checklists` reporting documents read.

## 4. git, and which copy of the agent will run

```powershell
git --version
```

The checklist repository arrives as a shallow clone, so git must be on `PATH`.

Then decide which copy of the review logic runs, because **the default entry point
re-fetches the agent from its own repository and re-executes it**:

| Command | Reviews with |
|---|---|
| `python -m review_agent` | the **committed** logic in `TFS_REPO_CODE_REVIEW_CodeReviewAgent` |
| `python -m review_agent --local` | this working copy |

Running the default against an unpushed branch reviews with code that does not contain
this feature, and the checklist section of the output comes back empty — for a reason that
looks exactly like the feature having failed. The first line of every run says which copy
ran; read it.

---

## The one-line answer

All four green looks like this, on a preview run:

```
review logic: LOCAL WORKING COPY
ai-review run=1234.3 phase=config outcome=ok mode=dry-run auth=basic
ai-review run=1234.3 phase=workitems outcome=ok count=1 criteria=6
ai-review run=1234.3 phase=checklists outcome=ok documents=5 rules=165
```

Any of those four lines missing or reporting `outcome=degraded` means stop here and fix it,
rather than continuing and attributing the result to the demonstration.
