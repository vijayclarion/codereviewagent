"""The hosting platform, as the pipeline sees it (feature 007, research D1-D3).

`run_review` reads a pull request, its stories, its changes and the agent's own
earlier comments, and then delivers feedback. It does every one of those things
through the `PlatformClient` protocol below, so it does not know whether the
pull request lives on TFS or GitHub.

TFS is served by `TfsPlatform`, an adapter that *composes* the existing
`TfsClient` and calls nothing but the twelve methods that client - and the
suite's `FakeTfsClient` - already have. That is what keeps `tfs_client.py`
untouched and every existing posting test byte-identical: delivery on TFS is
still `output_layer.post_plan`, verbatim.

GitHub is served by `github_client.GitHubClient`, which implements the protocol
directly; it is imported only when a run asks for it.

contracts/platform-client.md is the method-by-method contract.
"""

from typing import Protocol

from . import output_layer
from .diff_builder import resolve_iteration
from .errors import DegradedReview
from .models import PullRequestContext, Revision


class PlatformClient(Protocol):
    """Everything the pipeline asks of a hosting platform."""

    name: str

    # -- reads --
    def get_pull_request_context(self): ...
    def get_revision(self): ...
    def get_changed_files(self, revision): ...
    def get_file_content(self, path, commit_sha, repo=None): ...
    def get_threads(self): ...
    def list_items(self, scope_path, branch, repo=None): ...
    def get_file_on_branch(self, path, branch, repo=None): ...

    # -- writes --
    def post_summary(self, markdown, prior): ...
    def deliver(self, plan, prior, pr_context): ...

    @property
    def write_count(self): ...


NO_ITERATIONS = "the pull request has no iterations to review"


class TfsPlatform:
    """`PlatformClient` over a `TfsClient` - or anything with its surface."""

    name = "tfs"

    def __init__(self, client, config):
        self.client = client
        self.config = config
        self._pr_payload = None

    # -- reads -----------------------------------------------------------

    def get_pull_request_context(self):
        self._pr_payload = self.client.get_pull_request()
        return PullRequestContext.from_payload(self.config.tfs_pr_id, self._pr_payload)

    def get_revision(self):
        iterations = self.client.get_iterations()
        if not iterations:
            raise DegradedReview(NO_ITERATIONS)
        iteration_id, head, base = resolve_iteration(iterations, self._pr_payload)
        return Revision(iteration_id=int(iteration_id or 0), head=head or "", base=base or "")

    def get_changed_files(self, revision):
        payload = self.client.get_iteration_changes(revision.iteration_id)
        return (payload or {}).get("changeEntries", []) or []

    def get_file_content(self, path, commit_sha, repo=None):
        return self.client.get_file_content(path, commit_sha, repo=repo)

    def get_threads(self):
        return self.client.get_threads()

    def list_items(self, scope_path, branch, repo=None):
        return self.client.list_items(scope_path, branch, repo=repo)

    def get_file_on_branch(self, path, branch, repo=None):
        return self.client.get_file_on_branch(path, branch, repo=repo)

    def get_linked_work_item_ids(self):
        return self.client.get_linked_work_item_ids()

    def get_work_item(self, work_item_id):
        return self.client.get_work_item(work_item_id)

    # -- writes ----------------------------------------------------------

    def post_summary(self, markdown, prior):
        """The degraded notice: edit the summary in place, or start one."""
        if prior and prior.summary_thread_id and prior.summary_comment_id:
            return self.client.update_comment(
                prior.summary_thread_id, prior.summary_comment_id, markdown
            )
        return self.client.create_thread(markdown)

    def deliver(self, plan, prior, pr_context=None):
        return output_layer.post_plan(plan, self.client, prior)

    @property
    def write_count(self):
        return getattr(self.client, "write_count", 0)


def make_platform(config, tfs_factory):
    """The platform this run reviews on.

    `tfs_factory` is passed by the caller at call time - `main.TfsClient` - so
    that a test which replaces `main.TfsClient` is still the one honoured.
    """
    if getattr(config, "platform", "tfs") == "github":
        from .github_client import make_github_platform

        return make_github_platform(config)
    return TfsPlatform(tfs_factory(config), config)
