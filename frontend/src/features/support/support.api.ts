import { apiRequest } from "../refunds/refund.api";
import type { SupportRefundPage, SupportRefundRequest } from "../refunds/types";

export interface AuthenticatedSupportUser {
  username: string;
}

export interface SupportFilters {
  status?: string;
  customerEmail?: string;
  orderReference?: string;
  page?: number;
}

export async function listSupportRefunds(filters: SupportFilters): Promise<SupportRefundPage> {
  const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status);
  if (filters.customerEmail) query.set("customer_email", filters.customerEmail);
  if (filters.orderReference) query.set("order_reference", filters.orderReference);
  if (filters.page) query.set("page", String(filters.page));
  const suffix = query.size ? `?${query.toString()}` : "";
  return apiRequest<SupportRefundPage>(`/support/refund-requests/${suffix}`);
}

export async function getSupportSession(): Promise<AuthenticatedSupportUser> {
  return apiRequest<AuthenticatedSupportUser>("/auth/staff/session/");
}

export async function loginSupportStaff(
  username: string,
  password: string,
): Promise<AuthenticatedSupportUser> {
  await apiRequest<void>("/auth/csrf/", { method: "GET" });
  return apiRequest<AuthenticatedSupportUser>("/auth/staff/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function getSupportRefund(refundRequestId: number): Promise<SupportRefundRequest> {
  return apiRequest<SupportRefundRequest>(`/support/refund-requests/${refundRequestId}/`);
}

export async function reviewSupportRefund(
  refundRequestId: number,
  decision: "approved" | "rejected",
  note: string,
): Promise<SupportRefundRequest> {
  return apiRequest<SupportRefundRequest>(`/support/refund-requests/${refundRequestId}/review/`, {
    method: "POST",
    body: JSON.stringify({ decision, note }),
  });
}
