# Feature Specification: PR Code Review Agent (Local Mode)

**Feature Branch**: `001-pr-code-review-agent`
**Created**: 2026-09-15
**Status**: Draft
**Input**: User description: "Code review agent local mode where we pass the Pull Request and code repository. Agent gets the code difference from the pull request and the checklist documents in the code review checklist repository. Agent also gets the user stories linked in the PR. Where the agent finds a finding it adds comments directly in the PR on the line of code plus a summary at the end. Configuration comes from `.env` (checklist repo, base URL, access token). Test the flow by creating a sample PR and sample user story in the sample repository, running the agent, and pushing comments to the PR."

## Clarifications

### Session 2026-09-15

- Q: Where does the review evaluation happen, and what data leaves the local machine? → A: A public hosted language-model service (third-party vendor, reached over the internet). Source code, coding standards, and work-item content therefore leave the corporate network.
- Q: What severity scale applies, and which severities are posted as inline comments? → A: Three levels — Blocker, Major, Minor. Blocker and Major are posted inline by default; Minor appears in the summary only. The threshold is configurable.
- Q: Which branch, paths, and depth does the agent read checklist documents from? → A: Every `.xlsx` and `.docx` file anywhere in the checklist repository, on its default branch, searched recursively. No path or branch configuration — whatever is in the repository is in force.
- Q: What makes two findings "the same" for the purpose of not re-posting duplicates? → A: The file plus the checklist item or acceptance criterion cited. One finding per rule per file; identity survives line drift between runs.
- Q: What durable record does a run leave behind locally? → A: One machine-readable report file per run, written to a local folder, alongside the existing human-readable console output. No rolling log.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review a pull request against the team's coding checklists (Priority: P1)

A developer or reviewer runs the agent from their own machine, naming a repository and a pull request in it. The agent pulls the pull request's code changes, reads the organisation's coding-guideline and checklist documents from the central checklist repository, evaluates every changed line against those guidelines, and then writes its findings back into the pull request: one comment anchored to the exact file and line for each finding that can be located in the diff, plus one closing summary comment that lists everything it found and everything it checked.

**Why this priority**: This is the whole product. Without it there is no agent. A reviewer who runs only this story already gets the core value — an automated first-pass review grounded in the team's own published standards, delivered where the team already works (the pull request), with no other story implemented.

**Independent Test**: Point the agent at an existing pull request that contains at least one deliberate checklist violation. Confirm that the agent completes, that a line comment appears on the offending line in the pull request web view, and that a summary comment appears on the pull request. No user-story linkage and no preview mode are needed for this test.

**Acceptance Scenarios**:

1. **Given** a valid configuration and a pull request containing a change that violates a documented checklist item, **When** the reviewer runs the agent against that pull request, **Then** a comment is posted on the specific file and line of the violating change, the comment states the finding and cites the checklist item it came from, and a summary comment is posted on the pull request.
2. **Given** a pull request whose changes violate nothing in the checklists, **When** the agent runs, **Then** no line comments are posted and a single summary comment records that the review completed with no findings.
3. **Given** a finding that cannot be tied to a specific changed line (for example a missing file or a repository-wide concern), **When** the agent reports it, **Then** the finding appears in the summary comment rather than being anchored to an unrelated line.
4. **Given** a pull request that spans several files, **When** the agent runs, **Then** each finding is anchored to the correct file and to a line that is part of that pull request's changes.
5. **Given** the same pull request with no new commits, **When** the reviewer runs the agent a second time, **Then** findings the agent already posted are not duplicated in the pull request.

---

### User Story 2 - Check the change against the user stories linked to the pull request (Priority: P2)

Beyond style and standards, the reviewer wants to know whether the change actually does what it was asked to do. The agent reads the work items (user stories) linked to the pull request, takes their descriptions and acceptance criteria as the statement of intent, and reports where the submitted change appears to miss, contradict, or exceed that intent.

**Why this priority**: Requirement alignment is the highest-value part of human review and the part most often skipped under time pressure. It depends on Story 1's ability to fetch a diff and post comments, so it follows rather than leads.

**Independent Test**: Take a pull request linked to a user story whose acceptance criteria are only partly implemented. Run the agent and confirm the summary comment names the unmet criterion and references the user story it came from.

