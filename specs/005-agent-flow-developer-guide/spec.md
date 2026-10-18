# Feature Specification: Local-Mode Call Flow Diagram and Developer Onboarding Guide

**Feature Branch**: `005-agent-flow-developer-guide`
**Created**: 2026-09-17
**Status**: Draft
**Input**: User description: "I want details activity diagram of the flow of code and role of each method and file in call flow in case local mode when PR request send. Create the puml file for activity diagram in docs. Also explanation of file structure of project and what is the use of each file. How large change request is handled? What in case of token limit exceed?. I want the document to be simple and self explanatory so that other developer can easily understand and start working"

## Overview

A developer joining this project can already learn *how to run* the agent and *what it will
do to a pull request* — feature 004 answers that. What they still cannot get is the thing
they need before changing anything: a picture of the call flow, and a walk through it that
names, in order, which method in which file does what, from the moment they point the tool
at a pull request on their own machine to the moment a review is produced.

Three questions on top of that have no answer anywhere in the project today, and each is
asked the first time someone points the tool at a real, busy pull request:

- **How much of the project can the review actually see?** Whether it judges the change in
  isolation or against the surrounding codebase decides which findings it is capable of
  producing at all, and which it will get wrong. A developer who assumes the wrong answer
  either distrusts good findings or trusts findings the tool was never in a position to make.
- **What happens to a very large change?** Several independent limits reduce it, in a
  specific order, and each one leaves a different trace in the output.
- **What happens when the model's limits are hit?** The behaviour here is not what a reader
  would guess from the presence of chunking, and guessing wrong costs a lost review.

This feature produces a **visual activity diagram** plus a **plain-language companion
document**, both aimed at a developer on day one. It is a documentation feature:
**no behaviour of the agent changes, and no agent code is written.**

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A new developer sees the whole flow at once (Priority: P1)

Someone who has just cloned the repository opens one diagram and sees the entire path a
review takes when they run it locally against a pull request: where it starts, every stage
in order, every decision point, and where each path ends. They get this before reading any
prose and before opening any source file.

**Why this priority**: This is the single artefact the request centres on, and it is the
one thing that delivers value alone. A picture of the flow is useful to a reader who never
reads the companion text; the text without the picture is another wall of prose in a
project that already has several. The diagram is also the skeleton every later section
hangs from.

**Independent Test**: Give the diagram source file alone to a developer with a PlantUML
renderer and nothing else. They render it without editing it, and from the rendered image
alone they correctly state where a run begins, how many stages it passes through, and at
least three points where it can take a different path.

**Acceptance Scenarios**:

1. **Given** the diagram source file, **When** a developer renders it with a standard
   PlantUML tool, **Then** it renders without error and produces one readable activity
   diagram.
2. **Given** the rendered diagram, **When** a reader traces the default path top to bottom,
   **Then** every stage of a review appears exactly once, in the order the tool performs
   them, each labelled with the plain-language name a reader would search for.
3. **Given** the rendered diagram, **When** a reader looks at any stage, **Then** the file
   that owns that stage is identifiable from the diagram itself, without consulting the
   companion document.
4. **Given** the rendered diagram, **When** a reader looks for the points where a run
   stops early or changes course, **Then** each such point is drawn as a visible decision
   with every outcome labelled and terminating somewhere explicit — no path trails off.
5. **Given** the local-run entry point, **When** a reader compares it to the other way in,
   **Then** the diagram shows the difference between them and where the two paths rejoin.

---

### User Story 2 - A developer follows the flow method by method (Priority: P1)

A developer has the diagram and now needs the detail behind one box in it: which method is
called, in which file, what it receives, what it hands to the next stage, and what visible
output that stage produces. They read the flow as a sequence and can put their finger on the
exact place a change belongs.

**Why this priority**: The diagram and the walkthrough are one deliverable split in two
forms; a stage a reader cannot follow into the code is a stage they cannot change. This is
the half that turns "I can see the flow" into "I can start working", which is the stated
goal of the request.

**Independent Test**: Give a reader the companion document and five plain-language
behaviours of the agent. For each, using only the document, they name the stage it belongs
to, the file that owns it, and the method that performs it — then confirm by opening that
file that the named method exists.

**Acceptance Scenarios**:

1. **Given** the companion document, **When** a reader looks up any stage shown in the
   diagram, **Then** they find the ordered sequence of methods that stage performs, each
   with the file it lives in and a one-line statement of its role.
2. **Given** a named method in the document, **When** a reader opens the file it names,
   **Then** the method exists there with the role the document states.
3. **Given** the walkthrough, **When** a reader follows it end to end, **Then** the data
   handed from each stage to the next is named, so no stage's input appears from nowhere.
