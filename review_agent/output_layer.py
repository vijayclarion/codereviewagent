"""Render the feedback, then either print it or post it.

The renderer is one code path for both modes, which is what makes FR-026 ("in
preview mode, present exactly the feedback it would otherwise post") true by
construction rather than by discipline - the two cannot drift.

Sections with nothing to report still print an explicit "none". On a review whose
value is largely "what did it not find", a missing section is indistinguishable
from a section that failed to render, and that ambiguity is expensive.
"""

from .config import emit
from .models import SkippedFile
from .parser import (
    checklist_key,
    claim_overlap,
    code_issue_key,
    criterion_key,
    cross_file_key,
    fingerprint,
)

MARKER = "ai-review"
SUMMARY_MARKER = f"{MARKER}:summary"

FOOTER_TEMPLATE = "\n\n---\n\U0001F916 *AI code review* \u00b7 `{marker}`"

STATUS_LABEL = {
    "appears_addressed": "\u2705 appears addressed",
    "not_addressed": "\u2b1c not addressed",
    "possible_contradiction": "\u26a0\ufe0f possible contradiction",
}

SEVERITY_HEADER = {
    "high": "**\U0001F534 Code issue (high)**",
    "medium": "**\U0001F7E1 Code issue (medium)**",
    "low": "**\U0001F535 Code issue (low)**",
}

DISCLAIMER = (
    "*This is an automated reviewer aid, not a merge gate. It reasons over diff "
    "text and cannot verify runtime behaviour \u2014 a human decides the merge.*"
)


def _footer(kind=None, fp=None):
    marker = SUMMARY_MARKER if kind is None else f"{MARKER}:{kind}:{fp}"
    return FOOTER_TEMPLATE.format(marker=marker)


def _escape_cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


# --------------------------------------------------------------------------
# Inline comments
# --------------------------------------------------------------------------


class InlineComment:
    __slots__ = ("path", "right_line", "markdown", "fingerprint", "kind", "body", "identity")

    def __init__(self, path, right_line, markdown, fp, kind, body="", identity=""):
        #: Feature 007: the stable identity the fingerprint was built from, so a
        #: finding first reported summary-only (no path) is still recognised
        #: once it gains a location (`location_free_fingerprint`).
        self.identity = identity
        self.path = path
        self.right_line = right_line
        self.markdown = markdown
        self.fingerprint = fp
        self.kind = kind
        #: The comment without its footer, kept for the text comparison that
        #: catches a reworded finding a fingerprint cannot (research R14).
        self.body = body

    def thread_context(self):
        path = self.path if self.path.startswith("/") else f"/{self.path}"
        return {
            "filePath": path,
            "rightFileStart": {"line": self.right_line, "offset": 1},
            "rightFileEnd": {"line": self.right_line, "offset": 1},
        }


def _locate(report_file, report_line, reviewable, mapper):
    """Resolve a reported file+line to an anchorable location, or (None, None)."""
    if not report_file or not reviewable:
        return None, None
    normalised = report_file.lstrip("/").replace("\\", "/").lower()
    for changed in reviewable.reviewed:
        candidate = changed.path.lstrip("/").replace("\\", "/").lower()
        if candidate == normalised or candidate.endswith("/" + normalised):
            line = mapper(changed, report_line)
            if line:
                return changed.path, line
            return changed.path, None
    return None, None


def location_free_fingerprint(kind, identity):
    """A finding's fingerprint without its path (feature 007).

    The path is part of an inline comment's fingerprint, and a finding reported
    summary-only has none - so the two never matched, and a finding that gained
    a location on a later run was posted as if new. This form is the same in
    both places.
    """
    return fingerprint(kind, "", identity)