**Acceptance Scenarios**:

1. **Given** a pull request with one or more linked user stories, **When** the agent runs, **Then** the summary comment lists the linked user stories it took into account, each identified well enough for a reader to open it.
2. **Given** a linked user story with acceptance criteria that the change does not satisfy, **When** the agent runs, **Then** the gap is reported as a finding that names the specific unmet criterion.
3. **Given** a pull request with no linked user stories, **When** the agent runs, **Then** the checklist review still completes normally and the summary comment states that no user stories were linked.
4. **Given** a linked work item the configured credentials cannot read, **When** the agent runs, **Then** the checklist review still completes and the summary comment states that the work item could not be retrieved.

---

### User Story 3 - Preview the findings locally before anything is posted (Priority: P3)

Before letting the agent write into a pull request that the whole team can see, the reviewer runs it in a preview mode that performs the identical review and prints the findings — file, line, severity, text, and the checklist item behind each one — to the local console without contacting the pull request to post anything.

**Why this priority**: Comments on a pull request are visible to the team and awkward to retract, so a way to look before writing protects both the reviewer's credibility and the team's signal-to-noise ratio. It is a safety convenience rather than core value, so it ranks below the two review stories.

**Independent Test**: Run the agent in preview mode against a pull request with known violations. Confirm the findings are printed locally and confirm, by inspecting the pull request afterwards, that no comment was added to it.

**Acceptance Scenarios**:

1. **Given** preview mode is requested, **When** the agent runs and finds violations, **Then** every finding is printed locally with its file, line, severity, text, and source checklist item, and the pull request is left unmodified.
2. **Given** preview mode is requested, **When** the run finishes, **Then** the output states plainly that nothing was posted and what would have been posted.

---

### User Story 4 - Prove the end-to-end flow on a sample pull request (Priority: P3)

To demonstrate and regression-test the agent without touching production code, an operator sets up a sample user story and a sample pull request in a dedicated sample repository, runs the agent against it, and verifies that real comments land on the sample pull request.

**Why this priority**: This is the acceptance vehicle for the feature rather than a capability end users depend on day to day, but the feature cannot be declared done without it.

**Independent Test**: Follow the documented sample-setup steps from a clean machine, run the agent against the resulting sample pull request, and confirm both line comments and a summary comment appear on it.

**Acceptance Scenarios**:

1. **Given** access to the sample repository, **When** the operator follows the documented setup steps, **Then** a sample user story and a sample pull request containing code that deliberately violates at least one checklist item and leaves at least one acceptance criterion unmet exist and are linked to each other.
2. **Given** that sample pull request, **When** the agent is run against it, **Then** line comments and a summary comment appear on it and the operator can trace each finding back to the checklist item or acceptance criterion that produced it.
3. **Given** the demonstration is finished, **When** the operator follows the documented teardown steps, **Then** the sample pull request and sample user story can be removed or abandoned without affecting anything else.

---

### Edge Cases

