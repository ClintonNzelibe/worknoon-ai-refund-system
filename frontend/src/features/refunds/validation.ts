import type { RefundReasonCode } from "./types";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const VALID_REASON_CODES: RefundReasonCode[] = ["damaged", "incorrect", "other"];

export function validateEmail(email: string): string | null {
  if (!email.trim()) return "Enter your customer email.";
  if (!EMAIL_PATTERN.test(email.trim())) return "Enter a valid email address.";
  return null;
}

export function validateLoginCredentials(email: string, password: string): string | null {
  return validateEmail(email) ?? (password ? null : "Enter your password.");
}

export function validateOrderReference(reference: string): string | null {
  const normalized = reference.trim();
  if (!normalized) return "Enter an order reference to continue.";
  if (normalized.length > 64) return "Enter an order reference of 64 characters or fewer.";
  return null;
}

export function validateRefundDetails(
  reasonCode: string,
  details: string,
  selectedItemCount: number,
): string | null {
  if (selectedItemCount === 0) return "Select at least one item for refund.";
  if (!VALID_REASON_CODES.includes(reasonCode as RefundReasonCode)) return "Choose a valid refund reason.";
  if (!details.trim()) return "Tell us what happened with the selected item or items.";
  if (details.length > 4_000) return "Keep the details to 4,000 characters or fewer.";
  return null;
}
