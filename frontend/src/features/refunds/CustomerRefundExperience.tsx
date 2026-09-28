import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  createRefundRequest,
  getCustomerSession,
  getRefundRequest,
  lookupCustomer,
  lookupOrder,
  logoutCustomer,
  RefundApiError,
  type AuthenticatedCustomer,
} from "./refund.api";
import { CustomerLogin } from "./CustomerLogin";
import {
  customerLookupErrorMessage,
  lookupEmailMatchesAuthenticatedAccount,
  requiresCustomerLogin,
  shouldShowCustomerLoginForLookup,
} from "./auth.flow";
import { createIdleSessionController } from "./idle-session";
import { customerItemStatus, customerRefundPresentation } from "./customer-result";
import { shouldPollRefundResult } from "./refund-result";
import { validateEmail, validateOrderReference, validateRefundDetails } from "./validation";
import type {
  CustomerOrderLookup,
  Order,
  RefundReasonCode,
  RefundRequestResult,
} from "./types";

type LookupState = "idle" | "loading" | "ready" | "error";
type SubmitState = "idle" | "submitting" | "success" | "error";

const REFUND_STATUS_POLL_INTERVAL_MS = 5_000;

export function clearedOrderLookupState() {
  return {
    order: null as Order | null,
    quantities: {} as Record<number, number>,
    reasonCode: "damaged" as RefundReasonCode,
    reason: "",
    result: null as RefundRequestResult | null,
    idempotencyKey: null as string | null,
    submitState: "idle" as SubmitState,
  };
}

export function clearedCustomerSessionState() {
  return {
    ...clearedOrderLookupState(),
    customer: null as CustomerOrderLookup | null,
    orderReference: "",
    lookupState: "idle" as LookupState,
    error: "",
    notice: "",
  };
}

