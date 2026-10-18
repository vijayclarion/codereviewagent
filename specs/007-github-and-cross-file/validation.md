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
