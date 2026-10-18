"""Frozen dataclasses for every entity in data-model.md.

Nothing here talks to TFS or to a provider - it is the vocabulary the rest of the
modules share, which is what lets `tfs_client` stay pure REST and `parser` stay
provider-blind.
"""

import re
from dataclasses import dataclass, field, replace

from .textutil import html_to_text, split_criteria

# --------------------------------------------------------------------------
# Story
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AcceptanceCriterion:
    ordinal: int
    text: str
    work_item_id: int


@dataclass(frozen=True)
class WorkItem:
    id: int
    title: str = ""
    description: str = ""
    acceptance_criteria: str = ""
    work_item_type: str = ""
    state: str = ""
    tags: tuple = ()
    criteria: tuple = ()

    @classmethod
    def from_payload(cls, payload, ordinal_start=1):
        """Build from a TFS work-item response, stripping HTML from every field."""
        fields_ = (payload or {}).get("fields", {}) or {}
        wid = int((payload or {}).get("id") or 0)

        title = html_to_text(fields_.get("System.Title", ""))
        description = html_to_text(fields_.get("System.Description", ""))
        criteria_text = html_to_text(
            fields_.get("Microsoft.VSTS.Common.AcceptanceCriteria", "")
        )
        tags_raw = fields_.get("System.Tags", "") or ""
        tags = tuple(t.strip() for t in re.split(r"[;,]", tags_raw) if t.strip())

        # Criteria live in their own field when the template has one, and in the
        # description when it does not. Losing them silently would hollow out the
        # whole coverage map, so fall back rather than return nothing.
        source = criteria_text or description
        criteria = tuple(
            AcceptanceCriterion(ordinal=ordinal_start + i, text=text, work_item_id=wid)
            for i, text in enumerate(split_criteria(source))
        )

        return cls(
            id=wid,
            title=title,
            description=description,
            acceptance_criteria=criteria_text,
            work_item_type=fields_.get("System.WorkItemType", "") or "",
            state=fields_.get("System.State", "") or "",
            tags=tags,
            criteria=criteria,
        )

    @classmethod
    def from_issue(cls, payload, ordinal_start=1):
        """Build from a GitHub issue (feature 007, research D7).

        Criteria come from the "Acceptance criteria" section; with no such
        section they fall back to the description, exactly as a TFS work item
        without its criteria field does.
        """
        data = payload or {}
        number = int(data.get("number") or 0)
        description, section = split_issue_body(data.get("body") or "")
        source = _flatten_criteria(section) if section else description
        criteria = tuple(
            AcceptanceCriterion(ordinal=ordinal_start + i, text=text, work_item_id=number)
            for i, text in enumerate(split_criteria(source))
        )
        labels = tuple(
            (label.get("name") if isinstance(label, dict) else str(label)) or ""
            for label in (data.get("labels") or ())
        )
        return cls(
            id=number,
            title=data.get("title", "") or "",
            description=description,
            acceptance_criteria=section,
            work_item_type="GitHub issue",
            state=data.get("state", "") or "",
            tags=tuple(label for label in labels if label),
            criteria=criteria,
        )


_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_CRITERIA_HEADING = re.compile(r"^acceptance\s+criteria\b", re.IGNORECASE)
_CHECKBOX = re.compile(r"^(\s*(?:[-*•]|\d+[.)])\s+)\[[ xX]\]\s*")
_NESTED_BULLET = re.compile(r"^\s{2,}(?:[-*•]|\d+[.)])\s+(?:\[[ xX]\]\s*)?(.*)$")


def split_issue_body(body):
    """(description, acceptance-criteria section) of a GitHub issue body.

    The section is the one under a heading reading "Acceptance criteria" at any
    level and in any case, up to the next heading of any level. Absent ->
    (whole body, "").
    """
    lines = (body or "").replace("\r\n", "\n").split("\n")
    start = None
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match and _CRITERIA_HEADING.match(match.group(2)):
            start = index
            break
    if start is None:
        return (body or "").strip(), ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _HEADING.match(lines[index]):
            end = index
            break
    description = "\n".join(lines[:start] + lines[end:]).strip()
    return description, "\n".join(lines[start + 1:end]).strip()


def _flatten_criteria(section):
    """Checkbox markers stripped; a nested bullet folded into its parent."""
    out = []
    for line in section.split("\n"):
        nested = _NESTED_BULLET.match(line)
        if nested and out:
            out[-1] = f"{out[-1]} {nested.group(1).strip()}"
            continue
        out.append(_CHECKBOX.sub(lambda m: m.group(1), line))
    return "\n".join(out)


