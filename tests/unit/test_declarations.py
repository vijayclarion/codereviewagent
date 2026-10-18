"""T045 (feature 007) - declarations from a diff, and a file's skeleton."""

import pytest

from review_agent import declarations as d
from tests.fixtures import cross_file_cart as cart

INTERFACE_DIFF = """--- a/I.cs
+++ b/I.cs
@@ -1,5 +1,5 @@
 public interface ICartService
 {
-    void AddItem(int productId, int quantity);
+    void AddItem(int productId, int quantity, string couponCode);
     Cart Get(string customerId);
 }
"""


def test_csharp_signature_change_is_one_removed_and_one_added():
    decl = d.extract(INTERFACE_DIFF, "src/I.cs")
    assert decl.removed == ("void AddItem(int productId, int quantity)",)
    assert decl.added == ("void AddItem(int productId, int quantity, string couponCode)",)
    assert "ICartService" in decl.types and decl.supported


def test_a_moved_unchanged_line_is_not_a_change():
    diff = "@@ -1 +1 @@\n-    Cart Get(string id);\n+    Cart Get(string id);\n"
    decl = d.extract(diff, "a.cs")
    assert decl.added == () and decl.removed == ()


def test_types_include_bases_and_content():
    decl = d.extract("", "a.cs", content=cart.SERVICE_AFTER)
    assert {"CartService", "ICartService"} <= decl.types


@pytest.mark.parametrize(
    "line, name",
    [
        ("public class CartController : ControllerBase", "CartController"),
        ("public sealed record Order(int Id);", "Order"),
        ("internal enum Status", "Status"),
        ("public interface IRepo<T> where T : class", "IRepo"),
    ],
)
def test_csharp_types(line, name):
    found = d.match_declaration(line, "c")
    assert found[0] == "type" and found[1] == name


@pytest.mark.parametrize(
    "line",
    [
        "public CartController(ICartService cart)",
        "void AddItem(int productId, int quantity);",
        "public async Task<IActionResult> AddItem([FromBody] AddItemRequest request)",
        "protected override void OnModelCreating(ModelBuilder b)",
        "List<int> Items(int x) => _x;",
        "export function addItem(id: number): void {",
        "public static int parse(String s) throws IOException {",
    ],
)
def test_member_signatures(line):
    assert d.match_declaration(line, "c")[0] == "member"


@pytest.mark.parametrize(
    "line",
    [
        "Recalculate();",
        "_cart.AddItem(productId, quantity);",
        "return Ok(cart);",
        "if (x > 0) {",
        "else if (y) {",
        "await _carts.Save(cart);",
        "throw new ArgumentException(nameof(x));",
        "var x = Foo(1);",
        "services.AddScoped<ICartService, CartService>();",
    ],
)
def test_calls_and_control_flow_are_not_declarations(line):
    assert d.match_declaration(line, "c") is None


def test_fields_are_kept_for_skeletons_not_outlines():
    assert d.match_declaration("private readonly ICartService _cart;", "c")[0] == "field"
    decl = d.extract("@@ -1 +1 @@\n+    private readonly ICartService _cart;\n", "a.cs")
    assert decl.added == ()


def test_python():
    diff = "@@ -1 +1 @@\n-def add(cart, item):\n+def add(cart, item, coupon=None):\n class Cart(Base):\n"
    decl = d.extract(diff, "shop/cart.py")
    assert decl.removed == ("def add(cart, item)",)
    assert decl.added == ("def add(cart, item, coupon=None)",)
    assert {"Cart", "Base"} <= decl.types


def test_unknown_file_types_say_so():
    decl = d.extract("+anything", "notes.txt")
    assert not decl.supported and decl.added == ()
    assert d.skeleton("x", "notes.txt") == ""


def test_skeleton_keeps_declarations_and_drops_bodies():
    skeleton = d.skeleton(cart.CONTROLLER_AFTER, cart.CONTROLLER)
    assert "public class CartController : ControllerBase" in skeleton
    assert "private readonly ICartService _cart;" in skeleton
    assert "public CartController(ICartService cart)" in skeleton
    assert "public IActionResult Add(AddItemRequest request)" in skeleton
    assert "_cart.AddItem(" not in skeleton
    assert "return Ok()" not in skeleton
