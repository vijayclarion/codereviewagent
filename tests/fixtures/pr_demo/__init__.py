"""Recorded payloads for the SC-001 demo scenario.

Shapes match contracts/tfs-endpoints.md. Story #101 has five acceptance criteria;
CartController.AddItem implements four of them and omits the stock limit, while
the PR description claims stock checking is covered. That gap is the whole point
of the fixture - it is what a correct run must find.
"""

PULL_REQUEST = {
    "pullRequestId": 1234,
    "title": "Add items to shopping cart",
    "description": """Implements the add-to-cart endpoint for user story #101.

## Covered

- Quantity validation - rejects zero and negative quantities
- Unknown product returns not-found without changing the cart
- Adding an existing product increments the existing line
- Stock limit enforced when adding to cart
- Cart total recalculated after a successful add

## Not in this PR

- #102 - Remove items from the cart
- #103 - Apply promotional codes at checkout
""",
    "sourceRefName": "refs/heads/feature/add-to-cart",
    "targetRefName": "refs/heads/master",
    "status": "active",
    "lastMergeTargetCommit": {"commitId": "base000000000000000000000000000000000000"},
}

LINKED_WORK_ITEMS = {"count": 1, "value": [{"id": "101"}]}

WORK_ITEM_101 = {
    "id": 101,
    "fields": {
        "System.Title": "Add items to shopping cart",
        "System.WorkItemType": "User Story",
        "System.State": "Active",
        "System.Tags": "cart; checkout",
        "System.Description": (
            "<div>As a shopper, I want to add items to my shopping cart so that I "
            "can buy several products in one order.</div>"
        ),
        "Microsoft.VSTS.Common.AcceptanceCriteria": (
            "<ul>"
            "<li>Quantity must be a positive integer; a request with zero or a "
            "negative quantity is rejected with a validation error.</li>"
            "<li>Adding an unknown product returns a not-found response and does "
            "not change the cart.</li>"
            "<li>Adding a product already in the cart increments the quantity of "
            "the existing line instead of appending a second line.</li>"
            "<li>The system must not allow adding more items than are available in "
            "stock; a request exceeding available stock is rejected.</li>"
            "<li>The cart total is recalculated after a successful add, before the "
            "cart is saved.</li>"
            "</ul>"
        ),
    },
}

ITERATIONS = {
    "count": 1,
    "value": [
        {
            "id": 7,
            "sourceRefCommit": {"commitId": "head000000000000000000000000000000000000"},
            "commonRefCommit": {"commitId": "base000000000000000000000000000000000000"},
        }
    ],
}

CART_CONTROLLER_PATH = "/src/eShop.Api/Controllers/CartController.cs"
APPSETTINGS_PATH = "/src/eShop.Api/appsettings.json"

ITERATION_CHANGES = {
    "changeEntries": [
        {"changeType": "edit", "item": {"path": CART_CONTROLLER_PATH, "isFolder": False}},
        {"changeType": "edit", "item": {"path": APPSETTINGS_PATH, "isFolder": False}},
    ]
}

CART_CONTROLLER_BEFORE = """using Microsoft.AspNetCore.Mvc;

namespace eShop.Api.Controllers
{
    [ApiController]
    public class CartController : ControllerBase
    {
    }
}
"""

# Four criteria implemented. No stock check anywhere - criterion 4 is absent.
CART_CONTROLLER_AFTER = """using System.Linq;
using Microsoft.AspNetCore.Mvc;

namespace eShop.Api.Controllers
{
    [ApiController]
    public class CartController : ControllerBase
    {
        [HttpPost("{customerId}/items")]
        public IActionResult AddItem(string customerId, [FromBody] AddItemRequest request)
        {
            if (request == null || request.Quantity <= 0)
            {
                return BadRequest(new { message = "Quantity must be a positive integer." });
            }

            var product = _catalog.Find(request.ProductId);
            if (product == null)
            {
                return NotFound(new { message = "Product was not found." });
            }

            var cart = _carts.GetForCustomer(customerId) ?? Cart.CreateFor(customerId);
            var existing = cart.Items.FirstOrDefault(i => i.ProductId == request.ProductId);
            if (existing != null)
            {
                existing.Quantity += request.Quantity;
            }
            else
            {
                cart.Items.Add(new CartItem { ProductId = product.Id, Quantity = request.Quantity });
            }

            cart.Recalculate();
            _carts.Save(cart);
            return Ok(cart);
        }
    }
}
"""

APPSETTINGS_AFTER = """{
  "ConnectionStrings": {
    "Default": "Server=db;Database=eShop;User Id=sa;Password=hunter2;"
  }
}
"""

CHECKLIST_ITEMS = {
    "count": 2,
    "value": [
        {"path": "/code-review-checklist.md", "isFolder": False, "gitObjectType": "blob"},
        {"path": "/security-checklist.md", "isFolder": False, "gitObjectType": "blob"},
        {"path": "/docs", "isFolder": True, "gitObjectType": "tree"},
        {"path": "/README.txt", "isFolder": False, "gitObjectType": "blob"},
    ],
}

CHECKLIST_MAIN = """# Code Review Checklist

## Correctness

- Business rules from the story are enforced in code, not merely assumed.
- Input is validated before use.
"""

CHECKLIST_SECURITY = """# Security Checklist

- No secret, connection string, token, or key appears in committed configuration.
"""

# What a correct model response looks like for this diff.
MODEL_RESPONSE = {
    "coverage": [
        {
            "criterion": "Quantity must be a positive integer; a request with zero or a "
            "negative quantity is rejected with a validation error.",
            "status": "appears_addressed",
            "evidence": "AddItem returns BadRequest when request.Quantity <= 0.",
        },
        {
            "criterion": "Adding an unknown product returns a not-found response and does "
            "not change the cart.",
            "status": "appears_addressed",
            "evidence": "A null result from _catalog.Find returns NotFound before the cart "
            "is touched.",
        },
        {
            "criterion": "Adding a product already in the cart increments the quantity of "
            "the existing line instead of appending a second line.",
            "status": "appears_addressed",
            "evidence": "The existing-line branch increments existing.Quantity.",
        },
        {
            "criterion": "The system must not allow adding more items than are available in "
            "stock; a request exceeding available stock is rejected.",
            "status": "not_addressed",
            "evidence": "The diff contains no stock or inventory check; product stock is "
            "never read.",
        },
        {
            "criterion": "The cart total is recalculated after a successful add, before the "
            "cart is saved.",
            "status": "appears_addressed",
            "evidence": "cart.Recalculate() is called before _carts.Save(cart).",
        },
    ],
    "checklist_violations": [
        {
            "item": "Business rules from the story are enforced in code, not merely assumed.",
            "source": "code-review-checklist.md",
            "issue": "AddItem does not enforce the stock limit that acceptance criterion 4 "
            "requires.",
            "file": "src/eShop.Api/Controllers/CartController.cs",
            "line": 26,
        }
    ],
    "code_issues": [],
    "summary": "The change implements quantity validation, not-found handling, line "
    "merging, and total recalculation for story #101. It does not enforce the stock "
    "limit, which the description claims is covered.",
}