# --------------------------------------------------------------------------
# Pull request
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PullRequestContext:
    pr_id: int
    title: str = ""
    description: str = ""
    source_branch: str = ""
    target_branch: str = ""
    iteration_id: int = 0
    iteration_commit: str = ""
    base_commit: str = ""
    # Feature 007: which platform the pull request lives on. GitHub has no
    # iterations, so the summary names the head commit instead.
    platform: str = "tfs"
    is_draft: bool = False
    is_fork: bool = False

    @property
    def run_id(self):
        return f"{self.pr_id}.{self.iteration_id}"

    @classmethod
    def from_github(cls, number, payload):
        """Build from a GitHub pull-request payload (feature 007)."""
        data = payload or {}
        head = data.get("head") or {}
        base = data.get("base") or {}
        head_repo = (head.get("repo") or {}).get("full_name") or ""
        base_repo = (base.get("repo") or {}).get("full_name") or ""
        return cls(
            pr_id=int(number),
            title=data.get("title", "") or "",
            description=data.get("body", "") or "",
            source_branch=head.get("ref", "") or "",
            target_branch=base.get("ref", "") or "",
            platform="github",
            is_draft=bool(data.get("draft")),
            # A deleted fork reports no head repository at all; that is still
            # not this repository, so it counts as a fork.
            is_fork=bool(base_repo) and head_repo != base_repo,
        )

    @classmethod
    def from_payload(cls, pr_id, payload):
        data = payload or {}
        return cls(
            pr_id=int(pr_id),
            title=data.get("title", "") or "",
            description=data.get("description", "") or "",
            source_branch=(data.get("sourceRefName", "") or "").replace("refs/heads/", ""),
            target_branch=(data.get("targetRefName", "") or "").replace("refs/heads/", ""),
        )

    def with_iteration(self, iteration_id, iteration_commit, base_commit):
        return replace(
            self,
            iteration_id=int(iteration_id or 0),
            iteration_commit=iteration_commit or "",
            base_commit=base_commit or "",
        )


_COVERED_HEADING = re.compile(r"^\s*(?:#{1,6}\s*|\*\*)?\s*covered\b", re.IGNORECASE)
_NOT_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*|\*\*)?\s*(?:not\s+in\s+this\s+pr|out\s+of\s+scope|follow[\s-]?ups?)\b",
    re.IGNORECASE,
)
_OTHER_HEADING = re.compile(r"^\s*(?:#{1,6}\s+|\*\*)")
_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)$")


@dataclass(frozen=True)
class DeclaredScope:
    """The author's Covered / Not-in-this-PR claim.

    Authoritative for *intent* - the "Not in this PR" list is never flagged - but
    every "Covered" line is still verified against the diff, because that check is
    the whole point of the feature (FR-017).
    """

    covered: tuple = ()
    not_in_this_pr: tuple = ()
    parsed: bool = False

    @classmethod
    def from_description(cls, description):
        if not description:
            return cls()

        covered, excluded = [], None
        target = None
        for raw in description.splitlines():
            if _COVERED_HEADING.match(raw):
                target = covered
                if excluded is None:
                    excluded = []
                continue
            if _NOT_HEADING.match(raw):
                if excluded is None:
                    excluded = []
                target = excluded
                continue
            if _OTHER_HEADING.match(raw) and not _LIST_ITEM.match(raw):
                target = None
                continue
            item = _LIST_ITEM.match(raw)
            if item and target is not None:
                text = item.group(1).strip()
                if text:
                    target.append(text)

        parsed = bool(covered) or bool(excluded)
        return cls(
            covered=tuple(covered),
            not_in_this_pr=tuple(excluded or ()),
            parsed=parsed,
        )


# --------------------------------------------------------------------------
# Changes
# --------------------------------------------------------------------------

SOURCE_EXTENSIONS = {
    ".cs", ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".php",
    ".cpp", ".c", ".h", ".hpp", ".rs", ".kt", ".swift", ".sql", ".vb",
}


@dataclass(frozen=True)
class ChangedFile:
    path: str
    change_type: str = "edit"
    is_binary: bool = False
    diff: str = ""
    line_map: dict = field(default_factory=dict, compare=False)
    changed_lines: int = 0
    relevance: float = 0.0
    # Feature 007: the post-change text, kept for the file skeleton an
    # oversized file's pieces are shown with. Excluded from equality and repr:
    # it can be the largest thing in the run.
    content: str = field(default="", compare=False, repr=False)

    @property
    def is_source(self):
        lowered = self.path.lower()
        return any(lowered.endswith(ext) for ext in SOURCE_EXTENSIONS)


