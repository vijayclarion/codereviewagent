# Feature Specification: Checklist-Document Reviews from a Cloned Checklist Repository, with a Full-Cycle Demo

**Feature Branch**: `003-checklist-repo-review-demo`
**Created**: 2026-09-16
**Status**: Draft
**Input**: User description: ".env TFS_REPO_CODE_REVIEW_CodeReviewChecklist repo needs to be cloned to review the pull request based on the checklist in *.xlsx and *.docx files. Also user stories linked to PR request have to be used to review the PR. Please create full demo to test the full review cycle"

## Context

The original brief (`Req.md`) asks for three things the agent does not yet do together: read the team's real checklists — which are spreadsheets and Word documents, not markdown — review a pull request against the user story linked to it, and prove the whole cycle works by running it against a sample pull request.

Two of those three are present in the codebase but not connected to each other:

- **The document readers exist and are unused.** A component that turns `.xlsx` and `.docx` checklists into individually citable rules was built and unit-tested in feature 001, and nothing imports it. The path that actually runs fetches files over the collection's REST interface and returns their **text**, which cannot carry a spreadsheet or a Word document intact. This is feature 001's gap **G1**.
- **The checklist repository is never identified.** The setting the operator has in `.env` is spelled `TFS_REPO_CODE_REVIEW_CodeReviewChecklist`; the setting the agent looks for carries a trailing `T`. Nothing matches, no checklist repository is resolved, and every run reports that no checklist repository could be identified — then reviews against nothing. The default file selection is `*.md`, so even a correctly named repository would match none of the real documents.
- **Linked user stories already work.** Work items linked to the pull request are retrieved and their acceptance criteria are given an explicit verdict. This half needs verifying and demonstrating, not building — with one caveat the project has already paid for: a credential scoped to code alone is refused on the work-item read, and the review loses every requirement finding **without saying so**.

Feature 002 delivered a verified end-to-end walkthrough, but against markdown checklists and today's disconnected behaviour. This feature makes the real checklist corpus reviewable, makes every reduction in coverage state itself, and delivers a demonstration that exercises the complete cycle — story, documents, preview, posting, and a repeat run — against the sample repository.

## Clarifications

### Session 2026-09-16

- Q: Re-running `--post` duplicates every inline comment today, because a finding's identity is keyed on the provider's wording, which is regenerated each run. Repair it in this feature, or record it as a known defect the demonstration tells the operator to expect? → A: Repair it in this feature. Finding identity is re-keyed on stable inputs (rule identifier / criterion number, file, line); SC-007 stands as written and the demonstration's second run demonstrates suppression rather than duplication.
- Q: FR-037 requires the demonstration be executed once and record observed results — must that execution be live against the real collection, self-contained against fixtures, or both? → A: Both, with distinct jobs. A self-contained run is the repeatable proof of rule extraction, inventory, verdicts and degradation statements; one live run additionally proves working-copy acquisition, the work-item read, posting, and second-run suppression. Each recorded result names the run it came from.
- Q: When the rule corpus is larger than one review pass can carry, which rules survive? → A: Those most relevant to the change — rules are selected by their relation to the changed files (language, path, section). The applied set varies per pull request but MUST be deterministic for a given change and corpus, so two operators reviewing the same pull request apply the same rules.
- Q: SC-005 and SC-006 both rest on an operator who does not exist inside this feature — how are they validated? → A: By reproducing the self-contained run. SC-006 is checked by running the self-contained demonstration twice from a clean checkout and diffing the finding sets; SC-005 is restated as a per-step time budget summing to under 45 minutes, checked against the recorded run.
- Q: FR-009 requires a *stable* derived identifier where a document supplies none — stable against what? → A: Against the rule's own content. A derived identifier is a digest of source document, section, and rule text, so it survives row insertion, deletion and reordering, and changes only when the rule's wording changes. The document and section travel with the rule as the human-readable locator.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review a pull request against the team's real checklist documents (Priority: P1)

A reviewer runs the agent against a pull request. The agent obtains a working copy of the checklist repository named in the operator's configuration, reads every spreadsheet and Word document in it, and reviews the changed code against the individual rules those documents contain. Each violation the agent reports names the rule that was violated and the document it came from, so the author can look it up.