def build_inline_comments(report, reviewable, mapper):
    """One comment per located finding; everything else goes to the summary.

    Each `route` call passes an IDENTITY, not prose. What a finding is called
    changes every run - the provider regenerates it - and keying on that is why a
    second posting run used to repeat everything it had already said
    (contracts/finding-identity.md).
    """
    inline, summary_only = [], []

    def route(kind, path, line, identity, body):
        resolved_path, resolved_line = _locate(path, line, reviewable, mapper)
        # A finding with no identity cannot be recognised on a later run, so it is
        # never posted as a durable comment - it is reported in the summary.
        if not identity:
            fp = fingerprint(kind, path, body)
            summary_only.append((kind, path, line, body, fp))
            return
        fp = fingerprint(kind, path, identity)
        if resolved_path and resolved_line:
            inline.append(
                InlineComment(
                    resolved_path, resolved_line, body + _footer(kind, fp), fp, kind, body,
                    identity=identity,
                )
            )
        else:
            # Feature 007: a summary-only finding carries its LOCATION-FREE
            # fingerprint, which the summary publishes as a hidden marker. A
            # later run that manages to anchor the same finding recognises it
            # instead of posting it as new (live run T090, validation.md).
            summary_only.append((kind, path, line, body, location_free_fingerprint(kind, identity)))

    for claim in report.false_coverage_claims:
        ordinal = _ordinal_for(report, claim.criterion)
        header = f"**\u26a0\ufe0f False coverage claim{ordinal}**"
        body = (
            f"{header}\n\n"
            f"The pull request description claims **\"{claim.claimed_text}\"** is covered, "
            f"but the diff does not implement it.\n\n"
            f"> Acceptance criterion \u2014 *\"{claim.criterion}\"* \u2014 status: "
            f"`{claim.status}`"
        )
        if claim.evidence:
            body += f"\n\n{claim.evidence}"
        route("false-coverage", claim.file, claim.line, _criterion_identity(report, claim.criterion), body)

    for entry in report.coverage:
        if entry.status != "possible_contradiction":
            continue  # not_addressed never comments (FR-016)
        ordinal = f" {entry.ordinal}" if entry.ordinal else ""
        body = (
            f"**\u26a0\ufe0f Possible contradiction with acceptance criterion{ordinal}**\n\n"
            f"*\"{entry.criterion}\"*\n\n{entry.evidence}"
        )
        route("coverage", "", 0, criterion_key(entry.ordinal, entry.work_item_id), body)

    for violation in report.checklist_violations:
        body = (
            f"**\U0001F4CB Checklist: {violation.item}**\n\n{violation.issue}\n\n"
            f"*Source*: `{violation.source or 'checklist'}`"
        )
        route("checklist", violation.file, violation.line, checklist_key(violation), body)

    for issue in report.code_issues:
        body = f"{SEVERITY_HEADER.get(issue.severity, '**Code issue**')}\n\n{issue.issue}"
        _, resolved_line = _locate(issue.file, issue.line, reviewable, mapper)
        route("code", issue.file, issue.line, code_issue_key(issue, resolved_line), body)

    # Feature 007: keyed on the files involved, which do not change when the
    # provider rewords the finding (contracts/finding-identity.md).
    for issue in getattr(report, "cross_file_issues", ()):
        files = ", ".join(f"`{f}`" for f in issue.files)
        body = (
            f"**\U0001F517 Cross-file issue ({issue.severity})**\n\n{issue.issue}\n\n"
            f"*Files involved*: {files}"
        )
        route("cross-file", issue.file, issue.line, cross_file_key(issue), body)

    return inline, summary_only


def _criterion_identity(report, criterion):
    """The story and criterion number a claim concerns, or "" if neither is known."""
    for entry in report.coverage:
        if entry.criterion == criterion:
            return criterion_key(entry.ordinal, entry.work_item_id)
    return ""


def _ordinal_for(report, criterion):
    for entry in report.coverage:
        if entry.criterion == criterion and entry.ordinal:
            return f" \u2014 criterion {entry.ordinal}"
    return ""


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------


DOCUMENT_STATUS_LABEL = {
    "read": "read",
    "no_rules": "read, stated no rules",
    "skipped": "skipped",
}


