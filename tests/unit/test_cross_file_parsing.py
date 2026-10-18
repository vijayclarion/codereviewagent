"""T047 (feature 007) - the extended response contract and the synthesis merge rules."""

import json

import pytest

from review_agent import parser
from review_agent.models import CodeIssue, CoverageEntry, CrossFileIssue
from tests.fixtures import pr_demo as demo

XF = {"severity": "high", "issue": "caller not updated", "files": ["a.cs", "b.cs"], "file": "b.cs", "line": 4}


def _payload(**extra):
    base = {"coverage": [], "checklist_violations": [], "code_issues": [], "summary": "ok"}
    base.update(extra)
    return base


def test_every_pre_007_response_still_validates():
    result = parser.validate_payload(dict(demo.MODEL_RESPONSE))
    assert result["cross_file_issues"] == [] and result["change_notes"] == ""


def test_cross_file_issues_and_notes_are_parsed():
    result = parser.validate_payload(_payload(cross_file_issues=[XF], change_notes="Signature changed."))
    (issue,) = result["cross_file_issues"]
    assert (issue.severity, issue.files, issue.file, issue.line) == ("high", ("a.cs", "b.cs"), "b.cs", 4)
    assert result["change_notes"] == "Signature changed."


def test_one_file_is_demoted_to_a_code_issue_not_dropped():
    single = dict(XF, files=["a.cs", "/A.cs"], file="")
    result = parser.validate_payload(_payload(cross_file_issues=[single]))
    assert result["cross_file_issues"] == []
    assert result["code_issues"] == [CodeIssue("high", "caller not updated", "a.cs", 4)]


@pytest.mark.parametrize(
    "bad",
    [
        "not a list",
        ["not an object"],
        [dict(XF, severity="urgent")],
        [dict(XF, issue="")],
        [dict(XF, files="a.cs")],
    ],
)
def test_malformed_cross_file_issues_are_contract_violations(bad):
    with pytest.raises(parser.ContractViolation):
        parser.validate_payload(_payload(cross_file_issues=bad))


def test_null_cross_file_issues_mean_none():
    assert parser.validate_payload(_payload(cross_file_issues=None))["cross_file_issues"] == []


def test_change_notes_are_truncated():
    result = parser.validate_payload(_payload(change_notes="x" * 5000))
    assert len(result["change_notes"]) == parser.CHANGE_NOTES_LIMIT


def test_cross_file_key_is_sorted_and_normalised():
    a = CrossFileIssue("low", "x", files=("B.cs", "/a.cs"))
    b = CrossFileIssue("high", "y", files=("a.cs", "b.cs"))
    assert parser.cross_file_key(a) == parser.cross_file_key(b) == "a.cs|b.cs"


def test_merge_unions_cross_file_issues_first_wins_and_collects_notes():
    one = parser.validate_payload(_payload(cross_file_issues=[XF], change_notes="n1"))
    two = parser.validate_payload(
        _payload(cross_file_issues=[dict(XF, issue="reworded"), dict(XF, files=["c.cs", "d.cs"])],
                 change_notes="n2")
    )
    merged = parser.merge_results([one, two])
    assert [i.issue for i in merged["cross_file_issues"]] == ["caller not updated", "caller not updated"]
    assert [i.files for i in merged["cross_file_issues"]] == [("a.cs", "b.cs"), ("c.cs", "d.cs")]
    assert merged["change_notes"] == ["n1", "n2"]


def test_merge_accepts_results_without_the_new_keys():
    legacy = {"coverage": [], "checklist_violations": [], "code_issues": [], "summary": "s"}
    merged = parser.merge_results([legacy])
    assert merged["cross_file_issues"] == [] and merged["change_notes"] == [""]


def test_synthesis_contract():
    result = parser.parse_synthesis(json.dumps({"summary": "whole", "cross_file_issues": [XF],
                                                "code_issues": [{"severity": "high", "issue": "x"}]}))
    assert result["summary"] == "whole" and result["coverage"] == []
    assert len(result["cross_file_issues"]) == 1
    assert "code_issues" not in result  # the synthesis may not add code findings
    with pytest.raises(parser.ContractViolation):
        parser.parse_synthesis(json.dumps({"summary": ""}))
    with pytest.raises(parser.ContractViolation):
        parser.parse_synthesis(json.dumps({"summary": "s", "coverage": [{"criterion": "c", "status": "maybe"}]}))


def test_apply_synthesis_rules():
    merged = {
        "coverage": [CoverageEntry("Criterion one is met", "not_addressed"),
                     CoverageEntry("Criterion two is met", "appears_addressed")],
        "checklist_violations": [], "code_issues": [CodeIssue("low", "kept")],
        "summary": "part a. part b.",
        "cross_file_issues": [CrossFileIssue("low", "from a chunk", files=("a.cs", "b.cs"))],
        "change_notes": ["a", "b"],
    }
    synthesis = {
        "summary": "One summary.",
        "coverage": [CoverageEntry("criterion ONE is met", "appears_addressed"),
                     CoverageEntry("Criterion three", "possible_contradiction")],
        "cross_file_issues": [CrossFileIssue("high", "synthesis wording", files=("b.cs", "a.cs")),
                              CrossFileIssue("medium", "new one", files=("c.cs", "d.cs"))],
    }
    final = parser.apply_synthesis(merged, synthesis)
    assert [(c.criterion, c.status) for c in final["coverage"]] == [
        ("criterion ONE is met", "appears_addressed"),   # replaced
        ("Criterion two is met", "appears_addressed"),   # unmatched: kept
        ("Criterion three", "possible_contradiction"),   # only the synthesis judged it
    ]
    assert final["summary"] == "One summary."
    assert [i.issue for i in final["cross_file_issues"]] == ["synthesis wording", "new one"]
    assert final["code_issues"] == merged["code_issues"]


def test_build_report_carries_cross_file_issues():
    merged = parser.merge_results([parser.validate_payload(_payload(cross_file_issues=[XF]))])
    from review_agent.models import DeclaredScope

    report = parser.build_report(merged, DeclaredScope.from_description(""), ())
    assert len(report.cross_file_issues) == 1