export function CustomerRefundExperience() {
  const [orderReference, setOrderReference] = useState("");
  const [lookupEmail, setLookupEmail] = useState("");
  const [customer, setCustomer] = useState<CustomerOrderLookup | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [reasonCode, setReasonCode] = useState<RefundReasonCode>("damaged");
  const [reason, setReason] = useState("");
  const [lookupState, setLookupState] = useState<LookupState>("idle");
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [result, setResult] = useState<RefundRequestResult | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [authenticatedCustomer, setAuthenticatedCustomer] = useState<AuthenticatedCustomer | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [showLogin, setShowLogin] = useState(false);
  const [showIdleWarning, setShowIdleWarning] = useState(false);
  const idleSessionRef = useRef<ReturnType<typeof createIdleSessionController> | null>(null);

  const selectedCount = Object.keys(quantities).length;
  const selectedItems = useMemo(
    () => Object.entries(quantities).map(([id, quantity]) => ({
      order_item_id: Number(id),
      requested_quantity: quantity,
    })),
    [quantities],
  );

  useEffect(() => {
    let cancelled = false;
    void getCustomerSession()
      .then((customerSession) => {
        if (!cancelled) {
          setAuthenticatedCustomer(customerSession);
          setLookupEmail(customerSession.email);
        }
      })
      .catch(() => {
        if (!cancelled) setAuthenticatedCustomer(null);
      })
      .finally(() => {
        if (!cancelled) setSessionLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const handleIdleLogout = useCallback(() => {
    setShowIdleWarning(false);
    setAuthenticatedCustomer(null);
    clearCustomerSessionState();
    setShowLogin(true);
    void logoutCustomer().catch(() => {
      // Local state is still cleared if the server session has already expired.
    });
  }, []);

  useEffect(() => {
    if (!authenticatedCustomer || showLogin) return undefined;

    const controller = createIdleSessionController(
      () => setShowIdleWarning(true),
      handleIdleLogout,
    );
    idleSessionRef.current = controller;
    const recordActivity = () => {
      setShowIdleWarning(false);
      controller.reset();
    };
    const activityEvents = ["pointerdown", "keydown", "input", "touchstart", "focusin", "scroll"];
    activityEvents.forEach((eventName) => window.addEventListener(eventName, recordActivity));
    controller.reset();

    return () => {
      activityEvents.forEach((eventName) => window.removeEventListener(eventName, recordActivity));
      controller.clear();
      if (idleSessionRef.current === controller) idleSessionRef.current = null;
    };
  }, [authenticatedCustomer?.email, handleIdleLogout, showLogin]);

  useEffect(() => {
    if (!result || !shouldPollRefundResult(result)) {
      return undefined;
    }
    const escalatedResult = result;

    let cancelled = false;
    async function refreshReviewedResult() {
      try {
        const currentResult = await getRefundRequest(
          escalatedResult.id,
          escalatedResult.order_reference,
        );
        if (!cancelled && currentResult) {
          setResult(currentResult);
        }
      } catch {
        // Keep the last confirmed result visible if a background refresh fails.
      }
    }

    void refreshReviewedResult();
    const intervalId = window.setInterval(() => {
      void refreshReviewedResult();
    }, REFUND_STATUS_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [result?.id, result?.order_reference, result?.status]);

  async function handleCustomerLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!authenticatedCustomer) {
      setShowLogin(true);
      return;
    }
    const emailValidationError = validateEmail(lookupEmail);
    if (emailValidationError) {
      clearSelectedOrder();
      setCustomer(null);
      setLookupState("error");
      setError(emailValidationError);
      setNotice("");
      return;
    }
    if (!lookupEmailMatchesAuthenticatedAccount(lookupEmail, authenticatedCustomer.email)) {
      clearSelectedOrder();
      setCustomer(null);
      setLookupState("error");
      setError("The email does not match the signed-in account.");
      setNotice("");
      return;
    }
    setLookupState("loading");
    setError("");
    setNotice("");
    clearSelectedOrder();
    try {
      const foundCustomer = await lookupCustomer(authenticatedCustomer.email);
      setCustomer(foundCustomer);
      setLookupState("ready");
    } catch (lookupError) {
      if (shouldShowCustomerLoginForLookup(lookupError)) {
        setLookupState("idle");
        setNotice("We couldn’t find an available order. Sign in with the correct customer account to try again.");
        setShowLogin(true);
        return;
      }
      setCustomer(null);
      setLookupState("error");
      setError(customerLookupErrorMessage(lookupError) ?? errorMessage(lookupError));
    }
  }

  async function handleLogout() {
    try {
      await logoutCustomer();
      setAuthenticatedCustomer(null);
      setShowIdleWarning(false);
      clearCustomerSessionState();
      setShowLogin(true);
    } catch (logoutError) {
      setError(errorMessage(logoutError));
    }
  }

  async function handleOrderLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!authenticatedCustomer) {
      setShowLogin(true);
      return;
    }
    const referenceValidationError = validateOrderReference(orderReference);
    if (referenceValidationError) {
      clearSelectedOrder();
      setLookupState("error");
      setError(referenceValidationError);
      return;
    }
    setLookupState("loading");
    setError("");
    setNotice("");
    clearSelectedOrder();
    try {
      const foundOrder = await lookupOrder(orderReference.trim());
      selectOrder(foundOrder);
      setLookupState("ready");
    } catch (lookupError) {
      if (shouldShowCustomerLoginForLookup(lookupError)) {
        setLookupState("idle");
        setNotice("We couldn’t find an available order. Sign in with the correct customer account to try again.");
        setShowLogin(true);
        return;
      }
      setOrder(null);
      setLookupState("error");
      setError(customerLookupErrorMessage(lookupError) ?? errorMessage(lookupError));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateRefundDetails(reasonCode, reason, selectedItems.length);
    if (!order || validationError) {
      setError(validationError ?? "Select an order before submitting a refund request.");
      return;
    }
    setSubmitState("submitting");
    setError("");
    setNotice("");
    const requestKey = idempotencyKey ?? crypto.randomUUID();
    setIdempotencyKey(requestKey);
    try {
      const refundResult = await createRefundRequest({
        order_reference: order.reference,
        reason_code: reasonCode,
        reason: reason.trim(),
        items: selectedItems,
      }, requestKey);
      setResult(refundResult);
      setSubmitState("success");
      setIdempotencyKey(null);
    } catch (submitError) {
      if (requiresCustomerLogin(submitError)) {
        setSubmitState("idle");
        setError("");
        setShowLogin(true);
        return;
      }
      setSubmitState("error");
      setError(errorMessage(submitError));
    }
  }

  function selectOrder(foundOrder: Order) {
    setOrder(foundOrder);
    setOrderReference(foundOrder.reference);
    setQuantities({});
    setResult(null);
    setIdempotencyKey(null);
  }

  function clearSelectedOrder() {
    const cleared = clearedOrderLookupState();
    setOrder(cleared.order);
    setQuantities(cleared.quantities);
    setReasonCode(cleared.reasonCode);
    setReason(cleared.reason);
    setResult(cleared.result);
    setIdempotencyKey(cleared.idempotencyKey);
    setSubmitState(cleared.submitState);
  }

  function clearCustomerSessionState() {
    const cleared = clearedCustomerSessionState();
    setOrder(cleared.order);
    setQuantities(cleared.quantities);
    setReasonCode(cleared.reasonCode);
    setReason(cleared.reason);
    setResult(cleared.result);
    setIdempotencyKey(cleared.idempotencyKey);
    setSubmitState(cleared.submitState);
    setCustomer(cleared.customer);
    setOrderReference(cleared.orderReference);
    setLookupEmail("");
    setLookupState(cleared.lookupState);
    setError(cleared.error);
    setNotice(cleared.notice);
  }

  function toggleItem(itemId: number, checked: boolean) {
    setQuantities((current) => {
      if (!checked) {
        const { [itemId]: _, ...remaining } = current;
        return remaining;
      }
      return { ...current, [itemId]: 1 };
    });
    setIdempotencyKey(null);
  }

  function setItemQuantity(itemId: number, quantity: number, maximum: number) {
    const safeQuantity = Math.min(Math.max(1, quantity || 1), maximum);
    setQuantities((current) => ({ ...current, [itemId]: safeQuantity }));
    setIdempotencyKey(null);
  }

  if (showLogin) {
    return (
      <CustomerLogin
        onBack={() => setShowLogin(false)}
        onAuthenticated={(customerSession) => {
          setAuthenticatedCustomer(customerSession);
          setLookupEmail(customerSession.email);
          setSessionLoading(false);
          setNotice("You are signed in. Your account is ready to look up your orders.");
          setShowLogin(false);
        }}
      />
    );
  }

  return (
    <main className="refund-page">
      <section className="refund-intro" aria-labelledby="refund-title">
        <p className="eyebrow">Worknoon order support</p>
        <h1 id="refund-title">Request a refund</h1>
        <p>Find your order, select the affected items, and we’ll apply the refund policy right away.</p>
      </section>

      {sessionLoading ? (
        <p className="loading" aria-live="polite">Checking your secure customer session…</p>
      ) : authenticatedCustomer ? (
        <CustomerIdentity customer={authenticatedCustomer} onLogout={handleLogout} />
      ) : (
        <section className="signed-out-banner" aria-live="polite">
          <div><strong>Sign in to find your orders</strong><p>Your account identity—not an email typed into this page—controls which orders are available.</p></div>
          <button type="button" onClick={() => setShowLogin(true)}>Sign in</button>
        </section>
      )}

      {authenticatedCustomer && showIdleWarning && (
        <section className="idle-session-warning" role="alert" aria-live="assertive">
          <div>
            <strong>Your session will expire soon.</strong>
            <p>Continue your session to stay signed in.</p>
          </div>
          <button type="button" onClick={() => {
            setShowIdleWarning(false);
            idleSessionRef.current?.reset();
          }}>Continue Session</button>
        </section>
      )}

      <nav className="refund-steps" aria-label="Refund request steps">
        <StepIndicator number="1" label="Find your order" active />
        <StepIndicator number="2" label="Select items" active={Boolean(order)} />
        <StepIndicator number="3" label="Tell us what happened" active={Boolean(order)} />
      </nav>

      <section className="refund-card lookup-card" aria-label="Find your order">
        <div className="card-title-row">
          <div><p className="eyebrow">Step 1</p><h2>Find your order</h2></div>
          <span className="step-number" aria-hidden="true">1</span>
        </div>
        <p className="card-description">Your signed-in account controls the orders shown here. To use another account, switch customer first.</p>
        {authenticatedCustomer ? (
          <form className="lookup-form" onSubmit={handleCustomerLookup} noValidate>
            <CustomerLookupAccount
              customer={authenticatedCustomer}
              lookupEmail={lookupEmail}
              onLookupEmailChange={setLookupEmail}
            />
            <div className="inline-form"><button type="submit" disabled={lookupState === "loading"}>Find my orders</button></div>
          </form>
        ) : (
          <p className="lookup-login-hint">Sign in to securely look up your orders.</p>
        )}

        {customer && (
          <div className="customer-orders" aria-live="polite">
            <p>Matching orders</p>
            {customer.orders.length === 0 ? <p>No orders were found for this email.</p> : (
              <ul>
                {customer.orders.map((customerOrder) => (
                  <li key={customerOrder.reference}>
                    <button type="button" className="order-choice" onClick={() => handleOrderChoice(customerOrder.reference)}>
                      <span>{customerOrder.reference}</span>
                      <span>{formatMoney(customerOrder.total_amount, customerOrder.currency)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {authenticatedCustomer && <>
          <div className="or-divider">or</div>
          <form className="lookup-form" onSubmit={handleOrderLookup} noValidate>
            <label htmlFor="order-reference">Order reference</label>
            <div className="inline-form">
              <input
                id="order-reference"
                value={orderReference}
                onChange={(event) => setOrderReference(event.target.value)}
                placeholder="ORD-1001"
                maxLength={64}
                required
              />
              <button type="submit" disabled={lookupState === "loading"}>Look up order</button>
            </div>
          </form>
        </>}
      </section>

      {error && <div className="status-message error" role="alert">{error}</div>}
      {notice && <div className="status-message success" role="status">{notice}</div>}
      {lookupState === "loading" && <p className="loading" aria-live="polite">Looking up your order…</p>}

      {order && (
        <form className="refund-card request-form" onSubmit={handleSubmit} noValidate>
          <div className="section-heading">
            <div>
              <p className="eyebrow">Step 2</p>
              <h2>Select the items that need attention</h2>
              <p>{order.reference} · {formatDate(order.ordered_at)}</p>
            </div>
            <span className="order-total">{formatMoney(order.total_amount, order.currency)}</span>
          </div>

          <fieldset className="refund-fieldset">
            <legend>Choose one or more items</legend>
            <div className="item-list">
              {order.items.map((item) => {
                const isSelected = item.id in quantities;
                return (
                  <div className={`item-row ${isSelected ? "selected" : ""}`} key={item.id}>
                    <label className="item-select">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(event) => toggleItem(item.id, event.target.checked)}
                      />
                      <span>
                        <strong>{item.product_name}</strong>
                        <small>SKU {item.sku} · {formatMoney(item.unit_price, order.currency)} each</small>
                        <small className="item-selection-hint">{isSelected ? "Selected for this request" : "Select to request a refund"}</small>
                        {item.is_final_sale && <small className="final-sale">Final sale item — refund options may be limited</small>}
                      </span>
                    </label>
                    <label className="quantity-control">
                      Quantity
                      <input
                        type="number"
                        min="1"
                        max={item.quantity}
                        value={quantities[item.id] ?? 1}
                        disabled={!isSelected}
                        onChange={(event) => setItemQuantity(item.id, Number(event.target.value), item.quantity)}
                      />
                    </label>
                  </div>
                );
              })}
            </div>
          </fieldset>

          <fieldset className="refund-fieldset details-fieldset">
            <p className="eyebrow">Step 3</p>
            <legend>Tell us what happened</legend>
            <p className="field-help">A few clear details help us review your request quickly.</p>
            <div className="form-control-group">
              <label htmlFor="reason-code">Reason</label>
              <select id="reason-code" value={reasonCode} required onChange={(event) => {
                setReasonCode(event.target.value as RefundReasonCode);
                setIdempotencyKey(null);
              }}>
                <option value="damaged">Item arrived damaged</option>
                <option value="incorrect">I received an incorrect item</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="form-control-group">
              <div className="field-label-row">
                <label htmlFor="refund-reason">Details</label>
                <span aria-live="polite">{reason.length}/4,000</span>
              </div>
              <textarea
                id="refund-reason"
                value={reason}
                maxLength={4000}
                onChange={(event) => {
                  setReason(event.target.value);
                  setIdempotencyKey(null);
                }}
                placeholder="Please describe the issue."
                rows={4}
                required
              />
            </div>
          </fieldset>

          <button className="primary-action" type="submit" disabled={submitState === "submitting" || selectedCount === 0}>
            {submitState === "submitting" ? "Checking your request…" : "Submit refund request"}
          </button>
        </form>
      )}

      {result && <CustomerRefundResult result={result} currency={order?.currency ?? "USD"} />}
    </main>
  );

  async function handleOrderChoice(reference: string) {
    if (!authenticatedCustomer) {
      setShowLogin(true);
      return;
    }
    setOrderReference(reference);
    setLookupState("loading");
    setError("");
    clearSelectedOrder();
    try {
      selectOrder(await lookupOrder(reference));
      setLookupState("ready");
    } catch (lookupError) {
      if (shouldShowCustomerLoginForLookup(lookupError)) {
        setLookupState("idle");
        setNotice("We couldn’t find an available order. Sign in with the correct customer account to try again.");
        setShowLogin(true);
        return;
      }
      setLookupState("error");
      setError(customerLookupErrorMessage(lookupError) ?? errorMessage(lookupError));
    }
  }
}

export function CustomerIdentity({
  customer,
  onLogout,
}: {
  customer: AuthenticatedCustomer;
  onLogout: () => void;
}) {
  return (
    <section className="signed-in-banner" aria-label="Authenticated customer" aria-live="polite">
      <span className="identity-status"><span className="identity-dot" aria-hidden="true" />Logged in as <strong>{customer.email}</strong></span>
      <span className="identity-separator" aria-hidden="true">·</span>
      <button type="button" className="text-button logout-button" onClick={onLogout}>Logout</button>
    </section>
  );
}

export function CustomerLookupAccount({
  customer,
  lookupEmail = customer.email,
  onLookupEmailChange,
}: {
  customer: AuthenticatedCustomer;
  lookupEmail?: string;
  onLookupEmailChange?: (email: string) => void;
}) {
  return (
    <>
      <label htmlFor="customer-email">Email for this lookup</label>
      <input
        id="customer-email"
        type="email"
        value={lookupEmail}
        onChange={onLookupEmailChange ? (event) => onLookupEmailChange(event.target.value) : undefined}
        required
        readOnly={!onLookupEmailChange}
        aria-readonly={onLookupEmailChange ? undefined : "true"}
      />
      <p className="account-lookup-note">This must match your signed-in account. Changing it never changes which customer account can access orders.</p>
    </>
  );
}

function StepIndicator({ number, label, active }: { number: string; label: string; active: boolean }) {
  return <div className={`refund-step ${active ? "active" : ""}`}><span aria-hidden="true">{number}</span><strong>{label}</strong></div>;
}

export function CustomerRefundResult({ result, currency }: { result: RefundRequestResult; currency: string }) {
  const presentation = customerRefundPresentation(result);
  const itemNames = result.items.map((item) => item.order_item.product_name).join(", ");
  return (
    <section className={`refund-card customer-result-card ${presentation.status}`} aria-live="polite">
      <div className="result-status-row">
        <span className={`result-icon ${presentation.status}`} aria-hidden="true">{presentation.status === "approved" ? "✓" : presentation.status === "denied" ? "×" : "!"}</span>
        <div><p className="eyebrow">Refund request</p><h2>{presentation.title}</h2></div>
      </div>
      <span className={`customer-status-badge ${presentation.status}`}>{presentation.statusLabel}</span>
      <p className="result-description">{presentation.explanation}</p>
      <div className="result-summary-grid">
        <div><span>Items</span><strong>{itemNames}</strong></div>
        <div><span>Requested amount</span><strong>{formatMoney(result.requested_amount, currency)}</strong></div>
        {presentation.approvedAmount && <div><span>Approved amount</span><strong>{formatMoney(presentation.approvedAmount, currency)}</strong></div>}
      </div>
      <div className="customer-item-list" aria-label="Request items">
        {result.items.map((item) => (
          <article key={item.id} className="customer-item">
            <div>
              <strong>{item.order_item.product_name}</strong>
              <p>{item.requested_quantity} requested · {formatMoney(item.requested_amount, currency)}</p>
            </div>
            <span className={`customer-status-badge item-status ${item.decision}`}>{customerItemStatus(item.decision)}</span>
          </article>
        ))}
      </div>
      <section className="next-steps" aria-labelledby="next-steps-title">
        <h3 id="next-steps-title">What happens next?</h3>
        <ul>{presentation.nextSteps.map((step) => <li key={step}>{step}</li>)}</ul>
      </section>
      <AIAssistance assistance={result.ai_assistance} />
    </section>
  );
}

export function AIAssistance({ assistance }: { assistance?: RefundRequestResult["ai_assistance"] }) {
  if (!assistance) {
    return null;
  }
  return (
    <aside className="customer-guidance" aria-label="Helpful guidance">
      <p className="eyebrow">Powered by automated assistance</p>
      {assistance.available ? (
        <>
          <h3>Helpful guidance</h3>
          <p>{assistance.customer_message || "We’ve recorded your request and will keep you updated."}</p>
          <p className="guidance-disclaimer">Automated assistance helps explain your request. The final refund outcome follows our refund and support process.</p>
        </>
      ) : (
        <><h3>Helpful guidance</h3><p>We’ve recorded your request and will keep you updated.</p><p className="guidance-disclaimer">Automated assistance is temporarily unavailable, but your request is still being handled normally.</p></>
      )}
    </aside>
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof RefundApiError) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

function formatMoney(amount: string, currency: string): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(amount));
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(value));
}