- **Missing or incomplete configuration**: a required setting is absent or blank. The agent stops before contacting anything, names the specific missing setting, and exits with a failure status.
- **Invalid or expired credentials**: the agent reports an authentication failure in plain language and does not retry in a way that risks locking the account.
- **Insufficient permission to comment**: the agent can read the pull request but cannot write to it. It reports the findings locally, states clearly that posting was refused, and exits with a failure status rather than silently discarding the review.
- **Pull request not found, already completed, or abandoned**: the agent reports the state it found and does not attempt to post.
- **Empty diff**: a pull request with no changed lines produces a summary comment recording that there was nothing to review.
- **Very large pull request**: the change exceeds what can be reviewed in one pass. The agent reviews as much as it can, and the summary comment states explicitly which files or portions were not reviewed.
- **Binary, generated, or vendored files**: excluded from line-level review, and the exclusions are listed in the summary.
- **Deleted files and pure renames**: no line comments are attached to removed content; any relevant observation goes to the summary.
- **Empty, unreadable, or corrupt checklist documents**: the agent reports which documents it could not read, and refuses to run the review if no checklist content could be loaded at all, rather than reporting a misleading clean result.
- **Draft, archived, or superseded documents sitting in the checklist repository**: they are picked up and treated as in force, because the search is unfiltered. The agent names every document it used (FR-008a) so the team can spot this; keeping the repository clean is the standards owners' responsibility, not the agent's.
- **A file with a checklist extension that is not a checklist** (a meeting note, a template, a tracker): its text is still extracted as guidance. It is listed among the documents consulted so the reviewer can discount findings it produced.
- **The checklist repository grows large**: document retrieval and extraction still complete within the run's time budget, or the run reports which documents it could not process in time.
- **Checklist documents that contradict each other**: both guidelines are cited and the conflict is surfaced in the summary rather than silently resolved.
- **A finding whose line is no longer part of the diff** (the file changed between fetching and posting): the finding is moved to the summary instead of being anchored to the wrong line.
- **Partial failure while posting**: some comments post and then the connection fails. The agent reports exactly which findings were posted and which were not, in both the console output and the run report, so a re-run does not duplicate them.
- **Report folder missing or not writable**: the agent creates the folder where it can; where it cannot, it warns and still completes the review rather than discarding a finished review over a logging failure.
- **Network interruption mid-run**: the agent fails clearly and leaves the pull request in a state a re-run can recover from.
- **Re-running after new commits are pushed**: previously posted findings that still apply are not duplicated; findings on lines that no longer exist are not re-posted.
- **Analysis service unreachable, throttled, or timing out**: the run aborts with a clear message and posts nothing, rather than posting a partial review that reads as a clean result.
- **Analysis service returns an unusable response**: malformed or non-actionable output is treated as a failed run, not as "no findings".
- **Change too large for one request to the analysis service**: the review is split across requests, and the summary states which portions were reviewed separately or not at all.

## Requirements *(mandatory)*

### Functional Requirements

#### Invocation and configuration

- **FR-001**: The agent MUST run entirely from an operator's local machine, initiated on demand, with no requirement for a hosted service, scheduled job, or server-side hook.
- **FR-002**: The agent MUST accept, at invocation, the identifier of the repository to review and the identifier of the pull request within it.
- **FR-003**: The agent MUST read its connection settings from a local environment configuration file: the base address of the source-control and work-item system, the access token used to read pull requests and post comments, and the location of the checklist repository.
- **FR-004**: The agent MUST validate that every required setting is present before it contacts any remote system, and MUST name the specific missing setting when one is absent.
- **FR-005**: The agent MUST never write the access token, or any other secret, to console output, log files, review findings, or pull request comments.
- **FR-006**: The agent MUST exit with a success status when a review completes and with a distinct failure status when it could not complete, so it can be used from a script.

#### Gathering review inputs

- **FR-007**: The agent MUST retrieve the set of code changes introduced by the named pull request, sufficient to know, for every changed file, which lines were added, modified, or removed.
- **FR-008**: The agent MUST retrieve every spreadsheet (`.xlsx`) and word-processing (`.docx`) document held anywhere in the configured checklist repository, searching its default branch recursively from the repository root. Every such document found is treated as currently in force; there is no path, branch, or inclusion setting to narrow the search.
- **FR-008a**: The agent MUST list, in the summary comment and in its local output, every checklist document it read and every one it found but could not read, so a reader can see exactly which guidance produced the review and spot a stale or unintended document among them.
- **FR-009**: The agent MUST extract individual, citable guideline or checklist items from those documents, retaining for each item enough identity — its wording and its source document — to quote it back to the reviewer.
- **FR-010**: The agent MUST retrieve the user stories and other work items linked to the pull request, including their titles, descriptions, and acceptance criteria.
- **FR-011**: The agent MUST continue the review and report the shortfall when an individual checklist document or linked work item cannot be retrieved, and MUST refuse to report a clean result when no checklist content at all could be loaded.

#### Performing the review

