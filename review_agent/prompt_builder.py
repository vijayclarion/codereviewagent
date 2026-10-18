"""Assemble the review prompt.

The classification rules are stated verbatim in substance, per spec section 6.
They are the load-bearing part of this module: without them a model treats every
unimplemented acceptance criterion as a defect, which would make the agent noise
on every partial pull request - and partial pull requests are the normal case.
"""

import json

from . import chunk_planner
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

You may see only part of the pull request. The pull request outline lists every
reviewed file and the declarations each change added and removed. Report a
cross-file issue when a change you can see is inconsistent with a declaration,
signature, registration, configuration key, migration or test listed for another
file - for example: a signature changed while a caller still uses the old one; an
interface and its implementation disagree; a new dependency is not registered for
injection; a new configuration key is missing from the configuration files; a
model changed without a migration; behaviour changed without its tests being
updated. Name every file involved in "files". In "change_notes", state in two or
three sentences what changed in the files you saw, including any signature change,
for a later pass that sees only these notes.

Respond with ONLY the JSON object described below - no prose, no markdown fences."""

CONTRACT = """\
{
  "coverage": [
    {"criterion": "...", "status": "appears_addressed|not_addressed|possible_contradiction", "evidence": "..."}
  ],
  "checklist_violations": [{"rule_id": "<the bracketed identifier of the rule>", "item": "...", "issue": "...", "file": "...", "line": 0}],
  "code_issues": [{"severity": "high|medium|low", "issue": "...", "file": "...", "line": 0}],
  "cross_file_issues": [{"severity": "high|medium|low", "issue": "...", "files": ["<path>", "<path>"], "file": "<anchor path>", "line": 0}],
  "change_notes": "...",
  "summary": "..."
}"""

#: Feature 007 (D12): the one extra call a multi-chunk review makes.
SYNTHESIS_ROLE = (
    "You are a senior code reviewer completing a review that was done in parts. "
    "Each part saw only some of the changed files. You see the outline of the whole "
    "pull request, every finding the parts reported, and each part's notes on what "
    "changed. You do not see the code."
)

SYNTHESIS_RULES = """\
Produce the final review:
  - "summary": one coherent summary of the whole pull request.
  - "coverage": the final verdict for each acceptance criterion, using the same three
    statuses. A criterion one part saw implemented and another part saw nothing of is
    "appears_addressed"; "not_addressed" remains neutral, never a defect.
  - "cross_file_issues": defects that only appear when the parts are put together -
    for example a signature changed in one file while another file still calls the old
    form. Use the outline's added and removed declarations and the parts' notes. Name
    every file involved. Repeat cross-file issues the parts already reported only if
    they still hold.
