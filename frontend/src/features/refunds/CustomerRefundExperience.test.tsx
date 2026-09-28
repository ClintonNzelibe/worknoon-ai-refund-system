import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  clearedCustomerSessionState,
  clearedOrderLookupState,
  CustomerIdentity,
  CustomerLookupAccount,
  CustomerRefundResult,
} from "./CustomerRefundExperience";
import type { RefundRequestResult } from "./types";

function result(overrides: Partial<RefundRequestResult> = {}): RefundRequestResult {
  return {
    id: 16, order_reference: "SYN-001", customer_id: 4, status: "approved", policy_outcome: "approved",
    reason_code: "damaged", reason: "The package arrived opened and the item was damaged.", requested_amount: "85.00",
    resolution_note: "Internal policy engine note that customers must not see.", resolved_at: "2026-09-27T12:00:00Z", created_at: "2026-09-27T11:00:00Z",
    items: [{
      id: 3,
      order_item: { id: 8, sku: "TRAIL-001", product_name: "Trail shoes", unit_price: "85.00", quantity: 1, is_final_sale: false },
      requested_quantity: 1, requested_amount: "85.00", decision: "approved", decision_reason: "Internal item-level policy explanation.",
    }],
    ai_assistance: {
      available: true,
      customer_message: "Your refund has been approved and will be processed according to the store’s refund process.",
    },
    ...overrides,
  };
}

function renderResult(overrides: Partial<RefundRequestResult> = {}) {
  return renderToStaticMarkup(<CustomerRefundResult result={result(overrides)} currency="USD" />);
}

describe("customer refund result", () => {
  it("shows the authenticated customer identity and a switch-customer action", () => {
    const markup = renderToStaticMarkup(<CustomerIdentity customer={{
      email: "diego.ramos@example.test", full_name: "Diego Ramos",
    }} onLogout={() => undefined} />);
    expect(markup).toContain("Logged in as");
    expect(markup).toContain("diego.ramos@example.test");
    expect(markup).toContain("Logout");
  });

  it("uses a read-only session email for lookup, so typing another email cannot change identity", () => {
    const markup = renderToStaticMarkup(<CustomerLookupAccount customer={{
      email: "diego.ramos@example.test", full_name: "Diego Ramos",
    }} />);
    expect(markup).toContain("diego.ramos@example.test");
    expect(markup).toContain("readOnly");
    expect(markup).toContain("Changing it never changes which customer account can access orders");
  });

  it("clears customer, order, request, and polling state when switching customers", () => {
    expect(clearedCustomerSessionState()).toEqual({
      customer: null,
      orderReference: "",
      lookupState: "idle",
      error: "",
      notice: "",
      order: null,
      quantities: {},
      reasonCode: "damaged",
      reason: "",
      result: null,
      idempotencyKey: null,
      submitState: "idle",
    });
  });

  it("clears the previous order, selected items, request details, and polling result before a new lookup", () => {
    expect(clearedOrderLookupState()).toEqual({
      order: null,
      quantities: {},
      reasonCode: "damaged",
      reason: "",
      result: null,
      idempotencyKey: null,
      submitState: "idle",
    });
  });

  it("shows an approved outcome, clear amount, customer guidance, and next steps", () => {
    const markup = renderResult();
    expect(markup).toContain("Refund approved");
    expect(markup).toContain("Approved amount");
    expect(markup).toContain("$85.00");
    expect(markup).toContain("What happens next?");
    expect(markup).toContain("Helpful guidance");
    expect(markup).toContain("Powered by automated assistance");
  });

  it("presents an escalated request as customer-safe support review guidance", () => {
    const base = result();
    const markup = renderResult({ status: "escalated", policy_outcome: "escalated", items: [{ ...base.items[0], decision: "escalated" }] });
    expect(markup).toContain("Needs a quick review");
    expect(markup).toContain("Waiting for support review");
    expect(markup).toContain("Please provide clear photos of the damaged area and original packaging");
    expect(markup).toContain("Please keep the item and packaging available");
    expect(markup).toContain("you don’t need to submit it again");
  });

  it("presents a denied request without exposing provider errors", () => {
    const base = result();
    const markup = renderResult({
      status: "rejected", policy_outcome: "rejected", items: [{ ...base.items[0], decision: "rejected" }],
      ai_assistance: { available: false },
    });
    expect(markup).toContain("Refund request not approved");
    expect(markup).toContain("If you believe this decision is incorrect");
    expect(markup).toContain("Automated assistance is temporarily unavailable");
  });

  it("does not expose internal AI or policy fields in the customer result", () => {
    const markup = renderResult();
    expect(markup).not.toContain("Classification");
    expect(markup).not.toContain("Risk");
    expect(markup).not.toContain("Internal policy engine note");
    expect(markup).not.toContain("Internal item-level policy explanation");
    expect(markup).not.toContain("Deterministic policy");
  });

  it("uses the refreshed human-reviewed response naturally after polling", () => {
    const markup = renderResult();
    expect(markup).toContain("Refund approved");
    expect(markup).toContain("Approved");
    expect(markup).not.toContain("Needs a quick review");
  });

  it("uses responsive-safe result cards without fixed-width markup", () => {
    const markup = renderResult();
    expect(markup).toContain("customer-result-card");
    expect(markup).toContain("result-summary-grid");
    expect(markup).toContain("customer-item-list");
    expect(markup).not.toContain("width:");
  });
});
