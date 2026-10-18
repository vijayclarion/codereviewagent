"""Shared test fixtures.

No test in this suite touches the network. TFS and AI-provider HTTP surfaces are
faked with `responses`; everything else runs against recorded fixtures under
`tests/fixtures/`.
"""

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Make `review_agent` importable without installing the package.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Every test starts from a clean environment.

    Without this, a developer's real .env or an inherited SYSTEM_ACCESSTOKEN
    would change what the tests actually exercise - and the auth-mode tests
    would pass or fail depending on whose machine they ran on.
    """
    for key in list(os.environ):
        if key.startswith(
            ("TFS_", "LLM_", "CHECKLIST_", "REVIEW_", "SYSTEM_", "DRY_RUN", "FAIL_ON_")
        ):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("REVIEW_AGENT_SKIP_DOTENV", "1")


@pytest.fixture(autouse=True)
def _no_clone_in_tests(monkeypatch):
    """Nothing in this suite may reach a remote repository.

    Feature 003 wires a checklist working copy into every review, and `base_env`
    names a checklist repository - so without this fixture the whole suite would
    start shelling out to the network on a machine that may have neither
    credentials nor connectivity. A test that wants a corpus asks for the
    `cloned_checklist` fixture, which serves one from a temp directory.
    """
    from review_agent import checklist
    from review_agent.errors import SetupFailure

    def _refuse(*args, **kwargs):
        raise SetupFailure("no working copy was obtained (tests never reach a remote)")

    monkeypatch.setattr(checklist, "_fetch", _refuse)


class ServedCopy:
    """What the fake acquisition hands back, plus what the run did with it."""

    def __init__(self, root):
        self.root = root
        self.cleaned = []
        self.requested_refs = []


@pytest.fixture
def checklist_working_copy(tmp_path, monkeypatch):
    """Serve a checklist repository from a temp directory instead of a remote.

    The opt-in counterpart to `_no_clone_in_tests`: a test that wants a corpus
    says so, and gets one without a network, a credential, or a git binary.
    """

    def _serve(files, ref="master", commit="c0ffee1"):
        from review_agent import checklist, source_fetch

        root = tmp_path / "CodeReviewChecklist"
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))

        served = ServedCopy(root)

        class _Copy:
            repo = "CodeReviewChecklist"
            path = str(root)

        copy = _Copy()
        copy.ref = ref
        copy.commit = commit

        def _fetch(config, repo, ref=None):
            served.requested_refs.append(ref)
            return copy

        monkeypatch.setattr(checklist, "_fetch", _fetch)
        # The real one removes the parent directory, which here is the test's
        # own tmp_path. Record the request instead, so FR-005 stays assertable.
        monkeypatch.setattr(source_fetch, "cleanup", served.cleaned.append)
        return served

    return _serve


@pytest.fixture
def base_env(monkeypatch):
    """The minimum valid configuration, manual-run flavour."""
    values = {
        "TFS_BASE_URL": "https://tfs.example.com/tfs/Coll",
        "TFS_PROJECT": "Proj",
        "TFS_REPO": "eShop",
        "TFS_PR_ID": "1234",
        "TFS_PAT": "pat-secret-value",
        "LLM_PROVIDER": "claude",
        "LLM_MODEL": "claude-sonnet-5",
        "LLM_API_KEY": "llm-secret-value",
        "CHECKLIST_REPO_URL": "https://tfs.example.com/tfs/Coll/Proj/_git/TestMarkDown",
        "CHECKLIST_BRANCH": "master",
        # Feature 002: the review logic is fetched from its own repository on
        # every run (FR-012), so naming that repository is now part of a minimum
        # valid configuration.
        "TFS_REPO_CODE_REVIEW_CodeReviewAgent": "CodeReviewAgent",
        # The posting credential, separate from the reading one (FR-006). It is
        # present here so that posting tests work; that a DRY RUN does not need
        # it (FR-008) is asserted explicitly in tests/unit/test_auth_modes.py
        # rather than left implicit in every other test.
        "TFS_PAT_FOR_PR": "post-secret-value",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def load_fixture(*parts):
    """Read a JSON fixture from tests/fixtures/."""
    path = FIXTURES.joinpath(*parts)
    return json.loads(path.read_text(encoding="utf-8"))


def read_fixture_text(*parts):
    return FIXTURES.joinpath(*parts).read_text(encoding="utf-8")
