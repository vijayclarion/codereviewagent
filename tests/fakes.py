"""Fakes standing in for TFS and the AI provider.

A fake client rather than `responses` for the pipeline tests: these exercise
orchestration, and asserting on which *method* was called reads far better than
asserting on URL strings. `responses` is still the right tool for the transport
tests in tfs_client, which is where URL shapes actually matter.
"""

from tests.fixtures import pr_demo as demo


class FakeTfsClient:
    """Records calls; serves the demo fixtures."""

    def __init__(self, threads=None, checklist_files=None, fail_patch=False):
        self.calls = []
        self.writes = []
        self._threads = threads if threads is not None else []
        self._checklist_files = (
            checklist_files
            if checklist_files is not None
            else {
                "/code-review-checklist.md": demo.CHECKLIST_MAIN,
                "/security-checklist.md": demo.CHECKLIST_SECURITY,
            }
        )
        self.fail_patch = fail_patch

    # -- reads --

    def get_pull_request(self):
        self.calls.append("get_pull_request")
        return demo.PULL_REQUEST

    def get_linked_work_item_ids(self):
        self.calls.append("get_linked_work_item_ids")
        return [101]

    def get_work_item(self, work_item_id):
        self.calls.append(f"get_work_item:{work_item_id}")
        return demo.WORK_ITEM_101

    def get_iterations(self):
        self.calls.append("get_iterations")
        return demo.ITERATIONS["value"]

    def get_iteration_changes(self, iteration_id):
        self.calls.append(f"get_iteration_changes:{iteration_id}")
        return demo.ITERATION_CHANGES

    def get_file_content(self, path, commit_sha, repo=None):
        self.calls.append(f"get_file_content:{path}@{commit_sha[:4]}")
        is_head = commit_sha.startswith("head")
        if path == demo.CART_CONTROLLER_PATH:
            return demo.CART_CONTROLLER_AFTER if is_head else demo.CART_CONTROLLER_BEFORE
        if path == demo.APPSETTINGS_PATH:
            return demo.APPSETTINGS_AFTER if is_head else "{}\n"
        return None

    def list_items(self, scope_path, branch, repo=None):
        self.calls.append(f"list_items:{scope_path}@{branch}")
        return demo.CHECKLIST_ITEMS["value"]

    def get_file_on_branch(self, path, branch, repo=None):
        self.calls.append(f"get_file_on_branch:{path}")
        return self._checklist_files.get(path)

    def get_threads(self):
        self.calls.append("get_threads")
        return list(self._threads)

    # -- writes --

    def create_thread(self, content, thread_context=None):
        self.writes.append(("create_thread", content, thread_context))
        return {"id": 900 + len(self.writes), "comments": [{"id": 1}]}

    def add_comment(self, thread_id, content):
        self.writes.append(("add_comment", thread_id, content))
        return {"id": 1}

    def update_comment(self, thread_id, comment_id, content):
        if self.fail_patch:
            raise RuntimeError("PATCH not supported by this server")
        self.writes.append(("update_comment", thread_id, comment_id, content))
        return {"id": comment_id}

    # -- assertions helpers --

    @property
    def write_count(self):
        return len(self.writes)

    def created_threads(self):
        return [w for w in self.writes if w[0] == "create_thread"]

    def inline_threads(self):
        return [w for w in self.created_threads() if w[2] is not None]

    def summary_threads(self):
        return [w for w in self.created_threads() if w[2] is None]


class EmptyChangesClient(FakeTfsClient):
    def get_iteration_changes(self, iteration_id):
        self.calls.append("get_iteration_changes:empty")
        return {"changeEntries": []}


class NoWorkItemClient(FakeTfsClient):
    def get_linked_work_item_ids(self):
        self.calls.append("get_linked_work_item_ids")
        return []


class NoChecklistClient(FakeTfsClient):
    def list_items(self, scope_path, branch, repo=None):
        self.calls.append("list_items:none")
        return []


def fake_llm(response, fail_times=0, exception=None):
    """Return a call_llm stand-in. Records every prompt it is given."""
    import json

    state = {"calls": 0, "prompts": []}

    def _call(prompt, config=None, **kwargs):
        state["calls"] += 1
        state["prompts"].append(prompt)
        if state["calls"] <= fail_times:
            if exception:
                raise exception
            return "I cannot produce JSON right now."
        if isinstance(response, str):
            return response
        return json.dumps(response)

    _call.state = state
    return _call
