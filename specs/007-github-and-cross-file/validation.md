# Validation Record: 007 GitHub Platform Support and Cross-File Review

Every measured result of this feature, in the order it was measured. Nothing here is
predicted. Output is redacted; no token value appears.

## Baseline

| When | Commit | Command | Result |
|---|---|---|---|
| 2026-10-18 | `7eddb98` | `python -m pytest tests` | **597 passed** |
| 2026-10-18 | working tree | Phase 2 checkpoint (T014) | **643 passed, 3 skipped** — the 597 pre-existing pass unmodified; 46 new pass; 3 boundary cases skip until their modules exist |

Notes from Phase 2:
- `LLM_MAX_CHUNK_LINES` default became 0 (no cap). `prompt_builder.build_prompts` maps 0 to
  "no cap" immediately — the old `chunk_files` would otherwise have put every file in its own
  chunk. The suite did not catch this because the demo fixture reviews one file.
- `tests/conftest.py` also gained a `github_env` fixture (a new fixture, not a change to any
  existing one).
| 2026-10-18 | working tree | US1 checkpoint (T033) | **700 passed, 2 skipped** — 597 pre-existing unmodified |

Notes from US1:
- T031 needed no code in `checklist.py` or `bootstrap.py`: `load_config` puts GitHub's
  `owner/name` into `checklist_repo` / `agent_repo`, and `source_fetch.default_token` picks the
  checklist token for the checklist repository and the read token otherwise.
- `stories.py` and `WorkItem.from_issue` (T038-T041) were implemented during US1 because a
  GitHub run needs a story source; their dedicated tests are Phase 4 (T034-T037).
- Added beyond the plan: `GitHubClient` passes every posted body through `redact` (SC-009).
  TFS posting is unchanged.
- The 422 fallback is the one the plan specifies (a second review listing the findings).
  Analysis finding I4 proposed moving them into the summary instead; not applied (not approved).
| 2026-10-18 | working tree | US2 checkpoint (T043) | **732 passed, 2 skipped** |
| 2026-10-18 | working tree | US3 checkpoint (T060) | **809 passed** — the always-present `### Cross-file issues` section broke no pre-existing test, so T060's fallback was not needed |

## Budget measured against the real checklist corpus (T061)

Checklist repository `vijayclarion/codereviewchecklist` cloned read-only (public, no
credential) into the scratchpad; the corpus built by the agent's own `checklist` module.

