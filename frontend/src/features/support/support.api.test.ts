import { afterEach, describe, expect, it, vi } from "vitest";

import { RefundApiError } from "../refunds/refund.api";
import { getSupportSession, listSupportRefunds, loginSupportStaff, reviewSupportRefund } from "./support.api";

describe("support API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends support filters with session credentials", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ count: 0, page: 1, page_size: 10, total_pages: 0, results: [] }), {
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "" });

    await listSupportRefunds({ status: "escalated", customerEmail: "customer@example.com", page: 2 });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/support/refund-requests/?status=escalated&customer_email=customer%40example.com&page=2",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("posts a human decision and review note to the dedicated review endpoint", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ id: 7 }), { headers: { "content-type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "" });

    await reviewSupportRefund(7, "approved", "Confirmed damage.");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/support/refund-requests/7/review/",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ decision: "approved", note: "Confirmed damage." }) }),
    );
  });

  it("returns a typed error when support access is denied", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Support staff access is required." }), {
        status: 403,
        headers: { "content-type": "application/json" },
      }),
    ));
    vi.stubGlobal("document", { cookie: "" });

    await expect(listSupportRefunds({})).rejects.toBeInstanceOf(RefundApiError);
  });

  it("restores a staff session after a dashboard refresh using credentialed requests", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ username: "support" }), {
      headers: { "content-type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "" });

    await expect(getSupportSession()).resolves.toEqual({ username: "support" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/staff/session/", expect.objectContaining({ credentials: "include" }),
    );
  });

  it("creates a staff session through the existing CSRF-protected Django session flow", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ username: "support" }), {
        headers: { "content-type": "application/json" },
      }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "csrftoken=test-token" });

    await expect(loginSupportStaff("support", "staff-password")).resolves.toEqual({ username: "support" });
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/auth/csrf/", expect.objectContaining({ credentials: "include" }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/auth/staff/login/", expect.objectContaining({
      credentials: "include", method: "POST", body: JSON.stringify({ username: "support", password: "staff-password" }),
    }));
  });
});
