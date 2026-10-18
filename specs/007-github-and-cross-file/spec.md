# Feature Specification: GitHub Platform Support and Cross-File Review

**Feature Branch**: `007-github-and-cross-file`
**Created**: 2026-10-18
**Status**: Draft
**Input**: User description: `req/REq1.md` — "Support both TFS and GitHub; user stories from
GitHub Issues; cross-file and integration review; detailed prompt/response logging; a central
reusable GitHub workflow; documentation; set up the three repositories."

## Survey Findings *(what the request assumes vs. what the code holds today)*

Recorded so planning starts from the code, not from the request's description of it.

| # | The request says | The code says | Consequence for this feature |
|---|---|---|---|
| S1 | `llm_log.py` already exists — verify and extend | True. Feature 006 is implemented: one file per run, redacted, pruned (`LLM_LOG`, `LLM_LOG_DIR`, `LLM_LOG_KEEP`) | Extend, do not rebuild (US5) |
| S2 | Record real input/output token counts per call | The provider call returns **only the response text**; the provider's usage figures are discarded before anything can log them | Token counts require the provider call to return usage alongside text — a change to the one module that knows wire formats |
| S3 | Log retries | The log records the parse retry (attempt 1 or 2). Transport retries (timeouts, HTTP 429/5xx) happen **inside** the provider call and are invisible to the log | Transport retries must surface as their own entries, or the log under-reports what was sent |
| S4 | Chunks are cut by `LLM_MAX_CHUNK_LINES` | True (default 1200). Chunks split on file boundaries; an oversized file goes alone, whole | US4 replaces the budget and adds splitting of oversized files |
| S5 | Each call sees only its own files | True. Nothing tells a chunk what other files the pull request changed | US4's outline and synthesis pass address this |
| S6 | Exit codes 0 / 1 / 2 | True. Exit 3 is defined and unused; degraded exits 0 | Unchanged |
| S7 | Summary is deduplicated by the `ai-review:` marker | True, on TFS | GitHub must honour the same marker so re-runs edit in place |
| S8 | Credentials are in `.env` | `.env` carries TFS and LLM credentials and three **github.com** repository URLs, but **no GitHub token of any kind** | Live GitHub work (dry run, cloning private repos, opening PRs) is blocked until one is supplied — see Dependencies |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review a GitHub pull request (Priority: P1)

An operator whose code lives on GitHub (github.com or GitHub Enterprise Server) points the
agent at a pull request and gets the same review the TFS users get: inline comments on
changed lines and one summary comment. TFS users notice nothing different.

**Why this priority**: Every other GitHub capability (issues as stories, the workflow, the
demo) depends on the agent being able to read and comment on a GitHub pull request. Not
breaking TFS is a precondition for shipping anything.

**Independent Test**: With the platform set to GitHub and a fake GitHub service, run the
review of a pull request; confirm the changed files, the diff against the merge base, one
review containing all inline comments, and one summary comment. Run the full existing test
suite unchanged and confirm it still passes.

**Acceptance Scenarios**:

1. **Given** the platform is GitHub and a pull request changes three files, **When** the
   agent runs in preview, **Then** it prints the findings it would post and makes no write
   to GitHub.
2. **Given** the platform is GitHub and posting is enabled, **When** the review produces
   five inline findings, **Then** GitHub receives exactly one review carrying all five as
   comments (not five separate reviews), plus one summary comment.
3. **Given** a summary comment from an earlier run exists, **When** the agent re-runs,
   **Then** that summary is edited in place and no second summary appears.
4. **Given** inline comments from an earlier run exist, **When** the agent re-runs on the
   same commit, **Then** no inline comment is duplicated.
5. **Given** the pull request's branch is behind its target, **When** the diff is computed,
   **Then** it is taken against the merge base, so changes made on the target branch since
   the branch point are not reviewed as the author's.
6. **Given** the platform is TFS (or unset), **When** any existing test or run is
   performed, **Then** behaviour is identical to today.

---

### User Story 2 - Judge a GitHub pull request against its linked issue (Priority: P2)

A team that writes user stories as GitHub Issues, with an "Acceptance criteria" section,
gets a verdict for every criterion — appears addressed, not addressed, or possible
contradiction — exactly as a TFS team does for a linked work item.

