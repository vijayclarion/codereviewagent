"""T078-T079 - auth mode selection and retargeting by configuration alone."""

import base64

import pytest
import responses

from review_agent import main as main_module
from review_agent.config import load_config
from review_agent.errors import MissingConfiguration, SetupFailure
from review_agent.tfs_client import TfsClient
from tests.fakes import FakeTfsClient, fake_llm
from tests.fixtures import pr_demo as demo


# -- mode selection ---------------------------------------------------------


def test_pat_only_selects_basic(base_env):
    config = load_config()
    assert config.auth_mode == "basic"
    assert config.tfs_token == "pat-secret-value"


def test_pipeline_token_selects_bearer(base_env, monkeypatch):
    monkeypatch.setenv("SYSTEM_ACCESSTOKEN", "pipeline-token-value")
    config = load_config()
    assert config.auth_mode == "bearer"
    assert config.tfs_token == "pipeline-token-value"


def test_pipeline_token_is_preferred_over_a_pat(base_env, monkeypatch):
    """FR-004: when both are present the automation's own credential wins."""
    monkeypatch.setenv("SYSTEM_ACCESSTOKEN", "pipeline-token-value")
    config = load_config()
    assert config.auth_mode == "bearer"
    assert config.tfs_token != "pat-secret-value"


def test_an_empty_pipeline_token_counts_as_absent(base_env, monkeypatch):
    """A job without the OAuth-token setting exports exactly this."""
    monkeypatch.setenv("SYSTEM_ACCESSTOKEN", "")
    config = load_config()
    assert config.auth_mode == "basic", "must fall back to the PAT, not use an empty Bearer"


def test_a_whitespace_pipeline_token_counts_as_absent(base_env, monkeypatch):
    monkeypatch.setenv("SYSTEM_ACCESSTOKEN", "   ")
    assert load_config().auth_mode == "basic"


def test_no_credential_at_all_is_a_named_setup_failure(base_env, monkeypatch):
    monkeypatch.delenv("TFS_PAT")
    with pytest.raises(MissingConfiguration) as exc:
        load_config()
    problems = " ".join(exc.value.problems)
    assert "SYSTEM_ACCESSTOKEN" in problems
    assert "TFS_PAT" in problems


def test_pipeline_token_makes_a_pat_unnecessary(base_env, monkeypatch):
    monkeypatch.delenv("TFS_PAT")
    monkeypatch.setenv("SYSTEM_ACCESSTOKEN", "pipeline-token-value")
    assert load_config().auth_mode == "bearer"


# -- header construction ----------------------------------------------------


def test_basic_header_is_colon_prefixed_base64():
    class _Cfg:
        auth_mode = "basic"
        tfs_token = "mypat"
        tfs_base_url = "https://x/tfs/C"
        tfs_project = "P"
        tfs_repo = "R"
        tfs_api_version = "6.0"
        api_root = "https://x/tfs/C/P/_apis"

    client = TfsClient(_Cfg())
    expected = base64.b64encode(b":mypat").decode()
    assert client.session.headers["Authorization"] == f"Basic {expected}"


def test_bearer_header_uses_the_token_directly():
    class _Cfg:
        auth_mode = "bearer"
        tfs_token = "oauth-token"
        tfs_base_url = "https://x/tfs/C"
        tfs_project = "P"
        tfs_repo = "R"
        tfs_api_version = "6.0"
        api_root = "https://x/tfs/C/P/_apis"

    client = TfsClient(_Cfg())
    assert client.session.headers["Authorization"] == "Bearer oauth-token"


def test_the_session_identifies_itself():
    class _Cfg:
        auth_mode = "basic"
        tfs_token = "t"
        tfs_base_url = "https://x/tfs/C"
        tfs_project = "P"
        tfs_repo = "R"
        tfs_api_version = "6.0"
        api_root = "https://x/tfs/C/P/_apis"

    client = TfsClient(_Cfg())
    assert "review" in client.session.headers["User-Agent"].lower()


# -- T079: retargeting ------------------------------------------------------