@dataclass(frozen=True)
class SkippedFile:
    path: str
    reason: str  # "excluded" | "bound" | "binary" | "deleted" | "unavailable"
    detail: str = ""


@dataclass(frozen=True)
class ChangeSet:
    files: tuple = ()


#: Feature 007. The change types the pipeline understands, on either platform.
CHANGE_TYPES = ("add", "edit", "delete", "rename")


@dataclass(frozen=True)
class ChangeEntry:
    """One changed path, platform-neutral (feature 007, data-model "Platform")."""

    path: str
    change_type: str = "edit"
    previous_path: str = ""

    def __post_init__(self):
        if not self.path:
            raise ValueError("a change entry needs a path")
        if self.change_type not in CHANGE_TYPES:
            raise ValueError(f"unknown change type: {self.change_type!r}")


@dataclass(frozen=True)
class Revision:
    """What is being reviewed against what (feature 007).

    `base` is TFS's common-ref commit, or on GitHub the merge base from the
    compare API - never the target branch's current tip, which would review
    the target's own later changes as if the author had made them.
    """

    iteration_id: int = 0
    head: str = ""
    base: str = ""


@dataclass(frozen=True)
class ReviewableSet:
    reviewed: tuple = ()
    excluded: tuple = ()
    unreviewed: tuple = ()

    @property
    def is_empty(self):
        return not self.reviewed

    @property
    def total_diff_lines(self):
        return sum(f.changed_lines for f in self.reviewed)


# --------------------------------------------------------------------------
# Checklist
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ChecklistFile:
    filename: str
    path: str
    content: str


@dataclass(frozen=True)
class Checklist:
    sources: tuple = ()
    combined_markdown: str = ""
    available: bool = False
    unavailable_reason: str = ""

    @property
    def filenames(self):
        return tuple(s.filename for s in self.sources)

    @property
    def prompt_text(self):
        """The shape `CombinedChecklist` also offers, so the prompt builder can
        take either without asking which acquisition path ran (R9)."""
        return self.combined_markdown


# --------------------------------------------------------------------------
# Checklist documents (feature 002)
#
# The checklist stopped being "some markdown files" and became a corpus of Excel
# and Word documents maintained by quality leads. Two consequences shape these
# entities: a rule needs an identifier a finding can cite (FR-027), and every
# document needs a terminal state that is reported, because a document that was
# silently unreadable is indistinguishable from one that found nothing wrong
# (Principle VII).
# --------------------------------------------------------------------------

DOCUMENT_FORMATS = ("xlsx", "docx")
DOCUMENT_STATUSES = ("read", "no_rules", "skipped")


@dataclass(frozen=True)
class ChecklistDocument:
    """One .xlsx or .docx file found in the checklist repository."""

    filename: str
    format: str = ""
    status: str = "skipped"
    skip_reason: str = ""
    rule_count: int = 0
    sheets_ignored: tuple = ()

    def __post_init__(self):
        if self.status not in DOCUMENT_STATUSES:
            raise ValueError(f"unknown document status {self.status!r}")
        if self.status == "skipped" and not self.skip_reason:
            raise ValueError(
                f"{self.filename}: a skipped document must carry a reason - an "
                "unexplained skip is exactly the silence Principle VII forbids"
            )


@dataclass(frozen=True)
class ChecklistItem:
    """One review rule. The unit of citation."""

    item_id: str
    title: str
    detail: str = ""
    severity: str = ""
    section: str = ""
    documents: tuple = ()
    derived_id: bool = False

    def __post_init__(self):
        if not self.item_id:
            raise ValueError("a checklist item needs an identifier to be citable")
        if not self.title:
            raise ValueError("a checklist item with no title is not a rule")

    @property
    def source_label(self):
        """How the item is attributed in a prompt and in a posted comment."""
        return ", ".join(self.documents) if self.documents else "unknown document"

    def merged_with(self, other):
        """FR-020: the same rule in two documents is one rule citing both."""
        merged_docs = self.documents + tuple(
            d for d in other.documents if d not in self.documents
        )
        return replace(
            self,
            documents=merged_docs,
            detail=self.detail or other.detail,
            severity=self.severity or other.severity,
        )


