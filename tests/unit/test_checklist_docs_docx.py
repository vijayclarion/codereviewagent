"""T036 - reading rules out of the Word standards documents.

The documents look like prose and are not. Both real ones introduce every rule
with a single-row table carrying a stable identifier - SEC-WEB-01, DEV-SEC-01 -
and say so in their own "How to Use This Guide" section. Those identifiers are
what a finding cites, so the reader uses them in preference to anything it could
derive, and the tolerant scan exists only for a document that has none.
"""

from review_agent import checklist_docs as docs
from tests.fixtures import docs_builder as build


# -- marked rules (the real shape) ------------------------------------------


def test_rule_identifiers_come_from_the_document():
    doc, items = docs.read("Guidelines.docx", build.marked_rules_document(count=2))
    assert doc.status == "read"
    assert [i.item_id for i in items] == ["SEC-WEB-01", "SEC-WEB-02"]
    assert all(not i.derived_id for i in items), (
        "the documents supply citable identifiers; deriving one would throw that away"
    )


def test_the_rule_title_is_captured_without_its_identifier():
    _, items = docs.read("Guidelines.docx", build.marked_rules_document(count=1))
    assert items[0].title == "Rule title 1"


def test_severity_is_taken_from_the_document_never_invented():
    _, items = docs.read("Guidelines.docx", build.marked_rules_document(count=1))
    assert items[0].severity == "HIGH"


def test_the_enclosing_section_is_recorded():
    _, items = docs.read(
        "Guidelines.docx", build.marked_rules_document(count=1, section="2. API Security")
    )
    assert items[0].section == "2. API Security"


def test_the_requirement_body_is_kept():
    _, items = docs.read("Guidelines.docx", build.marked_rules_document(count=1))
    assert "Requirement body for rule 1" in items[0].detail


def test_commentary_blocks_are_dropped():
    """PROVENANCE and EXPLOIT SCENARIO are three quarters of the text and none of the rule."""
    _, items = docs.read("Guidelines.docx", build.marked_rules_document(count=1))
    assert "PROVENANCE" not in items[0].detail
    assert "EXPLOIT SCENARIO" not in items[0].detail


def test_navigation_and_traceability_sections_contribute_no_rules():
    _, items = docs.read("Guidelines.docx", build.marked_rules_document(count=2))
    ids = [i.item_id for i in items]
    assert "SEC-WEB-99" not in ids, "Appendix A is traceability, not a rule"
    assert not any("Contents" in (i.title or "") for i in items)


def test_each_rule_stops_at_the_next_rule():
    _, items = docs.read("Guidelines.docx", build.marked_rules_document(count=2))
    assert "rule 2" not in items[0].detail, "a rule must not absorb the next one's body"


# -- the tolerant fallback (FR-017b) ----------------------------------------


def test_a_document_without_identifiers_is_still_read():
    doc, items = docs.read("Guidance.docx", build.unmarked_document())
    assert doc.status == "read"
    assert items, "a document with no identifiers must not be silently useless"
    assert all(i.derived_id for i in items)


def test_the_fallback_derives_identifiers_from_the_filename():
    _, items = docs.read("Guidance.docx", build.unmarked_document())
    assert items[0].item_id.startswith("Guidance:")


def test_the_fallback_keeps_list_items_and_table_rows():
    _, items = docs.read("Guidance.docx", build.unmarked_document())
    titles = [i.title for i in items]
    assert "Always validate input before using it." in titles
    assert "Prefer asynchronous IO for network calls." in titles


def test_the_fallback_ignores_fragments_too_short_to_be_rules():
    _, items = docs.read("Guidance.docx", build.unmarked_document())
    assert "short" not in [i.title for i in items]


# -- T014: the tolerant path's identifiers survive an edit above them -------


def _guidance(rules):
    body = build._para("Coding Guidance", "Heading1") + "".join(
        build._para(rule, "ListParagraph") for rule in rules
    )
    return build.docx(body)


def _ids(rules):
    _, items = docs.read("Guidance.docx", _guidance(rules))
    return {i.title: i.item_id for i in items}


def test_inserting_a_rule_leaves_the_others_identifiers_unchanged():
    """Was an ordinal counter, which renumbered everything below an insertion."""
    before = _ids(["Always validate input before using it.", "Never log a token value."])
    after = _ids(
        [
            "Always validate input before using it.",
            "Escape every value rendered into a template.",
            "Never log a token value.",
        ]
    )
    assert after["Never log a token value."] == before["Never log a token value."]


def test_reordering_rules_leaves_every_identifier_unchanged():
    rules = ["Always validate input before using it.", "Never log a token value."]
    assert _ids(rules) == _ids(list(reversed(rules)))


# -- failure ----------------------------------------------------------------


def test_a_document_stating_no_rules_is_reported_as_such():
    doc, items = docs.read("Empty.docx", build.empty_document())
    assert doc.status == "no_rules"
    assert items == ()


def test_a_corrupt_document_is_skipped_with_a_reason():
    doc, items = docs.read("Broken.docx", build.corrupt_bytes())
    assert doc.status == "skipped"
    assert doc.skip_reason
    assert items == ()


def test_a_password_protected_document_says_so():
    doc, _ = docs.read("Locked.docx", build.encrypted_like_bytes())
    assert doc.status == "skipped"
    assert "password" in doc.skip_reason.lower() or "encrypted" in doc.skip_reason.lower()


def test_a_skipped_document_can_never_lack_a_reason():
    """The entity itself refuses an unexplained skip - Principle VII, enforced."""
    import pytest

    from review_agent.models import ChecklistDocument

    with pytest.raises(ValueError):
        ChecklistDocument(filename="x.docx", status="skipped")
