"""T021 (feature 007) - the GitHub API is spoken in one module.

contracts/platform-client.md "Boundary". The markers are fragments of GitHub's
wire format; finding one anywhere else means GitHub knowledge leaked out of
`github_client.py`.
"""

from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[2] / "review_agent"

MARKERS = (
    "api.github.com",
    "/pulls/",
    "/repos/",
    "graphql",
    "closingIssuesReferences",
    "X-GitHub-Api-Version",
)

#: config.py names the default API URL and derives the GraphQL endpoint from it.
ALLOWED = {"github_client.py": MARKERS, "config.py": ("api.github.com", "graphql")}


def test_github_wire_format_stays_in_github_client():
    offenders = []
    for path in sorted(AGENT_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        allowed = ALLOWED.get(path.name, ())
        for marker in MARKERS:
            if marker in text and marker not in allowed:
                offenders.append(f"{path.name}:{marker}")
    assert not offenders, "GitHub wire format leaked: " + ", ".join(offenders)


def test_github_client_is_imported_only_by_the_platform_seam():
    importers = [
        path.name
        for path in sorted(AGENT_DIR.rglob("*.py"))
        if path.name not in ("github_client.py", "platform.py")
        and "github_client" in path.read_text(encoding="utf-8")
    ]
    assert not importers, "github_client imported outside platform.py: " + ", ".join(importers)
