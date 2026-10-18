"""T029 - fetching a repository without leaking the credential (FR-012, R3).

The interesting assertions here are the negative ones. A PAT that reaches the
process argument list is readable by any other process on the machine; one that
reaches .git/config outlives the run entirely. Both are easy to write by
accident and impossible to notice by reading the output, so they are asserted
rather than reviewed.
"""

import os

import pytest

from review_agent import source_fetch
from review_agent.errors import SetupFailure


class _Cfg:
    tfs_base_url = "https://tfs.example.com/tfs/Coll"
    tfs_project = "Proj"
    tfs_token = "pat-secret-value"


class FakeRunner:
    """Records every git invocation instead of running one."""

    def __init__(self, returncode=0, stdout="abc1234\n", stderr=""):
        self.calls = []
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __call__(self, args, env=None, cwd=None, **kwargs):
        self.calls.append({"args": list(args), "env": dict(env or {}), "cwd": cwd})

        class _Result:
            pass

        result = _Result()
        result.returncode = self.returncode
        result.stdout = self.stdout
        result.stderr = self.stderr
        return result

    @property
    def all_args(self):
        return [arg for call in self.calls for arg in call["args"]]


@pytest.fixture
def fetched(tmp_path):
    runner = FakeRunner()
    source = source_fetch.clone(
        _Cfg(), "CodeReviewAgent", ref="master", into=str(tmp_path), runner=runner
    )
    return source, runner


# -- the credential ---------------------------------------------------------


def test_the_token_never_appears_in_any_argument(fetched):
    _, runner = fetched
    joined = " ".join(runner.all_args)
    assert "pat-secret-value" not in joined, (
        "a token in argv is readable by every other process on the machine"
    )


def test_the_token_never_appears_in_the_clone_url(fetched):
    _, runner = fetched
    urls = [a for a in runner.all_args if a.startswith("https://")]
    assert urls, "expected a clone URL"
    for url in urls:
        assert "pat-secret-value" not in url


def test_the_clone_url_carries_only_the_non_secret_username(fetched):
    _, runner = fetched
    url = [a for a in runner.all_args if a.startswith("https://")][0]
    assert url.startswith("https://pat@tfs.example.com/")


def test_the_token_reaches_the_child_only_through_the_documented_variable(fetched):
    _, runner = fetched
    for call in runner.calls:
        carriers = [k for k, v in call["env"].items() if v == "pat-secret-value"]
        assert carriers == [source_fetch.TOKEN_ENV], (
            f"the token must travel in {source_fetch.TOKEN_ENV} alone, found {carriers}"
        )


def test_the_askpass_helper_contains_no_secret(tmp_path):
    path = source_fetch._write_askpass(str(tmp_path))
    content = open(path, encoding="ascii").read()
    assert "pat-secret-value" not in content
    assert source_fetch.TOKEN_ENV in content, "it must read the variable, not embed a value"


def test_a_credential_store_is_never_consulted_or_written(fetched):
    _, runner = fetched
    clone_args = runner.calls[0]["args"]
    assert "credential.helper=" in clone_args, (
        "an empty credential.helper stops git reading or writing ~/.git-credentials"
    )


def test_an_interactive_prompt_is_never_offered(fetched):
    _, runner = fetched
    assert runner.calls[0]["env"]["GIT_TERMINAL_PROMPT"] == "0", (
        "a run that hangs on a hidden password prompt is worse than one that fails"
    )


# -- TLS (Principle III) ----------------------------------------------------


def test_tls_verification_is_never_disabled(fetched):
    _, runner = fetched
    joined = " ".join(runner.all_args)
    assert "sslVerify" not in joined
    assert "GIT_SSL_NO_VERIFY" not in " ".join(runner.calls[0]["env"].keys())


# -- clone behaviour --------------------------------------------------------


def test_the_clone_is_shallow_and_pinned_to_the_ref(fetched):
    _, runner = fetched
    args = runner.calls[0]["args"]
    assert "--depth" in args and args[args.index("--depth") + 1] == "1"
    assert "--branch" in args and args[args.index("--branch") + 1] == "master"


