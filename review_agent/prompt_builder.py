"""Assemble the review prompt.

The classification rules are stated verbatim in substance, per spec section 6.
They are the load-bearing part of this module: without them a model treats every
unimplemented acceptance criterion as a defect, which would make the agent noise
on every partial pull request - and partial pull requests are the normal case.
"""

from .models import Checklist

SYSTEM_ROLE = (
    "You are a senior code reviewer. You review a pull request against the user "
    "story it implements and against the team's shared code-review checklist. You "
    "reason only over the diff text you are shown; you cannot run or test the code."
)

RULES = """\
A pull request often implements only PART of a user story.
Do NOT treat an unaddressed acceptance criterion as a defect.
For each acceptance criterion, classify as exactly one:
  - "appears_addressed"      the diff plausibly implements it
  - "not_addressed"          no related changes (NEUTRAL - never an error)
  - "possible_contradiction" the diff conflicts with it (the only loud flag)

The PR description has a "Covered / Not in this PR" section. Treat the "Covered"
list as the author's authoritative scope. BUT still verify each covered item
against the diff: if the description claims an item is covered and the diff does
not implement it, report it as a false coverage claim.

Check the diff against each checklist item. Report only real violations.
Each checklist rule is shown as "[IDENTIFIER] rule text". When you report a
violation, set "rule_id" to that identifier exactly as shown, so the finding can
be traced back to the document it came from. Never invent an identifier: a rule
you cannot cite is a rule you should not report.

Respond with ONLY the JSON object described below - no prose, no markdown fences."""

CONTRACT = """\
{
  "coverage": [
    {"criterion": "...", "status": "appears_addressed|not_addressed|possible_contradiction", "evidence": "..."}
  ],
  "checklist_violations": [{"rule_id": "<the bracketed identifier of the rule>", "item": "...", "issue": "...", "file": "...", "line": 0}],
  "code_issues": [{"severity": "high|medium|low", "issue": "...", "file": "...", "line": 0}],
  "summary": "..."
}"""

STRICTER_RETRY = (
    "Your previous response was not valid JSON matching the required shape. "
    "Respond again with ONLY the JSON object - no explanation, no markdown code "
    "fences, no leading or trailing text. Every 'status' must be exactly one of "
    "appears_addressed, not_addressed, possible_contradiction. Every 'severity' "
    "must be exactly one of high, medium, low."
)


def _story_section(work_items):
    if not work_items:
        return (
            "## Linked user story\n\n"
            "No work item is linked to this pull request. Return an empty "
            "\"coverage\" array and review the diff against the checklist only.\n"
        )

    parts = ["## Linked user story\n"]
    for item in work_items:
        parts.append(f"### Work item #{item.id} - {item.title}")
        if item.work_item_type or item.state:
            parts.append(f"({item.work_item_type} / {item.state})")
        if item.description:
            parts.append(f"\n**Description**\n\n{item.description}")
        if item.acceptance_criteria:
            parts.append(f"\n**Acceptance criteria**\n\n{item.acceptance_criteria}")
        if item.criteria:
            enumerated = "\n".join(f"{c.ordinal}. {c.text}" for c in item.criteria)
            parts.append(
                "\n**Criteria, enumerated** (classify every one of these)\n\n" + enumerated
            )
        parts.append("")
    return "\n".join(parts)


def _scope_section(declared_scope, pr_description):
    parts = ["## Pull request description\n", pr_description or "(no description)", ""]
    if declared_scope.parsed:
        parts.append("### Author's declared scope, extracted\n")
        if declared_scope.covered:
            parts.append("**Claimed as covered** - verify each against the diff:")
            parts.extend(f"- {item}" for item in declared_scope.covered)
            parts.append("")
        if declared_scope.not_in_this_pr:
            parts.append("**Declared out of scope** - never report these as problems:")
            parts.extend(f"- {item}" for item in declared_scope.not_in_this_pr)
            parts.append("")
    else:
        parts.append(
            "The description has no Covered / Not-in-this-PR section, so no "
            "coverage claim can be verified against it.\n"
        )
    return "\n".join(parts)


def _checklist_section(checklist):
    """Renders either corpus shape - documents or plain text (research R9)."""
    if not checklist or not checklist.available:
        reason = (checklist.unavailable_reason if checklist else "") or "not available"
        return (
            f"## Code-review checklist\n\nNo checklist is available ({reason}). "
            "Return an empty \"checklist_violations\" array.\n"
        )
    return f"## Code-review checklist\n\n{checklist.prompt_text}\n"


def _diff_section(files, chunk_index, chunk_total):
    header = "## Diff"
    if chunk_total > 1:
        header += (
            f" (part {chunk_index} of {chunk_total} - you are seeing only some of "
            f"the changed files; do not conclude anything about files not shown)"
        )
    parts = [header, ""]
    for changed in files:
        parts.append(f"### {changed.path} ({changed.change_type})")
        parts.append("```diff")
        parts.append(changed.diff.rstrip("\n"))
        parts.append("```")
        parts.append("")
    return "\n".join(parts)


def chunk_files(reviewable, max_lines):
    """Split on file boundaries so a file is never judged from half of itself.

    A single file larger than the limit goes alone rather than being cut mid-hunk,
    which keeps the common case clean at the cost of one oversized prompt.
    """
    files = list(reviewable.reviewed)
    if not files:
        return []

    chunks, current, current_lines = [], [], 0
    for changed in files:
        if current and current_lines + changed.changed_lines > max_lines:
            chunks.append(current)
            current, current_lines = [], 0
        current.append(changed)
        current_lines += changed.changed_lines
    if current:
        chunks.append(current)
    return chunks


def build_prompts(work_items, declared_scope, checklist, reviewable, pr_context, config):
    """One prompt per chunk. Story, scope, and checklist repeat in every one."""
    checklist = checklist or Checklist()
    chunks = chunk_files(reviewable, config.llm_max_chunk_lines)
    if not chunks:
        return []

    story = _story_section(work_items)
    scope = _scope_section(declared_scope, pr_context.description)
    rules_block = _checklist_section(checklist)

    prompts = []
    for index, files in enumerate(chunks, start=1):
        prompts.append(
            "\n".join(
                [
                    SYSTEM_ROLE,
                    "",
                    "# Review rules",
                    "",
                    RULES,
                    "",
                    "# Required response shape",
                    "",
                    CONTRACT,
                    "",
                    "# Review material",
                    "",
                    story,
                    scope,
                    rules_block,
                    _diff_section(files, index, len(chunks)),
                    "Respond with only the JSON object.",
                ]
            )
        )
    return prompts


def estimated_size(prompt):
    """Rough token count. chars/4 is adequate for chunk sizing and needs no
    tokenizer dependency, which would be provider-specific anyway."""
    return len(prompt) // 4
