# Contract: Configuration (new and changed settings)

**Module**: `review_agent/config.py` — still the only module that reads the environment.
**Research**: D5, D8, D15

Precedence is unchanged: process environment (pipeline / workflow) → `.env` → default.
Every validation problem is reported at once.

## Platform selection

| Setting | Values | Default | Notes |
|---|---|---|---|
| `PLATFORM` | `tfs` \| `github` | `tfs` | case-insensitive; anything else is a setup failure |
| `STORY_SOURCE` | `tfs` \| `github-issues` \| `none` | `tfs` on TFS, `github-issues` on GitHub | mismatches with `PLATFORM` are setup failures |

With `PLATFORM=tfs` (or unset), every TFS setting behaves exactly as today and no `GH_*`
setting is read for validation.

## GitHub settings (read only when `PLATFORM=github`)

| Setting | Aliases | Required | Default | Secret |
|---|---|---|---|---|
| `GH_API_URL` | `GITHUB_API_URL` | no | `https://api.github.com` | no |
| `GH_REPOSITORY` | `GITHUB_REPOSITORY` | yes | — | no |
| `GH_PR_NUMBER` | — (or `--pr`) | yes | — | no |
| `GH_TOKEN` | `GITHUB_TOKEN`, `GIT_REPO_TOKEN` | yes | — | **yes** |
| `GH_TOKEN_FOR_PR` | — | only with `--post` / `DRY_RUN=false` | — | **yes** |
| `GH_CHECKLIST_TOKEN` | — | no | `GH_TOKEN` | **yes** |
| `GH_CHECKLIST_REPO` | existing checklist settings | no | — | no |
| `GH_AGENT_REPO` | — | yes unless `--local` | — | no |

Messages follow the existing form, e.g.
`GH_TOKEN_FOR_PR is required to post (omit --post for a dry run)`,
`GH_REPOSITORY must be owner/name (got 'codereviewsample')`.

Token permissions (fine-grained):

| Token | Repository | Permissions |
|---|---|---|
| `GH_TOKEN` | the PR's repository | Pull requests: read, Issues: read, Contents: read, Metadata: read |
| `GH_TOKEN_FOR_PR` | the PR's repository | Pull requests: write, Issues: write |
| `GH_CHECKLIST_TOKEN` | the checklist repository | Contents: read |

## Budget and cost (both platforms)

| Setting | Default | Range | Notes |
|---|---|---|---|
| `LLM_MAX_PROMPT_TOKENS` | `120000` | ≥ 8000 | whole-prompt estimate, `ceil(chars/3)` |
| `LLM_MAX_OUTPUT_TOKENS` | `8192` | ≥ 256, < half the prompt budget | sent as the provider's max output |
| `LLM_MAX_CHUNK_LINES` | unset | ≥ 1 | **changed**: was default 1200; now an optional extra cap |
| `LLM_PRICE_INPUT_PER_MTOK` | unset | ≥ 0, decimal | |
| `LLM_PRICE_OUTPUT_PER_MTOK` | unset | ≥ 0, decimal | |
| `LLM_PRICE_CURRENCY` | `USD` | text | label only |

## Redaction

Every value of `GH_TOKEN`, `GH_TOKEN_FOR_PR`, `GH_CHECKLIST_TOKEN` (whichever alias
supplied it) is passed to `register_secret`. Their names join `SECRET_ENV_NAMES`, so a git
child never inherits them; the clone credential reaches git only through
`REVIEW_AGENT_GIT_TOKEN` and the header variables (D6).

## Test isolation

`tests/conftest.py::_isolate_env` additionally clears variables beginning `GH_`, `GITHUB_`,
`GIT_REPO_`, and the names `PLATFORM`, `STORY_SOURCE`.