def test_the_commit_is_reported_for_provenance(fetched):
    source, _ = fetched
    assert source.commit == "abc1234", "FR-012b needs the commit that actually ran"


def test_the_origin_url_is_scrubbed_after_cloning(fetched):
    _, runner = fetched
    scrub = [c for c in runner.calls if "set-url" in c["args"]]
    assert scrub, "origin must be rewritten so no credential component survives"
    assert scrub[0]["args"][-1] == "https://tfs.example.com/tfs/Coll/Proj/_git/CodeReviewAgent"
    assert "pat@" not in scrub[0]["args"][-1]


def test_a_failed_clone_is_a_setup_failure_naming_the_repository(tmp_path):
    runner = FakeRunner(returncode=128, stdout="", stderr="fatal: repository not found")
    with pytest.raises(SetupFailure) as exc:
        source_fetch.clone(
            _Cfg(), "NoSuchRepo", ref="master", into=str(tmp_path), runner=runner
        )
    assert "NoSuchRepo" in exc.value.message
    assert "repository not found" in exc.value.message


def test_a_missing_git_binary_is_a_setup_failure_with_a_remedy(tmp_path):
    def missing(*args, **kwargs):
        raise FileNotFoundError("git")

    with pytest.raises(SetupFailure) as exc:
        source_fetch.clone(_Cfg(), "Repo", into=str(tmp_path), runner=missing)
    assert "git was not found" in exc.value.message
    assert exc.value.remedy


def test_an_empty_repository_name_is_rejected_before_invoking_git(tmp_path):
    runner = FakeRunner()
    with pytest.raises(SetupFailure):
        source_fetch.clone(_Cfg(), "", into=str(tmp_path), runner=runner)
    assert runner.calls == [], "nothing should have been invoked"


# -- cleanup ----------------------------------------------------------------


def test_cleanup_removes_the_fetched_tree(tmp_path):
    target = tmp_path / "repo" / "review_agent"
    target.mkdir(parents=True)
    (target / "main.py").write_text("x", encoding="utf-8")
    source_fetch.cleanup(str(tmp_path / "repo"))
    assert not (tmp_path / "repo").exists()


def test_cleanup_of_a_missing_path_is_harmless():
    source_fetch.cleanup(os.path.join("no", "such", "path"))
    source_fetch.cleanup(None)


# --------------------------------------------------------------------------
# T016 (feature 003) - an unset ref means the repository's own default branch.
#
# The previous default was the literal "master". A checklist repository whose
# default is "main" then failed with "could not obtain X at master", which reads
# as a missing repository and sends the reader to the wrong setting entirely.
# --------------------------------------------------------------------------


class BranchAwareRunner(FakeRunner):
    """Answers `rev-parse --abbrev-ref HEAD` with a branch, everything else a sha."""

    def __init__(self, branch="main", **kwargs):
        super().__init__(**kwargs)
        self.branch = branch

    def __call__(self, args, env=None, cwd=None, **kwargs):
        result = super().__call__(args, env=env, cwd=cwd, **kwargs)
        if "--abbrev-ref" in args:
            result.stdout = self.branch
        return result

    @property
    def clone_args(self):
        return next(call["args"] for call in self.calls if "clone" in call["args"])


def test_an_unset_ref_asks_git_for_no_particular_branch(tmp_path):
    runner = BranchAwareRunner()
    source_fetch.clone(_Cfg(), "Checklist", ref=None, into=str(tmp_path), runner=runner)
    assert "--branch" not in runner.clone_args


def test_an_explicit_ref_is_still_passed_through(tmp_path):
    runner = BranchAwareRunner()
    source_fetch.clone(_Cfg(), "Checklist", ref="release", into=str(tmp_path), runner=runner)
    args = runner.clone_args
    assert args[args.index("--branch") + 1] == "release"


def test_the_branch_that_actually_arrived_is_reported(tmp_path):
    """C2.3: "the default branch" is not something an operator can check against."""
    runner = BranchAwareRunner(branch="main")
    cloned = source_fetch.clone(_Cfg(), "Checklist", ref=None, into=str(tmp_path), runner=runner)
    assert cloned.ref == "main"
