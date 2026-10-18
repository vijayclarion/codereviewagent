"""T023 / T090 - the two replaceability boundaries, and config containment.

plan.md promises that swapping the hosting platform touches only `tfs_client.py`
and swapping the AI provider touches only `llm_adapter.py` (FR-032, FR-033), and
that no value is hard-coded because everything flows through `config.py`
(FR-001). Those promises are worth exactly as much as this test.
"""

import ast
import re
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[2] / "review_agent"

MAY_IMPORT_REQUESTS = {"tfs_client.py", "llm_adapter.py", "github_client.py"}  # 007: GitHub
MAY_READ_ENVIRONMENT = {"config.py", "main.py"}  # main.py only for its sys.path bootstrap


def _sources():
    return sorted(p for p in AGENT_DIR.rglob("*.py"))


def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_only_the_boundary_modules_import_requests():
    offenders = [
        p.name
        for p in _sources()
        if "requests" in _imported_modules(p) and p.name not in MAY_IMPORT_REQUESTS
    ]
    assert not offenders, (
        "requests imported outside the TFS/provider boundary: " + ", ".join(offenders)
    )


def test_provider_wire_format_stays_in_the_adapter():
    """Provider-specific response paths must not leak into parsing or output."""
    markers = ("choices", "content[0]", "message.content", "anthropic", "x-api-key")
    offenders = []
    for path in _sources():
        if path.name in ("llm_adapter.py", "config.py"):
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker in text:
                offenders.append(f"{path.name}:{marker}")
    assert not offenders, "provider wire format leaked: " + ", ".join(offenders)


def test_environment_is_read_only_in_config():
    offenders = []
    for path in _sources():
        if path.name in MAY_READ_ENVIRONMENT:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"os\.environ|os\.getenv|getenv\(", text):
            offenders.append(path.name)
    assert not offenders, (
        "environment read outside config.py: " + ", ".join(offenders)
    )


def test_no_hard_coded_collection_urls_or_models():
    """FR-001: no runtime value baked into the deliverable."""
    suspicious = re.compile(
        r"https://(?!json-schema\.org|najm\.sa/schemas)[a-z0-9.\-]*devops[a-z0-9.\-]*"
        r"|claude-[a-z0-9\-]*\d"
        r"|gpt-[0-9]"
        r"|Najm-Architecture-Unit",
        re.IGNORECASE,
    )
    offenders = []
    for path in _sources():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().startswith("#"):
                continue  # a comment cannot be a hard-coded runtime value
            if suspicious.search(line):
                offenders.append(f"{path.name}:{number}")
    assert not offenders, "hard-coded runtime value: " + ", ".join(offenders)


def test_all_agent_modules_parse():
    for path in _sources():
        ast.parse(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Feature 002 (T033): two new boundaries.
#
# git is a subprocess that carries a credential, and document formats are a
# parsing surface with its own dependency. Each belongs to exactly one module,
# for the same reason TFS REST and the provider wire format do: so that changing
# one never means reading the rest of the package.
# --------------------------------------------------------------------------

MAY_INVOKE_GIT = {"source_fetch.py", "bootstrap.py"}  # bootstrap re-executes the review
MAY_READ_DOCUMENT_FORMATS = {"checklist_docs.py"}


def test_git_is_invoked_from_one_module_only():
    offenders = []
    for path in _sources():
        if path.name in MAY_INVOKE_GIT:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"[\"']git[\"']|subprocess\.(run|Popen|check_)", text):
            offenders.append(path.name)
    assert not offenders, (
        "git or a subprocess invoked outside the fetch boundary: " + ", ".join(offenders)
    )


def test_subprocess_is_imported_only_where_a_child_process_is_the_point():
    offenders = [
        p.name
        for p in _sources()
        if "subprocess" in _imported_modules(p) and p.name not in MAY_INVOKE_GIT
    ]
    assert not offenders, "subprocess imported outside the fetch boundary: " + ", ".join(offenders)


