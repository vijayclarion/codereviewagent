# Feature Specification: Complete Worked Example — Create a Pull Request and Run the Review Agent

**Feature Branch**: `002-pr-review-walkthrough`
**Created**: 2026-09-15
**Status**: Draft
**Input**: User description: "Document complete example to create pull request and run the code review agent"

## Context

Feature 001 delivered the agent and a runbook sketch (`specs/001-pr-code-review-agent/quickstart.md`, Part 2). That sketch tells an operator *what kind* of artifacts to create — "a checklist violation, e.g. an unparameterised SQL string", "a `low`-severity nit" — but not *which ones*. Every reader must invent the sample change, guess whether their invention will actually trip the rule they intended, and then has no reference for what a correct run looks like. Two operators following it today produce two different demonstrations, and neither can tell whether a missing finding means the agent is broken or their sample was.

This feature closes that gap: one document containing the complete example, with every artifact given in full, so that following it is transcription rather than invention.

## Clarifications

### Session 2026-09-15

- Q: Does this feature include the live verification run — a real pull request in the sample repository and real analysis calls — or does it deliver the document for later verification? → A: Perform the live run end to end as part of the feature, including posting and the repeat run. The document records observed results, not predicted ones.
- Q: Is the sample change delivered as code blocks inside the walkthrough, or as committed example files the reader copies from disk? → A: Committed example files stored alongside the walkthrough, referenced by it. The reader copies files rather than transcribing them.
- Q: Does the walkthrough target the agent as it behaves today, with its known gaps open, or the agent as it will behave once those gaps are closed? → A: Today's agent. Findings that depend on a capability not yet wired in are documented as expected-absent with the reason. The walkthrough is not blocked on that work and requires no change to the agent.
- Q: What language is the sample change written in? → A: Whichever language the sample repository already predominantly contains, determined by inspecting it during implementation; Python if the repository is empty or has no dominant language.
- Q: Where does the walkthrough live, and what becomes of the existing runbook sketch in feature 001's quickstart? → A: In this feature's own directory, beside its example files, linked from the project's context file and the agent's own documentation. Feature 001's quickstart Part 2 is replaced by a pointer to it; its Part 1 remains authoritative for operator setup.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stand up the sample pull request from given artifacts (Priority: P1)

An operator who has never used the agent opens one document and, without inventing any content, produces a sample work item and a sample pull request in the sample repository. The work item text, the acceptance criteria, the source files before and after the change, the branch name, and the pull request title and description are all supplied verbatim. Each deliberate fault planted in the change is labelled with the finding it is expected to produce.

**Why this priority**: Nothing else in this feature can be exercised until a sample pull request exists that is known to contain the faults the demonstration depends on. This story alone already replaces the highest-friction part of the current runbook — an operator who stops here has a reproducible sample pull request other people can review against.

**Independent Test**: Hand the document to someone who has not seen the repository. Without asking a question, they produce a linked work item and pull request in the sample repository whose diff contains every labelled fault. No agent run is needed to test this story.

**Acceptance Scenarios**:

1. **Given** an operator with access to the sample repository and the document open, **When** they follow the setup steps in order, **Then** a sample work item exists with the exact title, description, and acceptance criteria given in the document.
2. **Given** the setup steps, **When** the operator creates the sample branch, **Then** the resulting diff contains every deliberate fault described, each one labelled in the document with the finding it should produce and the checklist rule or acceptance criterion behind it.
3. **Given** the setup steps, **When** the operator opens the pull request, **Then** its title and description match the text given in the document, including the description's deliberately false coverage claim.
4. **Given** the completed setup, **When** the operator checks the pull request, **Then** the sample work item is linked to it, and the document states plainly what the run will lose if that link is missing.
5. **Given** an operator whose sample repository already contains a previous sample branch, **When** they follow the setup, **Then** the document tells them how to name this run's artifacts so the two do not collide.

---

### User Story 2 - Run the agent and confirm the run matched the example (Priority: P1)

The operator runs the agent against the sample pull request, first in preview and then posting, and compares what they see against an expected-result reference in the same document. The reference states, for each deliberate fault, the finding it produces, its severity, and where that finding is expected to appear — anchored to a line, or in the summary only. A checkpoint list lets the operator confirm the run matched before spending a posting step.

**Why this priority**: The example exists to demonstrate the agent. A reader who can create the sample but cannot tell whether the run succeeded has not been helped. Paired with Story 1 this is the whole deliverable; it is separated only because the two can be verified independently.

