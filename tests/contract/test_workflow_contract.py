"""T062 (feature 007) - the workflow invariants of contracts/workflow.md.

Parsed, not grepped, so a comment mentioning a forbidden trigger cannot fail the
test and a quoted one cannot pass it. PyYAML is a test-only dependency
(requirements-dev.txt).
"""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
REUSABLE = ROOT / ".github" / "workflows" / "code-review.yml"
CALLER = ROOT / "specs" / "007-github-and-cross-file" / "sample-repo" / ".github" / "workflows" / "ai-review.yml"


def _load(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    # YAML 1.1 reads the key `on` as the boolean True.
    if True in data:
        data["on"] = data.pop(True)
    return data


@pytest.fixture(scope="module")
def reusable():
    return _load(REUSABLE)


@pytest.fixture(scope="module")
def caller():
    return _load(CALLER)


def _all_workflows():
    return sorted(ROOT.joinpath(".github").rglob("*.yml")) + sorted(CALLER.parent.rglob("*.yml"))


# 1
def test_no_workflow_uses_pull_request_target():
    for path in _all_workflows():
        triggers = _load(path)["on"]
        names = triggers if isinstance(triggers, (list, str)) else list(triggers)
        assert "pull_request_target" not in names, f"{path.name} runs fork code with secrets"


# 2
def test_reusable_trigger_and_safe_defaults(reusable):
    assert list(reusable["on"]) == ["workflow_call"]
    inputs = reusable["on"]["workflow_call"]["inputs"]
    assert inputs["dry_run"]["default"] is True
    assert inputs["llm_log"]["default"] is False
    assert inputs["fail_on_contradiction"]["default"] is False
    for name in ("model", "story_source", "checklist_repo", "dry_run", "llm_log", "fail_on_contradiction"):
        assert name in inputs
    secrets = reusable["on"]["workflow_call"]["secrets"]
    assert secrets["llm_api_key"]["required"] is True
    assert secrets["review_bot_token"]["required"] is False


# 3
LEAST_PRIVILEGE = {"contents": "read", "pull-requests": "write", "issues": "write"}


def test_permissions_are_exactly_least_privilege(reusable, caller):
    assert reusable["jobs"]["review"]["permissions"] == LEAST_PRIVILEGE
    assert caller["permissions"] == LEAST_PRIVILEGE
    assert reusable["jobs"]["skipped"]["permissions"] == {}


# 4
def test_drafts_and_forks_are_skipped_with_a_stated_reason(reusable):
    review_if = reusable["jobs"]["review"]["if"]
    assert "draft == false" in review_if and "head.repo.full_name == github.repository" in review_if
    skipped = reusable["jobs"]["skipped"]
    assert "draft == true" in skipped["if"] and "!= github.repository" in skipped["if"]
    script = " ".join(step.get("run", "") for step in skipped["steps"])
    assert "draft" in script and "fork" in script


# 5
def test_a_newer_commit_cancels_the_older_review(reusable):
    concurrency = reusable["jobs"]["review"]["concurrency"]
    assert concurrency["cancel-in-progress"] is True
    assert "github.event.pull_request.number" in concurrency["group"]


# 6
def test_the_log_is_uploaded_only_when_asked_and_briefly(reusable):
    upload = next(s for s in reusable["jobs"]["review"]["steps"] if "upload-artifact" in s.get("uses", ""))
    assert "inputs.llm_log" in upload["if"]
    assert upload["with"]["retention-days"] <= 7


# 7
def test_secrets_reach_the_agent_only_through_env(reusable):
    for job in reusable["jobs"].values():
        for step in job["steps"]:
            assert "secrets." not in step.get("run", ""), f"secret in a script body: {step.get('name')}"
    review = next(s for s in reusable["jobs"]["review"]["steps"] if s.get("name") == "Review the pull request")
    assert review["env"]["LLM_API_KEY"] == "${{ secrets.llm_api_key }}"
    assert review["env"]["GH_TOKEN"] == "${{ github.token }}"


def test_the_review_step_does_not_mask_the_exit_code(reusable):
    review = next(s for s in reusable["jobs"]["review"]["steps"] if s.get("name") == "Review the pull request")
    assert not review.get("continue-on-error")
    assert re.search(r"\|\|\s*true|;\s*exit\s+0|set\s+\+e", review["run"]) is None
    assert review["run"].strip() == "python -m review_agent --local"


def test_checkout_persists_no_credential(reusable):
    checkout = next(s for s in reusable["jobs"]["review"]["steps"] if "actions/checkout" in s.get("uses", ""))
    assert checkout["with"]["persist-credentials"] is False


# 8
def test_the_caller_is_short_and_calls_the_central_workflow(caller):
    lines = [line for line in CALLER.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) <= 20, f"onboarding must stay ~15-20 lines, found {len(lines)}"
    job = caller["jobs"]["review"]
    assert job["uses"].startswith("vijayclarion/codereviewagent/.github/workflows/code-review.yml@")
    assert set(caller["on"]["pull_request"]["types"]) == {"opened", "synchronize", "reopened", "ready_for_review"}
    assert set(job["secrets"]) == {"llm_api_key", "review_bot_token"}


def test_caller_ref_and_agent_ref_agree(caller):
    job = caller["jobs"]["review"]
    pinned = job["uses"].rsplit("@", 1)[1]
    assert job["with"].get("agent_ref", "master") == pinned
