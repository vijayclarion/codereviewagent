"""T044 (feature 007) - the cross-file defect the acceptance test must find.

`ICartService.AddItem` gains a `couponCode` parameter; `CartService` follows it;
`CartController` is edited elsewhere but still calls the two-argument form. No
single file is wrong on its own.
"""

from review_agent.models import ChangeEntry
from tests.fixtures import github_pr as gh

INTERFACES = "src/eShop.Api/Services/Interfaces.cs"
SERVICE = "src/eShop.Api/Services/CartService.cs"
CONTROLLER = "src/eShop.Api/Controllers/CartController.cs"
CART = "src/eShop.Api/Models/Cart.cs"

INTERFACES_BEFORE = """namespace eShop.Api.Services
{
    public interface ICartService
    {
        void AddItem(int productId, int quantity);
        Cart Get(string customerId);
    }
}
"""
INTERFACES_AFTER = INTERFACES_BEFORE.replace(
    "void AddItem(int productId, int quantity);",
    "void AddItem(int productId, int quantity, string couponCode);",
)

SERVICE_BEFORE = """namespace eShop.Api.Services
{
    public class CartService : ICartService
    {
        public void AddItem(int productId, int quantity)
        {
            _cart.Add(productId, quantity);
        }

        public Cart Get(string customerId) => _carts.Find(customerId);
    }
}
"""
SERVICE_AFTER = SERVICE_BEFORE.replace(
    "public void AddItem(int productId, int quantity)\n        {\n            _cart.Add(productId, quantity);",
    "public void AddItem(int productId, int quantity, string couponCode)\n        {\n"
    "            _cart.Add(productId, quantity, couponCode);",
)

CONTROLLER_BEFORE = """namespace eShop.Api.Controllers
{
    public class CartController : ControllerBase
    {
        private readonly ICartService _cart;

        public CartController(ICartService cart)
        {
            _cart = cart;
        }

        [HttpPost]
        public IActionResult Add(AddItemRequest request)
        {
            _cart.AddItem(request.ProductId, request.Quantity);
            return Ok();
        }
    }
}
"""
CONTROLLER_AFTER = CONTROLLER_BEFORE.replace(
    "        [HttpPost]\n",
    "        [HttpPost]\n        [ProducesResponseType(200)]\n",
)

CART_BEFORE = """namespace eShop.Api.Models
{
    public class Cart
    {
        public string CustomerId { get; set; }
    }
}
"""
CART_AFTER = CART_BEFORE.replace(
    "        public string CustomerId { get; set; }\n",
    "        public string CustomerId { get; set; }\n        public string CouponCode { get; set; }\n",
)

FILES = [
    ChangeEntry("/" + INTERFACES, "edit"),
    ChangeEntry("/" + SERVICE, "edit"),
    ChangeEntry("/" + CONTROLLER, "edit"),
    ChangeEntry("/" + CART, "edit"),
]

CONTENTS = {
    (INTERFACES, gh.HEAD): INTERFACES_AFTER,
    (INTERFACES, gh.MERGE_BASE): INTERFACES_BEFORE,
    (SERVICE, gh.HEAD): SERVICE_AFTER,
    (SERVICE, gh.MERGE_BASE): SERVICE_BEFORE,
    (CONTROLLER, gh.HEAD): CONTROLLER_AFTER,
    (CONTROLLER, gh.MERGE_BASE): CONTROLLER_BEFORE,
    (CART, gh.HEAD): CART_AFTER,
    (CART, gh.MERGE_BASE): CART_BEFORE,
}

CROSS_FILE_ISSUE = {
    "severity": "high",
    "issue": "ICartService.AddItem now takes a couponCode, but CartController still "
    "calls AddItem(productId, quantity); the call no longer compiles.",
    "files": [INTERFACES, CONTROLLER],
    "file": CONTROLLER,
    "line": 15,
}


def chunk_response(with_cross_file):
    return {
        "coverage": [],
        "checklist_violations": [],
        "code_issues": [],
        "cross_file_issues": [CROSS_FILE_ISSUE] if with_cross_file else [],
        "change_notes": "Signatures and models changed in the files shown.",
        "summary": "Part reviewed.",
    }


SYNTHESIS_RESPONSE = {
    "summary": "The coupon parameter was added to the service contract but one caller was missed.",
    "coverage": [],
    "cross_file_issues": [CROSS_FILE_ISSUE],
}
