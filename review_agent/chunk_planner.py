"""How a pull request is divided between model calls (feature 007, D8, D10, D11).

The budget is **tokens for a whole prompt**, not lines of diff. With the default
budget almost every pull request that passes selection is one call, so nothing
is split and nothing is missed. When a split is unavoidable:

1. Files that refer to each other - a shared type name, an interface and its
   implementation, the same stem, a source file and its test - are kept in the
   same chunk wherever the budget allows.
2. A file larger than the budget on its own is cut on hunk boundaries, and each
   piece is shown with the file's skeleton.
3. Every chunk carries the PR outline (`render_outline`), so a chunk that does
   not see a file still knows what it declares.

Grouping is a heuristic and is not the last line of defence: the outline and
the synthesis pass are what catch a cross-file defect whose files the budget
forced apart. That is the design, not a fallback.

Deterministic: the same pull request always plans the same way (ties break on
path), so a re-run reviews the same chunks and finds the same things.
"""

import math
import re
from dataclasses import dataclass, field

from . import declarations

#: Characters per token, pessimistic for code, which tokenizes denser than prose.
CHARS_PER_TOKEN = 3
#: Rendered overhead of one file in a chunk: heading, fences, part label.
PER_FILE_OVERHEAD = 40
#: A chunk always has room for at least this much diff, however large the fixed part.
MIN_DIFF_BUDGET = 2000

_ROLE_SUFFIXES = re.compile(
    r"(controller|service|services|repository|repo|handler|manager|provider|impl|"
    r"tests?|spec|specs)$",
    re.IGNORECASE,
)


def estimate_tokens(text):
    return math.ceil(len(text or "") / CHARS_PER_TOKEN)


@dataclass(frozen=True)
class ChunkPiece:
    file: object
    part: int = 1
    parts: int = 1
    diff: str = ""
    skeleton: str = ""
    split_inside_hunk: bool = False

    def __post_init__(self):
        if not 1 <= self.part <= self.parts:
            raise ValueError("piece position outside its file")

    @property
    def path(self):
        return self.file.path

    @property
    def tokens(self):
        return estimate_tokens(self.diff) + estimate_tokens(self.skeleton) + PER_FILE_OVERHEAD


@dataclass(frozen=True)
class ChunkPlan:
    chunks: tuple = ()
    assignment: dict = field(default_factory=dict)
    groups: tuple = ()
    budget_tokens: int = 0
    declarations: dict = field(default_factory=dict)

    @property
    def total(self):
        return len(self.chunks)


# --------------------------------------------------------------------------
# Relations
# --------------------------------------------------------------------------


def stem(path):
    """`src/Services/ICartService.cs` -> `cart`; `tests/test_cart.py` -> `cart`."""
    name = (path or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"(\.(spec|test))?\.[A-Za-z0-9]+$", "", name)
    name = re.sub(r"^test_", "", name)
    name = re.sub(r"_test$", "", name)
    if len(name) > 1 and name[0] == "I" and name[1].isupper():
        name = name[1:]
    previous = None
    while previous != name:
        previous = name
        stripped = _ROLE_SUFFIXES.sub("", name)
        name = stripped if stripped else name
    return name.lower().strip("._-")


def _words(text):
    return set(re.findall(r"[A-Za-z_]\w*", text or ""))


def _interface_pairs(types_a, types_b):
    """`IFoo` in one, `Foo` / `FooImpl` in the other."""
    for name in types_a:
        if len(name) > 1 and name[0] == "I" and name[1].isupper():
            plain = name[1:]
            if plain in types_b or f"{plain}Impl" in types_b:
                return True
    return False


def related(a, b, decls):
    """Whether two changed files should be reviewed together (research D10)."""
    da, db = decls[a.path], decls[b.path]
    text_a = f"{a.diff}\n{getattr(a, 'content', '')}"
    text_b = f"{b.diff}\n{getattr(b, 'content', '')}"
    # 1. a type one declares is named in the other
    if da.types & _words(text_b) or db.types & _words(text_a):
        return True
    # 2. interface and implementation
    if _interface_pairs(da.types, db.types) or _interface_pairs(db.types, da.types):
        return True
    # 3/4. same stem: Cart.cs, CartController.cs, ICartService.cs, CartTests.cs
    sa, sb = stem(a.path), stem(b.path)
    return bool(sa) and sa == sb


