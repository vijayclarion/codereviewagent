"""T019 - configuration loading, precedence, and validation."""

import pytest

from review_agent import config as cfg
from review_agent.errors import MissingConfiguration


def test_loads_minimum_valid_config(base_env):
    c = cfg.load_config()
    assert c.tfs_project == "Proj"
    assert c.tfs_pr_id == 1234
    assert c.auth_mode == "basic"
    assert c.tfs_api_version == "6.0"
    assert c.dry_run is True, "preview must be the default"
    assert c.fail_on_contradiction is False, "non-blocking must be the default"


def test_reports_every_missing_value_at_once(monkeypatch):
    monkeypatch.setenv("TFS_BASE_URL", "https://tfs.example.com/tfs/Coll")
    with pytest.raises(MissingConfiguration) as exc:
        cfg.load_config()
    problems = " ".join(exc.value.problems)
    for expected in ("TFS_PROJECT", "TFS_REPO", "TFS_PR_ID", "LLM_PROVIDER", "LLM_MODEL"):
        assert expected in problems
    assert "no usable credential" in problems


def test_pipeline_variables_take_precedence(base_env, monkeypatch):
    monkeypatch.delenv("TFS_PROJECT")
    monkeypatch.delenv("TFS_REPO")
    monkeypatch.delenv("TFS_PR_ID")
    monkeypatch.setenv("SYSTEM_TEAMPROJECT", "PipelineProject")
    monkeypatch.setenv("BUILD_REPOSITORY_NAME", "PipelineRepo")
    monkeypatch.setenv("SYSTEM_PULLREQUEST_PULLREQUESTID", "99")
    c = cfg.load_config()
    assert (c.tfs_project, c.tfs_repo, c.tfs_pr_id) == ("PipelineProject", "PipelineRepo", 99)


@pytest.mark.parametrize(
    "raw,expected",
    [("true", True), ("TRUE", True), ("1", True), ("yes", True), ("on", True),
     ("false", False), ("0", False), ("no", False), ("off", False)],
)
def test_boolean_parsing(base_env, monkeypatch, raw, expected):
    monkeypatch.setenv("DRY_RUN", raw)
    assert cfg.load_config().dry_run is expected


def test_invalid_boolean_is_a_named_error_not_a_silent_false(base_env, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "maybe")
    with pytest.raises(MissingConfiguration) as exc:
        cfg.load_config()
    assert "DRY_RUN" in " ".join(exc.value.problems)


def test_invalid_integer_is_reported(base_env, monkeypatch):
    monkeypatch.setenv("REVIEW_MAX_FILES", "lots")
    with pytest.raises(MissingConfiguration) as exc:
        cfg.load_config()
    assert "REVIEW_MAX_FILES" in " ".join(exc.value.problems)


def test_pr_id_must_be_positive(base_env, monkeypatch):
    monkeypatch.setenv("TFS_PR_ID", "0")
    with pytest.raises(MissingConfiguration):
        cfg.load_config()


def test_ollama_needs_no_api_key(base_env, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LLM_API_KEY")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434")
    assert cfg.load_config().llm_api_key == ""


