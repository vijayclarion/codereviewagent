"""The only module that speaks TFS REST (FR-032).

Everything else receives parsed data or calls a method here, which is what makes
the hosting platform replaceable in isolation - and is enforced by
tests/contract/test_import_boundaries.py.

Two things in here are less obvious than they look:

* Certificate trust. ``requests`` validates against ``certifi``, which by
  definition cannot contain an internal CA, so an on-prem collection behind a
  private PKI fails to verify out of the box. ``truststore`` binds verification
  to the OS store instead. Disabling verification is not an option (FR-034).

* An unauthenticated on-prem collection answers with a sign-in *page*, not a 401.
  Without the HTML check below, the symptom is a JSON decode error and the cause
  looks like anything but authentication.
"""

import base64
import time
from urllib.parse import quote

import requests

from .errors import DegradedReview, SetupFailure, WorkItemAccessDenied

USER_AGENT = "najm-ai-code-review/0.1 (+review_agent)"

RETRY_STATUSES = (429, 502, 503, 504)
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = (1, 2, 4)

_truststore_injected = False


def inject_system_trust():
    """Bind TLS verification to the OS trust store. Idempotent."""
    global _truststore_injected
    if _truststore_injected:
        return True
    try:
        import truststore
    except ImportError:
        # Documented fallback: REQUESTS_CA_BUNDLE pointing at the exported CA.
        # Not fatal here - the first request will fail with a clear TLS error.
        return False
    truststore.inject_into_ssl()
    _truststore_injected = True
    return True


#: The work-item surface. `wit` is the collection's own name for it.
WORK_ITEM_PATHS = ("/wit/", "/workitems")


def _is_work_item(url):
    lowered = (url or "").lower()
    return any(fragment in lowered for fragment in WORK_ITEM_PATHS)


def _looks_like_html(text):
    head = (text or "")[:400].lstrip().lower()
    return head.startswith("<!doctype html") or head.startswith("<html")