def _components(files, decls):
    parent = {f.path: f.path for f in files}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(files):
        for b in files[i + 1:]:
            if related(a, b, decls):
                ra, rb = find(a.path), find(b.path)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)

    groups = {}
    for f in files:
        groups.setdefault(find(f.path), []).append(f)
    return [sorted(g, key=lambda f: f.path) for _root, g in sorted(groups.items())]


# --------------------------------------------------------------------------
# Pieces
# --------------------------------------------------------------------------


def _split_hunks(diff):
    """(header lines, [hunk text, ...]) of one file's unified diff."""
    header, hunks, current = [], [], None
    for line in (diff or "").splitlines(keepends=True):
        if line.startswith("@@"):
            current = [line]
            hunks.append(current)
        elif current is None:
            header.append(line)
        else:
            current.append(line)
    return "".join(header), ["".join(h) for h in hunks]


#: A skeleton may use at most this share of a chunk's diff budget. A file with
#: hundreds of fields has a skeleton as large as its diff; uncapped, it would
#: leave no room for the hunks it is there to explain.
SKELETON_SHARE = 4


def _capped_skeleton(skel, budget):
    limit = max(budget // SKELETON_SHARE, 50) * CHARS_PER_TOKEN
    if len(skel) <= limit:
        return skel
    kept, used = [], 0
    lines = skel.splitlines()
    for line in lines:
        if used + len(line) + 1 > limit:
            break
        kept.append(line)
        used += len(line) + 1
    kept.append(f"... ({len(lines) - len(kept)} more declarations not shown)")
    return "\n".join(kept)


def _pieces_of(changed, budget):
    """The file whole, or cut on hunk boundaries under `budget` tokens."""
    whole = ChunkPiece(changed, diff=changed.diff)
    if whole.tokens <= budget:
        return [whole]

    skel = _capped_skeleton(
        declarations.skeleton(getattr(changed, "content", ""), changed.path), budget
    )
    header, hunks = _split_hunks(changed.diff)
    room = max(budget - estimate_tokens(skel) - estimate_tokens(header) - PER_FILE_OVERHEAD, 200)
    room_chars = room * CHARS_PER_TOKEN

    bodies, inside = [], []
    current = ""
    for hunk in hunks:
        if len(hunk) > room_chars:
            # A single hunk larger than the budget: cut on line boundaries.
            if current:
                bodies.append(current)
                inside.append(False)
                current = ""
            slice_ = ""
            for line in hunk.splitlines(keepends=True):
                if slice_ and len(slice_) + len(line) > room_chars:
                    bodies.append(slice_)
                    inside.append(True)
                    slice_ = ""
                slice_ += line
            if slice_:
                bodies.append(slice_)
                inside.append(True)
            continue
        if current and len(current) + len(hunk) > room_chars:
            bodies.append(current)
            inside.append(False)
            current = ""
        current += hunk
    if current:
        bodies.append(current)
        inside.append(False)

    total = len(bodies)
    return [
        ChunkPiece(changed, part=i + 1, parts=total, diff=header + body, skeleton=skel,
                   split_inside_hunk=inside[i])
        for i, body in enumerate(bodies)
    ]


# --------------------------------------------------------------------------
# The plan
# --------------------------------------------------------------------------


def diff_budget(config, fixed_text, outline_estimate=""):
    """Tokens left for diff in one chunk."""
    total = int(getattr(config, "llm_max_prompt_tokens", 120000))
    reserve = int(getattr(config, "llm_max_output_tokens", 8192))
    left = total - reserve - estimate_tokens(fixed_text) - estimate_tokens(outline_estimate)
    return max(left, MIN_DIFF_BUDGET)


def plan_chunks(reviewable, fixed_text, config):
    """Divide `reviewable.reviewed` into chunks (D8, D10, D11)."""
    files = list(reviewable.reviewed)
    decls = {f.path: declarations.extract(f.diff, f.path, getattr(f, "content", "")) for f in files}
    if not files:
        return ChunkPlan(declarations=decls)

    draft_outline = render_outline_rows(files, reviewable, decls, {})
    budget = diff_budget(config, fixed_text, draft_outline)
    line_cap = int(getattr(config, "llm_max_chunk_lines", 0) or 0)

    groups = _components(files, decls)
    # Largest group first; ties on its first path, for determinism.
    ordered = sorted(
        groups,
        key=lambda g: (-sum(ChunkPiece(f, diff=f.diff).tokens for f in g), g[0].path),
    )

    chunks = []  # each: {"pieces": [...], "tokens": int, "lines": int}

    def fits(chunk, tokens, lines):
        if chunk["tokens"] + tokens > budget:
            return False
        return not (line_cap and chunk["pieces"] and chunk["lines"] + lines > line_cap)

    def place(pieces, lines):
        tokens = sum(p.tokens for p in pieces)
        for chunk in chunks:
            if fits(chunk, tokens, lines):
                chunk["pieces"].extend(pieces)
                chunk["tokens"] += tokens
                chunk["lines"] += lines
                return
        chunks.append({"pieces": list(pieces), "tokens": tokens, "lines": lines})

    for group in ordered:
        group_pieces = [p for f in group for p in _pieces_of(f, budget)]
        group_tokens = sum(p.tokens for p in group_pieces)
        group_lines = sum(f.changed_lines for f in group)
        whole_files = all(p.parts == 1 for p in group_pieces)
        if whole_files and group_tokens <= budget and not (line_cap and group_lines > line_cap):
            place(group_pieces, group_lines)
            continue
        # Too big together: files in order of how connected they are, so the
        # most-related ones still share a chunk.
        degree = {
            f.path: sum(1 for g in group if g is not f and related(f, g, decls)) for f in group
        }
        for f in sorted(group, key=lambda f: (-degree[f.path], f.path)):
            pieces = _pieces_of(f, budget)
            if len(pieces) == 1:
                place(pieces, f.changed_lines)
            else:
                for piece in pieces:  # each piece of an oversized file stands alone
                    chunks.append({"pieces": [piece], "tokens": piece.tokens, "lines": 0})

    assignment = {}
    for index, chunk in enumerate(chunks, start=1):
        for piece in chunk["pieces"]:
            current = assignment.get(piece.path, ())
            if index not in current:
                assignment[piece.path] = current + (index,)

    return ChunkPlan(
        chunks=tuple(tuple(c["pieces"]) for c in chunks),
        assignment=assignment,
        groups=tuple(frozenset(f.path for f in g) for g in groups),
        budget_tokens=budget,
        declarations=decls,
    )


# --------------------------------------------------------------------------
# The outline
# --------------------------------------------------------------------------


def _cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def _line_counts(diff):
    added = removed = 0
    for line in (diff or "").splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def _declaration_cell(decl):
    if not decl.supported:
        return "declarations not extracted for this file type"
    parts = []
    if decl.removed:
        parts.append("removed: " + "; ".join(f"`{_cell(s)}`" for s in decl.removed))
    if decl.added:
        parts.append("added: " + "; ".join(f"`{_cell(s)}`" for s in decl.added))
    return " / ".join(parts) or "none changed"


def render_outline_rows(files, reviewable, decls, assignment, split_note=None):
    rows = [
        "| File | Change | Lines | Reviewed in part | Declarations |",
        "|---|---|---|---|---|",
    ]
    for f in files:
        added, removed = _line_counts(f.diff)
        parts = ", ".join(str(i) for i in assignment.get(f.path, ())) or "?"
        note = (split_note or {}).get(f.path, "")
        rows.append(
            f"| `{_cell(f.path)}` | {f.change_type}{note} | +{added} \u2212{removed} | {parts} | "
            f"{_declaration_cell(decls[f.path])} |"
        )
    return "\n".join(rows)


def render_outline(plan, reviewable):
    """The PR outline every chunk carries (FR-015)."""
    files = list(reviewable.reviewed)
    split = {}
    for chunk in plan.chunks:
        for piece in chunk:
            if piece.parts > 1:
                label = f", split in {piece.parts} parts"
                if piece.split_inside_hunk:
                    label += " (split inside a hunk)"
                if not split.get(piece.path, "").endswith("hunk)"):
                    split[piece.path] = label
    total = plan.total
    lead = (
        f"This pull request changes {len(files)} reviewed file(s), reviewed in {total} "
        f"part(s). You may see only some of them; this outline lists every one, with "
        "the declarations each change added and removed, so you can check the files you "
        "see against the ones you do not."
    )
    table = render_outline_rows(files, reviewable, plan.declarations, plan.assignment, split)
    # Files that were not sent are counted, never named: an excluded file's
    # path must not reach the provider either (tests/contract/
    # test_excluded_files_never_sent.py).
    withheld = len(tuple(getattr(reviewable, "excluded", ()))) + len(
        tuple(getattr(reviewable, "unreviewed", ()))
    )
    tail = (
        f"\n{withheld} other changed file(s) were not sent for review and are not listed.\n"
        if withheld
        else ""
    )
    return f"## Pull request outline\n\n{lead}\n\n{table}\n{tail}"
