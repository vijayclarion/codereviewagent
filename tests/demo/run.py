"""Drive one full review with no server, no credential and no provider (T050).

The sample material is NOT duplicated here. The work item, the code and the
checklist documents all come from `specs/003-checklist-repo-review-demo/demo-files/`,
which is the single copy the operator also uses for the live run - so the two
halves of the demonstration cannot drift apart.
"""

import json
import os
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from review_agent import checklist as checklist_module  # noqa: E402
from review_agent import main as main_module  # noqa: E402
from review_agent import source_fetch  # noqa: E402
from review_agent.config import load_config  # noqa: E402

DEMO_FILES = os.path.join(
    REPO_ROOT, "specs", "003-checklist-repo-review-demo", "demo-files"
)

CONTROLLER_PATH = "/src/eShop.Api/Controllers/CartController.cs"
APPSETTINGS_PATH = "/src/eShop.Api/appsettings.json"

#: What the pull request's description claims. The fourth line is the fault: the
#: change does not enforce the stock limit, and saying it does is what turns an
#: unimplemented criterion into the review's headline finding.
PR_DESCRIPTION = """Implements the add-to-cart endpoint for user story #4101.

## Covered

- Quantity validation - rejects zero and negative quantities
- Unknown product returns not-found without changing the cart
- Adding an existing product increments the existing line
- Stock limit enforced when adding to cart
- Cart total recalculated after a successful add

## Not in this PR

- Removing a line from the cart
"""

APPSETTINGS_AFTER = """{
  "ConnectionStrings": {
    "Catalog": "Server=db;Database=Catalog;User Id=sa;Password=NotARealPassword1;"
  }
}
"""


def _read(*parts):
    with open(os.path.join(DEMO_FILES, *parts), encoding="utf-8") as handle:
        return handle.read()


def work_item():
    with open(os.path.join(DEMO_FILES, "work-item.json"), encoding="utf-8") as handle:
        payload = json.load(handle)
    payload.pop("_comment", None)
    return payload


class DemoClient:
    """The collection, as far as one review can tell. Records every write."""

    def __init__(self, threads=None):
        self.writes = []
        self._threads = list(threads or [])
        self.story = work_item()

    # -- reads --

    def get_pull_request(self):
        return {
            "pullRequestId": 4242,
            "title": "Add items to the shopping cart",
            "description": PR_DESCRIPTION,
            "sourceRefName": "refs/heads/feature/demo-003-add-to-cart",
            "targetRefName": "refs/heads/master",
            "lastMergeTargetCommit": {"commitId": "base00000000000000000000000000000000000d"},
        }

    def get_linked_work_item_ids(self):
        return [self.story["id"]]

    def get_work_item(self, work_item_id):
        return self.story

    def get_iterations(self):
        return [
            {
                "id": 1,
                "sourceRefCommit": {"commitId": "head00000000000000000000000000000000000d"},
                "commonRefCommit": {"commitId": "base00000000000000000000000000000000000d"},
            }
        ]

    def get_iteration_changes(self, iteration_id):
        return {
            "changeEntries": [
                {"changeType": "edit", "item": {"path": CONTROLLER_PATH, "isFolder": False}},
                {"changeType": "edit", "item": {"path": APPSETTINGS_PATH, "isFolder": False}},
            ]
        }

    def get_file_content(self, path, commit_sha, repo=None):
        after = commit_sha.startswith("head")
        if path == CONTROLLER_PATH:
            return _read("src", "CartController.cs" if after else "CartController.before.cs")
        if path == APPSETTINGS_PATH:
            return APPSETTINGS_AFTER if after else "{}\n"
        return None

    def list_items(self, scope_path, branch, repo=None):
        return []

    def get_file_on_branch(self, path, branch, repo=None):
        return None

    def get_threads(self):
        return list(self._threads)

    # -- writes --

    def create_thread(self, content, thread_context=None):
        self.writes.append(("create_thread", content, thread_context))
        return {"id": 900 + len(self.writes), "comments": [{"id": len(self.writes)}]}

    def add_comment(self, thread_id, content):
        self.writes.append(("add_comment", thread_id, content))
        return {"id": 1}

    def update_comment(self, thread_id, comment_id, content):
        self.writes.append(("update_comment", thread_id, comment_id, content))
        return {"id": comment_id}

    @property
    def write_count(self):
        return len(self.writes)

    def threads_for_next_run(self):
        """The pull request as a second run would read it back."""
        threads = []
        for index, (_kind, content, context) in enumerate(self.writes, start=1):
            thread = {"id": index, "comments": [{"id": index, "content": content}]}
            if context:
                thread["threadContext"] = context
            threads.append(thread)
        return threads