**Independent Test**: Against an already-prepared sample pull request, follow the run section alone. Confirm the preview output can be checked item by item against the expected-result reference, and that following the posting step puts comments on the pull request.

**Acceptance Scenarios**:

1. **Given** a prepared sample pull request, **When** the operator runs the documented preview command, **Then** the command is reproduced exactly as it must be typed, and the document states what output confirms success and what the run's exit status should be.
2. **Given** the preview output, **When** the operator compares it with the expected-result reference, **Then** every expected finding is traceable to the specific fault that caused it and to the checklist rule or acceptance criterion cited.
3. **Given** a confirmed preview, **When** the operator runs the documented posting command, **Then** the document states which comments should appear, on which file and line, and that exactly one summary comment is expected.
4. **Given** a completed posting run, **When** the operator runs the agent again against the unchanged pull request, **Then** the document states that no new comments should appear and how to confirm that the repeat findings were recognised as already posted.
5. **Given** the documented run steps, **When** the operator reads them, **Then** preview is presented as the step that precedes posting, and the document states what posting makes visible to the team.

---

### User Story 3 - Recover when the run does not match (Priority: P2)

The operator's run deviates — a finding is missing, a comment lands nowhere, the agent refuses to start. The document maps each deviation an operator can plausibly hit during *this specific walkthrough* to its cause and its fix, including the deviations that are expected and harmless given the agent's current state.

**Why this priority**: A walkthrough that only describes the happy path fails the first reader whose environment differs, and the agent has known conditions — an incomplete local configuration, a checklist source that currently yields nothing — that will make a first run look broken when it is behaving as built. Valuable, but only once Stories 1 and 2 give the operator something to deviate from.

**Independent Test**: Introduce each documented deviation deliberately (omit the work-item link, skip the configuration fix, target a pull request that is already abandoned). Confirm the document names the symptom and the operator resolves it without consulting anyone.

**Acceptance Scenarios**:

1. **Given** a run that stops before contacting anything, **When** the operator looks up the message, **Then** the document names the setting to change and states that the run cannot succeed until it is changed.
2. **Given** a run that reports a degraded or incomplete review, **When** the operator looks it up, **Then** the document distinguishes conditions that need fixing from conditions that are expected in the agent's current state and require no action.
3. **Given** a deviation in the findings — an expected finding absent, or an unexpected one present — **When** the operator looks it up, **Then** the document states the most likely cause in the sample setup and how to correct the sample.
4. **Given** any documented symptom, **When** the operator applies the stated fix, **Then** the document names the step to resume from rather than requiring the walkthrough to be restarted.

---

### User Story 4 - Leave nothing behind (Priority: P3)

Having demonstrated the flow, the operator reverses every change the walkthrough made: the pull request, the branch, the work item, and any local files the run produced that contain source excerpts.

**Why this priority**: The walkthrough runs in a shared sample repository and produces local artifacts containing copied source. Cleanup is short and mechanical, but its absence means each demonstration leaves residue that pollutes the next one and may retain content that should not persist. It is last because the demonstration delivers its value before teardown.

**Independent Test**: Run the teardown section against a completed walkthrough. Confirm by inspection that the sample repository is back to its prior state and no local run artifact remains.

**Acceptance Scenarios**:

1. **Given** a completed walkthrough, **When** the operator follows the teardown steps, **Then** the sample pull request is closed without merging and the document states explicitly that nothing from the sample is to be merged.
2. **Given** the teardown steps, **When** they are complete, **Then** the sample branch and sample work item are removed or retired, and no local artifact containing copied source remains.
3. **Given** a teardown performed after a posting run, **When** it is complete, **Then** nothing outside the sample repository has been altered.

---

### Edge Cases

