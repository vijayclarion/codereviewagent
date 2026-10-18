"""T009 (feature 007) - the TFS adapter is invisible.

Every assertion here compares the adapter with what the pipeline did directly
before the seam existed. `tests/fakes.py` is used unmodified.
"""

import pytest

from review_agent import diff_builder, output_layer
from review_agent.dedupe import PriorFeedback
from review_agent.errors import DegradedReview
from review_agent.models import PullRequestContext, Revision
from review_agent.platform import NO_ITERATIONS, TfsPlatform, make_platform
from tests.fakes import FakeTfsClient
from tests.fixtures import pr_demo as demo


class _Cfg:
    tfs_pr_id = 1234
    platform = "tfs"


def _platform(**kwargs):
    fake = FakeTfsClient(**kwargs)
    return TfsPlatform(fake, _Cfg()), fake


def test_reads_delegate_and_match_the_direct_path():
    platform, fake = _platform()
    ctx = platform.get_pull_request_context()
    assert ctx == PullRequestContext.from_payload(1234, demo.PULL_REQUEST)

    revision = platform.get_revision()
    iteration_id, head, base = diff_builder.resolve_iteration(
        demo.ITERATIONS["value"], demo.PULL_REQUEST
    )
    assert revision == Revision(iteration_id, head, base)

    assert platform.get_changed_files(revision) == demo.ITERATION_CHANGES["changeEntries"]
    assert platform.get_threads() == []
    assert platform.get_linked_work_item_ids() == [101]
    assert platform.get_work_item(101) == demo.WORK_ITEM_101
    assert fake.calls[:3] == ["get_pull_request", "get_iterations", f"get_iteration_changes:{iteration_id}"]


def test_no_iterations_is_the_same_degraded_review():
    class Empty(FakeTfsClient):
        def get_iterations(self):
            return []

    platform = TfsPlatform(Empty(), _Cfg())
    platform.get_pull_request_context()
    with pytest.raises(DegradedReview) as caught:
        platform.get_revision()
    assert caught.value.message == NO_ITERATIONS == "the pull request has no iterations to review"


def _plan():
    inline = output_layer.InlineComment("/src/a.cs", 3, "body\n\nfooter", "fp1", "code", "body")
    return output_layer.FeedbackPlan("summary md", [inline], [], [], "create_summary")


@pytest.mark.parametrize("prior", [None, PriorFeedback(summary_thread_id=7, summary_comment_id=1)])
@pytest.mark.parametrize("fail_patch", [False, True])
def test_delivery_is_byte_identical_to_post_plan(prior, fail_patch):
    direct = FakeTfsClient(fail_patch=fail_patch)
    plan = _plan()
    if prior is not None:
        plan.action = "update_summary"
    expected_count = output_layer.post_plan(plan, direct, prior)

    platform, adapted = _platform(fail_patch=fail_patch)
    assert platform.deliver(plan, prior, None) == expected_count
    assert adapted.writes == direct.writes
    assert platform.write_count == direct.write_count


def test_post_summary_edits_in_place_or_starts_a_thread():
    platform, fake = _platform()
    platform.post_summary("degraded", PriorFeedback(summary_thread_id=7, summary_comment_id=2))
    platform.post_summary("degraded", None)
    assert fake.writes == [
        ("update_comment", 7, 2, "degraded"),
        ("create_thread", "degraded", None),
    ]


def test_make_platform_uses_the_factory_it_is_given():
    fake = FakeTfsClient()
    seen = []

    def factory(config):
        seen.append(config)
        return fake

    config = _Cfg()
    platform = make_platform(config, tfs_factory=factory)
    assert isinstance(platform, TfsPlatform)
    assert platform.client is fake and seen == [config]
