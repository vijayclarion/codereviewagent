"""T031 - the JSON contract, enum enforcement, retry, and claim derivation."""

import json

import pytest

from review_agent import parser
from review_agent.errors import DegradedReview
from review_agent.models import (
    ChecklistItem,
    ChecklistViolation,
    CodeIssue,
    CombinedChecklist,
    CoverageEntry,
    DeclaredScope,
)

VALID = {
    "coverage": [
        {"criterion": "quantity must be positive", "status": "appears_addressed", "evidence": "x"}
    ],
    "checklist_violations": [],
    "code_issues": [],
    "summary": "Looks reasonable.",
}


def test_accepts_a_valid_payload():
    result = parser.parse_response(json.dumps(VALID))
    assert len(result["coverage"]) == 1
    assert result["summary"] == "Looks reasonable."


def test_tolerates_markdown_fences():
    text = "```json\n" + json.dumps(VALID) + "\n```"
    assert parser.parse_response(text)["summary"] == "Looks reasonable."


def test_tolerates_a_leading_sentence():
    text = "Here is the review:\n" + json.dumps(VALID)
    assert parser.parse_response(text)["summary"] == "Looks reasonable."


def test_rejects_a_bad_coverage_status():
    payload = json.loads(json.dumps(VALID))
    payload["coverage"][0]["status"] = "probably_fine"
    with pytest.raises(parser.ContractViolation) as exc:
        parser.parse_response(json.dumps(payload))
    assert "probably_fine" in str(exc.value)


def test_rejects_a_bad_severity():
    payload = json.loads(json.dumps(VALID))
    payload["code_issues"] = [{"severity": "catastrophic", "issue": "boom"}]
    with pytest.raises(parser.ContractViolation) as exc:
        parser.parse_response(json.dumps(payload))
    assert "catastrophic" in str(exc.value)


@pytest.mark.parametrize("key", ["coverage", "checklist_violations", "code_issues"])
def test_rejects_a_missing_array(key):
    payload = json.loads(json.dumps(VALID))
    del payload[key]
    with pytest.raises(parser.ContractViolation) as exc:
        parser.parse_response(json.dumps(payload))
    assert key in str(exc.value)


def test_rejects_an_empty_summary():
    payload = json.loads(json.dumps(VALID))
    payload["summary"] = "  "
    with pytest.raises(parser.ContractViolation):
        parser.parse_response(json.dumps(payload))


def test_rejects_non_json():
    with pytest.raises(parser.ContractViolation):
        parser.parse_response("I'd rather explain in prose.")


def test_rejects_a_json_array():
    with pytest.raises(parser.ContractViolation):
        parser.parse_response("[1, 2, 3]")


def test_ignores_unknown_extra_keys():
    """A chatty model should not cost the reader a review."""
    payload = json.loads(json.dumps(VALID))
    payload["confidence"] = 0.9
    payload["coverage"][0]["notes"] = "extra"
    assert parser.parse_response(json.dumps(payload))["summary"] == "Looks reasonable."


def test_empty_arrays_are_valid():
    payload = {
        "coverage": [],
        "checklist_violations": [],
        "code_issues": [],
        "summary": "Nothing to report.",
    }
    assert parser.parse_response(json.dumps(payload))["coverage"] == []


def test_zero_line_means_no_specific_line():
    payload = json.loads(json.dumps(VALID))
    payload["code_issues"] = [{"severity": "low", "issue": "x", "file": "a.cs", "line": 0}]
    assert parser.parse_response(json.dumps(payload))["code_issues"][0].line == 0


def test_negative_line_is_normalised_to_zero():
    payload = json.loads(json.dumps(VALID))
    payload["code_issues"] = [{"severity": "low", "issue": "x", "file": "a.cs", "line": -3}]
    assert parser.parse_response(json.dumps(payload))["code_issues"][0].line == 0


# -- retry ------------------------------------------------------------------


