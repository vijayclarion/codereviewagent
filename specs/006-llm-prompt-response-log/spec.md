# Feature Specification: LLM Prompt and Response Log

**Feature Branch**: `006-llm-prompt-response-log`
**Created**: 2026-09-17
**Status**: Draft
**Input**: User description: "Configurable to log prompt sent in the execution to LLM and response in log file in text format. Keep the file simple and easy to understand."

## Overview

Today a run tells you *what the agent concluded* and nothing about *what it asked*. The
phase log prints one line per stage; the review prints findings. The exact text sent to
the provider — story, scope, checklist corpus and diff, assembled per chunk — and the
exact text that came back exist only in memory and are gone when the process exits.

This feature gives an operator an opt-in setting that writes both to a plain text file,
so that a puzzling review can be explained after the fact instead of reproduced.

**This is not the run report of feature 001's gap G2.** G2 asks for a structured record of
a review's *outcome* in `.review-reports/`. This writes the *provider conversation*, is off
by default, and leaves G2 open.

## Clarifications

### Session 2026-09-17

- Q: Two runs against the same pull request iteration — what happens to the first log? → A: Name includes a timestamp, so every run writes a new file and nothing is ever overwritten
- Q: Where does the file land when the review re-executes itself from fetched agent source? → A: The parent resolves the destination to an absolute path before re-executing; the file always lands relative to where the operator launched the agent
- Q: Is each exchange written as it happens, or is the file assembled and written once at the end? → A: Each exchange is written and flushed as soon as that call completes; a killed run still leaves every exchange that finished
- Q: The checklist corpus repeats in every chunk prompt — does the log repeat it too? → A: Record every prompt in full, repetition included; the file is a faithful transcript
- Q: Do old log files ever get cleaned up? → A: Keep the most recent N logs in the destination and delete older ones at the start of each run

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read exactly what the agent asked and what it was told (Priority: P1)

A developer gets a review that flags something surprising — a checklist criterion marked
`not_addressed` for a file that plainly addresses it. They turn on the log setting, re-run
in preview mode, and open the resulting file. They read the prompt top to bottom and find
that the diff chunk in question never reached the provider, because the file was excluded.
No guessing, no instrumentation, no reading the agent's source.

**Why this priority**: This is the whole feature. Every other story is a guard rail around
it. Delivered alone it already turns "the agent is behaving strangely" from a code-reading
exercise into a file-reading one.

**Independent Test**: Enable the setting, run a review in preview mode against a pull
request, and confirm the file contains the full prompt text and the full response text for
every provider call the run made, in the order they were made.

**Acceptance Scenarios**:

1. **Given** logging is enabled and a pull request with changes that fit one chunk,
   **When** a review runs, **Then** the file contains one entry holding the complete
   prompt as sent and the complete response as received.
2. **Given** a pull request large enough to be split into three chunks, **When** a review
   runs, **Then** the file contains three entries, each stating which chunk it is and how
   many there are in total, in the order sent.
3. **Given** a completed run, **When** a reader opens the file in any text editor,
   **Then** each entry's header states the run identifier, the pull request, the provider
   and model, the chunk position, the attempt, the timestamp, the elapsed time and the
   outcome — without the reader needing a tool to decode it.
4. **Given** a run in which nothing was reviewable and no provider call was made,
   **When** the file is opened, **Then** it states that the run made no provider call
   rather than being empty or absent.

---

### User Story 2 - Off by default, and never a way for a secret to escape (Priority: P2)

An operator runs the agent on a shared build agent. They have not asked for logging, and
nothing new is written anywhere. When they do switch it on for a single investigation, the
file that appears carries no credential — not the read token, not the posting token, not
the provider key — and the review it accompanies reaches exactly the same conclusion it
would have reached with logging off.

**Why this priority**: The prompt contains the source diff and the checklist corpus, and
the surrounding code has a standing rule that every byte the process writes is redacted
first. A logging feature that silently defaults to on, or that bypasses redaction, is worse
than no logging feature. This story is what makes P1 safe to ship.

**Independent Test**: Run a review with no new configuration and confirm no file is
created anywhere; then run with logging enabled and confirm no configured credential value
appears in the file, and that the findings and exit code are identical to the run with
logging off.

**Acceptance Scenarios**:

1. **Given** no logging setting is configured, **When** a review runs, **Then** no log
   file is created and no existing file is modified.
