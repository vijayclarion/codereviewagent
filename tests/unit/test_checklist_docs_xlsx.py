"""T035 - reading rules out of the spreadsheets the quality leads actually keep.

Every shape asserted here was observed in CodeReviewChecklist on 2026-09-15: the
merged banner above the header, the two metadata sheets, the disagreement about
column names between documents, and - the one that changed the specification -
a `#` column that exists and is empty in every data row.
"""

from review_agent import checklist_docs as docs
from tests.fixtures import docs_builder as build


def read(name, data):
    return docs.read(name, data)


# -- sheet qualification ----------------------------------------------------


def test_the_header_row_is_found_below_a_banner_row():
    doc, items = read("API.xlsx", build.xlsx([build.checklist_sheet_with_ids(count=3)]))
    assert doc.status == "read"
    assert len(items) == 3, "row 1 is a banner; the header is row 2"
    assert items[0].title == "Rule number 1"


def test_a_metadata_sheet_contributes_nothing_and_is_named():
    doc, items = read(
        "API.xlsx",
        build.xlsx([build.metadata_sheet(), build.checklist_sheet_with_ids(count=2)]),
    )
    assert len(items) == 2
    assert "Document Control" in doc.sheets_ignored, (
        "a sheet that was ignored must be visible, not silently absent"
    )


def test_a_lookups_sheet_is_ignored_too():
    doc, _ = read(
        "API.xlsx",
        build.xlsx([build.checklist_sheet_with_ids(count=1), build.lookups_sheet()]),
    )
    assert "lookups" in doc.sheets_ignored


def test_a_workbook_with_no_rule_column_anywhere_yields_no_rules():
    doc, items = read("Meta.xlsx", build.xlsx([build.metadata_sheet(), build.lookups_sheet()]))
    assert items == ()
    assert doc.status == "no_rules", (
        "readable but ruleless is a content problem, not a technical one"
    )


# -- identifiers ------------------------------------------------------------


def test_a_populated_identifier_column_is_used_verbatim():
    _, items = read("API.xlsx", build.xlsx([build.checklist_sheet_with_ids(count=3)]))
    assert [i.item_id for i in items] == ["1", "2", "3"]
    assert all(not i.derived_id for i in items)


def test_an_empty_identifier_column_derives_a_stable_identifier():
    """The NFR document's shape. Requiring an id here would reject a real checklist."""
    _, items = read(
        "Non Functional Requirements Checklist v2.0.xlsx",
        build.xlsx([build.checklist_sheet_without_ids(count=2)]),
    )
    assert len(items) == 2
    assert all(i.derived_id for i in items)
    # Feature 003: derived from the rule's own content, not from its row number.
    # The document and sheet still lead, because a person reads this in a comment.
    prefix = "Non Functional Requirements Checklist v2.0:Arch Quality Attributes:"
    assert items[0].item_id.startswith(prefix)
    assert len(items[0].item_id[len(prefix) :]) == 8


def test_a_derived_identifier_is_stable_across_reads():
    data = build.xlsx([build.checklist_sheet_without_ids(count=2)])
    first = [i.item_id for i in read("NFR.xlsx", data)[1]]
    second = [i.item_id for i in read("NFR.xlsx", data)[1]]
    assert first == second, "a citation that changes between runs is not a citation"


# -- T014: identifiers survive an editor tidying the document ---------------
#
# After feature 003 an identifier is what a posted comment is recognised by, so
# a row inserted above a rule must not resurface every comment below it.


def _sheet(titles, sheet="Arch Quality Attributes"):
    rows = [
        ["", "Solution Architecture Quality Attributes", "", "", "", ""],
        ["#", "Category", "Sub-Category", "Checklist Item", "Comply?", "Comments"],
    ]
    for index, title in enumerate(titles, start=1):
        rows.append(["", "Architecture", f"Sub {index}", title, "", ""])
    return (sheet, rows)


def _ids(titles):
    data = build.xlsx([_sheet(titles)])
    return {i.title: i.item_id for i in read("NFR.xlsx", data)[1]}


