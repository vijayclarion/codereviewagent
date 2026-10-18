"""Obtain the shared checklists and turn them into rules.

Two acquisition paths, one consumer.

**The document path (feature 003, the default).** The team's checklists are
spreadsheets and Word documents maintained by quality leads. Those cannot travel
through the collection's text-oriented item interface - it returns a `str`, and a
`.xlsx` is a zip container - so a working copy of the checklist repository is
obtained instead, every supported document in it is read into individually
citable rules, and the copy is removed when the run ends. Acquisition is asked of
`source_fetch`, parsing is asked of `checklist_docs`; this module owns neither,
which is what keeps both boundaries testable.

**The text path (feature 002, retained).** Plain-text checklists are still fetched
over the item interface and combined into one document. It is the fallback when
no rule-bearing document is found, and remains the whole story for anyone whose
checklists are markdown. It is not the default because a markdown file yields no
individually citable rule, and FR-017 requires every violation to cite one.

A checklist that cannot be read is a DEGRADED review, never a failure: the
coverage half of the review is still worth having (FR-029). And every way of
ending up with fewer rules than expected carries a reason, because the condition
this project was actually in - a configured name with one character too many,
resolving nothing, reporting success - is indistinguishable from a clean review
unless the run says so.
"""

import fnmatch
import os

from . import checklist_docs, source_fetch
from .config import CHECKLIST_REPO_SETTING, split_patterns
from .errors import DegradedReview, SetupFailure
from .models import (
    Checklist,
    ChecklistDocument,
    ChecklistFile,
    ChecklistSource,
    CombinedChecklist,
)

#: Office leaves these beside an open document. They are not documents, and
#: reporting them as skipped would be noise in the one place noise is expensive.
LOCK_PREFIX = "~$"

#: Patterns the document path can read. Anything else the operator has selected
#: belongs to the text path.
DOCUMENT_PATTERNS = ("*.xlsx", "*.docx")

#: What the text path looks for when the operator has selected only documents.
#: Without this, an operator configured exactly as feature 002 left them - a
#: markdown checklist repository and no pattern set - would quietly stop having a
#: checklist applied the moment this feature landed.
DEFAULT_TEXT_PATTERNS = ("*.md",)


def text_patterns(config):
    """What the text path should look for when the document path found nothing."""
    configured = tuple(
        pattern
        for pattern in split_patterns(config.checklist_file_pattern)
        if pattern.lower() not in DOCUMENT_PATTERNS
    )
    return configured or DEFAULT_TEXT_PATTERNS


# --------------------------------------------------------------------------
# The document path
# --------------------------------------------------------------------------


def _fetch(config, repo, ref=None):
    """The seam between this module and the one that obtains a working copy.

    A named indirection rather than a direct call, so a test can replace the
    acquisition without reaching into `source_fetch` - whose own tests assert
    what the real one does and must keep exercising it.
    """
    return source_fetch.clone(config, repo, ref=ref)


def obtain_corpus(config, fetcher=None, cleaner=None):
    """Every rule the review measures against. Never raises.

    `fetcher` and `cleaner` exist so a test can serve a corpus from a temp
    directory without reaching a remote repository.
    """
    fetcher = fetcher or _fetch
    cleaner = cleaner or source_fetch.cleanup

    source, working_copy = _acquire(config, fetcher)
    if not source.available:
        return CombinedChecklist(source=source, unavailable_reason=source.unavailable_reason)
    try:
        return _read_corpus(config, source, working_copy.path)
    finally:
        # FR-005: on every path, including the one where reading raised.
        cleaner(working_copy.path)


def _acquire(config, fetcher):
    """(ChecklistSource, working copy or None). Distinguishes the four failures."""
    if not config.checklist_repo:
        return (
            ChecklistSource(
                unavailable_reason=(
                    "no checklist repository is configured, so no checklist was "
                    f"applied - set {CHECKLIST_REPO_SETTING} to the repository "
                    "holding the team's checklist documents"
                )
            ),
            None,
        )

    ref = config.checklist_branch or None
    try:
        working_copy = fetcher(config, config.checklist_repo, ref=ref)
    except (SetupFailure, DegradedReview) as exc:
        return (
            ChecklistSource(unavailable_reason=_acquisition_reason(config, exc)),
            None,
        )

    return (
        ChecklistSource(
            repo=config.checklist_repo,
            ref=working_copy.ref,
            commit=working_copy.commit,
            setting=config.checklist_setting,
            available=True,
        ),
        working_copy,
    )