4. **Given** a stage that produces visible output, **When** a reader reaches it in the
   walkthrough, **Then** the document shows the line the run prints for that stage, so a
   reader can match a real run's output against the walkthrough position by position.
5. **Given** a decision point shown in the diagram, **When** a reader looks it up in the
   document, **Then** they find what selects each branch and what the run does next on each.

---

### User Story 3 - A developer finds what every file is for (Priority: P2)

Before making a change, a developer needs to know which file owns the behaviour they are
about to touch, what else that file is responsible for, and which files are not free to
change because a rule constrains them.

**Why this priority**: Valuable, and required by the request, but partially served already —
the project has an existing structure map. The work here is to make the map usable
*alongside the flow*, showing each file at the point it enters the call flow rather than as
an alphabetical list, and to avoid producing a second, competing copy of what exists.

**Independent Test**: Give a reader the structure section and the name of any file that
ships in the repository. They state what it is for and whether a rule constrains changes to
it, without opening the file.

**Acceptance Scenarios**:

1. **Given** the structure section, **When** a reader looks up any file or directory that
   ships in the project, **Then** they find it with a one-line statement of its purpose.
2. **Given** a file that carries an architectural rule, **When** a reader looks it up,
   **Then** the rule is stated along with the fact that a test enforces it.
3. **Given** the structure section, **When** a reader looks for a file's place in the flow,
   **Then** files that participate in a review are tied to the stage they serve, and files
   that do not participate are marked as such rather than left ambiguous.
4. **Given** the existing structure map elsewhere in the project, **When** a reader uses
   both, **Then** they do not contradict each other, and this document points at the
   existing one rather than restating it in full.

---

### User Story 4 - A developer learns how much of the project the review can see (Priority: P2)

A developer reads a finding and needs to know what the reviewer was looking at when it made
that judgement. Was it shown only the lines that changed, or the whole file, or the whole
project? They need to know which kinds of finding the tool is in a position to make, which it
structurally cannot, and what else besides the change itself is put in front of it.

**Why this priority**: This is the question that decides whether a reader trusts the output.
A developer who believes the reviewer sees the whole project will accept a confident claim
about a caller it never looked at; one who believes it sees only changed lines will dismiss a
correct finding as a guess. It also decides what is worth asking of the tool at all — a
checklist rule that can only be judged with project-wide knowledge will never be judged
correctly, and a developer writing checklist rules needs to know that before writing them.
Ranked below the flow itself only because a reader must know the flow exists before asking
what it carries.

**Independent Test**: Give a reader the document and four proposed checklist rules — some
answerable from a changed region alone, some requiring knowledge of unchanged code elsewhere.
Using only the document, they correctly sort them into "this tool can judge it" and "this
tool cannot", and explain why for each.

**Acceptance Scenarios**:

1. **Given** the document, **When** a reader asks what the reviewer is shown for a changed
   file, **Then** it states plainly whether that is the changed lines, the changed lines with
   surrounding context, or the whole file — and how much surrounding material accompanies a
   change.
2. **Given** a file that was not touched by the pull request, **When** a reader asks whether
   the reviewer sees it, **Then** the document answers plainly, and states whether it is
   retrieved at all.
3. **Given** the document, **When** a reader asks what else besides the change is placed in
   front of the reviewer, **Then** every other source of context is listed, with what each
   contributes.
4. **Given** a change that adds an entirely new file, **When** a reader asks what the
   reviewer sees of it, **Then** the document states how this case differs from a change to
   an existing file, because the difference is real and affects what can be judged.
5. **Given** a kind of finding that would require knowledge the reviewer does not have,
   **When** a reader looks for the limits of the review, **Then** the document names concrete
   examples of judgements the tool structurally cannot make, so a reader can recognise one.
6. **Given** a large change split across more than one pass, **When** a reader asks what each
   pass can see of the others, **Then** the document states it, since a pass judging part of a
   change sees less than the whole change.
7. **Given** material the tool retrieves but does not place in front of the reviewer, **When**
   a reader asks about it, **Then** the document distinguishes what is fetched from what is
   sent, rather than letting a reader assume the two are the same.

---

### User Story 5 - A developer predicts what a huge pull request will do (Priority: P2)

A developer is about to point the tool at a pull request with hundreds of changed files.
They need to know, before spending a provider call, how much of it will actually be
reviewed, what decides which parts are kept, what happens to the parts that are not, and
how they would tell from the output that a limit was reached.

**Why this priority**: Explicitly asked for, and unanswered anywhere today beyond a bare
list of limit names and default values. It is also where a reader's intuition is most
likely to be wrong — several limits interact, and the parts left out are reported rather
than dropped silently, which a reader will not assume.

