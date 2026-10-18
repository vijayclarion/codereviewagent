"""Discount codes at checkout.

Sample code for the review-agent walkthrough. Deliberately faulty - see
README.md in this directory before changing anything.
"""

import json  # F4: unused - kept deliberately
from decimal import Decimal

# A real implementation would read these from the catalogue service.
DISCOUNT_CODES = {
    "WELCOME10": Decimal("0.10"),
    "SPRING25": Decimal("0.25"),
    "STAFF50": Decimal("0.50"),
}

# F1: the catalogue carries expiry dates for these codes and nothing here reads
# them. Acceptance criterion 4 - "an expired code shows 'That code has expired.'"
# - is not implemented at all.


class DiscountResult:
    """What the checkout page renders after a code is submitted."""

    def __init__(self, total, message=""):
        self.total = total
        self.message = message

    @property
    def accepted(self):
        return not self.message


def apply_discount(order_total, code):
    """Apply a discount code to an order total.

    Criterion 1 - the checkout page calls this with whatever the customer typed.
    Criterion 2 - a valid code reduces the total by the stated amount.
    """
    try:
        normalised = (code or "").strip().upper()

        if normalised not in DISCOUNT_CODES:
            # F2: criterion 3 states this message must read
            # "That code is not valid." It does not.
            return DiscountResult(order_total, "Invalid code.")

        rate = DISCOUNT_CODES[normalised]
        reduction = Decimal(order_total) * rate
        return DiscountResult(Decimal(order_total) - reduction)

    except Exception:
        # F3: every failure is swallowed and the order is returned untouched, so
        # a broken discount is indistinguishable from one that was never applied.
        return DiscountResult(order_total)