#: Fragments an acquisition failure carries when the repository is absent rather
#: than out of reach. Matched case-insensitively against the reported message.
NOT_FOUND_MARKERS = ("not found", "does not exist", "repository not", "404")

#: ... and when it is present but this credential may not have it.
NOT_PERMITTED_MARKERS = (
    "authentication",
    "authorization",
    "permission",
    "denied",
    "403",
    "401",
    "terminal prompts disabled",
)


def _acquisition_reason(config, exc):
    """Which of "not found" and "not permitted" this was, and what to correct.

    They are different corrections - one is a name, the other is a token scope -
    and a message that conflates them sends the reader to the wrong setting. The
    distinction has to be drawn from what the acquisition reported, because the
    repository either way answers the same way to anyone without access.
    """
    where = f"{config.checklist_repo}"
    if config.checklist_branch:
        where += f" at {config.checklist_branch}"
    lowered = (getattr(exc, "message", "") or str(exc)).lower()

    if any(marker in lowered for marker in NOT_PERMITTED_MARKERS):
        return (
            f"the checklist repository {where} could not be read with this "
            f"credential - grant Code (read) on {config.checklist_repo} to the "
            "token in TFS_PAT"
        )
    if any(marker in lowered for marker in NOT_FOUND_MARKERS):
        return (
            f"no checklist repository named {where} was found - check "
            f"{config.checklist_setting or CHECKLIST_REPO_SETTING}"
            + (" and CHECKLIST_BRANCH" if config.checklist_branch else "")
        )
    return (
        f"a working copy of the checklist repository {where} could not be "
        f"obtained ({getattr(exc, 'message', None) or exc})"
    )


def matching_files(root, patterns):
    """Every file under `root` whose FILENAME matches one of `patterns`.

    Filename rather than path, so `*.xlsx` finds `standards/api/Security.xlsx` -
    which is what an operator means by it. Recursive, so adding a folder needs no
    configuration change either (FR-007, SC-010). Sorted, so the corpus does not
    depend on the order the filesystem happened to return.
    """
    found = []
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = sorted(d for d in subdirectories if d != ".git")
        for filename in sorted(filenames):
            if filename.startswith(LOCK_PREFIX):
                continue
            if not any(fnmatch.fnmatch(filename.lower(), p.lower()) for p in patterns):
                continue
            absolute = os.path.join(directory, filename)
            found.append((os.path.relpath(absolute, root).replace("\\", "/"), absolute))
    return sorted(found)


def _read_corpus(config, source, root):
    patterns = split_patterns(config.checklist_file_pattern)
    scope = (config.checklist_path or "/").strip("/")
    base = os.path.join(root, *scope.split("/")) if scope else root

    if not os.path.isdir(base):
        return CombinedChecklist(
            source=source,
            unavailable_reason=(
                f"the path {config.checklist_path} does not exist in "
                f"{source.repo} at {source.ref or 'its default branch'}"
            ),
        )

    matches = matching_files(base, patterns)
    if not matches:
        return CombinedChecklist(
            source=source,
            unavailable_reason=(
                f"{source.repo} at {source.ref or 'its default branch'} was reached, but "
                f"no file under {config.checklist_path} matched "
                f"{config.checklist_file_pattern}"
            ),
        )

    documents, items = [], []
    for relative, absolute in matches:
        document, rules = _read_one(relative, absolute)
        documents.append(document)
        items.extend(rules)

    items = _fold_duplicates(items)
    documents = tuple(documents)

    if not items:
        return CombinedChecklist(
            documents=documents,
            source=source,
            unavailable_reason=_nothing_read_reason(documents),
        )
    return CombinedChecklist(items=tuple(items), documents=documents, source=source)