2. **Given** logging is enabled and credentials are configured, **When** a review runs,
   **Then** no credential value appears anywhere in the file.
3. **Given** the same pull request and the same provider responses, **When** one review
   runs with logging off and another with it on, **Then** both produce the same findings
   and the same exit code.
4. **Given** logging is enabled, **When** the run starts, **Then** the run states once, on
   its normal output, that logging is on and where the file is being written.
5. **Given** logging is enabled in preview mode, **When** the review runs, **Then** the log
   file is written and the pull request is still not modified in any way.

---

### User Story 3 - Explain a degraded or unparseable run (Priority: P3)

A run reports that the response did not match the required shape after a retry, and the
whole review is discarded. The operator opens the log and sees, for that chunk, the first
response and the second — the one sent with the stricter instruction appended — and can
see immediately that the model wrapped its output in prose. They also see the responses
for the chunks that *did* parse, which the run itself threw away.

**Why this priority**: It is the highest-value case, but it depends on P1 already writing
entries, and it is the rarer path. Its own value is recovering work a degraded run
destroys: a provider rejection discards the findings of chunks already parsed, and the log
is the only place those responses survive.

**Independent Test**: Force a response the parser rejects and confirm the file holds both
attempts for that chunk, each labelled, plus the stated reason the run degraded.

**Acceptance Scenarios**:

1. **Given** a response the agent cannot parse, **When** the stricter retry is sent,
   **Then** the file holds two entries for that chunk, marked as first attempt and retry,
   each with the text actually sent and actually received.
2. **Given** a provider that is unreachable, **When** the call fails after its retries,
   **Then** the entry records the prompt that was attempted and the stated failure reason
   in place of a response.
3. **Given** a run that degrades on its third chunk, **When** the file is opened,
   **Then** the responses for chunks one and two are present in full, even though the run
   reported no findings at all.

---

### Edge Cases

- **The destination cannot be written** (missing directory, read-only path, permission
  denied). The review continues and completes; the run states once, in its normal output,
  that logging was requested and why it could not be provided. A logging problem never
  changes a review's outcome or its exit code.
- **Two runs at once on the same build agent.** Each run writes its own file, so
  neither can corrupt or interleave with the other. Two runs of the *same* pull request,
  whether concurrent or one after the other, also get separate files. Neither run's pruning
  may delete the log the other is still writing (FR-014d).
- **The destination holds files the agent did not write.** They are never candidates for
  deletion, however old (FR-014c).
- **Pruning fails** — a file is locked, or the destination is not writable for deletion.
  The run says so, writes its own log anyway, and completes unchanged (FR-014f).
- **Retention is set to keep one log.** The current run's own log is the most recent, so it
  survives; every earlier one is removed.
- **A very large prompt.** The checklist corpus alone measures 48,485 characters of rule
  items and is repeated in every chunk's prompt, so a three-chunk review records roughly
  150 KB of near-identical text. This is accepted (FR-015a): a truncated or
  cross-referenced prompt cannot answer the question the log exists to answer. Growth is
  bounded per run, not per file.
- **The review re-executes itself from fetched agent source.** The process that actually
  calls the provider is the one that writes the log, and the setting reaches it already
  resolved (FR-003a). An operator must not get an empty directory because the work
  happened in a child process whose working directory was a fetched clone. The `--local`
  path, where no re-execution happens, must put the file in the same place.
- **A response that is empty or not valid JSON.** Recorded verbatim as received, including
  when it is what caused the run to degrade.
- **The run is killed part-way through.** The file holds every completed exchange and no
  closing summary. A reader can tell the run did not finish because the summary is missing.
- **Content the console cannot render.** The file is written in a single consistent text
  encoding and is unaffected by the console's limitations, which already force character
  substitution on the terminal path.
- **Logging enabled with `--post`.** The log is written for posting runs too, and records
  the same exchanges; it does not record the comments posted, which are not provider
  exchanges.

## Requirements *(mandatory)*

### Functional Requirements

**Configuration**

- **FR-001**: The agent MUST provide a single operator-facing setting that turns
  prompt-and-response logging on, and a setting for where the file is written.
- **FR-002**: Logging MUST be off unless explicitly turned on. A run with no new
  configuration MUST write no file.
