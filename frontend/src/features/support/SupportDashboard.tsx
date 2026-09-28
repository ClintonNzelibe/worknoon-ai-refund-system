import { FormEvent, useEffect, useState } from "react";

import { RefundApiError } from "../refunds/refund.api";
import type { SupportRefundPage, SupportRefundRequest } from "../refunds/types";
import {
  getSupportRefund,
  getSupportSession,
  listSupportRefunds,
  reviewSupportRefund,
  type SupportFilters,
} from "./support.api";
import { SupportLogin } from "./SupportLogin";
import type { AuthenticatedSupportUser } from "./support.api";

const emptyPage: SupportRefundPage = {
  count: 0,
  page: 1,
  page_size: 10,
  total_pages: 0,
  results: [],
};

export function SupportDashboard() {
  const [pageData, setPageData] = useState<SupportRefundPage>(emptyPage);
  const [filters, setFilters] = useState<SupportFilters>({ page: 1 });
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<SupportRefundRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [reviewDecision, setReviewDecision] = useState<"approved" | "rejected">("approved");
  const [reviewNote, setReviewNote] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [staffUser, setStaffUser] = useState<AuthenticatedSupportUser | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void getSupportSession()
      .then((user) => { if (!cancelled) setStaffUser(user); })
      .catch(() => { if (!cancelled) setStaffUser(null); })
      .finally(() => { if (!cancelled) setSessionLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!staffUser) return;
    void loadPage(filters);
  }, [filters, staffUser?.username]);

  async function loadPage(nextFilters: SupportFilters) {
    setLoading(true);
    setError("");
    try {
      setPageData(await listSupportRefunds(nextFilters));
    } catch (requestError) {
      if (requestError instanceof RefundApiError && requestError.status === 403) {
        setStaffUser(null);
        return;
      }
      setError(errorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelected(null);
    setFilters({
      page: 1,
      status: statusFilter || undefined,
      customerEmail: search.includes("@") ? search : undefined,
      orderReference: search.includes("@") ? undefined : search || undefined,
    });
  }

  async function selectRefund(refundRequestId: number) {
    setDetailLoading(true);
    setError("");
    try {
      setSelected(await getSupportRefund(refundRequestId));
      setReviewNote("");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setDetailLoading(false);
    }
  }

  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !reviewNote.trim()) {
      setError("A review note is required before submitting a human decision.");
      return;
    }
    setReviewing(true);
    setError("");
    try {
      const updatedRequest = await reviewSupportRefund(
        selected.id,
        reviewDecision,
        reviewNote.trim(),
      );
      setSelected(updatedRequest);
      setReviewNote("");
      await loadPage(filters);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setReviewing(false);
    }
  }

  if (sessionLoading) {
    return <main className="support-page"><p className="loading" aria-live="polite">Checking your support session…</p></main>;
  }

  if (!staffUser) {
    return <SupportLogin onAuthenticated={setStaffUser} />;
  }

  return (
    <main className="support-page">
      <header className="support-header">
        <div>
          <p className="eyebrow">Support workspace</p>
          <h1>Refund review queue</h1>
          <p>Signed in as <strong>{staffUser.username}</strong> · Policy decisions are authoritative. Human review is available only for escalated items.</p>
        </div>
        <a href="/" className="customer-link">Customer experience</a>
      </header>

      <form className="support-filters" onSubmit={applyFilters}>
        <label>
          Status
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">All statuses</option>
            <option value="escalated">Escalated</option>
            <option value="approved">Approved</option>
            <option value="rejected">Denied</option>
            <option value="pending">Pending</option>
          </select>
        </label>
        <label>
          Customer email or order reference
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="ORD-1001 or customer@example.com" />
        </label>
        <button type="submit">Apply filters</button>
      </form>

      {error && <div className="status-message error" role="alert">{error}</div>}
      {loading && <p className="loading" aria-live="polite">Loading refund requests…</p>}

      <section className="support-layout">
        <section className="support-card queue-card" aria-label="Refund request list">
          <div className="queue-heading">
            <h2>Recent requests</h2>
            <span>{pageData.count} total</span>
          </div>
          {!loading && pageData.results.length === 0 && <p>No refund requests match these filters.</p>}
          <div className="support-request-list">
            {pageData.results.map((refundRequest) => (
              <button
                type="button"
                className={`support-request ${selected?.id === refundRequest.id ? "selected" : ""}`}
                key={refundRequest.id}
                onClick={() => void selectRefund(refundRequest.id)}
              >
                <span className="support-request-topline">
                  <strong>{refundRequest.order_reference}</strong>
                  <StatusBadge status={refundRequest.status} />
                </span>
                <span>{refundRequest.customer_name} · {formatMoney(refundRequest.requested_amount, refundRequest.currency)}</span>
                <small>{formatDate(refundRequest.created_at)}</small>
              </button>
            ))}
          </div>
          <Pagination pageData={pageData} onPageChange={(page) => setFilters({ ...filters, page })} />
        </section>

        <section className="support-card detail-card" aria-label="Refund request detail">
          {detailLoading && <p className="loading">Loading request detail…</p>}
          {!detailLoading && !selected && <p>Select a request to inspect policy reasons, audit history, and any AI assistance.</p>}
          {selected && (
            <RefundDetail
              refundRequest={selected}
              reviewDecision={reviewDecision}
              reviewNote={reviewNote}
              reviewing={reviewing}
              onDecisionChange={setReviewDecision}
              onNoteChange={setReviewNote}
              onSubmitReview={submitReview}
            />
          )}
        </section>
      </section>
    </main>
  );
}

