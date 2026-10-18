"""T035 (feature 007) - STORY_SOURCE selects the reader, and nothing is dropped silently."""

import pytest

from review_agent import main as main_module
from review_agent import stories
from review_agent.errors import WorkItemAccessDenied
from review_agent.github_client import CLOSING_KEYWORD, IssueLinks
from tests.fakes import FakeTfsClient, NoWorkItemClient
from tests.fakes_github import FakeGitHubClient
from tests.fixtures import github_pr as gh


class _Log:
    def __init__(self):
        self.lines = []

    def phase(self, name, outcome="ok", **counts):
        self.lines.append((name, outcome, counts))


class _Cfg:
    def __init__(self, source):
        self.story_source = source


def test_none_is_a_stated_reason_and_reads_nothing():
    fake = FakeGitHubClient()
    outcome = stories.fetch_stories(_Cfg("none"), fake, _Log())
    assert outcome.work_items == () and outcome.reason == stories.SOURCE_IS_NONE
    assert fake.calls == []


def test_tfs_reader_returns_exactly_what_fetch_story_returned():
    log_a, log_b = _Log(), _Log()
    direct = main_module._fetch_story(FakeTfsClient(), log_a)
    selected = stories.fetch_stories(_Cfg("tfs"), FakeTfsClient(), log_b)
    assert (selected.work_items, selected.reason) == direct
    assert log_a.lines == log_b.lines
    assert stories.fetch_stories(_Cfg("tfs"), NoWorkItemClient(), _Log()).reason == stories.NO_STORY_LINKED


def test_github_issues_reader_numbers_criteria_across_issues():
    second = dict(gh.ISSUE_7, number=8, body="## Acceptance criteria\n- one more criterion here")
    fake = FakeGitHubClient(linked=(7, 8), issues={7: gh.ISSUE_7, 8: second})
    outcome = stories.fetch_stories(_Cfg("github-issues"), fake, _Log())
    assert [w.id for w in outcome.work_items] == [7, 8]
    assert [c.ordinal for w in outcome.work_items for c in w.criteria] == [1, 2, 3, 4]
    assert outcome.reason == ""


def test_each_issue_is_read_once():
    fake = FakeGitHubClient(linked=(7,))
    stories.fetch_stories(_Cfg("github-issues"), fake, _Log())
    assert fake.calls.count("get_issue:7") == 1


def test_set_aside_issues_carry_reasons():
    fake = FakeGitHubClient(
        linked=(7, 8, 9, 10),
        issues={
            7: gh.ISSUE_7,
            8: {"number": 8, "pull_request": {}},
            10: {"number": 10, "title": "t", "body": "Just a paragraph of description text."},
        },
        notes=("other/repo#3 is in another repository and was not read",),
    )
    outcome = stories.fetch_stories(_Cfg("github-issues"), fake, _Log())
    assert [w.id for w in outcome.work_items] == [7, 10]
    assert "other/repo#3 is in another repository and was not read" in outcome.notes
    assert "#8 is a pull request, not an issue" in outcome.notes
    assert "issue #9 was not found" in outcome.notes
    assert any("#10 has no \"Acceptance criteria\" section" in n for n in outcome.notes)


def test_no_linked_issue_is_a_stated_reason():
    outcome = stories.fetch_stories(_Cfg("github-issues"), FakeGitHubClient(linked=()), _Log())
    assert outcome.reason == stories.NO_ISSUE_LINKED


def test_a_refused_issue_read_loses_only_the_story():
    class Refusing(FakeGitHubClient):
        def get_issue(self, number):
            raise WorkItemAccessDenied("https://api.github.com/repos/o/r/issues/7", 403, scope="Issues (read)")

    log = _Log()
    outcome = stories.fetch_stories(_Cfg("github-issues"), Refusing(), log)
    assert outcome.work_items == ()
    assert "Issues (read)" in outcome.reason
    assert log.lines[-1][1] == "degraded"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Closes #7", ["7"]),
        ("fixes #7", ["7"]),
        ("Resolved #7", ["7"]),
        ("closed: #12 and Fix #3", ["12", "3"]),
        ("Closes acme/shop#5", ["5"]),
        ("see #7", []),
        ("closes 7", []),
        ("#7", []),
    ],
)
def test_closing_keyword_spellings(text, expected):
    assert [m.group("number") for m in CLOSING_KEYWORD.finditer(text)] == expected


def test_issue_links_default_to_empty():
    assert IssueLinks().numbers == () and IssueLinks().notes == ()
