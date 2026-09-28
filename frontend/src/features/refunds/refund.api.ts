import type {
  CreateRefundRequestInput,
  CustomerOrderLookup,
  Order,
  RefundRequestResult,
} from "./types";

const apiBaseUrl = import.meta.env.VITE_REFUND_API_BASE_URL ?? "/api";

export class RefundApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly details: unknown,
  ) {
    super(message);
    this.name = "RefundApiError";
  }
}

export interface AuthenticatedCustomer {
  email: string;
  full_name: string;
}

export async function loginCustomer(
  email: string,
  password: string,
): Promise<AuthenticatedCustomer> {
  await apiRequest<void>("/auth/csrf/", { method: "GET" });
  return apiRequest<AuthenticatedCustomer>("/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function logoutCustomer(): Promise<void> {
  return apiRequest<void>("/auth/logout/", { method: "POST" });
}

export async function getCustomerSession(): Promise<AuthenticatedCustomer> {
  return apiRequest<AuthenticatedCustomer>("/auth/session/");
}

export async function lookupCustomer(email: string): Promise<CustomerOrderLookup> {
  return apiRequest<CustomerOrderLookup>(`/customers/lookup/?email=${encodeURIComponent(email)}`);
}

export async function lookupOrder(reference: string): Promise<Order> {
  return apiRequest<Order>(`/orders/${encodeURIComponent(reference)}/`);
}

export async function createRefundRequest(
  input: CreateRefundRequestInput,
  idempotencyKey: string,
): Promise<RefundRequestResult> {
  return apiRequest<RefundRequestResult>("/refund-requests/", {
    method: "POST",
    body: JSON.stringify(input),
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export async function getRefundRequest(
  refundRequestId: number,
  orderReference: string,
): Promise<RefundRequestResult | null> {
  const requests = await apiRequest<RefundRequestResult[]>(
    `/refund-requests/?order_reference=${encodeURIComponent(orderReference)}`,
  );
  return requests.find((request) => request.id === refundRequestId) ?? null;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("Content-Type", "application/json");
  const csrf = csrfToken();
  if (csrf) {
    headers.set("X-CSRFToken", csrf);
  }

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
  } catch {
    throw new RefundApiError(
      "We could not reach the refund service. Please try again shortly.",
      0,
      null,
    );
  }

  const payload: unknown = await parseResponse(response);
  if (!response.ok) {
    // DRF SessionAuthentication returns a 403, rather than a 401, when no
    // session credentials are supplied. Normalize only that exact condition
    // for the customer-flow state machine; ownership denials remain 403.
    const errorStatus = isMissingSessionCredentials(response.status, payload)
      ? 401
      : response.status;
    throw new RefundApiError(
      messageFromPayload(payload, errorStatus),
      errorStatus,
      payload,
    );
  }
  return payload as T;
}

function isMissingSessionCredentials(status: number, payload: unknown): boolean {
  return status === 403
    && typeof payload === "object"
    && payload !== null
    && "detail" in payload
    && payload.detail === "Authentication credentials were not provided.";
}

function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return null;
}

function messageFromPayload(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  if (status === 401 || status === 403) {
    return "Please sign in before looking up an order or submitting a refund request.";
  }
  return "We could not complete that request. Please check the details and try again.";
}
