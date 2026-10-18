"""T061 - fingerprints and recovering prior feedback from the pull request."""

from review_agent import dedupe
from review_agent.output_layer import _footer
from tests.fakes import FakeTfsClient


def _thread(thread_id, content, comment_id=1, deleted=False):
    return {
        "id": thread_id,
        "isDeleted": deleted,
        "comments": [{"id": comment_id, "content": content}],
    }


# -- marker parsing --------------------------------------------------------


def test_parses_a_summary_marker():
    assert dedupe.parse_markers("body\n\nai-review:summary") == [("summary", None)]


def test_parses_a_finding_marker_with_its_fingerprint():
    markers = dedupe.parse_markers("body ai-review:checklist:a1b2c3d4e5f6")
    assert markers == [("checklist", "a1b2c3d4e5f6")]


def test_parses_the_rendered_footer_shape():
    """The parser must understand exactly what the renderer emits."""
    body = "finding text" + _footer("code", "0123456789ab")
    assert dedupe.parse_markers(body) == [("code", "0123456789ab")]


def test_parses_the_rendered_summary_footer():
    body = "summary text" + _footer()
    assert ("summary", None) in dedupe.parse_markers(body)


def test_a_human_comment_has_no_markers():
    assert dedupe.parse_markers("This looks wrong to me, can you check?") == []


def test_empty_content_is_safe():
    assert dedupe.parse_markers(None) == []
    assert dedupe.parse_markers("") == []


# -- reading prior feedback ------------------------------------------------


def test_no_threads_means_no_prior_feedback():
    prior = dedupe.read_prior_feedback(FakeTfsClient(threads=[]))
    assert prior.is_empty
    assert prior.summary_thread_id is None
    assert prior.posted_fingerprints == frozenset()


def test_finds_the_summary_thread_and_comment():
    threads = [_thread(11, "## AI Code Review\n\nai-review:summary", comment_id=99)]
    prior = dedupe.read_prior_feedback(FakeTfsClient(threads=threads))
    assert prior.summary_thread_id == 11
    assert prior.summary_comment_id == 99


def test_collects_posted_fingerprints():
    threads = [
        _thread(1, "x ai-review:checklist:aaaaaaaaaaaa"),
        _thread(2, "y ai-review:code:bbbbbbbbbbbb"),
    ]
    prior = dedupe.read_prior_feedback(FakeTfsClient(threads=threads))
    assert prior.posted_fingerprints == frozenset({"aaaaaaaaaaaa", "bbbbbbbbbbbb"})


def test_human_threads_are_not_claimed_as_our_own():
    threads = [
        _thread(1, "Please rename this variable"),
        _thread(2, "x ai-review:code:cccccccccccc"),
    ]
    prior = dedupe.read_prior_feedback(FakeTfsClient(threads=threads))
    assert prior.own_thread_ids == frozenset({2})


def test_deleted_threads_are_ignored():
    """FakeTfsClient returns what the client would after filtering isDeleted."""
    client = FakeTfsClient(threads=[])
    prior = dedupe.read_prior_feedback(client)
    assert prior.is_empty


def test_first_summary_wins_so_there_is_only_ever_one():
    threads = [
        _thread(5, "first ai-review:summary", comment_id=50),
        _thread(6, "second ai-review:summary", comment_id=60),
    ]
    prior = dedupe.read_prior_feedback(FakeTfsClient(threads=threads))
    assert prior.summary_thread_id == 5


def test_identification_does_not_depend_on_the_comment_author():
    """A manual PAT run and a pipeline run post under different identities."""
    threads = [
        {
            "id": 3,
            "comments": [
                {"id": 1, "content": "x ai-review:code:dddddddddddd",
                 "author": {"displayName": "Some Build Service"}}
            ],
        }
    ]
    prior = dedupe.read_prior_feedback(FakeTfsClient(threads=threads))
    assert prior.posted_fingerprints == frozenset({"dddddddddddd"})


def test_unreadable_threads_degrade_to_no_prior_feedback():
    """A duplicate comment beats refusing to review."""

    class Broken(FakeTfsClient):
        def get_threads(self):
            raise RuntimeError("threads unavailable")

    prior = dedupe.read_prior_feedback(Broken())
    assert prior.is_empty


def test_multiple_markers_in_one_comment_are_all_collected():
    threads = [_thread(1, "a ai-review:code:aaaaaaaaaaaa and b ai-review:checklist:bbbbbbbbbbbb")]
    prior = dedupe.read_prior_feedback(FakeTfsClient(threads=threads))
    assert len(prior.posted_fingerprints) == 2


def test_fingerprint_is_re_exported_from_one_definition():
    """Two fingerprint implementations would silently stop matching each other."""
    from review_agent import parser

    assert dedupe.fingerprint is parser.fingerprint