**Why this priority**: Requirement coverage is the agent's distinguishing value over a
plain linter; without it a GitHub review is checklist-and-code only.

**Independent Test**: With a fake GitHub service, link a pull request to an issue holding
three acceptance criteria; confirm three per-criterion verdicts appear in the summary.

**Acceptance Scenarios**:

1. **Given** a pull request whose body says "Closes #7" and which GitHub also lists as
   closing #7, **When** stories are gathered, **Then** issue #7 is read once, not twice.
2. **Given** issue #7 has an "Acceptance criteria" section of three checkbox items,
   **When** the review runs, **Then** the summary reports a verdict for each of the three.
3. **Given** the criteria are a plain bullet list instead of checkboxes, **When** the review
   runs, **Then** they are recognised the same way.
4. **Given** a linked issue has no "Acceptance criteria" section, **When** the review runs,
   **Then** the issue is still used as context and the summary states that it carried no
   criteria — it is not silently dropped.
5. **Given** the story source is "none", **When** the review runs, **Then** it reviews
   against the checklist only and says so.
6. **Given** a criterion is judged not addressed, **When** findings are posted, **Then** it
   produces no comment of its own (the existing rule), only a line in the summary.

---

### User Story 3 - Catch defects that span files (Priority: P2)

A reviewer relying on the agent learns about problems no single file shows: a method
signature changed in an interface while a caller still uses the old one, an implementation
that no longer matches its interface, a new dependency never registered, a new
configuration key never added to configuration files, a model changed without a migration,
behaviour changed without its tests being updated.

**Why this priority**: These are the defects that pass every per-file check and fail in
production. Today the agent cannot see them whenever the related files land in different
review calls.

**Independent Test**: A test pull request changes the signature of a method in
`ICartService` and leaves `CartController` calling the old signature. Run it once with a
budget that keeps both files together and once with a budget that forces them apart; both
runs report one cross-file finding naming both files.

**Acceptance Scenarios**:

1. **Given** a typical pull request (well under the budget), **When** it is reviewed,
   **Then** it is reviewed in a single call.
2. **Given** a pull request that must be split, **When** each part is reviewed, **Then**
   every part sees an outline of the whole pull request: every changed file, its change
   type, its line counts, which part reviews it, and the declarations added or removed.
3. **Given** files that reference each other (a shared type name, an interface and its
   implementation, the same base name, a source file and its test), **When** the pull
   request is split, **Then** they are kept in the same part wherever the budget allows.
4. **Given** one file alone exceeds the budget, **When** it is reviewed, **Then** it is
   split on hunk boundaries and each piece is preceded by a skeleton of that file
   (types, fields, method signatures).
5. **Given** the pull request was reviewed in more than one part, **When** all parts finish,
   **Then** exactly one further call produces a coherent summary, final per-criterion
   verdicts, and a list of cross-file issues; with one part, no extra call is made.
6. **Given** cross-file issues were found, **When** the summary is posted, **Then** it
   carries a distinct cross-file section.
7. **Given** the synthesis call fails, **When** the run finishes, **Then** the per-part
   findings are still reported and the summary states that synthesis did not run and why.

---

### User Story 4 - Run the central agent from any repository's GitHub workflow (Priority: P3)

A repository owner onboards their repository to automated review by adding one short caller
workflow file (about fifteen lines) and two secrets. Reviews then run on every non-draft
pull request from the same repository, and a newer push cancels the review of the older one.

**Why this priority**: This is how the agent reaches many repositories without each one
copying it. It depends on US1 working.

**Independent Test**: In the sample repository, open a pull request; the caller workflow
runs the central workflow, which reviews against the checklist repository and posts. Mark a
pull request as draft and confirm no review runs.

**Acceptance Scenarios**:

1. **Given** the caller workflow is installed, **When** a pull request is opened,
   synchronized, reopened, or marked ready for review, **Then** a review runs.
2. **Given** a draft pull request or one from a fork, **When** the trigger fires, **Then**
   the review is skipped and the run says why.
3. **Given** a review is in progress, **When** a newer commit is pushed, **Then** the older
   review is cancelled.
4. **Given** the workflow runs, **When** its permissions are inspected, **Then** it holds
   read access to contents and write access to pull requests and issues, and nothing else.
5. **Given** the inputs model, story source, checklist repository, preview mode, log
   enabled, and fail-on-contradiction, **When** the caller omits them, **Then** each takes a
   documented default, with preview mode **on**.
