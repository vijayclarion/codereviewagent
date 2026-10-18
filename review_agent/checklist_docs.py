"""The only module that knows what a .xlsx or .docx looks like (Principle IV).

Everything downstream receives ChecklistItem objects and never learns which
format a rule came from. That is what makes "add a third format" a change here
and nowhere else.

Both readers were written against the real corpus in CodeReviewChecklist, and
the real corpus is less tidy than a specification would like:

*Spreadsheets* put a merged title banner in row 1 and the real header in row 2,
carry two or three sheets of which only one holds rules, and disagree about
column names - `Title` in one document, `Checklist Item` in another. One of the
three has a `#` column that is present and **empty in every data row**, which is
why an identifier is derived rather than required (research R4, FR-017a).

*Word documents* look like prose but are not: every rule is introduced by a
single-row table whose first cell carries a stable identifier, and the documents
say so themselves - "Rule ID & Title, a stable identifier (e.g. SEC-WEB-01) you
can cite in code reviews". Those identifiers are exactly what a citation needs,
so they are used in preference to anything derived. A document that carries none
falls back to a tolerant scan (FR-017b).

Commentary is dropped on the way in, not at prompt time: the EXPLOIT SCENARIO
and PROVENANCE blocks are three quarters of the text and none of the rule
(research R6).
"""

import hashlib
import re
import zipfile
from xml.etree import ElementTree as ET

from .models import ChecklistDocument, ChecklistItem

# --------------------------------------------------------------------------
# Shared
# --------------------------------------------------------------------------

#: Rule text longer than this is a discussion, not a rule.
MAX_DETAIL_CHARS = 400

#: How far down a sheet to look for the header row. Row 1 is often a banner.
HEADER_SCAN_ROWS = 5

SEVERITIES = ("HIGH", "MEDIUM", "LOW")


