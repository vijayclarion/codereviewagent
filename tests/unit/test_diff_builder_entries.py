"""T011 (feature 007) - one change-set builder for both entry shapes."""

from review_agent.diff_builder import build_change_set
from review_agent.models import ChangeEntry, PullRequestContext


class _Blobs:
    def __init__(self, files):
        self.files = files
        self.calls = []

    def get_file_content(self, path, sha, repo=None):
        self.calls.append((path, sha))
        return self.files.get((path, sha))


CTX = PullRequestContext(pr_id=1).with_iteration(1, "head1", "base1")


def test_change_entry_objects_build_the_same_diff_as_tfs_dicts():
    blobs = {("/a.cs", "head1"): "one\ntwo\n", ("/a.cs", "base1"): "one\n"}
    as_entry, _ = build_change_set(_Blobs(blobs), CTX, [ChangeEntry("/a.cs", "edit")])
    as_dict, _ = build_change_set(
        _Blobs(blobs), CTX, [{"item": {"path": "/a.cs"}, "changeType": "edit"}]
    )
    assert as_entry == as_dict
    assert as_entry.files[0].changed_lines == 1


def test_content_is_kept_for_the_skeleton():
    blobs = {("/a.cs", "head1"): "class A {}\n"}
    change_set, _ = build_change_set(_Blobs(blobs), CTX, [ChangeEntry("/a.cs", "add")])
    assert change_set.files[0].content == "class A {}\n"


def test_deleted_and_binary_entries_are_skipped_with_reasons():
    client = _Blobs({})
    _, skipped = build_change_set(
        client, CTX, [ChangeEntry("/gone.cs", "delete"), ChangeEntry("/logo.png", "add")]
    )
    assert [(s.path, s.reason) for s in skipped] == [("/gone.cs", "deleted"), ("/logo.png", "binary")]
    assert client.calls == []


def test_added_files_never_fetch_the_base():
    client = _Blobs({("/new.cs", "head1"): "x\n"})
    build_change_set(client, CTX, [ChangeEntry("/new.cs", "add")])
    assert client.calls == [("/new.cs", "head1")]
