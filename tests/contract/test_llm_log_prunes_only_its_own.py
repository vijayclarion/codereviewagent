"""T024 (feature 006) - retention never destroys anything it did not create.

Pruning is the only destructive operation in this package that touches a
directory the *operator* chose. `source_fetch.cleanup` removes a temp tree it
made itself; this removes files from a path someone configured, and
`LLM_LOG_DIR=.` is a setting somebody will eventually try.

Two guards, and this is what holds them:

* a filename pattern that proves this module wrote the file, so an operator's
  own notes, archives and unrelated `.log` files are never candidates;
* a timestamp comparison, so a run never removes the log a concurrent run is
  still writing.

Everything else in this feature can be repaired by running it again. A deleted
file cannot, which is why this is a contract test and not a unit test.
"""

from datetime import datetime, timedelta

import pytest

from review_agent import llm_log

NOW = datetime(2026, 9, 17, 14, 30, 22)


def destination(tmp_path, keep=3):
    return llm_log.LogDestination(str(tmp_path), keep)


def log_named(tmp_path, stamp, pr=1234, body="old log"):
    path = tmp_path / f"llm-pr{pr}-{stamp}.log"
    path.write_text(body, encoding="utf-8")
    return path


def stamp_for(offset_minutes):
    return (NOW + timedelta(minutes=offset_minutes)).strftime(llm_log.STAMP_FORMAT)


# --------------------------------------------------------------------------
# What may never be deleted
# --------------------------------------------------------------------------


def test_a_file_this_module_did_not_write_is_never_deleted(tmp_path):
    """SC-009. The destination is a path the operator chose; they may keep
    things in it."""
    strangers = {
        "notes.txt": "my notes",
        "important.log": "somebody else's log",
        "llm-pr1234.log": "close, but not our shape",
        "llm-prABC-20260101-000000.log": "not a pull request id",
        "20260101-000000.log": "no prefix",
        ".env": "SECRET=value",
        "llm-pr1234-20260101-000000.log.bak": "a backup of one of ours",
    }
    for name, body in strangers.items():
        (tmp_path / name).write_text(body, encoding="utf-8")

    # Plenty of genuine logs, so the sweep is definitely under pressure.
    for minutes in range(-10, 0):
        log_named(tmp_path, stamp_for(minutes))

    removed, problem = llm_log.prune(destination(tmp_path, keep=2), NOW)

    assert removed == 9, "genuine logs should have been pruned"
    assert not problem
    for name, body in strangers.items():
        assert (tmp_path / name).exists(), f"{name} was deleted"
        assert (tmp_path / name).read_text(encoding="utf-8") == body


def test_a_subdirectory_is_never_entered_or_removed(tmp_path):
    nested = tmp_path / "archive"
    nested.mkdir()
    buried = nested / "llm-pr1234-20200101-000000.log"
    buried.write_text("archived on purpose", encoding="utf-8")
    for minutes in range(-5, 0):
        log_named(tmp_path, stamp_for(minutes))

    llm_log.prune(destination(tmp_path, keep=1), NOW)

    assert nested.is_dir()
    assert buried.exists(), "an archived log inside a subdirectory was deleted"


def test_a_log_newer_than_this_run_is_never_deleted(tmp_path):
    """FR-014d. A concurrent run's file is newer than ours, so it is excluded
    by comparison rather than by a lock or an mtime tolerance."""
    concurrent = log_named(tmp_path, stamp_for(+1), body="a run in progress")
    same_second = log_named(tmp_path, stamp_for(0), body="started with us")
    for minutes in range(-8, 0):
        log_named(tmp_path, stamp_for(minutes))

    llm_log.prune(destination(tmp_path, keep=1), NOW)

    assert concurrent.exists(), "deleted the log a concurrent run was writing"
    assert same_second.exists(), "deleted a log started in the same second"


