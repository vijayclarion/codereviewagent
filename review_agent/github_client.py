"""The only module that speaks the GitHub API (feature 007, research D1-D3).

REST for everything except linked issues, which only GraphQL exposes
(`closingIssuesReferences`). github.com and GitHub Enterprise Server differ only
in the base URL, which arrives on `Config` (`GH_API_URL`).

Implements the `PlatformClient` protocol in `platform.py` directly. Three
things in here are less obvious than they look:

* **One review, not N comments.** GitHub can take every inline comment of a run
  in a single review. That is what FR-005 asks for, and it is also the only way
  to keep a re-run from notifying the author once per comment.

* **GitHub refuses the whole review if one anchor is outside its diff** (HTTP
  422), without saying which. The fallback re-posts the review with no inline
  comments and a body listing every finding and its location, so nothing is
  lost and the reason is visible (Principle VII).

* **Two clients, two tokens.** Reads use the read token. Writes go to a second
  client built with the posting token, and that client is constructed only when
  the run will post - so a preview never holds a credential that could write,
  by construction rather than by care (`make_github_platform`).

contracts/platform-client.md is the contract.
"""

import re
import time
from urllib.parse import quote

import requests

from . import __version__
from .config import redact, register_secret
from .errors import DegradedReview, SetupFailure, WorkItemAccessDenied
from .models import ChangeEntry, PullRequestContext, Revision
from .tfs_client import inject_system_trust

USER_AGENT = f"najm-ai-code-review/{__version__} (+review_agent)"
API_VERSION = "2022-11-28"
JSON_MEDIA = "application/vnd.github+json"
RAW_MEDIA = "application/vnd.github.raw"

RETRY_STATUSES = (429, 502, 503, 504)
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = (1, 2, 4)
MAX_RETRY_AFTER = 30.0
PAGE_SIZE = 100

#: GitHub's `files[].status` -> the pipeline's change types (data-model).
STATUS_TO_CHANGE = {
    "added": "add",
    "removed": "delete",
    "modified": "edit",
    "changed": "edit",
    "renamed": "rename",
    "copied": "add",
}

#: Issue bodies and PR bodies say "Closes #7" in many spellings (research D7).
CLOSING_KEYWORD = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+"
    r"(?:(?P<repo>[\w.-]+/[\w.-]+))?#(?P<number>\d+)\b",
    re.IGNORECASE,
)

LINKED_ISSUES_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      closingIssuesReferences(first: 50) {
        nodes { number repository { nameWithOwner } }
      }
    }
  }
}
"""

REFUSED_ANCHOR = "GitHub refused the inline anchor"


class ReviewRefused(Exception):
    """HTTP 422 on a review: at least one anchor is outside GitHub's diff."""


class IssueLinks:
    """Linked issue numbers in this repository, and what was set aside and why."""

    def __init__(self, numbers=(), notes=()):
        self.numbers = tuple(numbers)
        self.notes = tuple(notes)


def _endpoint(url):
    """URL without the query string - never report a value that rode along."""
    return (url or "").split("?", 1)[0]


