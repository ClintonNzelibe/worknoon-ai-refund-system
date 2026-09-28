import { describe, expect, it } from "vitest";

import {
  refundDecisionCounts,
  refundOutcomeTitle,
  shouldPollRefundResult,
} from "./refund-result";
import type { RefundRequestResult } from "./types";

const approvedAfterHumanReview: RefundRequestResult = {
  id: 42,
  order_reference: "SYN-001",
  customer_id: 7,
  status: "approved",
  policy_outcome: "approved",
  reason_code: "damaged",
  reason: "The shoe arrived damaged.",
  requested_amount: "120.00",
  resolution_note: "Human review (approved): Confirmed damage during manual review.",
  resolved_at: "2026-09-26T12:00:00Z",
  created_at: "2026-09-26T11:00:00Z",
  items: [{
    id: 99,
    order_item: {
      id: 14,
      sku: "TRAIL-001",
      product_name: "Trail shoes",
      unit_price: "120.00",
      quantity: 1,
      is_final_sale: false,
    },
    requested_quantity: 1,
    requested_amount: "120.00",
    decision: "approved",
    decision_reason: "Human review: Confirmed damage during manual review.",
  }],
};

describe("reviewed refund result presentation", () => {
  it("uses the complete refreshed response after staff approves an escalated item", () => {
    expect(refundOutcomeTitle(approvedAfterHumanReview.status)).toBe("Your request is approved");
    expect(refundDecisionCounts(approvedAfterHumanReview)).toEqual({
      approved: 1,
      rejected: 0,
      escalated: 0,
      pending: 0,
    });
    expect(approvedAfterHumanReview.resolution_note).toBe(
      "Human review (approved): Confirmed damage during manual review.",
    );
    expect(approvedAfterHumanReview.items[0]).toMatchObject({
      decision: "approved",
      decision_reason: "Human review: Confirmed damage during manual review.",
    });
    expect(shouldPollRefundResult(approvedAfterHumanReview)).toBe(false);
  });

  it("continues polling when an item is still awaiting human review", () => {
    expect(shouldPollRefundResult({
      ...approvedAfterHumanReview,
      items: [{ ...approvedAfterHumanReview.items[0], decision: "escalated" }],
    })).toBe(true);
  });
});