def _read_one(relative, absolute):
    """One file's outcome. A document that cannot be read never stops the run."""
    if not checklist_docs.document_format(relative):
        return (
            ChecklistDocument(
                filename=relative,
                status="skipped",
                skip_reason=(
                    "not a spreadsheet or Word document - narrow "
                    "CHECKLIST_FILE_PATTERN, or use the plain-text checklist path"
                ),
            ),
            (),
        )
    try:
        with open(absolute, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        return (
            ChecklistDocument(
                filename=relative,
                status="skipped",
                skip_reason=f"could not be opened ({type(exc).__name__})",
            ),
            (),
        )
    return checklist_docs.read(relative, data)


def _fold_duplicates(items):
    """FR-020: the same rule in two documents is one rule citing both.

    Folding on the identifier is also what keeps `CombinedChecklist`'s invariant
    satisfiable - and, after feature 003, what stops two documents' copies of one
    rule becoming two comments saying the same thing.
    """
    folded = {}
    order = []
    for item in items:
        existing = folded.get(item.item_id)
        if existing is None:
            folded[item.item_id] = item
            order.append(item.item_id)
        else:
            folded[item.item_id] = existing.merged_with(item)
    return [folded[item_id] for item_id in order]


def _nothing_read_reason(documents):
    """Read-but-empty and unreadable are different answers (FR-013, FR-015)."""
    skipped = [d for d in documents if d.status == "skipped"]
    if len(skipped) == len(documents):
        return (
            f"all {len(documents)} matching document(s) were found but none could "
            "be read - see the per-document reasons in the summary"
        )
    return (
        f"{len(documents)} document(s) were read but none of them stated any rules"
    )


# --------------------------------------------------------------------------
# The text path (feature 002, retained)
# --------------------------------------------------------------------------


def _matching_blobs(items, patterns):
    blobs = []
    for item in items or []:
        if item.get("isFolder") or item.get("gitObjectType") == "tree":
            continue
        path = item.get("path") or ""
        if not path:
            continue
        filename = path.rsplit("/", 1)[-1]
        if any(fnmatch.fnmatch(filename.lower(), p.lower()) for p in patterns):
            blobs.append((path, filename))
    return sorted(blobs)


def combine(sources):
    """One markdown document, each section labelled with its source filename."""
    parts = []
    for source in sources:
        parts.append(f"## From: {source.filename}")
        parts.append("")
        parts.append(source.content.strip())
        parts.append("")
    return "\n".join(parts).strip()


def fetch_checklist(client, config, patterns=None):
    """Returns a Checklist. Never raises for an absent or unreadable source."""
    if not config.checklist_repo:
        return Checklist(
            available=False,
            unavailable_reason=(
                "no checklist repository is configured, so no checklist was applied "
                f"- set {CHECKLIST_REPO_SETTING}"
            ),
        )

    patterns = patterns or split_patterns(config.checklist_file_pattern)
    scope = config.checklist_path or "/"
    branch = config.checklist_branch or None
    try:
        items = client.list_items(scope, branch, repo=config.checklist_repo)
    except SetupFailure as exc:
        # A permission or path problem on the checklist repo must not sink the
        # whole review - it only costs us the checklist half.
        return Checklist(available=False, unavailable_reason=exc.message)
    except DegradedReview as exc:
        return Checklist(available=False, unavailable_reason=exc.message)

    blobs = _matching_blobs(items, patterns)
    if not blobs:
        return Checklist(
            available=False,
            unavailable_reason=(
                f"no files matching {', '.join(patterns)} were found under "
                f"{scope} on branch {branch or 'its default branch'}"
            ),
        )

    sources = []
    for path, filename in blobs:
        try:
            content = client.get_file_on_branch(path, branch, repo=config.checklist_repo)
        except (SetupFailure, DegradedReview):
            continue
        if content:
            sources.append(ChecklistFile(filename=filename, path=path, content=content))

    if not sources:
        return Checklist(
            available=False,
            unavailable_reason=(
                f"{len(blobs)} checklist file(s) were listed under {scope} on branch "
                f"{branch or 'its default branch'} but none could be read"
            ),
        )

    return Checklist(
        sources=tuple(sources),
        combined_markdown=combine(sources),
        available=True,
    )
