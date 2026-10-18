"""T024 (feature 007) - cloning from GitHub without leaking the credential.

The same negative assertions as tests/unit/test_source_fetch.py, for the GitHub
URL and header form. That file is untouched and still asserts the TFS form.
"""

import base64

import pytest

from review_agent import source_fetch
from review_agent.config import redact
from tests.unit.test_source_fetch import FakeRunner


class _GhCfg:
    platform = "github"
    gh_web_url = "https://github.com"
    gh_token = "gh-read-secret-value"
    gh_checklist_token = "gh-checklist-secret-value"
    checklist_repo = "acme/checklists"


class _GheCfg(_GhCfg):
    gh_web_url = "https://ghe.example"


def _clone(cfg, repo, tmp_path):
    runner = FakeRunner()
    source = source_fetch.clone(cfg, repo, ref="master", into=str(tmp_path), runner=runner)
    return source, runner


def _clone_call(runner):
    return next(c for c in runner.calls if "clone" in c["args"])


def test_clone_url_carries_only_the_non_secret_username():
    assert (
        source_fetch.clone_url(_GhCfg(), "acme/agent")
        == "https://x-access-token@github.com/acme/agent.git"
    )
    assert source_fetch.public_url(_GhCfg(), "acme/agent") == "https://github.com/acme/agent.git"
    assert (
        source_fetch.clone_url(_GheCfg(), "acme/agent")
        == "https://x-access-token@ghe.example/acme/agent.git"
    )


def test_header_uses_the_github_username_and_is_registered(tmp_path):
    _, runner = _clone(_GhCfg(), "acme/agent", tmp_path)
    env = _clone_call(runner)["env"]
    encoded = base64.b64encode(b"x-access-token:gh-read-secret-value").decode("ascii")
    assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert env["GIT_CONFIG_VALUE_0"] == f"Authorization: Basic {encoded}"
    assert redact(encoded) == "***"
    assert redact(env["GIT_CONFIG_VALUE_0"]) == "***"


def test_the_token_is_never_in_argv(tmp_path):
    _, runner = _clone(_GhCfg(), "acme/agent", tmp_path)
    joined = " ".join(runner.all_args)
    assert "gh-read-secret-value" not in joined
    assert "x-access-token:" not in joined


def test_the_checklist_repository_uses_its_own_token(tmp_path):
    _, runner = _clone(_GhCfg(), "acme/checklists", tmp_path)
    assert _clone_call(runner)["env"][source_fetch.TOKEN_ENV] == "gh-checklist-secret-value"
    other = tmp_path / "other"
    other.mkdir()
    _, runner = _clone(_GhCfg(), "acme/agent", other)
    assert _clone_call(runner)["env"][source_fetch.TOKEN_ENV] == "gh-read-secret-value"


def test_clone_lands_at_the_same_depth_as_tfs(tmp_path):
    source, _ = _clone(_GhCfg(), "acme/agent", tmp_path)
    assert source.path == str(tmp_path / "agent")


def test_origin_is_left_credential_free(tmp_path):
    _, runner = _clone(_GhCfg(), "acme/agent", tmp_path)
    set_url = next(c for c in runner.calls if "set-url" in c["args"])
    assert set_url["args"][-1] == "https://github.com/acme/agent.git"


@pytest.mark.parametrize(
    "name", ["GH_TOKEN", "GH_TOKEN_FOR_PR", "GH_CHECKLIST_TOKEN", "GITHUB_TOKEN", "GIT_REPO_TOKEN"]
)
def test_git_children_never_inherit_a_github_token_variable(tmp_path, monkeypatch, name):
    monkeypatch.setenv(name, "inherited-secret-value")
    _, runner = _clone(_GhCfg(), "acme/agent", tmp_path)
    assert name not in _clone_call(runner)["env"]


def test_tfs_form_is_unchanged():
    class _Tfs:
        tfs_base_url = "https://tfs.example.com/tfs/Coll"
        tfs_project = "Proj"
        tfs_token = "pat-secret-value"

    assert source_fetch.clone_url(_Tfs(), "Repo") == "https://pat@tfs.example.com/tfs/Coll/Proj/_git/Repo"
    assert source_fetch.default_token(_Tfs(), "Repo") == "pat-secret-value"
