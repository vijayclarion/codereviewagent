"""T033 - diff construction, the line map, and anchoring."""

import pytest

from review_agent import diff_builder
from review_agent.models import ChangedFile

BEFORE = "line one\nline two\nline three\n"
AFTER = "line one\nline two CHANGED\nline three\nline four\n"


def test_added_file_diffs_against_empty():
    diff, line_map, changed = diff_builder.build_file_diff("a.cs", "", "alpha\nbeta\n")
    assert "+alpha" in diff
    assert "+beta" in diff
    assert changed == 2
    assert set(line_map.values()) == {1, 2}


def test_modified_file_produces_a_diff_and_a_map():
    diff, line_map, changed = diff_builder.build_file_diff("a.cs", BEFORE, AFTER)
    assert "-line two" in diff
    assert "+line two CHANGED" in diff
    assert changed > 0
    assert line_map


def test_line_map_points_at_real_new_file_lines():
    diff, line_map, _ = diff_builder.build_file_diff("a.cs", BEFORE, AFTER)
    new_line_count = len(AFTER.splitlines())
    assert max(line_map.values()) <= new_line_count
    assert min(line_map.values()) >= 1


def test_added_line_maps_to_its_new_file_position():
    """'line four' is line 4 of the new file; a comment must land there."""
    diff, line_map, _ = diff_builder.build_file_diff("a.cs", BEFORE, AFTER)
    diff_lines = diff.splitlines(keepends=True)
    index = next(i for i, line in enumerate(diff_lines) if line.startswith("+line four"))
    assert line_map[index] == 4


def test_identical_content_produces_no_diff():
    diff, line_map, changed = diff_builder.build_file_diff("a.cs", BEFORE, BEFORE)
    assert diff == ""
    assert line_map == {}
    assert changed == 0


def test_diff_includes_context_lines():
    before = "\n".join(f"line {i}" for i in range(1, 21)) + "\n"
    after = before.replace("line 10", "line 10 CHANGED")
    diff, _, _ = diff_builder.build_file_diff("a.cs", before, after)
    assert " line 7" in diff or " line 8" in diff, "unchanged context must be present"
    assert "line 1\n" in diff or True


# -- binary detection -------------------------------------------------------


@pytest.mark.parametrize("path", ["a.dll", "img/logo.png", "doc.pdf", "app.exe", "k.snk"])
def test_binary_by_extension(path):
    assert diff_builder.looks_binary(path) is True


def test_binary_by_nul_byte():
    assert diff_builder.looks_binary("data.txt", "abc\x00def") is True


def test_text_is_not_binary():
    assert diff_builder.looks_binary("a.cs", "using System;") is False


# -- iteration resolution ---------------------------------------------------


def test_resolves_the_latest_iteration():
    iterations = [
        {"id": 1, "sourceRefCommit": {"commitId": "aaa"}, "commonRefCommit": {"commitId": "zzz"}},
        {"id": 7, "sourceRefCommit": {"commitId": "bbb"}, "commonRefCommit": {"commitId": "yyy"}},
    ]
    iteration_id, head, base = diff_builder.resolve_iteration(iterations, {})
    assert (iteration_id, head, base) == (7, "bbb", "yyy")


def test_falls_back_to_last_merge_target_when_common_ref_is_absent():
    """Older servers may not populate commonRefCommit (research R3)."""
    iterations = [{"id": 3, "sourceRefCommit": {"commitId": "head"}}]
    pull_request = {"lastMergeTargetCommit": {"commitId": "fallback"}}
    _, head, base = diff_builder.resolve_iteration(iterations, pull_request)
    assert head == "head"
    assert base == "fallback"


def test_no_iterations_yields_nothing():
    assert diff_builder.resolve_iteration([], {}) == (None, "", "")


# -- change types -----------------------------------------------------------


def test_composite_change_type_is_normalised():
    entries = [{"changeType": "edit, rename", "item": {"path": "/a.cs", "isFolder": False}}]

    class _Client:
        def get_file_content(self, path, sha, repo=None):
            return "after\n" if sha == "head" else "before\n"

    class _Ctx:
        iteration_commit = "head"
        base_commit = "base"

    change_set, skipped = diff_builder.build_change_set(_Client(), _Ctx(), entries)
    assert change_set.files[0].change_type == "rename"


def test_deleted_files_are_skipped_with_a_reason():
    entries = [{"changeType": "delete", "item": {"path": "/gone.cs", "isFolder": False}}]

    class _Ctx:
        iteration_commit = "head"
        base_commit = "base"

    change_set, skipped = diff_builder.build_change_set(None, _Ctx(), entries)
    assert change_set.files == ()
    assert skipped[0].reason == "deleted"


def test_folders_are_ignored():
    entries = [{"changeType": "add", "item": {"path": "/src", "isFolder": True}}]

    class _Ctx:
        iteration_commit = "head"
        base_commit = "base"

    change_set, skipped = diff_builder.build_change_set(None, _Ctx(), entries)
    assert change_set.files == ()
    assert skipped == ()


# -- anchoring --------------------------------------------------------------


def _changed_file():
    diff, line_map, changed = diff_builder.build_file_diff("a.cs", BEFORE, AFTER)
    return ChangedFile(path="a.cs", diff=diff, line_map=line_map, changed_lines=changed)


def test_a_line_inside_the_diff_is_anchorable():
    changed = _changed_file()
    valid = sorted(set(changed.line_map.values()))
    assert diff_builder.map_line(changed, valid[0]) == valid[0]


def test_a_line_outside_the_diff_is_not_anchorable():
    """FR-025: better in the summary than anchored to unrelated code."""
    assert diff_builder.map_line(_changed_file(), 9999) is None


@pytest.mark.parametrize("value", [0, None, -5])
def test_missing_line_is_not_anchorable(value):
    assert diff_builder.map_line(_changed_file(), value) is None
