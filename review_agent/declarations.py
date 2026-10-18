"""What a change declares, read from text alone (feature 007, research D9).

Two uses, both in service of cross-file review:

* The **PR outline** shown in every chunk lists, per file, the types and member
  signatures the diff added and removed. A chunk that sees `CartController.cs`
  but not `Interfaces.cs` can still notice that `AddItem(int, int)` was removed
  and `AddItem(int, int, string)` added - which is exactly the defect a
  per-file review misses.
* The **skeleton** of an oversized file - its types, fields and member
  signatures with bodies dropped - is shown with each piece of that file, so a
  piece is never judged without knowing what surrounds it.

Pattern matching, not parsing. That is deliberate: a parser per language is a
dependency per language, and the outline is a hint to a model, not a compiler.
Where a file type is not recognised the outline says so rather than implying
the file declares nothing.
"""

import re
from dataclasses import dataclass

C_FAMILY = (".cs", ".java", ".ts", ".tsx", ".js", ".jsx", ".kt", ".scala", ".swift", ".go", ".cpp", ".hpp", ".h")
PYTHON = (".py",)

_MODIFIERS = (
    r"(?:(?:public|private|protected|internal|static|abstract|sealed|partial|export|"
    r"default|final|readonly|virtual|override|async|extern|unsafe|new|const|open|"
    r"suspend|inline|data|fun|func)\s+)*"
)
_NOT_A_DECLARATION = (
    r"(?!(?:return|new|await|throw|else|case|yield|using|if|while|for|foreach|"
    r"switch|catch|lock|typeof|nameof|sizeof|var|let|const)\b)"
)

C_TYPE = re.compile(
    rf"^\s*{_MODIFIERS}(class|interface|record|struct|enum|trait|object)\s+([A-Za-z_]\w*)"
    r"(?:\s*<[^>]*>)?(?:\s*(?::|extends|implements)\s*([^{]+))?"
)
_ONE_MODIFIER = _MODIFIERS[:-1] + "+"  # the same alternation, at least once
_TYPE_TOKEN = r"[A-Za-z_][\w<>\[\],.?]*\s+"
C_METHOD = re.compile(
    # A declaration has a modifier (a constructor: `public CartController(...)`)
    # or a return type (`void AddItem(...)`). A bare call - `Recalculate();` -
    # has neither, and must not be mistaken for one.
    rf"^\s*{_NOT_A_DECLARATION}(?:{_ONE_MODIFIER}{_NOT_A_DECLARATION}(?:{_TYPE_TOKEN})*"
    rf"|(?:{_TYPE_TOKEN})+)"
    r"([A-Za-z_]\w*)\s*(?:<[^>()]*>)?\s*\(([^()]*)\)\s*(?:[{;]|=>|:|where\b|throws\b|$)"
)
C_FIELD = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|readonly|final|const|volatile)\s+)+"
    r"[A-Za-z_][\w<>\[\],.?]*\s+([A-Za-z_]\w*)\s*(?:[;=]|\{\s*get)"
)
PY_TYPE = re.compile(r"^\s*class\s+([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?\s*:")
PY_METHOD = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\((.*)\)\s*(?:->\s*[^:]+)?:")

#: Control-flow words that look like a call followed by a block.
_KEYWORD_NAMES = {"if", "for", "foreach", "while", "switch", "catch", "using", "lock", "return", "when"}


@dataclass(frozen=True)
class Declarations:
    added: tuple = ()
    removed: tuple = ()
    #: Type names this file declares or inherits from - the dependency planner's vocabulary.
    types: frozenset = frozenset()
    supported: bool = True


def language(path):
    lowered = (path or "").lower()
    if lowered.endswith(PYTHON):
        return "python"
    if lowered.endswith(C_FAMILY):
        return "c"
    return None


def _normalise(signature):
    text = re.sub(r"\s+", " ", signature.strip())
    text = re.sub(r"\s*(\{|=>).*$", "", text)
    return text.rstrip(" ;:")


def match_declaration(line, lang):
    """(kind, name, signature, bases) for a declaring line, else None."""
    if lang == "python":
        found = PY_TYPE.match(line)
        if found:
            return "type", found.group(1), _normalise(line), found.group(2) or ""
        found = PY_METHOD.match(line)
        if found:
            return "member", found.group(1), _normalise(line), ""
        return None
    found = C_TYPE.match(line)
    if found:
        return "type", found.group(2), _normalise(line), found.group(3) or ""
    found = C_METHOD.match(line)
    if found and found.group(1) not in _KEYWORD_NAMES:
        return "member", found.group(1), _normalise(line), ""
    found = C_FIELD.match(line)
    if found:
        return "field", found.group(1), _normalise(line), ""
    return None


def _base_names(bases):
    return {
        name
        for name in re.findall(r"[A-Za-z_]\w*", bases or "")
        if name not in ("public", "private", "protected", "virtual", "where", "new", "class")
    }


def extract(diff, path, content=""):
    """Declarations added and removed by `diff`, plus the types the file knows."""
    lang = language(path)
    if lang is None:
        return Declarations(supported=False)

    added, removed, types = [], [], set()
    for raw in (diff or "").splitlines():
        if raw.startswith(("+++", "---", "@@")):
            continue
        marker, line = (raw[:1], raw[1:]) if raw[:1] in "+- " else (" ", raw)
        found = match_declaration(line, lang)
        if not found:
            continue
        kind, name, signature, bases = found
        if kind == "type":
            types.add(name)
            types.update(_base_names(bases))
        if kind == "field":
            continue  # fields belong in a skeleton, not in the outline
        if marker == "+":
            added.append(signature)
        elif marker == "-":
            removed.append(signature)

    for line in (content or "").splitlines():
        found = match_declaration(line, lang)
        if found and found[0] == "type":
            types.add(found[1])
            types.update(_base_names(found[3]))

    # A line that moved, unchanged, is not a change of declaration.
    moved = set(added) & set(removed)
    return Declarations(
        added=tuple(dict.fromkeys(s for s in added if s not in moved)),
        removed=tuple(dict.fromkeys(s for s in removed if s not in moved)),
        types=frozenset(types),
        supported=True,
    )


def skeleton(text, path):
    """Types, fields and member signatures of a whole file, bodies dropped."""
    lang = language(path)
    if lang is None:
        return ""
    lines = []
    for line in (text or "").splitlines():
        if match_declaration(line, lang):
            lines.append(line.rstrip().rstrip("{").rstrip())
    return "\n".join(lines)
