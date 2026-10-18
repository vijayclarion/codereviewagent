"""Fetch the review logic, then run it (FR-012, FR-012a, FR-012b, research R2).

The problem this solves: a developer runs the agent from whatever copy happens to
be on their machine, which may be behind, ahead, or edited. A review produced by
uncommitted logic is not the review the team's rules describe.

So the default path fetches the agent repository and **re-executes** the review
inside that clone. Re-exec rather than a sys.path trick is the whole point: by
the time this module runs, the local package's modules are already imported, and
injecting a path would review with a mixture of two copies - exactly the
ambiguity the clarification was asked to remove.

``--local`` skips the fetch and runs the working copy, because otherwise
developing the agent would mean committing and pushing every experiment.

Either way the child reports which copy ran, from the marker this module sets.
A review can therefore never be mistaken for one produced by committed logic.
"""

import os
import subprocess
import sys

from . import source_fetch
from .config import bootstrap_marker, child_environment, emit, emit_error, load_config
from .errors import EXIT_SETUP_FAILURE, ReviewAgentError, SetupFailure
from .models import AgentSource

#: Set in the child's environment; its presence stops the child re-fetching, and
#: its value is the commit the child reports as its provenance. Read back through
#: config.bootstrap_marker(), so environment access still lives in one module.
MARKER_ENV = "REVIEW_AGENT_BOOTSTRAPPED"
MARKER_REPO_ENV = "REVIEW_AGENT_BOOTSTRAPPED_REPO"
MARKER_REF_ENV = "REVIEW_AGENT_BOOTSTRAPPED_REF"

#: Feature 006. The child re-reads its own configuration, and its working
#: directory is not the operator's - so the resolved log destination travels
#: with it rather than being worked out again at the far end.
LOG_ENV = "LLM_LOG"
LOG_DIR_ENV = "LLM_LOG_DIR"


def already_bootstrapped():
    return bool(bootstrap_marker()["commit"])


def source_from_marker():
    """The AgentSource for a process that was launched by a bootstrap."""
    marker = bootstrap_marker()
    return AgentSource(
        mode="fetched",
        commit=marker["commit"],
        repo=marker["repo"],
        ref=marker["ref"],
    )


def local_source():
    return AgentSource(mode="local")


def _child_env(cloned, config=None):
    parent = os.path.dirname(cloned.path)
    overrides = {
        MARKER_ENV: cloned.commit or "unknown",
        MARKER_REPO_ENV: cloned.repo,
        MARKER_REF_ENV: cloned.ref,
    }
    # Feature 006 (FR-003a): the log destination is resolved HERE, where the
    # operator launched the agent. The child runs with its working directory
    # inside the fetched clone - which this module deletes when the run ends -
    # so a relative path resolved there would put the log somewhere that no
    # longer exists, with no error to show for it.
    if config is not None:
        overrides[LOG_DIR_ENV] = config.llm_log_dir
        overrides[LOG_ENV] = "true" if config.llm_log else "false"
    env = child_environment(overrides)
    # The fetched tree must win over anything already importable, so the review
    # cannot silently run a mixture of the two copies.
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join([parent] + ([existing] if existing else []))
    return env


def run_fetched(cloned, argv, runner=subprocess.run, config=None):
    """Execute the review inside the fetched clone and return its exit code."""
    child = runner(
        [sys.executable, "-m", "review_agent.run", *argv],
        cwd=os.path.dirname(cloned.path),
        env=_child_env(cloned, config),
    )
    return child.returncode


def main(argv=None, runner=subprocess.run, fetcher=source_fetch.clone):
    """The `python -m review_agent` entry point."""
    from . import main as main_module
    from . import run as run_module

    argv = list(sys.argv[1:] if argv is None else argv)
    args = main_module.build_parser().parse_args(argv)

    # A child already running inside a fetched clone reviews directly; fetching
    # again would recurse forever.
    if already_bootstrapped():
        return run_module.main(argv, agent_source=source_from_marker())

    if args.local:
        emit("review logic: LOCAL WORKING COPY (--local)")
        return run_module.main(argv, agent_source=local_source())

    try:
        config = load_config(
            pr_id_override=args.pr,
            dry_run_override=main_module.resolve_dry_run(args),
            local_logic_override=args.local,
            llm_log_override=args.log_llm,
        )
    except ReviewAgentError as exc:
        emit_error(f"ai-review setup failure: {exc.describe()}")
        return EXIT_SETUP_FAILURE

    cloned = None
    try:
        cloned = fetcher(config, config.agent_repo, ref=config.agent_ref)
    except SetupFailure as exc:
        # Never fall back to the local copy silently: a fetch that failed and a
        # fetch that was never asked for must not produce the same review
        # (FR-014).
        emit_error(
            "ai-review setup failure: the review logic could not be obtained - "
            f"{exc.describe()}"
        )
        return EXIT_SETUP_FAILURE

    try:
        return run_fetched(cloned, argv, runner=runner, config=config)
    finally:
        source_fetch.cleanup(cloned.path if cloned else None)
