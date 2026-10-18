"""Regression: preview mode must survive a non-UTF-8 console.

Found the hard way. The rendered feedback carries emoji and en dashes; a Windows
console defaults to cp1252, which is the target platform for the build agent. The
first real dry run died with UnicodeEncodeError partway through the summary -
after the phase log had already reported success, which is the worst possible
place to fail.

pytest's capsys is UTF-8, so no ordinary test would have caught this. Hence a
deliberately hostile stream.
"""

import io

from review_agent import config as cfg
from review_agent import output_layer


class Cp1252Stream:
    """A stream that behaves like a legacy Windows console.

    Deliberately not a TextIOBase subclass: `encoding` is read-only there, and
    what matters is that emit() copes with any file-like object whose encoding
    cannot represent the content - and that has no reconfigure() to rescue it.
    """

    def __init__(self):
        self._buffer = io.BytesIO()
        self.encoding = "cp1252"

    def write(self, text):
        self._buffer.write(text.encode("cp1252"))  # raises on emoji
        return len(text)

    def flush(self):
        pass

    def value(self):
        return self._buffer.getvalue().decode("cp1252")


def test_emit_survives_a_cp1252_stream():
    stream = Cp1252Stream()
    cfg.emit("\U0001F916 AI Code Review — done", stream=stream)
    assert "AI Code Review" in stream.value(), "the words must survive"


def test_the_full_summary_renders_to_a_cp1252_stream():
    from review_agent.models import (
        ChecklistViolation,
        CoverageEntry,
        FalseCoverageClaim,
        PullRequestContext,
        ReviewReport,
        SkippedFile,
        WorkItem,
    )

    report = ReviewReport(
        coverage=(
            CoverageEntry(criterion="a criterion", status="appears_addressed",
                          evidence="yes", ordinal=1),
            CoverageEntry(criterion="another criterion", status="not_addressed",
                          evidence="no", ordinal=2),
        ),
        checklist_violations=(
            ChecklistViolation(item="rule", source="c.md", issue="broken", file="a.cs", line=3),
        ),
        false_coverage_claims=(
            FalseCoverageClaim(criterion="another criterion", claimed_text="claimed",
                               status="not_addressed"),
        ),
        summary="Summary text.",
        skipped=(SkippedFile(path="x.json", reason="excluded", detail="matched *.json"),),
    )
    markdown = output_layer.render_summary(
        report,
        (WorkItem(id=101, title="Story"),),
        PullRequestContext(pr_id=1, iteration_id=2),
    )
    stream = Cp1252Stream()
    cfg.emit(markdown, stream=stream)
    rendered = stream.value()
    for expected in ("AI Code Review", "False coverage claim", "a criterion", "x.json"):
        assert expected in rendered


def test_degraded_summary_renders_to_a_cp1252_stream():
    stream = Cp1252Stream()
    cfg.emit(output_layer.render_degraded_summary("provider unreachable"), stream=stream)
    assert "could not complete" in stream.value()


def test_prepare_console_is_idempotent_and_safe():
    cfg.prepare_console()
    cfg.prepare_console()
    cfg.emit("plain text still works")


# --------------------------------------------------------------------------
# Feature 002: the real checklist corpus, not hypothetical glyphs.
#
# The Word standards documents in CodeReviewChecklist head their commentary
# blocks with U+2139 and U+2716, and typeset rule titles with em dashes and
# curly quotes. Checklist text reaches the console through findings, so a rule
# quoted verbatim must not kill the run on a cp1252 terminal. Probing those
# documents during planning did exactly that (T008).
# --------------------------------------------------------------------------

CHECKLIST_GLYPHS = "ℹ✖—’“”"


def test_real_checklist_glyphs_survive_a_cp1252_stream():
    stream = Cp1252Stream()
    cfg.emit(
        "ℹ  PROVENANCE — SEC-WEB-01 Prevention of Cross-Site Scripting (XSS)\n"
        "✖  EXPLOIT SCENARIO: a claimant’s “description” field is stored raw.",
        stream=stream,
    )
    rendered = stream.value()
    assert "SEC-WEB-01" in rendered, "the rule identifier must survive"
    assert "EXPLOIT SCENARIO" in rendered
    assert "description" in rendered


def test_every_checklist_glyph_is_individually_safe():
    for glyph in CHECKLIST_GLYPHS:
        stream = Cp1252Stream()
        cfg.emit(f"rule text {glyph} more text", stream=stream)
        rendered = stream.value()
        assert "rule text" in rendered
        assert "more text" in rendered
