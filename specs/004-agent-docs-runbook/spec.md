# Feature Specification: Agent Documentation and Manual Run Runbook

**Feature Branch**: `004-agent-docs-runbook`
**Created**: 2026-09-16
**Status**: Draft
**Input**: User description: "Document the file structure and code flow. How will the tool work and what will it perform . How to run manually steps"

## Overview

Four questions are asked of this project often enough that answering them from the code
each time is the cost: *what is in here*, *what happens when a review runs*, *what will
the tool actually do to my pull request*, and *how do I run it myself*. Partial answers
exist — the package README, the 002 walkthrough, the 003 demonstration, two quickstarts —
and they disagree with each other and, in places, with the code.

This feature produces one authoritative reference that answers all four, every claim
anchored to the code that proves it, with the disagreements resolved rather than
restated. It is a documentation feature: **no behaviour of the agent changes.**

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An operator runs a review by hand, first time (Priority: P1)

Someone who has never run this agent needs a review posted onto a specific pull request
today. They have a machine, access to the server, and no one available to ask. They
follow a numbered runbook from a clean checkout to a preview run, read the preview, then
repeat it as a posting run and confirm the comments landed on the pull request.

**Why this priority**: This is the only story that produces value on its own. Someone who
can run the tool can learn the rest by reading its output; someone who cannot run it gets
nothing from a structure map. It is also where the project currently loses the most time —
two settings the defaults get wrong each cost an afternoon when they are missed.

**Independent Test**: Hand the runbook to a person who has not run the agent, give them
credentials and a pull request identifier, and take nothing else. They reach a posted
review without asking a question and without editing a command.

**Acceptance Scenarios**:

1. **Given** a clean checkout and no configuration, **When** the operator follows the
   runbook steps in order, **Then** each step states the command, the expected visible
   output, and the symptom that means the step failed — and the operator reaches a
   completed preview run.
2. **Given** a completed preview run, **When** the operator follows the posting steps,
   **Then** the review appears on the pull request as inline comments plus one summary,
   and the runbook told them in advance which findings appear inline and which reach only
   the summary.
3. **Given** the operator uses the defaults for this server, **When** they reach the first
   step that contacts the server, **Then** the settings those defaults get wrong are
   stated at that step — not in an appendix reached after the failure.
4. **Given** the operator repeats the posting run unchanged, **Then** the runbook states
   what a second run is expected to do, and what it would mean if more comments appeared.
5. **Given** the operator has no server access at all, **Then** the runbook names the
   self-contained path that exercises the tool with no server, and says plainly what that
   path does and does not prove.

---

### User Story 2 - A maintainer finds where a behaviour lives (Priority: P2)

A developer has a change to make — a new finding kind, a different exclusion rule, an
extra checklist format. Before touching anything they need to know which file owns that
behaviour, what else that file is responsible for, and which rule they would break by
putting the change in the wrong place.

**Why this priority**: This is a project where most of what a task asks for already
exists, and where the expensive mistake is building a second copy of something already
present. A structure map is the cheapest available defence against that.

**Independent Test**: Give a reader five behaviours of the agent, named in plain language.
Using only the map, they name the correct owning file for each, and for each one they also
state which architectural rule constrains a change there.

**Acceptance Scenarios**:

1. **Given** the map, **When** a reader looks up any file that ships in the project,
   **Then** they find it listed with a one-line statement of what it is for.
2. **Given** a module that carries an architectural rule — sole owner of environment
   access, of the server protocol, of a provider's wire format, of the document formats —
   **When** the reader looks it up, **Then** the map states the rule and that a test
   enforces it.
3. **Given** files that exist deliberately and must never be "fixed" — faulty sample code,
   demonstration inputs, an unfilled template — **When** the reader encounters them,
   **Then** the map says so and says why.
4. **Given** the test suite, **When** a reader asks what proves a given behaviour, **Then**
   the map points them at the test group that covers it.

---

### User Story 3 - A reader traces one review end to end (Priority: P3)