**Why this priority**: This is the half of the review the team actually asked for and the half that does not work today. Without it the agent reviews against no checklist at all and reports that run as a success.

**Independent Test**: Point the agent at a pull request with a known checklist violation, and at a checklist repository containing the rule that forbids it. Confirm the violation is reported and cites the rule identifier and the source document's filename. No user story and no posting step are needed to test this.

**Acceptance Scenarios**:

1. **Given** a configured checklist repository containing `.xlsx` and `.docx` documents, **When** a review runs, **Then** a working copy of that repository is obtained and every supported document in it is read.
2. **Given** a spreadsheet whose rules carry no identifier of their own, **When** it is read, **Then** each rule still receives an identifier derived from its own content that can be cited, and the run states that the identifier was derived rather than taken from the document.
3. **Given** a document whose rules carry derived identifiers, **When** rows are inserted above a rule, or rules are reordered, and the review is run again, **Then** that rule's identifier is unchanged and findings already raised against it are still recognised.
4. **Given** a Word document whose rules carry the team's own identifiers, **When** a violation of one is reported, **Then** the finding cites that identifier verbatim and names the document it came from.
5. **Given** a checklist repository, **When** a review runs, **Then** the run reports, for every document found, either the number of rules read from it or the reason it was skipped. No document is passed over in silence.
6. **Given** one document in the repository that cannot be read — encrypted, corrupt, or an unsupported format — **When** a review runs, **Then** that document is reported as skipped with its reason and the review continues against the remaining documents.
7. **Given** a checklist repository that cannot be reached at all, **When** a review runs, **Then** the review continues as a story-coverage-only review, states plainly that no checklist was applied and why, and does not report a failure.
8. **Given** a rule corpus larger than the review can carry in one pass, **When** a review runs, **Then** the rules applied are those most relevant to the changed files, and the run states how much of the corpus was applied, how much was left out, and that relevance was the basis. Truncation is never silent.
9. **Given** the same pull request and the same rule corpus, **When** the review is run twice, or by two different operators, **Then** the same rules are selected and applied both times.

---

### User Story 2 - Review a pull request against the user stories linked to it (Priority: P1)

The same review reads every work item linked to the pull request, takes its acceptance criteria, and gives each criterion an explicit verdict against the change: satisfied, contradicted, or outside this pull request's scope. Where the pull request's own description claims coverage the change does not deliver, the review says so.

**Why this priority**: Requirement coverage is the second half of the brief and the half a checklist cannot supply. It is P1 alongside Story 1 because a review that reports only style violations does not answer the question the reviewer is actually asking.

**Independent Test**: Against a pull request linked to a work item with several acceptance criteria — some satisfied by the change, at least one not — run a review with no checklist repository configured. Confirm each criterion receives a verdict and the unmet one is identified.

**Acceptance Scenarios**:

1. **Given** a pull request with one or more linked work items, **When** a review runs, **Then** every acceptance criterion of every linked work item receives an explicit verdict, identified by its number within its story.
2. **Given** a pull request with no linked work item, **When** a review runs, **Then** the review continues as a checklist-only review and states that no story coverage was assessed and why.
3. **Given** credentials that cannot read work items, **When** a review runs, **Then** the review states that story coverage was lost, names the access the credential is missing, and continues as a checklist-only review. It never reports the run as clean when the story was unreadable.
4. **Given** a pull request whose description claims to satisfy a criterion the change does not satisfy, **When** a review runs, **Then** the discrepancy is reported against the criterion it concerns.
5. **Given** a change that implements only part of a story, **When** a review runs, **Then** criteria outside this pull request's scope are distinguished from criteria the change contradicts, and the unaddressed ones do not become defects.

---

### User Story 3 - Run the full review cycle end to end as a demonstration (Priority: P1)

An operator follows one document from an unconfigured starting point to feedback visible on a pull request. It supplies the sample checklist documents, the sample work item and its acceptance criteria, the sample code change with every deliberate fault labelled, the commands to run, and — for each fault — the finding it should produce and where that finding should appear. The operator previews the review, checks it against the expected results, posts, and runs it once more to see what a second run does.

**Why this priority**: The brief asks explicitly for the flow to be tested. The first two stories can each be true in isolation while the cycle as a whole is broken; only running it proves otherwise. This story is the acceptance test for the feature.

