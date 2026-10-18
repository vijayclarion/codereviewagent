"""Entrypoint: parse arguments, orchestrate the review, set the exit code.

Exit codes are the contract (contracts/cli-contract.md):

    0  review completed, or degraded - the default outcome, findings or not
    1  blocking findings, only with FAIL_ON_CONTRADICTION=true
    2  setup failure - something must change before a review can ever work

0 covering both "reviewed fine" and "could not review" is deliberate: a provider
outage must not gate anyone's merge. What a human needs to tell them apart lives
in the summary discussion and the phase log, not the exit code.
"""

import argparse
import os
import sys
import time
from dataclasses import replace
from datetime import datetime

# Support both `python review_agent/main.py` and `python -m review_agent.main`.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from review_agent import __version__, checklist as checklist_module
from review_agent import diff_builder, output_layer, parser, prompt_builder, selection, stories
from review_agent.config import emit, emit_error, load_config
from review_agent.dedupe import read_prior_feedback
from review_agent.errors import (
    EXIT_BLOCKING_FINDINGS,
    EXIT_OK,
    EXIT_SETUP_FAILURE,
    DegradedReview,
    ReviewAgentError,
    SetupFailure,
    WorkItemAccessDenied,
)
from review_agent import llm_log as llm_log_module
from review_agent.llm_adapter import call_llm
from review_agent.models import (
    DeclaredScope,
    ReviewReport,
    RunInventory,
    WorkItem,
)
from review_agent.platform import make_platform
from review_agent.tfs_client import TfsClient

EPILOG = """\
configuration:
  All values come from .env (manual runs) or pipeline variables (validation
  builds); pipeline values win. See review_agent/.env.example for the full list.

  Required:  TFS_BASE_URL TFS_PROJECT TFS_REPO TFS_PR_ID LLM_PROVIDER LLM_MODEL
  Auth:      SYSTEM_ACCESSTOKEN (pipeline) or TFS_PAT (manual) - exactly one
  Provider:  LLM_API_KEY (unless ollama), LLM_BASE_URL (azure/ollama)
  Checklist: CHECKLIST_REPO_URL CHECKLIST_PATH CHECKLIST_FILE_PATTERN
             CHECKLIST_BRANCH
  Behaviour: DRY_RUN (default true)  FAIL_ON_CONTRADICTION (default false)
  Scope:     REVIEW_EXCLUDE_PATTERNS REVIEW_EXCLUDE_MODE REVIEW_MAX_FILES
             REVIEW_MAX_DIFF_LINES LLM_MAX_PROMPT_TOKENS LLM_MAX_OUTPUT_TOKENS
             LLM_MAX_CHUNK_LINES (optional cap)
  Platform:  PLATFORM (tfs | github, default tfs)  STORY_SOURCE (tfs |
             github-issues | none, default: the platform's own)
  GitHub:    GH_REPOSITORY GH_PR_NUMBER GH_TOKEN (aliases GITHUB_TOKEN,
             GIT_REPO_TOKEN)  GH_TOKEN_FOR_PR (to post)  GH_API_URL
             GH_CHECKLIST_REPO GH_CHECKLIST_TOKEN GH_AGENT_REPO
  Cost:      LLM_PRICE_INPUT_PER_MTOK LLM_PRICE_OUTPUT_PER_MTOK LLM_PRICE_CURRENCY

exit codes:
  0  review completed or degraded (default - never blocks a merge)
  1  blocking findings, only when FAIL_ON_CONTRADICTION=true
  2  setup failure - configuration, credential, or permission
"""


class PhaseLog:
    """One line per phase, so a build log answers "what happened" on its own.

    Every line goes through `emit`, so a value that should not be printed cannot
    ride along in a count or a message.
    """

    def __init__(self, run_id="-", enabled=True):
        self.run_id = run_id
        self.enabled = enabled
        self._start = time.monotonic()
        self._phase_start = self._start

    def set_run_id(self, run_id):
        self.run_id = run_id

    def start(self):
        self._phase_start = time.monotonic()

    def phase(self, name, outcome="ok", **counts):
        elapsed = int((time.monotonic() - self._phase_start) * 1000)
        self._phase_start = time.monotonic()
        if not self.enabled:
            return
        extras = " ".join(f"{k}={v}" for k, v in counts.items() if v is not None)
        line = f"ai-review run={self.run_id} phase={name} outcome={outcome} ms={elapsed}"
        emit(f"{line} {extras}".rstrip())

    def done(self, outcome, exit_code):
        total = int((time.monotonic() - self._start) * 1000)
        if self.enabled:
            emit(
                f"ai-review run={self.run_id} phase=done outcome={outcome} "
                f"ms={total} exit={exit_code}"
            )