Someone reviewing a finding, diagnosing an odd result, or planning a change needs to
follow a single review from the command that started it to the comment that appeared on
the pull request: what happens at each stage, what it hands to the next, and where the
path forks.

**Why this priority**: It converts the structure map from a list into an explanation.
Valuable, but a reader who can run the tool and read its phase log can approximate it; the
previous two stories cannot be approximated.

**Independent Test**: A reader follows the trace against the phase log of a real run and
matches every logged line to a stage in the document, with none left over on either side.

**Acceptance Scenarios**:

1. **Given** the trace, **When** a reader follows the straight-through path, **Then** every
   stage names what it receives, what it produces, and what the run prints when it
   completes that stage.
2. **Given** a run that departs from the straight-through path, **When** the reader looks
   for that path in the trace, **Then** it is documented — including: reviewing with the
   committed logic versus the working copy; document checklists versus the plain-text
   fallback; no linked story, or a token that cannot read one; nothing left to review after
   exclusions; a provider that is unreachable or answers unusably; preview versus posting;
   and a repeat run that finds its own earlier comments.
3. **Given** any stage in the trace, **When** the reader wants to check it, **Then** the
   stage cites the file and symbol that implements it.
4. **Given** a reader who wants to see a trace against real output, **Then** the trace
   links to the existing worked examples rather than reproducing them.

---

### User Story 4 - A stakeholder decides whether to trust it (Priority: P4)

A lead deciding whether to put this in front of their team needs a straight statement of
what the tool will and will not do: what it looks for, what it will comment on, what it
will never comment on, what can block a build, and what it cannot know.

**Why this priority**: It changes an adoption decision rather than a working session, and
much of it can be inferred from a review's own output once the tool is running.

**Independent Test**: A reader answers, without opening any source file: which findings
comment inline, which reach only the summary, which never produce a comment, what causes
each non-zero exit, and what the tool cannot determine.

**Acceptance Scenarios**:

1. **Given** the capability statement, **When** a reader asks what happens to each kind of
   finding, **Then** they get inline / summary-only / never, and whether it can block.
2. **Given** the same statement, **When** a reader asks what the tool cannot do, **Then**
   the limits are stated as plainly as the capabilities — including the bounds on how much
   of a pull request is reviewed, and that the tool reasons over diff text and cannot
   observe running behaviour.
3. **Given** a capability that an existing project document claims but the code does not
   support, **Then** the statement says so and names the document that is wrong.
4. **Given** an exit code, **When** a reader looks it up, **Then** they find what it means
   and what a person should do about it.

---

### Edge Cases

- **An existing document contradicts the code.** The reference must state which one is
  right, in a form a reader cannot mistake for a second opinion — this has already happened
  three times and cost a survey to discover.
- **A claim cannot be verified without a live server.** It must be marked unobserved rather
  than asserted, following the project's own convention that a claim closed by reasoning
  alone is not closed.
- **The code changes after the document is written.** The reference must say what it was
  verified against and on what date, so a later reader can tell fresh from stale.
- **A reader copies an example containing a credential.** No real credential, token, live
  host name, or live project identifier may appear; placeholders only.
- **A command is copied on a different shell than it was written for.** The runbook states
  which shell its commands are written for and what changes on the alternative.
- **A file is added or deleted after this document ships.** The document says what part of
  itself must be updated, so the next change does not silently rot it.
- **A reader arrives expecting a walkthrough.** The reference states, in its first screen,
  what it covers and what the two existing worked examples cover, and sends them to the
  right one.

## Requirements *(mandatory)*

### Functional Requirements

#### The deliverable

- **FR-001**: The feature MUST deliver a single documentation entry point that answers all
  four questions — file structure, code flow, capabilities, manual run — and that is
  reachable from the package README.
- **FR-002**: The reference MUST state, within its opening section, what it covers and what
  the existing worked examples and quickstarts cover, with links, so a reader can tell
  within one screen whether they are in the right document.
- **FR-003**: The reference MUST NOT reproduce content that an existing project document
  already carries correctly; where that content is needed it MUST be linked, and the link
  MUST say what the reader will find there.

#### File structure