6. **Given** fail-on-contradiction is enabled and a criterion is judged a possible
   contradiction, **When** the review finishes, **Then** the workflow run fails.

---

### User Story 5 - See every prompt, response, token count, and cost (Priority: P3)

An operator investigating a review, or its cost, opens the run's log and sees every call the
agent made — review parts, retries, and the synthesis pass — with the provider's own token
counts and the time each took, and a run total of tokens and estimated cost, also shown on
the console.

**Why this priority**: Cost visibility becomes necessary once the agent runs automatically
on many repositories; the log already exists (S1), so this is an extension.

**Independent Test**: With logging on and a fake provider that reports usage, run a
two-part review in which one call is retried; the log holds an entry per call sent,
including the retried one and the synthesis call, each with token counts and latency, and a
total that equals the sum of the entries.

**Acceptance Scenarios**:

1. **Given** logging is on, **When** a call is made, **Then** its entry records timestamp,
   provider, model, part identifier, prompt, raw response, input and output token counts as
   reported by the provider, and latency.
2. **Given** the provider timed out once and then answered, **When** the log is read,
   **Then** both sends appear as entries.
3. **Given** the provider's response reports no usage, **When** the entry is written,
   **Then** token counts are recorded as "not reported" — never estimated and presented as
   real.
4. **Given** the run finishes, **When** the log and the console are read, **Then** both show
   total input tokens, total output tokens, and the estimated cost (or "not estimated" when
   no price is configured).
5. **Given** the log file cannot be written, **When** the review runs, **Then** the review
   completes normally and the console states that logging failed.
6. **Given** the workflow's log input is on, **When** the run finishes, **Then** the log is
   uploaded as a short-retention workflow artifact, and the documentation warns that it
   contains source code.

---

### User Story 6 - Understand, set up, and onboard (Priority: P3)

A new developer or operator can understand the full review flow from one diagram, find any
file's purpose and relationships in one structure document, and set up GitHub — tokens,
secrets, onboarding a repository, running locally, troubleshooting — from one setup guide.

**Why this priority**: Required for anyone other than the author to run or change the agent;
it describes US1-US5, so it is written after them.

**Independent Test**: A reader with no prior knowledge onboards a second repository using
only the setup guide; the flow diagram renders without error.

**Acceptance Scenarios**:

