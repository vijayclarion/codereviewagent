"""Configuration loading, validation, and secret hygiene.

The only module that reads the environment. Everything else receives a frozen
``Config`` (FR-001), which is what makes "no hard-coded values" checkable rather
than aspirational - see tests/contract/test_import_boundaries.py.

Also the home of the redaction registry. Every secret value loaded here is
registered, and every byte the process prints goes through ``emit``, so a token
cannot escape through an exception message or a stray repr (FR-006, research R8).
"""

import os
import re
import sys
from dataclasses import dataclass, field, fields
from urllib.parse import urlparse

from .errors import MissingConfiguration

# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------

_SECRETS = set()
_REDACTION = "***"
# Short values would match everywhere and turn output into a wall of ***.
_MIN_SECRET_LEN = 6


def register_secret(value):
    """Mark a value as never printable."""
    if value and isinstance(value, str) and len(value) >= _MIN_SECRET_LEN:
        _SECRETS.add(value)


def clear_secrets():
    """Test-only: reset the registry between cases."""
    _SECRETS.clear()


def redact(text):
    """Replace every registered secret in ``text``.

    Longest first, so a token that contains a shorter registered value does not
    leave a fragment behind.
    """
    if not text:
        return text
    result = str(text)
    for secret in sorted(_SECRETS, key=len, reverse=True):
        if secret in result:
            result = result.replace(secret, _REDACTION)
    return result


_console_prepared = False


def prepare_console():
    """Make stdout/stderr able to carry the rendered markdown.

    The feedback contains emoji and en dashes, and a Windows console defaults to
    cp1252 - which is precisely the target platform (a self-hosted build agent).
    Left alone, preview mode (the DEFAULT mode) dies with UnicodeEncodeError
    partway through printing the summary. Idempotent and best-effort.
    """
    global _console_prepared
    if _console_prepared:
        return
    _console_prepared = True
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass  # a stream that refuses is handled by the fallback in emit


def emit(text="", stream=None):
    """The single output path. Everything user-visible goes through here."""
    prepare_console()
    target = stream if stream is not None else sys.stdout
    message = redact(text)
    try:
        print(message, file=target)
    except UnicodeEncodeError:
        # Never lose the review to an encoding limitation: degrade the characters
        # the console cannot represent, keep every word of the content.
        encoding = getattr(target, "encoding", None) or "ascii"
        print(message.encode(encoding, errors="replace").decode(encoding), file=target)


def emit_error(text):
    emit(text, stream=sys.stderr)


# --------------------------------------------------------------------------
# Value parsing
# --------------------------------------------------------------------------

_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off"}

PROVIDERS = ("claude", "openai", "azure", "ollama")

#: Feature 007. Where pull requests live, and where their stories come from.
PLATFORMS = ("tfs", "github")
STORY_SOURCES = ("tfs", "github-issues", "none")
NATIVE_STORY_SOURCE = {"tfs": "tfs", "github": "github-issues"}

DEFAULT_GH_API_URL = "https://api.github.com"
_GH_REPOSITORY = re.compile(r"^[\w.-]+/[\w.-]+$")
KEYLESS_PROVIDERS = ("ollama",)
BASE_URL_REQUIRED = ("azure", "ollama")

DEFAULT_EXCLUDE_PATTERNS = (
    # Secret-bearing
    ".env", ".env.*", "*.pem", "*.key", "*.pfx", "*.p12", "*.cer", "*.crt",
    "*.jks", "*.keystore", "*.snk", "id_rsa*", "*secrets*.json",
    "*.publishsettings", "appsettings*.json",
    # Machine-generated / noise
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "*.min.js", "*.min.css", "*.designer.cs", "*.g.cs",
    "*.generated.*", "**/Migrations/**", "**/bin/**", "**/obj/**",
    "**/node_modules/**", "**/dist/**", "**/packages/**",
    # Binary
    "*.dll", "*.exe", "*.pdb", "*.zip", "*.png", "*.jpg", "*.jpeg", "*.gif",
    "*.ico", "*.pdf",
    # Checklist documents are what a review measures against, never what it
    # reviews (FR-018). A pull request that legitimately touches one must not
    # turn the standard itself into a finding.
    "*.xlsx", "*.docx",
)

