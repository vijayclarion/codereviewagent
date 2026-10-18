"""T020 - HTML to plain text, and criteria enumeration."""

import pytest

from review_agent.textutil import html_to_text, split_criteria


def test_strips_tags_and_keeps_text():
    assert html_to_text("<p>Hello <b>world</b></p>") == "Hello world"


def test_unescapes_entities():
    assert html_to_text("<div>a &amp; b &lt; c &gt; d &quot;e&quot;</div>") == 'a & b < c > d "e"'


def test_nbsp_becomes_a_space():
    assert html_to_text("<p>a&nbsp;b</p>") == "a b"


def test_br_becomes_a_newline():
    assert html_to_text("line one<br/>line two") == "line one\nline two"


def test_list_items_become_dashes():
    text = html_to_text("<ul><li>first item here</li><li>second item here</li></ul>")
    assert "- first item here" in text
    assert "- second item here" in text


def test_nested_markup_is_flattened():
    html = "<div><p>Outer <span>inner <em>deep</em></span></p></div>"
    assert html_to_text(html) == "Outer inner deep"


def test_script_and_style_content_is_dropped():
    html = "<div>keep<script>var x=1;</script><style>.a{}</style></div>"
    assert html_to_text(html) == "keep"


def test_blank_line_runs_are_collapsed():
    assert "\n\n\n" not in html_to_text("<p>a</p><p></p><p></p><p>b</p>")


def test_plain_text_passes_through_unchanged():
    assert html_to_text("just text") == "just text"


def test_idempotent():
    once = html_to_text("<p>a &amp; b</p>")
    assert html_to_text(once) == once


@pytest.mark.parametrize("value", [None, ""])
def test_empty_input(value):
    assert html_to_text(value) == ""


def test_malformed_markup_still_yields_the_text():
    # A requirement must never be lost to bad markup.
    assert "important requirement" in html_to_text("<p>important requirement<<<")


# -- split_criteria ----------------------------------------------------------


def test_splits_dash_bullets():
    text = "- first criterion here\n- second criterion here\n- third criterion here"
    assert len(split_criteria(text)) == 3


def test_splits_numbered_list():
    text = "1. first criterion here\n2. second criterion here"
    assert split_criteria(text) == ["first criterion here", "second criterion here"]


def test_continuation_lines_join_the_bullet():
    text = "- a criterion that wraps\n  onto a second line\n- another criterion here"
    result = split_criteria(text)
    assert result[0] == "a criterion that wraps onto a second line"
    assert len(result) == 2


def test_falls_back_to_paragraphs_when_no_markers():
    text = "the first requirement statement\n\nthe second requirement statement"
    assert len(split_criteria(text)) == 2


def test_drops_fragments_under_three_words():
    text = "- ok\n- this one is long enough"
    assert split_criteria(text) == ["this one is long enough"]


@pytest.mark.parametrize("value", [None, ""])
def test_split_empty(value):
    assert split_criteria(value) == []


def test_story_101_criteria_enumerate_to_five():
    """The demo story must yield exactly five criteria - SC-001 depends on it."""
    html = (
        "<ul>"
        "<li>Quantity must be a positive integer; zero or negative is rejected.</li>"
        "<li>Adding an unknown product returns a not-found response.</li>"
        "<li>Adding a product already in the cart increments the existing line.</li>"
        "<li>The system must not allow adding more items than are in stock.</li>"
        "<li>The cart total is recalculated after a successful add.</li>"
        "</ul>"
    )
    assert len(split_criteria(html_to_text(html))) == 5