def test_document_format_libraries_stay_in_one_module():
    """openpyxl and the zip/XML reading of .docx belong to the reader alone."""
    offenders = []
    for path in _sources():
        if path.name in MAY_READ_DOCUMENT_FORMATS:
            continue
        if "openpyxl" in _imported_modules(path):
            offenders.append(f"{path.name}:openpyxl")
    assert not offenders, "document parsing leaked: " + ", ".join(offenders)


# --------------------------------------------------------------------------
# T018 (feature 003): the corpus module holds neither boundary it depends on.
#
# Obtaining a working copy and parsing a spreadsheet are both things
# `checklist.py` needs and neither is a thing it may do. The natural
# implementation of each - `subprocess.run(["git", ...])` and `import openpyxl` -
# breaks a boundary that took a feature to establish, and does so invisibly.
# --------------------------------------------------------------------------

CORPUS_MODULE = AGENT_DIR / "checklist.py"


def test_the_corpus_module_asks_for_a_working_copy_rather_than_obtaining_one():
    text = CORPUS_MODULE.read_text(encoding="utf-8")
    assert "subprocess" not in _imported_modules(CORPUS_MODULE)
    assert re.search(r"[\"']git[\"']", text) is None


def test_the_corpus_module_asks_for_a_document_to_be_read_rather_than_reading_it():
    imported = _imported_modules(CORPUS_MODULE)
    assert "openpyxl" not in imported
    assert "zipfile" not in imported


def test_the_corpus_module_reads_no_environment():
    text = CORPUS_MODULE.read_text(encoding="utf-8")
    assert re.search(r"os\.environ|os\.getenv|getenv\(", text) is None


# --------------------------------------------------------------------------
# T032 (feature 006): the deletion boundary.
#
# Until this feature the package deleted exactly one thing - a temp tree
# source_fetch had created itself. Retention deletes inside a directory the
# OPERATOR chose, which is a different kind of act, and the set of modules
# allowed to perform it should be small enough to read in one line.
# --------------------------------------------------------------------------

MAY_DELETE_PATHS = {"source_fetch.py", "llm_log.py"}

_DELETES = re.compile(
    r"os\.remove\(|os\.unlink\(|os\.rmdir\(|os\.removedirs\(|shutil\.rmtree\(|\.unlink\("
)


def test_only_two_modules_delete_anything():
    offenders = []
    for path in _sources():
        if path.name in MAY_DELETE_PATHS:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if _DELETES.search(line):
                offenders.append(f"{path.name}:{number}")
    assert not offenders, "a path is deleted outside the two modules that may: " + ", ".join(
        offenders
    )


def test_the_log_module_reads_no_environment():
    """Its three settings arrive on the frozen Config like everything else."""
    text = (AGENT_DIR / "llm_log.py").read_text(encoding="utf-8")
    assert re.search(r"os\.environ|os\.getenv|getenv\(", text) is None


def test_the_log_module_knows_nothing_it_should_not():
    """It records a conversation. It does not know how one is transported,
    what a checklist document looks like, or how to reach a pull request."""
    imported = _imported_modules(AGENT_DIR / "llm_log.py")
    for forbidden in ("requests", "subprocess", "openpyxl", "zipfile"):
        assert forbidden not in imported


# --------------------------------------------------------------------------
# T012 (feature 007): the modules this feature adds are pure.
#
# Planning, declaration extraction, story selection and the platform seam are
# all things the pipeline needs and none of them may reach the network, run a
# child process, or read the environment. Each is asserted once it exists, so
# this test tightens as the feature lands.
# --------------------------------------------------------------------------

import pytest  # noqa: E402

PURE_007_MODULES = ("platform.py", "stories.py", "declarations.py", "chunk_planner.py")


@pytest.mark.parametrize("name", PURE_007_MODULES)
def test_feature_007_modules_reach_nothing_outside_themselves(name):
    path = AGENT_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not written yet")
    imported = _imported_modules(path)
    text = path.read_text(encoding="utf-8")
    assert "requests" not in imported, f"{name} imports requests"
    assert "subprocess" not in imported, f"{name} imports subprocess"
    assert re.search(r"os\.environ|os\.getenv|getenv\(", text) is None, f"{name} reads the environment"
    assert re.search(r"[\"']git[\"']", text) is None, f"{name} invokes git"
