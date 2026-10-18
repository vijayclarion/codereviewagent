"""T046 (feature 007) - token budget, dependency groups, packing, pieces."""

import pytest

from review_agent import chunk_planner as cp
from review_agent.diff_builder import build_file_diff
from review_agent.models import ChangedFile, ReviewableSet, SkippedFile
from tests.fixtures import cross_file_cart as cart


class _Cfg:
    def __init__(self, prompt=120000, output=8192, lines=0):
        self.llm_max_prompt_tokens = prompt
        self.llm_max_output_tokens = output
        self.llm_max_chunk_lines = lines


def _file(path, before, after):
    diff, line_map, changed = build_file_diff(path, before, after)
    return ChangedFile(path="/" + path, change_type="edit", diff=diff, line_map=line_map,
                       changed_lines=changed, content=after)


def _cart_files():
    return [
        _file(cart.INTERFACES, cart.INTERFACES_BEFORE, cart.INTERFACES_AFTER),
        _file(cart.SERVICE, cart.SERVICE_BEFORE, cart.SERVICE_AFTER),
        _file(cart.CONTROLLER, cart.CONTROLLER_BEFORE, cart.CONTROLLER_AFTER),
        _file(cart.CART, cart.CART_BEFORE, cart.CART_AFTER),
    ]


def _unrelated(name, lines=5):
    body = "".join(f"x{name}{i} = {i}\n" for i in range(lines))
    return _file(f"lib/{name}.txt", "", body)


def test_estimate_is_pessimistic():
    assert cp.estimate_tokens("abc") == 1
    assert cp.estimate_tokens("abcd") == 2
    assert cp.estimate_tokens("") == 0


def test_diff_budget_subtracts_fixed_outline_and_output():
    assert cp.diff_budget(_Cfg(prompt=20000, output=4000), "x" * 3000, "y" * 300) == 20000 - 4000 - 1000 - 100
    assert cp.diff_budget(_Cfg(prompt=8000, output=3000), "x" * 30000) == cp.MIN_DIFF_BUDGET


@pytest.mark.parametrize(
    "path, expected",
    [
        ("src/Services/ICartService.cs", "cart"),
        ("src/Controllers/CartController.cs", "cart"),
        ("tests/CartTests.cs", "cart"),
        ("tests/test_cart.py", "cart"),
        ("web/cart.spec.ts", "cart"),
        ("src/Order.cs", "order"),
        ("src/Services/Interfaces.cs", "interfaces"),
    ],
)
def test_stem(path, expected):
    assert cp.stem(path) == expected


def test_cart_files_form_one_group_and_one_chunk_by_default():
    files = _cart_files()
    plan = cp.plan_chunks(ReviewableSet(reviewed=tuple(files)), "fixed", _Cfg())
    assert plan.total == 1
    assert {f.path for f in files} in [set(g) for g in plan.groups]


def test_unrelated_files_are_separate_groups():
    files = _cart_files() + [_unrelated("alpha"), _unrelated("beta")]
    plan = cp.plan_chunks(ReviewableSet(reviewed=tuple(files)), "fixed", _Cfg())
    assert len(plan.groups) == 3


def test_the_line_cap_applies_only_when_set():
    files = _cart_files()
    capped = cp.plan_chunks(ReviewableSet(reviewed=tuple(files)), "", _Cfg(lines=1))
    assert capped.total == len(files)
    assert all(len(chunk) == 1 for chunk in capped.chunks)


def test_a_group_stays_together_when_unrelated_files_must_move_out():
    files = _cart_files() + [_unrelated(f"u{i}", lines=600) for i in range(4)]
    plan = cp.plan_chunks(ReviewableSet(reviewed=tuple(files)), "", _Cfg(prompt=16000, output=4000))
    assert plan.total > 1
    cart_chunks = {plan.assignment[f.path] for f in _cart_files()}
    assert len(cart_chunks) == 1, "related files were split although they fit together"