- **The operator has no write access to the sample repository**: the walkthrough states the access needed up front, as a prerequisite that is checked before any setup work, rather than failing at the point of opening the pull request.
- **The operator's local configuration is incomplete**: the known-broken settings are corrected as a numbered prerequisite step, before the first command that costs anything, and the document states how to confirm the fix worked.
- **The checklist source yields nothing**: this is the agent's current expected state. The walkthrough says so plainly at the point the operator will see the warning, states which findings will be absent as a result, and does not present the run as a failure.
- **No work item is linked to the pull request**: the run still completes, but the requirement-alignment findings — the headline of the demonstration — will not appear. The document treats the link as mandatory and says what its absence costs.
- **The sample repository's default branch has moved** since the example was written: the document specifies the target branch by role rather than by a fixed name.
- **A previous walkthrough's artifacts still exist**: naming guidance prevents collision, and teardown covers the leftovers.
- **The operator runs the posting step twice**: the document presents this as a step to perform deliberately, with the expected result stated, rather than as an accident to avoid.
- **The pull request is abandoned or completed before the run**: the document states the pull request must be active and what the agent reports if it is not.
- **The document drifts from the agent**: a command, flag, message, or exit status quoted in the document no longer matches the agent. The document names where each quoted element comes from so a change to the agent has an identifiable effect on the document.
- **The operator wants to demonstrate without posting**: the preview path is complete on its own and the document says which checkpoints can be satisfied from preview alone.
- **The reader's terminal cannot render the agent's output characters**: the document notes what is display-only and must not be mistaken for a failure.

## Requirements *(mandatory)*

### Functional Requirements

#### Scope and placement

- **FR-001**: The walkthrough MUST be a single document that carries the example from an unprepared machine to comments posted on a pull request, without requiring the reader to consult another document to complete any step.
- **FR-002**: The walkthrough MUST live in this feature's own directory, beside the example files it references, and MUST be reachable by a link from the project's context file and from the agent's own documentation, so a reader who starts at either entry point finds it without knowing its path.
- **FR-003**: The walkthrough MUST NOT duplicate the operator-setup material that already exists; where it depends on that material it MUST reference it at a named point, and MUST NOT leave two versions of the same instruction to drift apart.
- **FR-003a**: The runbook sketch in feature 001's quickstart MUST be replaced by a pointer to this walkthrough, so exactly one runbook for this flow exists. That quickstart's operator-setup material MUST remain in place and MUST remain the authority the walkthrough defers to.

#### Prerequisites

- **FR-004**: The walkthrough MUST open with a prerequisite section listing everything required before step one: the access rights needed on the sample repository and on work items, the local tooling required, and the configuration corrections known to be outstanding.
- **FR-005**: The walkthrough MUST give the reader a way to confirm each prerequisite is satisfied before proceeding, and MUST place these confirmations before any step that contacts a remote system or consumes a paid analysis call.
- **FR-006**: The walkthrough MUST state, before the reader creates anything, that the demonstration sends source code and work-item content to an external analysis service.

#### The sample artifacts

- **FR-007**: The walkthrough MUST supply the sample work item's title, description, and acceptance criteria verbatim, ready to be copied without editing.
- **FR-008**: The walkthrough MUST identify which acceptance criterion is deliberately left unimplemented, and MUST explain what that omission is there to demonstrate.
- **FR-009**: The walkthrough MUST supply the complete content of every file the sample change adds or modifies as ready-made example files stored alongside the walkthrough, so the reader copies them rather than transcribing them and never decides what the code should say.
- **FR-009a**: The example files MUST be stored beside the walkthrough in this feature's directory, where they are not picked up by the agent's own automated checks and cannot be mistaken for part of the agent, and the walkthrough MUST name their location.
- **FR-009b**: The walkthrough MUST NOT restate the example files' contents in full in its own body; it MUST reference them, so there is only one copy of the faulty code to keep correct.
- **FR-009c**: The example files MUST be written in the language the sample repository predominantly contains, established by inspecting that repository before the files are written, defaulting to the agent's own language if the repository is empty or has no dominant language. The walkthrough MUST state which language was chosen and on what basis, so a later reader can tell whether the sample still fits the repository.
- **FR-010**: The walkthrough MUST label each deliberate fault in the sample change with the finding it is expected to produce, the severity expected, and the checklist rule or acceptance criterion that produces it.
- **FR-011**: The sample change MUST produce at least one finding that cannot be anchored to a changed line, so that the demonstration exercises the distinction between findings posted inline and findings reported only in the summary. That finding MUST NOT depend on the checklist source, since the checklist source yields nothing in the agent's current state.

  *Amended 2026-09-15 during planning.* This originally required a fault "below the inline-comment threshold". The agent has no severity threshold: placement is decided by whether a finding anchors to a changed line, not by severity (`review_agent/output_layer.py:87-137`). The original wording described behaviour the agent does not have. When a configurable threshold is introduced, this requirement reverts to severity-based wording. See `plan.md` § Reality Reconciliation R1.