NO_STORY_LINKED = "no work item is linked to this pull request"


def _fetch_story(client, log):
    """Linked TFS work items, and the reason when there are none.

    Feature 007 moved the logic to `stories.fetch_tfs` unchanged; this name stays
    because the suite and earlier documents refer to it.
    """
    return stories.fetch_tfs(client, log)


def _report_degraded(config, reason, platform, prior, log):
    """Say on the pull request that the review could not run, and why (FR-029).

    Silence would be indistinguishable from a clean review, which is the one
    outcome a degraded run must never be mistaken for.
    """
    markdown = output_layer.render_degraded_summary(reason)
    if config.dry_run:
        emit("")
        emit(markdown)
        log.phase("post", outcome="dry-run", summary="degraded")
        return
    try:
        platform.post_summary(markdown, prior)
        log.phase("post", outcome="degraded", summary="posted")
    except Exception as exc:
        # Losing the notice is not worth turning a degraded run into a red build.
        log.phase("post", outcome="degraded-unposted", error=type(exc).__name__)


def _fetch_checklist(client, config, log):
    """(corpus, what the prompt should use). Never raises.

    The document path runs first because it is the one that produces citable
    rules. The text path is the fallback rather than a competitor: an operator
    configured exactly as feature 002 left them must not quietly lose their
    checklist the day this feature lands.
    """
    corpus = checklist_module.obtain_corpus(config)
    if corpus.available:
        log.phase(
            "checklists",
            documents=len(corpus.documents),
            rules=corpus.rule_count,
            skipped=len(corpus.documents_skipped),
        )
        return corpus, corpus

    text = checklist_module.fetch_checklist(
        client, config, patterns=checklist_module.text_patterns(config)
    )
    log.phase(
        "checklists",
        outcome="ok" if text.available else "degraded",
        documents=len(corpus.documents),
        files=len(text.sources),
    )
    return corpus, text if text.available else corpus


def _build_inventory(corpus, work_items, story_reason, report):
    """Everything the run applied, in one object the summary renders (FR-026)."""
    applied = corpus.rule_count
    omitted = len(corpus.dropped_for_budget)
    return RunInventory(
        source=corpus.source,
        documents=tuple(corpus.documents),
        rules_read=applied + omitted,
        rules_applied=applied,
        rules_omitted=omitted,
        selection_basis=corpus.selection_basis,
        work_items=tuple(w.id for w in work_items),
        criteria_judged=len(report.coverage),
        story_unavailable_reason=story_reason or ("" if work_items else NO_STORY_LINKED),
        dropped_citations=tuple(report.dropped_citations),
    )