- **FR-003**: The logging settings MUST be read through the same configuration path as
  every other setting, so that no other part of the agent reads them from the environment.
- **FR-003a**: A destination given as a relative path MUST be resolved against the
  directory the operator launched the agent from, and MUST resolve to that same place even
  though the process that performs the review and writes the log is a child re-executed
  from fetched agent source in a different working directory. The resolution MUST happen
  once, in the launching process, and be carried to the child.
- **FR-004**: When logging is on, the run MUST state once, on its normal output, that it is
  on and the path of the file being written.

**What is recorded**

- **FR-005**: Every provider exchange the run performs MUST produce one entry, in the order
  the exchanges occurred.
- **FR-006**: An entry MUST record the prompt exactly as sent — after chunking, and
  including the stricter instruction when the exchange is a retry.
- **FR-007**: An entry MUST record the response exactly as received, including a response
  that could not be parsed.
- **FR-008**: When an exchange fails without a usable response, the entry MUST record the
  stated failure reason in place of the response.
- **FR-009**: An entry MUST identify itself with: the run identifier, the pull request, the
  provider and model, the chunk position and total, whether it is the first attempt or the
  retry, the time it was sent, the elapsed time, and the outcome.
- **FR-010**: The file MUST state, at its head, the run identity it belongs to, and at its
  foot, how many exchanges it recorded and how the run ended.
- **FR-010a**: Each entry MUST be written and flushed to disk as soon as its exchange
  completes, before the next exchange begins. A run that is killed, times out, or dies on
  an unhandled failure MUST leave on disk every entry whose exchange had finished.
- **FR-010b**: Because the closing summary of FR-010 cannot be written by a run that is
  killed, a file that ends without one MUST still be readable and complete up to its last
  entry; the absence of the summary is itself the signal that the run did not finish.
- **FR-011**: A run that makes no provider call MUST still produce a file that says so.

**Form**

- **FR-012**: The file MUST be plain readable text. The prompt and response bodies MUST
  appear as they are, not encoded, escaped, or wrapped in a structured data format.
- **FR-013**: Entries MUST be separated by an obvious delimiter, so a reader can tell where
  one prompt ends and the next begins without counting characters.
- **FR-014**: Each run MUST write its own file, named so that it can be traced to the pull
  request and run that produced it, and made distinct by the time the run started.
- **FR-014a**: A run MUST NOT overwrite, truncate, or append to the log of any previous
  run, including a previous review of the same pull request at the same iteration. The
  identifier the agent carries today (`pull request . iteration`) repeats across re-runs,
  so it is not sufficient on its own to keep two files apart.
- **FR-014b**: At the start of a run, the agent MUST retain only the most recent logs in
  the destination and delete the rest. How many are retained MUST be operator-configurable,
  with a default that keeps enough runs to compare an investigation's attempts.
- **FR-014c**: Pruning MUST only ever delete files the agent itself wrote as logs,
  identified by the naming it controls. Any other file in the destination MUST be left
  untouched, whatever its age — the destination is a path the operator chose and may hold
  their own files.
- **FR-014d**: Pruning MUST NOT delete a log that another run is currently writing.
- **FR-014e**: The run MUST state which logs it deleted, or that it deleted none. A
  deletion the operator cannot see is indistinguishable from a file that was never written.
- **FR-014f**: A failure to prune MUST NOT fail, degrade, or alter the review, and MUST NOT
  prevent the current run's log from being written. The run states the reason and continues.
- **FR-015**: The prompt and response MUST be recorded in full, without truncation or
  summarisation.
- **FR-015a**: Text that repeats between prompts — the story, the declared scope and the
  checklist corpus appear in every chunk's prompt — MUST be repeated in every entry rather
  than recorded once and referenced. An entry MUST be copyable out of the file as a
  complete prompt, with nothing to reassemble.
- **FR-015b**: An entry's header MUST state the size of the prompt it carries, so a reader
  knows how far the body runs before reading into it.

**Safety**

- **FR-016**: Every byte written to the file MUST pass through the same redaction that
  guards the agent's console output, so that no registered credential can reach the file.
- **FR-017**: Enabling logging MUST NOT change what is sent to the provider, what findings
  are produced, what is posted, or what exit code is returned.
- **FR-018**: A failure to create or write the file MUST NOT fail, degrade, or alter the
  review; the run MUST continue and MUST state the reason it could not log.
