"""Turn iteration change entries into unified diffs the model can read.

The `changes` endpoint returns change *entries* - a path and a change type - not
patch text, and no on-prem endpoint reliably returns per-file unified diff across
TFS versions (research R3). So the diff is computed here from the blob at the
iteration commit and the blob at the base commit.

Computing it locally also produces the diff-line -> new-file-line map, which is
what lets an inline comment land on the right line instead of a guess.
"""

import difflib

from .models import ChangedFile, ChangeSet, SkippedFile

CONTEXT_LINES = 3

_BINARY_EXTENSIONS = (
    ".dll", ".exe", ".pdb", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".pdf", ".woff", ".woff2", ".ttf", ".eot", ".so", ".dylib", ".bin", ".snk",
)

_CHANGE_TYPES = {
    "add": "add",
    "edit": "edit",
    "delete": "delete",
    "rename": "rename",
}


def _normalise_change_type(raw):
    """TFS reports composites like 'edit, rename'; take the meaningful part."""
    value = (raw or "edit").lower()
    for token in ("delete", "add", "rename", "edit"):
        if token in value:
            return _CHANGE_TYPES[token]
    return "edit"


def looks_binary(path, content=None):
    lowered = (path or "").lower()
    if any(lowered.endswith(ext) for ext in _BINARY_EXTENSIONS):
        return True
    return bool(content) and "\x00" in content


def resolve_iteration(iterations, pull_request):
    """Pick the latest iteration and the commit to diff against.

    Falls back through commonRefCommit -> the PR's lastMergeTargetCommit, because
    an older server may not populate the first (research R3).
    """
    if not iterations:
        return None, "", ""
    latest = iterations[-1]
    iteration_id = latest.get("id") or len(iterations)
    head = (latest.get("sourceRefCommit") or {}).get("commitId", "")
    base = (latest.get("commonRefCommit") or {}).get("commitId", "")
    if not base:
        base = ((pull_request or {}).get("lastMergeTargetCommit") or {}).get("commitId", "")
    return iteration_id, head, base


def _split(text):
    if not text:
        return []
    return text.splitlines(keepends=True)


def build_file_diff(path, before, after):
    """Unified diff plus a map from diff-line index to new-file line number.

    The map is built while emitting rather than reparsed afterwards - reparsing
    hunk headers is where off-by-one anchoring bugs live.
    """
    before_lines, after_lines = _split(before), _split(after)
    diff_lines = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=CONTEXT_LINES,
        )
    )
    if not diff_lines:
        return "", {}, 0

    line_map = {}
    new_line = 0
    changed = 0
    for index, raw in enumerate(diff_lines):
        if raw.startswith("@@"):
            # @@ -a,b +c,d @@
            try:
                new_part = raw.split("+", 1)[1].split(" ", 1)[0]
                new_line = int(new_part.split(",")[0]) - 1
            except (IndexError, ValueError):
                new_line = 0
            continue
        if raw.startswith(("---", "+++")):
            continue
        if raw.startswith("+"):
            new_line += 1
            line_map[index] = new_line
            changed += 1
        elif raw.startswith("-"):
            # Removed lines have no new-file line; anchor to the following line so
            # a finding about a deletion still lands somewhere sensible.
            line_map[index] = max(new_line, 1)
            changed += 1
        else:
            new_line += 1
            line_map[index] = new_line

    return "".join(diff_lines), line_map, changed


def build_change_set(client, pull_request_context, change_entries):
    """Fetch blobs and assemble the ChangeSet. Returns (ChangeSet, skipped)."""
    files = []
    skipped = []

    for entry in change_entries or []:
        item = entry.get("item") or {}
        path = item.get("path") or ""
        if not path or item.get("isFolder") or item.get("gitObjectType") == "tree":
            continue

        change_type = _normalise_change_type(entry.get("changeType"))

        if change_type == "delete":
            # Nothing in the post-change file to comment on.
            skipped.append(SkippedFile(path=path, reason="deleted", detail="file removed"))
            continue

        if looks_binary(path):
            skipped.append(SkippedFile(path=path, reason="binary", detail="binary by extension"))
            continue

        after = client.get_file_content(path, pull_request_context.iteration_commit)
        if after is None:
            skipped.append(
                SkippedFile(path=path, reason="unavailable", detail="content not retrievable")
            )
            continue
        if looks_binary(path, after):
            skipped.append(SkippedFile(path=path, reason="binary", detail="binary content"))
            continue

        before = ""
        if change_type != "add" and pull_request_context.base_commit:
            fetched = client.get_file_content(path, pull_request_context.base_commit)
            before = fetched if fetched is not None else ""

        diff, line_map, changed = build_file_diff(path, before, after)
        if not diff:
            continue

        files.append(
            ChangedFile(
                path=path,
                change_type=change_type,
                diff=diff,
                line_map=line_map,
                changed_lines=changed,
            )
        )

    return ChangeSet(files=tuple(files)), tuple(skipped)


def map_line(changed_file, reported_line):
    """Validate a model-reported line against the file's real new-file lines.

    Returns None when the line is not in the diff, so the caller routes the
    finding to the summary rather than anchoring a comment to unrelated code
    (FR-025, research R4).
    """
    if not reported_line or reported_line < 1:
        return None
    valid = set(changed_file.line_map.values())
    if reported_line in valid:
        return reported_line
    return None
