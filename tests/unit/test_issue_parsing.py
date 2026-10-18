"""T034 (feature 007) - acceptance criteria from a GitHub issue body."""

import pytest

from review_agent.models import WorkItem, split_issue_body


def _issue(body, number=7, **extra):
    return dict({"number": number, "title": "Add item", "state": "open", "body": body}, **extra)


CRITERIA = [
    "Quantity must be a positive integer for every request.",
    "Unknown products return a not-found response.",
    "Stock limits are enforced on every add request.",
]


@pytest.mark.parametrize(
    "markers",
    [("- [ ] ", "- [x] ", "- [X] "), ("- ", "* ", "- "), ("1. ", "2. ", "3. ")],
    ids=["checkboxes", "bullets", "numbered"],
)
def test_checkbox_bullet_and_numbered_lists(markers):
    body = "## Acceptance criteria\n\n" + "\n".join(m + c for m, c in zip(markers, CRITERIA))
    item = WorkItem.from_issue(_issue(body))
    assert [c.text for c in item.criteria] == CRITERIA
    assert [c.ordinal for c in item.criteria] == [1, 2, 3]
    assert all(c.work_item_id == 7 for c in item.criteria)


@pytest.mark.parametrize("heading", ["## Acceptance criteria", "### acceptance Criteria", "# ACCEPTANCE CRITERIA"])
def test_heading_case_and_level(heading):
    item = WorkItem.from_issue(_issue(f"{heading}\n- [ ] {CRITERIA[0]}"))
    assert [c.text for c in item.criteria] == [CRITERIA[0]]


def test_section_stops_at_the_next_heading_and_description_keeps_the_rest():
    body = (
        "## Description\n\nAs a shopper I want this.\n\n"
        f"## Acceptance criteria\n- [ ] {CRITERIA[0]}\n\n"
        "### Notes\n- this is not a criterion at all"
    )
    item = WorkItem.from_issue(_issue(body))
    assert [c.text for c in item.criteria] == [CRITERIA[0]]
    assert "As a shopper" in item.description and "Notes" in item.description
    assert "Acceptance criteria" not in item.description
    assert item.acceptance_criteria == f"- [ ] {CRITERIA[0]}"


def test_nested_bullets_fold_into_their_parent():
    body = f"## Acceptance criteria\n- [ ] {CRITERIA[0]}\n  - including zero and negatives\n- {CRITERIA[1]}"
    item = WorkItem.from_issue(_issue(body))
    assert [c.text for c in item.criteria] == [
        f"{CRITERIA[0]} including zero and negatives",
        CRITERIA[1],
    ]


def test_without_a_section_criteria_come_from_the_description():
    item = WorkItem.from_issue(_issue(f"Some intro.\n\n- {CRITERIA[0]}\n- {CRITERIA[1]}"))
    assert item.acceptance_criteria == ""
    assert [c.text for c in item.criteria] == CRITERIA[:2]


def test_metadata_and_ordinal_start():
    item = WorkItem.from_issue(
        _issue(f"## Acceptance criteria\n- {CRITERIA[0]}", number=9, labels=[{"name": "user-story"}, "x"]),
        ordinal_start=4,
    )
    assert (item.id, item.work_item_type, item.state) == (9, "GitHub issue", "open")
    assert item.tags == ("user-story", "x")
    assert item.criteria[0].ordinal == 4


def test_split_issue_body_handles_crlf_and_absence():
    assert split_issue_body("") == ("", "")
    desc, section = split_issue_body("Intro\r\n## Acceptance criteria\r\n- one two three\r\n")
    assert desc == "Intro" and section == "- one two three"
