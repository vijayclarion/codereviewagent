"""T030 - fetch-and-execute, the recursion guard, and --local (FR-012, R2).

The property worth protecting: a review must never be produced by a copy of the
logic nobody can identify. Either the fetched commit ran, or the working copy
ran and said so - and a failed fetch must not quietly become the second one.
"""

import pytest

from review_agent import bootstrap
from review_agent.errors import EXIT_SETUP_FAILURE, SetupFailure
from review_agent.source_fetch import ClonedSource


class FakeChild:
    """Stands in for the re-executed review."""

    def __init__(self, returncode=0):
        self.returncode = returncode
        self.calls = []

    def __call__(self, args, cwd=None, env=None, **kwargs):
        self.calls.append({"args": list(args), "cwd": cwd, "env": dict(env or {})})

        class _Result:
            pass

        result = _Result()
        result.returncode = self.returncode
        return result


@pytest.fixture
def cloned(tmp_path):
    path = tmp_path / "CodeReviewAgent"
    path.mkdir()
    return ClonedSource(repo="CodeReviewAgent", ref="master", path=str(path), commit="a1b2c3d")


# -- the default path: fetch, then run the fetched copy ---------------------


def test_the_fetched_copy_is_what_executes(base_env, cloned):
    child = FakeChild()
    code = bootstrap.main(["--pr", "42"], runner=child, fetcher=lambda *a, **k: cloned)
    assert code == 0
    assert child.calls, "the review must have been re-executed"
    args = child.calls[0]["args"]
    assert args[1:3] == ["-m", "review_agent.run"], (
        "the child must be the reviewing entry point, not the bootstrap again"
    )
    assert "--pr" in args and "42" in args, "arguments must reach the child"


def test_the_child_is_told_which_commit_it_is(base_env, cloned):
    child = FakeChild()
    bootstrap.main(["--pr", "42"], runner=child, fetcher=lambda *a, **k: cloned)
    env = child.calls[0]["env"]
    assert env[bootstrap.MARKER_ENV] == "a1b2c3d"
    assert env[bootstrap.MARKER_REPO_ENV] == "CodeReviewAgent"
    assert env[bootstrap.MARKER_REF_ENV] == "master"


def test_the_fetched_tree_wins_on_the_import_path(base_env, cloned, tmp_path):
    child = FakeChild()
    bootstrap.main(["--pr", "42"], runner=child, fetcher=lambda *a, **k: cloned)
    env = child.calls[0]["env"]
    assert env["PYTHONPATH"].split(";")[0].replace("\\", "/") == str(tmp_path).replace("\\", "/")


def test_the_child_exit_code_is_the_run_exit_code(base_env, cloned):
    assert (
        bootstrap.main(["--pr", "1"], runner=FakeChild(returncode=2), fetcher=lambda *a, **k: cloned)
        == 2
    )


def test_the_fetched_tree_is_cleaned_up(base_env, cloned, monkeypatch):
    removed = []
    monkeypatch.setattr(bootstrap.source_fetch, "cleanup", removed.append)
    bootstrap.main(["--pr", "1"], runner=FakeChild(), fetcher=lambda *a, **k: cloned)
    assert removed == [cloned.path]


# -- the recursion guard ----------------------------------------------------


def test_a_bootstrapped_child_reviews_instead_of_fetching_again(base_env, monkeypatch):
    monkeypatch.setenv(bootstrap.MARKER_ENV, "a1b2c3d")
    monkeypatch.setenv(bootstrap.MARKER_REPO_ENV, "CodeReviewAgent")
    monkeypatch.setenv(bootstrap.MARKER_REF_ENV, "master")
    seen = {}

    def fake_run(argv, agent_source=None):
        seen["source"] = agent_source
        return 0

    monkeypatch.setattr(bootstrap, "source_fetch", bootstrap.source_fetch)
    from review_agent import run as run_module

    monkeypatch.setattr(run_module, "main", fake_run)

    def explode(*args, **kwargs):
        raise AssertionError("a bootstrapped child must never fetch again")

    assert bootstrap.main(["--pr", "1"], fetcher=explode) == 0
    assert seen["source"].mode == "fetched"
    assert seen["source"].commit == "a1b2c3d"


