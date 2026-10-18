"""T032 - exclusion list, review bound, and relevance ordering."""

import pytest

from review_agent import selection
from review_agent.config import DEFAULT_EXCLUDE_PATTERNS
from review_agent.models import ChangedFile, ChangeSet, WorkItem


def _file(path, lines=10):
    return ChangedFile(path=path, diff=f"diff for {path}", changed_lines=lines)


class _Cfg:
    def __init__(self, **kw):
        self.review_exclude_patterns = kw.get("patterns", DEFAULT_EXCLUDE_PATTERNS)
        self.review_max_files = kw.get("max_files", 40)
        self.review_max_diff_lines = kw.get("max_lines", 3000)


# -- exclusions -------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "src/.env.production",
        "certs/server.pem",
        "keys/private.key",
        "app/cert.pfx",
        "store/keys.jks",
        "config/my-secrets.json",
        "src/App/appsettings.json",
        "src/App/appsettings.Production.json",
        "deploy/site.publishsettings",
        "id_rsa",
        "sign/key.snk",
    ],
)
def test_secret_bearing_paths_are_excluded(path):
    assert selection.match_exclusion(path, DEFAULT_EXCLUDE_PATTERNS) is not None


@pytest.mark.parametrize(
    "path",
    [
        "package-lock.json",
        "web/yarn.lock",
        "poetry.lock",
        "wwwroot/app.min.js",
        "wwwroot/site.min.css",
        "Forms/Main.Designer.cs",
        "Generated/Model.g.cs",
        "src/Api/Migrations/20240101_Init.cs",
        "src/Api/bin/Debug/App.dll",
        "src/Api/obj/project.assets.json",
        "web/node_modules/lodash/index.js",
        "web/dist/bundle.js",
    ],
)
def test_generated_and_noise_paths_are_excluded(path):
    assert selection.match_exclusion(path, DEFAULT_EXCLUDE_PATTERNS) is not None


@pytest.mark.parametrize(
    "path",
    [
        "src/eShop.Api/Controllers/CartController.cs",
        "src/eShop.Api/Models/Cart.cs",
        "review_agent/main.py",
        "README.md",
        "azure-pipelines.yml",
    ],
)
def test_ordinary_source_is_not_excluded(path):
    assert selection.match_exclusion(path, DEFAULT_EXCLUDE_PATTERNS) is None


def test_leading_slash_does_not_defeat_matching():
    assert selection.match_exclusion("/src/App/appsettings.json", DEFAULT_EXCLUDE_PATTERNS)


def test_exclusion_is_case_insensitive():
    assert selection.match_exclusion("SRC/App/AppSettings.JSON", DEFAULT_EXCLUDE_PATTERNS)


def test_replace_mode_lets_a_team_review_configuration():
    """The appsettings default is the debatable one; it must be removable."""
    config = _Cfg(patterns=("*.dll",))
    change_set = ChangeSet(files=(_file("src/App/appsettings.json"),))
    result = selection.select_reviewable(change_set, config)
    assert len(result.reviewed) == 1
    assert result.excluded == ()


def test_excluded_files_are_recorded_with_the_matched_pattern():
    change_set = ChangeSet(files=(_file("src/App/appsettings.json"), _file("src/A.cs")))
    result = selection.select_reviewable(change_set, _Cfg())
    assert len(result.reviewed) == 1
    assert len(result.excluded) == 1
    assert "appsettings" in result.excluded[0].detail
    assert result.excluded[0].reason == "excluded"


def test_everything_excluded_leaves_an_empty_reviewable_set():
    change_set = ChangeSet(files=(_file(".env"), _file("certs/a.pem")))
    result = selection.select_reviewable(change_set, _Cfg())
    assert result.is_empty
    assert len(result.excluded) == 2


# -- bound ------------------------------------------------------------------


def test_file_count_bound_truncates_and_records():
    files = tuple(_file(f"src/File{i}.cs") for i in range(10))
    result = selection.select_reviewable(ChangeSet(files=files), _Cfg(max_files=4))
    assert len(result.reviewed) == 4
    assert len(result.unreviewed) == 6
    assert all(s.reason == "bound" for s in result.unreviewed)


def test_line_bound_truncates():
    files = tuple(_file(f"src/File{i}.cs", lines=100) for i in range(10))
    result = selection.select_reviewable(ChangeSet(files=files), _Cfg(max_lines=250))
    assert result.total_diff_lines <= 250
    assert result.unreviewed


def test_unreviewed_files_state_their_size():
    files = tuple(_file(f"src/File{i}.cs", lines=50) for i in range(6))
    result = selection.select_reviewable(ChangeSet(files=files), _Cfg(max_files=2))
    assert all("changed lines" in s.detail for s in result.unreviewed)


def test_a_single_oversized_file_is_still_reviewed():
    """Reviewing nothing would be worse than exceeding the bound by one file."""
    result = selection.select_reviewable(
        ChangeSet(files=(_file("src/Huge.cs", lines=9000),)), _Cfg(max_lines=100)
    )
    assert len(result.reviewed) == 1