def run_review(config, log, agent_source=""):
    """The pipeline. Returns a ReviewReport; raises SetupFailure / DegradedReview."""
    # Feature 006. Opened before anything can fail, so that a run which never
    # reaches the provider still leaves a file saying so (FR-011). A no-op
    # session when logging is off, which is why nothing below is conditional.
    llm_session = llm_log_module.open_session(
        config,
        provider=config.llm_provider,
        model=config.llm_model,
        agent_source=agent_source,
    )
    # Feature 007: the hosting platform. `TfsClient` is looked up here, at call
    # time, so a test that replaces `main.TfsClient` is the one that runs.
    client = make_platform(config, tfs_factory=TfsClient)
    # Feature 007 (D15): tokens and cost, accumulated whether or not logging is on.
    usage = llm_log_module.RunUsage.for_config(config)

    pr_context = client.get_pull_request_context()
    declared_scope = DeclaredScope.from_description(pr_context.description)
    log.phase(
        "pullrequest",
        source=pr_context.source_branch or "-",
        target=pr_context.target_branch or "-",
        scope="parsed" if declared_scope.parsed else "absent",
        platform=pr_context.platform if pr_context.platform != "tfs" else None,
        draft=pr_context.is_draft if pr_context.platform != "tfs" else None,
    )

    story_outcome = stories.fetch_stories(config, client, log)
    work_items, story_reason = story_outcome.work_items, story_outcome.reason

    corpus, checklist = _fetch_checklist(client, config, log)

    revision = client.get_revision()
    pr_context = pr_context.with_iteration(revision.iteration_id, revision.head, revision.base)
    log.set_run_id(pr_context.run_id)
    llm_session.set_run_id(pr_context.run_id)

    entries = client.get_changed_files(revision)
    change_set, pre_skipped = diff_builder.build_change_set(client, pr_context, entries)
    reviewable = selection.select_reviewable(
        change_set, config, work_items=work_items, checklist=checklist, pre_skipped=pre_skipped
    )
    # Rules are ranked against the files that survived selection, so the corpus
    # the model sees is the part of it that relates to what actually changed.
    if corpus.available:
        corpus = selection.select_rules(corpus, reviewable, config.checklist_max_chars)
        checklist = corpus
        log.phase(
            "rules",
            applied=corpus.rule_count,
            omitted=len(corpus.dropped_for_budget),
        )
    log.phase(
        "changes",
        changed=len(entries),
        reviewed=len(reviewable.reviewed),
        excluded=len(reviewable.excluded),
        unreviewed=len(reviewable.unreviewed),
        lines=reviewable.total_diff_lines,
    )

    prior = read_prior_feedback(client)
    log.phase("prior", posted=len(prior.posted_fingerprints), summary=bool(prior.summary_thread_id))

    notes = []
    if pr_context.is_draft:
        notes.append("This pull request is a draft; it was reviewed because it was asked for.")
    notes.extend(f"Story source: {note}." for note in story_outcome.notes)
    if story_reason:
        notes.append(
            f"No story coverage was assessed: {story_reason}. This is a "
            "checklist-only review."
        )
    if not checklist.available:
        notes.append(
            f"No checklist was applied ({checklist.unavailable_reason}). This is a "
            "coverage-only review."
        )

    # Nothing reviewable is a real answer, not a failure (FR-014d).
    if reviewable.is_empty:
        report = ReviewReport(
            summary="There was nothing to review in this pull request: no reviewable "
            "text changes remained after exclusions.",
            skipped=reviewable.excluded,
            unreviewed=reviewable.unreviewed,
            notes=tuple(notes),
        )
        report = replace(
            report, inventory=_build_inventory(corpus, work_items, story_reason, report)
        )
        log.phase("llm", outcome="skipped", chunks=0)
        llm_session.close("no exchange", usage)
        _deliver(config, report, work_items, pr_context, reviewable, client, prior, log)
        return report

    # Feature 007: chunks are planned by token budget, and every prompt carries
    # the PR outline. The plan and outline are kept for the synthesis pass.
    review = prompt_builder.build_review(
        work_items, declared_scope, checklist, reviewable, pr_context, config
    )
    prompts = review.prompts
    log.phase(
        "plan",
        chunks=len(prompts),
        budget=review.plan.budget_tokens,
        groups=len(review.plan.groups),
    )

    results, retries = [], 0
    try:
        for chunk_index, prompt in enumerate(prompts, start=1):
            send = _recording_sender(
                config, llm_session, chunk_index, len(prompts), usage=usage
            )
            result, used_retry = parser.parse_with_retry(
                prompt,
                config,
                send,
                prompt_builder.STRICTER_RETRY,
            )
            results.append(result)
            retries += used_retry
    except DegradedReview as exc:
        # The provider was unreachable, or its response was unusable after the
        # retry. Say so on the pull request and exit 0 - an outage must not gate
        # a merge (FR-029).
        log.phase(
            "llm", outcome="degraded", chunks=len(prompts), retries=retries, **_usage_extras(usage)
        )
        llm_session.close("degraded", usage)
        emit(f"llm usage: {usage.describe()}")
        _report_degraded(config, exc.message, client, prior, log)
        degraded = ReviewReport(
            summary=f"The review could not be completed: {exc.message}",
            outcome="degraded",
            degraded_reason=exc.message,
            skipped=reviewable.excluded,
            unreviewed=reviewable.unreviewed,
            notes=tuple(notes),
        )
        return replace(
            degraded,
            inventory=_build_inventory(corpus, work_items, story_reason, degraded),
            usage=usage,
        )
    log.phase("llm", chunks=len(prompts), retries=retries, **_usage_extras(usage))

    merged = parser.merge_results(results)
    merged, synthesis_state = _synthesise(
        config, llm_session, review, work_items, merged, notes, log, usage
    )
    # The APPLIED checklist, which may be the text path's - resolution only
    # applies where there are identifiers to resolve against.
    report = parser.build_report(
        merged, declared_scope, work_items, reviewable, notes, corpus=checklist
    )
    report = replace(
        report,
        inventory=_build_inventory(corpus, work_items, story_reason, report),
        synthesis=synthesis_state,
        usage=usage,
    )
    log.phase(
        "parse",
        coverage=len(report.coverage),
        violations=len(report.checklist_violations),
        issues=len(report.code_issues),
        cross_file=len(report.cross_file_issues),
        false_claims=len(report.false_coverage_claims),
    )

    llm_session.close("complete", usage)
    emit(f"llm usage: {usage.describe()}")
    _deliver(config, report, work_items, pr_context, reviewable, client, prior, log)
    return report