def test_one_retry_then_success():
    calls = []

    def call(prompt):
        calls.append(prompt)
        return "nope" if len(calls) == 1 else json.dumps(VALID)

    result, retries = parser.parse_with_retry("p", None, call, "BE STRICTER")
    assert retries == 1
    assert result["summary"] == "Looks reasonable."
    assert "BE STRICTER" in calls[1]


def test_second_failure_degrades_rather_than_returning_partial():
    def call(prompt):
        return "still not json"

    with pytest.raises(DegradedReview) as exc:
        parser.parse_with_retry("p", None, call, "STRICTER")
    assert "after a retry" in str(exc.value)


def test_no_retry_when_the_first_response_is_valid():
    calls = []

    def call(prompt):
        calls.append(prompt)
        return json.dumps(VALID)

    _, retries = parser.parse_with_retry("p", None, call, "STRICTER")
    assert retries == 0
    assert len(calls) == 1


# -- fingerprints -----------------------------------------------------------


def test_fingerprint_is_line_independent():
    a = parser.fingerprint("code", "a/b.cs", "missing null check")
    b = parser.fingerprint("code", "a/b.cs", "missing null check")
    assert a == b


def test_fingerprint_survives_rewording_whitespace_and_case():
    a = parser.fingerprint("code", "a/b.cs", "Missing  null check.")
    b = parser.fingerprint("code", "a/b.cs", "missing null check")
    assert a == b


def test_fingerprint_normalises_path_separators_and_leading_slash():
    a = parser.fingerprint("code", "/src/A.cs", "x")
    b = parser.fingerprint("code", "src\\a.cs", "x")
    assert a == b


def test_fingerprint_differs_by_kind():
    assert parser.fingerprint("code", "a.cs", "x") != parser.fingerprint("checklist", "a.cs", "x")


def test_fingerprint_differs_by_text():
    assert parser.fingerprint("code", "a.cs", "x") != parser.fingerprint("code", "a.cs", "y")


# -- claim matching ---------------------------------------------------------

CRITERIA = [
    "Quantity must be a positive integer; zero or negative is rejected with a validation error.",
    "Adding an unknown product returns a not-found response and does not change the cart.",
    "Adding a product already in the cart increments the quantity of the existing line.",
    "The system must not allow adding more items than are available in stock.",
    "The cart total is recalculated after a successful add, before the cart is saved.",
]


@pytest.mark.parametrize(
    "claim,expected",
    [
        ("Quantity validation - rejects zero and negative quantities", 0),
        ("Unknown product returns not-found without changing the cart", 1),
        ("Adding an existing product increments the existing line", 2),
        ("Stock limit enforced when adding to cart", 3),
        ("Cart total recalculated after a successful add", 4),
    ],
)
def test_terse_claims_match_their_criterion(claim, expected):
    """A one-word overlap can still be decisive when the word is distinctive."""
    index, _ = parser.match_claim(claim, CRITERIA)
    assert index == expected


def test_unrelated_claim_matches_nothing():
    index, _ = parser.match_claim("Refactored the logging middleware", CRITERIA)
    assert index is None


def test_ambiguous_claim_matches_nothing_rather_than_guessing():
    """Matching the wrong row would put the headline finding on the wrong criterion."""
    index, _ = parser.match_claim("cart", CRITERIA)
    assert index is None


def test_empty_inputs():
    assert parser.match_claim("", CRITERIA) == (None, 0.0)
    assert parser.match_claim("anything", []) == (None, 0.0)


# -- false coverage derivation ---------------------------------------------


def _coverage(status_for_stock):
    entries = []
    for index, text in enumerate(CRITERIA):
        status = status_for_stock if index == 3 else "appears_addressed"
        entries.append(CoverageEntry(criterion=text, status=status, evidence="", ordinal=index + 1))
    return tuple(entries)


def test_claim_plus_unaddressed_criterion_is_a_false_claim():
    scope = DeclaredScope(covered=("Stock limit enforced when adding to cart",), parsed=True)
    claims, unmatched = parser.derive_false_coverage_claims(_coverage("not_addressed"), scope)
    assert len(claims) == 1
    assert claims[0].status == "not_addressed"
    assert unmatched == ()


