"""Validate the model's JSON contract, then derive the headline finding.

Two responsibilities worth separating in your head:

1. Shape enforcement. The contract in contracts/llm-response.schema.json is
   non-negotiable: a response that does not match it gets exactly one stricter
   retry, then the run degrades rather than posting partial or invented feedback
   (FR-022). Unknown extra keys are ignored, because turning a chatty model into
   a degraded review buys the reader nothing.

2. False coverage claims are DERIVED here, not asked of the model. It already
   reports coverage status and already sees the declared scope; asking for a
   fourth list invites it to disagree with its own coverage array. Deriving makes
   the headline a deterministic function of the coverage map, so the same map
   always yields the same headline - and the SC-001 regression test pins one rule
   instead of two.
"""

import hashlib
import json
import re

from .errors import DegradedReview
from .models import (
    COVERAGE_STATUSES,
    SEVERITIES,
    ChecklistViolation,
    CodeIssue,
    CoverageEntry,
    FalseCoverageClaim,
    ReviewReport,
)

CLAIM_MATCH_THRESHOLD = 0.5

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "is", "are", "be",
    "must", "should", "not", "with", "that", "this", "it", "as", "on", "by",
    "when", "then", "given", "if", "from", "at", "system", "does", "do",
}


class ContractViolation(Exception):
    """Raised internally when a response does not match the contract."""


# --------------------------------------------------------------------------
# JSON extraction
# --------------------------------------------------------------------------


def extract_json(text):
    """Recover the JSON object from a model response.

    The contract says "no prose, no markdown fences", and models mostly comply -
    but a fenced block or a leading sentence is common enough that failing the
    whole review over it would be a self-inflicted wound. Anything beyond these
    two tolerances is a genuine contract violation.
    """
    if not text:
        raise ContractViolation("empty response")

    candidate = text.strip()

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    else:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ContractViolation("no JSON object found in the response")
        candidate = candidate[start : end + 1]

    try:
        parsed = json.loads(candidate)
    except ValueError as exc:
        raise ContractViolation(f"response is not valid JSON ({exc})")

    if not isinstance(parsed, dict):
        raise ContractViolation("response JSON is not an object")
    return parsed


# --------------------------------------------------------------------------
# Shape validation
# --------------------------------------------------------------------------


def _require_list(payload, key):
    value = payload.get(key)
    if value is None:
        raise ContractViolation(f"missing required key: {key}")
    if not isinstance(value, list):
        raise ContractViolation(f"{key} must be an array")
    return value


def _text(value):
    return str(value).strip() if value is not None else ""


