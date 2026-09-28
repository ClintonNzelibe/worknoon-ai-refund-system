import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createRefundRequest,
  getCustomerSession,
  getRefundRequest,
  loginCustomer,
  logoutCustomer,
  RefundApiError,
} from "./refund.api";

describe("customer authentication API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("obtains CSRF protection then establishes a credentialed Django session", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        email: "avery.brooks@example.test", full_name: "Avery Brooks",
      }), { headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "csrftoken=test-token" });

    await loginCustomer("avery.brooks@example.test", "local-demo-refund-avery");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1, "/api/auth/csrf/", expect.objectContaining({ credentials: "include", method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2, "/api/auth/login/", expect.objectContaining({
        credentials: "include",
        method: "POST",
        body: JSON.stringify({ email: "avery.brooks@example.test", password: "local-demo-refund-avery" }),
      }),
    );
  });

  it("surfaces invalid Django credentials without retaining the password", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Invalid email or password." }), {
        status: 401,
        headers: { "content-type": "application/json" },
      })));
    vi.stubGlobal("document", { cookie: "csrftoken=test-token" });

    await expect(loginCustomer("customer@example.test", "wrong-password")).rejects.toBeInstanceOf(RefundApiError);
  });

  it("submits a refund with the existing credentialed session", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ id: 9 }), {
      headers: { "content-type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "csrftoken=test-token" });

    await createRefundRequest({
      order_reference: "SYN-001",
      reason_code: "damaged",
      reason: "The item arrived damaged.",
      items: [{ order_item_id: 1, requested_quantity: 1 }],
    }, "authenticated-key");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/refund-requests/",
      expect.objectContaining({ credentials: "include", method: "POST" }),
    );
  });

  it("fetches the current reviewed status for an escalated customer request", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify([{
      id: 9,
      order_reference: "SYN-005",
      status: "approved",
      policy_outcome: "approved",
      items: [],
    }]), { headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "" });

    const result = await getRefundRequest(9, "SYN-005");

    expect(result?.status).toBe("approved");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/refund-requests/?order_reference=SYN-005",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("normalizes DRF's missing-session response so submission can show login", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      detail: "Authentication credentials were not provided.",
    }), {
      status: 403,
      headers: { "content-type": "application/json" },
    })));
    vi.stubGlobal("document", { cookie: "" });

    await expect(createRefundRequest({
      order_reference: "SYN-001",
      reason_code: "damaged",
      reason: "The item arrived damaged.",
      items: [{ order_item_id: 1, requested_quantity: 1 }],
    }, "unauthenticated-key")).rejects.toMatchObject({ status: 401 });
  });

  it("keeps an ownership or authorization denial as a 403", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      detail: "You cannot create a refund request for this order.",
    }), {
      status: 403,
      headers: { "content-type": "application/json" },
    })));
    vi.stubGlobal("document", { cookie: "" });

    await expect(createRefundRequest({
      order_reference: "SYN-001",
      reason_code: "damaged",
      reason: "The item arrived damaged.",
      items: [{ order_item_id: 1, requested_quantity: 1 }],
    }, "ownership-denied-key")).rejects.toMatchObject({ status: 403 });
  });

  it("ends the existing Django session through the logout endpoint", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "csrftoken=test-token" });

    await logoutCustomer();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout/",
      expect.objectContaining({ credentials: "include", method: "POST" }),
    );
  });

  it("reads the existing Django customer session without using lookup email as identity", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      email: "diego.ramos@example.test", full_name: "Diego Ramos",
    }), { headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "" });

    await expect(getCustomerSession()).resolves.toEqual({
      email: "diego.ramos@example.test", full_name: "Diego Ramos",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/session/", expect.objectContaining({ credentials: "include" }),
    );
  });
});
