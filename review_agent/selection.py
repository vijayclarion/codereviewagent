"""Decide what actually gets sent to the AI provider.

Two independent jobs, both required by the clarifications:

* Exclusion (FR-014a-d). A pull request can legitimately touch a certificate or
  an environment file, so a developer's mistake would otherwise become an
  outbound data leak. Path matching only - this is a safety net, not secret
  scanning, and the spec says so.

* Bounding (FR-014e-f). An 8,000-line bulk rename would blow the latency target
  and produce weaker findings as context fragments. So: review the most relevant
  portion, and name every file left out, because an unreviewed file that looks
  reviewed is worse than an obvious gap.
"""

import fnmatch
import re
from dataclasses import replace

from .models import ReviewableSet, SkippedFile

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "is", "are", "be",
    "must", "should", "not", "with", "that", "this", "it", "as", "on", "by",
    "when", "then", "given", "if", "from", "at", "system", "user", "add", "adding",
}

WEIGHT_STORY = 3.0
WEIGHT_CHECKLIST = 2.0
WEIGHT_SOURCE = 1.0


def _matches(path, pattern):
    """Glob match against the path and against the bare filename.

    `**/bin/**` has to match `src/App/bin/x.dll`, and `*.key` has to match a key
    file at any depth - fnmatch alone does neither reliably, hence both forms.
    """
    normalised = (path or "").lstrip("/").replace("\\", "/")
    name = normalised.rsplit("/", 1)[-1]
    candidates = (normalised, name, "/" + normalised)

    for candidate in candidates:
        if fnmatch.fnmatch(candidate.lower(), pattern.lower()):
            return True

    if "**" in pattern:
        # Translate `**/bin/**` into a substring test on path segments.
        core = pattern.replace("**/", "").replace("/**", "").strip("/").lower()
        if core and core in normalised.lower().split("/"):
            return True
    return False


def match_exclusion(path, patterns):
    for pattern in patterns or ():
        if _matches(path, pattern):
            return pattern
    return None


def _keywords(*texts):
    words = set()
    for text in texts:
        for token in re.split(r"[^a-z0-9]+", (text or "").lower()):
            if len(token) > 2 and token not in _STOPWORDS:
                words.add(token)
    return words


def _path_tokens(path):
    return set(
        token
        for token in re.split(r"[^a-z0-9]+", (path or "").lower())
        if len(token) > 2
    )


def score_relevance(changed_file, story_words, checklist_words):
    """How likely this file is to matter for what we are checking against.

    Relevance means "related to the story or the checklist", because those are the
    only two things the review measures against (research R11).
    """
    tokens = _path_tokens(changed_file.path)
    score = 0.0
    score += WEIGHT_STORY * len(tokens & story_words)
    score += WEIGHT_CHECKLIST * len(tokens & checklist_words)
    if changed_file.is_source:
        score += WEIGHT_SOURCE
    return score


def select_reviewable(change_set, config, work_items=(), checklist=None, pre_skipped=()):
    """Apply exclusions then the bound. Returns a ReviewableSet."""
    excluded = list(pre_skipped)
    candidates = []

    for changed in change_set.files:
        pattern = match_exclusion(changed.path, config.review_exclude_patterns)
        if pattern:
            excluded.append(
                SkippedFile(path=changed.path, reason="excluded", detail=f"matched {pattern}")
            )
            continue
        candidates.append(changed)

    story_words = _keywords(
        *[w.title for w in work_items],
        *[w.acceptance_criteria for w in work_items],
        *[c.text for w in work_items for c in w.criteria],
    )
    checklist_words = _keywords(checklist.prompt_text if checklist else "")

    scored = [
        (score_relevance(c, story_words, checklist_words), c.changed_lines, c)
        for c in candidates
    ]
    # Most relevant first; among equals the smaller change first, so the bound
    # covers more files rather than being eaten by one large one.
    scored.sort(key=lambda item: (-item[0], item[1], item[2].path))

    reviewed = []
    unreviewed = []
    used_lines = 0
    for score, lines, changed in scored:
        over_files = len(reviewed) >= config.review_max_files
        over_lines = used_lines + lines > config.review_max_diff_lines and reviewed
        if over_files or over_lines:
            unreviewed.append(
                SkippedFile(
                    path=changed.path,
                    reason="bound",
                    detail=f"{lines} changed lines; review bound reached",
                )
            )
            continue
        reviewed.append(
            changed.__class__(
                path=changed.path,
                change_type=changed.change_type,
                is_binary=changed.is_binary,
                diff=changed.diff,
                line_map=changed.line_map,
                changed_lines=changed.changed_lines,
                relevance=score,
            )
        )
        used_lines += lines

    return ReviewableSet(
        reviewed=tuple(reviewed),
        excluded=tuple(excluded),
        unreviewed=tuple(unreviewed),
    )