- **FR-012**: The agent MUST evaluate the pull request's changed lines against the extracted checklist and guideline items.
- **FR-013**: The agent MUST evaluate whether the pull request's changes satisfy the acceptance criteria of its linked user stories, and MUST report criteria that appear unmet or contradicted.
- **FR-014**: The agent MUST confine its findings to lines the pull request changed, together with as much surrounding file context as it needs to judge them correctly, and MUST NOT raise findings about pre-existing code the pull request did not touch.
- **FR-015**: Each finding MUST carry the file it concerns, the line it concerns where one applies, a severity, the problem stated in plain language, and a citation of the checklist item or acceptance criterion that produced it.
- **FR-016**: The agent MUST classify each finding into exactly one of three severities — **Blocker** (the change should not merge as it stands), **Major** (a real defect or standards breach that ought to be fixed but need not block), or **Minor** (a suggestion, preference, or polish item) — so a reviewer can tell a blocking defect from a stylistic suggestion.
- **FR-017**: The agent MUST exclude binary, generated, and vendored files from line-level review and MUST state in the summary which files it excluded.

#### Publishing results

- **FR-018**: The agent MUST post each line-locatable finding **at or above the configured inline severity threshold** as a comment anchored to the corresponding file and line of the pull request, so a reader sees it beside the code it concerns.
- **FR-019**: The agent MUST post exactly one summary comment on the pull request per run, recording **every finding it raised — including those below the inline threshold, which appear only here** — grouped by severity, together with the findings that could not be anchored to a line, the checklist documents consulted, the linked user stories considered, and anything that was skipped or could not be retrieved.
- **FR-019a**: The inline severity threshold MUST be configurable, and MUST default to Blocker and Major, so that Minor findings stay in the summary and do not interrupt the author in their diff view unless the team opts in.
- **FR-019b**: Every finding the agent raises MUST reach the pull request somewhere — inline when it meets the threshold, in the summary otherwise. The threshold MUST NOT cause a finding to be discarded silently.
- **FR-020**: The agent MUST NOT post a finding it has already posted on the same pull request, so that re-running it does not flood the pull request with duplicates. Two findings count as the same when they concern the same file and cite the same checklist item or acceptance criterion; the line number is deliberately not part of that identity, so a finding is not re-posted merely because intervening edits shifted the code down the file.
- **FR-020a**: The agent MUST determine what it has already posted by reading its own existing comments on the pull request, not from local state, so that duplicate suppression holds when the agent is run from a different machine or after local files are lost.
- **FR-020b**: When a rule is violated more than once in the same file, the agent MUST post one comment — anchored to the first occurrence — and note in that comment that the rule is breached elsewhere in the file, so the author learns of every occurrence without receiving a comment for each.
- **FR-021**: The agent MUST report, on completion, how many comments it posted and how many it failed to post, and MUST name the findings in each group.
- **FR-022**: The agent MUST NOT change the pull request's approval vote, status, completion state, or any of its content other than adding the comments described above.
- **FR-023**: The agent MUST offer a preview mode that performs the full review and presents the findings locally without posting anything to the pull request.
- **FR-024**: Findings posted to the pull request MUST identify themselves as coming from the automated review agent, so readers can tell them apart from human reviewer comments.

#### Validating the flow

- **FR-025**: The feature MUST include documented, repeatable steps for creating a sample user story and a sample pull request in the sample repository, containing at least one deliberate checklist violation and at least one unmet acceptance criterion, and for removing them afterwards.
- **FR-026**: The feature MUST demonstrate a complete run against that sample pull request, ending with line comments and a summary comment visible on it.

#### Analysis service and data handling

- **FR-027**: The agent MUST perform its evaluation using an external hosted language-model service, reached over the internet, whose endpoint and credential are supplied in the local configuration file.
- **FR-028**: The agent MUST send to that service only what the review requires — the changed lines with their necessary surrounding context, the extracted checklist items, and the linked user-story content — and MUST NOT send repository content from files the pull request did not change.
- **FR-029**: The agent MUST NOT include the source-control access token, the analysis service credential, or any other configured secret in what it sends to the analysis service.
- **FR-030**: The agent MUST state at startup which analysis service it will send content to, so the operator knows where the code is going before the run begins.
- **FR-031**: The agent MUST abort the run with a clear message, posting nothing to the pull request, when the analysis service is unreachable, refuses the request, or returns a response it cannot use.
- **FR-032**: The feature's documentation MUST record plainly that source code, internal coding standards, and work-item content are transmitted to a third-party service outside the corporate network, so the team can obtain whatever approval its policy requires before adopting the agent.

#### Run record