#: The configuration name that identifies the checklist repository. Three older
#: names remain accepted (see `_resolve_checklist_repo`) so that no working
#: configuration has to be renamed (FR-001), but this is the one an operator who
#: has set nothing is told to set.
CHECKLIST_REPO_SETTING = "TFS_REPO_CODE_REVIEW_CodeReviewChecklist"

#: Both document formats, comma-separated, matched against the filename, and
#: adjustable without a code change (FR-007). Markdown is deliberately NOT in the
#: default: a markdown file yields no individually citable rule, and FR-017
#: requires every violation to cite one. Setting this to `*.md` still selects the
#: plain-text path feature 002 delivered, which remains fully supported.
DEFAULT_CHECKLIST_PATTERN = "*.xlsx,*.docx"


def split_patterns(raw):
    """A comma-separated pattern list as a tuple. Tolerates a single pattern."""
    return tuple(p.strip() for p in (raw or "").split(",") if p.strip())


class _Problems:
    """Accumulates validation failures so all of them are reported at once."""

    def __init__(self):
        self.items = []

    def add(self, text):
        self.items.append(text)

    def raise_if_any(self):
        if self.items:
            raise MissingConfiguration(self.items)


def _parse_bool(raw, name, problems, default):
    if raw is None or raw == "":
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    problems.add(f"{name} must be true/false (got {raw!r})")
    return default


def _parse_int(raw, name, problems, default, minimum=1):
    if raw is None or raw == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        problems.add(f"{name} must be an integer (got {raw!r})")
        return default
    if value < minimum:
        problems.add(f"{name} must be >= {minimum} (got {value})")
        return default
    return value


def _parse_price(raw, name, problems):
    """A non-negative decimal, or None when unset (feature 007, D15)."""
    if raw is None or raw == "":
        return None
    try:
        value = float(raw.strip())
    except ValueError:
        problems.add(f"{name} must be a number (got {raw!r})")
        return None
    if value < 0:
        problems.add(f"{name} must be >= 0 (got {value})")
        return None
    return value


