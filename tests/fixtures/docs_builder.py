"""Generate checklist documents in the shapes the real corpus actually uses.

Generated rather than copied (research R13). The real documents are internal
Najm standards, 38-63 KB each, and this repository is cloned onto developer
machines on every run - committing five internal documents to it would be a
poor trade for test coverage. Generating them also lets a test exercise the
empty-identifier case on purpose, rather than depending on one real document
keeping its current shape.

Each builder reproduces one shape found in the corpus on 2026-09-15:

    banner_then_header   row 1 a merged title, row 2 the real header
    populated_ids        a `#` column with values        (API checklists)
    empty_ids            a `#` column that is always blank (NFR checklist)
    metadata_sheet       `Document Control` / `lookups`  (all three)
    marked_rules         SEC-WEB-01 style rule tables    (both .docx)
    unmarked_document    prose with no identifiers       (the FR-017b fallback)
"""

import io
import zipfile

DOCX_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)

DOCX_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)

W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


# --------------------------------------------------------------------------
# Spreadsheets
# --------------------------------------------------------------------------


def xlsx(sheets):
    """Build a workbook. `sheets` is [(title, [[cell, ...], ...]), ...]."""
    import openpyxl

    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for title, rows in sheets:
        sheet = workbook.create_sheet(title=title[:31])
        for row in rows:
            sheet.append(list(row))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def checklist_sheet_with_ids(title="API Security Checklist", count=3):
    """Banner row, header row 2, populated `#` - the API checklists' shape."""
    rows = [["", title, "", "", ""], ["#", "Title", "Description", "Comply?", "Comments"]]
    for index in range(1, count + 1):
        rows.append([str(index), f"Rule number {index}", f"Detail for {index}", "", ""])
    return (title, rows)


def checklist_sheet_without_ids(title="Arch Quality Attributes", count=3):
    """The NFR shape: a `#` column present but empty in every data row."""
    rows = [
        ["", "Solution Architecture Quality Attributes", "", "", "", ""],
        ["#", "Category", "Sub-Category", "Checklist Item", "Comply?", "Comments"],
    ]
    for index in range(1, count + 1):
        rows.append(
            ["", "Architecture", f"Sub {index}", f"Unidentified rule {index}", "", ""]
        )
    return (title, rows)


def metadata_sheet(title="Document Control"):
    """No rule-text column anywhere - must contribute nothing and be named."""
    return (
        title,
        [
            [], [], [], [], [],
            ["", "Item", "Description", "", ""],
            ["", "Document Title:", "Some Checklist", "", ""],
            ["", "Version:", "3.0", "", ""],
        ],
    )


def lookups_sheet():
    return ("lookups", [["Yes"], ["No"], ["N/A"]])


# --------------------------------------------------------------------------
# Word documents
# --------------------------------------------------------------------------


def _para(text, style=None):
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{style_xml}<w:r><w:t>{text}</w:t></w:r></w:p>"


def _table(rows):
    body = ""
    for cells in rows:
        cells_xml = "".join(
            f"<w:tc><w:p><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>" for cell in cells
        )
        body += f"<w:tr>{cells_xml}</w:tr>"
    return f"<w:tbl>{body}</w:tbl>"


def docx(body_xml):
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W_NS}><w:body>{body_xml}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", DOCX_CONTENT_TYPES)
        archive.writestr("_rels/.rels", DOCX_RELS)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def marked_rules_document(count=2, section="1. Web Security"):
    """The real .docx shape: rule-ID tables, severity cells, commentary blocks."""
    parts = [
        _para("Contents", "Heading1"),
        _para("1. Web Security ...... 3"),
        _para("How to Use This Guide", "Heading1"),
        _para("Rule ID and Title - a stable identifier you can cite.", "ListParagraph"),
        _para(section, "Heading1"),
    ]
    for index in range(1, count + 1):
        parts.append(_table([[f"SEC-WEB-0{index}  Rule title {index}", "HIGH"]]))
        parts.append(_table([["&#8505;  PROVENANCE Every rule traces to a register entry."]]))
        parts.append(_para(f"Requirement body for rule {index}."))
        parts.append(_table([["&#10006;  EXPLOIT SCENARIO A field is stored raw."]]))
    parts.append(_para("Appendix A - Rule-to-Gap Traceability", "Heading1"))
    parts.append(_table([["SEC-WEB-99  Traceability only, not a rule", ""]]))
    return docx("".join(parts))


def unmarked_document():
    """No identifiers anywhere - exercises the FR-017b tolerant fallback."""
    return docx(
        "".join(
            [
                _para("Contents", "Heading1"),
                _para("Coding Guidance", "Heading1"),
                _para("Always validate input before using it.", "ListParagraph"),
                _para("Never log a credential or a token value.", "ListParagraph"),
                _para("short", "ListParagraph"),
                _table([["Prefer asynchronous IO for network calls."]]),
            ]
        )
    )


def empty_document():
    """Parses cleanly, states no rules - must be `no_rules`, not `skipped`."""
    return docx(_para("Contents", "Heading1") + _para("Nothing to see here."))


def corrupt_bytes():
    return b"PK\x03\x04 this is not a real office document at all"


def encrypted_like_bytes():
    """A valid zip with no document part - what an encrypted file looks like."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("EncryptedPackage", b"\x00\x01\x02")
    return buffer.getvalue()