SYNTHESIS_INCOMPLETE = "Synthesis did not complete: {reason}. Cross-file issues may be missing."


def _usage_extras(usage):
    """`tokens_in= tokens_out= cost=` for the phase line - omitted with no call."""
    if not usage.calls:
        return {}
    cost = usage.cost
    return {
        "tokens_in": usage.input_tokens,
        "tokens_out": usage.output_tokens,
        "cost": f"{cost:.4f}{usage.currency}" if cost is not None else "n/a",
    }


def _synthesise(config, llm_session, review, work_items, merged, notes, log, usage=None):
    """The one extra call of a multi-chunk review (feature 007, D12).

    Returns (merged results, synthesis state). A failure here costs the
    synthesis and nothing else: the per-chunk findings came from seeing the
    code and stand on their own (FR-020).
    """
    if len(review.prompts) <= 1:
        return merged, "not needed"
    prompt = prompt_builder.build_synthesis_prompt(
        review.outline, work_items, merged, merged.get("change_notes", [])
    )
    send = _recording_sender(
        config, llm_session, len(review.prompts), len(review.prompts), kind="synthesis",
        usage=usage,
    )
    try:
        synthesis, _retried = parser.parse_synthesis_with_retry(
            prompt, send, prompt_builder.STRICTER_RETRY
        )
    except DegradedReview as exc:
        log.phase("synthesis", outcome="failed")
        notes.append(SYNTHESIS_INCOMPLETE.format(reason=exc.message))
        return merged, f"failed: {exc.message}"
    log.phase("synthesis", cross_file=len(synthesis["cross_file_issues"]))
    return parser.apply_synthesis(merged, synthesis), "complete"


def _log_exchange(llm_session, **fields):
    """Build and append one record, inside the session's guard.

    Feature 007 (D16): building a record can fail too - an invariant, an odd
    value - and logging must never be the reason a review fails.
    """
    if not llm_session.enabled:
        return
    llm_session._guarded(
        lambda: llm_session.record(
            llm_log_module.ExchangeRecord(index=llm_session.count + 1, **fields)
        ),
        "build a log entry",
    )


def _recording_sender(config, llm_session, chunk_index, chunk_total, kind="review", usage=None):
    """The provider callable for one chunk, recording each send (feature 006).

    `parse_with_retry` calls this once, or twice when the first response will
    not parse - the second time with the stricter instruction appended. Both are
    exchanges and both are recorded, which is what makes an unparseable run
    explainable after the fact.

    Feature 007: `call_llm` returns an `LlmText` (or raises an error) carrying
    `.sends` - one entry per HTTP attempt - and the provider's own usage. Each
    send becomes its own record, so a timeout followed by success is two
    entries; and each send's usage is added to the run's totals. A test fake
    returns a plain `str` with neither, and gets exactly one record, as before.

    `call_llm` is looked up on the module at call time, never captured: seven
    tests replace `main.call_llm` with a fake, and a captured reference would
    silently ignore every one of them.
    """
    state = {"attempt": 0}
    common = {
        "chunk": chunk_index,
        "chunk_total": chunk_total,
        "kind": kind,
        "provider": getattr(config, "llm_provider", "") or "",
        "model": getattr(config, "llm_model", "") or "",
    }

    def _record_all(text, sent_at, started, sends, final_failure=None, response=""):
        attempt = state["attempt"]
        if not sends:
            if usage is not None:
                usage.add()
            if final_failure is not None:
                _log_exchange(
                    llm_session, attempt=attempt, sent_at=sent_at,
                    elapsed_ms=int((time.monotonic() - started) * 1000), prompt=text,
                    outcome="failed", failure=final_failure, **common,
                )
            else:
                _log_exchange(
                    llm_session, attempt=attempt, sent_at=sent_at,
                    elapsed_ms=int((time.monotonic() - started) * 1000), prompt=text,
                    outcome="ok", response=response, **common,
                )
            return
        last = len(sends) - 1
        for position, record in enumerate(sends):
            tokens = record.usage
            input_tokens = getattr(tokens, "input", None)
            output_tokens = getattr(tokens, "output", None)
            if usage is not None:
                usage.add(input_tokens, output_tokens)
            if record.outcome == "ok":
                fields = {"outcome": "ok", "response": record.text or str(response)}
            else:
                reason = record.detail
                if record.outcome == "retried":
                    reason = f"{record.detail} - retried"
                elif position == last and final_failure:
                    reason = final_failure
                fields = {"outcome": "failed", "failure": reason}
            _log_exchange(
                llm_session, attempt=attempt, send=min(record.number, 3), sent_at=sent_at,
                elapsed_ms=record.elapsed_ms, prompt=text,
                input_tokens=input_tokens, output_tokens=output_tokens, **common, **fields,
            )

    def send(text):
        state["attempt"] = min(state["attempt"] + 1, 2)
        started = time.monotonic()
        sent_at = datetime.now().strftime(llm_log_module.DISPLAY_FORMAT)
        try:
            response = call_llm(text, config)
        except ReviewAgentError as exc:
            _record_all(text, sent_at, started, getattr(exc, "sends", None), final_failure=exc.message)
            raise  # unchanged: same type, same message (FR-017)
        _record_all(text, sent_at, started, getattr(response, "sends", None), response=response)
        return response

    return send