def test_claim_plus_addressed_criterion_is_not_a_false_claim():
    scope = DeclaredScope(covered=("Stock limit enforced when adding to cart",), parsed=True)
    claims, _ = parser.derive_false_coverage_claims(_coverage("appears_addressed"), scope)
    assert claims == ()


def test_contradiction_on_a_claimed_item_is_also_a_false_claim():
    scope = DeclaredScope(covered=("Stock limit enforced when adding to cart",), parsed=True)
    claims, _ = parser.derive_false_coverage_claims(_coverage("possible_contradiction"), scope)
    assert len(claims) == 1


def test_unaddressed_without_a_claim_is_not_a_false_claim():
    """FR-016: a partial pull request is normal, not a defect."""
    scope = DeclaredScope(covered=(), not_in_this_pr=(), parsed=False)
    claims, _ = parser.derive_false_coverage_claims(_coverage("not_addressed"), scope)
    assert claims == ()


def test_unmatched_claim_is_reported_not_dropped():
    scope = DeclaredScope(covered=("Rewrote the deployment scripts",), parsed=True)
    claims, unmatched = parser.derive_false_coverage_claims(_coverage("not_addressed"), scope)
    assert claims == ()
    assert unmatched == ("Rewrote the deployment scripts",)


def test_false_claim_borrows_a_location_from_a_matching_violation():
    from review_agent.models import ChecklistViolation

    scope = DeclaredScope(covered=("Stock limit enforced when adding to cart",), parsed=True)
    violation = ChecklistViolation(
        item="Business rules from the story are enforced",
        issue="no stock check when adding items in stock",
        file="src/Cart.cs",
        line=42,
    )
    claims, _ = parser.derive_false_coverage_claims(
        _coverage("not_addressed"), scope, (violation,)
    )
    assert claims[0].file == "src/Cart.cs"
    assert claims[0].line == 42


# -- merging ---------------------------------------------------------------


def test_merge_keeps_the_most_informative_status_across_chunks():
    """A chunk without the relevant file reports not_addressed; that must not win."""
    chunk_a = {
        "coverage": [CoverageEntry(criterion="stock limit", status="not_addressed")],
        "checklist_violations": [],
        "code_issues": [],
        "summary": "a",
    }
    chunk_b = {
        "coverage": [CoverageEntry(criterion="stock limit", status="appears_addressed")],
        "checklist_violations": [],
        "code_issues": [],
        "summary": "b",
    }
    merged = parser.merge_results([chunk_a, chunk_b])
    assert len(merged["coverage"]) == 1
    assert merged["coverage"][0].status == "appears_addressed"


def test_contradiction_outranks_everything_when_merging():
    chunk_a = {
        "coverage": [CoverageEntry(criterion="c", status="appears_addressed")],
        "checklist_violations": [],
        "code_issues": [],
        "summary": "a",
    }
    chunk_b = {
        "coverage": [CoverageEntry(criterion="c", status="possible_contradiction")],
        "checklist_violations": [],
        "code_issues": [],
        "summary": "b",
    }
    merged = parser.merge_results([chunk_a, chunk_b])
    assert merged["coverage"][0].status == "possible_contradiction"


def test_merge_dedupes_identical_findings():
    from review_agent.models import CodeIssue

    chunk = {
        "coverage": [],
        "checklist_violations": [],
        "code_issues": [CodeIssue(severity="low", issue="same thing", file="a.cs", line=1)],
        "summary": "s",
    }
    other = {
        "coverage": [],
        "checklist_violations": [],
        "code_issues": [CodeIssue(severity="low", issue="same thing", file="a.cs", line=9)],
        "summary": "s",
    }
    merged = parser.merge_results([chunk, other])
    assert len(merged["code_issues"]) == 1, "line differs but the finding is the same"


# --------------------------------------------------------------------------
# T032 (feature 003) - citation resolution (contracts/llm-response.md).
# --------------------------------------------------------------------------



def _corpus(*items):
    return CombinedChecklist(items=tuple(items))