class GitHubClient:
    """Thin, explicit GitHub client. One method per operation in the contract."""

    name = "github"

    def __init__(self, config, session=None, sleep=time.sleep, purpose="read", writer=None):
        if purpose not in ("read", "post"):
            raise ValueError(f"purpose must be 'read' or 'post' (got {purpose!r})")
        self.config = config
        self.purpose = purpose
        self.writer = writer
        self._sleep = sleep
        self._pr_payload = None
        self.own_writes = 0
        self.refused_inline = 0
        register_secret(self.token)
        inject_system_trust()
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": JSON_MEDIA,
                "User-Agent": USER_AGENT,
                "X-GitHub-Api-Version": API_VERSION,
                "Authorization": f"Bearer {self.token}",
            }
        )

    # -- identity --------------------------------------------------------

    @property
    def token(self):
        """The one credential this client may use."""
        if self.purpose == "post":
            return self.config.gh_post_token
        return self.config.gh_token

    @property
    def repository(self):
        return self.config.gh_repository

    @property
    def number(self):
        return int(self.config.gh_pr_number)

    def _url(self, path):
        return f"{self.config.gh_api_url.rstrip('/')}/{path.lstrip('/')}"

    def _repo_url(self, path, repo=None):
        tail = path.lstrip("/")
        return self._url(f"repos/{repo or self.repository}" + (f"/{tail}" if tail else ""))

    # -- transport -------------------------------------------------------

    def _request(self, method, url, params=None, json_body=None, allow_404=False,
                 accept=None, what=None, read_only=False):
        """One call, with retry. Returns the `requests.Response`, or None on an
        allowed 404. `read_only` marks a POST that changes nothing (GraphQL)."""
        is_write = method.upper() not in ("GET", "HEAD") and not read_only
        headers = {"Accept": accept} if accept else None
        last_error = None

        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = self.session.request(
                    method, url, params=params, json=json_body, headers=headers, timeout=60
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < RETRY_ATTEMPTS - 1:
                    self._sleep(RETRY_BACKOFF[attempt])
                    continue
                raise self._transport_failure(url, exc, is_write)

            if self._should_retry(response) and attempt < RETRY_ATTEMPTS - 1:
                self._sleep(self._retry_after(response, attempt))
                continue

            return self._handle(response, url, is_write, allow_404, what)

        raise self._transport_failure(url, last_error, is_write)

    @staticmethod
    def _should_retry(response):
        if response.status_code in RETRY_STATUSES:
            return True
        # A secondary rate limit is a 403 that says when to come back.
        return response.status_code == 403 and (
            "Retry-After" in response.headers
            or response.headers.get("X-RateLimit-Remaining") == "0"
        )

    @staticmethod
    def _retry_after(response, attempt):
        header = response.headers.get("Retry-After")
        if header:
            try:
                return min(float(header), MAX_RETRY_AFTER)
            except ValueError:
                pass
        return RETRY_BACKOFF[attempt]

    def _transport_failure(self, url, exc, is_write):
        detail = type(exc).__name__ if exc else "unknown transport error"
        if "SSLError" in detail or "SSLCert" in str(exc or ""):
            return SetupFailure(
                f"TLS verification failed for {_endpoint(url)} ({detail})",
                remedy="install `truststore` (in requirements.txt) or set "
                "REQUESTS_CA_BUNDLE to the internal CA bundle - never disable verification",
            )
        message = f"could not reach {_endpoint(url)} after {RETRY_ATTEMPTS} attempts ({detail})"
        if is_write:
            return SetupFailure(message, remedy="check network access to GH_API_URL")
        return DegradedReview(message)

    def _token_setting(self):
        return "GH_TOKEN_FOR_PR" if self.purpose == "post" else "GH_TOKEN"

    def _handle(self, response, url, is_write, allow_404, what):
        status = response.status_code
        endpoint = _endpoint(url)

        if status == 404 and allow_404:
            return None
        if status == 401:
            raise SetupFailure(
                f"authentication failed for {endpoint} (HTTP 401)",
                remedy=f"check {self._token_setting()}",
            )
        if status == 403:
            if what == "issue":
                raise WorkItemAccessDenied(endpoint, status, scope="Issues (read)")
            raise SetupFailure(
                f"not permitted to {'write to' if is_write else 'read'} {endpoint} (HTTP 403)",
                remedy=(
                    "grant Pull requests (write) and Issues (write) to GH_TOKEN_FOR_PR"
                    if is_write
                    else "grant Contents, Pull requests and Issues (read) to GH_TOKEN"
                ),
            )
        if status == 404:
            if what == "pull":
                raise SetupFailure(
                    f"not found: {endpoint} (HTTP 404)",
                    remedy="check GH_REPOSITORY and GH_PR_NUMBER",
                )
            raise SetupFailure(
                f"not found: {endpoint} (HTTP 404)",
                remedy="check the repository name and that the token can see it",
            )
        if status == 422 and what == "review":
            raise ReviewRefused(endpoint)
        if status >= 400:
            raise SetupFailure(f"unexpected HTTP {status} from {endpoint}")

        if is_write:
            self.own_writes += 1
        return response

    @staticmethod
    def _json(response):
        if response is None or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise SetupFailure(
                f"{_endpoint(response.url)} returned a non-JSON body (HTTP {response.status_code})"
            )

    def _paginate(self, url, params=None, what=None):
        """Every page of a list endpoint, following the Link header."""
        items = []
        query = dict(params or {})
        query.setdefault("per_page", PAGE_SIZE)
        next_url, next_params = url, query
        while next_url:
            response = self._request("GET", next_url, params=next_params, what=what)
            page = self._json(response)
            items.extend(page if isinstance(page, list) else [])
            next_url = ((getattr(response, "links", None) or {}).get("next") or {}).get("url")
            next_params = None  # the next URL carries its own query
        return items

    # -- reads -----------------------------------------------------------

    def get_pull_request_context(self):
        response = self._request("GET", self._repo_url(f"pulls/{self.number}"), what="pull")
        self._pr_payload = self._json(response)
        return PullRequestContext.from_github(self.number, self._pr_payload)

    def _pull(self):
        if self._pr_payload is None:
            self.get_pull_request_context()
        return self._pr_payload

    def get_revision(self):
        """Head commit, and the merge base - not the target's current tip."""
        pull = self._pull()
        head = (pull.get("head") or {}).get("sha") or ""
        target = (pull.get("base") or {}).get("sha") or ""
        base = ""
        if head and target:
            compare = self._json(
                self._request("GET", self._repo_url(f"compare/{target}...{head}"))
            )
            base = (compare.get("merge_base_commit") or {}).get("sha") or ""
        return Revision(iteration_id=int(pull.get("commits") or 0), head=head, base=base or target)

    def get_changed_files(self, revision=None):
        entries = []
        for item in self._paginate(self._repo_url(f"pulls/{self.number}/files")):
            change = STATUS_TO_CHANGE.get(item.get("status") or "")
            filename = item.get("filename") or ""
            if not change or not filename:
                continue  # "unchanged" carries no diff
            previous = item.get("previous_filename") or ""
            entries.append(
                ChangeEntry(
                    path="/" + filename,
                    change_type=change,
                    previous_path=("/" + previous) if previous else "",
                )
            )
        return entries

    def _contents(self, path, ref=None, repo=None):
        url = self._repo_url(f"contents/{quote(path.lstrip('/'), safe='/')}", repo=repo)
        response = self._request(
            "GET", url, params={"ref": ref} if ref else None, allow_404=True, accept=RAW_MEDIA
        )
        if response is None:
            return None
        return response.text

    def get_file_content(self, path, commit_sha, repo=None):
        """Blob text at a commit, or None when the path does not exist there."""
        return self._contents(path, ref=commit_sha, repo=repo)

    def get_file_on_branch(self, path, branch, repo=None):
        return self._contents(path, ref=branch, repo=repo)

    def list_items(self, scope_path, branch, repo=None):
        """Every path under `scope_path`, in the item shape the checklist reader
        already understands (`{path, isFolder}`)."""
        ref = branch
        if not ref:
            info = self._request("GET", self._repo_url("", repo=repo), allow_404=True)
            if info is None:
                return []
            ref = self._json(info).get("default_branch") or "master"
        response = self._request(
            "GET",
            self._repo_url(f"git/trees/{quote(ref, safe='')}", repo=repo),
            params={"recursive": "1"},
            allow_404=True,
        )
        if response is None:
            return []
        scope = (scope_path or "/").strip("/")
        items = []
        for node in self._json(response).get("tree", []) or []:
            path = node.get("path") or ""
            if scope and not (path == scope or path.startswith(scope + "/")):
                continue
            items.append({"path": "/" + path, "isFolder": node.get("type") == "tree"})
        return items

    def get_threads(self):
        """Review comments and conversation comments, in the neutral thread shape (D2)."""
        threads = []
        for comment in self._paginate(self._repo_url(f"pulls/{self.number}/comments")):
            threads.append(
                {
                    "id": comment.get("id"),
                    "threadContext": {"filePath": "/" + (comment.get("path") or "")},
                    "comments": [{"id": comment.get("id"), "content": comment.get("body") or ""}],
                }
            )
        for comment in self._paginate(self._repo_url(f"issues/{self.number}/comments")):
            threads.append(
                {
                    "id": comment.get("id"),
                    "threadContext": None,
                    "comments": [{"id": comment.get("id"), "content": comment.get("body") or ""}],
                }
            )
        return threads

    # -- stories ---------------------------------------------------------

    def linked_issue_numbers(self):
        """Issues this pull request closes: GitHub's own record, plus the body."""
        notes = []
        numbers = []
        owner, _, name = self.repository.partition("/")
        here = self.repository.lower()

        try:
            response = self._request(
                "POST",
                self.config.gh_graphql_url,
                json_body={
                    "query": LINKED_ISSUES_QUERY,
                    "variables": {"owner": owner, "name": name, "number": self.number},
                },
                what="graphql",
                read_only=True,
            )
            payload = self._json(response)
        except (SetupFailure, DegradedReview) as exc:
            payload = {}
            notes.append(f"linked issues could not be read from GitHub ({exc.message})")
        if payload.get("errors"):
            notes.append(
                "GitHub reported an error listing linked issues: "
                + "; ".join(str(e.get("message", e)) for e in payload["errors"])
            )
        nodes = (
            (((payload.get("data") or {}).get("repository") or {}).get("pullRequest") or {})
            .get("closingIssuesReferences", {})
            .get("nodes", [])
        ) or []
        for node in nodes:
            repo = ((node.get("repository") or {}).get("nameWithOwner") or "").lower()
            number = int(node.get("number") or 0)
            if repo and repo != here:
                notes.append(f"{repo}#{number} is in another repository and was not read")
            elif number and number not in numbers:
                numbers.append(number)

        for match in CLOSING_KEYWORD.finditer(self._pull().get("body") or ""):
            number = int(match.group("number"))
            repo = (match.group("repo") or "").lower()
            if repo and repo != here:
                note = f"{repo}#{number} is in another repository and was not read"
                if note not in notes:
                    notes.append(note)
            elif number not in numbers:
                numbers.append(number)

        return IssueLinks(numbers, notes)

    def get_issue(self, number):
        """The issue payload, or None (with the reason) when it is not an issue."""
        response = self._request(
            "GET", self._repo_url(f"issues/{int(number)}"), allow_404=True, what="issue"
        )
        if response is None:
            return None, f"issue #{number} was not found"
        payload = self._json(response)
        # The key's presence is the signal; its value can be an empty object.
        if "pull_request" in payload:
            return None, f"#{number} is a pull request, not an issue"
        return payload, ""

    # -- writes ----------------------------------------------------------

    def _writer(self):
        if self.writer is None:
            raise SetupFailure(
                "this run holds no posting credential",
                remedy="pass --post with GH_TOKEN_FOR_PR set",
            )
        return self.writer

    def post_summary(self, markdown, prior):
        """Edit this agent's summary in place, or start one."""
        writer = self._writer()
        # Everything posted passes through `redact`, like everything printed:
        # a model that echoed a credential must not publish it (SC-009).
        body = {"body": redact(markdown)}
        if prior and prior.summary_comment_id:
            return writer._request(
                "PATCH",
                writer._repo_url(f"issues/comments/{int(prior.summary_comment_id)}"),
                json_body=body,
            )
        return writer._request(
            "POST", writer._repo_url(f"issues/{self.number}/comments"), json_body=body
        )

    def deliver(self, plan, prior, pr_context):
        """The summary, then every inline comment in ONE review. Returns the
        number of inline comments posted."""
        writer = self._writer()
        self.post_summary(plan.summary_markdown, prior if plan.action == "update_summary" else None)
        if not plan.inline:
            return 0

        url = writer._repo_url(f"pulls/{self.number}/reviews")
        commit = getattr(pr_context, "iteration_commit", "") or ""
        comments = [
            {
                "path": comment.path.lstrip("/"),
                "line": int(comment.right_line),
                "side": "RIGHT",
                "body": redact(comment.markdown),
            }
            for comment in plan.inline
        ]
        count = len(comments)
        body = (
            f"AI code review: {count} inline comment{'s' if count != 1 else ''}. "
            "The summary is in the conversation."
        )
        try:
            writer._request(
                "POST",
                url,
                json_body={"commit_id": commit, "event": "COMMENT", "body": body, "comments": comments},
                what="review",
            )
            return count
        except ReviewRefused:
            self.refused_inline = count
            lines = [
                f"{REFUSED_ANCHOR} for this run's findings (HTTP 422), so they are "
                "listed here instead of on the lines they concern:",
                "",
            ]
            for comment in plan.inline:
                headline = (comment.body or comment.markdown).strip().splitlines()[0]
                lines.append(f"- `{comment.path.lstrip('/')}:{comment.right_line}` - {headline}")
            writer._request(
                "POST",
                url,
                json_body={
                    "commit_id": commit,
                    "event": "COMMENT",
                    "body": redact("\n".join(lines)),
                    "comments": [],
                },
            )
            return 0

    @property
    def write_count(self):
        return self.own_writes + (self.writer.own_writes if self.writer else 0)


def make_github_platform(config, session_factory=None):
    """The read client, with a posting client attached only for a posting run."""
    session_factory = session_factory or (lambda: None)
    writer = None
    if not config.dry_run:
        writer = GitHubClient(config, session=session_factory(), purpose="post")
    return GitHubClient(config, session=session_factory(), purpose="read", writer=writer)