def test_azure_requires_base_url(base_env, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    with pytest.raises(MissingConfiguration) as exc:
        cfg.load_config()
    assert "LLM_BASE_URL" in " ".join(exc.value.problems)


def test_unknown_provider_is_rejected(base_env, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gpt-9")
    with pytest.raises(MissingConfiguration) as exc:
        cfg.load_config()
    assert "LLM_PROVIDER" in " ".join(exc.value.problems)


def test_checklist_repo_derived_from_url(base_env):
    assert cfg.load_config().checklist_repo == "TestMarkDown"


def test_explicit_checklist_repo_overrides_derivation(base_env, monkeypatch):
    monkeypatch.setenv("CHECKLIST_REPO", "OtherRepo")
    assert cfg.load_config().checklist_repo == "OtherRepo"


def test_exclude_mode_extend_keeps_defaults(base_env, monkeypatch):
    monkeypatch.setenv("REVIEW_EXCLUDE_PATTERNS", "*.custom")
    patterns = cfg.load_config().review_exclude_patterns
    assert "*.custom" in patterns
    assert ".env" in patterns


def test_exclude_mode_replace_discards_defaults(base_env, monkeypatch):
    monkeypatch.setenv("REVIEW_EXCLUDE_PATTERNS", "*.custom")
    monkeypatch.setenv("REVIEW_EXCLUDE_MODE", "replace")
    patterns = cfg.load_config().review_exclude_patterns
    assert patterns == ("*.custom",)


def test_trailing_slash_stripped_from_base_url(base_env, monkeypatch):
    monkeypatch.setenv("TFS_BASE_URL", "https://tfs.example.com/tfs/Coll/")
    c = cfg.load_config()
    assert c.tfs_base_url.endswith("Coll")
    assert c.api_root == "https://tfs.example.com/tfs/Coll/Proj/_apis"


def test_repr_never_shows_secrets(base_env):
    text = repr(cfg.load_config())
    assert "pat-secret-value" not in text
    assert "llm-secret-value" not in text
    assert "***" in text


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://h/tfs/C/P/_git/TestMarkDown", "TestMarkDown"),
        ("https://h/tfs/C/P/_git/Repo.With.Dots", "Repo.With.Dots"),
        ("https://h/tfs/C/P/nothing", None),
        ("", None),
    ],
)
def test_derive_repo_name(url, expected):
    assert cfg.derive_repo_name(url) == expected


# --------------------------------------------------------------------------
# T012 / T066 (feature 003) - the checklist repository's four names.
#
# One trailing character in `config.py` is the whole reason no checklist has
# ever been applied on this machine. These pin the resolution order, and pin
# that no existing configuration has to be renamed to get a checklist review.
# --------------------------------------------------------------------------


def test_the_operators_spelling_is_canonical(base_env, monkeypatch):
    """The name the provisioned .env actually carries - no trailing T."""
    monkeypatch.setenv("TFS_REPO_CODE_REVIEW_CodeReviewChecklist", "RealChecklist")
    config = cfg.load_config()
    assert config.checklist_repo == "RealChecklist"
    assert config.checklist_setting == "TFS_REPO_CODE_REVIEW_CodeReviewChecklist"


def test_the_canonical_name_wins_over_every_legacy_name(base_env, monkeypatch):
    monkeypatch.setenv("TFS_REPO_CODE_REVIEW_CodeReviewChecklist", "Canonical")
    monkeypatch.setenv("TFS_REPO_CODE_REVIEW_CodeReviewChecklistT", "BriefTypo")
    monkeypatch.setenv("CHECKLIST_REPO", "Older")
    assert cfg.load_config().checklist_repo == "Canonical"


@pytest.mark.parametrize(
    "name, expected_setting",
    [
        ("TFS_REPO_CODE_REVIEW_CodeReviewChecklistT", "TFS_REPO_CODE_REVIEW_CodeReviewChecklistT"),
        ("CHECKLIST_REPO", "CHECKLIST_REPO"),
    ],
)
def test_every_legacy_name_still_resolves(base_env, monkeypatch, name, expected_setting):
    """FR-001: a working configuration must not have to be renamed."""
    monkeypatch.setenv(name, "LegacyNamed")
    config = cfg.load_config()
    assert config.checklist_repo == "LegacyNamed"
    assert config.checklist_setting == expected_setting


def test_the_url_derivation_records_itself_as_the_source(base_env):
    """base_env supplies only CHECKLIST_REPO_URL, which is the fourth name."""
    config = cfg.load_config()
    assert config.checklist_repo == "TestMarkDown"
    assert config.checklist_setting == "CHECKLIST_REPO_URL"


def test_no_checklist_setting_leaves_both_empty(base_env, monkeypatch):
    monkeypatch.delenv("CHECKLIST_REPO_URL", raising=False)
    config = cfg.load_config()
    assert config.checklist_repo == ""
    assert config.checklist_setting == ""


def test_both_document_formats_are_matched_by_default(base_env):
    patterns = cfg.split_patterns(cfg.load_config().checklist_file_pattern)
    assert "*.xlsx" in patterns
    assert "*.docx" in patterns
    # Markdown is not in the default: it yields no citable rule identifier, and
    # FR-017 requires every violation to cite one. The plain-text path is still
    # reachable by setting the pattern - see test_a_single_pattern_still_works.
    assert "*.md" not in patterns