function RefundDetail({
  refundRequest,
  reviewDecision,
  reviewNote,
  reviewing,
  onDecisionChange,
  onNoteChange,
  onSubmitReview,
}: {
  refundRequest: SupportRefundRequest;
  reviewDecision: "approved" | "rejected";
  reviewNote: string;
  reviewing: boolean;
  onDecisionChange: (decision: "approved" | "rejected") => void;
  onNoteChange: (note: string) => void;
  onSubmitReview: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <>
      <div className="detail-heading">
        <div>
          <p className="eyebrow">{refundRequest.order_reference}</p>
          <h2>{refundRequest.customer_name}</h2>
          <p>{refundRequest.customer_email} · {formatMoney(refundRequest.requested_amount, refundRequest.currency)}</p>
        </div>
        <StatusBadge status={refundRequest.status} />
      </div>
      <p className="customer-reason"><strong>Customer reason:</strong> {refundRequest.reason}</p>
      <p className="policy-note"><strong>Authoritative policy:</strong> {refundRequest.resolution_note}</p>

      <h3>Item-level decisions</h3>
      <div className="support-items">
        {refundRequest.items.map((item) => (
          <article key={item.id}>
            <div>
              <strong>{item.order_item.product_name}</strong>
              <small>{item.requested_quantity} requested · {formatMoney(item.requested_amount, refundRequest.currency)}</small>
            </div>
            <div>
              <StatusBadge status={item.decision} />
              <p>{item.decision_reason}</p>
            </div>
          </article>
        ))}
      </div>

      <AIAssistance assistance={refundRequest.ai_assistance} />
      <AuditTrail auditLogs={refundRequest.audit_logs} />

      {refundRequest.status === "escalated" && (
        <form className="review-form" onSubmit={onSubmitReview}>
          <h3>Human review</h3>
          <p>Only items escalated by policy will be resolved. Hard policy denials stay unchanged.</p>
          <label>
            Decision
            <select value={reviewDecision} onChange={(event) => onDecisionChange(event.target.value as "approved" | "rejected")}> 
              <option value="approved">Approve escalated items</option>
              <option value="rejected">Deny escalated items</option>
            </select>
          </label>
          <label>
            Review note
            <textarea value={reviewNote} onChange={(event) => onNoteChange(event.target.value)} rows={3} maxLength={1000} required />
          </label>
          <button type="submit" disabled={reviewing}>{reviewing ? "Recording review…" : "Record human decision"}</button>
        </form>
      )}
    </>
  );
}

function AIAssistance({ assistance }: { assistance?: SupportRefundRequest["ai_assistance"] }) {
  return (
    <section className="ai-assistance">
      <p className="eyebrow">AI assistance — advisory</p>
      {assistance?.available ? (
        <>
          <p><strong>Classification:</strong> {assistance.classification} &middot; <strong>Risk:</strong> {assistance.risk}</p>
          <p><strong>Claim summary:</strong> {assistance.summary}</p>
          <p><strong>Support reasoning:</strong> {assistance.reasoning}</p>
          {assistance.policy_alignment === "concern" && <p><strong>AI flagged a concern.</strong> The deterministic decision still remains authoritative.</p>}
          <small>AI assistance is supplementary and cannot change the policy result.</small>
        </>
      ) : (
        <p>{assistance?.message ?? "No AI assistance is available for this request."}</p>
      )}
    </section>
  );
}

function AuditTrail({ auditLogs }: { auditLogs: SupportRefundRequest["audit_logs"] }) {
  return (
    <section className="audit-trail">
      <h3>Audit trail</h3>
      {auditLogs.length === 0 ? <p>No audit entries yet.</p> : (
        <ol>
          {auditLogs.map((log) => <li key={log.id}><strong>{log.action.replaceAll("_", " ")}</strong><span>{log.message || "System event"} · {formatDate(log.created_at)}</span></li>)}
        </ol>
      )}
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  const label = status === "rejected" ? "Denied" : status;
  return <span className={`decision-badge ${status}`}>{label}</span>;
}

function Pagination({ pageData, onPageChange }: { pageData: SupportRefundPage; onPageChange: (page: number) => void }) {
  if (pageData.total_pages <= 1) return null;
  return (
    <nav className="pagination" aria-label="Refund request pages">
      <button type="button" disabled={pageData.page === 1} onClick={() => onPageChange(pageData.page - 1)}>Previous</button>
      <span>Page {pageData.page} of {pageData.total_pages}</span>
      <button type="button" disabled={pageData.page === pageData.total_pages} onClick={() => onPageChange(pageData.page + 1)}>Next</button>
    </nav>
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof RefundApiError) return error.message;
  return "The support dashboard could not complete that request.";
}

function formatMoney(amount: string, currency: string): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(amount));
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
