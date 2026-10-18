"""Write the demonstration's sample checklist documents (T048, research R12).

Generated rather than committed, for the same reason `tests/fixtures/docs_builder.py`
generates its own: the real corpus is internal Najm standards, and this repository
is cloned onto a developer's machine on every review. It also means the operator
can watch the documents being made, rather than trusting two binaries.

Run from the repository root:

    python specs/003-checklist-repo-review-demo/demo-files/generate_checklists.py OUTPUT_DIR

Four documents, chosen to exercise four different paths through the reader:

    Najm-API-Checklist.xlsx           populated identifier column, plus a second
                                      sheet that holds no rules and is ignored
    Najm-NFR-Checklist.xlsx           identifier column present and EMPTY in every
                                      row - the derived-identifier path
    Najm-Secure-Coding-Standard.docx  SEC-WEB-nn identifiers, used verbatim
    Najm-Legacy-Standard.docx         unreadable - reported as skipped, with its
                                      reason, while the other three still apply
"""

import os
import sys

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.fixtures import docs_builder as build  # noqa: E402


API_SHEET = (
    "API Checklist",
    [
        ["", "Najm API Review Checklist v3.1", "", "", ""],
        ["#", "Title", "Description", "Comply?", "Comments"],
        [
            "API-01",
            "Validate every request parameter before it is used",
            "Reject out-of-range and malformed values at the controller boundary.",
            "",
            "",
        ],
        [
            "API-02",
            "Business rules stated in the linked story are enforced in code",
            "A rule that exists only in the story is not enforced.",
            "",
            "",
        ],
        [
            "API-03",
            "Return the documented status code for every failure path",
            "Not-found, validation and conflict paths each have their own code.",
            "",
            "",
        ],
    ],
)

#: Present in all three real spreadsheets. Holds no rule column, so it is ignored
#: and reported as ignored rather than silently dropped.
DOCUMENT_CONTROL = (
    "Document Control",
    [
        ["Owner", "Quality Unit"],
        ["Version", "3.1"],
        ["Approved", "2026-08-30"],
    ],
)

NFR_SHEET = (
    "Quality Attributes",
    [
        ["", "Najm Non-Functional Requirements Checklist v2.0", "", "", "", ""],
        ["#", "Category", "Sub-Category", "Checklist Item", "Comply?", "Comments"],
        [
            "",
            "Observability",
            "Logging",
            "No credential, token or personal identifier is written to a log",
            "",
            "",
        ],
        [
            "",
            "Performance",
            "Data access",
            "A request performs no unbounded query against the catalogue",
            "",
            "",
        ],
    ],
)

SECURE_CODING_RULES = [
    (
        "SEC-WEB-01",
        "Never build a SQL statement by concatenating user input",
        "Use a parameterised query or a bound command for every value that reaches "
        "the database, without exception.",
    ),
    (
        "SEC-WEB-02",
        "Never write a credential or token value to a log",
        "Log the presence of a credential if you must, never its value. Logs are "
        "retained, shipped and read by people who are not you.",
    ),
]


def _rule_document(rules, section="1. Web Application Security"):
    """A Word document in the shape both real standards use: a single-row table
    carrying the identifier and title, then the requirement as prose."""
    body = [build._para(section, "Heading1")]
    for identifier, title, detail in rules:
        body.append(build._table([[f"{identifier} {title}"]]))
        body.append(build._para(detail))
        body.append(build._para("PROVENANCE: OWASP ASVS v4, chapter 5. (commentary - dropped on the way in)"))
    return build.docx("".join(body))


DOCUMENTS = {
    "Najm-API-Checklist.xlsx": lambda: build.xlsx([API_SHEET, DOCUMENT_CONTROL]),
    "Najm-NFR-Checklist.xlsx": lambda: build.xlsx([NFR_SHEET, DOCUMENT_CONTROL]),
    "Najm-Secure-Coding-Standard.docx": lambda: _rule_document(SECURE_CODING_RULES),
    # Deliberately unreadable. One document that cannot be read must cost that
    # document and nothing else (FR-012), and the demonstration has to show it.
    "Najm-Legacy-Standard.docx": build.corrupt_bytes,
}


def write(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    written = {}
    for filename, make in DOCUMENTS.items():
        path = os.path.join(output_dir, filename)
        data = make()
        with open(path, "wb") as handle:
            handle.write(data)
        written[filename] = len(data)
    return written


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__.strip().splitlines()[4].strip())
        return 2
    for filename, size in write(argv[0]).items():
        print(f"{filename:36} {size:>7,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