- **FR-019**: The log MUST be written in preview mode as well as posting mode, and writing
  it MUST NOT count as a write to the pull request.
- **FR-020**: The default destination MUST be excluded from version control, so that a
  developer investigating a review cannot accidentally commit a pull request's source diff.

### Key Entities

- **Exchange Record**: One request to the provider and its outcome. Carries the identity
  (run, pull request, provider, model, chunk position, attempt), the timing, the prompt
  text as sent, and either the response text as received or the stated reason there is
  none.
- **Run Log**: The file for one run. A head that names the run, the Exchange Records in
  the order they happened, and a foot that states the count and how the run ended.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a completed review, 100% of the provider exchanges it performed appear in
  the file, each with its prompt and its response in full.
- **SC-002**: No configured credential value appears anywhere in the file, for every
  credential the agent accepts.
- **SC-003**: A run with no logging configuration creates zero files.
- **SC-004**: The same pull request and the same provider responses produce identical
  findings and an identical exit code whether logging is on or off.
- **SC-005**: A developer who did not write the agent can point to the exact text of any
  one provider call of a past run, using only the file and a text editor, without
  re-running the review.
- **SC-005a**: The log appears in the same location whether the run bootstrapped from
  fetched agent source or ran with the local working copy.
- **SC-006**: A run whose log destination cannot be written completes with the same exit
  code it would have returned with logging off, and states the reason once.
- **SC-007**: When a run degrades after some chunks parsed, the responses for those chunks
  are recoverable from the file, though the run itself reported none.
- **SC-007a**: A run terminated part-way through — killed, timed out, or failed
  unexpectedly — leaves a readable file holding every exchange that had completed.
- **SC-008**: After any number of runs with logging on, the destination holds no more than
  the configured number of the agent's log files.
- **SC-009**: A file in the destination that the agent did not write is still present after
  any number of runs.
- **SC-010**: The existing test suite continues to pass in full, with the feature's own
  coverage added to it.

## Assumptions

Defaults chosen where the description did not specify. Each is a decision, not a guess left
open — a later `/speckit.clarify` can overturn any of them.

- **Off by default.** The prompt carries the pull request's source diff and the full
  checklist corpus. An opt-in setting is the standard treatment for verbose diagnostic
  output that contains sensitive material.
- **One file per run**, rather than one file appended across runs. Two reasons: a build
  agent can review two pull requests at once, and interleaved multi-kilobyte prompts from
  two runs would be unreadable; and "simple and easy to understand" is best served by a
  file whose entire contents belong to a single review. Re-running the same pull request
  is the normal shape of an investigation, so no run may ever clobber an earlier one
  (FR-014a) — the operator's comparison between the two is the point.
- **Default destination is a directory dedicated to these logs**, distinct from the
  `.review-reports/` path that feature 001's gap G2 reserves for the unwritten run report.
  This feature does not close G2.
- **The prompt is recorded after chunking**, because that is what is actually sent. A
  reader who wants the unsplit assembly can read the chunks in order. Fidelity is preferred
  over brevity throughout: an entry that can be copied out and replayed verbatim against
  the provider is worth more than a shorter file.
- **Network-level retries inside a single call are not separate entries.** The same prompt
  re-sent after a timeout is one exchange; the stricter parse retry, which sends different
  text, is a separate entry.
- **The log records provider exchanges only** — not TFS requests, not posted comments, not
  checklist fetches. Those have their own stated behaviour and are outside this feature.
- **Retention is by count, not by age or size**, and is bounded so that a build agent left
  with logging switched on does not accumulate files without limit. The default retention
  keeps the ten most recent runs — enough to compare the attempts of a single investigation
  — and is configurable. Deletion is confined to the agent's own log files (FR-014c): the
  feature is a diagnostic aid, and a diagnostic aid that removes an operator's unrelated
  files is a defect, not a convenience.
- **Preview mode's read-only guarantee is about the pull request**, not the local file
  system. The existing guarantee asserts that no non-GET call reaches the server; writing a
  local file does not violate it.

## Out of Scope

- The structured run report of gap G2 (`.review-reports/`).
- Logging TFS REST traffic, checklist document reads, or posted comment bodies.
- Any change to what the prompt contains, how it is chunked, or how the response is parsed.
- Sending logs anywhere off the machine, or any log aggregation format.
