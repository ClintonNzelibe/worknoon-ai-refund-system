import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { CustomerLogin } from "./CustomerLogin";

describe("CustomerLogin", () => {
  it("renders a focused customer sign-in form", () => {
    const markup = renderToStaticMarkup(
      <CustomerLogin onAuthenticated={vi.fn()} onBack={vi.fn()} />,
    );

    expect(markup).toContain("Sign in to access your orders");
    expect(markup).toContain('type="email"');
    expect(markup).toContain('type="password"');
    expect(markup).toContain("noValidate");
    expect(markup).toContain("required");
    expect(markup).toContain("Back to refund request");
  });
});