def render_inventory(inventory):
    """What the review actually applied (FR-014, FR-026, SC-004).

    The section that makes a review against an empty checklist distinguishable
    from a review that found nothing wrong. Those two produced identical output
    for the whole of this project's life until now, and the second is what
    everyone read.
    """
    if inventory is None:
        return []

    parts = ["### What this review applied", ""]

    source = inventory.source
    if source is None:
        parts.append("**Checklist**: no checklist source was consulted.")
    else:
        parts.append(f"**Checklist**: {source.description}")
    parts.append("")

    if inventory.documents:
        parts.append("| Document | Outcome |")
        parts.append("|---|---|")
        for document in inventory.documents:
            label = DOCUMENT_STATUS_LABEL.get(document.status, document.status)
            if document.status == "read":
                label = f"read, {document.rule_count} rules"
            elif document.status == "skipped":
                label = f"skipped - {_escape_cell(document.skip_reason)}"
            parts.append(f"| `{document.filename}` | {label} |")
        parts.append("")

    if inventory.rules_read:
        applied = f"**Rules applied**: {inventory.rules_applied} of {inventory.rules_read}"
        if inventory.rules_omitted:
            applied += (
                f" - {inventory.rules_omitted} omitted, selected by "
                f"{inventory.selection_basis}"
            )
        parts.append(applied)
        parts.append("")

    if inventory.work_items:
        stories = ", ".join(f"#{wid}" for wid in inventory.work_items)
        parts.append(
            f"**Story**: {stories} - {inventory.criteria_judged} acceptance "
            "criteria judged"
        )
    else:
        parts.append(f"**Story**: not assessed - {inventory.story_unavailable_reason}")
    parts.append("")

    if inventory.dropped_citations:
        parts.append(
            f"{len(inventory.dropped_citations)} citation(s) matched no applied rule "
            "and were not reported as findings:"
        )
        parts.extend(f"- `{citation}`" for citation in inventory.dropped_citations)
        parts.append("")

    return parts


def render_degraded_summary(reason):
    return (
        "## \U0001F916 AI Code Review \u2014 could not complete\n\n"
        "The review did not run to completion, so **no findings should be inferred "
        "from its silence**.\n\n"
        f"**Reason**: {reason}\n\n"
        "Nothing about this pull request has been assessed. This build reports "
        "success by design \u2014 a review outage does not gate a merge."
        + _footer()
    )