def generate_documents(into):
    """Write the sample checklist repository. Returns its root."""
    sys.path.insert(0, DEMO_FILES)
    import generate_checklists

    root = os.path.join(into, "CodeReviewChecklist")
    generate_checklists.write(root)
    return root


class _WorkingCopy:
    repo = "CodeReviewChecklist"

    def __init__(self, path):
        self.path = path
        self.ref = "master"
        self.commit = "d3m0003"


def scripted_response(corpus):
    """What a provider that did its job would return for this change.

    Rule identifiers are taken from the corpus that was actually read, not
    written down here - so a citation in this response is a citation of a rule
    that genuinely exists in the generated documents, and the resolution path is
    exercised rather than simulated.
    """
    logging_rule = next(
        item for item in corpus.items if "credential" in item.title.lower()
    )
    return json.dumps(
        {
            "coverage": [
                {
                    "criterion": "Quantity must be a positive integer; a request with zero or a negative quantity is rejected with a validation error.",
                    "status": "appears_addressed",
                    "evidence": "AddItem returns BadRequest when request.Quantity <= 0.",
                },
                {
                    "criterion": "Adding an unknown product returns a not-found response and does not change the cart.",
                    "status": "appears_addressed",
                    "evidence": "A null product returns NotFound before the cart is loaded.",
                },
                {
                    "criterion": "Adding a product already in the cart increments the quantity of the existing line instead of appending a second line.",
                    "status": "appears_addressed",
                    "evidence": "The existing-line branch increments existing.Quantity.",
                },
                {
                    "criterion": "The system must not allow adding more items than are available in stock; a request exceeding available stock is rejected.",
                    "status": "not_addressed",
                    "evidence": "Nothing in the diff reads product.Stock; no quantity is compared against it.",
                },
                {
                    "criterion": "The cart total is recalculated after a successful add, before the cart is saved.",
                    "status": "appears_addressed",
                    "evidence": "cart.Recalculate() is called before _carts.Save(cart).",
                },
                {
                    "criterion": "A shopper can remove a single line from the cart without emptying it.",
                    "status": "not_addressed",
                    "evidence": "This change adds an endpoint only; removal is untouched.",
                },
            ],
            "checklist_violations": [
                {
                    "rule_id": "SEC-WEB-01",
                    "item": "Never build a SQL statement by concatenating user input",
                    "issue": "request.ProductId is concatenated into the product lookup, so a crafted identifier changes the statement.",
                    "file": CONTROLLER_PATH,
                    "line": 43,
                },
                {
                    "rule_id": "SEC-WEB-02",
                    "item": "Never write a credential or token value to a log",
                    "issue": "The bearer token is written to the information log on every call.",
                    "file": CONTROLLER_PATH,
                    "line": 40,
                },
                {
                    "rule_id": logging_rule.item_id,
                    "item": logging_rule.title,
                    "issue": "The same call writes the caller's token into the application log.",
                    "file": CONTROLLER_PATH,
                    "line": 40,
                },
                {
                    "rule_id": "API-02",
                    "item": "Business rules stated in the linked story are enforced in code",
                    "issue": "The stock limit required by acceptance criterion 4 is never enforced.",
                    "file": CONTROLLER_PATH,
                    "line": 54,
                },
                {
                    # Deliberate: no such rule exists in the applied corpus. The
                    # run must report it and post nothing, because a citation
                    # nobody can look up is worse than no citation at all.
                    "rule_id": "SEC-WEB-99",
                    "item": "Rotate database credentials quarterly",
                    "issue": "Invented by the provider; matches no rule that was applied.",
                    "file": CONTROLLER_PATH,
                    "line": 20,
                },
            ],
            "code_issues": [
                {
                    "severity": "medium",
                    "issue": "User.Identity.Name is dereferenced without checking that the caller is authenticated.",
                    "file": CONTROLLER_PATH,
                    "line": 51,
                }
            ],
            "summary": "The change implements four of six acceptance criteria and violates four checklist rules.",
        }
    )