- **FR-012**: The walkthrough MUST supply the pull request title and description verbatim, including the deliberately false claim that the unimplemented criterion is covered.
- **FR-013**: The walkthrough MUST state how the sample artifacts are to be named so that repeated demonstrations do not collide with each other.
- **FR-014**: The sample change MUST be confined to the designated sample repository and MUST NOT touch the agent's own code or any production repository.

#### Creating the pull request

- **FR-015**: The walkthrough MUST give the steps to create the sample branch, commit the sample change, open the pull request against the repository's default branch, and link the sample work item to it — in the order they must be performed.
- **FR-016**: Where a step must be performed through the source-control system's web interface, the walkthrough MUST name the specific screen and control, not merely the outcome.
- **FR-017**: The walkthrough MUST state what each step should look like when it succeeded, so the reader can confirm before moving on.
- **FR-018**: The walkthrough MUST state that the work-item link is required and name the findings the demonstration loses without it.

#### Running the agent

- **FR-019**: The walkthrough MUST give the exact command to preview the review, and MUST place the preview run before any run that writes to the pull request.
- **FR-020**: The walkthrough MUST give the exact command to post the review, and MUST state what becomes visible to other people when it is run.
- **FR-021**: The walkthrough MUST provide an expected-result reference listing, for every deliberate fault, the finding produced, its severity, and whether it is expected on a line or in the summary only.
- **FR-022**: The walkthrough MUST provide a checkpoint list the reader can work through against their own preview output before posting.
- **FR-023**: The walkthrough MUST state the run's expected completion status, and MUST explain what each other completion status the reader could receive means for this walkthrough.
- **FR-024**: The walkthrough MUST include a repeat run against the unchanged pull request as a required step, state that it must add no further comments, and state how the reader confirms that.
- **FR-025**: The walkthrough MUST state where to look in the pull request to confirm that comments landed on the intended file and line, and that exactly one summary comment was added.
- **FR-026**: The walkthrough MUST distinguish, in its expected results, the findings that depend on the checklist source from those that do not, and MUST mark the checklist-dependent ones as expected-absent in the agent's current state, giving the reason.
- **FR-026a**: The walkthrough MUST NOT instruct the reader to look for any output, artifact, or comment the agent does not currently produce. A checkpoint the reader cannot satisfy today MUST NOT appear in the checkpoint list.
- **FR-026b**: The demonstration MUST remain meaningful with the checklist source yielding nothing: the requirement-alignment findings drawn from the linked work item MUST be sufficient on their own to exercise inline comments, the summary comment, the severity threshold, and the repeat run.

#### Recovery

- **FR-027**: The walkthrough MUST provide a symptom-to-resolution reference covering the failures reachable from its own steps, giving for each the symptom as the reader will see it, the cause, the fix, and the step to resume from.
- **FR-028**: The symptom reference MUST separate conditions requiring a change of setting from conditions that are transient and worth retrying, and MUST mark the conditions that are expected in the agent's current state and need no action.

#### Teardown

- **FR-029**: The walkthrough MUST provide teardown steps that reverse every change it made, and MUST state explicitly that the sample pull request is to be closed without merging.
- **FR-030**: Teardown MUST cover local artifacts produced by the run that contain copied source, not only the remote artifacts.

#### Safety and maintenance

- **FR-031**: The walkthrough MUST NOT contain any credential, token, or other secret, and MUST NOT contain a real host address, project name, or identifier that would expose the organisation's environment; placeholders MUST be visibly distinguishable from literal values.
- **FR-032**: Every command, message, completion status, and setting name quoted in the walkthrough MUST be attributable to the part of the agent that defines it, so that a change to the agent has a locatable effect on the walkthrough.
- **FR-033**: The walkthrough MUST state the date it was last verified against a real run, and against which version of the agent, so a reader can judge how far it may have drifted.

#### Verification of the walkthrough itself

- **FR-034**: The walkthrough MUST be verified by performing it end to end against the live sample repository before it is considered complete — creating the sample work item and pull request, running the preview, running the posting step, running the repeat step, and performing teardown.
- **FR-035**: Every expected result the walkthrough states MUST be one that was observed during that verification run, not one predicted from reading the agent. Where an expected result could not be observed, the walkthrough MUST say so rather than assert it.
- **FR-036**: Where the verification run reveals that the agent behaves differently from what the walkthrough author expected, the walkthrough MUST record the observed behaviour and MUST NOT be adjusted to describe the intended behaviour instead.
- **FR-037**: Teardown MUST be performed as part of the verification run, so the walkthrough's teardown steps are confirmed to work rather than assumed.