def test_the_pattern_list_is_operator_adjustable(base_env, monkeypatch):
    monkeypatch.setenv("CHECKLIST_FILE_PATTERN", "*.xlsx, *.rst")
    patterns = cfg.split_patterns(cfg.load_config().checklist_file_pattern)
    assert patterns == ("*.xlsx", "*.rst")


def test_a_single_pattern_still_works(base_env, monkeypatch):
    """Every value anyone can currently have set stays valid."""
    monkeypatch.setenv("CHECKLIST_FILE_PATTERN", "*.md")
    assert cfg.split_patterns(cfg.load_config().checklist_file_pattern) == ("*.md",)


def test_an_unset_branch_means_the_repositorys_own_default(base_env, monkeypatch):
    monkeypatch.delenv("CHECKLIST_BRANCH", raising=False)
    assert cfg.load_config().checklist_branch == ""


def test_checklist_documents_are_never_reviewed_as_code(base_env):
    """FR-018: the standard is what a review measures against, not what it reviews."""
    patterns = cfg.load_config().review_exclude_patterns
    assert "*.xlsx" in patterns
    assert "*.docx" in patterns


# --------------------------------------------------------------------------
# T027 (feature 006) - the prompt/response log settings.
# --------------------------------------------------------------------------


def test_logging_is_off_unless_asked_for(base_env):
    """FR-002. The prompt carries the pull request's whole diff."""
    assert cfg.load_config().llm_log is False


def test_the_flag_turns_logging_on_without_touching_the_environment(base_env):
    assert cfg.load_config(llm_log_override=True).llm_log is True


def test_the_environment_variable_turns_logging_on(base_env, monkeypatch):
    monkeypatch.setenv("LLM_LOG", "true")
    assert cfg.load_config().llm_log is True


def test_a_relative_destination_is_stored_absolute(base_env, monkeypatch, tmp_path):
    """FR-003a. Resolved here, in the process the operator launched - the child
    that performs the review runs inside a clone that is deleted afterwards."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_LOG_DIR", "my-logs")
    config = cfg.load_config()

    assert cfg.os.path.isabs(config.llm_log_dir)
    assert config.llm_log_dir == str(tmp_path / "my-logs")


def test_the_default_destination_is_resolved_too(base_env, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = cfg.load_config()

    assert config.llm_log_dir == str(tmp_path / ".llm-logs")


def test_an_absolute_destination_is_left_alone(base_env, monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_LOG_DIR", str(tmp_path / "elsewhere"))
    assert cfg.load_config().llm_log_dir == str(tmp_path / "elsewhere")


def test_retention_defaults_to_ten_runs(base_env):
    assert cfg.load_config().llm_log_keep == 10


def test_retention_below_one_is_refused(base_env, monkeypatch):
    """Keeping zero logs would delete the log of the run doing the deleting."""
    monkeypatch.setenv("LLM_LOG_KEEP", "0")
    with pytest.raises(MissingConfiguration) as exc:
        cfg.load_config()
    assert "LLM_LOG_KEEP" in str(exc.value)


def test_a_bad_retention_value_is_reported_even_when_logging_is_off(
    base_env, monkeypatch
):
    """A configuration error that only surfaces the day you first need the
    feature is a configuration error found at the worst possible moment."""
    monkeypatch.setenv("LLM_LOG_KEEP", "ten")
    with pytest.raises(MissingConfiguration) as exc:
        cfg.load_config()
    assert "LLM_LOG_KEEP" in str(exc.value)


def test_the_log_settings_are_not_secrets(base_env, monkeypatch, tmp_path):
    """They belong in output: a path nobody can see is a file nobody can find."""
    monkeypatch.setenv("LLM_LOG_DIR", str(tmp_path / "visible"))
    config = cfg.load_config()

    assert "visible" in repr(config)
    for name in cfg.Config.SECRET_FIELDS:
        assert not name.startswith("llm_log")