@dataclass(frozen=True)
class ChecklistSource:
    """Where the rules came from - and, when they did not come, why (feature 003).

    The reason is not optional. A source that is unavailable without saying so is
    precisely the condition this project spent two features in: the configured
    name had one character too many, nothing resolved, and every run reported a
    clean review against no checklist at all.
    """

    repo: str = ""
    ref: str = ""
    commit: str = ""
    setting: str = ""  # which configuration name supplied `repo`
    available: bool = False
    unavailable_reason: str = ""

    def __post_init__(self):
        if not self.available and not self.unavailable_reason:
            raise ValueError(
                "an unavailable checklist source must carry a reason - silence here "
                "is indistinguishable from a review that found nothing"
            )
        if self.available and not self.repo:
            raise ValueError("an available checklist source must name its repository")

    @property
    def description(self):
        """One line, for the inventory block."""
        if not self.available:
            return f"not applied - {self.unavailable_reason}"
        where = f"{self.repo}@{self.ref}" if self.ref else self.repo
        return f"{where} ({self.commit})" if self.commit else where


@dataclass(frozen=True)
class CombinedChecklist:
    """Every rule the review measures against, plus the fate of every document."""

    items: tuple = ()
    documents: tuple = ()
    dropped_for_budget: tuple = ()
    # Feature 003: where the corpus came from, and what it left out.
    source: object = None
    selection_basis: str = ""
    unavailable_reason: str = ""

    def __post_init__(self):
        if not self.items and not self.unavailable_reason:
            raise ValueError(
                "a corpus with no rules must carry a reason (FR-015) - an empty "
                "checklist and an unreadable one are not the same outcome"
            )
        if self.dropped_for_budget and not self.selection_basis:
            raise ValueError(
                "rules were omitted with no stated basis for keeping the others (FR-016)"
            )
        applied = {item.item_id for item in self.items}
        overlap = applied & {item.item_id for item in self.dropped_for_budget}
        if overlap:
            raise ValueError(f"rule applied and omitted at once: {sorted(overlap)[0]}")

    @property
    def available(self):
        return bool(self.items)

    @property
    def prompt_text(self):
        """What the prompt renders: grouped by document, identifier first (R6).

        The identifier leads because it is what a violation must cite back, and a
        model cites what it can see.
        """
        by_document = {}
        for item in self.items:
            key = item.source_label
            by_document.setdefault(key, []).append(item)
        parts = []
        for filename, items in by_document.items():
            parts.append(f"## From: {filename}")
            parts.append("")
            for item in items:
                line = f"- [{item.item_id}] {item.title}"
                if item.detail:
                    line += f" - {item.detail}"
                if item.severity:
                    line += f" (severity: {item.severity})"
                parts.append(line)
            parts.append("")
        return "\n".join(parts).strip()

    @property
    def rule_count(self):
        return len(self.items)

    def by_id(self, item_id):
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None

    @property
    def documents_read(self):
        return tuple(d for d in self.documents if d.status == "read")

    @property
    def documents_skipped(self):
        return tuple(d for d in self.documents if d.status == "skipped")

    @property
    def documents_without_rules(self):
        return tuple(d for d in self.documents if d.status == "no_rules")

    @property
    def sheets_ignored_count(self):
        return sum(len(d.sheets_ignored) for d in self.documents)


@dataclass(frozen=True)
class RunInventory:
    """What one run actually applied (feature 003, FR-014/FR-026).

    The object the demonstration's checkpoint is checked against. `reductions` is
    DERIVED from the fields below rather than assembled by a caller, so a new way
    for a review to cover less than it appears to cannot be added without
    appearing in the summary. That is Principle VII made mechanical.
    """

    source: object = None
    documents: tuple = ()
    rules_read: int = 0
    rules_applied: int = 0
    rules_omitted: int = 0
    selection_basis: str = ""
    work_items: tuple = ()
    criteria_judged: int = 0
    story_unavailable_reason: str = ""
    dropped_citations: tuple = ()

    def __post_init__(self):
        if self.rules_applied + self.rules_omitted != self.rules_read:
            raise ValueError(
                f"inventory does not balance: {self.rules_applied} applied + "
                f"{self.rules_omitted} omitted != {self.rules_read} read"
            )
        if self.rules_omitted and not self.selection_basis:
            raise ValueError("rules were omitted with no stated basis (FR-016)")
        if not self.work_items and not self.story_unavailable_reason:
            raise ValueError(
                "no work items and no reason - 'none is linked' is itself a reason "
                "and must be stated (FR-022)"
            )

    @property
    def reductions(self):
        """Every condition that made this review cover less than it could have."""
        found = []
        source = self.source
        if source is not None and not source.available:
            found.append(f"No checklist was applied: {source.unavailable_reason}")
        for document in self.documents:
            if document.status == "skipped":
                found.append(
                    f"{document.filename} was not read: {document.skip_reason}"
                )
        if self.rules_omitted:
            found.append(
                f"{self.rules_omitted} of {self.rules_read} rules were not applied, "
                f"selected by {self.selection_basis}"
            )
        if self.story_unavailable_reason:
            found.append(f"Story coverage was not assessed: {self.story_unavailable_reason}")
        if self.dropped_citations:
            found.append(
                f"{len(self.dropped_citations)} citation(s) matched no applied rule "
                "and were not reported as findings"
            )
        return tuple(found)


