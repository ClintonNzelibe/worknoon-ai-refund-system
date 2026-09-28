# Refund policy

The deterministic policy engine is the source of truth for refund eligibility. AI assistance may summarize evidence, but it must not approve, reject, or override these rules.

## Rules

1. The refund period is **30 calendar days from the order timestamp**. An item is outside the period once the current timestamp is later than `ordered_at + 30 days`.
2. Final-sale items are never refundable, even when another item on the same order is eligible.
3. A request cannot exceed the quantity purchased for an item.
4. Requests for damaged or incorrect items are approved when the item is within the refund period and no higher-priority review rule applies.
5. A request whose stated refund amount is greater than **$500.00** is escalated to human review.
6. A request marked suspicious, or one that conflicts with an unresolved, approved, paid, or escalated claim for the same item, is escalated to human review.
7. Other stated reasons are rejected by this synthetic policy.

Rules 1–3 are hard eligibility rules. Requests are evaluated item by item, so an order containing both an eligible item and a final-sale item receives separate decisions.

## Human review boundary

Only policy-escalated items are eligible for staff review. Human review can resolve those items, but it does not alter final-sale or expired-item hard denials. Quantity overages are rejected before policy evaluation. Every staff review action is recorded in the audit log.
