---

description: "Task list for 006-llm-prompt-response-log"
---

# Tasks: LLM Prompt and Response Log

**Input**: Design documents from `/specs/006-llm-prompt-response-log/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: **REQUIRED, not optional.** SC-010 requires the suite to grow with the feature,
research D12 specifies the eight test files, and two of them are gates
(`plan.md` → Safety Register). A repository with 532 contract-enforced tests does not take
code without them.

**Organization**: grouped by user story. Two deviations from the default mapping are marked
where they occur and justified — honesty about them is worth more than a tidy table.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable — different file, no dependency on an incomplete task
- **[Story]**: US1 / US2 / US3 from spec.md

## Path Conventions

Single flat package at the repository root: `review_agent/`, `tests/{contract,unit,integration}/`.
No sub-packages — see `plan.md` → Structure Decision.

---

## Phase 1: Setup

**Purpose**: establish the baseline and the empty surfaces.

- [X] T001 Run `python -m pytest tests` and confirm **532 passed**. Not `-q` — `pytest.ini` already sets it and `-qq` prints no summary (`004.../research.md` C2). A different number means the baseline is wrong before anything has changed
- [X] T002 Create `review_agent/llm_log.py` with a module docstring stating its single responsibility and its boundary. **The docstring must not contain the quoted word `"git"` or the text `subprocess.`** — `test_git_is_invoked_from_one_module_only` greps source text, not imports, and would fail the suite with a message about git (research E14)
- [X] T003 [P] Add `.llm-logs/` to `.gitignore` under a comment naming what these files contain (FR-020)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the values, the single write path, and the configuration. Every user story
needs all of it.

**⚠️ CRITICAL**: no user story work can begin until this phase is complete.

**Note on redaction**: `_write` with `redact()` inside it lands here, in Foundational, not in
US2 where the safety story lives. It cannot be deferred — the first byte US1 writes must
already be redacted. US2 owns the *proof* (T023), not the mechanism.

- [X] T004 [P] Implement the `LogDestination` frozen dataclass in `review_agent/llm_log.py` with `__post_init__` invariants: `directory` absolute, `keep >= 1` (`data-model.md` §1)
- [X] T005 [P] Implement the `ExchangeRecord` frozen dataclass in `review_agent/llm_log.py` with `__post_init__` invariants: `outcome` in `(ok, failed)`, `failed` ⇒ non-empty `failure`, `attempt` in `(1, 2)`, `chunk <= chunk_total` (`data-model.md` §2)
- [X] T006 Implement the single `_write(path, text)` helper in `review_agent/llm_log.py`, calling `config.redact(text)` inside it. **There must be no second way to write to the file** — head, entries, foot, bodies and failure reasons all route through this one function (FR-016, `contracts/module-boundary.md`)
- [X] T007 Implement the `LogSession` skeleton in `review_agent/llm_log.py`: `open` / `record` / `close`, the `enabled` flag, and the no-op session returned when logging is off. **Every method is total — nothing in this module ever raises into the review** (FR-018, research D9, `data-model.md` §3)
- [X] T008 Add `llm_log`, `llm_log_dir` and `llm_log_keep` to `Config` and `load_config` in `review_agent/config.py`, using the existing `_parse_bool` / `_parse_int` / `_Problems`. Store `llm_log_dir` **absolute** via `os.path.abspath`. None is a secret; none joins `SECRET_FIELDS` (FR-001, FR-003, FR-003a, `contracts/configuration.md`)
- [X] T009 Add `--log-llm` to `build_parser` in `review_agent/main.py` and thread it into `load_config` as an override, following the `--local` pattern. On only; there is no `--no-log-llm` (FR-001)

**Checkpoint**: `python -m pytest tests` → still 532. Nothing is wired yet; the module exists, the settings parse, the flag is accepted.

---

## Phase 3: User Story 1 — Read exactly what the agent asked and what it was told (Priority: P1) 🎯 MVP

**Goal**: with the setting on, a run leaves a file holding the complete prompt and complete
response for every provider call it made, in order, readable in any text editor.

**Independent Test**: enable the setting, run a review in preview mode against a pull
request, open the file — every exchange is there, in full, in the order sent.

### Tests for User Story 1

- [X] T010 [P] [US1] Unit tests for the head, entry and foot shapes in `tests/unit/test_llm_log.py`, asserting against `contracts/log-format.md` — the anchored rules, the aligned `key : value` lines, the character counts, and bodies written verbatim with no escaping
- [X] T011 [P] [US1] Unit tests for naming in `tests/unit/test_llm_log.py`: `llm-pr<id>-<YYYYmmdd>-<HHMMSS>.log`, and the `-2` / `-3` collision suffix when the name is taken. All against `tmp_path`, never beside the suite (`contracts/module-boundary.md` trap 4)
- [X] T012 [P] [US1] Integration test in `tests/integration/test_llm_log_run.py`: a three-chunk review produces three entries, each carrying its chunk position, in the order sent (US1 AS2)
- [X] T013 [P] [US1] Integration test in `tests/integration/test_llm_log_run.py`: a run where nothing is reviewable still produces a file that says no provider call was made (US1 AS4, FR-011)

### Implementation for User Story 1

- [X] T014 [US1] Implement `LogDestination.path_for(pr_id, started)` in `review_agent/llm_log.py` — naming plus the collision suffix. The name is from `config.tfs_pr_id` and the start time, **not** from `run_id`, which repeats across re-runs and is not known this early (research D5, E9, E10)
- [X] T015 [US1] Implement the head block writer in `review_agent/llm_log.py`, including `run : pending` at open and its completion once the PR context arrives (`contracts/log-format.md`)
- [X] T016 [US1] Implement the entry writer in `review_agent/llm_log.py` — open, append, close per entry, so an entry is durable before the next call begins (FR-010a, research D6)
- [X] T017 [US1] Implement the foot writer in `review_agent/llm_log.py` with outcomes `complete` / `degraded` / `no exchange` (FR-010)
- [X] T018 [US1] Open the session at L4 in `run_review` (`review_agent/main.py`) and close it at L8 (normal completion) and L7 (nothing reviewable). **Do not close it on an unhandled failure** — the missing foot is the documented signal (FR-010b, L9, research D11)
- [X] T019 [US1] **The feature.** Wrap the `lambda text: call_llm(text, config)` at `review_agent/main.py:296` so each send records an `ExchangeRecord`. Count the attempt in the per-chunk closure: `parse_with_retry` calls the wrapper once, or twice when the first response will not parse (`parser.py:550-569`). **Resolve `call_llm` at call time, never capture it by value** — seven tests monkeypatch `main_module.call_llm` and a captured reference silently ignores every fake (research D1, E17)
- [X] T020 [US1] Emit the announcement line naming the file, through `config.emit`, once at session open in `review_agent/main.py` (FR-004; also satisfies US2 AS4)
- [X] T021 [US1] Add `LLM_LOG_DIR` (already absolute) and `LLM_LOG` to the overrides dictionary in `bootstrap._child_env` (`review_agent/bootstrap.py`). Without this the operator gets no file and no error, because the child writes into a temp clone that is deleted moments later (FR-003a, research D4, E11)
- [X] T022 [US1] Unit test in `tests/unit/test_bootstrap.py`: the child's environment carries an **absolute** `LLM_LOG_DIR` (SC-005a)

**Checkpoint**: US1 is fully functional. A real run with `--local --pr <id> --log-llm` writes a readable file. `python -m pytest tests` → 532 + new, all passing.

---

## Phase 4: User Story 2 — Off by default, and never a way for a secret to escape (Priority: P2)

**Goal**: nothing is written unless asked for; nothing written carries a credential; the
review reaches an identical conclusion either way; and the agent never damages a file it
did not create.

**Independent Test**: run with no new configuration and confirm zero files; run with logging
on and confirm no credential value appears and that findings and exit code match a
logging-off run of the same fixture.

**Note on retention**: FR-014b–f arrived from clarification Q5 and map to no user story
directly. They live here because US2 is the operator-safety story — "the agent does not
damage your machine" belongs beside "the agent does not leak your token". SC-008 and SC-009
are their acceptance.

### Tests for User Story 2

- [X] T023 [P] [US2] **GATE.** Contract test in `tests/contract/test_llm_log_is_redacted.py`: register all three credential values (`tfs_token`, `llm_api_key`, `post_token`), drive a run through the **real** write path, assert none appears in the file. Asserts on the values, through the real path — the shape of `test_no_secrets_leak.py`, for the same reason
- [X] T024 [P] [US2] **GATE.** Contract test in `tests/contract/test_llm_log_prunes_only_its_own.py`: a foreign file in the destination survives any number of runs (SC-009); a log whose embedded timestamp is newer than the running process is never deleted (FR-014d); a nested directory is untouched
- [X] T025 [P] [US2] Unit test in `tests/unit/test_llm_log.py`: with no `LLM_LOG` and no `--log-llm`, no directory is created, no file is written, nothing is emitted (FR-002, SC-003)
- [X] T026 [P] [US2] Integration test in `tests/integration/test_llm_log_run.py`: the same fixture and the same provider responses produce identical findings and an identical exit code with logging on and off (FR-017, SC-004)
- [X] T027 [P] [US2] Unit tests in `tests/unit/test_config.py` for the three settings: defaults, a bad integer reported alongside every other configuration problem, and a relative path arriving absolute

### Implementation for User Story 2

- [X] T028 [US2] Implement candidate selection for pruning in `review_agent/llm_log.py`: non-recursive listing, filtered by the exact pattern `^llm-pr\d+-\d{8}-\d{6}(-\d+)?\.log$`. **The pattern is the proof of authorship — nothing outside it is ever a deletion candidate** (FR-014c, `contracts/retention.md` steps 1–2)
- [X] T029 [US2] Implement the timestamp guard and the sweep in `review_agent/llm_log.py`: discard candidates whose embedded timestamp is ≥ this run's start, sort oldest first, delete until at most `keep - 1` remain, **before** the run's own file is written (FR-014b, FR-014d, SC-008, `contracts/retention.md` steps 3–5)
- [X] T030 [US2] Implement the pruning report line in `review_agent/llm_log.py` — what was removed, or that nothing was. Silence about a deletion is indistinguishable from a file that was never written (FR-014e)
- [X] T031 [US2] Implement pruning failure isolation in `review_agent/llm_log.py`: a file that cannot be deleted is skipped, a directory that cannot be listed skips pruning entirely, and the run's own log is still written. One stated line, then done (FR-014f, `contracts/retention.md`)
- [X] T032 [US2] Extend `tests/contract/test_import_boundaries.py` with the new invariant: no module other than `source_fetch.py` and `llm_log.py` may contain `os.remove`, `os.unlink`, `os.rmdir`, `shutil.rmtree` or `Path.unlink` (`contracts/module-boundary.md`)
- [X] T033 [US2] **Verify both gates actually gate.** Temporarily remove `redact()` from `_write` and confirm T023 fails; temporarily loosen the name pattern to `*.log` and confirm T024 fails. Restore both. A gate test that stays green when its guard is gone is not a gate (`quickstart.md` checkpoint 2)

**Checkpoint**: US1 and US2 both hold. The feature is safe to ship.

---

## Phase 5: User Story 3 — Explain a degraded or unparseable run (Priority: P3)

**Goal**: the log explains the runs that produced no review — the stricter retry, the
unreachable provider, and the degraded run that discarded chunks it had already parsed.

**Independent Test**: force a response the parser rejects; the file holds both attempts for
that chunk, each labelled, with the text actually sent and actually received.

**Note**: most of this behaviour falls out of the T019 wrapper, which already sees both
attempts. The tasks here are the failure-recording path and the tests that prove the
behaviour — which is the point of the story, since these are the runs nobody can reproduce.

### Tests for User Story 3

- [X] T034 [P] [US3] Integration test in `tests/integration/test_llm_log_run.py`: a response the parser rejects produces two entries for that chunk, `attempt 1` and `attempt 2`, the second showing the appended stricter instruction in its body (US3 AS1)
- [X] T035 [P] [US3] Integration test in `tests/integration/test_llm_log_run.py`: a run that degrades on its third chunk still holds the full responses for chunks one and two, though the run itself reported no findings (US3 AS3, SC-007)
- [X] T036 [P] [US3] Unit test in `tests/unit/test_llm_log.py`: a failed exchange records the stated reason in place of a response, and an `ExchangeRecord` with `outcome="failed"` and an empty `failure` raises (US3 AS2, FR-008)
- [X] T037 [P] [US3] Unit test in `tests/unit/test_llm_log.py`: a session with entries written but never closed leaves a readable file with no foot (FR-010b, SC-007a)

### Implementation for User Story 3

- [X] T038 [US3] Record the failure path in the wrapper in `review_agent/main.py`: catch, build an `ExchangeRecord` with `outcome="failed"` and the stated reason, write it, then **re-raise unchanged — same type, same message**. The review must not be able to tell that logging exists (FR-008, FR-017)
- [X] T039 [US3] Write the foot with outcome `degraded` on the `DegradedReview` path at L6 in `review_agent/main.py` (FR-010)

**Checkpoint**: all three stories hold independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T040 [P] Document the three settings in the **Optional** table and `--log-llm` in the **CLI** section of `review_agent/README.md`
- [X] T041 [P] Add a line to the **Security** section of `review_agent/README.md` saying plainly that a log contains the pull request's full source diff and the full checklist corpus, and that the default destination is gitignored
- [X] T042 [P] Update the invariant row in `CLAUDE.md` to drop "**added by 006**, not yet written" once T032 exists
- [X] T043 Run the `quickstart.md` validation: `python -m review_agent --local --pr <id> --log-llm` against a real pull request. Confirm the file opens and reads top to bottom, contains no credential, and that the run reported its path and what it pruned
- [X] T044 Run `python -m pytest tests` — 532 + the feature's own, all passing, with the summary line visible

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: needs Setup. **Blocks all three stories**
- **US1 (Phase 3)**: needs Foundational. The MVP
- **US2 (Phase 4)**: needs Foundational. Its gate tests need US1's write path to exist (T023 drives a real run), so in practice it follows US1
- **US3 (Phase 5)**: needs Foundational and T019. Its behaviour rides on the US1 wrapper
- **Polish (Phase 6)**: needs the stories that are being shipped

### Story independence, honestly stated

The template's ideal is three stories that can be built in any order by three people. That
is not true here, and pretending otherwise would mislead whoever picks this up:

- **US1 is genuinely independent** and is a complete, shippable increment on its own.
- **US2 is a property of US1's implementation, not a separate feature.** Its retention half
  *is* independent; its redaction half is a gate on code US1 writes. The mechanism is
  therefore in Foundational (T006) and only the proof is in US2.
- **US3 is almost entirely tests over US1's wrapper**, plus one failure-recording path.

**Do not ship US1 without T023.** The redaction gate is what makes a file full of source
diff and provider traffic safe to exist. It is listed under US2 for story mapping; it is a
release gate for US1.

### Within each story

Tests before implementation. Values before the session. The session before the wiring. The
wiring before the wrapper.

### Parallel Opportunities

- T004 and T005 — different dataclasses, same file, coordinate or serialize
- All of T010–T013 (US1 tests) — different concerns, two files
- All of T023–T027 (US2 tests) — four different files
- All of T034–T037 (US3 tests) — two files
- T040, T041, T042 — documentation, three different edits

---

## Parallel Example: User Story 1

```bash
# The US1 tests, together:
Task: "Unit tests for head/entry/foot shapes in tests/unit/test_llm_log.py"
Task: "Unit tests for naming and the collision suffix in tests/unit/test_llm_log.py"
Task: "Integration test: three chunks produce three ordered entries in tests/integration/test_llm_log_run.py"
Task: "Integration test: nothing reviewable still produces a file in tests/integration/test_llm_log_run.py"
```

---

## Implementation Strategy

### MVP (US1 + the redaction gate)

1. Phase 1 Setup
2. Phase 2 Foundational — **blocking**
3. Phase 3 US1
4. **T023 from Phase 4.** Not optional for the MVP, whatever the story mapping says
5. Validate: a real run writes a readable, credential-free file

### Incremental delivery

1. Setup + Foundational → surfaces exist, 532 still green
2. US1 + T023 → **shippable**. The feature does what was asked
3. US2 → off-by-default proven, retention bounded, boundary enforced
4. US3 → the degraded and retry paths explained
5. Polish → documentation, real-run validation

### If time runs short

Drop **US3's tests last, not US2's**. US3 documents behaviour that already works; US2
prevents damage. Dropping T024 leaves a sweep that deletes files in a directory the operator
chose, with nothing asserting it only touches its own.

---

## Notes

- `[P]` = different file, no dependency on an incomplete task
- Run `python -m pytest tests` after each task — **never with `-q`**
- Commit after each task or logical group
- Three traps, each an afternoon: capturing `call_llm` by value (T019); a relative path
  resolved in the child (T021); `"git"` or `subprocess.` in a docstring (T002)
- Out of scope and must stay so: the run report (gap G2), token counting
  (`prompt_builder.estimated_size` is still called from nowhere), and any edit to
  `llm_adapter.py`, `prompt_builder.py` or `parser.py`