**Independent Test**: Describe a pull request of a stated size to a reader who has only this
document. They correctly state how many files will be reviewed, what happens to the rest,
whether the work is split into more than one provider pass, and which output lines would
confirm it.

**Acceptance Scenarios**:

1. **Given** the document, **When** a reader looks for size handling, **Then** every limit
   that reduces a change before review is listed with what it bounds, its default value, the
   setting that changes it, and the order the limits apply in.
2. **Given** a change larger than a limit, **When** a reader asks what happens to the excess,
   **Then** the document states whether it is reported or silently dropped, and shows the
   output that reveals it.
3. **Given** a change that survives the limits but is still large, **When** a reader asks how
   it reaches the model, **Then** the document explains that it is split, what the split
   respects, and what each part of the split is told about the others.
4. **Given** a single item larger than the split size on its own, **Then** the document
   states what happens to it, because this case is the one that produces an oversized
   request.
5. **Given** the document, **When** a reader asks which parts of a large change are kept,
   **Then** the basis for choosing is stated in plain language, not merely named.

---

### User Story 6 - A developer knows what happens when a model limit is exceeded (Priority: P3)

A developer wants to know what the tool does when a request is too big for the model, or
when the model's answer is cut off before it finishes. They need to know whether the run
recovers, what is lost, what the exit code is, and what they would see.

**Why this priority**: Explicitly asked for, and the answer is the least guessable thing in
the project: the presence of splitting strongly implies a size-aware safeguard that does not
exist, and the failure of one part does not cost only that part. Placed at P3 only because
it is narrower than the five above — it is a section, not a document.

**Independent Test**: Ask a reader who has only this document what the tool does when a
request exceeds the model's limit. They state the outcome, what is lost, the exit code, and
the message a person would see — and each answer matches what the code does.

**Acceptance Scenarios**:

1. **Given** the document, **When** a reader asks whether the tool measures a request
   against the model's limit before sending it, **Then** the document answers plainly,
   including stating that no such measurement is performed if that is the case, rather than
   leaving a reader to infer one from the presence of splitting.
2. **Given** a request the provider rejects as too large, **When** a reader looks up the
   outcome, **Then** the document states what the run does next, what happens to work
   already completed in the same run, what appears on the pull request, and the exit code.
3. **Given** an answer from the model that is cut off before it is complete, **When** a
   reader looks up the outcome, **Then** the document states the recovery attempt made, how
   many times, and what happens when it does not succeed.
4. **Given** a limit on the length of the model's *answer*, **When** a reader looks for it,
   **Then** the document distinguishes it from limits on the *request*, since confusing the
   two leads a reader to the wrong setting.
5. **Given** the document, **When** a reader asks what they can change today to avoid the
   problem, **Then** it names the settings that actually reduce request size, and does not
   imply a capability the tool does not have.

---

### Edge Cases

- **A reader has no PlantUML renderer.** The diagram source must still be readable as text,
  and the companion document must carry the same flow in a form that does not require
  rendering.
- **A stage is skipped entirely on a given run** — no linked story, no checklist, nothing
  reviewable left. The diagram must show these as labelled outcomes, not as gaps.
- **The reader is looking at the other entry point**, not the local one. The document must
  say what differs so a reader does not follow the wrong path and conclude the document is
  wrong.
- **A reader asks about a behaviour the tool does not have** — a run report on disk, a
  severity threshold, a token budget, project-wide code knowledge. The document must say
  plainly that it does not exist, rather than omitting it and leaving the reader to search
  the code for it.
- **A finding refers to code the reviewer was never shown.** The document must explain how
  this becomes possible and what the tool does about a claim it cannot anchor, so a reader
  meeting one knows whether it is a defect or expected.
- **A reader wants project-wide review and concludes the tool is broken because it does not
  do it.** The document must state that reviewing against the change rather than the whole
  project is a deliberate choice, and give the reasons, so the limit reads as a boundary
  rather than a bug.
- **The code changes after this document is written.** The document must make each claim
  traceable to the place that proves it, so a later reader can check rather than trust.
- **An existing project document already answers part of a question.** The document must
  point to it rather than restate it, and must not disagree with it.

## Requirements *(mandatory)*

### Functional Requirements

**The diagram**

- **FR-001**: The feature MUST deliver an activity diagram as a PlantUML source file located
  in the repository's `docs/` directory.
- **FR-002**: The diagram MUST render without error using a standard PlantUML renderer, with
  no manual edit required first.
