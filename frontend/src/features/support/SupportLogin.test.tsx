import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SupportLogin } from "./SupportLogin";

describe("SupportLogin", () => {
  it("renders a dedicated staff-only sign-in form", () => {
    const markup = renderToStaticMarkup(<SupportLogin onAuthenticated={() => undefined} />);

    expect(markup).toContain("Sign in to review refunds");
    expect(markup).toContain("Staff username");
    expect(markup).toContain('type="password"');
    expect(markup).toContain("Customer accounts cannot access the refund review queue.");
  });
});
