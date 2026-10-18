"""The only module that invokes git (Principle IV, research R3).

Two repositories are obtained at run time: the agent repository, whose code
actually performs the review (FR-012), and the checklist repository, whose
documents it reviews against (FR-013). Both are shallow clones into a temp
directory that is removed when the run ends.

Handling the credential is the whole difficulty here. Three common ways of
giving git a PAT all leak it:

  * ``https://user:pat@host/...``     writes the token into the clone's .git/config
  * ``-c http.extraHeader=...``       puts it in the process argument list, which
                                      any other process on the machine can read
  * ``credential.helper=store``       writes it to ~/.git-credentials

So the token goes through GIT_ASKPASS instead: git runs a tiny helper script and
reads the credential from its stdout. The helper contains no secret - it echoes
an environment variable that exists only in the git child process. The username
half is not a secret and travels in the URL, so the helper is only ever asked
for the password.

**That was not enough on this collection** (feature 003, research R13). GIT_ASKPASS
answers a *challenge*, and this server challenges with Negotiate and NTLM only, so
git never asks and the clone fails with "Authentication failed" - while the same
token reads the same repository over REST without complaint. The header is now
presented unasked, through git's environment config rather than through `-c`,
because `-c http.extraHeader=...` would put it in the argument list.

So the credential travels in **two** environment variables of the git child, in
two forms - the raw token for askpass, and its base64 Basic encoding for the
header. Both are registered as unprintable, both are confined to that child, and
neither is ever in argv, on disk, or in output. tests/contract/test_no_secrets_leak.py
asserts each of those three for both forms.

TLS: git on Windows uses the schannel backend, which validates against the
machine trust store - the same store ``truststore`` points requests at. So the
private CA on the collection host validates for both, and no certificate check
is ever switched off here (Principle III).
"""

import base64
import os
import shutil
import subprocess
import tempfile

from .config import child_environment, register_secret
from .errors import SetupFailure

#: The one environment variable that carries a credential into a child process.
#: Named explicitly so a test can assert nothing else does.
TOKEN_ENV = "REVIEW_AGENT_GIT_TOKEN"

#: Username half of Basic auth. TFS ignores it when a PAT is the password; it is
#: not a secret and so may safely travel in the URL, which keeps the askpass
#: helper down to a single question.
PAT_USERNAME = "pat"

#: The second way a credential reaches the git child, added by feature 003 after
#: the live run (research R13).
#:
#: The askpass route below answers git's *password prompt* - which only happens if
#: the server challenges with Basic. This collection challenges with Negotiate and
#: NTLM only, so git never asks, and the clone fails with "Authentication failed"
#: while the same token reads the same repository over REST perfectly well.
#:
#: The fix is to present the header unasked. It goes through git's environment
#: config (`GIT_CONFIG_COUNT` / `_KEY_n` / `_VALUE_n`, git >= 2.31) rather than
#: through `-c http.extraHeader=...`, because the latter puts the credential in
#: the process argument list where any other process on the machine can read it.
#: So the credential still exists in exactly one place: the environment of the
#: git child.
HEADER_CONFIG_ENV = ("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0")

CLONE_TIMEOUT = 300

_ASKPASS_POSIX = """#!/bin/sh
printf '%s' "${token_env}"
"""

_ASKPASS_WINDOWS = """@echo off
echo %{token_env}%
"""


class ClonedSource:
    """A fetched working tree and where it came from."""

    def __init__(self, repo, ref, path, commit):
        self.repo = repo
        self.ref = ref
        self.path = path
        self.commit = commit

    def __repr__(self):
        return f"ClonedSource(repo={self.repo!r}, ref={self.ref!r}, commit={self.commit!r})"


#: Feature 007. GitHub's git endpoint needs a username in Basic auth; for a
#: token it is this fixed, non-secret word (the form actions/checkout uses).
GITHUB_USERNAME = "x-access-token"


def _on_github(config):
    return getattr(config, "platform", "tfs") == "github"


def _repo_dir(repo):
    """The clone's directory name. `owner/name` on GitHub -> `name`, so a clone
    sits at the same depth as on TFS and `cleanup` removes the whole temp tree."""
    return (repo or "").rstrip("/").split("/")[-1]


def default_token(config, repo):
    """The credential for cloning `repo` (feature 007, D6).

    On GitHub the checklist repository may be private to a different owner, so
    it has a token of its own; everything else uses the read token.
    """
    if not _on_github(config):
        return getattr(config, "tfs_token", "")
    checklist = (getattr(config, "checklist_repo", "") or "").lower()
    if checklist and (repo or "").lower() == checklist:
        return getattr(config, "gh_checklist_token", "") or getattr(config, "gh_token", "")
    return getattr(config, "gh_token", "")


def clone_url(config, repo):
    """Credential-free clone URL, with the non-secret username only."""
    if _on_github(config):
        scheme, _, rest = config.gh_web_url.rstrip("/").partition("://")
        return f"{scheme}://{GITHUB_USERNAME}@{rest}/{repo}.git"
    base = config.tfs_base_url.rstrip("/")
    scheme, _, rest = base.partition("://")
    if not rest:  # not a URL we recognise; let git report it
        return f"{base}/{config.tfs_project}/_git/{repo}"
    return f"{scheme}://{PAT_USERNAME}@{rest}/{config.tfs_project}/_git/{repo}"