**Independent Test**: Run the self-contained demonstration twice from a clean checkout and confirm both runs produce the same findings, matching the expected-results reference item by item. Then follow the live portion end to end, from an unconfigured start to a posted review, supplying no content the document does not provide and taking no longer than the per-step time budgets it states.

**Acceptance Scenarios**:

1. **Given** the demonstration document and access to the sample repository, **When** the operator follows the setup steps, **Then** a sample work item with the given acceptance criteria and a sample pull request containing every labelled fault exist, and the work item is linked to the pull request.
2. **Given** the sample setup, **When** the operator runs the documented preview command, **Then** the output can be checked item by item against an expected-results reference in which every finding traces to the fault that caused it and to the rule identifier or criterion number behind it.
3. **Given** the preview, **When** the operator inspects it, **Then** it confirms that spreadsheet rules and Word-document rules were both applied, and that the linked story's criteria were both read and judged.
4. **Given** a confirmed preview, **When** the operator runs the documented posting command, **Then** the document states which comments appear on which file and line, that exactly one summary is expected, and what the exit status should be.
5. **Given** a completed posting run, **When** the operator runs the review again against the unchanged pull request, **Then** the document states what the second run should do and how to confirm that already-posted findings were recognised.
6. **Given** an operator who has run the demonstration before, **When** they run it again, **Then** the document tells them how to name this run's artifacts and what to remove afterwards so that the two runs do not collide.
7. **Given** any step in the demonstration, **When** it is followed, **Then** no credential appears in the console output, in any posted comment, or in any file the run leaves behind.
8. **Given** any observed result recorded in the demonstration, **When** a reader inspects it, **Then** it states whether it came from the self-contained run or from the live run, and the self-contained portion can be reproduced with no server and no credential.

---

### User Story 4 - Diagnose a misconfigured checklist source before trusting the review (Priority: P2)

An operator whose configuration names no checklist repository, names one that cannot be reached, or selects no documents finds out which of those it is from the run itself, in terms that name the setting to change.

**Why this priority**: The condition this story addresses is the exact condition the project is in today, and it went unnoticed because the run reported success. It is P2 only because Stories 1-3 deliver the capability while this one makes its absence visible.

**Independent Test**: Run a review with the checklist repository setting empty, then naming a repository that does not exist, then naming a reachable repository containing no supported documents. Confirm each produces a different, actionable statement.

**Acceptance Scenarios**:

1. **Given** the checklist repository setting is absent, **When** a review runs, **Then** the run names the setting the operator must provide.
2. **Given** a checklist repository setting naming a repository that cannot be reached, **When** a review runs, **Then** the run distinguishes "not found" from "not permitted" and says which credential the access depends on.
3. **Given** a reachable repository in which the configured selection matches no document, **When** a review runs, **Then** the run reports the selection it applied, the branch it looked at, and that nothing matched — enough to correct it without guessing.
4. **Given** the settings the operator already has in place, **When** the agent reads them, **Then** it uses them under the names they already carry. An operator with a working configuration does not have to rename anything to get a checklist review.

---

### Edge Cases

- The checklist repository's working copy cannot be obtained because the version-control client is unavailable on the machine, or the credential is rejected — the review degrades to story-coverage-only with that reason stated.
- A document is password-protected or corrupt — skipped with its reason; the other documents still apply.
- A spreadsheet carries several sheets, only one of which holds rules — the rule-bearing sheet is used and the others are reported as ignored.
- A spreadsheet's identifier column is present but empty in every row — its rules are still citable.
- A Word document contains no rule identifiers at all — its rules are still extracted and still citable.
- The repository contains supported documents that hold zero rules — reported as read-but-empty, not as a failure.
- The combined rule corpus exceeds what one review pass can carry — the rules most relevant to the changed files are applied, and the operator is told what was applied, what was not, and on what basis.
- The pull request has several linked work items, or one linked item that is not a user story — all linked items are read and their criteria judged.
- The credential can read code but not work items — the review says story coverage was lost rather than reporting no requirement findings.
- The same review is run twice against an unchanged pull request.
- The sample repository already holds artifacts from a previous demonstration run.
- The checklist repository is large enough that taking a full copy would be wasteful — only what the review needs is retrieved.
- The temporary working copy does not survive the run, and never holds a credential on disk.

## Requirements *(mandatory)*