def configure(monkeypatch_env, checklist_root):
    """The minimum configuration, with nothing that could reach a network."""
    for name, value in {
        "TFS_BASE_URL": "https://collection.invalid/tfs/Demo",
        "TFS_PROJECT": "DemoProject",
        "TFS_REPO_CODE_SAMPLE": "eShop",
        "TFS_PR_ID": "4242",
        "TFS_PAT": "not-a-real-token-value",
        "TFS_PAT_FOR_PR": "not-a-real-posting-token",
        "TFS_REPO_CODE_REVIEW_CodeReviewAgent": "CodeReviewAgent",
        "TFS_REPO_CODE_REVIEW_CodeReviewChecklist": "CodeReviewChecklist",
        "LLM_PROVIDER": "claude",
        "LLM_MODEL": "claude-sonnet-5",
        "LLM_API_KEY": "not-a-real-api-key",
        "REVIEW_AGENT_SKIP_DOTENV": "1",
    }.items():
        monkeypatch_env(name, value)


def perform(monkeypatch, workspace, threads=None, dry_run=True, quiet=True):
    """One complete review. Returns (report, client, prompts)."""
    checklist_root = generate_documents(workspace)
    configure(monkeypatch.setenv, checklist_root)

    client = DemoClient(threads=threads)
    monkeypatch.setattr(checklist_module, "_fetch", lambda *a, **k: _WorkingCopy(checklist_root))
    monkeypatch.setattr(source_fetch, "cleanup", lambda path: None)
    monkeypatch.setattr(main_module, "TfsClient", lambda config: client)

    config = load_config(dry_run_override=dry_run)
    corpus = checklist_module.obtain_corpus(config)
    response = scripted_response(corpus)

    prompts = []

    def _call_llm(prompt, _config):
        prompts.append(prompt)
        return response

    monkeypatch.setattr(main_module, "call_llm", _call_llm)
    report = main_module.run_review(config, main_module.PhaseLog(enabled=not quiet))
    return report, client, prompts


def findings_of(report):
    """The comparable shape of a run's result, for the repeatability check."""
    return {
        "rules": sorted(
            (v.rule_id, v.source, v.file, v.line) for v in report.checklist_violations
        ),
        "criteria": sorted((c.ordinal, c.status) for c in report.coverage),
        "false_claims": sorted(c.claimed_text for c in report.false_coverage_claims),
        "code_issues": sorted((i.severity, i.file, i.line) for i in report.code_issues),
        "dropped_citations": sorted(report.dropped_citations),
        "documents": sorted(
            (d.filename, d.status, d.rule_count) for d in report.inventory.documents
        ),
    }


class _Monkeypatch:
    """The two things `perform` needs from pytest, for a run outside pytest."""

    def __init__(self):
        self._undo = []

    def setenv(self, name, value):
        self._undo.append((os.environ, name, os.environ.get(name)))
        os.environ[name] = value

    def setattr(self, target, name, value):
        self._undo.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def undo(self):
        for target, name, previous in reversed(self._undo):
            if target is os.environ:
                if previous is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = previous
            else:
                setattr(target, name, previous)
        self._undo = []


def main(argv=None):
    """`python -m tests.demo.run` - the operator-facing entry point."""
    monkeypatch = _Monkeypatch()
    workspace = tempfile.mkdtemp(prefix="review-demo-")
    try:
        report, _client, _prompts = perform(monkeypatch, workspace, quiet=False)
    finally:
        monkeypatch.undo()

    print()
    print("=" * 78)
    print("SELF-CONTAINED DEMONSTRATION - no server, no credential, no provider")
    print("=" * 78)
    for line in report.inventory.reductions:
        print(f"  reduction: {line}")
    print()
    print(f"  documents found      {len(report.inventory.documents)}")
    print(f"  rules applied        {report.inventory.rules_applied}")
    print(f"  criteria judged      {report.inventory.criteria_judged}")
    print(f"  checklist findings   {len(report.checklist_violations)}")
    print(f"  dropped citations    {len(report.dropped_citations)}")
    print(f"  false coverage claim {len(report.false_coverage_claims)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
