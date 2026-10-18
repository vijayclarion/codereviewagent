"""Failure taxonomy.

Two kinds of incomplete run, deliberately not conflated (FR-029):

* ``SetupFailure``  - the agent could not start, or could not deliver anything.
  A misconfiguration, an unusable credential, an unreachable pull request, or no
  permission to post. Exits 2, which turns a validation build red, because the
  review will never work until someone changes a setting.

* ``DegradedReview`` - the agent reached the pull request but could not produce a
  full review. The provider was unreachable, the response was unusable after the
  retry, the checklist source was down. Exits 0, so a transient outage never
  gates a merge, and says so on the pull request.

Anything else escaping to the top level is a bug, and ``main`` reports it as a
setup failure rather than pretending a review happened.
"""

EXIT_OK = 0
EXIT_BLOCKING_FINDINGS = 1
EXIT_SETUP_FAILURE = 2
#: Feature 002: a manual run has a human reading the terminal, and nothing here
#: gates a merge. Reporting "no review happened" with the same code as "reviewed,
#: found nothing" is the silence Principle VII forbids - so a degraded manual run
#: exits 3. Pipeline behaviour (DegradedReview.exit_code) is unchanged.
EXIT_DEGRADED = 3


class ReviewAgentError(Exception):
    """Base class so callers can catch either kind at once."""

    exit_code = EXIT_SETUP_FAILURE

    def __init__(self, message, remedy=None):
        super().__init__(message)
        self.message = message
        self.remedy = remedy

    def describe(self):
        """One-line, operator-facing text: what happened and what to change."""
        if self.remedy:
            return f"{self.message} -> {self.remedy}"
        return self.message


class SetupFailure(ReviewAgentError):
    """The review cannot run until a setting changes. Exit 2."""

    exit_code = EXIT_SETUP_FAILURE


class DegradedReview(ReviewAgentError):
    """The review could not complete, but nothing needs fixing here. Exit 0."""

    exit_code = EXIT_OK


class WorkItemAccessDenied(SetupFailure):
    """The credential can read code but not work items (feature 003, FR-023).

    Its own class because the caller treats it differently from every other
    refusal: the story half of the review is lost and the checklist half still
    runs. Catching plain `SetupFailure` there would also swallow a collection
    that is down, which is a different condition with a different correction.
    """

    def __init__(self, endpoint, status, scope="Work Items (read)"):
        super().__init__(
            f"the credential cannot read work items (HTTP {status} from {endpoint}), "
            "so story coverage was not assessed",
            remedy=f"grant {scope} to the token in TFS_PAT, then run the review again",
        )
        self.status = status
        self.scope = scope


class MissingConfiguration(SetupFailure):
    """Required configuration values are absent or unusable.

    Carries every offending value, because reporting them one run at a time is
    the difference between one fix and five (FR-003).
    """

    def __init__(self, problems):
        self.problems = tuple(problems)
        joined = "; ".join(self.problems)
        super().__init__(
            f"configuration is incomplete or invalid: {joined}",
            remedy="set the listed values in .env or as pipeline variables "
            "(see review_agent/.env.example)",
        )