1. **Given** the flow diagram, **When** it is rendered, **Then** it renders without error and
   shows swimlanes for Developer, GitHub/TFS, Workflow, Agent, and LLM, both platform
   branches, splitting and synthesis, retry, degraded paths, deduplication, and preview
   mode, with a worked example (issue #7 "Add item to cart", three criteria → pull request
   #12 changing four files → two parts → findings → posted comments).
2. **Given** the structure document, **When** any file in the repository is looked up,
   **Then** it states purpose, responsibility, main functions or classes, inputs and
   outputs, what it depends on, and what calls it — including tests, specifications, and
   configuration files.
3. **Given** the README and project guide, **When** a new configuration setting is looked
   up, **Then** it is listed with its meaning and default.

---

### User Story 7 - A working demonstration across the three repositories (Priority: P3)

The requester can see the whole system working: the sample repository holds an issue
template, a sample issue with acceptance criteria, and a demo pull request carrying one
deliberate cross-file defect and one checklist violation; the review of that pull request
produces inline comments, a summary, per-criterion verdicts, and the cross-file finding;
a second run adds nothing.

**Why this priority**: It is the end-to-end proof in the Definition of Done, but every part
of it is delivered by an earlier story.

**Independent Test**: Run the review of the demo pull request twice; inspect the pull request.

**Acceptance Scenarios**:

1. **Given** the demo pull request, **When** it is reviewed, **Then** it receives inline
   comments, a summary, a verdict per criterion, and a finding for the deliberate
   cross-file defect.
2. **Given** a second review of the same commit, **When** it finishes, **Then** no comment
   has been added or duplicated.
3. **Given** the changes in each of the three repositories, **When** they are delivered,
   **Then** each is on a feature branch with a pull request opened, nothing is pushed to a
   main branch, `.env` is ignored in every repository, and no secret value appears in the
   history of the changes.

---

### Edge Cases

- A GitHub pull request with more changed files than one listing page returns — every page
  must be read, or files are silently not reviewed.
- A file renamed with no content change, a deleted file, and a binary file on GitHub — each
  handled as TFS handles it today.
- An inline finding on a line GitHub will not accept a comment on — it is moved to the
  summary with a stated reason, and does not fail the whole review submission.
- A pull request body referencing an issue in another repository (`owner/repo#N`) or a
  number that is a pull request, not an issue.
- An issue whose "Acceptance criteria" heading differs in case or level, or which contains
  nested bullets.
- A pull request with no changed reviewable files — no review call and no synthesis call;
  the summary says why.
- Two files with the same base name in different folders that are unrelated.
- A dependency cycle among files larger than the budget — the grouping must still terminate
  and respect the budget.
- An oversized file whose single hunk alone exceeds the budget.
- The synthesis call's response is unparseable — treated as a failed synthesis (US3-7).
- A provider that reports usage under a different field name, or not at all.
- A GitHub Enterprise Server address configured with or without a trailing path.
- A fork pull request reaching the workflow — must be skipped, never given write access.
- `PLATFORM=github` with TFS-only settings present, or the reverse — the unused settings are
  ignored, the missing ones reported.

## Requirements *(mandatory)*

### Functional Requirements

**Platform (US1)**

- **FR-001**: The agent MUST support two platforms, TFS / Azure DevOps Server and GitHub,
  selected by one setting (`PLATFORM`, values `tfs` or `github`, default `tfs`).
- **FR-002**: The pipeline MUST depend on a single platform contract covering: get the pull
  request, list changed files, get a file's content at a commit, get head and base commits,
  list the agent's prior comments, post inline comments, and create or update the summary.
- **FR-003**: With the platform set to TFS, behaviour MUST be unchanged; every existing test
  MUST pass without modification.
- **FR-004**: On GitHub, the base commit MUST be the merge base of the pull request's head and
  target, and the head commit MUST be the pull request's head commit.
- **FR-005**: On GitHub, all inline comments from one run MUST be posted as a single review
  of type "comment" (neither approve nor request changes).
- **FR-006**: On GitHub, the summary MUST be one conversation comment, edited in place on
  re-runs, identified by the existing `ai-review:` marker.
- **FR-007**: The agent MUST work against github.com and GitHub Enterprise Server, chosen by
  a configured API address (`GH_API_URL`, defaulting to github.com's).
- **FR-008**: Exactly one part of the agent MAY speak to the GitHub API, and the existing
  boundary rules (one module reads the environment, one speaks TFS, one speaks provider
  formats, one runs git) MUST still hold; both MUST be enforced by tests.
- **FR-009**: Re-running the review on an unchanged pull request MUST NOT duplicate any
  inline or summary comment, on either platform.

**Stories from GitHub Issues (US2)**

- **FR-010**: The story source MUST be selectable (`STORY_SOURCE`: `tfs`, `github-issues`,
  `none`), defaulting to the source native to the platform.
- **FR-011**: Linked issues MUST be gathered both from the issues GitHub records the pull
  request as closing and from `Closes`, `Fixes`, or `Resolves #N` in the pull request body,
  case-insensitively, with duplicates removed.
- **FR-012**: Acceptance criteria MUST be read from an "Acceptance criteria" section of the
  issue body, whether written as a checkbox list or a bullet list, and MUST map into the same
  story model TFS work items use, so verdicts are produced identically.
- **FR-013**: An issue that cannot be read, or carries no criteria, MUST be reported with a
  stated reason and MUST NOT stop the review.

**Cross-file review (US3)**

- **FR-014**: The review budget MUST be expressed in tokens (`LLM_MAX_PROMPT_TOKENS`,
  default 120,000) rather than lines.
- **FR-015**: Every review part MUST include an outline of the whole pull request: each
  changed file, its change type, lines added and removed, which part reviews it, and the
  declarations (types, interfaces, method signatures) added or removed — derived from the
  diff without a model call.
- **FR-016**: When a pull request must be split, files that reference each other (shared type
  names, interface and implementation, same base name, source and test) MUST be kept in the
  same part wherever the budget allows.
- **FR-017**: A single file exceeding the budget MUST be split on hunk boundaries, each piece
  preceded by a skeleton of the file (types, fields, method signatures).
- **FR-018**: When more than one part was reviewed, exactly one synthesis call MUST be made,
  taking the merged findings, each part's change notes, the outline, and the acceptance
  criteria, and returning one summary, final per-criterion verdicts, and a list of
  cross-file issues. With one part, no synthesis call is made and the single part's
  response supplies the same three things.
- **FR-019**: The review response contract MUST include a cross-file issues section, and the
  posted summary MUST present it as its own section; each cross-file issue names every file
  involved.
- **FR-020**: A failed synthesis MUST leave the per-part findings intact and reported, with
  the reason synthesis did not complete stated in the summary.

**Logging and cost (US5)**

- **FR-021**: When logging is on, every call sent to the provider MUST be logged — each
  review part, each retry of any kind, and the synthesis call — on both platforms.
- **FR-022**: Each entry MUST record timestamp, provider, model, part identifier, prompt, raw
  response, input and output token counts as reported by the provider, and latency.
  Counts the provider did not report MUST be recorded as not reported, never estimated.
- **FR-023**: The log and the console MUST show per-run totals of input and output tokens and
  an estimated cost computed from operator-configured prices; without prices, the cost is
  shown as not estimated.
- **FR-024**: Every log entry MUST pass through the existing redaction; no credential may
  reach the log.
- **FR-025**: A logging failure of any kind MUST NOT fail, degrade, or alter the review; it
  MUST be stated on the console.

**Central workflow (US4)**

- **FR-026**: The agent repository MUST provide a reusable workflow, callable from other
  repositories, that obtains the agent, installs its dependencies, and runs it against the
  calling pull request. Inputs: model, story source, checklist repository, preview mode,
  log enabled, fail-on-contradiction. Secrets: the model's API key and the review bot's
  token.
- **FR-027**: Preview mode MUST default to on — in the agent and in the workflow.
- **FR-028**: The workflow MUST hold only read access to contents and write access to pull
  requests and issues; it MUST NOT use the trigger that runs fork code with the base
  repository's secrets.
- **FR-029**: Draft and fork pull requests MUST be skipped with a stated reason.
- **FR-030**: A newer commit on the same pull request MUST cancel the in-progress review.
- **FR-031**: Onboarding a repository MUST require only the caller workflow file (about
  fifteen lines) and the two secrets.
- **FR-032**: When logging is enabled in the workflow, the log MUST be uploaded as a workflow
  artifact retained for a short period, and its documentation MUST state that it contains
  source code.
- **FR-033**: Exit codes keep their meaning: 0 for a completed or degraded review, 1 for
  blocking findings (including a possible contradiction when fail-on-contradiction is on),
  2 for a setup failure.

**Documentation (US6)**

- **FR-034**: The repository MUST contain a rendered-valid flow diagram as specified in
  US6-1, a code structure document covering every file as specified in US6-2, and a GitHub
  setup guide covering tokens and permissions, secrets, onboarding, local runs, and
  troubleshooting.
- **FR-035**: The README and project guide MUST list every new setting with meaning and
  default.

**Repositories and demonstration (US7)**

- **FR-036**: The sample repository MUST receive the caller workflow, a user-story issue
  template with Description and Acceptance criteria sections, one sample issue with
  acceptance criteria, and one demo pull request linked to it containing one deliberate
  cross-file defect and one checklist violation.
- **FR-037**: All changes MUST be delivered on feature branches with pull requests; nothing
  is pushed to a main branch; no secret value is set by the agent or appears in the history
  of the changes; `.env` MUST be ignored in every repository.
- **FR-038**: The delivery MUST end with a precise list of every secret the requester must
  add: its name, where it is added, and the permissions it needs.

**Constraints across all stories**

- **FR-039**: Every new part of the agent MUST be covered by unit, contract, and fake-backed
  integration tests; the GitHub path MUST have a test suite equivalent to the TFS one.
- **FR-040**: No runtime dependency may be added unless essential, and any added MUST be
  justified in the plan.
- **FR-041**: When a credential or permission required for a step is missing, work on that
  step MUST stop and the requester MUST be told which one; it MUST NOT be worked around.
- **FR-042**: The model and its key remain configurable through `.env`.

### Key Entities

- **Platform**: Where pull requests live (TFS or GitHub); provides the operations in FR-002.
- **Pull request context**: The pull request under review — identity, head commit, base
  commit, title, body, changed files.
- **Story / Work item**: A requirement the change is judged against — from a TFS work item or
  a GitHub issue — with an ordered list of acceptance criteria.
- **Review part (chunk)**: A subset of the changed files, or of one oversized file, reviewed
  in one model call, sized by token budget.
- **PR outline**: A whole-pull-request summary shown to every part: files, change types, line
  counts, part assignment, added and removed declarations.
- **File skeleton**: The declarations of one oversized file, shown with each piece of it.
- **Cross-file issue**: A finding that involves two or more files, naming each.
- **Synthesis result**: The final summary, final criterion verdicts, and cross-file issues for
  a multi-part review.
- **Log entry**: One call sent to the provider, with the fields in FR-022.
- **Run totals**: Summed tokens and estimated cost for one run.
- **Workflow inputs and secrets**: What a caller repository passes to the central workflow.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the tests that pass before this feature still pass after it, unmodified,
  and the full suite (old and new) passes.
- **SC-002**: A preview review completes against one real TFS pull request and one real GitHub
  pull request, making zero writes to either.
- **SC-003**: On the demo pull request, the deliberate cross-file defect is reported in 100% of
  runs, including when its two files are forced into different parts.
- **SC-004**: A second review of an unchanged pull request adds zero comments on either
  platform.
- **SC-005**: Pull requests under the default budget are reviewed in exactly one model call.
- **SC-006**: With logging on, the number of log entries equals the number of calls sent to the
  provider, and the run total equals the sum of the entries' reported tokens.
- **SC-007**: Onboarding a new repository takes one caller file of no more than about fifteen
  lines plus two secrets, and can be completed by following the setup guide alone.
- **SC-008**: A review is never started for a draft or fork pull request, and a newer commit
  cancels the older review within the workflow platform's normal cancellation time.
- **SC-009**: Zero secret values appear in any log, console output, posted comment, workflow
  artifact, or the history of the delivered changes.

## Assumptions

- **Token budget measurement**: The budget in FR-014 is applied using an estimate of a
  prompt's size, since exact counts are only known after the provider replies; the estimate
  is deliberately conservative. Real counts (FR-022) are used only for reporting.
- **Pricing**: Per-token prices are supplied by the operator as settings (input and output
  separately); no price list is built in, because prices change and differ by provider.
- **Default story source**: `tfs` on TFS, `github-issues` on GitHub, when `STORY_SOURCE` is
  unset.
- **Fork pull requests**: Skipped entirely rather than reviewed without posting; reviewing
  them safely would need a different trigger model, out of scope.
- **Checklist repository access**: The workflow's built-in token cannot read another private
  repository, so the review bot token is assumed to need read access to the checklist
  repository as well; the setup guide will say so.
- **Declaration extraction**: Uses pattern matching over the diff for the languages in the
  sample repository (C#-style types, interfaces, methods) and common equivalents; unknown
  languages yield an outline without declarations, stated as such.
- **Dependency grouping**: Is a best-effort heuristic; when the budget forces related files
  apart, the outline and synthesis pass (FR-015, FR-018) are what still catch the defect.
- **Inline comment threading on GitHub**: Prior-comment deduplication relies on the existing
  marker carried in every comment body, as on TFS.
- **Outward-facing steps**: Cloning, pushing branches, creating issues, and opening pull
  requests in the three GitHub repositories are confirmed with the requester before they
  are performed.

## Dependencies

- **A GitHub token is required and is not in `.env` today** (S8). It is needed to clone the
  three private repositories, to perform the GitHub preview run, to create the sample issue
  and demo pull request, and to open pull requests. Per FR-041, the live GitHub steps stop
  until it is supplied; everything testable with fakes proceeds without it.
- The workflow secrets (model API key, review bot token) are set by the requester, not by
  the agent.
- A PlantUML renderer, if available locally, to validate the diagram; otherwise validation is
  recorded as not performed.
- The existing TFS server, settings (`TFS_API_VERSION=5.0`), and tokens, for the TFS preview run.

## Out of Scope

- Reviewing fork pull requests.
- Approving or requesting changes on GitHub (reviews are comment-only).
- Measuring prompts against a model's hard context limit beyond the configured budget.
- A severity threshold for inline comments, a written run report, and exit code 3 — open
  gaps from feature 001 that this feature does not change.
- Other platforms (GitLab, Bitbucket).