- **FR-003**: The diagram MUST show every stage of a review, in execution order, for a run
  started locally against a pull request.
- **FR-004**: Every stage in the diagram MUST identify the file that owns it.
- **FR-005**: The diagram MUST show each point where the run can take a different path, with
  every branch labelled and every branch reaching an explicit end — no unterminated path.
- **FR-006**: The diagram MUST show the difference between the local entry point and the
  default entry point, and the point at which the two become the same path.
- **FR-007**: The diagram MUST show where a large change is reduced and where the review
  work is split into more than one provider pass.
- **FR-008**: The diagram MUST remain legible at a size a developer can read on one screen;
  where detail would overwhelm it, that detail belongs in the companion document, which the
  diagram MUST reference.

**The companion document**

- **FR-009**: The feature MUST deliver one companion document, written for a developer who
  has never seen this project, in plain language with no assumed familiarity with its
  history.
- **FR-010**: The document MUST walk the call flow stage by stage, and for each stage name
  the methods performed, the file each lives in, and each method's role in one line.
- **FR-011**: The document MUST state, for each stage, what it receives from the previous
  stage and what it hands to the next.
- **FR-012**: The document MUST show the output a run prints for each stage, so a reader can
  match a live run against the walkthrough.
- **FR-013**: The document MUST explain every decision point the diagram shows: what selects
  each branch, how an operator can tell which was taken, and where the run ends up.
- **FR-014**: The document MUST list every file and directory that ships in the project with
  a one-line statement of its purpose, tying each participating file to the stage it serves
  and marking those that take no part in a review.
- **FR-015**: The document MUST state, for each file that carries an architectural rule, what
  that rule is and that a test enforces it.
- **FR-016**: The document MUST answer how a large change request is handled: every limit
  that reduces it, in application order, with what each bounds, its default, the setting that
  changes it, the basis on which kept parts are chosen, and what becomes of the parts left
  out.
- **FR-017**: The document MUST answer what happens when the request is split, including what
  the split respects, what each part is told about the others, and what happens to a single
  item larger than the split size.
- **FR-018**: The document MUST answer what happens when a model limit is exceeded — both a
  request that is too large and an answer that is cut off — stating the recovery attempted,
  what is lost, what appears on the pull request, and the exit code.
- **FR-019**: The document MUST distinguish limits on the request from limits on the model's
  answer.
- **FR-020**: The document MUST state plainly where a safeguard a reader would expect does
  not exist, rather than omitting it.

**What the review can see**

- **FR-021**: The document MUST state whether a review judges a pull request from the change
  alone or from the surrounding project, and MUST answer it in one unambiguous sentence
  before elaborating.
- **FR-022**: The document MUST state exactly what is presented for each changed file — the
  changed lines, the changed lines plus surrounding material, or the whole file — including
  how much surrounding material accompanies a change, and MUST state how a newly added file
  differs from a modification to an existing one.
- **FR-023**: The document MUST state whether files untouched by the pull request are
  retrieved, and whether they are presented to the reviewer.
- **FR-024**: The document MUST list every source of context presented alongside the change,
  and what each contributes to a judgement.
- **FR-025**: The document MUST distinguish material the tool retrieves from material it
  presents to the reviewer, wherever the two differ.
- **FR-026**: The document MUST state what a single pass of a split review can see of the
  other parts of the same change.
- **FR-027**: The document MUST name concrete kinds of judgement the tool structurally cannot
  make given what it is shown, and MUST state what the tool does with a finding it cannot
  anchor to the material it was given.
- **FR-028**: The document MUST state that reviewing against the change rather than the whole
  project is a deliberate choice, and give the reasons, so the limit is legible as a boundary
  rather than a defect.
- **FR-029**: The diagram MUST show what is assembled into the material the reviewer receives,
  distinguishing it from what the run retrieved but did not send.

**Trustworthiness and boundaries**

- **FR-030**: Every factual claim about the tool's behaviour MUST be traceable to the place in
  the project that proves it, so a later reader can verify rather than trust.
- **FR-031**: The document MUST distinguish a claim verified by running the tool from one
  established by reading the code, and MUST mark any claim that is neither.
- **FR-032**: Where an existing project document already answers a question correctly, this
  feature MUST point at it rather than restate it, and MUST NOT contradict it.
- **FR-033**: Where this feature finds that an existing project document disagrees with the
  code, it MUST record the disagreement rather than silently pick a side.
- **FR-034**: This feature MUST NOT change the agent's behaviour: no file under the agent
  package or the test suite is modified.
- **FR-035**: The deliverables MUST contain no credential, token, or environment value, in
  keeping with the project's rule that no secret reaches any output.

### Key Entities

