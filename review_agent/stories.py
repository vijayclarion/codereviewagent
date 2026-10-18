"""Where a pull request's user stories come from (feature 007, research D7).

`STORY_SOURCE` selects one of three readers:

* ``tfs``            - the work items TFS links to the pull request. The logic is
                       the one `main._fetch_story` has always run, moved here
                       verbatim; `main._fetch_story` remains as a delegate.
* ``github-issues``  - the issues the pull request closes: GitHub's own record
                       plus "Closes #N" in the body, deduplicated, this
                       repository only.
* ``none``           - no story; a checklist-only review, said so.

Every story that is set aside carries its reason into the summary notes. An
issue that is really a pull request, one in another repository, one with no
"Acceptance criteria" section - none of them disappears silently.
"""

from dataclasses import dataclass

from .errors import WorkItemAccessDenied
from .models import WorkItem

NO_STORY_LINKED = "no work item is linked to this pull request"
NO_ISSUE_LINKED = "no issue is linked to this pull request"
SOURCE_IS_NONE = "the story source is set to none (STORY_SOURCE=none)"


@dataclass(frozen=True)
class StoryOutcome:
    work_items: tuple = ()
    reason: str = ""
    notes: tuple = ()


def fetch_tfs(client, log):
    """Linked work items, and the reason when there are none (FR-022, FR-023).

    A credential that cannot read work items used to raise out of here and exit
    2, taking the checklist half of the review with it. Now the story half is
    lost, loudly, and the rest runs.
    """
    try:
        ids = client.get_linked_work_item_ids()
        work_items = []
        ordinal = 1
        for work_item_id in ids:
            payload = client.get_work_item(work_item_id)
            item = WorkItem.from_payload(payload, ordinal_start=ordinal)
            ordinal += max(len(item.criteria), 1)
            work_items.append(item)
    except WorkItemAccessDenied as exc:
        log.phase("workitems", outcome="degraded", count=0, criteria=0)
        return (), exc.describe()

    log.phase("workitems", count=len(work_items), criteria=sum(len(w.criteria) for w in work_items))
    return tuple(work_items), "" if work_items else NO_STORY_LINKED


def fetch_github_issues(platform, log):
    """The issues this pull request closes, as work items."""
    links = platform.linked_issue_numbers()
    notes = list(links.notes)
    work_items = []
    ordinal = 1
    try:
        for number in links.numbers:
            payload, why = platform.get_issue(number)
            if payload is None:
                notes.append(why)
                continue
            item = WorkItem.from_issue(payload, ordinal_start=ordinal)
            if not item.acceptance_criteria:
                notes.append(
                    f"issue #{item.id} has no \"Acceptance criteria\" section; its criteria "
                    "were taken from the description"
                )
            ordinal += max(len(item.criteria), 1)
            work_items.append(item)
    except WorkItemAccessDenied as exc:
        log.phase("workitems", outcome="degraded", count=0, criteria=0)
        return StoryOutcome((), exc.describe(), tuple(notes))

    log.phase(
        "workitems",
        source="github-issues",
        count=len(work_items),
        criteria=sum(len(w.criteria) for w in work_items),
    )
    reason = "" if work_items else NO_ISSUE_LINKED
    return StoryOutcome(tuple(work_items), reason, tuple(notes))


def fetch_stories(config, platform, log):
    """The stories for this run, by `config.story_source`."""
    source = getattr(config, "story_source", "tfs")
    if source == "none":
        log.phase("workitems", outcome="skipped", count=0, criteria=0)
        return StoryOutcome((), SOURCE_IS_NONE)
    if source == "github-issues":
        return fetch_github_issues(platform, log)
    work_items, reason = fetch_tfs(platform, log)
    return StoryOutcome(work_items, reason)
