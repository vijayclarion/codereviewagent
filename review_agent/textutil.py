"""HTML to plain text, using only the standard library.

TFS returns work-item titles, descriptions, and acceptance criteria as HTML. Left
as-is, the model would spend its attention on markup instead of requirements
(FR-009). ``bs4`` would do this in one line, but a fourth runtime dependency on a
locked-down build agent is a worse trade than forty lines of ``html.parser``.
"""

import html
import re
from html.parser import HTMLParser

# Tags whose close should end the line.
_BLOCK_TAGS = {
    "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "section", "article", "ul", "ol", "table",
}
_SKIP_CONTENT = {"script", "style"}


class _Stripper(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._out = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_CONTENT:
            self._skip_depth += 1
        elif tag == "br":
            self._out.append("\n")
        elif tag == "li":
            self._out.append("\n- ")
        elif tag in _BLOCK_TAGS:
            self._out.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_CONTENT:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._out.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self._out.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._out.append(data)

    def text(self):
        return "".join(self._out)


def html_to_text(raw):
    """Reduce an HTML fragment to readable plain text.

    Idempotent on input that is already plain text, so it is safe to apply to a
    field whose format varies between work-item types.
    """
    if not raw:
        return ""
    stripper = _Stripper()
    try:
        stripper.feed(str(raw))
        stripper.close()
        text = stripper.text()
    except Exception:
        # Malformed markup must not lose the requirement text - fall back to a
        # blunt tag strip rather than returning nothing.
        text = re.sub(r"<[^>]+>", " ", str(raw))

    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("​", "")
    # Collapse runs of spaces/tabs, then runs of blank lines.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_criteria(text):
    """Enumerate acceptance criteria from a plain-text block.

    Tries markdown/HTML list markers first, then numbered lines, then
    blank-line-separated paragraphs. Entries under three words are dropped as
    fragments rather than presented as criteria.

    Advisory only: the model also receives the full criteria text, so a bad split
    costs granularity in the coverage map, never information.
    """
    if not text:
        return []

    lines = [line.strip() for line in text.splitlines()]
    bullets = []
    current = None
    for line in lines:
        match = re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)$", line)
        if match:
            if current:
                bullets.append(current)
            current = match.group(1).strip()
        elif current is not None and line:
            current = f"{current} {line}"
        elif current is not None and not line:
            bullets.append(current)
            current = None
    if current:
        bullets.append(current)

    if not bullets:
        bullets = [
            block.strip().replace("\n", " ")
            for block in re.split(r"\n\s*\n", text)
            if block.strip()
        ]

    return [b for b in (b.strip() for b in bullets) if len(b.split()) >= 3]