### Functional Requirements

#### Identifying and obtaining the checklist source

- **FR-001**: The agent MUST identify the checklist repository from the setting the operator already has in place, under the name it already carries in their configuration, and MUST continue to honour the names previously accepted so that no existing configuration breaks.
- **FR-002**: The agent MUST obtain a local working copy of the checklist repository — by a means capable of carrying binary documents intact — at the configured branch or reference.
- **FR-003**: Obtaining that working copy MUST retrieve only what the review needs, rather than the repository's full history.
- **FR-004**: No credential used to obtain the working copy may be written to disk, recorded in any stored setting of that copy, or appear in any output.
- **FR-005**: The working copy MUST be removed when the run ends, whether the run succeeded or failed.
- **FR-006**: Failure to obtain the working copy MUST degrade the review to story-coverage-only with a stated reason, and MUST NOT be reported either as a successful review or as a setup failure.
- **FR-007**: The documents considered MUST include spreadsheets and Word documents by default, and MUST remain adjustable by the operator without a code change. Adding a document to the checklist repository MUST require no configuration change.

#### Reading the checklist documents

- **FR-008**: Each supported document MUST be read into individually addressable rules, each carrying its rule text, its source document, and its section within that document.
- **FR-009**: Where a document supplies its own rule identifier, that identifier MUST be used verbatim. Where it does not, an identifier MUST be derived from the rule's own content — its source document, its section, and its text — and not from its position within the document, so that inserting, deleting or reordering rules does not change the identifier of any other rule. A derived identifier MUST change only when the rule's own wording changes. The rule MUST be marked as carrying a derived identifier.
- **FR-010**: A rule's severity MUST be carried through when the document states one, and MUST be absent rather than guessed when it does not.
- **FR-011**: Document content that exists to explain or justify a rule rather than to state it MUST NOT be carried into the review.
- **FR-012**: A document that cannot be read MUST be reported as skipped with its reason, and MUST NOT stop the run or affect any other document.
- **FR-013**: A document that is read but contains no rules MUST be reported as such, distinctly from one that could not be read.
- **FR-014**: The run MUST report a per-document inventory — every document found, and for each either its rule count or its skip reason. A document MUST NOT be passed over silently.
- **FR-015**: The entire corpus being unreadable MUST degrade the review with a stated reason, exactly as an unreachable repository does.
- **FR-016**: Where the rule corpus exceeds what one review pass can carry, the rules applied MUST be those most relevant to the change, selected by their relation to the changed files — language, path, and section. That selection MUST be deterministic: the same change against the same corpus MUST apply the same rules on every run and for every operator. The run MUST state how much of the corpus was applied, how much was omitted, and that relevance to the change was the basis of the selection.
- **FR-017**: Every checklist violation reported MUST cite the rule's identifier and the filename of the document it came from.
- **FR-018**: Checklist documents MUST NOT be treated as reviewable code, and MUST NOT appear in the review's changed-file counts or findings.

#### Reviewing against the linked user stories

- **FR-019**: The agent MUST retrieve every work item linked to the pull request and MUST extract the acceptance criteria of each.
- **FR-020**: Every acceptance criterion MUST receive an explicit verdict — satisfied, contradicted, or outside this pull request's scope — identified by its number within its story.
- **FR-021**: Criteria outside this pull request's scope MUST NOT be reported as defects.
- **FR-022**: A pull request with no linked work item MUST produce a checklist-only review with that stated as the reason.
- **FR-023**: Where the credential cannot read work items, the run MUST state that story coverage was lost and name the access the credential is missing. A refused work-item read MUST NOT be indistinguishable from a story against which nothing was found.
- **FR-024**: A claim in the pull request's own description that the change does not support MUST be reported against the criterion it concerns.

#### Reporting the review

