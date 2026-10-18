// DELIBERATELY FAULTY. This file exists to be reviewed, never to be shipped, and
// never to be "fixed" - each fault below is what one expected finding is made of.
// See faults.md for the fault-to-finding mapping.
//
// Not compiled, not imported, not collected by pytest: `pytest.ini` sets
// `testpaths = tests`, and the import-boundary test scans `review_agent/` only.

using System.Linq;
using Microsoft.AspNetCore.Mvc;

namespace eShop.Api.Controllers
{
    [ApiController]
    [Route("api/cart")]
    public class CartController : ControllerBase
    {
        private readonly ICartRepository _carts;
        private readonly ICatalog _catalog;
        private readonly ILogger<CartController> _log;
        private readonly IDbConnection _db;

        public CartController(ICartRepository carts, ICatalog catalog, ILogger<CartController> log, IDbConnection db)
        {
            _carts = carts;
            _catalog = catalog;
            _log = log;
            _db = db;
        }

        [HttpPost("items")]
        public IActionResult AddItem(AddItemRequest request)
        {
            // Criterion 1 - satisfied. Quantity is validated before anything else.
            if (request.Quantity <= 0)
            {
                return BadRequest("Quantity must be a positive integer.");
            }

            // FAULT 2 -> SEC-WEB-02. The bearer token is written to the log.
            _log.LogInformation("AddItem called with token {Token}", request.AuthToken);

            // FAULT 1 -> SEC-WEB-01. The product id is concatenated into SQL.
            var lookup = "SELECT Id, Name, Price FROM Products WHERE Id = '" + request.ProductId + "'";
            var product = _db.Query<Product>(lookup).FirstOrDefault();

            // Criterion 2 - satisfied. An unknown product changes nothing.
            if (product == null)
            {
                return NotFound();
            }

            var cart = _carts.GetForUser(User.Identity.Name);

            // FAULT 3 -> criterion 4. Nothing here reads product.Stock, so the stock
            // limit is never enforced - and the pull request description claims it is.

            // Criterion 3 - satisfied. An existing line is incremented, not duplicated.
            var existing = cart.Lines.FirstOrDefault(l => l.ProductId == product.Id);
            if (existing != null)
            {
                existing.Quantity += request.Quantity;
            }
            else
            {
                cart.Lines.Add(new CartLine(product.Id, product.Price, request.Quantity));
            }

            // Criterion 5 - satisfied. The total is recalculated before the save.
            cart.Recalculate();
            _carts.Save(cart);

            return Ok(cart);
        }
    }
}