| Quantity | Measured |
|---|---|
| Documents read | 5 |
| Rules | 140 (the TFS copy measured 165 in feature 003; the GitHub copy differs) |
| Rendered rule text | 37,477 characters |
| Fixed prompt sections (role, rules, contract, story #7, scope, checklist) | 41,617 characters, **13,873 estimated tokens** |
| Diff budget per chunk at defaults (120,000 − 8,192 − fixed − outline) | **97,935 tokens ≈ 293,805 characters** |

So a pull request whose reviewed diffs total under ~290,000 characters is one call.

Notes from US3:
- The outline lists every **reviewed** file. Excluded and unreviewed files are **counted, not
  named**, because the pre-existing contract test
  `test_excluded_files_never_sent.py::test_the_excluded_file_path_is_not_even_named_in_the_prompt`
  forbids an excluded path reaching the provider. FR-015 says "every changed file"; the
  existing invariant wins.
- Skeletons are capped at a quarter of the diff budget (with a "N more declarations not
  shown" line): a file with hundreds of fields otherwise has a skeleton as large as its
  diff and forces every hunk to be cut mid-way. Found by `test_chunk_planner.py`.
- `LLM_MAX_OUTPUT_TOKENS` is sent only to Claude (`max_tokens`). Not added to OpenAI/Azure
  requests: newer OpenAI models reject `max_tokens` in favour of `max_completion_tokens`, so
  adding it could break a working configuration. T059 narrowed accordingly.
- Synthesis reuses `STRICTER_RETRY` for its one retry.
| 2026-10-18 | working tree | US5 checkpoint (T073) | **846 passed**; `python -m tests.demo.run` exit 0 (T098) |

## Diagram render (T075)

PlantUML 1.2023.13 (the newest line that runs on this machine's Java 8), downloaded to the
scratchpad and run locally - nothing was sent to a public server.

| Diagram | Result |
|---|---|
| `docs/review-flow.puml` | renders, 0 syntax errors, SVG 4574px tall. Two fixes were needed first: a multi-line activity cannot start a line with `(`, and a line ending `;` ends the activity early |
| `docs/local-mode-pr-review-activity.puml` (control, unchanged) | renders, 0 syntax errors, 4178px |

| 2026-10-18 | working tree | after US6 docs | **846 passed** |

## Live runs

| Task | Result |
|---|---|
| T080 preflight | `.env` holds `GIT_REPO_TOKEN`, `LLM_API_KEY`, `LLM_MODEL`, `TFS_PAT`, `TFS_PAT_FOR_PR`, `TFS_BASE_URL` (presence counted, values never read out). `gh` CLI not installed - GitHub operations use scratch REST scripts |
| T081 TFS live preview | **Blocked, not performed.** The TFS host does not resolve from this machine (`NameResolutionError ... getaddrinfo failed`) - presumably it needs the internal network or VPN. Not worked around (FR-041) |
| T081 decision | The requester chose not to test TFS live now ("dont test TFS now just github now"). Not performed |
| T094 (Q1) | Approved by the requester. TFS posts with `TFS_PAT_FOR_PR` from a client built only when posting. **851 passed** |
| T083 | Sample source read (C#: `ICartRepository`, `ICatalogService`, `CartController`, `Cart`). Demo violation chosen: **DEV-STD-06 Deterministic Time Handling** (`DateTime.Now` in business logic). The sample has no `ICartService`; the demo's cross-file defect is a signature change to `ICartRepository.Save` |
| T082 push | **Blocked.** `origin` added (`https://github.com/vijayclarion/codereviewagent`, no credential in the URL); `git fetch` succeeded; `git push -u origin 007-github-and-cross-file` refused: `Permission to vijayclarion/codereviewagent.git denied` (HTTP 403). The repository API reports the *account* as admin, but the fine-grained `GIT_REPO_TOKEN` itself evidently lacks Contents (write). Stopped per FR-041; T084-T093 depend on it. History scan of `7eddb98..HEAD` before the attempt: 0 secret hits |
| T082 (retry, after the token was fixed) | Pushed `007-github-and-cross-file`; history scan 0 hits. **PR https://github.com/vijayclarion/codereviewagent/pull/1** |
| T084 | Sample branch `ai-review-setup` (caller workflow + issue template; `.gitignore` already had `.env`). **PR https://github.com/vijayclarion/codereviewsample/pull/1**. Its workflow run fails until `AI_REVIEW_LLM_API_KEY` is set (expected) |
| T085 | **Issue https://github.com/vijayclarion/codereviewsample/issues/2** "Apply a coupon when adding an item to the cart", 3 criteria |
| T086 | Branch `demo/cart-coupon` from `ai-review-setup`. **PR https://github.com/vijayclarion/codereviewsample/pull/3** ("Closes #2") |
| T092 | Checklist branch `add-gitignore`. **PR https://github.com/vijayclarion/codereviewchecklist/pull/1** |
| T087 GitHub live preview of PR #3 | **Stopped at the model call: the provider rejected `LLM_API_KEY` (HTTP 401), exit 2.** Everything before it worked live: PR read (`platform=github draft=False`), issue #2 found with 3 criteria (`source=github-issues count=1 criteria=3`), checklist cloned (5 documents, 140 rules), 5 files diffed against the merge base (60 changed lines), prior comments read (`posted=0`), planned as 1 chunk (budget 97,465 tokens, 4 groups). The log recorded the failed send with `model    : claude / claude-sonnet-5`, `tokens   : not reported` and the reason. The outline row for `Interfaces.cs` read `removed: void Save(Cart cart) / added: void Save(Cart cart, string appliedCouponCode)`. Not worked around (FR-041) |

### Demo PR #3: the defects planted, and what the review should report

Kept here rather than in the PR description, which is sent to the model.

| Planted | Where | Expected finding |
|---|---|---|
| `ICartRepository.Save(Cart)` became `Save(Cart, string appliedCouponCode)`; `CartController` still calls `_carts.Save(cart)` | `Interfaces.cs`, `CartController.cs` | **cross-file issue** naming both files |
| `cart.CouponAppliedAt = DateTime.Now;` in the controller | `CartController.cs` | **checklist violation DEV-STD-06** (Deterministic Time Handling) |
| The discount is applied **after** `_carts.Save(cart)` | `CartController.cs` | criterion 3 **possible contradiction**; the description's "Covered" claim for it is a **false coverage claim** |
| Unknown/expired coupons are not rejected (declared "Not in this PR") | - | criterion 2 **not addressed** (neutral, no comment) |
| The coupon code is stored on the cart | `CartController.cs`, `Cart.cs` | criterion 1 **appears addressed** |
| T087 (rerun, after the key was replaced) | **Complete, exit 0, zero writes.** `phase=llm chunks=1 retries=0 tokens_in=18813 tokens_out=4826` (provider-reported); `phase=parse coverage=3 violations=2 issues=2 cross_file=2 false_claims=1`; `phase=post outcome=dry-run inline=6`. **Every planted defect found**: cross-file `Save` signature (high, both files named); DEV-STD-06 `DateTime.Now`; criterion 3 possible contradiction + false coverage claim; criterion 2 not addressed; criterion 1 appears addressed. Also reported: missing tests (a second cross-file issue, plus the NFR "unit tests" rule), hard-coded 10% discount, no bounds check in `ApplyCoupon` |
| T089 first attempt | The workflow's first run on PR #3 (before the new secret) ran checkout, setup-python and install successfully, reviewed up to the model call in CI (`platform=github`, issue #2, 140 rules, 1 chunk), and stopped on HTTP 401 - the old key. The `skipped` job was correctly skipped. Re-run requested |
| T089 (attempt 3, after the secret was replaced) | **Posted, exit 0.** `phase=llm tokens_in=18813 tokens_out=5411`; `phase=post inline=6 suppressed=0 summary=create`. On PR #3: **exactly one review** (`COMMENTED`, by `github-actions[bot]`) carrying all 6 inline comments, and **one** summary comment. The cross-file `Save` signature issue was posted inline on `Interfaces.cs:8` and listed under `### Cross-file issues (1)`. DEV-STD-06 inline on `CartController.cs:63` |
| T090 (attempt 4, unchanged PR) | **Partly met.** `phase=prior posted=6 summary=True`; `phase=post inline=2 suppressed=5 summary=update`. The summary was **edited in place** (still 1 issue comment; updated 15:12:14Z) and 5 findings were recognised. **2 new inline comments were posted** in a second review: (a) the false coverage claim for criterion 3 - summary-only on run 1 (no location, so no marker anywhere), anchored on run 2 by borrowing a checklist violation's line; (b) the "no unit tests" checklist finding - run 1 cited *"Create Unit Tests for critical parts ... XUnit + NCrunch"*, run 2 cited *"Create unit tests"*, a different rule identifier for the same problem. Both are limits of the 003 finding-identity design (identity = rule id; summary-only findings carry no marker), not of the GitHub path. **SC-004 is not met on this live run** |
