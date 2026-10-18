"""T094 (feature 007, Q1) - TFS posts with TFS_PAT_FOR_PR, never with the read token.

Before 007 the pipeline built one `TfsClient` (purpose "read") and posted with
it; `TFS_PAT_FOR_PR` was required and unused (research E3).
"""

import base64

import responses

from review_agent import output_layer
from review_agent.config import load_config
from review_agent.platform import TfsPlatform, make_platform
from review_agent.tfs_client import TfsClient


def _basic(token):
    return "Basic " + base64.b64encode(f":{token}".encode()).decode()


def test_a_preview_builds_no_posting_client(base_env):
    platform = make_platform(load_config(dry_run_override=True), tfs_factory=TfsClient)
    assert platform.writer is None
    assert platform.client.purpose == "read"


def test_a_posting_run_builds_a_separate_posting_client(base_env):
    platform = make_platform(load_config(dry_run_override=False), tfs_factory=TfsClient)
    assert platform.writer.purpose == "post"
    assert platform.writer.token == "post-secret-value"
    assert platform.client.token == "pat-secret-value"


def test_a_factory_without_purpose_keeps_one_client(base_env):
    fake = object()
    platform = make_platform(load_config(dry_run_override=False), tfs_factory=lambda config: fake)
    assert platform.writer is None and platform.client is fake


@responses.activate
def test_posts_carry_the_posting_credential(base_env):
    config = load_config(dry_run_override=False)
    platform = make_platform(config, tfs_factory=TfsClient)
    url = f"{config.api_root}/git/repositories/eShop/pullRequests/1234/threads"
    responses.add(responses.POST, url, json={"id": 1, "comments": [{"id": 1}]})
    plan = output_layer.FeedbackPlan("summary", [], [], [], "create_summary")
    platform.deliver(plan, None, None)
    (call,) = responses.calls
    assert call.request.headers["Authorization"] == _basic("post-secret-value")
    assert platform.write_count == 1


def test_adapter_routes_writes_to_the_writer():
    class _Rec:
        def __init__(self):
            self.writes = []
            self.write_count = 0

        def create_thread(self, content, thread_context=None):
            self.writes.append(content)
            self.write_count += 1

    reader, writer = _Rec(), _Rec()
    platform = TfsPlatform(reader, object(), writer=writer)
    platform.post_summary("x", None)
    assert writer.writes == ["x"] and reader.writes == []
    assert platform.write_count == 1