RULE = ChecklistItem(
    item_id="SEC-WEB-01",
    title="Never concatenate user input into a SQL statement",
    documents=("Secure-Coding-Standard.docx",),
)


def _violation(**kwargs):
    defaults = dict(item="something", issue="broken")
    defaults.update(kwargs)
    return ChecklistViolation(**defaults)


def test_a_cited_identifier_resolves_to_its_document():
    resolved, dropped = parser.resolve_citations([_violation(rule_id="SEC-WEB-01")], _corpus(RULE))
    assert dropped == ()
    assert resolved[0].source == "Secure-Coding-Standard.docx"


def test_the_models_own_filename_is_overwritten():
    resolved, _ = parser.resolve_citations(
        [_violation(rule_id="SEC-WEB-01", source="Invented.xlsx")], _corpus(RULE)
    )
    assert resolved[0].source == "Secure-Coding-Standard.docx"


def test_a_missing_rule_id_falls_back_to_the_rule_text():
    resolved, dropped = parser.resolve_citations(
        [_violation(item="never concatenate user input into a SQL statement.")], _corpus(RULE)
    )
    assert dropped == ()
    assert resolved[0].rule_id == "SEC-WEB-01"


def test_an_unresolvable_citation_is_reported_rather_than_posted():
    resolved, dropped = parser.resolve_citations([_violation(rule_id="SEC-WEB-99")], _corpus(RULE))
    assert resolved == ()
    assert dropped == ("SEC-WEB-99",)


def test_no_checklist_applied_means_no_checklist_violations():
    """R4: findings from general knowledge must not look like cited ones."""
    corpus = CombinedChecklist(unavailable_reason="the repository could not be reached")
    resolved, dropped = parser.resolve_citations([_violation(item="Avoid magic numbers")], corpus)
    assert resolved == ()
    assert dropped == ("Avoid magic numbers",)


def test_the_text_checklist_path_passes_violations_through_unresolved():
    """Feature 002's markdown checklist has no identifiers, and still works."""
    resolved, dropped = parser.resolve_citations([_violation(item="Avoid magic numbers")], None)
    assert len(resolved) == 1
    assert dropped == ()


# --------------------------------------------------------------------------
# T043 (feature 003) - finding identity (contracts/finding-identity.md).
#
# `fingerprint` was always stable; what was handed to it was not. These pin the
# keys, because the defect they fix was recorded as "no gap" by reasoning about
# `fingerprint` without noticing its input.
# --------------------------------------------------------------------------


def test_a_checklist_finding_keys_on_the_rule_identifier():
    first = _violation(rule_id="SEC-WEB-01", issue="Concatenated a query here")
    reworded = _violation(rule_id="SEC-WEB-01", issue="This query is built by concatenation")
    assert parser.checklist_key(first) == parser.checklist_key(reworded)


def test_two_different_rules_are_two_different_findings():
    assert parser.checklist_key(_violation(rule_id="SEC-WEB-01")) != parser.checklist_key(
        _violation(rule_id="SEC-WEB-02")
    )


def test_a_criterion_keys_on_its_number_within_its_story():
    assert parser.criterion_key(4, 101) == "wi101:c4"


def test_the_same_criterion_number_in_two_stories_is_two_findings():
    assert parser.criterion_key(1, 101) != parser.criterion_key(1, 102)


def test_a_criterion_with_no_ordinal_has_no_identity():
    """No identity means summary-only: it could never be recognised again."""
    assert parser.criterion_key(0, 101) == ""


def test_a_code_issue_keys_on_severity_and_line_not_prose():
    first = CodeIssue(severity="high", issue="Missing null check", file="a.cs", line=12)
    reworded = CodeIssue(severity="high", issue="This dereference is unguarded", file="a.cs", line=12)
    assert parser.code_issue_key(first, 12) == parser.code_issue_key(reworded, 12)


def test_a_code_issue_at_a_different_line_is_a_different_finding():
    issue = CodeIssue(severity="high", issue="Missing null check", file="a.cs", line=12)
    assert parser.code_issue_key(issue, 12) != parser.code_issue_key(issue, 30)
