"""Recover what the agent already said, so a re-review adds only what is new.

The agent is stateless, and a build agent's working directory does not survive to
the next run - so the pull request itself is the only durable store. Each run
reads its own threads back, keyed on the `ai-review:` marker in the comment text
(research R5).

Keyed on the marker rather than the comment's author id on purpose: the author
differs between a manual PAT run (a person) and a pipeline run (the build service
identity), and the same pull request often sees both.
"""

import re

from .parser import fingerprint  # re-exported: one fingerprint definition only

MARKER_PATTERN = re.compile(r"ai-review:(summary|[a-z\-]+):?([0-9a-f]{6,})?")


class PriorFeedback:
    """What this agent has already posted on the pull request."""

    __slots__ = (
        "summary_thread_id",
        "summary_comment_id",
        "posted_fingerprints",
        "own_thread_ids",
        "posted_texts",
    )

    def __init__(
        self,
        summary_thread_id=None,
        summary_comment_id=None,
        posted_fingerprints=frozenset(),
        own_thread_ids=frozenset(),
        posted_texts=(),
    ):
        self.summary_thread_id = summary_thread_id
        self.summary_comment_id = summary_comment_id
        self.posted_fingerprints = frozenset(posted_fingerprints)
        self.own_thread_ids = frozenset(own_thread_ids)
        #: (kind, path, text) for every comment this agent has already posted.
        #: A fingerprint answers "have I said exactly this?"; for a finding with
        #: no natural identifier that is not the question - the provider rewords
        #: it, and moves the line it reports, every single run (research R14).
        self.posted_texts = tuple(posted_texts)

    @property
    def is_empty(self):
        return not self.own_thread_ids


FOOTER_SEPARATOR = "\n\n---\n"


def strip_footer(content):
    """The comment without the marker footer this agent appends."""
    return (content or "").split(FOOTER_SEPARATOR)[0].strip()


def parse_markers(content):
    """Every ai-review marker in one comment body: (kind, fingerprint)."""
    return [
        (match.group(1), match.group(2))
        for match in MARKER_PATTERN.finditer(content or "")
    ]


def read_prior_feedback(client):
    """Read the PR's threads and identify this agent's own feedback.

    Best-effort: if threads cannot be read we treat the pull request as having no
    prior feedback. The failure mode is a duplicate comment, which is strictly
    better than refusing to review.
    """
    try:
        threads = client.get_threads()
    except Exception:
        return PriorFeedback()

    summary_thread_id = None
    summary_comment_id = None
    fingerprints = set()
    own_threads = set()
    texts = []

    for thread in threads or []:
        comments = thread.get("comments") or []
        if not comments:
            continue
        thread_id = thread.get("id")
        context = thread.get("threadContext") or {}
        path = (context.get("filePath") or "").lstrip("/").replace("\\", "/").lower()

        for index, comment in enumerate(comments):
            content = comment.get("content") or ""
            markers = parse_markers(content)
            if not markers:
                continue
            own_threads.add(thread_id)
            for kind, fp in markers:
                if kind != "summary":
                    texts.append((kind, path, strip_footer(content)))
                if kind == "summary":
                    # First marked thread wins, so there is exactly one summary
                    # discussion per pull request even if an earlier run raced.
                    if summary_thread_id is None:
                        summary_thread_id = thread_id
                        summary_comment_id = comment.get("id")
                elif fp:
                    fingerprints.add(fp)

    return PriorFeedback(
        summary_thread_id=summary_thread_id,
        summary_comment_id=summary_comment_id,
        posted_fingerprints=frozenset(fingerprints),
        own_thread_ids=frozenset(own_threads),
        posted_texts=tuple(texts),
    )


__all__ = [
    "PriorFeedback",
    "read_prior_feedback",
    "parse_markers",
    "strip_footer",
    "fingerprint",
]
