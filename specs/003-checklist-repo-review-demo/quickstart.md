# Implementer Quickstart

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

How to execute this plan. Not the operator's document — that is `demo.md`, which this
feature delivers.

---

## Read first, in this order

1. [plan.md](./plan.md) — the **Survey Findings** table is the spine
2. [research.md](./research.md) — R2, R4 and R7 decide most of the code
3. [data-model.md](./data-model.md) — seven of nine entities already exist
4. `contracts/` — four contracts, each with clauses a test can assert

Then, before writing anything: read `review_agent/checklist_docs.py`,
`review_agent/source_fetch.py`, and `review_agent/models.py:256-353`. **All three are
complete, tested, and connected to nothing.** Most of what a task in this feature asks for
already exists; the work is wiring, not building. The single most expensive mistake
available here is writing a second `.xlsx` reader.

## The gate: the suite must pass before and after

```bash
python -m pytest tests -q          # 401 passing, no live network
```

Run it before your first edit. If it is not green on arrival, stop and find out why — the
number is the one thing this feature cannot move backwards.

## The hard orderings

Three, all discovered in the survey rather than assumed.

**1. `.env` blocks every live run.** `config.py:359-361` requires `LLM_PROVIDER` and
`LLM_MODEL`; gap G5 says `.env` has a model identifier that does not exist. This feature
does not touch `.env` — it is a human-applied prerequisite, as it was in 001 and 002. The
self-contained work does not need it, so start there.

**2. The identifier change (R4) must land before the identity change (R7).** Finding
identity keys on the rule identifier. Keying on an identifier that still contains a row
number means the suppression tests pass and the behaviour is still wrong the first time
someone edits a spreadsheet.

**3. The live run comes last, and it is gated.** Before attempting it, confirm: `.env`
corrected, `TFS_API_VERSION=5.0`, `TFS_PAT` carries **Work Items (read)**, and either this
branch's code is pushed to the agent repository **or** the run uses `--local`
(research R10 — the default entry point re-fetches and re-executes the committed logic, so
without one of those two the live run reviews with code that does not contain this
feature).

## Where things go

```text
review_agent/
├── checklist.py         # gains the document-corpus path; keeps the markdown path
├── checklist_docs.py    # identifier derivation only (R4) — no other change
├── source_fetch.py      # optional ref; the only module that may invoke git
├── selection.py         # gains select_rules() — relevance ranking for rules
├── parser.py            # citation resolution; identity keys
├── output_layer.py      # four identity call sites; the inventory block
├── models.py            # ChecklistSource, RunInventory, 4 fields on CombinedChecklist
├── errors.py            # WorkItemAccessDenied
├── tfs_client.py        # raises it for work-item endpoints
├── config.py            # setting resolution order; pattern default
└── main.py              # orchestration; the story-degradation path

tests/demo/              # NEW — the self-contained harness (not collected: no test_*.py)
tests/integration/test_us3_demo.py   # runs the harness twice, compares findings (SC-006)

specs/003-checklist-repo-review-demo/
├── demo.md              # THE DELIVERABLE
├── demo-files/          # deliberately faulty sample code + the document generator
└── contracts/
```

`demo-files/` is never imported and never collected — `pytest.ini` sets `testpaths = tests`
and `test_import_boundaries.py:13` scans only `review_agent/`. Do not "fix" the faults in
it, for the same reason 002's `example-files/` carries the same warning.

## Working rhythm

Each change follows the same shape, because the contract tests will tell you immediately
if you have drifted:

1. Write the test that fails for the right reason.
2. Make it pass without touching a module that does not own the responsibility.
3. Run the full suite, not just your file. The import-boundary tests are cheap and they
   are the ones that catch an accidental `subprocess` import or a stray `openpyxl`.

Two boundary traps worth naming, because both are easy to hit and neither fails obviously:

- `test_git_is_invoked_from_one_module_only` greps for the **literal string** `git` and for
  `subprocess.` in every module except `source_fetch.py` and `bootstrap.py`. A comment
  mentioning git in `checklist.py` fails it.
- `test_no_hard_coded_collection_urls_or_models` greps for model identifiers and collection
  URLs in non-comment lines. The demonstration's sample content belongs under `specs/`, not
  in a docstring.

## Definition of done

- 401 tests still pass, plus the new ones.
- The five checkpoint questions of `contracts/demonstration.md` §3 are answerable from a
  preview's own output.
- The self-contained demonstration runs twice from a clean checkout and produces identical
  finding sets.
- The live run has posted, and **a second live posting run added no comment** — observed,
  not reasoned about. This is the row that closes the defect 001 recorded as "no gap".
- Every observed result in `demo.md` says which run produced it.
- The redaction scan has been run against `demo.md`.