- **FR-025**: A finding that anchors to a changed line MUST be reported against that line; a finding that does not MUST appear in the review's summary.
- **FR-026**: The review MUST produce exactly one summary, stating what was reviewed, what was applied, and every reduction in coverage that occurred during the run.
- **FR-027**: Preview MUST be the default, and MUST make no change to the pull request.
- **FR-028** *(amended during planning — see below)*: Running the same review twice against an unchanged pull request MUST NOT present the reviewer with feedback they have already seen. A finding already posted MUST be recognised on the later run by an identity that does not change between runs, and MUST NOT depend on the wording of the finding, which is regenerated on every run. Where the finding has a natural identifier — the rule identifier, or the acceptance criterion number within its story — that identifier alone, with the file, is the identity. Where it has none, the file and line stand in for one. The run MUST state how many already-posted findings it suppressed.

  > **Amendment, recorded rather than applied silently.** The clarification of 2026-09-16 answered "the rule identifier or criterion number … together with the file and line". Including the line for *every* finding kind would regress feature 001's FR-030: the line is deliberately excluded from a finding's identity today, because an unrelated edit above a finding shifts it and a line-sensitive identity re-posts the same comment on every push. The line therefore participates only for a code issue, which has no identifier to key on and would otherwise fall back to the provider's prose — the exact defect this requirement exists to fix. Rationale in `research.md` R7; the resulting behaviour is fully specified in `contracts/finding-identity.md`.
- **FR-029**: No credential may reach the console, the logs, the material sent for analysis, or anything posted to the pull request.

#### The demonstration

- **FR-030**: The feature MUST deliver a demonstration that an operator can follow from an unconfigured starting point to feedback posted on a pull request, inventing no content of their own.
- **FR-031**: The demonstration MUST supply sample checklist documents in both supported formats, carrying rules the sample change is known to violate, and MUST state how to place them in the checklist repository.
- **FR-032**: The demonstration MUST supply a sample work item whose acceptance criteria include at least one the sample change satisfies, at least one it contradicts, and at least one that lies outside its scope.
- **FR-033**: The demonstration MUST supply the sample code change with every deliberate fault labelled with the rule identifier or criterion number it is expected to trip.
- **FR-034**: The demonstration MUST cover the cycle in order — configure, obtain the checklists, preview, check against expected results, post, run again — and MUST state the expected outcome and exit status of each step.
- **FR-035**: The demonstration MUST include a checkpoint confirming that spreadsheet rules and Word-document rules were both applied and that the linked story's criteria were both read and judged, so that a review against an empty checklist cannot be mistaken for a successful one.
- **FR-036**: The demonstration MUST be repeatable: it MUST state how to name each run's artifacts and what to remove afterwards so that repeated runs do not collide.
- **FR-037**: The demonstration MUST be executed once as part of this feature, and MUST record observed results rather than predicted ones. That execution MUST take both forms, each with a stated job. A self-contained run, requiring no server and no credential, MUST be the repeatable proof of rule extraction, the per-document inventory, the per-criterion verdicts, and every degradation statement. One live run against the collection and a real pull request MUST additionally prove acquisition of the working copy, the linked work-item read, posting, and suppression of already-posted findings on a second run. Every recorded result MUST name which of the two runs produced it.
- **FR-038**: Any finding the demonstration expects but that today's agent cannot produce MUST be recorded as expected-absent with its reason, rather than quietly omitted.

### Key Entities

