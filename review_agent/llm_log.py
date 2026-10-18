"""A durable record of every prompt sent to the provider and every reply.

Off unless asked for. One file per run, one entry per exchange, written and
closed as each exchange completes - because the runs whose prompts you most want
to read are the ones that were killed, and a file assembled in memory has nothing
in it when the process dies.

Two properties matter more than anything else here:

* **One write path.** Exactly one function touches the file, and it redacts.
  A second one would be the leak. The prompt carries the pull request's whole
  diff and the entire checklist corpus, so this is the only reason such a file
  is safe to write at all.

* **Nothing raises.** Every public function is total. A destination that cannot
  be written costs the operator their log, never their review (FR-018). The
  review must be unable to tell that this module exists.

Retention deletes files, and it deletes them inside a directory the *operator*
chose - the first thing in this package to do so. Two guards keep that honest:
a filename pattern that proves this module wrote the file, and a timestamp
comparison that never removes a file newer than the running process. See
`specs/006-llm-prompt-response-log/contracts/retention.md`.
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime

from .config import emit, redact

# --------------------------------------------------------------------------
# Naming
# --------------------------------------------------------------------------

NAME_PREFIX = "llm-pr"
NAME_SUFFIX = ".log"
STAMP_FORMAT = "%Y%m%d-%H%M%S"
DISPLAY_FORMAT = "%Y-%m-%d %H:%M:%S"

#: Proof of authorship. Pruning deletes nothing this does not match, so an
#: operator's own files in the destination are never candidates - however old,
#: however much they look like logs.
LOG_NAME = re.compile(r"^llm-pr\d+-(\d{8}-\d{6})(?:-\d+)?\.log$")

RULE_WIDTH = 69
PENDING_RUN = "pending"

# --------------------------------------------------------------------------
# Values
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LogDestination:
    """Where logs go and how many survive a prune."""

    directory: str
    keep: int = 10

    def __post_init__(self):
        if not self.directory:
            raise ValueError("a log destination needs a directory")
        if not os.path.isabs(self.directory):
            # A relative path here means it was resolved in the wrong process.
            # The child that performs the review runs inside a fetched clone
            # that is deleted moments later, so the operator would get no file
            # and no error - see research D4.
            raise ValueError(
                f"log destination must be absolute, got {self.directory!r}"
            )
        if self.keep < 1:
            raise ValueError("LLM_LOG_KEEP must keep at least the current run's log")

    def path_for(self, pr_id, started):
        """The file for this run. Never an existing path (FR-014a)."""
        base = f"{NAME_PREFIX}{int(pr_id)}-{started.strftime(STAMP_FORMAT)}"
        candidate = os.path.join(self.directory, base + NAME_SUFFIX)
        suffix = 2
        while os.path.exists(candidate):
            candidate = os.path.join(
                self.directory, f"{base}-{suffix}{NAME_SUFFIX}"
            )
            suffix += 1
        return candidate


@dataclass(frozen=True)
class ExchangeRecord:
    """One request to the provider and its outcome."""

    index: int
    chunk: int
    chunk_total: int
    attempt: int
    sent_at: str
    elapsed_ms: int
    prompt: str
    outcome: str = "ok"
    response: str = ""
    failure: str = ""

    def __post_init__(self):
        if self.outcome not in ("ok", "failed"):
            raise ValueError(f"unknown exchange outcome: {self.outcome!r}")
        if self.outcome == "failed" and not self.failure:
            # A failure with no stated reason is the silence the conventions
            # forbid: it is indistinguishable from a bug in this module.
            raise ValueError("a failed exchange must state why")
        if self.outcome == "ok" and self.failure:
            raise ValueError("a successful exchange has no failure reason")
        if self.attempt not in (1, 2):
            raise ValueError("an exchange is a first send or its one retry")
        if self.chunk < 1 or self.chunk_total < 1 or self.chunk > self.chunk_total:
            raise ValueError("chunk position outside the run's chunks")


# --------------------------------------------------------------------------
# The only way to write
# --------------------------------------------------------------------------


def _write(path, text, mode="a"):
    """THE write path. Every byte that reaches a log passes through `redact`.

    There is deliberately no second one. A future section added to the format
    cannot forget to redact, because there is no other door.
    """
    with open(path, mode, encoding="utf-8", errors="replace", newline="\n") as handle:
        handle.write(redact(text))


def _rule(text, char):
    """`text` followed by `char` to a fixed width - anchored, so a diff line
    that happens to contain dashes cannot be mistaken for a section boundary."""
    lead = f"{text} " if text else ""
    return lead + char * max(3, RULE_WIDTH - len(lead))


def _count(value):
    return f"{value:,}"


# --------------------------------------------------------------------------
# The session
# --------------------------------------------------------------------------


class LogSession:
    """One run's log. Stateful, because `enabled` and the count both move.

    Every method is total. The first failure states its reason once, disables
    the session, and the run carries on untouched.
    """

    def __init__(self, path="", pr_id=0, started=None, enabled=False):
        self.path = path
        self.pr_id = pr_id
        self.started = started or datetime.now()
        self.enabled = bool(enabled and path)
        self.count = 0
        self.run_id = PENDING_RUN

    # -- lifecycle ---------------------------------------------------------

    def head(self, provider="", model="", agent_source=""):
        """The opening block. `run` is pending until the pull request is read."""
        if not self.enabled:
            return
        block = "\n".join(
            [
                _rule("=== ai-review llm log", "="),
                f"run          : {self.run_id}",
                f"pull request : {self.pr_id}",
                f"provider     : {provider} / {model}" if provider else "provider     : -",
                f"started      : {self.started.strftime(DISPLAY_FORMAT)}",
                f"agent source : {agent_source or 'unknown'}",
                _rule("", "-"),
                "",
                "",
            ]
        )
        self._guarded(lambda: _write(self.path, block), "write the log header")

    def set_run_id(self, run_id):
        """Resolve `pending` once the pull request context arrives.

        Only while the file still holds nothing but the header - which is always
        the case, because the context is read long before the first exchange.
        Rewriting is therefore a few hundred bytes, never the whole log.
        """
        if not self.enabled or self.count or not run_id:
            return
        self.run_id = str(run_id)

        def _resolve():
            with open(self.path, encoding="utf-8", errors="replace") as handle:
                current = handle.read()
            _write(
                self.path,
                current.replace(
                    f"run          : {PENDING_RUN}", f"run          : {self.run_id}", 1
                ),
                mode="w",
            )

        self._guarded(_resolve, "record the run identifier")

    def record(self, record):
        """Append one exchange and close the file behind it (FR-010a)."""
        if not self.enabled:
            return
        self.count += 1
        self._guarded(
            lambda: _write(self.path, _render(record)), "write a log entry"
        )

    def close(self, outcome):
        """The closing summary. A run that is killed never reaches this, and
        the missing line is how a reader knows it did not finish (FR-010b)."""
        if not self.enabled:
            return
        plural = "" if self.count == 1 else "s"
        foot = (
            _rule(
                f"=== end | {self.count} exchange{plural} | outcome {outcome}", "="
            )
            + "\n"
        )
        self._guarded(lambda: _write(self.path, foot), "write the log summary")

    # -- failure isolation -------------------------------------------------

    def _guarded(self, action, what):
        """Run `action`; on any failure say so once and go quiet for good."""
        try:
            action()
        except OSError as exc:
            self.enabled = False
            emit(f"llm log: could not {what} - {type(exc).__name__}: {exc}")


#: The session a run gets when logging is off: every call is a no-op, so
#: `run_review` needs no conditional branches and the disabled path is
#: exercised by the whole existing suite.
def disabled_session():
    return LogSession(enabled=False)


def _render(record):
    """One entry, per contracts/log-format.md."""
    header = _rule(
        f"--- exchange {record.index} of {record.chunk_total} "
        f"| chunk {record.chunk} of {record.chunk_total} "
        f"| attempt {record.attempt}",
        "-",
    )
    body_rule = "- " * ((RULE_WIDTH - 1) // 2) + "-"
    if record.outcome == "ok":
        outcome = (
            f"outcome  : ok in {_count(record.elapsed_ms)} ms "
            f"| response {_count(len(record.response))} characters"
        )
        tail = record.response
    else:
        outcome = f"outcome  : failed in {_count(record.elapsed_ms)} ms"
        tail = record.failure
    return "\n".join(
        [
            header,
            f"sent     : {record.sent_at}",
            f"prompt   : {_count(len(record.prompt))} characters",
            body_rule,
            record.prompt,
            body_rule,
            outcome,
            body_rule,
            tail,
            "",
            "",
        ]
    )


# --------------------------------------------------------------------------
# Retention
# --------------------------------------------------------------------------


def prune(destination, started):
    """Delete this module's own oldest logs, leaving room for the new one.

    Returns (removed_count, problem). Deletes nothing it cannot prove it wrote,
    and nothing newer than `started` - which is what stops one run removing the
    log a concurrent run is writing.
    """
    try:
        names = os.listdir(destination.directory)
    except OSError as exc:
        return 0, f"could not read {destination.directory} ({type(exc).__name__})"

    ours = started.strftime(STAMP_FORMAT)
    candidates = []
    for name in names:
        match = LOG_NAME.match(name)
        if not match or match.group(1) >= ours:
            continue
        full = os.path.join(destination.directory, name)
        if os.path.isfile(full):
            candidates.append((match.group(1), name, full))

    candidates.sort()
    excess = len(candidates) - (destination.keep - 1)
    if excess <= 0:
        return 0, ""

    removed, problem = 0, ""
    for _stamp, _name, full in candidates[:excess]:
        try:
            os.remove(full)
            removed += 1
        except OSError as exc:
            problem = problem or f"could not remove {full} ({type(exc).__name__})"
    return removed, problem


# --------------------------------------------------------------------------
# Opening a session
# --------------------------------------------------------------------------


def open_session(config, provider="", model="", agent_source="", now=None):
    """The session for this run, or a no-op one when logging is off.

    Creates the destination, prunes, writes the header, and says where the file
    is and what it removed. Any failure leaves the review untouched.
    """
    if not getattr(config, "llm_log", False):
        return disabled_session()

    started = now or datetime.now()
    try:
        destination = LogDestination(config.llm_log_dir, config.llm_log_keep)
        os.makedirs(destination.directory, exist_ok=True)
    except (OSError, ValueError) as exc:
        emit(f"llm log: disabled - {type(exc).__name__}: {exc}")
        return disabled_session()

    removed, problem = prune(destination, started)
    if problem:
        emit(f"llm log: {problem}")

    try:
        path = destination.path_for(config.tfs_pr_id, started)
    except OSError as exc:
        emit(f"llm log: disabled - {type(exc).__name__}: {exc}")
        return disabled_session()

    session = LogSession(
        path=path, pr_id=config.tfs_pr_id, started=started, enabled=True
    )
    session.head(provider=provider, model=model, agent_source=agent_source)
    if not session.enabled:
        return session

    emit(f"llm log: {path}")
    emit(f"llm log: removed {removed or 'no'} older log{'' if removed == 1 else 's'} "
         f"(keeping {destination.keep})")
    return session