- **FR-033**: The agent MUST write exactly one machine-readable report file per run to a local folder, in addition to its human-readable console output, so that a completed run leaves evidence that outlives the terminal session.
- **FR-034**: The run report MUST record the repository and pull request reviewed, when the run started and finished, whether it was a preview, every finding with its file, line, severity, text, and cited rule, whether each finding was posted inline, carried in the summary, or suppressed as a duplicate, the checklist documents consulted and those that could not be read, the linked user stories considered, the files excluded from review, and every failure encountered.
- **FR-035**: The agent MUST write the run report even when the run aborts, recording how far it got and why it stopped, so that a half-completed or failed run can be diagnosed and safely re-run.
- **FR-036**: The run report MUST contain no access token, analysis-service credential, or other secret.
- **FR-037**: Preview runs MUST produce a report identical in form to a posting run, marked as a preview, with every finding shown as not posted.

### Key Entities *(include if feature involves data)*

- **Review Run**: One on-demand execution of the agent. Knows which repository and pull request it targeted, when it started and finished, whether it was a preview, what it produced, and what it could not do.
- **Run Report**: The durable local record of one Review Run — the machine-readable file it writes on completion or abort, holding the run's findings, what became of each, the inputs consulted, and the failures met. It is the evidence a disputed finding or a half-posted run is examined against.
- **Pull Request**: The change under review. Identified within a repository; carries a source and target branch, a state, the set of changed files, and its links to work items.
- **Code Change**: The changed portion of one file in the pull request — the file's path, its change type (added, modified, deleted, renamed), and the specific line ranges the pull request touched. Findings anchor here.
- **Checklist Document**: One coding-guideline or checklist file held in the checklist repository, in spreadsheet or word-processing form. Identified by name and location so findings can cite it.
- **Checklist Item**: One individual, citable rule extracted from a checklist document — its wording, its source document, and, where the document provides one, its category or identifier.
- **Linked User Story**: A work item associated with the pull request — its identifier, title, description, and acceptance criteria. The statement of intent the change is judged against.
- **Finding**: One issue the agent raises — the file and line it concerns (line optional), a severity of Blocker, Major, or Minor, a plain-language description, and a citation of the checklist item or acceptance criterion behind it. Its severity, measured against the configured inline threshold, decides whether it lands beside the code or in the summary.
- **Posted Comment**: The record of a finding having been published to the pull request — which finding, where it landed, and whether the post succeeded. Its identity, and therefore the basis for non-duplicating re-runs, is the file it concerns plus the checklist item or acceptance criterion it cites, never the line number.
- **Configuration**: The local settings that let the agent reach the system: base address, access credential, checklist repository location, and sample repository location.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer who has the configuration file in place can start a review of a pull request with a single command and no further input.
- **SC-002**: A review of a typical pull request — up to 20 changed files and 500 changed lines — completes and has its comments posted within 10 minutes of being started.
- **SC-003**: 100% of posted line comments land on a file and line that the pull request actually changed; none land on unchanged or non-existent lines.
- **SC-004**: 100% of posted findings cite the checklist item or the user-story acceptance criterion that produced them, so a reader can verify every finding against its source without asking the agent.
- **SC-005**: Every run that posts anything also posts exactly one summary comment; no run posts two, and no run posts line comments without a summary.
- **SC-006**: Running the agent twice against an unchanged pull request adds no duplicate findings on the second run, and running it again after commits that shift line numbers without changing behaviour likewise adds none.
- **SC-007**: At least 80% of the findings the agent posts **inline** are judged by a human reviewer to be genuine and worth acting on, so that reviewers keep reading the comments instead of learning to ignore them.
- **SC-007a**: Every finding raised in a run appears either inline or in the summary comment; across all runs, zero findings are dropped by the severity threshold.
- **SC-008**: In preview mode, zero comments reach the pull request across all runs.
- **SC-009**: Every failure the agent can encounter — missing configuration, bad credentials, no permission to comment, missing pull request, unreadable checklist — produces a message that names the specific cause, with no unexplained crash.
- **SC-010**: A new operator, given only the written setup steps, can create the sample user story and sample pull request and see the agent's comments appear on it within 30 minutes, without help from the feature's authors.
- **SC-011**: No secret value appears anywhere in the agent's console output, its run reports, anything it posts to a pull request, or anything it sends to the analysis service, verified across all runs.
- **SC-013**: Every run, including one that aborts, leaves a run report from which a reader can reconstruct what was found, what was posted, and what failed, without access to the original terminal session.
- **SC-012**: Everything the agent sends to the external analysis service is confined to changed-file content, checklist items, and linked user-story content; no file the pull request did not change is ever transmitted, verified by inspecting what the agent sends.