def test_inserting_a_row_leaves_every_other_identifier_unchanged():
    before = _ids(["Rule one", "Rule two", "Rule three"])
    after = _ids(["Rule one", "Brand new rule", "Rule two", "Rule three"])
    for title in ("Rule one", "Rule two", "Rule three"):
        assert after[title] == before[title], f"{title} changed when a row was inserted above it"


def test_deleting_a_row_leaves_every_other_identifier_unchanged():
    before = _ids(["Rule one", "Rule two", "Rule three"])
    after = _ids(["Rule one", "Rule three"])
    assert after["Rule three"] == before["Rule three"]


def test_reordering_rules_leaves_every_identifier_unchanged():
    before = _ids(["Rule one", "Rule two", "Rule three"])
    after = _ids(["Rule three", "Rule one", "Rule two"])
    assert after == before


def test_rewording_a_rule_changes_only_that_rules_identifier():
    """Correct, and deliberate: a reworded rule is a different rule."""
    before = _ids(["Rule one", "Rule two"])
    after = _ids(["Rule one", "Rule two, restated"])
    assert after["Rule one"] == before["Rule one"]
    assert "Rule two, restated" not in before


# -- column roles -----------------------------------------------------------


def test_the_rule_column_is_recognised_under_either_name():
    _, with_title = read("A.xlsx", build.xlsx([build.checklist_sheet_with_ids(count=1)]))
    _, with_item = read("B.xlsx", build.xlsx([build.checklist_sheet_without_ids(count=1)]))
    assert with_title[0].title == "Rule number 1"
    assert with_item[0].title == "Unidentified rule 1"


def test_answer_columns_never_become_rules():
    _, items = read("API.xlsx", build.xlsx([build.checklist_sheet_with_ids(count=2)]))
    titles = [i.title for i in items]
    assert not any("Comply" in t or "Comments" in t for t in titles)


def test_detail_and_section_are_captured():
    _, items = read("API.xlsx", build.xlsx([build.checklist_sheet_with_ids(count=1)]))
    assert items[0].detail == "Detail for 1"
    assert items[0].section == "API Security Checklist"


def test_the_source_document_is_recorded_for_citation():
    _, items = read("API Security Checklist_v3.0.xlsx", build.xlsx([build.checklist_sheet_with_ids(count=1)]))
    assert items[0].documents == ("API Security Checklist_v3.0.xlsx",)
    assert items[0].source_label == "API Security Checklist_v3.0.xlsx"


# -- rows -------------------------------------------------------------------


def test_rows_with_no_rule_text_are_skipped():
    sheet = (
        "Checklist",
        [
            ["", "Banner", "", ""],
            ["#", "Title", "Description", "Comply?"],
            ["1", "A real rule", "", ""],
            ["", "", "", ""],
            ["2", "Another real rule", "", ""],
        ],
    )
    _, items = read("X.xlsx", build.xlsx([sheet]))
    assert [i.title for i in items] == ["A real rule", "Another real rule"]


def test_long_rule_text_is_trimmed_rather_than_dropped():
    long_text = "x" * 900
    sheet = (
        "Checklist",
        [["#", "Title", "Description"], ["1", long_text, long_text]],
    )
    _, items = read("X.xlsx", build.xlsx([sheet]))
    assert len(items) == 1
    assert len(items[0].title) <= docs.MAX_DETAIL_CHARS
    assert items[0].title.endswith("…")


# -- failure ----------------------------------------------------------------


def test_a_corrupt_workbook_is_skipped_with_a_reason():
    doc, items = read("broken.xlsx", build.corrupt_bytes())
    assert doc.status == "skipped"
    assert doc.skip_reason
    assert items == ()


def test_an_unsupported_extension_is_skipped_with_a_reason():
    doc, items = read("rules.pdf", b"%PDF-1.4")
    assert doc.status == "skipped"
    assert "unsupported format" in doc.skip_reason
    assert items == ()


def test_reading_never_raises_for_bad_content():
    for name, data in (
        ("a.xlsx", b""),
        ("b.xlsx", b"not a zip"),
        ("c.docx", build.corrupt_bytes()),
    ):
        doc, _ = read(name, data)
        assert doc.status == "skipped", f"{name} should be reported, not raised"
