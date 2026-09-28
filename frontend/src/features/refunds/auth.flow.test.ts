import { describe, expect, it } from "vitest";

import {
  customerLookupErrorMessage,
  lookupEmailMatchesAuthenticatedAccount,
  requiresCustomerLogin,
  shouldShowCustomerLoginForLookup,
} from "./auth.flow";
import { RefundApiError } from "./refund.api";

describe("refund authentication handoff", () => {
  it("redirects an unauthenticated submission to login", () => {
    expect(requiresCustomerLogin(new RefundApiError("Sign in", 401, null))).toBe(true);
  });

  it("redirects the normalized DRF missing-session response to login", () => {
    expect(requiresCustomerLogin(new RefundApiError(
      "Please sign in",
      401,
      { detail: "Authentication credentials were not provided." },
    ))).toBe(true);
  });

  it("does not treat an ownership denial as a login request", () => {
    expect(requiresCustomerLogin(new RefundApiError("Forbidden", 403, null))).toBe(false);
  });

  it("keeps a signed-in customer on lookup after a generic unavailable-order response", () => {
    const error = new RefundApiError(
      "Order not found or unavailable.",
      404,
      { detail: "Order not found or unavailable." },
    );
    expect(shouldShowCustomerLoginForLookup(error)).toBe(false);
    expect(customerLookupErrorMessage(error)).toBe(
      "Order not found. Please check your order reference and try again.",
    );
  });

  it("does not turn unrelated lookup errors or ownership denials into login redirects", () => {
    expect(shouldShowCustomerLoginForLookup(new RefundApiError("Not found", 404, null))).toBe(false);
    expect(shouldShowCustomerLoginForLookup(new RefundApiError("Forbidden", 403, null))).toBe(false);
    expect(customerLookupErrorMessage(new RefundApiError("Not found", 404, null))).toBeNull();
  });

  it("rejects a lookup email that differs from the signed-in customer without changing identity", () => {
    expect(lookupEmailMatchesAuthenticatedAccount(
      "avery.brooks@example.test",
      "avery.brooks@example.test",
    )).toBe(true);
    expect(lookupEmailMatchesAuthenticatedAccount(
      "mina.patel@example.test",
      "avery.brooks@example.test",
    )).toBe(false);
  });
});
