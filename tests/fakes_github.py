"""T016 (feature 007) - a protocol-level stand-in for `GitHubClient`.

Like `tests/fakes.FakeTfsClient`, it exercises orchestration: asserting which
operation ran reads better than asserting on URLs. The URL shapes are asserted
where they matter, in tests/unit/test_github_client.py with `responses`.
"""

from review_agent.models import ChangeEntry, PullRequestContext, Revision
from tests.fixtures import github_pr as gh


class FakeGitHubClient:
    """Serves the `github_pr` fixtures and records every operation."""

    name = "github"

    def __init__(self, threads=None, refuse_inline=False, issues=None, linked=(7,),
                 notes=(), pull=None, files=None, contents=None):
        self.calls = []
        self.writes = []
        self._threads = list(threads or [])
        self.refuse_inline = refuse_inline
        self._issues = {7: gh.ISSUE_7} if issues is None else issues
        self._linked = tuple(linked)
        self._notes = tuple(notes)
        self._pull = pull or gh.PULL
        self._files = files
        self._contents = contents or gh.CONTENTS
        self._next_id = 5000

    # -- reads --

    def get_pull_request_context(self):
        self.calls.append("get_pull_request_context")
        return PullRequestContext.from_github(self._pull["number"], self._pull)

    def get_revision(self):
        self.calls.append("get_revision")
        return Revision(iteration_id=self._pull.get("commits", 1), head=gh.HEAD, base=gh.MERGE_BASE)

    def get_changed_files(self, revision=None):
        self.calls.append("get_changed_files")
        if self._files is not None:
            return list(self._files)
        return [
            ChangeEntry("/" + gh.CART_PATH, "edit"),
            ChangeEntry("/" + gh.APPSETTINGS_PATH, "edit"),
        ]

    def get_file_content(self, path, commit_sha, repo=None):
        self.calls.append(f"get_file_content:{path}@{commit_sha[:4]}")
        return self._contents.get((path.lstrip("/"), commit_sha))

    def get_threads(self):
        self.calls.append("get_threads")
        return list(self._threads)

    def list_items(self, scope_path, branch, repo=None):
        self.calls.append(f"list_items:{scope_path}")
        return []

    def get_file_on_branch(self, path, branch, repo=None):
        return None

    def linked_issue_numbers(self):
        from review_agent.github_client import IssueLinks

        self.calls.append("linked_issue_numbers")
        return IssueLinks(self._linked, self._notes)

    def get_issue(self, number):
        self.calls.append(f"get_issue:{number}")
        payload = self._issues.get(number)
        if payload is None:
            return None, f"issue #{number} was not found"
        if "pull_request" in payload:
            return None, f"#{number} is a pull request, not an issue"
        return payload, ""

    # -- writes --

    def _id(self):
        self._next_id += 1
        return self._next_id

    def post_summary(self, markdown, prior):
        if prior and prior.summary_comment_id:
            self.writes.append(("update_summary", prior.summary_comment_id, markdown))
        else:
            self.writes.append(("create_summary", markdown))

    def deliver(self, plan, prior, pr_context):
        self.post_summary(plan.summary_markdown, prior if plan.action == "update_summary" else None)
        if not plan.inline:
            return 0
        comments = [(c.path, c.right_line, c.markdown) for c in plan.inline]
        if self.refuse_inline:
            self.writes.append(("create_review", pr_context.iteration_commit, [], "refused"))
            return 0
        self.writes.append(("create_review", pr_context.iteration_commit, comments, ""))
        return len(comments)

    @property
    def write_count(self):
        return len(self.writes)

    # -- helpers --

    def reviews(self):
        return [w for w in self.writes if w[0] == "create_review"]

    def summaries(self):
        return [w for w in self.writes if w[0] in ("create_summary", "update_summary")]

    def as_threads(self):
        """What a later run would read back: this run's comments as threads."""
        threads = []
        for write in self.writes:
            if write[0] == "create_summary":
                threads.append({"id": self._id(), "threadContext": None,
                                "comments": [{"id": self._next_id, "content": write[1]}]})
            elif write[0] == "create_review":
                for path, _line, markdown in write[2]:
                    cid = self._id()
                    threads.append({"id": cid, "threadContext": {"filePath": path},
                                    "comments": [{"id": cid, "content": markdown}]})
        return threads