def render_summary(report, work_items, pr_context, reviewable=None, summary_only=()):
    parts = ["## \U0001F916 AI Code Review", ""]

    reviewed_count = len(reviewable.reviewed) if reviewable else 0
    total = reviewed_count + (
        len(reviewable.excluded) + len(reviewable.unreviewed) if reviewable else 0
    )
    story_note = (
        ", ".join(f"story #{w.id}" for w in work_items) if work_items else "no linked story"
    )
    # Feature 007: GitHub has no iterations; the head commit is what a reader
    # can check the review against.
    if getattr(pr_context, "platform", "tfs") == "github":
        revision = f"commit {(pr_context.iteration_commit or '')[:7] or '-'}"
    else:
        revision = f"iteration {pr_context.iteration_id}"
    parts.append(
        f"**Reviewed**: PR #{pr_context.pr_id}, {revision} \u00b7 "
        f"{reviewed_count} of {total} changed files \u00b7 {story_note}"
    )
    parts.append("")

    # Before any finding: what was actually applied. A reader who sees no
    # violations needs to know whether that means "none" or "none looked for".
    parts.extend(render_inventory(report.inventory))

    # False coverage claims lead: this is the headline finding (FR-023).
    if report.false_coverage_claims:
        parts.append("### \u26a0\ufe0f False coverage claim")
        parts.append("")
        for claim in report.false_coverage_claims:
            parts.append(
                f"The PR description lists **\"{claim.claimed_text}\"** as covered, but "
                f"the diff does not implement it."
            )
            parts.append("")
            parts.append(
                f"> Acceptance criterion \u2014 *\"{claim.criterion}\"* \u2014 status: "
                f"`{claim.status}`"
            )
            parts.append("")

    if report.unmatched_claims:
        parts.append("### Claims not matched to a criterion")
        parts.append("")
        parts.extend(
            f"- \"{claim}\" \u2014 claimed as covered, but no acceptance criterion matched it"
            for claim in report.unmatched_claims
        )
        parts.append("")

    parts.append("### Story coverage")
    parts.append("")
    if not report.coverage:
        parts.append(
            "No acceptance criteria were assessed"
            + (" \u2014 no work item is linked to this pull request." if not work_items else ".")
        )
        parts.append("")
    else:
        parts.append("| # | Acceptance criterion | Status | Evidence |")
        parts.append("|---|---|---|---|")
        for entry in report.coverage:
            ordinal = str(entry.ordinal) if entry.ordinal else "\u2014"
            parts.append(
                f"| {ordinal} | {_escape_cell(entry.criterion)} | "
                f"{STATUS_LABEL.get(entry.status, entry.status)} | "
                f"{_escape_cell(entry.evidence)} |"
            )
        parts.append("")
        if any(e.status == "not_addressed" for e in report.coverage):
            parts.append(
                "\u2b1c *Not addressed* is neutral \u2014 a pull request routinely "
                "implements only part of a story, and these are not defects."
            )

            parts.append("")

    parts.append(f"### Checklist violations ({len(report.checklist_violations)})")
    parts.append("")
    if report.checklist_violations:
        for violation in report.checklist_violations:
            location = f"\n  \u2192 `{violation.file}:{violation.line}`" if violation.file else ""
            parts.append(
                f"- **{violation.item}** \u2014 `{violation.source or 'checklist'}`\n"
                f"  {violation.issue}{location}"
            )
    else:
        parts.append("None found in the reviewed diff.")
    parts.append("")

    parts.append(f"### Code issues ({len(report.code_issues)})")
    parts.append("")
    if report.code_issues:
        for issue in report.code_issues:
            location = f" \u2014 `{issue.file}:{issue.line}`" if issue.file else ""
            parts.append(f"- **{issue.severity}** \u2014 {issue.issue}{location}")
    else:
        parts.append("None found in the reviewed diff.")
    parts.append("")

    # Feature 007: always present, with an explicit "none" - a missing section
    # cannot be told apart from one that failed to render (module docstring).
    cross_file = tuple(getattr(report, "cross_file_issues", ()))
    parts.append(f"### Cross-file issues ({len(cross_file)})")
    parts.append("")
    if cross_file:
        for issue in cross_file:
            files = ", ".join(f"`{f}`" for f in issue.files)
            parts.append(f"- **{issue.severity}** — {issue.issue}\n  Files: {files}")
    else:
        parts.append("None found.")
    parts.append("")

    if summary_only:
        parts.append("### Findings without a specific location")
        parts.append("")
        parts.extend(
            f"- {body.splitlines()[0].strip('*') } \u2014 {' '.join(body.splitlines()[1:]).strip()}"
            for _kind, _path, _line, body, _fp in summary_only
        )
        parts.append("")

    skipped = list(report.skipped) + list(report.unreviewed)
    if skipped:
        parts.append("### Not sent for review")
        parts.append("")
        parts.append("| File | Reason |")
        parts.append("|---|---|")
        for item in skipped:
            parts.append(f"| `{item.path}` | {item.reason} \u2014 {_escape_cell(item.detail)} |")
        parts.append("")

    for note in report.notes:
        parts.append(f"> {note}")
        parts.append("")

    parts.append("---")
    parts.append(DISCLAIMER)

    # Feature 007: one hidden marker per summary-only finding, so the summary
    # itself records that the finding was reported. Invisible when rendered;
    # read back by `dedupe.read_prior_feedback` like any other marker.
    hidden = sorted({f"<!-- {MARKER}:{kind}:{fp} -->" for kind, _p, _l, _b, fp in summary_only if fp})
    if hidden:
        parts.append("")
        parts.extend(hidden)

    return "\n".join(parts).rstrip() + _footer()


# --------------------------------------------------------------------------
# Plan and delivery
# --------------------------------------------------------------------------


class FeedbackPlan:
    """What the run intends to do. Rendered identically in both modes."""

    def __init__(self, summary_markdown, inline, summary_only, suppressed, action):
        self.summary_markdown = summary_markdown
        self.inline = tuple(inline)
        self.summary_only = tuple(summary_only)
        self.suppressed = tuple(suppressed)
        self.action = action  # "create_summary" | "update_summary"


#: Kinds whose findings carry no natural identifier, so an identity built from
#: what the provider reported cannot be stable (research R14). Observed live: the
#: provider reworded every code issue AND moved the line it attributed them to
#: between two runs against an unchanged pull request.
#:
#: Feature 007 adds `checklist`, approved by the requester after live run T090:
#: the provider cited "Create Unit Tests for critical parts ..." on one run and
#: "Create unit tests" on the next for the same problem in the same file - two
#: rule identifiers, one finding. The accepted cost: two genuinely different
#: violations worded alike in one file collapse into one comment.
TEXT_MATCHED_KINDS = ("code", "checklist")