Do not report code issues or checklist violations: the parts that saw the code
already did. Respond with ONLY the JSON object - no prose, no markdown fences."""

SYNTHESIS_CONTRACT = """\
{
  "summary": "...",
  "coverage": [
    {"criterion": "...", "status": "appears_addressed|not_addressed|possible_contradiction", "evidence": "..."}
  ],
  "cross_file_issues": [{"severity": "high|medium|low", "issue": "...", "files": ["<path>", "<path>"], "file": "<anchor path>", "line": 0}]
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


def _diff_section(pieces, chunk_index, chunk_total):
    header = "## Diff"
    if chunk_total > 1:
        header += (
            f" (part {chunk_index} of {chunk_total} - you are seeing only some of "
            f"the changed files; do not conclude anything about files not shown)"
        )
    parts = [header, ""]
    for piece in pieces:
        # A ChangedFile (the pre-007 shape) is a whole piece of itself.
        changed = getattr(piece, "file", piece)
        diff = getattr(piece, "diff", changed.diff)
        heading = f"### {changed.path} ({changed.change_type})"
        if getattr(piece, "parts", 1) > 1:
            heading += f" — part {piece.part} of {piece.parts}"
        parts.append(heading)
        if getattr(piece, "skeleton", ""):
            parts.append("File skeleton (declarations only, bodies omitted):")
            parts.append("```")
            parts.append(piece.skeleton)
            parts.append("```")
        parts.append("```diff")
        parts.append(diff.rstrip("\n"))
        parts.append("```")
        parts.append("")
    return "\n".join(parts)


def chunk_files(reviewable, max_lines):
    """Split on file boundaries so a file is never judged from half of itself.

    The pre-007 line-count chunker, kept for anything that still calls it. The
    review itself now plans by token budget (`chunk_planner.plan_chunks`).
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


def _fixed_sections(work_items, declared_scope, checklist, pr_context):
    return [
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
        _story_section(work_items),
        _scope_section(declared_scope, pr_context.description),
        _checklist_section(checklist or Checklist()),
    ]


class ReviewPrompts:
    """The prompts for one run, and the plan and outline they were built from."""

    def __init__(self, prompts, plan, outline):
        self.prompts = list(prompts)
        self.plan = plan
        self.outline = outline

    def __len__(self):
        return len(self.prompts)

    def __iter__(self):
        return iter(self.prompts)


def build_review(work_items, declared_scope, checklist, reviewable, pr_context, config):
    """Plan the chunks by token budget and build one prompt per chunk (feature 007).

    Story, scope, checklist and the PR outline repeat in every prompt; only the
    diff differs.
    """
    fixed = _fixed_sections(work_items, declared_scope, checklist, pr_context)
    plan = chunk_planner.plan_chunks(reviewable, "\n".join(fixed), config)
    if not plan.chunks:
        return ReviewPrompts([], plan, "")
    outline = chunk_planner.render_outline(plan, reviewable)

    prompts = []
    for index, pieces in enumerate(plan.chunks, start=1):
        prompts.append(
            "\n".join(
                fixed
                + [
                    outline,
                    _diff_section(pieces, index, plan.total),
                    "Respond with only the JSON object.",
                ]
            )
        )
    return ReviewPrompts(prompts, plan, outline)


def build_prompts(work_items, declared_scope, checklist, reviewable, pr_context, config):
    """One prompt per chunk - the list form of `build_review`."""
    return build_review(
        work_items, declared_scope, checklist, reviewable, pr_context, config
    ).prompts


def build_synthesis_prompt(outline, work_items, merged, notes):
    """The one extra call a multi-chunk review makes (feature 007, D12)."""
    findings = {
        "coverage": [
            {"criterion": c.criterion, "status": c.status, "evidence": c.evidence}
            for c in merged.get("coverage", ())
        ],
        "checklist_violations": [
            {"item": v.item, "issue": v.issue, "file": v.file, "line": v.line}
            for v in merged.get("checklist_violations", ())
        ],
        "code_issues": [
            {"severity": i.severity, "issue": i.issue, "file": i.file, "line": i.line}
            for i in merged.get("code_issues", ())
        ],
        "cross_file_issues": [
            {"severity": i.severity, "issue": i.issue, "files": list(i.files),
             "file": i.file, "line": i.line}
            for i in merged.get("cross_file_issues", ())
        ],
    }
    criteria = [c for item in work_items for c in item.criteria]
    if criteria:
        story = "## Acceptance criteria\n\n" + "\n".join(f"{c.ordinal}. {c.text}" for c in criteria)
    else:
        story = "## Acceptance criteria\n\nNone - return an empty \"coverage\" array."
    total = len(notes)
    part_notes = "\n\n".join(
        f"### Part {index} of {total}\n\n{note or '(no notes)'}"
        for index, note in enumerate(notes, start=1)
    )
    return "\n".join(
        [
            SYNTHESIS_ROLE,
            "",
            "# Rules",
            "",
            SYNTHESIS_RULES,
            "",
            "# Required response shape",
            "",
            SYNTHESIS_CONTRACT,
            "",
            "# Material",
            "",
            story,
            "",
            outline,
            "## Findings reported by the parts",
            "",
            "```json",
            json.dumps(findings, indent=1, ensure_ascii=False),
            "```",
            "",
            "## Notes from each part",
            "",
            part_notes,
            "",
            "Respond with only the JSON object.",
        ]
    )


def estimated_size(prompt):
    """Rough token count. chars/4 is adequate for chunk sizing and needs no
    tokenizer dependency, which would be provider-specific anyway."""
    return len(prompt) // 4