class TfsClient:
    """Thin, explicit REST client. One method per call in contracts/tfs-endpoints.md."""

    def __init__(self, config, session=None, sleep=time.sleep, purpose="read"):
        """`purpose` selects which credential this client can reach (FR-006).

        A client is built for exactly one of the two tokens and cannot reach the
        other. That is what makes "a dry run never holds a credential that could
        write" a property of construction rather than a promise about behaviour:
        the dry-run path simply never builds a `purpose="post"` client (R9).
        """
        if purpose not in ("read", "post"):
            raise ValueError(f"purpose must be 'read' or 'post' (got {purpose!r})")
        self.config = config
        self.purpose = purpose
        self._sleep = sleep
        inject_system_trust()
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
                "Authorization": self._auth_header(),
            }
        )
        self.write_count = 0

    # -- auth ------------------------------------------------------------

    @property
    def token(self):
        """The one credential this client is allowed to use."""
        if self.purpose == "post":
            return self.config.post_token
        return self.config.tfs_token

    def _auth_header(self):
        # A posting credential is always a PAT (Basic); only the reading path can
        # arrive as a pipeline OAuth token.
        if self.purpose == "read" and self.config.auth_mode == "bearer":
            return f"Bearer {self.token}"
        encoded = base64.b64encode(f":{self.token}".encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"

    # -- transport -------------------------------------------------------

    def _url(self, path, repo=None):
        repo_name = repo or self.config.tfs_repo
        return f"{self.config.api_root}/{path}".replace("{repo}", quote(str(repo_name), safe=""))

    def _params(self, extra=None):
        params = {"api-version": self.config.tfs_api_version}
        if extra:
            params.update({k: v for k, v in extra.items() if v is not None})
        return params

    def _request(self, method, url, params=None, json_body=None, allow_404=False):
        is_write = method.upper() != "GET"
        last_error = None

        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = self.session.request(
                    method, url, params=self._params(params), json=json_body, timeout=60
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < RETRY_ATTEMPTS - 1:
                    self._sleep(RETRY_BACKOFF[attempt])
                    continue
                raise self._transport_failure(url, exc, is_write)

            if response.status_code in RETRY_STATUSES and attempt < RETRY_ATTEMPTS - 1:
                self._sleep(self._retry_after(response, attempt))
                continue

            return self._handle(response, url, is_write, allow_404)

        raise self._transport_failure(url, last_error, is_write)

    def _retry_after(self, response, attempt):
        header = response.headers.get("Retry-After")
        if header:
            try:
                return min(float(header), 30.0)
            except ValueError:
                pass
        return RETRY_BACKOFF[attempt]

    def _transport_failure(self, url, exc, is_write):
        detail = type(exc).__name__ if exc else "unknown transport error"
        if "SSLError" in detail or "SSLCert" in str(exc or ""):
            return SetupFailure(
                f"TLS verification failed for {self._endpoint(url)} ({detail})",
                remedy="install `truststore` (in requirements.txt) or set "
                "REQUESTS_CA_BUNDLE to the internal CA bundle - never disable verification",
            )
        message = f"could not reach {self._endpoint(url)} after {RETRY_ATTEMPTS} attempts ({detail})"
        # A failed write means findings exist but cannot be delivered - that is a
        # setup problem. A failed read just means no review this time.
        return SetupFailure(message, remedy="check network access to the TFS collection") if is_write \
            else DegradedReview(message)

    def _handle(self, response, url, is_write, allow_404):
        status = response.status_code
        endpoint = self._endpoint(url)

        if status == 404 and allow_404:
            return None

        if status in (401, 403):
            # A refused work-item read is its own condition: it costs the story
            # half of the review and nothing else. Classified here because this
            # is the only module that knows which endpoint answered (Principle IV).
            if _is_work_item(url):
                raise WorkItemAccessDenied(endpoint, status)
            if is_write or status == 403:
                raise SetupFailure(
                    f"not permitted to {'write to' if is_write else 'read'} {endpoint} "
                    f"(HTTP {status}, auth mode: {self.config.auth_mode})",
                    remedy="grant the build service identity 'Contribute to pull requests' "
                    "on the repository, or use a PAT with Code (read & write) scope",
                )
            raise SetupFailure(
                f"authentication failed for {endpoint} (HTTP {status}, "
                f"auth mode: {self.config.auth_mode})",
                remedy="check TFS_PAT, or enable 'Allow scripts to access the OAuth token'",
            )

        if status == 404:
            raise SetupFailure(
                f"not found: {endpoint} (HTTP 404)",
                remedy="check TFS_PROJECT, TFS_REPO, and TFS_PR_ID",
            )

        if status == 400 and "api-version" in (response.text or "").lower():
            raise SetupFailure(
                f"the server rejected api-version {self.config.tfs_api_version} at {endpoint}",
                remedy="set TFS_API_VERSION to 5.0, then 4.1, until one is accepted",
            )

        if status >= 400:
            raise SetupFailure(f"unexpected HTTP {status} from {endpoint}")

        if _looks_like_html(response.text):
            raise SetupFailure(
                f"authentication failed for {endpoint}: the collection returned a "
                f"sign-in page instead of JSON",
                remedy="check the credential; for a pipeline run enable "
                "'Allow scripts to access the OAuth token'",
            )

        if is_write:
            self.write_count += 1

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise SetupFailure(f"{endpoint} returned a non-JSON body (HTTP {status})")

    @staticmethod
    def _endpoint(url):
        """URL without the query string - never log a token that rode along."""
        return url.split("?", 1)[0]

    # -- reads -----------------------------------------------------------

    def get_pull_request(self):
        return self._request("GET", self._url("git/repositories/{repo}/pullRequests/%d"
                                              % self.config.tfs_pr_id))

    def get_linked_work_item_ids(self):
        data = self._request(
            "GET",
            self._url("git/repositories/{repo}/pullRequests/%d/workitems" % self.config.tfs_pr_id),
        )
        return [int(item["id"]) for item in (data or {}).get("value", []) if item.get("id")]

    def get_work_item(self, work_item_id):
        return self._request(
            "GET",
            f"{self.config.api_root}/wit/workitems/{int(work_item_id)}",
            params={"$expand": "all"},
        )

    def get_iterations(self):
        data = self._request(
            "GET",
            self._url("git/repositories/{repo}/pullRequests/%d/iterations" % self.config.tfs_pr_id),
        )
        return (data or {}).get("value", [])

    def get_iteration_changes(self, iteration_id):
        return self._request(
            "GET",
            self._url(
                "git/repositories/{repo}/pullRequests/%d/iterations/%d/changes"
                % (self.config.tfs_pr_id, int(iteration_id))
            ),
        )

    def get_file_content(self, path, commit_sha, repo=None):
        """Blob text at a commit, or None when the path does not exist there."""
        data = self._request(
            "GET",
            self._url("git/repositories/{repo}/items", repo=repo),
            params={
                "path": path,
                "versionDescriptor.version": commit_sha,
                "versionDescriptor.versionType": "commit",
                "includeContent": "true",
                "$format": "json",
            },
            allow_404=True,
        )
        if data is None:
            return None
        return data.get("content", "")

    def list_items(self, scope_path, branch, repo=None):
        data = self._request(
            "GET",
            self._url("git/repositories/{repo}/items", repo=repo),
            params={
                "scopePath": scope_path,
                "recursionLevel": "Full",
                "versionDescriptor.version": branch,
                "versionDescriptor.versionType": "branch",
                "$format": "json",
            },
            allow_404=True,
        )
        if data is None:
            return []
        return data.get("value", [])

    def get_file_on_branch(self, path, branch, repo=None):
        data = self._request(
            "GET",
            self._url("git/repositories/{repo}/items", repo=repo),
            params={
                "path": path,
                "versionDescriptor.version": branch,
                "versionDescriptor.versionType": "branch",
                "includeContent": "true",
                "$format": "json",
            },
            allow_404=True,
        )
        if data is None:
            return None
        return data.get("content", "")

    def get_threads(self):
        data = self._request(
            "GET",
            self._url("git/repositories/{repo}/pullRequests/%d/threads" % self.config.tfs_pr_id),
        )
        return [t for t in (data or {}).get("value", []) if not t.get("isDeleted")]

    # -- writes ----------------------------------------------------------

    def create_thread(self, content, thread_context=None):
        """Create a discussion. Always active, never resolved by us (FR-024a)."""
        body = {
            "comments": [{"parentCommentId": 0, "content": content, "commentType": "text"}],
            "status": "active",
        }
        if thread_context:
            body["threadContext"] = thread_context
        return self._request(
            "POST",
            self._url("git/repositories/{repo}/pullRequests/%d/threads" % self.config.tfs_pr_id),
            json_body=body,
        )

    def add_comment(self, thread_id, content):
        return self._request(
            "POST",
            self._url(
                "git/repositories/{repo}/pullRequests/%d/threads/%d/comments"
                % (self.config.tfs_pr_id, int(thread_id))
            ),
            json_body={"parentCommentId": 0, "content": content, "commentType": "text"},
        )

    def update_comment(self, thread_id, comment_id, content):
        return self._request(
            "PATCH",
            self._url(
                "git/repositories/{repo}/pullRequests/%d/threads/%d/comments/%d"
                % (self.config.tfs_pr_id, int(thread_id), int(comment_id))
            ),
            json_body={"content": content},
        )