## Assumptions

These are reasonable defaults chosen where the feature description was silent. Each one is a decision that can be revisited.

- **Target platform**: the pull requests, work items, and checklist repository all live in the same Team Foundation Server / Azure DevOps instance, reached through the single configured base address with the single configured access token. The token is assumed to carry read access to code and work items and write access to pull request comment threads.
- **Configuration file**: settings come from a `.env` file in the working directory, holding at least `TFS_BASE_URL`, `TFS_PAT_FOR_PR`, and `TFS_REPO_CODE_REVIEW_CodeReviewChecklistT`. The sample repository used in User Story 4 needs its own setting — assumed to be `TFS_REPO_CODE_SAMPLE` — which the original description referenced but did not list among the settings.
- **Review scope**: the agent reviews the lines the pull request changed, reading surrounding file content only as context. It does not audit untouched code, which would bury the author's actual change under pre-existing debt.
- **User stories as intent**: linked work items are treated as the authoritative statement of what the change was meant to do, and gaps against their acceptance criteria are reported as findings. Where a work item has no written acceptance criteria, its description is used instead.
- **Checklist extraction**: checklist documents are assumed to be human-authored prose and tables rather than a machine-readable rule format, so guideline items are extracted from their text.
- **Checklist discovery** *(decided in clarification, Session 2026-09-15)*: every `.xlsx` and `.docx` file anywhere in the checklist repository's default branch is in force, found by recursive search, with no filtering configuration. The tradeoff is accepted knowingly — it needs no setup and picks up new standards the moment they are committed, but it also picks up drafts, archived revisions, and non-checklist files that happen to share those extensions. The mitigation is transparency rather than filtering: FR-008a makes the agent name every document it used, so unintended guidance is visible in the review itself. Curating the repository stays a human responsibility.
- **Posting is the default**: findings are posted directly to the pull request, as the description asks. Preview mode is opt-in, not the default.
- **Report-only**: the agent never votes on, approves, rejects, blocks, or completes a pull request. It only adds comments; the decision stays with the human reviewer.
- **One run, one summary**: each run is independent and ends with its own summary comment. The agent does not edit or replace summary comments from earlier runs.
- **Run records** *(decided in clarification, Session 2026-09-15)*: each run writes one machine-readable report to a local folder; there is no rolling log and no report is sent anywhere. Reports accumulate locally and are the operator's to prune, and they carry source-code excerpts inside findings, so the folder deserves the same care as a working copy.
- **Duplicate suppression** *(decided in clarification, Session 2026-09-15)*: a finding's identity is its file plus the rule it cites, read back from the agent's own prior comments on the pull request. This keeps re-runs quiet across line drift and across machines. The accepted cost is that a second, genuinely distinct violation of the same rule in the same file produces no new comment — FR-020b covers it by noting the other occurrences inside the one comment that is posted.
- **Single pull request per run**: the agent reviews one pull request per invocation. Batch review across many pull requests is out of scope.
- **No automatic triggering**: local, on-demand invocation only. Reacting automatically to pull request creation or update is out of scope for this feature.
- **No code modification**: the agent never edits the code under review, pushes commits, or proposes committable fixes. Suggested remedies, where given, are prose inside a comment.
- **Language coverage**: review quality depends on the languages the checklists address; no per-language guarantee is made beyond what the team's own checklist documents cover.
- **Analysis engine** *(decided in clarification, Session 2026-09-15)*: evaluation is performed by a public hosted language-model service reached over the internet, configured alongside the other settings. The consequence is accepted deliberately: proprietary source code, internal coding standards, and work-item content leave the corporate network on every run, and adoption therefore depends on the organisation's data-handling policy permitting it (FR-032). The agent limits exposure to the changed-file content the review actually needs (FR-028) but does not eliminate it.
- **Operator trust**: the person running the agent is already an authorised member of the team with legitimate access to the repository, the work items, and the checklists. The agent grants no access the operator does not already have.