def derive_repo_name(url):
    """Pull the repository name out of a TFS git URL.

    The brief hands us ``CHECKLIST_REPO_URL`` (a clone URL) but the REST call
    needs a repository name, so the ``_git/{name}`` segment is the bridge.
    Returns None when the URL has no such segment, which the caller reports
    rather than guessing.
    """
    if not url:
        return None
    path = urlparse(url).path or url
    parts = [p for p in path.split("/") if p]
    if "_git" in parts:
        index = parts.index("_git")
        if index + 1 < len(parts):
            return parts[index + 1]
    return None


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    tfs_base_url: str
    tfs_project: str
    tfs_repo: str
    tfs_pr_id: int
    tfs_api_version: str
    auth_mode: str  # "bearer" | "basic"
    tfs_token: str = field(repr=False)
    llm_provider: str = "claude"
    llm_model: str = ""
    llm_api_key: str = field(default="", repr=False)
    llm_base_url: str = ""
    checklist_repo: str = ""
    #: Which configuration name supplied `checklist_repo`, so the run can say so.
    checklist_setting: str = ""
    checklist_path: str = "/"
    checklist_file_pattern: str = DEFAULT_CHECKLIST_PATTERN
    #: Empty means "the repository's own default branch" - see R2. Guessing
    #: `main` produced "could not obtain X at main", which reads as a missing
    #: repository rather than a wrong branch.
    checklist_branch: str = ""
    checklist_max_chars: int = 60000
    # Feature 002: the posting credential is separate from the reading one, so a
    # dry run can be proven never to hold a token that could write (FR-006, R9).
    post_token: str = field(default="", repr=False)
    # Feature 002: where the review logic itself comes from (FR-012).
    agent_repo: str = ""
    agent_ref: str = "master"
    local_logic: bool = False
    bootstrapped_sha: str = ""
    dry_run: bool = True
    fail_on_contradiction: bool = False
    review_exclude_patterns: tuple = DEFAULT_EXCLUDE_PATTERNS
    review_max_files: int = 40
    review_max_diff_lines: int = 3000
    llm_max_chunk_lines: int = 1200
    # Feature 006: an opt-in transcript of the provider conversation. Off by
    # default because a prompt carries the pull request's whole diff. The
    # directory is stored ABSOLUTE - it is resolved in the launching process,
    # because the child that performs the review runs inside a fetched clone
    # that is deleted moments later (006 research D4).
    llm_log: bool = False
    llm_log_dir: str = ""
    llm_log_keep: int = 10
    # Feature 007: the second platform. On GitHub the TFS fields above stay
    # empty, and `checklist_repo` / `agent_repo` carry `owner/name`.
    platform: str = "tfs"
    story_source: str = "tfs"
    gh_api_url: str = DEFAULT_GH_API_URL
    gh_repository: str = ""
    gh_pr_number: int = 0
    gh_token: str = field(default="", repr=False)
    gh_post_token: str = field(default="", repr=False)
    gh_checklist_token: str = field(default="", repr=False)
    gh_checklist_repo: str = ""
    gh_agent_repo: str = ""
    # Feature 007: the budget is tokens for a whole prompt, not lines of diff.
    # `llm_max_chunk_lines` survives as an optional extra cap - 0 means none.
    llm_max_prompt_tokens: int = 120000
    llm_max_output_tokens: int = 8192
    llm_price_input_per_mtok: object = None
    llm_price_output_per_mtok: object = None
    llm_price_currency: str = "USD"

    SECRET_FIELDS = (
        "tfs_token",
        "llm_api_key",
        "post_token",
        "gh_token",
        "gh_post_token",
        "gh_checklist_token",
    )

    def __repr__(self):
        parts = []
        for f in fields(self):
            if f.name in self.SECRET_FIELDS:
                parts.append(f"{f.name}={_REDACTION}")
            else:
                parts.append(f"{f.name}={getattr(self, f.name)!r}")
        return f"Config({', '.join(parts)})"

    @property
    def api_root(self):
        return f"{self.tfs_base_url}/{self.tfs_project}/_apis"

    @property
    def pr_id(self):
        """The pull request under review, whichever platform holds it."""
        return self.gh_pr_number if self.platform == "github" else self.tfs_pr_id

    @property
    def gh_web_url(self):
        """The git/web host behind `gh_api_url`.

        github.com's API lives on its own host; GitHub Enterprise Server's
        lives under `/api/v3` on the same host as the web interface.
        """
        api = (self.gh_api_url or DEFAULT_GH_API_URL).rstrip("/")
        if api == DEFAULT_GH_API_URL:
            return "https://github.com"
        if api.endswith("/api/v3"):
            return api[: -len("/api/v3")]
        return api

    @property
    def gh_graphql_url(self):
        api = (self.gh_api_url or DEFAULT_GH_API_URL).rstrip("/")
        if api == DEFAULT_GH_API_URL:
            return f"{DEFAULT_GH_API_URL}/graphql"
        return f"{self.gh_web_url}/api/graphql"


def _env(name, default=None):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip() or default


#: Environment variables that carry a credential into this process. A child that
#: does not need one must not inherit it.
SECRET_ENV_NAMES = (
    "TFS_PAT",
    "TFS_PAT_FOR_PR",
    "LLM_API_KEY",
    # Feature 007.
    "GH_TOKEN",
    "GH_TOKEN_FOR_PR",
    "GH_CHECKLIST_TOKEN",
    "GITHUB_TOKEN",
    "GIT_REPO_TOKEN",
)