def test_the_current_run_always_has_room_even_at_the_smallest_retention(tmp_path):
    """keep=1 means this run's log and nothing else - never nothing at all."""
    for minutes in range(-4, 0):
        log_named(tmp_path, stamp_for(minutes))

    removed, _ = llm_log.prune(destination(tmp_path, keep=1), NOW)

    assert removed == 4
    assert list(tmp_path.glob("*.log")) == []


# --------------------------------------------------------------------------
# What is deleted, and in what order
# --------------------------------------------------------------------------


def test_the_oldest_go_first_and_the_newest_survive(tmp_path):
    paths = {m: log_named(tmp_path, stamp_for(m)) for m in range(-5, 0)}

    removed, _ = llm_log.prune(destination(tmp_path, keep=3), NOW)

    assert removed == 3
    assert not paths[-5].exists() and not paths[-4].exists() and not paths[-3].exists()
    assert paths[-2].exists() and paths[-1].exists()


def test_a_directory_below_the_limit_loses_nothing(tmp_path):
    paths = [log_named(tmp_path, stamp_for(m)) for m in (-2, -1)]

    removed, problem = llm_log.prune(destination(tmp_path, keep=10), NOW)

    assert removed == 0
    assert not problem
    assert all(p.exists() for p in paths)


def test_the_collision_suffix_is_still_recognised_as_ours(tmp_path):
    """Two runs in the same second produce `...-2.log`, which must still be
    prunable later - otherwise those accumulate forever."""
    suffixed = tmp_path / f"llm-pr1234-{stamp_for(-9)}-2.log"
    suffixed.write_text("second run of that second", encoding="utf-8")
    for minutes in range(-8, 0):
        log_named(tmp_path, stamp_for(minutes))

    llm_log.prune(destination(tmp_path, keep=1), NOW)

    assert not suffixed.exists()


# --------------------------------------------------------------------------
# Failure never touches the review
# --------------------------------------------------------------------------


def test_a_destination_that_cannot_be_read_is_reported_not_raised(tmp_path):
    missing = llm_log.LogDestination(str(tmp_path / "nowhere"), 3)

    removed, problem = llm_log.prune(missing, NOW)

    assert removed == 0
    assert "could not read" in problem


def test_a_file_that_cannot_be_removed_is_skipped_and_reported(tmp_path, monkeypatch):
    for minutes in range(-5, 0):
        log_named(tmp_path, stamp_for(minutes))

    calls = {"n": 0}

    def _sometimes_refuse(path):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("in use by another process")
        return None

    monkeypatch.setattr(llm_log.os, "remove", _sometimes_refuse)
    removed, problem = llm_log.prune(destination(tmp_path, keep=1), NOW)

    # 5 candidates, keep=1 leaves room for the run's own log, so all 5 are
    # attempted; one refuses and the other four still go.
    assert removed == 4, "one refusal must not stop the rest"
    assert "could not remove" in problem


def test_pruning_never_raises_whatever_the_destination_does(tmp_path, monkeypatch):
    """FR-014f. A tidy directory is worth less than the run's own evidence."""

    def _explode(*args, **kwargs):
        raise OSError("the volume has been disconnected")

    monkeypatch.setattr(llm_log.os, "listdir", _explode)
    removed, problem = llm_log.prune(destination(tmp_path), NOW)

    assert removed == 0
    assert problem


def test_the_authorship_pattern_is_anchored_at_both_ends():
    """A pattern that matched loosely would be the whole guard, undone."""
    assert llm_log.LOG_NAME.match("llm-pr1234-20260917-143022.log")
    assert llm_log.LOG_NAME.match("llm-pr1234-20260917-143022-2.log")

    for hostile in (
        "x-llm-pr1234-20260917-143022.log",
        "llm-pr1234-20260917-143022.log.bak",
        "llm-pr1234-20260917-143022.txt",
        "llm-pr-20260917-143022.log",
        "llm-pr1234-2026917-143022.log",
        "notes.log",
    ):
        assert not llm_log.LOG_NAME.match(hostile), f"{hostile} matched"