def test_every_file_is_assigned_and_no_chunk_exceeds_the_budget():
    files = _cart_files() + [_unrelated(f"u{i}", lines=400) for i in range(6)]
    plan = cp.plan_chunks(ReviewableSet(reviewed=tuple(files)), "", _Cfg(prompt=12000, output=3000))
    assert set(plan.assignment) == {f.path for f in files}
    for chunk in plan.chunks:
        if len(chunk) > 1:
            assert sum(p.tokens for p in chunk) <= plan.budget_tokens


def test_planning_is_deterministic():
    files = _cart_files() + [_unrelated(f"u{i}", lines=300) for i in range(5)]
    reviewable = ReviewableSet(reviewed=tuple(files))
    first = cp.plan_chunks(reviewable, "", _Cfg(prompt=10000, output=3000))
    again = cp.plan_chunks(ReviewableSet(reviewed=tuple(reversed(files))), "", _Cfg(prompt=10000, output=3000))
    assert first.assignment == again.assignment


def _oversized(hunks=6, lines_per_hunk=200):
    before_lines, after_lines = [], []
    for h in range(hunks):
        block = [f"    public int Field{h}_{i};\n" for i in range(lines_per_hunk)]
        before_lines += block + [f"    // spacer {h}-{j}\n" for j in range(10)]
        after_lines += [line.replace("int", "long") for line in block] + [
            f"    // spacer {h}-{j}\n" for j in range(10)
        ]
    before = "public class Big\n{\n" + "".join(before_lines) + "}\n"
    after = "public class Big\n{\n" + "".join(after_lines) + "}\n"
    return _file("src/Big.cs", before, after)


def test_an_oversized_file_is_cut_on_hunk_boundaries_with_its_skeleton():
    big = _oversized()
    plan = cp.plan_chunks(ReviewableSet(reviewed=(big,)), "", _Cfg(prompt=16000, output=4000))
    pieces = [p for chunk in plan.chunks for p in chunk]
    assert len(pieces) > 1
    assert [p.part for p in pieces] == list(range(1, len(pieces) + 1))
    assert all(p.parts == len(pieces) for p in pieces)
    assert all("public class Big" in p.skeleton for p in pieces)
    assert all(p.diff.startswith("--- a/") for p in pieces)
    assert not any(p.split_inside_hunk for p in pieces)
    assert plan.assignment[big.path] == tuple(range(1, len(pieces) + 1))


def test_a_single_hunk_over_the_budget_is_cut_inside_and_says_so():
    big = _oversized(hunks=1, lines_per_hunk=2500)
    plan = cp.plan_chunks(ReviewableSet(reviewed=(big,)), "", _Cfg(prompt=16000, output=4000))
    pieces = [p for chunk in plan.chunks for p in chunk]
    assert len(pieces) > 1 and all(p.split_inside_hunk for p in pieces)
    outline = cp.render_outline(plan, ReviewableSet(reviewed=(big,)))
    assert "(split inside a hunk)" in outline


def test_outline_lists_every_reviewed_file_and_counts_but_never_names_withheld_ones():
    files = _cart_files()
    reviewable = ReviewableSet(
        reviewed=tuple(files),
        excluded=(SkippedFile("/appsettings.json", "excluded", "appsettings*.json"),),
    )
    plan = cp.plan_chunks(reviewable, "", _Cfg())
    outline = cp.render_outline(plan, reviewable)
    for f in files:
        assert f"`{f.path}`" in outline
    assert "appsettings" not in outline
    assert "1 other changed file(s) were not sent for review" in outline
    assert "| +1 −1 | 1 |" in outline  # Interfaces.cs: one line each way, part 1


def test_empty_reviewable_has_no_chunks():
    plan = cp.plan_chunks(ReviewableSet(), "", _Cfg())
    assert plan.total == 0 and plan.assignment == {}


def test_piece_position_invariant():
    with pytest.raises(ValueError):
        cp.ChunkPiece(file=_unrelated("z"), part=2, parts=1)