def child_environment(overrides=None, drop_secrets=False):
    """The environment to hand a child process, with `overrides` applied.

    Feature 002 spawns two kinds of child, and they need different things.
    The re-executed review loads its own configuration, so it inherits
    everything. git needs one credential and no others, so it is given
    ``drop_secrets=True``: the PAT it uses arrives through its own variable
    (see source_fetch.TOKEN_ENV) and the posting credential never reaches it at
    all, because cloning is a reading operation.

    Building both here keeps Principle I intact - the environment is still read
    in exactly one module - and lets the fetch and bootstrap paths be tested
    without touching the real environment.
    """
    env = dict(os.environ)
    if drop_secrets:
        for name in SECRET_ENV_NAMES:
            env.pop(name, None)
    env.update(overrides or {})
    return env


def bootstrap_marker():
    """The marker a bootstrapped child was launched with (empty when not one).

    Read here rather than in `bootstrap.py` for the same reason as above. The
    marker is process plumbing, not configuration, but it still arrives through
    the environment and so belongs to this module.
    """
    return {
        "commit": _env("REVIEW_AGENT_BOOTSTRAPPED") or "",
        "repo": _env("REVIEW_AGENT_BOOTSTRAPPED_REPO") or "",
        "ref": _env("REVIEW_AGENT_BOOTSTRAPPED_REF") or "",
    }


def load_dotenv_if_present(repo_root=None):
    """Load `.env` for manual runs. Pipeline variables still win.

    ``python-dotenv`` does not override already-set variables by default, which
    is exactly the precedence we want: pipeline -> .env -> default.
    """
    if os.environ.get("REVIEW_AGENT_SKIP_DOTENV"):
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # dotenv is optional at runtime in a pipeline
        return
    root = repo_root or os.getcwd()
    load_dotenv(os.path.join(root, ".env"), override=False)


def _resolve_checklist_repo():
    """The checklist repository name, and which setting supplied it (FR-001, R1).

    Four names, first non-empty wins. The canonical one is the spelling the
    operator's provisioned `.env` actually carries; the second is the spelling
    the original brief carried, which differs by one trailing character and is
    the entire reason no checklist has ever been applied on this machine.
    Renaming the operator's variable would have been the smaller change to make
    here and the larger one to make everywhere else, so every older name stays
    accepted.
    """
    for name in (
        CHECKLIST_REPO_SETTING,
        CHECKLIST_REPO_SETTING + "T",
        "CHECKLIST_REPO",
    ):
        value = _env(name)
        if value:
            return value, name

    url = _env("CHECKLIST_REPO_URL") or ""
    derived = derive_repo_name(url)
    if derived:
        return derived, "CHECKLIST_REPO_URL"
    return "", ""