- **FR-004**: Every file and directory that ships in the repository MUST appear in the
  structure map with a one-line statement of its purpose — application package, tests,
  specification artifacts, configuration, and project-root files.
- **FR-005**: For each module, the map MUST state its single responsibility and any
  architectural rule it carries, and MUST state that those rules are test-enforced.
- **FR-006**: The map MUST identify files that exist deliberately in a state that looks
  like a defect — faulty sample code, demonstration inputs, an unfilled template — and say
  that they are not to be repaired.
- **FR-007**: The map MUST group the test suite by what each group proves, so a reader can
  find the test that covers a behaviour they are changing.

#### Code flow

- **FR-008**: The reference MUST trace one complete review from the invoking command to the
  posted result, stage by stage, naming for each stage its input, its output, and the line
  it contributes to the run's phase log.
- **FR-009**: The trace MUST document every alternate path listed in User Story 3
  acceptance scenario 2, each with the condition that selects it, the visible signal that
  it was taken, and the resulting outcome.
- **FR-010**: The trace MUST state which entry point performs which role, including the
  difference between reviewing with the committed logic and reviewing with the working
  copy, and how a reader can tell from the output which one ran.
- **FR-011**: Each stage MUST cite the file and symbol that implements it.

#### Capabilities

- **FR-012**: The reference MUST state every kind of finding the tool produces, and for
  each: whether it can appear as an inline comment, whether it reaches the summary, and
  whether it can cause a non-zero exit.
- **FR-013**: The reference MUST state what decides inline placement, in terms of the rule
  the code actually applies.
- **FR-014**: The reference MUST state every exit code, its meaning, and the action a
  person should take on it — including any code that is defined but never returned.
- **FR-015**: The reference MUST state the tool's limits as explicitly as its capabilities:
  the bounds on how much of a pull request is reviewed, what the tool cannot determine from
  diff text, and what it does not produce at all.
- **FR-016**: Where a capability is claimed by an existing project document but not
  supported by the code, the reference MUST record the correction and name the document.

#### Manual run

- **FR-017**: The runbook MUST give numbered steps from a clean checkout to a posted
  review: obtain the code, install dependencies, supply configuration, run in preview, read
  the preview, run posting, and confirm the result on the pull request.
- **FR-018**: Each step MUST state the command to run, the output that means it worked, and
  the symptom that means it did not, with the corrective action for each stated symptom.
- **FR-019**: The runbook MUST present the settings whose defaults are wrong for this
  environment at the step where they first matter, not in an appendix.
- **FR-020**: The runbook MUST state every credential permission the run depends on, and
  what degrades or fails if a permission is missing.
- **FR-021**: The runbook MUST state what a repeat posting run is expected to do, and what
  observation would indicate it is misbehaving.
- **FR-022**: The runbook MUST name a path that can be exercised without server access, and
  state what that path does and does not demonstrate.
- **FR-023**: The runbook MUST name the shell its commands are written for, and state what
  changes for the alternative available in this project.
- **FR-024**: The runbook MUST include the command that verifies the installation is sound
  before any server is contacted, with the result that counts as passing.

#### Accuracy and upkeep

- **FR-025**: Every factual claim about the tool MUST be traceable to the code that proves
  it, by file and symbol, so a reader can check it without searching.
- **FR-026**: The reference MUST distinguish claims verified by executing something from
  claims read from the code, and MUST mark as unobserved anything that could not be
  verified in the authoring environment.
- **FR-027**: The reference MUST record which version of the code it was verified against
  and the date of that verification.
- **FR-028**: The reference MUST NOT contain any real credential, token, live host name, or
  live project identifier; placeholders only.
- **FR-029**: The reference MUST state what must be updated in it when a module, an entry
  point, a configuration setting, or a finding kind is added or removed.
- **FR-030**: Producing this documentation MUST NOT change the behaviour of the tool; the
  existing test suite MUST pass unchanged at the end of the feature.

### Key Entities

- **Documentation reference**: The single deliverable. Has an audience statement, a
  verification record, and four parts — structure, flow, capabilities, runbook.
