import { RefundApiError } from "./refund.api";

/** A 401 means the protected refund request needs a Django customer session. */
export function requiresCustomerLogin(error: unknown): boolean {
  return error instanceof RefundApiError && error.status === 401;
}

/** Lookup should only open login when the current customer session is missing. */
export function shouldShowCustomerLoginForLookup(error: unknown): boolean {
  return requiresCustomerLogin(error);
}

/** Preserve the generic server response while giving signed-in customers useful next steps. */
export function customerLookupErrorMessage(error: unknown): string | null {
  if (error instanceof RefundApiError
    && error.status === 404
    && typeof error.details === "object"
    && error.details !== null
    && "detail" in error.details
    && error.details.detail === "Order not found or unavailable."
  ) {
    return "Order not found. Please check your order reference and try again.";
  }
  return null;
}

export function lookupEmailMatchesAuthenticatedAccount(
  lookupEmail: string,
  authenticatedEmail: string,
): boolean {
  return lookupEmail.trim().toLocaleLowerCase() === authenticatedEmail.trim().toLocaleLowerCase();
}