def load_config(
    pr_id_override=None,
    dry_run_override=None,
    repo_root=None,
    local_logic_override=None,
    llm_log_override=None,
):
    """Build a validated Config, or raise with every problem at once."""
    load_dotenv_if_present(repo_root)
    problems = _Problems()

    # Feature 007: which platform. Everything below that is platform-specific
    # is required ONLY for the platform in use, so a TFS run never needs a
    # GitHub setting and the reverse - and a TFS run reads exactly what it
    # read before this feature, with the same messages.
    platform = (_env("PLATFORM") or "tfs").lower()
    if platform not in PLATFORMS:
        problems.add(f"PLATFORM must be one of {'/'.join(PLATFORMS)} (got {platform!r})")
        platform = "tfs"
    on_github = platform == "github"

    base_url = project = repo = None
    pr_id = 0
    auth_mode, token = "basic", ""
    gh = {
        "api_url": DEFAULT_GH_API_URL,
        "repository": "",
        "pr_number": 0,
        "token": "",
        "post_token": "",
        "checklist_token": "",
        "checklist_repo": "",
        "agent_repo": "",
    }

    if not on_github:
        # Pipeline variables take precedence over their .env equivalents.
        base_url = _env("TFS_BASE_URL") or _env("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI")
        project = _env("TFS_PROJECT") or _env("SYSTEM_TEAMPROJECT")
        # Feature 002 (R10): the provisioned .env names are canonical; the 001 names
        # remain accepted aliases so existing configurations keep working. Renaming
        # would have broken the only working configuration on the developer's machine.
        repo = (
            _env("TFS_REPO_CODE_SAMPLE")
            or _env("TFS_REPO")
            or _env("BUILD_REPOSITORY_NAME")
        )
        raw_pr = _env("TFS_PR_ID") or _env("SYSTEM_PULLREQUEST_PULLREQUESTID")

        if base_url:
            base_url = base_url.rstrip("/")
        else:
            problems.add("TFS_BASE_URL is required")
        if not project:
            problems.add("TFS_PROJECT is required")
        if not repo:
            problems.add("TFS_REPO_CODE_SAMPLE is required (alias: TFS_REPO)")

        if pr_id_override is not None:
            pr_id = pr_id_override
        elif raw_pr:
            pr_id = _parse_int(raw_pr, "TFS_PR_ID", problems, 0, minimum=1)
        else:
            problems.add("TFS_PR_ID is required")

        # Auth. An empty-string pipeline token counts as absent - that is exactly
        # what a job without "Allow scripts to access the OAuth token" exports, and
        # treating it as present produces a baffling redirect instead of this
        # message (research R2).
        pipeline_token = _env("SYSTEM_ACCESSTOKEN")
        pat = _env("TFS_PAT")
        if pipeline_token:
            auth_mode, token = "bearer", pipeline_token
        elif pat:
            auth_mode, token = "basic", pat
        else:
            auth_mode, token = "basic", ""
            problems.add(
                "no usable credential: set SYSTEM_ACCESSTOKEN (pipeline) or TFS_PAT (manual)"
            )
        register_secret(token)
    else:
        gh["api_url"] = (
            _env("GH_API_URL") or _env("GITHUB_API_URL") or DEFAULT_GH_API_URL
        ).rstrip("/")
        gh["repository"] = _env("GH_REPOSITORY") or _env("GITHUB_REPOSITORY") or ""
        if not gh["repository"]:
            problems.add("GH_REPOSITORY is required (owner/name; alias: GITHUB_REPOSITORY)")
        elif not _GH_REPOSITORY.match(gh["repository"]):
            problems.add(f"GH_REPOSITORY must be owner/name (got {gh['repository']!r})")

        if pr_id_override is not None:
            gh["pr_number"] = pr_id_override
        elif _env("GH_PR_NUMBER"):
            gh["pr_number"] = _parse_int(_env("GH_PR_NUMBER"), "GH_PR_NUMBER", problems, 0)
        else:
            problems.add("GH_PR_NUMBER is required (or pass --pr)")

        # GIT_REPO_TOKEN is the name the requester's own .env uses; GITHUB_TOKEN
        # is what a workflow step usually exports. GH_TOKEN wins over both.
        gh["token"] = _env("GH_TOKEN") or _env("GITHUB_TOKEN") or _env("GIT_REPO_TOKEN") or ""
        if not gh["token"]:
            problems.add(
                "GH_TOKEN is required to read the pull request "
                "(aliases: GITHUB_TOKEN, GIT_REPO_TOKEN)"
            )
        gh["checklist_token"] = _env("GH_CHECKLIST_TOKEN") or gh["token"]
        gh["checklist_repo"] = _env("GH_CHECKLIST_REPO") or ""
        gh["agent_repo"] = _env("GH_AGENT_REPO") or ""
        auth_mode, token = "bearer", ""
        register_secret(gh["token"])
        register_secret(gh["checklist_token"])

    provider = (_env("LLM_PROVIDER") or "").lower()
    if not provider:
        problems.add("LLM_PROVIDER is required")
    elif provider not in PROVIDERS:
        problems.add(f"LLM_PROVIDER must be one of {'/'.join(PROVIDERS)} (got {provider!r})")

    model = _env("LLM_MODEL") or ""
    if not model:
        problems.add("LLM_MODEL is required")

    api_key = _env("LLM_API_KEY") or ""
    if provider and provider not in KEYLESS_PROVIDERS and not api_key:
        problems.add(f"LLM_API_KEY is required for LLM_PROVIDER={provider}")
    register_secret(api_key)

    base_llm_url = _env("LLM_BASE_URL") or ""
    if provider in BASE_URL_REQUIRED and not base_llm_url:
        problems.add(f"LLM_BASE_URL is required for LLM_PROVIDER={provider}")

    checklist_repo, checklist_setting = _resolve_checklist_repo()
    if on_github and gh["checklist_repo"]:
        checklist_repo, checklist_setting = gh["checklist_repo"], "GH_CHECKLIST_REPO"

    # Feature 002: the agent repository is fetched and executed on every run, so
    # that a review always reflects the latest committed logic (FR-012). The
    # --local override is the only way to review with an unfetched copy.
    agent_setting = "GH_AGENT_REPO" if on_github else "TFS_REPO_CODE_REVIEW_CodeReviewAgent"
    agent_repo = (gh["agent_repo"] if on_github else _env(agent_setting)) or ""
    agent_ref = _env("AGENT_REF") or "master"
    local_logic = bool(local_logic_override)
    bootstrapped_sha = _env("REVIEW_AGENT_BOOTSTRAPPED") or ""
    if not agent_repo and not local_logic and not bootstrapped_sha:
        problems.add(f"{agent_setting} is required (or run with --local)")

    # Feature 007: the story source, defaulting to the platform's own.
    story_source = (_env("STORY_SOURCE") or NATIVE_STORY_SOURCE[platform]).lower()
    if story_source not in STORY_SOURCES:
        problems.add(
            f"STORY_SOURCE must be one of {'/'.join(STORY_SOURCES)} (got {story_source!r})"
        )
        story_source = NATIVE_STORY_SOURCE[platform]
    elif story_source == "github-issues" and not on_github:
        problems.add("STORY_SOURCE=github-issues requires PLATFORM=github")
    elif story_source == "tfs" and on_github:
        problems.add("STORY_SOURCE=tfs requires PLATFORM=tfs")

    exclude_raw = _env("REVIEW_EXCLUDE_PATTERNS") or ""
    extra = tuple(p.strip() for p in exclude_raw.split(",") if p.strip())
    mode = (_env("REVIEW_EXCLUDE_MODE") or "extend").lower()
    if mode not in ("extend", "replace"):
        problems.add(f"REVIEW_EXCLUDE_MODE must be extend or replace (got {mode!r})")
        mode = "extend"
    patterns = extra if mode == "replace" and extra else DEFAULT_EXCLUDE_PATTERNS + extra

    dry_run = (
        dry_run_override
        if dry_run_override is not None
        else _parse_bool(_env("DRY_RUN"), "DRY_RUN", problems, True)
    )

    # Feature 002 (FR-006, FR-008): a separate credential for posting, required
    # only by a run that will actually post. A dry run must succeed without it -
    # that is what makes "a preview cannot write" a property rather than a promise.
    post_token = ""
    if not on_github:
        post_token = _env("TFS_PAT_FOR_PR") or ""
        register_secret(post_token)
        if not dry_run and not post_token:
            problems.add("TFS_PAT_FOR_PR is required to post (omit --post for a dry run)")
    else:
        gh["post_token"] = _env("GH_TOKEN_FOR_PR") or ""
        register_secret(gh["post_token"])
        if not dry_run and not gh["post_token"]:
            problems.add("GH_TOKEN_FOR_PR is required to post (omit --post for a dry run)")

    # Feature 006. Parsed even when logging is off, so a bad value is reported
    # now rather than on the day someone first needs the feature. The directory
    # is resolved HERE, in whichever process the operator launched, and carried
    # to the re-executed child through bootstrap's environment overrides.
    llm_log = bool(llm_log_override) or _parse_bool(
        _env("LLM_LOG"), "LLM_LOG", problems, False
    )
    llm_log_dir = os.path.abspath(_env("LLM_LOG_DIR") or ".llm-logs")

    # Feature 007 (D8, D15).
    prompt_tokens = _parse_int(
        _env("LLM_MAX_PROMPT_TOKENS"), "LLM_MAX_PROMPT_TOKENS", problems, 120000, minimum=8000
    )
    output_tokens = _parse_int(
        _env("LLM_MAX_OUTPUT_TOKENS"), "LLM_MAX_OUTPUT_TOKENS", problems, 8192, minimum=256
    )
    if output_tokens * 2 >= prompt_tokens:
        problems.add(
            f"LLM_MAX_OUTPUT_TOKENS ({output_tokens}) must be less than half of "
            f"LLM_MAX_PROMPT_TOKENS ({prompt_tokens})"
        )

    config = Config(
        tfs_base_url=base_url or "",
        tfs_project=project or "",
        tfs_repo=repo or "",
        tfs_pr_id=pr_id,
        tfs_api_version=_env("TFS_API_VERSION") or "6.0",
        auth_mode=auth_mode,
        tfs_token=token,
        llm_provider=provider,
        llm_model=model,
        llm_api_key=api_key,
        llm_base_url=base_llm_url,
        checklist_repo=checklist_repo,
        checklist_setting=checklist_setting,
        checklist_path=_env("CHECKLIST_PATH") or "/",
        checklist_file_pattern=_env("CHECKLIST_FILE_PATTERN") or DEFAULT_CHECKLIST_PATTERN,
        checklist_branch=_env("CHECKLIST_BRANCH") or "",
        # Measured, not guessed: the five real checklist documents render to
        # 48,485 characters of rule items (165 rules). Planning predicted ~22,000
        # and set the cap at 40,000, which would have silently dropped a third of
        # the corpus on its first real run.
        checklist_max_chars=_parse_int(
            _env("CHECKLIST_MAX_CHARS"), "CHECKLIST_MAX_CHARS", problems, 60000
        ),
        post_token=post_token,
        agent_repo=agent_repo,
        agent_ref=agent_ref,
        local_logic=local_logic,
        bootstrapped_sha=bootstrapped_sha,
        dry_run=dry_run,
        fail_on_contradiction=_parse_bool(
            _env("FAIL_ON_CONTRADICTION"), "FAIL_ON_CONTRADICTION", problems, False
        ),
        review_exclude_patterns=patterns,
        review_max_files=_parse_int(_env("REVIEW_MAX_FILES"), "REVIEW_MAX_FILES", problems, 40),
        review_max_diff_lines=_parse_int(
            _env("REVIEW_MAX_DIFF_LINES"), "REVIEW_MAX_DIFF_LINES", problems, 3000
        ),
        # Feature 007: unset means no line cap - the token budget decides.
        llm_max_chunk_lines=_parse_int(
            _env("LLM_MAX_CHUNK_LINES"), "LLM_MAX_CHUNK_LINES", problems, 0
        ),
        llm_log=llm_log,
        llm_log_dir=llm_log_dir,
        llm_log_keep=_parse_int(
            _env("LLM_LOG_KEEP"), "LLM_LOG_KEEP", problems, 10, minimum=1
        ),
        platform=platform,
        story_source=story_source,
        gh_api_url=gh["api_url"],
        gh_repository=gh["repository"],
        gh_pr_number=gh["pr_number"],
        gh_token=gh["token"],
        gh_post_token=gh["post_token"],
        gh_checklist_token=gh["checklist_token"],
        gh_checklist_repo=gh["checklist_repo"],
        gh_agent_repo=gh["agent_repo"],
        llm_max_prompt_tokens=prompt_tokens,
        llm_max_output_tokens=output_tokens,
        llm_price_input_per_mtok=_parse_price(
            _env("LLM_PRICE_INPUT_PER_MTOK"), "LLM_PRICE_INPUT_PER_MTOK", problems
        ),
        llm_price_output_per_mtok=_parse_price(
            _env("LLM_PRICE_OUTPUT_PER_MTOK"), "LLM_PRICE_OUTPUT_PER_MTOK", problems
        ),
        llm_price_currency=_env("LLM_PRICE_CURRENCY") or "USD",
    )

    problems.raise_if_any()
    return config