def _deliver(config, report, work_items, pr_context, reviewable, client, prior, log):
    plan = output_layer.build_plan(
        report, work_items, pr_context, reviewable, diff_builder.map_line, prior
    )
    if config.dry_run:
        output_layer.print_plan(plan)
        log.phase(
            "post",
            outcome="dry-run",
            inline=len(plan.inline),
            suppressed=len(plan.suppressed),
            summary=plan.action.replace("_summary", ""),
        )
        return plan

    posted = client.deliver(plan, prior, pr_context)
    log.phase(
        "post",
        inline=posted,
        suppressed=len(plan.suppressed),
        summary=plan.action.replace("_summary", ""),
    )
    return plan


def build_parser():
    parser = argparse.ArgumentParser(
        prog="review_agent",
        description="Review a TFS pull request against its user story and the "
        "shared checklists. A reviewer aid, not a merge gate.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="print the feedback, post nothing (overrides DRY_RUN)",
    )
    mode.add_argument(
        "--post",
        action="store_true",
        help="post the feedback to the pull request (overrides DRY_RUN)",
    )
    parser.add_argument("--pr", type=int, metavar="ID", help="override TFS_PR_ID")
    parser.add_argument(
        "--local",
        action="store_true",
        help="review with this working copy instead of the fetched agent source",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress the phase log")
    parser.add_argument(
        "--log-llm",
        action="store_true",
        help="write the prompts and responses to a log file (overrides LLM_LOG)",
    )
    parser.add_argument("--version", action="version", version=f"review_agent {__version__}")
    return parser


def resolve_dry_run(args):
    if args.dry_run:
        return True
    if args.post:
        return False
    return None  # fall through to DRY_RUN


def main(argv=None, agent_source=None):
    args = build_parser().parse_args(argv)
    log = PhaseLog(enabled=not args.quiet)

    # FR-012b: say which copy of the review logic is about to run, before it runs
    # anything. A review from an uncommitted working copy must never be mistaken
    # for one produced by the committed logic.
    if agent_source is not None:
        emit(f"review logic: {agent_source.description}")

    try:
        config = load_config(
            pr_id_override=args.pr,
            dry_run_override=resolve_dry_run(args),
            local_logic_override=args.local,
            llm_log_override=args.log_llm,
        )
        log.phase("config", mode="dry-run" if config.dry_run else "post", auth=config.auth_mode)
    except ReviewAgentError as exc:
        emit_error(f"ai-review setup failure: {exc.describe()}")
        log.done("setup-failure", EXIT_SETUP_FAILURE)
        return EXIT_SETUP_FAILURE

    try:
        outcome = run_review(
            config, log, agent_source=agent_source.description if agent_source else ""
        )
    except SetupFailure as exc:
        emit_error(f"ai-review setup failure: {exc.describe()}")
        log.done("setup-failure", EXIT_SETUP_FAILURE)
        return EXIT_SETUP_FAILURE
    except DegradedReview as exc:
        # Reported, posted where possible, and explicitly not a merge gate.
        emit(f"ai-review degraded: {exc.describe()}")
        log.done("degraded", EXIT_OK)
        return EXIT_OK
    except Exception as exc:  # never claim a review happened when it did not
        emit_error(f"ai-review unexpected failure: {type(exc).__name__}: {exc}")
        log.done("error", EXIT_SETUP_FAILURE)
        return EXIT_SETUP_FAILURE

    exit_code = (
        EXIT_BLOCKING_FINDINGS
        if config.fail_on_contradiction and outcome.has_blocking_findings
        else EXIT_OK
    )
    log.done(outcome.status, exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