- **Structure entry**: One file or directory. Carries its purpose, its responsibility, any
  architectural rule it holds, and whether it is a deliberate non-defect.
- **Flow stage**: One step of a review. Carries its input, its output, its visible signal in
  the run log, its implementing file and symbol, and the alternate paths that leave it.
- **Alternate path**: A departure from the straight-through review. Carries its triggering
  condition, its visible signal, and its outcome.
- **Capability entry**: One kind of finding, or one exit code. Carries its routing — inline,
  summary, never — whether it can block, and what a person should do about it.
- **Run step**: One numbered instruction. Carries its command, its success signal, its
  failure symptom, and the corrective action.
- **Source anchor**: The file-and-symbol citation attached to a claim, by which a reader
  checks it.
- **Correction record**: A claim in an existing project document that the code contradicts.
  Carries the document, the wrong claim, the true one, and the evidence.
- **Verification record**: What was executed, what was only read, what remains unobserved,
  against which version of the code, on what date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person who has never run the agent completes a preview run against a real
  pull request using only the runbook, within 30 minutes, without asking a question and
  without editing any command as written.
- **SC-002**: Every command in the runbook is executed as written during verification; 100%
  run as printed, and any that cannot be executed in the authoring environment is marked
  unobserved rather than presented as verified.
- **SC-003**: Given five behaviours of the agent named in plain language, a reader using
  only the structure map identifies the owning file for 5 of 5, and the constraining
  architectural rule wherever one applies.
- **SC-004**: Every line the agent prints to its run log during a straight-through review
  maps to exactly one documented stage, and every documented stage maps to what the run
  shows — no stage without a signal, no signal without a stage.
- **SC-005**: A reader answers, without opening any source file, which findings appear
  inline, which reach only the summary, which never produce a comment, what causes each
  non-zero exit, and three things the tool cannot do.
- **SC-006**: A spot check of 10 claims chosen at random finds all 10 carrying a citation,
  and all 10 matching the code they cite.
- **SC-007**: Every contradiction between an existing project document and the code found
  during authoring is recorded as a correction; none is left unreconciled or silently
  repeated.
- **SC-008**: No real credential, token, live host name, or live project identifier appears
  anywhere in the deliverable.
- **SC-009**: The test suite passes unchanged after the feature, at the same count as
  before it.
- **SC-010**: 100% of files and directories that ship in the repository appear in the
  structure map.

## Assumptions

- **Audience is internal**: the team's own developers and operators. Nothing here is
  written for an external customer, and no marketing framing is required.
- **The deliverable lives with the feature**, under this feature's directory, and is linked
  from the package README — the same shape the two previous documentation features used,
  which keeps the README a summary and the depth one link away.
- **The package README stays**, and is corrected where this feature finds it wrong rather
  than being replaced. It is the first thing a reader meets, and rewriting it wholesale is
  outside this feature.
- **Verification is honest rather than complete.** Anything that can be run in the authoring
  environment is run and its output quoted; anything needing a live pull request, a live
  provider, or credentials that are not available is marked unobserved, with the
  observation that would close it. This follows the project's existing convention that a
  claim closed by reasoning alone is not closed.
- **The primary shell is the one this project already scripts for** on the developer
  machines in use; the alternative available here is named wherever behaviour differs.
- **Existing worked examples remain authoritative** for their own paths and are linked, not
  restated.
- **Past features' specification directories are documented as artifacts** — what they are
  and which are still current — not summarised in content.
- **No agent behaviour changes.** Where documenting reveals a defect, it is recorded as a
  correction and left for a future feature; the only code that may change is a link or a
  comment that is factually wrong.

## Out of Scope

- Changing any behaviour of the agent, including the open gaps this documentation will
  describe (no run report is written, no severity threshold exists, a defined exit code is
  never returned).
- Replacing the package README, the operator quickstarts, or either existing worked
  example.
- Generating documentation automatically from source, or introducing a documentation build,
  site, or publishing pipeline.
- Documentation of the pipeline-hosted mode beyond what a manual runner needs to know; the
  manual run is the subject.
- Translating or re-hosting any of this material outside the repository.