def test_no_file_is_silently_dropped():
    """Every input must appear in exactly one output bucket (FR-014c, FR-014f)."""
    files = (
        _file("src/A.cs"),
        _file("src/B.cs"),
        _file(".env"),
        _file("src/App/appsettings.json"),
        _file("src/C.cs"),
    )
    result = selection.select_reviewable(ChangeSet(files=files), _Cfg(max_files=2))
    accounted = len(result.reviewed) + len(result.excluded) + len(result.unreviewed)
    assert accounted == len(files)


# -- relevance --------------------------------------------------------------


def _story():
    return (
        WorkItem(
            id=101,
            title="Add items to shopping cart",
            acceptance_criteria="The cart must not exceed available stock.",
        ),
    )


def test_story_related_files_are_reviewed_first_under_a_tight_bound():
    files = (
        _file("src/Infrastructure/Logging/Logger.cs"),
        _file("src/Api/Controllers/CartController.cs"),
        _file("src/Api/Utils/StringHelpers.cs"),
    )
    result = selection.select_reviewable(
        ChangeSet(files=files), _Cfg(max_files=1), work_items=_story()
    )
    assert "Cart" in result.reviewed[0].path


def test_source_files_outrank_documentation_when_nothing_else_differs():
    files = (_file("docs/notes.txt"), _file("src/Service.cs"))
    result = selection.select_reviewable(ChangeSet(files=files), _Cfg(max_files=1))
    assert result.reviewed[0].path.endswith(".cs")


def test_smaller_changes_win_ties_so_the_bound_covers_more_files():
    files = (_file("src/Big.cs", lines=500), _file("src/Small.cs", lines=5))
    result = selection.select_reviewable(ChangeSet(files=files), _Cfg(max_files=1))
    assert result.reviewed[0].path.endswith("Small.cs")


def test_relevance_score_is_recorded_on_the_reviewed_file():
    result = selection.select_reviewable(
        ChangeSet(files=(_file("src/Api/CartController.cs"),)), _Cfg(), work_items=_story()
    )
    assert result.reviewed[0].relevance > 0


# --------------------------------------------------------------------------
# T028 (feature 003) - rule selection when the corpus is larger than one pass.
#
# The scoring decides which rules are worth keeping. The tie-break decides
# whether two operators reviewing the same pull request apply the same rules,
# which is what SC-006 rests on - so it is the part asserted hardest.
# --------------------------------------------------------------------------

from review_agent.models import ChangedFile, ChecklistItem, CombinedChecklist, ReviewableSet


def _corpus(*titles, documents=("Std.docx",)):
    """Identifiers derive from the title, as the real readers' do - so that
    reversing the corpus reverses only the order, not the identities."""
    return CombinedChecklist(
        items=tuple(
            ChecklistItem(item_id=f"R-{abs(hash(title)) % 10**6}", title=title, documents=documents)
            for title in titles
        )
    )


def _reviewable(*paths):
    return ReviewableSet(
        reviewed=tuple(ChangedFile(path=path, changed_lines=10) for path in paths)
    )


def test_rules_about_the_changed_files_come_first():
    corpus = _corpus(
        "Log every exception with its context",
        "Validate every cart quantity before use",
    )
    applied = selection.select_rules(corpus, _reviewable("src/CartController.cs"), 10_000)
    assert applied.items[0].title.startswith("Validate every cart")


def test_a_corpus_that_fits_loses_nothing_and_states_no_basis():
    corpus = _corpus("Rule one", "Rule two")
    applied = selection.select_rules(corpus, _reviewable("a.cs"), 10_000)
    assert applied.rule_count == 2
    assert applied.dropped_for_budget == ()
    assert applied.selection_basis == ""


def test_an_oversized_corpus_states_what_it_omitted_and_why():
    corpus = _corpus(*[f"Rule number {n} about something" for n in range(1, 21)])
    applied = selection.select_rules(corpus, _reviewable("a.cs"), 120)
    assert applied.dropped_for_budget, "an oversized corpus must report what it dropped"
    assert applied.selection_basis == "relevance to the changed files"
    assert applied.rule_count + len(applied.dropped_for_budget) == 20


def test_at_least_one_rule_is_always_applied():
    """A budget too small for one rule is a misconfiguration, not a silent no-op."""
    corpus = _corpus("A rule whose text is far longer than the budget allows")
    applied = selection.select_rules(corpus, _reviewable("a.cs"), 1)
    assert applied.rule_count == 1


def test_the_same_change_and_corpus_select_the_same_rules_whatever_the_order():
    """SC-006: two operators, same pull request, same rules."""
    titles = [f"Rule about cart {n}" for n in range(1, 11)]
    reviewable = _reviewable("src/CartController.cs")
    forwards = selection.select_rules(_corpus(*titles), reviewable, 200)
    backwards = selection.select_rules(_corpus(*reversed(titles)), reviewable, 200)
    assert [i.title for i in forwards.items] == [i.title for i in backwards.items]


def test_an_unavailable_corpus_is_returned_untouched():
    corpus = CombinedChecklist(unavailable_reason="nothing was reachable")
    assert selection.select_rules(corpus, _reviewable("a.cs"), 10_000) is corpus