### Key Entities

- **Walkthrough document**: the single deliverable. Sections in execution order — prerequisites, sample artifacts, pull request creation, preview run, posting run, repeat run, recovery reference, teardown.
- **Sample work item**: the statement of intent for the demonstration. Carries a title, a description, and a fixed set of acceptance criteria, one of which is knowingly not implemented.
- **Sample change set**: a set of ready-made example files the operator copies into the sample repository and commits. Each fault they carry is deliberate and paired with the finding it is expected to produce. These files are the single source of truth for the sample code; the walkthrough points at them rather than reproducing them.
- **Sample pull request**: the subject of the review. Carries a title, a description containing a false coverage claim, a source branch, a target branch, and a link to the sample work item.
- **Expected-result reference**: the mapping from each deliberate fault to the finding, severity, and placement the reader should observe. This is what makes the run verifiable rather than merely performable.
- **Checkpoint list**: the reader's own pass/fail record, worked through against preview output before anything is posted.
- **Symptom reference**: the mapping from an observed deviation to its cause, its fix, and the step to resume from.
- **Teardown checklist**: the set of artifacts — remote and local — the walkthrough created and must remove.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator who has never run the agent completes the walkthrough — from opening the document to comments visible on the sample pull request — within 30 minutes.
- **SC-002**: Every step is executable as written: an operator following the walkthrough invents no content of their own and asks no clarifying question of a colleague. Measured by observing a first-time run and counting interruptions; the target is zero.
- **SC-003**: Two operators following the walkthrough independently produce sample pull requests that yield the same set of findings, category for category.
- **SC-004**: 100% of the findings the reader observes can be traced, using only the document, to the deliberate fault and the rule or acceptance criterion that produced them.
- **SC-005**: The repeat run adds zero further comments to the pull request.
- **SC-006**: The document contains zero credentials, tokens, real host addresses, or real project identifiers. Verifiable by inspection of the document alone.
- **SC-007**: At least 90% of the deviations a first-time operator encounters are resolved from the symptom reference without outside help.
- **SC-008**: After teardown, an inspection of the sample repository and the local machine finds no artifact created by the walkthrough.
- **SC-009**: A reader can tell, before running anything, which of the documented expected findings will be absent in the agent's current state and why.
- **SC-010**: 100% of the expected results stated in the walkthrough were observed during a real end-to-end run — including a posting run and a repeat run — rather than predicted. Verifiable from the walkthrough's own record of when and against what it was verified.

## Assumptions

- The walkthrough is written for the sample repository designated in the existing configuration; it does not introduce a new repository and it never targets a production one.
- The reader already has an account on the source-control system with access to the project. Obtaining that access is out of scope; the walkthrough only states what level is needed.
- The walkthrough is written for a single operator working on one machine. Automating it, running it in a pipeline, or scheduling it are out of scope.
- Where a step can be done either through the web interface or by command, the web interface is documented as the primary path — work-item linkage is done there in practice — with the command-line equivalent offered where one exists and is not more error-prone.
- The sample repository's contents can be inspected before the example files are written. If it proves inaccessible at that point, the fallback language applies and the walkthrough records that the choice was made without inspection.
- The walkthrough documents the agent as it behaves today, including its known degraded conditions. It is not a specification of behaviour to be built, and it does not require any change to the agent's code. Delivery of this feature is therefore not blocked on closing those gaps.
- When a gap is later closed, the walkthrough becomes the acceptance vehicle for it: findings currently marked expected-absent should start appearing, and the walkthrough is re-verified and its expected results updated at that point.
- The existing operator-setup material remains the authority on installation and configuration; the walkthrough carries the reader through it but does not become a second source of truth for it.
- Performing the verification run consumes real analysis calls against the external service and creates real artifacts in the sample repository. Working credentials, posting rights on the sample repository, and a funded analysis key are therefore prerequisites of *delivering* this feature, not only of reading it.
- The example files are committed to this repository as reference material, not as code this project builds or tests. They are deliberately faulty, so they must sit where nothing treats them as production or test code.
- "Single document" (FR-001) means a single document the reader follows; the example files it points at are part of the same deliverable, and copying a file from disk is not "consulting another document".