def test_retargeting_needs_only_configuration(base_env, monkeypatch):
    first = load_config()
    monkeypatch.setenv("TFS_PROJECT", "OtherProject")
    monkeypatch.setenv("TFS_REPO", "OtherRepo")
    monkeypatch.setenv("TFS_PR_ID", "4321")
    second = load_config()

    assert (first.tfs_project, first.tfs_repo, first.tfs_pr_id) != (
        second.tfs_project, second.tfs_repo, second.tfs_pr_id
    )
    assert second.api_root.endswith("OtherProject/_apis")


def test_the_same_run_works_against_a_different_pr_via_the_flag(base_env, monkeypatch):
    monkeypatch.setattr(main_module, "TfsClient", lambda config: FakeTfsClient())
    monkeypatch.setattr(main_module, "call_llm", fake_llm(demo.MODEL_RESPONSE))
    assert main_module.main(["--dry-run", "--quiet", "--pr", "9999"]) == 0


def test_provider_swap_needs_only_configuration(base_env, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    assert load_config().llm_provider == "openai"
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    assert load_config().llm_provider == "claude"


# -- error mapping ----------------------------------------------------------


def _live_config(base_env):
    return load_config()


@responses.activate
def test_a_sign_in_page_is_reported_as_authentication_not_json(base_env):
    """The naive symptom is a JSON decode error; the cause is authentication."""
    config = _live_config(base_env)
    responses.add(
        responses.GET,
        f"{config.api_root}/git/repositories/eShop/pullRequests/1234",
        body="<!DOCTYPE html><html><body>Sign In</body></html>",
        status=200,
        content_type="text/html",
    )
    with pytest.raises(SetupFailure) as exc:
        TfsClient(config).get_pull_request()
    assert "authentication failed" in exc.value.message
    assert "sign-in page" in exc.value.message


@responses.activate
def test_a_403_on_a_write_names_the_permission_to_grant(base_env):
    config = _live_config(base_env)
    responses.add(
        responses.POST,
        f"{config.api_root}/git/repositories/eShop/pullRequests/1234/threads",
        status=403,
    )
    with pytest.raises(SetupFailure) as exc:
        TfsClient(config).create_thread("body")
    assert "Contribute to pull requests" in exc.value.remedy


@responses.activate
def test_an_api_version_rejection_names_the_variable(base_env):
    config = _live_config(base_env)
    responses.add(
        responses.GET,
        f"{config.api_root}/git/repositories/eShop/pullRequests/1234",
        json={"message": "The requested api-version is not supported"},
        status=400,
    )
    with pytest.raises(SetupFailure) as exc:
        TfsClient(config).get_pull_request()
    assert "TFS_API_VERSION" in exc.value.remedy


@responses.activate
def test_a_404_names_the_values_to_check(base_env):
    config = _live_config(base_env)
    responses.add(
        responses.GET,
        f"{config.api_root}/git/repositories/eShop/pullRequests/1234",
        status=404,
    )
    with pytest.raises(SetupFailure) as exc:
        TfsClient(config).get_pull_request()
    assert "TFS_REPO" in exc.value.remedy


@responses.activate
def test_a_missing_file_at_the_base_commit_is_not_an_error(base_env):
    """A 404 there means the file was added - diff against empty."""
    config = _live_config(base_env)
    responses.add(
        responses.GET, f"{config.api_root}/git/repositories/eShop/items", status=404
    )
    assert TfsClient(config).get_file_content("/new.cs", "abc") is None


@responses.activate
def test_error_messages_never_include_the_query_string(base_env):
    """A token could ride along in a query parameter."""
    config = _live_config(base_env)
    responses.add(
        responses.GET, f"{config.api_root}/git/repositories/eShop/items", status=500
    )
    with pytest.raises(SetupFailure) as exc:
        TfsClient(config).list_items("/", "master")
    assert "?" not in exc.value.message
    assert "api-version" not in exc.value.message


# --------------------------------------------------------------------------
# Feature 002: two credentials, one purpose each (FR-006, FR-008, research R9).
# --------------------------------------------------------------------------


class _TwoTokenCfg:
    """Minimal config carrying both credentials."""

    auth_mode = "basic"
    tfs_token = "read-token"
    post_token = "post-token"
    tfs_base_url = "https://x/tfs/C"
    tfs_project = "P"
    tfs_repo = "R"
    tfs_api_version = "6.0"
    api_root = "https://x/tfs/C/P/_apis"


def test_a_read_client_reaches_only_the_read_token():
    client = TfsClient(_TwoTokenCfg(), purpose="read")
    assert client.token == "read-token"
    expected = base64.b64encode(b":read-token").decode()
    assert client.session.headers["Authorization"] == f"Basic {expected}"


def test_a_post_client_reaches_only_the_post_token():
    client = TfsClient(_TwoTokenCfg(), purpose="post")
    assert client.token == "post-token"
    expected = base64.b64encode(b":post-token").decode()
    assert client.session.headers["Authorization"] == f"Basic {expected}"


def test_a_post_client_never_sends_a_bearer_token():
    """A pipeline OAuth token is a reading credential; posting is always a PAT."""

    class _Cfg(_TwoTokenCfg):
        auth_mode = "bearer"

    client = TfsClient(_Cfg(), purpose="post")
    assert client.session.headers["Authorization"].startswith("Basic ")
    assert "read-token" not in client.session.headers["Authorization"]


def test_an_unknown_purpose_is_rejected_at_construction():
    with pytest.raises(ValueError, match="purpose"):
        TfsClient(_TwoTokenCfg(), purpose="admin")


def test_the_default_purpose_is_read():
    assert TfsClient(_TwoTokenCfg()).purpose == "read"


def test_a_dry_run_needs_no_posting_credential(base_env, monkeypatch):
    """FR-008: the preview is useful to a developer who cannot post at all."""
    monkeypatch.delenv("TFS_PAT_FOR_PR")
    config = load_config(dry_run_override=True)
    assert config.dry_run is True
    assert config.post_token == ""


def test_a_posting_run_requires_the_posting_credential(base_env, monkeypatch):
    monkeypatch.delenv("TFS_PAT_FOR_PR")
    with pytest.raises(MissingConfiguration) as exc:
        load_config(dry_run_override=False)
    assert "TFS_PAT_FOR_PR" in " ".join(exc.value.problems)


def test_both_credentials_are_registered_for_redaction(base_env):
    from review_agent import config as cfg

    cfg.clear_secrets()
    load_config()
    leaked = cfg.redact("read=pat-secret-value post=post-secret-value")
    assert "pat-secret-value" not in leaked
    assert "post-secret-value" not in leaked


def test_the_posting_token_never_appears_in_a_config_repr(base_env):
    assert "post-secret-value" not in repr(load_config())


# --------------------------------------------------------------------------
# T035 (feature 003) - a refused WORK-ITEM read is its own condition.
#
# Classified in the client because it is the only module that knows which
# endpoint answered. Catching plain SetupFailure in the caller would also swallow
# a collection that is down, which needs a different correction entirely.
# --------------------------------------------------------------------------

from review_agent.errors import WorkItemAccessDenied


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_work_item_read_is_its_own_error(base_env, status):
    import responses

    config = load_config(dry_run_override=True)
    client = TfsClient(config)
    with responses.RequestsMock() as mocked:
        mocked.add(
            responses.GET,
            f"{config.api_root}/wit/workitems/101",
            status=status,
            json={"message": "denied"},
        )
        with pytest.raises(WorkItemAccessDenied) as exc:
            client.get_work_item(101)
    assert "Work Items (read)" in exc.value.describe()


def test_the_same_status_from_the_pull_request_is_not_a_work_item_problem(base_env):
    """A credential with no Code access is a different fix, and must read as one."""
    import responses

    config = load_config(dry_run_override=True)
    client = TfsClient(config)
    with responses.RequestsMock() as mocked:
        mocked.add(
            responses.GET,
            f"{config.api_root}/git/repositories/eShop/pullRequests/1234",
            status=401,
            json={"message": "denied"},
        )
        with pytest.raises(SetupFailure) as exc:
            client.get_pull_request()
    assert not isinstance(exc.value, WorkItemAccessDenied)