def public_url(config, repo):
    """The same URL with no credential component at all - what origin is left as."""
    if _on_github(config):
        return f"{config.gh_web_url.rstrip('/')}/{repo}.git"
    base = config.tfs_base_url.rstrip("/")
    return f"{base}/{config.tfs_project}/_git/{repo}"


def _write_askpass(directory):
    """Write the helper that answers git's password prompt.

    The file holds no secret: it echoes an environment variable. It lives in the
    run's own temp directory and dies with it.
    """
    if os.name == "nt":
        path = os.path.join(directory, "askpass.bat")
        content = _ASKPASS_WINDOWS.format(token_env=TOKEN_ENV)
    else:
        path = os.path.join(directory, "askpass.sh")
        content = _ASKPASS_POSIX.format(token_env=TOKEN_ENV)
    with open(path, "w", encoding="ascii", newline="\n") as handle:
        handle.write(content)
    if os.name != "nt":
        os.chmod(path, 0o700)
    return path


def basic_auth_header(token, username=""):
    """The Authorization header value for a PAT. Registered as unprintable.

    TFS ignores the username; GitHub requires one (`x-access-token`)."""
    encoded = base64.b64encode(f"{username}:{token}".encode("utf-8")).decode("ascii")
    header = f"Authorization: Basic {encoded}"
    # The encoded form is as much a credential as the raw one, and an error
    # message that echoed it would leak just as completely.
    register_secret(encoded)
    register_secret(header)
    return header


def _git_env(token, askpass_path, username=""):
    """Environment for the git child: the credential, and nothing else new."""
    values = {
        TOKEN_ENV: token or "",
        "GIT_ASKPASS": askpass_path,
        # Never fall back to an interactive prompt: a hung run is worse than
        # a failed one, and a terminal prompt would sit there forever.
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    if token:
        # Presented unasked, because this collection never asks (R13).
        count, key, value = HEADER_CONFIG_ENV
        values[count] = "1"
        values[key] = "http.extraHeader"
        values[value] = basic_auth_header(token, username)
    return child_environment(
        values,
        # git gets the one credential it needs and no other. In particular the
        # posting token never reaches it: cloning only ever reads.
        drop_secrets=True,
    )


def _run(args, env=None, cwd=None, runner=subprocess.run):
    try:
        return runner(
            args,
            env=env,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT,
        )
    except FileNotFoundError as exc:
        raise SetupFailure(
            "git was not found on PATH, and the agent fetches its own logic and "
            "the checklists with it",
            remedy="install git, or run with --local against a local checklist copy",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SetupFailure(
            f"git did not finish within {CLONE_TIMEOUT}s",
            remedy="check network access to the collection",
        ) from exc


def clone(config, repo, ref=None, into=None, runner=subprocess.run, token=None):
    """Shallow-clone `repo` at `ref`, returning a ClonedSource.

    Never raises with the token in the message: git's stderr is passed through
    the redaction registry by the error path, and the token is not in the URL
    that appears in it anyway.
    """
    if not repo:
        raise SetupFailure(
            "no repository name was given to clone",
            remedy="set the repository name in configuration",
        )
    parent = into or tempfile.mkdtemp(prefix="review-agent-")
    target = os.path.join(parent, _repo_dir(repo))
    askpass = _write_askpass(parent)
    credential = default_token(config, repo) if token is None else token
    env = _git_env(
        credential, askpass, username=GITHUB_USERNAME if _on_github(config) else ""
    )

    # No ref means the repository's own default branch (feature 003, R2). The
    # previous default was the literal "master", which turned a repository whose
    # default is "main" into "could not obtain X at master" - a message that
    # reads as a missing repository and sends the reader to the wrong setting.
    branch = ["--branch", ref] if ref else []

    result = _run(
        [
            "git",
            "-c", "credential.helper=",   # never consult or write a credential store
            "clone",
            "--depth", "1",
            *branch,
            "--quiet",
            clone_url(config, repo),
            target,
        ],
        env=env,
        runner=runner,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        raise SetupFailure(
            f"could not obtain {repo} at {ref}: {detail[-1] if detail else 'git failed'}",
            remedy=(
                "check the repository name, the branch, and that "
                + (
                    "the GitHub token (GH_TOKEN, or GH_CHECKLIST_TOKEN for the checklist "
                    "repository) grants Contents (read) on it"
                    if _on_github(config)
                    else "TFS_PAT grants Code (read) on it"
                )
            ),
        )

    _scrub_origin(config, repo, target, env, runner)
    # When no ref was asked for, report the one that actually arrived: "the
    # default branch" is not something an operator can check a review against.
    resolved = ref or _current_branch(target, env, runner)
    return ClonedSource(
        repo=repo, ref=resolved, path=target, commit=_head_sha(target, env, runner)
    )


def _scrub_origin(config, repo, target, env, runner):
    """Leave no credential component in the clone's stored remote."""
    _run(
        ["git", "remote", "set-url", "origin", public_url(config, repo)],
        env=env,
        cwd=target,
        runner=runner,
    )


def _current_branch(target, env, runner):
    result = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], env=env, cwd=target, runner=runner
    )
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _head_sha(target, env, runner):
    result = _run(["git", "rev-parse", "--short", "HEAD"], env=env, cwd=target, runner=runner)
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def cleanup(path):
    """Remove a fetched tree. Best effort: a leftover temp dir must never fail a run."""
    if not path:
        return
    parent = os.path.dirname(path) or path
    shutil.rmtree(parent, ignore_errors=True)