- **Checklist Repository Source**: The repository holding the team's coding standards, identified by the operator's configuration and obtained as a temporary working copy for the duration of a run. Carries the reference it was taken at, and the reason it is unavailable when it is.
- **Checklist Document**: One file from that repository. Carries its filename, its format, its outcome — read, read-but-empty, or skipped — its rule count, its skip reason, and any parts of it that were ignored.
- **Checklist Rule**: One individually citable requirement taken from a document. Carries an identifier — taken from the document, or derived from the rule's own content when the document supplies none — whether that identifier came from the document or was derived, its text, its section, its severity when stated, and the document it came from. The document and section together are the human-readable locator an author uses to look the rule up.
- **Rule Corpus**: The rules from all documents, assembled for one review. Carries how much of itself was applied, what was omitted, and the basis on which the applied rules were selected when not all of them fit.
- **Linked Work Item**: A work item attached to the pull request. Carries its identifier, its type, its title, its description, and its acceptance criteria.
- **Acceptance Criterion**: One numbered requirement from a work item, carrying the verdict the review reached on it.
- **Finding**: One reported problem, carrying its severity, the file and line it anchors to when it has one, and the rule identifier or criterion number it is raised against.
- **Run Inventory**: The record of what a single run actually applied — which documents, how many rules, which work items, how many criteria, and every reduction in coverage that occurred. This is what the demonstration's checkpoint is checked against.
- **Deliberate Fault**: One planted defect in the sample change, carrying the rule identifier or criterion number it is expected to trip and where its finding is expected to appear.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A review of the sample pull request cites at least one rule taken from a spreadsheet and at least one taken from a Word document, each by its own identifier and its source document's filename.
- **SC-002**: 100% of the documents present in the checklist repository are accounted for in the run inventory — each either read with a rule count or skipped with a reason. Zero documents are passed over without a statement.
- **SC-003**: 100% of the acceptance criteria of every work item linked to the pull request receive an explicit verdict.
- **SC-004**: Every condition that reduces what a review covers — no checklist repository, an unreachable one, no matching documents, unreadable documents, an omitted portion of the corpus, no linked story, or unreadable work items — produces a distinct statement naming the setting or the access to correct. Zero such conditions produce a run that reads as clean.
- **SC-005**: The demonstration carries a stated time budget for each of its steps, from an unconfigured start to feedback posted on a pull request, summing to under 45 minutes; the budgets are checked against the elapsed times recorded during this feature's own execution of it, and no step requires the operator to supply content the document does not provide.
- **SC-006**: The self-contained demonstration, run twice from a clean checkout, produces identical finding sets — same rule identifiers, same criterion numbers, same files and lines. A difference between the two runs is a defect.
- **SC-007**: Running the demonstration's posting step a second time against an unchanged pull request presents the reviewer with no feedback they have already seen.
- **SC-008**: No credential appears in any console output, any posted comment, or any file left on disk after a run — confirmed by inspection as a step of the demonstration.
- **SC-009**: A review whose checklist source is unavailable still delivers its story-coverage half, and a review whose linked story is unavailable still delivers its checklist half.
- **SC-010**: Adding a document to the checklist repository causes it to be applied on the next review with no configuration change.

## Assumptions

- **The configuration name in use wins.** The setting present in the operator's `.env` is spelled `TFS_REPO_CODE_REVIEW_CodeReviewChecklist`; the agent currently looks for a name with a trailing `T`, inherited from the original brief. The agent will accept the operator's spelling and will keep accepting the older names, so no existing configuration breaks. This is treated as a defect in the agent, not in the operator's configuration.
- **A working copy, not a document fetch.** The documents are spreadsheets and Word files, which the collection's text-oriented file interface cannot carry intact. Obtaining a working copy of the repository is therefore the acquisition path. The existing text-fetch path is retained where it still serves — for plain-text checklists — and is not the route by which documents arrive.
- **Markdown checklists remain supported.** Nothing in this feature removes the existing plain-text checklist path; spreadsheets and Word documents are added to the default selection alongside it.
- **The document readers already built are the readers used.** Feature 001 delivered and unit-tested components that read both formats against the real corpus. This feature connects them rather than replacing them, closing feature 001's gap **G1**.
- **Story coverage is already implemented.** Retrieval of linked work items, extraction of acceptance criteria, and per-criterion verdicts exist today. This feature's work on Story 2 is verification, the missing statement when a work-item read is refused, and demonstration.
- **Credential scope.** The credential reading the pull request needs work-item read access in addition to code access. The demonstration states this as a prerequisite, and a run without it reports the loss rather than proceeding quietly.
- **Collection interface version.** The demonstration states the interface version this collection requires, which is not the agent's default; getting it wrong returns a not-found response from every endpoint, with a misleading explanation.
- **The sample repository and the sample story.** The demonstration creates its own pull request in the existing sample repository rather than reusing feature 002's, and names its artifacts so the two coexist. Feature 002's walkthrough remains valid for the markdown path and is linked from this one, not replaced by it.
- **The checklist documents used by the demonstration are samples, not the team's internal standards.** The real corpus is internal and is not committed to this repository; the demonstration supplies sample documents in the same shapes the real ones use.
- **Preview remains the default and posting remains explicit.** A review is a reviewer's aid and does not gate a merge; that is unchanged.
- **Scope boundary.** This feature does not add a written run report to disk (feature 001's gap **G2**), does not introduce a severity threshold for inline-versus-summary placement, and does not change which exit statuses the agent returns. It does repair the re-posting duplication recorded by feature 002's verification run — finding identity keyed on regenerated prose — because the demonstration's second-run step and SC-007 both depend on a previously posted finding being recognised.
