import { FormEvent, useState } from "react";

import { loginCustomer, RefundApiError } from "./refund.api";
import type { AuthenticatedCustomer } from "./refund.api";
import { validateLoginCredentials } from "./validation";

interface CustomerLoginProps {
  onAuthenticated: (customer: AuthenticatedCustomer) => void;
  onBack: () => void;
}

export function CustomerLogin({ onAuthenticated, onBack }: CustomerLoginProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateLoginCredentials(email, password);
    if (validationError) {
      setError(validationError);
      return;
    }
    setIsSubmitting(true);
    setError("");
    try {
      const customer = await loginCustomer(email.trim(), password);
      setPassword("");
      onAuthenticated(customer);
    } catch (loginError) {
      setError(loginError instanceof RefundApiError
        ? loginError.message
        : "We could not sign you in. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="refund-page login-page">
      <section className="refund-intro" aria-labelledby="login-title">
        <p className="eyebrow">Order support</p>
        <h1 id="login-title">Sign in to access your orders</h1>
        <p>Your customer account securely controls the orders and refund requests available here.</p>
      </section>
      <section className="refund-card login-card" aria-label="Customer sign in">
        <div className="login-card-heading">
          <h2>Welcome back</h2>
          <p>Use the email and password for your customer account.</p>
        </div>
        <form className="login-form" onSubmit={handleSubmit} noValidate>
          <label htmlFor="login-email">Customer email</label>
          <input id="login-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" placeholder="you@example.com" required aria-invalid={Boolean(error)} />
          <label htmlFor="login-password">Password</label>
          <input id="login-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required aria-invalid={Boolean(error)} />
          {error && <div className="status-message error login-error" role="alert">{error}</div>}
          <button type="submit" disabled={isSubmitting}>{isSubmitting ? "Signing in..." : "Sign in"}</button>
          <button type="button" className="text-button" onClick={onBack} disabled={isSubmitting}>Back to refund request</button>
        </form>
      </section>
    </main>
  );
}
