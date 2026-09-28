# Architecture

## Purpose

The application processes item-level refund requests while keeping business decisions predictable, auditable, and independent from optional AI assistance.

## Components and responsibilities

| Component | Responsibility |
| --- | --- |
| React/Vite frontend | Customer submission flow and staff support dashboard. It displays server results but never determines a refund outcome. |
| Django REST API | Authenticates requests, enforces customer/staff object access, validates input, coordinates persistence, and returns safe errors. |
| Deterministic policy engine | Calculates item-level policy outcomes from orders, items, reason, quantity, age, and conflict signals. It is the sole authority for approval, denial, and escalation. |
| AI service | Optional advisory classification, explanation, and customer-response generation. It receives constrained context and cannot write decisions or call tools. |
| PostgreSQL | Runtime persistence for customers, orders, request items, idempotency keys, human reviews, and audit logs. |

## Request flow

```
Customer UI
  -> authenticated API request with Idempotency-Key
  -> ownership, order, item, and quantity validation
  -> server-side amount calculation
  -> deterministic item-level policy evaluation
  -> RefundRequest, RefundRequestItem, and AuditLog persistence
  -> optional advisory AI response
  -> UI renders authoritative policy result separately from AI assistance
```

For a request containing mixed items, each requested item receives its own decision and reason list. The overall request status summarizes those item decisions; it does not erase hard denials.

An escalated case follows a separate path:

```
Support user (is_staff)
  -> support detail endpoint
  -> review only policy-escalated items
  -> record human decision and audit event
  -> return updated request and audit history
```

Human review does not turn final-sale or expired-item denials into approvals. The dashboard cannot bypass the policy engine's hard constraints.

## Data model

```
User 0..1 <-> 0..1 Customer 1 -> * Order 1 -> * OrderItem
                                      |
                                      v
                              RefundRequest 1 -> * RefundRequestItem
                                      |
                                      +--> 0..1 RefundAIAssistance
                                      |
                                      v
                                   AuditLog
```

`Customer.user` is optional so synthetic and support-managed records can exist without a browser login. When it is populated, customer endpoints scope access to that user. Staff users may access support data under the dedicated staff permission.

Orders and items are the source of truth for prices and quantities. The client submits identifiers and requested quantities only; it never submits an authoritative amount, item price, or policy status.

## Policy boundary

The policy engine uses a 30-day refund window and evaluates rules consistently at the item level:

- Final-sale items and expired orders are hard denials.
- Eligible damaged or incorrect items can be approved.
- Refund value above $500 and suspicious or conflicting requests are escalated.
- Invalid quantities and cross-order item references are rejected before policy evaluation.

The complete rule set is in [REFUND_POLICY.md](REFUND_POLICY.md). Policy results, human review events, and material request actions are audit logged.

## AI boundary

AI is intentionally downstream from the policy decision. It can describe a request but cannot choose a result, invoke a tool, mutate a model, or provide a policy override. Customer notes are treated as untrusted input and are delimited as data in the prompt. The AI client uses a fixed output schema, bounded context, short timeout, no retries, no provider-side storage, and safe fallback handling.

No response exposes an API key, internal prompt, or provider error body. A missing or failing AI provider only removes advisory content; it never prevents a deterministic refund decision.

## Security boundaries

- Every API route requires authentication.
- Customer order and refund-request access is object-scoped through `Customer.user`.
- Support routes require Django `is_staff` and are separate from customer routes.
- Idempotency keys prevent duplicate request creation caused by retrying the same submission.
- Server-side serializers validate order membership, quantities, and status transitions.
- The configured CORS/CSRF allowlists support the local Compose frontend and should be narrowed for a deployed domain.
- Audit rows capture request decisions and staff review actions for investigation.

## Runtime topology

`compose.yaml` runs three services on a private Compose network:

- `db`: PostgreSQL with a health check.
- `backend`: waits for the database health condition, applies migrations, then starts Django.
- `frontend`: Vite, serving the React UI and proxying `/api` and `/admin` requests to Django.

Credentials are supplied through environment variables, with placeholders documented in [`.env.example`](.env.example). The backend image includes the PostgreSQL driver for container runtime; the test settings use SQLite to keep the isolated Django test suite fast and reproducible.

## Deliberate prototype trade-offs

- Authentication relies on Django sessions. The customer UI supports login only for an existing `Customer.user` link; self-service registration and account recovery remain outside this prototype. The synthetic seed command provisions two local-only linked demo accounts, while other links can be provisioned in Django admin.
- AI assistance is generated on demand and is not stored as a decision record, because it is non-authoritative.
- The frontend is purposefully small and focuses on validation states and decision clarity instead of a design system.
- Docker Compose is the supported end-to-end runtime. Host-only tests may use SQLite when PostgreSQL tooling is unavailable.