- **Activity diagram**: The visual flow. Composed of stages, decisions, branches and end
  points; each stage names an owning file.
- **Stage**: One step of a review, with a name a reader would search for, an owning file, an
  ordered set of methods, an input, an output, and a visible output line.
- **Decision point**: A place the run can diverge; carries what selects each branch, the
  observable signal of which was taken, and each branch's destination.
- **File entry**: One file or directory that ships in the project, with its purpose, the
  stage it serves (or the fact that it serves none), and any architectural rule that
  constrains it.
- **Context source**: One thing placed in front of the reviewer alongside the change, with
  what it contributes, whether it is always present, and whether it is retrieved but withheld.
- **Review blind spot**: One kind of judgement the tool cannot make given what it is shown,
  with why, and what a reader should do instead.
- **Size limit**: One bound that reduces a change before or during review, with what it
  bounds, its default, the setting that changes it, its position in the order, and how a
  reader can tell it was reached.
- **Failure mode**: One way a run departs from the straight-through path, with its trigger,
  what is lost, what the reader sees, and the exit code.
- **Claim anchor**: The pointer that makes a statement checkable, plus whether it was
  verified by running the tool or by reading the code.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer who has never seen this project can, using only these two
  deliverables and within 30 minutes, correctly describe the review flow end to end and name
  the file that owns each stage.
- **SC-002**: Given five plain-language behaviours of the agent, a reader using only these
  deliverables names the correct owning file and method for all five, and every method named
  is confirmed to exist where the document says it does.
- **SC-003**: The diagram source renders on first attempt with a standard PlantUML renderer,
  with no edit.
- **SC-004**: 100% of the files and directories that ship in the project appear in the
  structure section with a stated purpose.
- **SC-005**: Given a described pull request of a stated large size, a reader using only
  these deliverables correctly states how much of it is reviewed, what happens to the rest,
  and how many provider passes it takes.
- **SC-006**: Asked what happens when a model limit is exceeded, a reader using only these
  deliverables correctly states the outcome, what is lost, and the exit code.
- **SC-007**: Every behavioural claim in the deliverables carries an anchor that a reviewer
  can follow to the place that proves it, and every anchor checked resolves.
- **SC-008**: A reviewer comparing these deliverables against the project's existing
  documents finds no contradiction between them that is not recorded as a known
  disagreement.
- **SC-009**: No agent source file or test is modified by this feature.
- **SC-010**: Asked whether the review judges a pull request from the change alone or from
  the whole project, a reader using only these deliverables gives the correct answer, and
  correctly states what accompanies the change.
- **SC-011**: Given four proposed checklist rules, some answerable from a changed region
  alone and some requiring knowledge of unchanged code elsewhere, a reader using only these
  deliverables sorts all four correctly into judgeable and not judgeable.

## Assumptions

- **"Local mode" means running the review from the working copy on a developer's own
  machine** — the path that skips fetching the review logic — as opposed to the default path
  that fetches a committed copy first. Both are covered; the local one is the spine, because
  it is the path a developer starting work will use. The difference between them is one
  stage, and the document states it.
- **"When a PR request is sent" means pointing the tool at an existing pull request
  identifier** and running a review against it. The tool is invoked by a person or a
  pipeline; it does not listen for pull request events.
- **Both deliverables go in `docs/`**, which the request names for the diagram. The companion
  document sits beside it as an ongoing developer reference rather than inside the feature
  folder, and the feature folder points at both. The existing `docs/` directory is empty, so
  nothing is displaced.
- **PlantUML is the diagram format**, as named in the request. No rendered image is
  committed; the source file is the deliverable, since an image goes stale invisibly.
- **One activity diagram is the deliverable.** If a single diagram cannot stay legible while
  meeting FR-003 through FR-007 and FR-029, the excess detail moves to the companion document rather
  than to a second diagram.
- **The audience is a developer, not an operator.** How to configure and run the tool is
  already documented; this feature assumes the reader can run it, and concerns itself with
  what happens inside.
- **The question "changes only or full project context" is answered by describing what the
  tool does today, not by proposing a change to it.** This feature documents the existing
  behaviour and the reasoning behind it. If a reader concludes that broader context is
  wanted, that is a separate feature; this one makes the current boundary visible so that
  conclusion can be reached deliberately rather than by surprise.
- **The existing project documents remain in force.** This feature adds a developer-facing
  view; it does not supersede the operator runbook, the structure map, or the walkthroughs,
  and where they are already correct it points at them.
- **Claims are established by reading the code and by running the self-contained path that
  needs no server.** Claims that would require a live server or a live provider call to
  confirm are marked as unverified rather than asserted.