# --------------------------------------------------------------------------
# Rule selection (feature 003, FR-016)
#
# The same job as file bounding, one level down. A corpus larger than a review
# pass can carry has to lose something, and which rules it loses must not depend
# on the order a filesystem walk returned documents in: two operators reviewing
# the same pull request have to apply the same rules or SC-006 is unobservable.
# --------------------------------------------------------------------------

WEIGHT_RULE_PATH = 3.0
WEIGHT_RULE_EXTENSION = 2.0
WEIGHT_RULE_SEVERITY = 1.0

#: Overhead per rendered rule: the brackets, the separators, the newline.
RULE_RENDER_OVERHEAD = 8

SELECTION_BASIS = "relevance to the changed files"


def _identifier_tokens(path):
    """Path tokens, with CamelCase split apart.

    `CartController.cs` has to yield `cart` as well as `cartcontroller`, or a rule
    about carts never finds the file that is all about carts. The file-level
    scorer above matches whole segments only, which is adequate for its job and
    would be a silent behaviour change to alter here.
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", path or "")
    return set(token for token in re.split(r"[^a-z0-9]+", spaced.lower()) if len(token) > 2)


def _changed_tokens(reviewable):
    """What the change is *about*, as far as a path can say."""
    paths, extensions = set(), set()
    for changed in (reviewable.reviewed if reviewable else ()):
        paths |= _identifier_tokens(changed.path)
        _, _, extension = changed.path.rpartition(".")
        if extension and "/" not in extension:
            extensions.add(extension.lower())
    return paths, extensions


def rule_relevance(item, path_tokens, extension_tokens):
    """How likely this rule is to matter for what actually changed."""
    tokens = _keywords(item.title, item.detail, item.section)
    score = WEIGHT_RULE_PATH * len(tokens & path_tokens)
    score += WEIGHT_RULE_EXTENSION * len(tokens & extension_tokens)
    if item.severity:
        score += WEIGHT_RULE_SEVERITY
    return score


def rule_cost(item):
    return len(item.item_id) + len(item.title) + len(item.detail) + RULE_RENDER_OVERHEAD


def select_rules(corpus, reviewable, budget):
    """Order the corpus by relevance and apply as much of it as fits.

    Returns a corpus whose `items` are the rules applied and whose
    `dropped_for_budget` are the rules that did not fit - never a corpus that
    quietly contains fewer rules than it was given.

    The tie-break on (document, identifier) is the load-bearing part. The scoring
    only decides which rules are worth keeping; the tie-break is what makes the
    answer the same on every machine.
    """
    if not corpus.available:
        return corpus

    path_tokens, extension_tokens = _changed_tokens(reviewable)
    ranked = sorted(
        corpus.items,
        key=lambda item: (
            -rule_relevance(item, path_tokens, extension_tokens),
            item.source_label,
            item.item_id,
        ),
    )

    applied, dropped, used = [], [], 0
    for item in ranked:
        cost = rule_cost(item)
        # The first rule always goes in: a budget too small for one rule is a
        # misconfiguration, and applying nothing while reporting a checklist
        # would be the silent outcome this whole feature exists to prevent.
        if applied and used + cost > budget:
            dropped.append(item)
            continue
        applied.append(item)
        used += cost

    return replace(
        corpus,
        items=tuple(applied),
        dropped_for_budget=tuple(dropped),
        selection_basis=SELECTION_BASIS if dropped else "",
    )