def _line(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def validate_payload(payload):
    """Turn a raw dict into typed findings, or raise ContractViolation."""
    coverage = []
    for row in _require_list(payload, "coverage"):
        if not isinstance(row, dict):
            raise ContractViolation("coverage entries must be objects")
        status = _text(row.get("status")).lower()
        if status not in COVERAGE_STATUSES:
            raise ContractViolation(
                f"invalid coverage status {status!r}; expected one of "
                f"{', '.join(COVERAGE_STATUSES)}"
            )
        criterion = _text(row.get("criterion"))
        if not criterion:
            raise ContractViolation("coverage entry has an empty criterion")
        coverage.append(
            CoverageEntry(criterion=criterion, status=status, evidence=_text(row.get("evidence")))
        )

    violations = []
    for row in _require_list(payload, "checklist_violations"):
        if not isinstance(row, dict):
            raise ContractViolation("checklist_violations entries must be objects")
        item = _text(row.get("item"))
        if not item:
            raise ContractViolation("checklist violation has an empty item")
        violations.append(
            ChecklistViolation(
                item=item,
                rule_id=_text(row.get("rule_id")),
                source=_text(row.get("source")),
                issue=_text(row.get("issue")),
                file=_text(row.get("file")),
                line=_line(row.get("line")),
            )
        )

    issues = []
    for row in _require_list(payload, "code_issues"):
        if not isinstance(row, dict):
            raise ContractViolation("code_issues entries must be objects")
        severity = _text(row.get("severity")).lower()
        if severity not in SEVERITIES:
            raise ContractViolation(
                f"invalid severity {severity!r}; expected one of {', '.join(SEVERITIES)}"
            )
        issue = _text(row.get("issue"))
        if not issue:
            raise ContractViolation("code issue has an empty issue")
        issues.append(
            CodeIssue(
                severity=severity,
                issue=issue,
                file=_text(row.get("file")),
                line=_line(row.get("line")),
            )
        )

    summary = _text(payload.get("summary"))
    if not summary:
        raise ContractViolation("summary is required and must be non-empty")

    return {
        "coverage": coverage,
        "checklist_violations": violations,
        "code_issues": issues,
        "summary": summary,
    }


def parse_response(text):
    return validate_payload(extract_json(text))


# --------------------------------------------------------------------------
# Fingerprints and merging
# --------------------------------------------------------------------------


def normalise(text):
    lowered = re.sub(r"\s+", " ", (text or "").strip().lower())
    return lowered.rstrip(" .;:,!?")


def fingerprint(kind, path, text):
    """Stable, LINE-INDEPENDENT identity for a finding (research R6).

    Excluding the line is the whole point: between iterations an unrelated edit
    above a finding shifts its line, and a line-sensitive fingerprint would
    re-post the same comment on every push - exactly the noise FR-030 exists to
    prevent. The cost is that two identical issues in one file collapse into one
    comment, which is the cheaper error.
    """
    normalised_path = (path or "").lstrip("/").replace("\\", "/").lower()
    raw = f"{kind}|{normalised_path}|{normalise(text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------------------
# Citation resolution (feature 003, contracts/llm-response.md)
# --------------------------------------------------------------------------


def resolve_citations(violations, corpus):
    """Split reported violations into findings and unresolvable citations.

    Resolution against the APPLIED corpus, not the full one: a rule omitted for
    budget was never shown to the model, so a citation of it is invention rather
    than observation.

    The document filename comes from the corpus and overwrites whatever the model
    reported. The model is a poor source for it - it copies a section heading with
    whatever fidelity it feels like - and a filename that looks authoritative and
    is wrong is worse than no citation at all (FR-017).

    A citation that resolves to nothing is not a finding. It has no stable
    identity, so under contracts/finding-identity.md it would re-post on every
    run; and it is exactly what a model produces when asked for checklist
    violations with no checklist in front of it.
    """
    if corpus is None or not hasattr(corpus, "items"):
        # No rule corpus took part - the plain-text checklist path supplied the
        # rules, and it has no identifiers to resolve against. The model's own
        # attribution is all there is, which is what feature 002 shipped.
        return tuple(violations), ()
    if not corpus.available:
        # A checklist was asked for and none was applied. Anything the model
        # reports here comes from its general knowledge rather than from the
        # team's standards, and posting it as a checklist violation would put
        # this project's own failure mode back: a finding that looks cited and
        # is not.
        return (), tuple(v.rule_id or v.item for v in violations)

    by_id = {item.item_id: item for item in corpus.items}
    by_text = {}
    for rule in corpus.items:
        by_text.setdefault(normalise(rule.item_id), rule)
        by_text.setdefault(normalise(rule.title), rule)

    resolved, dropped = [], []
    for violation in violations:
        rule = by_id.get(violation.rule_id)
        if rule is None:
            rule = by_text.get(normalise(violation.rule_id)) or by_text.get(
                normalise(violation.item)
            )
        if rule is None:
            dropped.append(violation.rule_id or violation.item)
            continue
        resolved.append(
            ChecklistViolation(
                item=violation.item or rule.title,
                rule_id=rule.item_id,
                source=rule.source_label,
                issue=violation.issue,
                file=violation.file,
                line=violation.line,
            )
        )
    return tuple(resolved), tuple(dropped)


# --------------------------------------------------------------------------
# Finding identity (feature 003, contracts/finding-identity.md)
#
# `fingerprint` was always stable. What was handed to it was not: all four call
# sites passed the provider's prose, which is regenerated on every run, so a
# second posting run matched nothing it had already posted and said everything
# twice. Feature 001 recorded this as "no gap" by reasoning about `fingerprint`
# without noticing its input.
#
# So each kind of finding gets a key that does not change between runs. Where a
# natural identifier exists it is used alone, which keeps the line-independence
# that stops an unrelated edit above a finding re-posting it. A code issue has no
# such identifier, so it keys on severity and line - stable against rewording,
# which is the failure that matters, and unstable across a line move, which is
# the cheaper of the two errors available.
# --------------------------------------------------------------------------


def checklist_key(violation):
    return violation.rule_id or normalise(violation.item)


def criterion_key(ordinal, work_item_id=0):
    """A criterion's number within its story - not its position in a response."""
    if not ordinal:
        return ""
    return f"wi{work_item_id}:c{ordinal}"


def code_issue_key(issue, line):
    return f"{issue.severity}@{line or issue.line}"


def _tokens(text):
    return set(
        token
        for token in re.split(r"[^a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in _STOPWORDS
    )


def claim_overlap(claim, criterion):
    """Token overlap as a fraction of the shorter side.

    Used where both sides are expected to be near-verbatim restatements of each
    other - matching the model's echo of a criterion back to the story's numbered
    criterion. For matching a terse description line to a criterion, use
    ``match_claim`` instead: raw overlap is the wrong metric there.
    """
    left, right = _tokens(claim), _tokens(criterion)
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


MIN_DISTINCTIVE_WEIGHT = 1.0
RUNNER_UP_RATIO = 1.4


def _distinctiveness(criteria_texts):
    """Weight each token by how few criteria contain it.

    A term appearing in one criterion out of five identifies it; a term appearing
    in all five identifies nothing. This is what lets "stock limit enforced" find
    "must not allow adding more items than are available in stock" - they share
    exactly one word, but that word is decisive.
    """
    import math

    total = max(len(criteria_texts), 1)
    frequency = {}
    for text in criteria_texts:
        for token in _tokens(text):
            frequency[token] = frequency.get(token, 0) + 1
    return {
        token: math.log(1 + total / count) for token, count in frequency.items()
    }, total


def match_claim(claim, criteria_texts):
    """Best-matching criterion index for a declared-scope line, or None.

    Requires the winner to carry real distinctive weight AND to beat the
    runner-up: a claim that matches two criteria equally well identifies neither,
    and guessing between them would put the headline finding on the wrong row.
    """
    if not claim or not criteria_texts:
        return None, 0.0

    weights, _ = _distinctiveness(criteria_texts)
    claim_tokens = _tokens(claim)
    if not claim_tokens:
        return None, 0.0

    scored = []
    for index, text in enumerate(criteria_texts):
        shared = claim_tokens & _tokens(text)
        score = sum(weights.get(token, 0.0) for token in shared)
        scored.append((score, index))

    scored.sort(reverse=True)
    best_score, best_index = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0

    if best_score < MIN_DISTINCTIVE_WEIGHT:
        return None, best_score
    if runner_up > 0 and best_score < runner_up * RUNNER_UP_RATIO:
        return None, best_score
    return best_index, best_score


def merge_results(results):
    """Union findings across chunks, collapsing duplicates by fingerprint."""
    coverage, violations, issues, summaries = [], [], [], []
    seen_coverage, seen_violations, seen_issues = set(), set(), set()

    for result in results:
        summaries.append(result["summary"])

        for entry in result["coverage"]:
            key = normalise(entry.criterion)
            existing = next((c for c in coverage if normalise(c.criterion) == key), None)
            if existing is None:
                coverage.append(entry)
                seen_coverage.add(key)
                continue
            # Across chunks the same criterion may be judged differently because
            # each chunk sees different files. Keep the most informative verdict:
            # a contradiction outranks evidence of implementation, which outranks
            # "saw nothing" - the last being the default when a chunk lacks the
            # relevant file, not a real finding.
            if _coverage_rank(entry.status) > _coverage_rank(existing.status):
                coverage[coverage.index(existing)] = entry

        for violation in result["checklist_violations"]:
            key = fingerprint("checklist", violation.file, f"{violation.item} {violation.issue}")
            if key not in seen_violations:
                seen_violations.add(key)
                violations.append(violation)

        for issue in result["code_issues"]:
            key = fingerprint("code", issue.file, issue.issue)
            if key not in seen_issues:
                seen_issues.add(key)
                issues.append(issue)

    summary = " ".join(s for s in summaries if s).strip()
    return {
        "coverage": coverage,
        "checklist_violations": violations,
        "code_issues": issues,
        "summary": summary,
    }


_COVERAGE_RANK = {"not_addressed": 0, "appears_addressed": 1, "possible_contradiction": 2}


def _coverage_rank(status):
    return _COVERAGE_RANK.get(status, 0)


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------


def _assign_ordinals(coverage, work_items):
    """Attach the story's criterion numbers so the report can say "criterion 4".

    The work item travels with the ordinal, because after feature 003 the pair is
    what a posted comment is recognised by on a later run - and two linked stories
    can each have a criterion 1.
    """
    criteria = [c for item in work_items for c in item.criteria]
    result = []
    for entry in coverage:
        ordinal = 0
        work_item_id = 0
        best = 0.0
        for criterion in criteria:
            score = claim_overlap(entry.criterion, criterion.text)
            if score > best:
                best, ordinal, work_item_id = score, criterion.ordinal, criterion.work_item_id
        matched = best >= CLAIM_MATCH_THRESHOLD
        result.append(
            CoverageEntry(
                criterion=entry.criterion,
                status=entry.status,
                evidence=entry.evidence,
                ordinal=ordinal if matched else 0,
                work_item_id=work_item_id if matched else 0,
            )
        )
    return tuple(result)


def derive_false_coverage_claims(coverage, declared_scope, violations=()):
    """The headline finding: claimed as covered, but not implemented (FR-017).

    Returns (claims, unmatched) - unmatched Covered lines are reported rather
    than dropped, because a claim nobody could match to a criterion is itself
    worth a reviewer's attention.
    """
    claims, unmatched = [], []
    if not declared_scope.parsed or not coverage:
        return tuple(claims), tuple(unmatched)

    criteria_texts = [entry.criterion for entry in coverage]

    for claimed in declared_scope.covered:
        index, _score = match_claim(claimed, criteria_texts)
        if index is None:
            unmatched.append(claimed)
            continue
        best_entry = coverage[index]

        if best_entry.status != "appears_addressed":
            location = _best_location(index, criteria_texts, violations)
            claims.append(
                FalseCoverageClaim(
                    criterion=best_entry.criterion,
                    claimed_text=claimed,
                    status=best_entry.status,
                    evidence=best_entry.evidence,
                    file=location[0],
                    line=location[1],
                )
            )

    return tuple(claims), tuple(unmatched)


def _best_location(criterion_index, criteria_texts, violations):
    """Borrow a location from a checklist violation about the same criterion.

    The coverage array carries no file or line - the model reports criteria, not
    code positions - so the headline finding would always land in the summary.
    But a checklist violation about the same rule usually *does* carry a location,
    and on the code is where a reviewer wants the headline.

    Matched with the same distinctive-token rule as claims: a violation is about
    this criterion when the criterion is the one its wording points to, not
    merely the one it shares the most common words with.
    """
    for violation in violations or ():
        if not violation.file:
            continue
        text = f"{violation.item} {violation.issue}"
        index, _score = match_claim(text, criteria_texts)
        if index == criterion_index:
            return violation.file, violation.line
    return "", 0


def build_report(merged, declared_scope, work_items, reviewable=None, notes=(), corpus=None):
    coverage = _assign_ordinals(merged["coverage"], work_items)
    violations, dropped = resolve_citations(merged["checklist_violations"], corpus)
    claims, unmatched = derive_false_coverage_claims(coverage, declared_scope, violations)

    return ReviewReport(
        coverage=coverage,
        checklist_violations=violations,
        code_issues=tuple(merged["code_issues"]),
        summary=merged["summary"],
        false_coverage_claims=claims,
        unmatched_claims=unmatched,
        skipped=tuple(reviewable.excluded) if reviewable else (),
        unreviewed=tuple(reviewable.unreviewed) if reviewable else (),
        outcome="complete",
        notes=tuple(notes),
        documents=tuple(getattr(corpus, "documents", ()) or ()),
        dropped_citations=dropped,
        dropped_for_budget=tuple(getattr(corpus, "dropped_for_budget", ()) or ()),
    )


def parse_with_retry(prompt, config, call, retry_instruction):
    """One stricter retry, then degrade (FR-022).

    Never returns partial findings: a response we cannot trust the shape of is a
    response we cannot trust the content of.
    """
    first_error = None
    for attempt in (1, 2):
        text = call(prompt if attempt == 1 else f"{prompt}\n\n{retry_instruction}")
        try:
            return parse_response(text), attempt - 1
        except ContractViolation as exc:
            if attempt == 1:
                first_error = exc
                continue
            raise DegradedReview(
                f"the AI response did not match the required shape after a retry "
                f"(first: {first_error}; second: {exc})"
            )
    raise DegradedReview("the AI response could not be parsed")