def test_the_marker_describes_the_provenance(monkeypatch):
    monkeypatch.setenv(bootstrap.MARKER_ENV, "a1b2c3d")
    monkeypatch.setenv(bootstrap.MARKER_REPO_ENV, "CodeReviewAgent")
    monkeypatch.setenv(bootstrap.MARKER_REF_ENV, "master")
    assert bootstrap.source_from_marker().description == (
        "fetched a1b2c3d (CodeReviewAgent@master)"
    )


# -- --local ----------------------------------------------------------------


def test_local_skips_the_fetch_entirely(base_env, monkeypatch, capsys):
    seen = {}

    def fake_run(argv, agent_source=None):
        seen["source"] = agent_source
        return 0

    from review_agent import run as run_module

    monkeypatch.setattr(run_module, "main", fake_run)

    def explode(*args, **kwargs):
        raise AssertionError("--local must not fetch")

    assert bootstrap.main(["--pr", "1", "--local"], fetcher=explode) == 0
    assert seen["source"].mode == "local"
    assert "LOCAL WORKING COPY" in capsys.readouterr().out, (
        "a review from an uncommitted copy must say so before it reviews"
    )


# -- failure --------------------------------------------------------------


def test_a_failed_fetch_never_falls_back_to_the_local_copy(base_env, monkeypatch, capsys):
    from review_agent import run as run_module

    monkeypatch.setattr(
        run_module,
        "main",
        lambda *a, **k: pytest.fail("a failed fetch must not review with the local copy"),
    )

    def failing(*args, **kwargs):
        raise SetupFailure("repository not found", remedy="check the name")

    code = bootstrap.main(["--pr", "1"], fetcher=failing)
    assert code == EXIT_SETUP_FAILURE
    assert "could not be obtained" in capsys.readouterr().err


def test_a_missing_agent_repository_name_is_reported_before_fetching(monkeypatch, capsys):
    for key in ("TFS_BASE_URL", "TFS_PROJECT", "TFS_REPO", "TFS_PAT", "TFS_PR_ID"):
        monkeypatch.delenv(key, raising=False)
    code = bootstrap.main(["--pr", "1"], fetcher=lambda *a, **k: pytest.fail("no fetch"))
    assert code == EXIT_SETUP_FAILURE
    assert "setup failure" in capsys.readouterr().err


# --------------------------------------------------------------------------
# T022 (feature 006) - the log destination travels to the child, resolved.
#
# The child's working directory is inside the fetched clone, which this module
# deletes when the run ends. A relative path resolved at the far end therefore
# writes the log into a directory that no longer exists - and reports nothing,
# because failing to log must never fail a review. That combination is silent
# by construction, so it gets a test rather than a comment.
# --------------------------------------------------------------------------


def test_the_child_is_given_an_absolute_log_destination(base_env, monkeypatch, tmp_path):
    import os

    monkeypatch.setenv("LLM_LOG", "true")
    monkeypatch.setenv("LLM_LOG_DIR", ".llm-logs")
    monkeypatch.chdir(tmp_path)

    child = FakeChild()
    cloned = ClonedSource(
        path=str(tmp_path / "clone" / "review_agent"),
        repo="CodeReviewAgent",
        ref="master",
        commit="a1b2c3d",
    )
    bootstrap.main(["--pr", "1"], runner=child, fetcher=lambda *a, **k: cloned)

    env = child.calls[0]["env"]
    assert env["LLM_LOG"] == "true"
    assert os.path.isabs(env["LLM_LOG_DIR"])
    assert env["LLM_LOG_DIR"] == str(tmp_path / ".llm-logs")
    # And it is emphatically not resolved against where the child will run.
    assert not env["LLM_LOG_DIR"].startswith(child.calls[0]["cwd"])


def test_logging_left_off_still_reaches_the_child_explicitly(base_env, monkeypatch, tmp_path):
    """The child cannot find the operator's .env from a temp clone, so "off"
    has to travel too rather than being inferred from an absent variable."""
    monkeypatch.chdir(tmp_path)
    child = FakeChild()
    cloned = ClonedSource(
        path=str(tmp_path / "clone" / "review_agent"),
        repo="CodeReviewAgent",
        ref="master",
        commit="a1b2c3d",
    )
    bootstrap.main(["--pr", "1"], runner=child, fetcher=lambda *a, **k: cloned)

    assert child.calls[0]["env"]["LLM_LOG"] == "false"