def _norm(value):
    """Normalise a header or title for comparison."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _key(value):
    return _norm(value).lower().rstrip(":?").strip()


def _trim(text, limit=MAX_DETAIL_CHARS):
    text = _norm(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def document_format(filename):
    lowered = (filename or "").lower()
    if lowered.endswith(".xlsx"):
        return "xlsx"
    if lowered.endswith(".docx"):
        return "docx"
    return ""


def stem(filename):
    name = (filename or "").rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0]


#: Length of a derived identifier's digest. Eight hex characters over a corpus of
#: a few hundred rules leaves collision a theoretical concern, and the identifier
#: is read by people in posted comments.
DIGEST_CHARS = 8


def derive_id(filename, section, title):
    """A rule's identifier when its document supplies none (FR-009, research R4).

    Derived from the rule's own content, never from its position. A spreadsheet
    row number was the obvious choice and the wrong one: inserting a row above a
    rule changed the identifier of every rule below it, and after feature 003 an
    identifier is what a posted comment is recognised by. An editor tidying a
    checklist would have resurfaced every comment underneath the edit.

    The cost is the other direction: rewording a rule mints a new identifier. That
    is correct - a reworded rule is a different rule, and a reviewer should see it
    raised again.
    """
    raw = f"{_norm(filename)}|{_norm(section)}|{_norm(title)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:DIGEST_CHARS]


def read(filename, data):
    """Read one document. Returns (ChecklistDocument, tuple[ChecklistItem]).

    Never raises for bad content: an unreadable document is a reported outcome,
    not a failed run (FR-018). Only the whole corpus being empty stops a run.
    """
    fmt = document_format(filename)
    if not fmt:
        return (
            ChecklistDocument(
                filename=filename,
                status="skipped",
                skip_reason="unsupported format (expected .xlsx or .docx)",
            ),
            (),
        )
    try:
        if fmt == "xlsx":
            items, sheets_ignored = _read_xlsx(filename, data)
        else:
            items, sheets_ignored = _read_docx(filename, data)
    except _Unreadable as exc:
        return (
            ChecklistDocument(
                filename=filename, format=fmt, status="skipped", skip_reason=str(exc)
            ),
            (),
        )
    except Exception as exc:  # a malformed document must not take the run with it
        return (
            ChecklistDocument(
                filename=filename,
                format=fmt,
                status="skipped",
                skip_reason=f"could not be read ({type(exc).__name__})",
            ),
            (),
        )

    if not items:
        return (
            ChecklistDocument(
                filename=filename,
                format=fmt,
                status="no_rules",
                sheets_ignored=tuple(sheets_ignored),
            ),
            (),
        )
    return (
        ChecklistDocument(
            filename=filename,
            format=fmt,
            status="read",
            rule_count=len(items),
            sheets_ignored=tuple(sheets_ignored),
        ),
        tuple(items),
    )


class _Unreadable(Exception):
    """Known, explainable reasons a document cannot be read."""


# --------------------------------------------------------------------------
# Spreadsheets
# --------------------------------------------------------------------------

RULE_TEXT_HEADERS = ("checklist item", "title", "requirement", "rule", "check")
DETAIL_HEADERS = ("description", "sub-category", "subcategory", "details", "guidance")
IDENTIFIER_HEADERS = ("#", "item", "id", "ref", "no", "no.", "s.no")
SECTION_HEADERS = ("category", "area", "group")
SEVERITY_HEADERS = ("severity", "priority", "risk")
#: Answer columns. A reviewer fills these in; they are not rules.
IGNORED_HEADERS = ("comply?", "comply", "comments", "status", "owner", "evidence", "remarks")


def _role_of(header):
    key = _key(header)
    if not key:
        return None
    if key in IGNORED_HEADERS:
        return "ignored"
    if key in RULE_TEXT_HEADERS:
        return "rule"
    if key in DETAIL_HEADERS:
        return "detail"
    if key in IDENTIFIER_HEADERS:
        return "identifier"
    if key in SECTION_HEADERS:
        return "section"
    if key in SEVERITY_HEADERS:
        return "severity"
    return None


def _find_header_row(rows):
    """The first row within the scan window that names a rule-text column.

    Returns (row_index, {role: column_index}) or (None, {}). Requiring the rule
    column - and only that one - is the whole of the layout contract: it is what
    separates "a checklist sheet" from "a document-control sheet", without
    guessing at anything.
    """
    for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        roles = {}
        for column, cell in enumerate(row):
            role = _role_of(cell)
            if role and role != "ignored" and role not in roles:
                roles[role] = column
        if "rule" in roles:
            return index, roles
    return None, {}


def _cell(row, index):
    if index is None or index >= len(row):
        return ""
    return _norm(row[index])


def _read_xlsx(filename, data):
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise _Unreadable("openpyxl is not installed, so spreadsheets cannot be read") from exc

    import io

    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except zipfile.BadZipFile as exc:
        raise _Unreadable("not a readable spreadsheet (corrupt or encrypted file)") from exc

    items = []
    ignored = []
    try:
        for sheet in workbook.worksheets:
            rows = [
                [("" if cell is None else cell) for cell in row]
                for row in sheet.iter_rows(values_only=True)
            ]
            header_index, roles = _find_header_row(rows)
            if header_index is None:
                ignored.append(sheet.title)
                continue
            items.extend(_items_from_sheet(filename, sheet.title, rows, header_index, roles))
    finally:
        workbook.close()
    return items, ignored


def _items_from_sheet(filename, sheet_title, rows, header_index, roles):
    items = []
    for row in rows[header_index + 1 :]:
        title = _cell(row, roles.get("rule"))
        if not title:
            continue  # spacer or section break, not a rule
        native_id = _cell(row, roles.get("identifier"))
        derived = not native_id
        section = _cell(row, roles.get("section")) or sheet_title
        item_id = native_id or f"{stem(filename)}:{sheet_title}:{derive_id(filename, section, title)}"
        severity = _norm(_cell(row, roles.get("severity"))).upper()
        items.append(
            ChecklistItem(
                item_id=item_id,
                title=_trim(title),
                detail=_trim(_cell(row, roles.get("detail"))),
                severity=severity if severity in SEVERITIES else "",
                section=section,
                documents=(filename,),
                derived_id=derived,
            )
        )
    return items


# --------------------------------------------------------------------------
# Word documents
# --------------------------------------------------------------------------

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: SEC-WEB-01, DEV-SEC-01, ... - the identifier style both real documents use.
RULE_MARKER = re.compile(r"^([A-Z]{2,4}(?:-[A-Z]{2,6}){1,2}-\d{1,3})\s+(.{3,})$")

#: Sections that exist to navigate or trace, not to state rules.
SKIP_HEADINGS = ("contents", "how to use this guide", "table of contents", "revision history")
SKIP_HEADING_PREFIXES = ("appendix",)

#: Decorated commentary blocks. The rule is kept; the essay is not (R6).
COMMENTARY_MARKERS = ("PROVENANCE", "EXPLOIT SCENARIO", "WHY IT MATTERS", "REFERENCES")


def _text_of(element):
    return _norm("".join(node.text or "" for node in element.iter(W + "t")))


def _is_commentary(text):
    head = text[:60].upper()
    return any(marker in head for marker in COMMENTARY_MARKERS)


def _should_skip_heading(text):
    key = _key(text)
    if key in SKIP_HEADINGS:
        return True
    return any(key.startswith(prefix) for prefix in SKIP_HEADING_PREFIXES)


def _docx_body(data):
    import io

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise _Unreadable("not a readable document (corrupt or encrypted file)") from exc
    try:
        if "word/document.xml" not in archive.namelist():
            raise _Unreadable("no document body found (is the file password-protected?)")
        return ET.fromstring(archive.read("word/document.xml"))
    finally:
        archive.close()


def _blocks(document):
    """Walk the body in order, yielding (kind, text) for paragraphs and tables.

    Order matters: a rule's body is everything between its marker and the next
    one, so the reader has to see the document the way a person reads it.
    """
    body = document.find(W + "body")
    if body is None:
        return
    for child in body:
        tag = child.tag
        if tag == W + "p":
            style = child.find(".//" + W + "pStyle")
            style_value = style.get(W + "val") if style is not None else ""
            yield ("heading" if (style_value or "").startswith("Heading") else "para",
                   _text_of(child), style_value or "")
        elif tag == W + "tbl":
            for row in child.iter(W + "tr"):
                cells = [_text_of(cell) for cell in row.iter(W + "tc")]
                yield ("row", cells, "")


def _read_docx(filename, data):
    document = _docx_body(data)
    blocks = list(_blocks(document))
    items = _docx_marked_rules(filename, blocks)
    if items:
        return items, []
    # FR-017b: a document with no identifiers still deserves to be read.
    return _docx_tolerant(filename, blocks), []


def _docx_marked_rules(filename, blocks):
    items = []
    current = None
    section = ""
    skipping = False

    def close(pending):
        if pending is None:
            return
        items.append(
            ChecklistItem(
                item_id=pending["id"],
                title=_trim(pending["title"]),
                detail=_trim(" ".join(pending["body"])),
                severity=pending["severity"],
                section=pending["section"],
                documents=(filename,),
                derived_id=False,
            )
        )

    for kind, payload, _style in blocks:
        if kind == "heading":
            close(current)
            current = None
            section = payload
            skipping = _should_skip_heading(payload)
            continue
        if skipping:
            continue

        texts = payload if kind == "row" else [payload]
        marker = None
        severity = ""
        for text in texts:
            match = RULE_MARKER.match(text)
            if match:
                marker = match
            elif _norm(text).upper() in SEVERITIES:
                severity = _norm(text).upper()
        if marker:
            close(current)
            current = {
                "id": marker.group(1),
                "title": marker.group(2),
                "body": [],
                "severity": severity,
                "section": section,
            }
            continue
        if current is not None:
            for text in texts:
                if text and not _is_commentary(text):
                    current["body"].append(text)
    close(current)
    return items


def _docx_tolerant(filename, blocks):
    """Every heading, list item, and table row is a candidate rule (FR-017b)."""
    items = []
    section = ""
    seen = set()
    for kind, payload, style in blocks:
        if kind == "heading":
            section = payload
            if _should_skip_heading(payload):
                section = ""
            continue
        if not section and kind != "row":
            pass
        candidates = payload if kind == "row" else [payload]
        for text in candidates:
            text = _norm(text)
            if len(text) < 12 or _is_commentary(text):
                continue
            if kind == "para" and not (style or "").startswith(("ListParagraph", "Heading")):
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(
                ChecklistItem(
                    item_id=f"{stem(filename)}:{derive_id(filename, section, text)}",
                    title=_trim(text),
                    section=section,
                    documents=(filename,),
                    derived_id=True,
                )
            )
    return items