# --------------------------------------------------------------------------
# Run provenance (feature 002)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentSource:
    """Which copy of the review logic actually performed the review (FR-012b).

    Printed first in every report and in every posted summary, so a review
    produced from an uncommitted working copy can never be mistaken for one
    produced by the committed logic.
    """

    mode: str = "local"  # "fetched" | "local"
    commit: str = ""
    ref: str = ""
    repo: str = ""

    def __post_init__(self):
        if self.mode not in ("fetched", "local"):
            raise ValueError(f"unknown agent source mode {self.mode!r}")

    @property
    def description(self):
        if self.mode == "local":
            return "LOCAL WORKING COPY"
        where = f"{self.repo}@{self.ref}" if self.repo else self.ref
        return f"fetched {self.commit}" + (f" ({where})" if where else "")


@dataclass(frozen=True)
class RunInvocation:
    """One hand-started review."""

    pr_id: int
    dry_run: bool = True
    local_logic: bool = False


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

COVERAGE_STATUSES = ("appears_addressed", "not_addressed", "possible_contradiction")
SEVERITIES = ("high", "medium", "low")


@dataclass(frozen=True)
class CoverageEntry:
    criterion: str
    status: str
    evidence: str = ""
    ordinal: int = 0
    # Feature 003: the story the ordinal belongs to. Two linked work items can
    # each have a criterion 1, and a finding has to be able to say which.
    work_item_id: int = 0


@dataclass(frozen=True)
class ChecklistViolation:
    item: str
    source: str = ""
    issue: str = ""
    file: str = ""
    line: int = 0
    # Feature 003: resolved against the applied corpus, never taken from the
    # model. It is what the finding cites (FR-017) and what a second run
    # recognises it by (FR-028).
    rule_id: str = ""


@dataclass(frozen=True)
class CodeIssue:
    severity: str
    issue: str
    file: str = ""
    line: int = 0


def normalise_path(path):
    return (path or "").lstrip("/").replace("\\", "/").lower()


@dataclass(frozen=True)
class CrossFileIssue:
    """A finding no single file shows (feature 007, D13). Names every file involved."""

    severity: str
    issue: str
    files: tuple = ()
    file: str = ""
    line: int = 0

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"invalid severity {self.severity!r}")
        if not (self.issue or "").strip():
            raise ValueError("a cross-file issue must say what is wrong")
        if len({normalise_path(f) for f in self.files if f}) < 2:
            raise ValueError("a cross-file issue names at least two distinct files")


@dataclass(frozen=True)
class FalseCoverageClaim:
    criterion: str
    claimed_text: str
    status: str
    evidence: str = ""
    file: str = ""
    line: int = 0


@dataclass(frozen=True)
class ReviewReport:
    coverage: tuple = ()
    checklist_violations: tuple = ()
    code_issues: tuple = ()
    summary: str = ""
    false_coverage_claims: tuple = ()
    unmatched_claims: tuple = ()
    skipped: tuple = ()
    unreviewed: tuple = ()
    outcome: str = "complete"  # "complete" | "degraded"
    degraded_reason: str = ""
    notes: tuple = ()
    # Feature 002: everything a reader needs to tell a clean review from a
    # silent one - which logic ran, which documents contributed, and what the
    # agent threw away (Principle VII).
    agent_source: object = None
    documents: tuple = ()
    dropped_citations: tuple = ()
    dropped_for_budget: tuple = ()
    # Feature 003: the whole of the above, in one object the summary renders.
    inventory: object = None
    # Feature 007.
    cross_file_issues: tuple = ()
    synthesis: str = "not needed"  # "not needed" | "complete" | "failed: <reason>"
    usage: object = None

    @property
    def has_blocking_findings(self):
        """Only these three block, and only with FAIL_ON_CONTRADICTION (FR-028).

        `not_addressed` is deliberately absent: a pull request routinely
        implements part of a story, and treating that as a defect would make the
        agent useless (FR-016).
        """
        if self.false_coverage_claims:
            return True
        if any(c.status == "possible_contradiction" for c in self.coverage):
            return True
        if any(i.severity == "high" for i in self.cross_file_issues):
            return True
        return any(i.severity == "high" for i in self.code_issues)

    @property
    def status(self):
        return self.outcome
