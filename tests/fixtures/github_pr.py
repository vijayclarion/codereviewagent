"""T015 (feature 007) - a GitHub pull request, as the GitHub API reports it.

The same cart change as `pr_demo`, so a GitHub run and a TFS run can be compared
finding for finding. Repository `acme/shop`, pull request #12, linked issue #7.
"""

from tests.fixtures import pr_demo as demo

API = "https://api.github.com"
REPO = "acme/shop"
NUMBER = 12
HEAD = "h" * 40
TARGET = "t" * 40
MERGE_BASE = "m" * 40

CART_PATH = demo.CART_CONTROLLER_PATH.lstrip("/")
APPSETTINGS_PATH = demo.APPSETTINGS_PATH.lstrip("/")

PULL = {
    "number": NUMBER,
    "title": "Add item to cart",
    "body": (
        "Implements the cart endpoint.\n\nCloses #7\n\n"
        "## Covered\n- Quantity validation\n- Unknown product\n\n"
        "## Not in this PR\n- Stock limit\n"
    ),
    "draft": False,
    "commits": 2,
    "head": {"ref": "feature/cart", "sha": HEAD, "repo": {"full_name": REPO}},
    "base": {"ref": "master", "sha": TARGET, "repo": {"full_name": REPO}},
}

COMPARE = {"merge_base_commit": {"sha": MERGE_BASE}, "status": "ahead"}

FILES_PAGE_1 = [
    {"filename": CART_PATH, "status": "modified", "additions": 30, "deletions": 2},
]
FILES_PAGE_2 = [
    {"filename": APPSETTINGS_PATH, "status": "modified", "additions": 1, "deletions": 0},
    {"filename": "docs/unchanged.md", "status": "unchanged"},
]

CONTENTS = {
    (CART_PATH, HEAD): demo.CART_CONTROLLER_AFTER,
    (CART_PATH, MERGE_BASE): demo.CART_CONTROLLER_BEFORE,
    (APPSETTINGS_PATH, HEAD): demo.APPSETTINGS_AFTER,
    (APPSETTINGS_PATH, MERGE_BASE): "{}\n",
}

ISSUE_7 = {
    "number": 7,
    "title": "Add item to cart",
    "state": "open",
    "labels": [{"name": "user-story"}],
    "body": (
        "## Description\n\nAs a shopper I want to add an item to my cart.\n\n"
        "## Acceptance criteria\n\n"
        "- [ ] Quantity must be a positive integer; a request with zero or a negative "
        "quantity is rejected with a validation error.\n"
        "- [x] Adding an unknown product returns a not-found response and does not "
        "change the cart.\n"
        "- [ ] The system must not allow adding more items than are available in "
        "stock; a request exceeding available stock is rejected.\n"
    ),
}

GRAPHQL_LINKED = {
    "data": {
        "repository": {
            "pullRequest": {
                "closingIssuesReferences": {
                    "nodes": [{"number": 7, "repository": {"nameWithOwner": REPO}}]
                }
            }
        }
    }
}


def review_comment(comment_id, path, body):
    return {"id": comment_id, "path": path, "line": 10, "body": body}


def issue_comment(comment_id, body):
    return {"id": comment_id, "body": body}
