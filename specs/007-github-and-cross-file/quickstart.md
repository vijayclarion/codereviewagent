# Implementer Quickstart: 007 GitHub Platform Support and Cross-File Review

Read [plan.md](./plan.md) first — the Call Site Ledger and the Safety Register are the spine.

## 0. Baseline

```bash
python -m pytest tests          # 597 passed at 7eddb98. Not -q (pytest.ini already sets it).
```

Re-run after **every** change. A count below 597 means an existing test broke — that is a
stop, not a fix-up: the existing suite is the contract that TFS did not change.

## 1. Order of work (each step leaves the suite green)

| Step | Story | What | Proves |
|---|---|---|---|
| 1 | — | `conftest.py` isolation; `Config` platform fields; boundary-test extensions | nothing reads a real GitHub token |
| 2 | US1 | `platform.py` + `TfsPlatform`; `main` routes through it | 597 still pass — the seam is invisible on TFS |
| 3 | US1 | `github_client.py` + `FakeGitHubClient`; GitHub pipeline tests | US1 with fakes |
| 4 | US1 | `source_fetch` GitHub clone; secrets-leak tests for the new header | checklist on GitHub |
| 5 | US2 | `stories.py`, `WorkItem.from_issue` | verdicts from an issue |
| 6 | US5 | `LlmText`, `.sends`, usage per provider; log lines; totals; guard widening | real token counts |
| 7 | US3 | token budget; `declarations.py`; `chunk_planner.py`; outline; pieces | single call by default |
| 8 | US3 | `cross_file_issues`; synthesis; summary section | ICartService acceptance test, both layouts |
| 9 | US4 | `code-review.yml`; workflow contract test | invariants |
| 10 | US6 | docs + diagram render | — |
| 11 | US7 | live: TFS dry run, GitHub dry run, sample repo, demo PR, two posting runs | Definition of Done |

## 2. Five traps

1. **`main.TfsClient` and `main.call_llm` are resolved at call time.** Six and twenty-two
   tests monkeypatch them. `make_platform(config, tfs_factory=TfsClient)` must receive the
   name looked up inside `run_review`, never a default argument bound at import.
2. **Do not add a keyword to `call_llm`.** `tests/demo/run.py:309` defines
   `_call_llm(prompt, _config)`. Usage rides on the returned `LlmText`.
3. **Log headers are asserted verbatim** (`"| chunk 1 of 1 | attempt 1 ---"`). New data goes
   on new lines.
4. **The boundary test greps source text.** A docstring in `platform.py` mentioning
   `/pulls/` or `"git"` fails the suite with a message about the wrong boundary.
5. **`LLM_MAX_CHUNK_LINES` changes meaning** (cap only when set). `test_llm_log_run.py:67`
   still sets it to 1 — if that run has more than one chunk it now makes **one extra synthesis
call**, and the
   test counts `--- exchange ` against `llm.state["calls"]`, so the synthesis entry must use
   the same prefix.

## 3. Local manual runs

TFS (unchanged — note `TFS_API_VERSION=5.0` on this server):

```bash
python -m review_agent --local --pr <id>                 # preview
```

GitHub (from `.env`; `GIT_REPO_TOKEN` is accepted as `GH_TOKEN`):

```bash
PLATFORM=github GH_REPOSITORY=vijayclarion/codereviewsample \
GH_CHECKLIST_REPO=vijayclarion/codereviewchecklist \
python -m review_agent --local --pr <number> --log-llm   # preview, with the log
```

Expected: phase lines for every stage, a `llm usage:` line with real counts, and a printed
summary containing `### Cross-file issues`.

## 4. The acceptance test that matters most

`tests/integration/test_cross_file_cart.py`: a fixture PR changes
`ICartService.AddItem(int productId, int quantity)` to
`AddItem(int productId, int quantity, string couponCode)` and leaves `CartController`
calling the two-argument form.

- **Together**: default budget → one call; the fake provider's `cross_file_issues` naming
  both files is reported.
- **Apart**: `LLM_MAX_PROMPT_TOKENS` set so the planner must separate them (asserted from
  `ChunkPlan.assignment`, not assumed) → two chunks + synthesis; the fake returns the
  cross-file issue **only from the synthesis call**, and it is still reported.

Both assert the summary names both files, and that the outline in each chunk prompt lists
`AddItem` as a removed and an added declaration of `Interfaces.cs`.

## 5. Before any outward step

Pushing a branch, creating an issue, opening a PR, or uploading anything: confirm with the
requester first. Secrets are never set; the final report lists them (plan.md, Secrets).
