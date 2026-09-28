import { FormEvent, useState } from "react";

import { RefundApiError } from "../refunds/refund.api";
import { loginSupportStaff, type AuthenticatedSupportUser } from "./support.api";

export function SupportLogin({ onAuthenticated }: { onAuthenticated: (user: AuthenticatedSupportUser) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!username.trim() || !password) {
      setError("Enter your staff username and password.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const user = await loginSupportStaff(username.trim(), password);
      setPassword("");
      onAuthenticated(user);
    } catch (loginError) {
      setError(loginError instanceof RefundApiError
        ? loginError.message
        : "We could not sign you in. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="support-page support-login-page">
      <section className="support-header">
        <div><p className="eyebrow">Support workspace</p><h1>Sign in to review refunds</h1><p>Use your Django staff account. Customer accounts cannot access the refund review queue.</p></div>
        <a href="/" className="customer-link">Customer experience</a>
      </section>
      <section className="support-card support-login-card" aria-label="Support staff sign in">
        <form className="login-form" onSubmit={submit}>
          <label htmlFor="support-username">Staff username</label>
          <input id="support-username" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          <label htmlFor="support-password">Password</label>
          <input id="support-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
          {error && <div className="status-message error login-error" role="alert">{error}</div>}
          <button type="submit" disabled={submitting}>{submitting ? "Signing in…" : "Sign in to support"}</button>
        </form>
      </section>
    </main>
  );
}