#: Token overlap between two findings' prose, above which they are taken to be
#: the same finding said differently.
#:
#: Measured against the pair this feature's live run actually produced, where the
#: provider restated one finding completely between two runs minutes apart: those
#: two texts overlap at 0.40, and the most similar genuinely-different pair in the
#: same file overlapped at 0.00. 0.3 sits between them with room on both sides.
#:
#: Compared on the prose ALONE, never on the rendered comment: the rendered form
#: shares a severity header, which lifts every pair by a constant and would make
#: two unrelated findings look alike.
SAME_FINDING_OVERLAP = 0.3


def _headline(text):
    return (text or "").strip().splitlines()[0].strip() if text else ""


def _detail(text):
    return " ".join((text or "").strip().splitlines()[1:]).strip()


def _already_said(comment, prior):
    """Has this finding already been posted, in different words?

    Only for kinds with nothing stable to key on, and only within the same file.
    A rewording is caught; a different finding in the same file is not.

    Severity is deliberately NOT part of the comparison. The live run showed the
    provider re-rating the same finding between runs as well as restating it, and
    a reviewer who has read "this exception handler hides errors" has read it
    whether it is labelled medium or high.
    """
    if comment.kind not in TEXT_MATCHED_KINDS or prior is None:
        return False
    here = comment.path.lstrip("/").replace("\\", "/").lower()
    detail = _detail(comment.body)
    for kind, path, text in getattr(prior, "posted_texts", ()):
        if kind != comment.kind or path != here:
            continue
        if claim_overlap(detail, _detail(text)) >= SAME_FINDING_OVERLAP:
            return True
    return False


def build_plan(report, work_items, pr_context, reviewable, mapper, prior=None):
    inline, summary_only = build_inline_comments(report, reviewable, mapper)

    posted = prior.posted_fingerprints if prior else frozenset()

    def seen(comment):
        if comment.fingerprint in posted:
            return True
        # Feature 007: reported summary-only on an earlier run, located now.
        if comment.identity and location_free_fingerprint(comment.kind, comment.identity) in posted:
            return True
        return _already_said(comment, prior)

    fresh = [c for c in inline if not seen(c)]
    suppressed = [c for c in inline if seen(c)]

    summary = render_summary(report, work_items, pr_context, reviewable, summary_only)
    action = "update_summary" if (prior and prior.summary_thread_id) else "create_summary"
    return FeedbackPlan(summary, fresh, summary_only, suppressed, action)


def print_plan(plan):
    """Preview mode. Exactly the text that would be posted (FR-026)."""
    emit("")
    emit("=" * 78)
    emit("DRY RUN - the following would be posted to the pull request")
    emit("=" * 78)
    emit("")
    emit(f"--- summary discussion ({plan.action.replace('_', ' ')}) ---")
    emit("")
    emit(plan.summary_markdown)
    emit("")
    for comment in plan.inline:
        emit(f"--- inline comment: {comment.path}:{comment.right_line} ---")
        emit("")
        emit(comment.markdown)
        emit("")
    if plan.suppressed:
        emit(
            f"--- {len(plan.suppressed)} finding(s) already posted on this pull "
            f"request; not repeated ---"
        )
        emit("")
    if not plan.inline and not plan.suppressed:
        emit("--- no inline comments ---")
        emit("")
    emit("=" * 78)


def post_plan(plan, client, prior=None):
    """Live posting. Creates active threads; never resolves or deletes (FR-024a)."""
    if plan.action == "update_summary" and prior and prior.summary_comment_id:
        try:
            client.update_comment(
                prior.summary_thread_id, prior.summary_comment_id, plan.summary_markdown
            )
        except Exception:
            # Some on-prem versions refuse a comment PATCH from the build identity.
            # Appending in the same thread keeps the "one summary discussion per
            # pull request" guarantee, with the newest comment last (research R5).
            client.add_comment(prior.summary_thread_id, plan.summary_markdown)
    else:
        client.create_thread(plan.summary_markdown)

    for comment in plan.inline:
        client.create_thread(comment.markdown, thread_context=comment.thread_context())

    return len(plan.inline)


def skipped_note(path, reason, detail=""):
    return SkippedFile(path=path, reason=reason, detail=detail)
