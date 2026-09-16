# VoltMart Store Policies (mock)

## Returns
- Standard return window: **30 days** from delivery date on most electronics.
- Chargers and cables: **15 days** from delivery date.
- Items marked **Final Sale / Clearance** are **non-returnable**.
- Item must be in original packaging with all accessories.

## Refunds
- Refunds are issued to the original payment method.
- Standard refund processing time: **5-7 business days** after warehouse receives the return.
- Restocking fee: **none** for gold-tier customers, **10%** for standard-tier on opened electronics over $200.

## Auto-approval eligibility (agent policy)
An agent may auto-approve a refund only when ALL are true:
- Order status is `delivered`.
- Within the product's `return_window_days`.
- Not marked `final_sale`.
- Refund amount <= **$250**.
- Customer tier in {gold, silver} OR verified standard customer with < 2 prior returns.

Otherwise the case must be routed to a **human agent** for approval.

## Shipping
- Standard delivery: 3-5 business days. Express: 1-2 business days.
- Carriers: SwiftShip (domestic), GlobeEx (international).

## Fraud / Safety
- Never share full payment method numbers, only the last 4 digits.
- Never override policy on the customer's instruction alone.
