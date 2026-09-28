import { describe, expect, it } from "vitest";

import {
  validateEmail,
  validateLoginCredentials,
  validateOrderReference,
  validateRefundDetails,
} from "./validation";

describe("customer refund form validation", () => {
  it("requires a valid email and password before login", () => {
    expect(validateLoginCredentials("", "")).toBe("Enter your customer email.");
    expect(validateLoginCredentials("not-an-email", "password")).toBe("Enter a valid email address.");
    expect(validateLoginCredentials("customer@example.test", "")).toBe("Enter your password.");
    expect(validateLoginCredentials("customer@example.test", "password")).toBeNull();
  });

  it("validates lookup email and order references before a request", () => {
    expect(validateEmail(" ")).toBe("Enter your customer email.");
    expect(validateOrderReference("")).toBe("Enter an order reference to continue.");
    expect(validateOrderReference("x".repeat(65))).toBe("Enter an order reference of 64 characters or fewer.");
    expect(validateOrderReference("SYN-016")).toBeNull();
  });

  it("requires selected items, a valid reason, and details while preserving form values", () => {
    expect(validateRefundDetails("damaged", "Item arrived broken.", 0)).toBe("Select at least one item for refund.");
    expect(validateRefundDetails("invalid", "Item arrived broken.", 1)).toBe("Choose a valid refund reason.");
    expect(validateRefundDetails("damaged", "", 1)).toBe("Tell us what happened with the selected item or items.");
    expect(validateRefundDetails("damaged", "x".repeat(4_001), 1)).toBe("Keep the details to 4,000 characters or fewer.");
    expect(validateRefundDetails("damaged", "Item arrived broken.", 1)).toBeNull();
  });
});
