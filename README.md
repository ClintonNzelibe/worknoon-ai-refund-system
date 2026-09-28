# Worknoon AI-Powered Customer Support Refund System

A containerized full-stack refund workflow for the Worknoon product challenge. Customers securely access only their own orders, submit item-level refund requests, and receive a clear result. Django's deterministic policy is authoritative; OpenAI assistance is optional, structured, and advisory only. Staff review escalated requests through a separate support workspace.

## What it demonstrates

- React customer refund experience and staff support dashboard
- Django REST API with PostgreSQL, Django session authentication, CSRF protection, and ownership-scoped customer data
- Repeatable synthetic CRM/order data: 15 customers and order scenarios
- Deterministic, item-level refund policy with audit events and idempotent submission
- Optional OpenAI Responses API integration for classification, summary, support reasoning, and customer guidance
- Human-only review of escalated items; AI can never decide or override a refund

## Architecture

```text
React customer UI / support dashboard
              |
       Vite same-origin proxy
              |
 Django REST API + session / CSRF / ownership checks
       |                 |                  |
PostgreSQL      deterministic policy     audit log
       |
optional OpenAI advisory assistance
```

The authoritative flow is:

```text
Customer request -> ownership validation -> deterministic policy
                 -> optional AI assistance -> persist/audit -> response
```

AI assistance is downstream of the policy decision. It has no write path to policy decisions or staff review actions.

## Run locally with Docker Compose

Prerequisites: Docker Desktop with Docker Compose.

1. Create a local environment file. Do not commit it.

   ```powershell
   Copy-Item .env.example .env
   ```

2. Set a unique development `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD` in `.env`.

   `OPENAI_API_KEY` is optional. Without it, the application still processes refunds normally and returns a safe AI-unavailable state.

3. Start the stack.

   ```powershell
   docker compose up --build
   ```

4. Seed the deterministic local data. The command is idempotent.

   ```powershell
   docker compose exec backend python manage.py seed_synthetic_refunds
   ```

5. Open:

   - Customer experience: <http://localhost:5173/>
   - Support dashboard: <http://localhost:5173/support>
   - Django admin: <http://localhost:8000/admin/>

## Local demo accounts

The seed command creates these synthetic `.test` customer accounts for local demonstration only. They are not production credentials and are not read from production configuration.

| Customer | Email | Password | Owned order | Scenario |
| --- | --- | --- | --- | --- |
| Avery Brooks | `avery.brooks@example.test` | `local-demo-refund-avery` | `SYN-016`, `SYN-018` | Clean approved Trail shoes; clean ineligible-other Travel mug |
| Jordan Lee | `jordan.lee@example.test` | `local-demo-refund-jordan` | `SYN-003` | Clean expired-order Desk lamp denial |
| Mina Patel | `mina.patel@example.test` | `local-demo-refund-mina` | `SYN-002` | Clean final-sale Limited edition coat denial |
| Priya Nair | `priya.nair@example.test` | `local-demo-refund-priya` | `SYN-004` | Incorrect-item Wireless headphones |
| Diego Ramos | `diego.ramos@example.test` | `local-demo-refund-diego` | `SYN-005` | $650 damaged Premium television; human review |

Each of `SYN-002`, `SYN-003`, `SYN-005`, `SYN-016`, and `SYN-018` is reset to zero refund claims by `seed_synthetic_refunds`, so it can be reused as a first-request local demo.

Create a reviewer when needed:

```powershell
docker compose exec backend python manage.py createsuperuser
```

Sign in at `/admin/`, then use `/support` in that same browser session.

## Security and customer ownership

Customer identity comes from the authenticated Django session, never from an email, customer ID, order ID, or order reference submitted by the browser.

- `GET /api/auth/session/` identifies the current linked customer session.
- `/api/customers/lookup/` and `/api/orders/<reference>/` require authentication and query only `order.customer.user == request.user` for non-staff users.
- A non-owner receives the generic response `Order not found or unavailable.` No order, item, price, customer, refund, or AI data is returned.
- Customer refund history is ownership-scoped; submitted `customer_id` and `order_reference` query parameters cannot expand it.
- Refund creation performs ownership-scoped order lookup before policy evaluation.
- The frontend shows the session identity, keeps the lookup email read-only, and clears order/request state on lookup failure or logout.

Staff users retain access through staff-protected support endpoints. Customer and staff roles are enforced server-side.

## Deterministic refund policy

The policy module has no AI dependency. It evaluates each selected item using immutable order values.

- Final-sale items: denied
- Orders older than 30 days: denied
- Eligible damaged or incorrect items: may be approved
- Refunds over $500: escalated to human review
- Suspicious or conflicting requests: escalated to human review
- Mixed requests: separate item-level outcomes with a combined request status

Only staff can resolve escalated items. Staff approval cannot overturn a hard final-sale or expired-order denial. All request creation, policy evaluation, AI availability, and human-review events are audited.

## AI assistance

Set these optional values in `.env`:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
OPENAI_TIMEOUT_SECONDS=20
```

The OpenAI integration uses the Responses API with:

- `store=False`, a bounded timeout, low reasoning effort, no retries, and bounded output
- Strict JSON-schema output for `classification`, `risk`, `summary`, `reasoning`, and `customer_message`
- Bounded trusted order/item/policy context and a separately labeled untrusted customer explanation
- Prompt-injection instructions that customer text is data, never instructions
- Validation that rejects malformed, incomplete, oversized, or truncated responses

The provider output is persisted in a dedicated `RefundAIAssistance` record. `policy_alignment` is derived by the application for staff visibility and remains advisory. Missing credentials, timeouts, rate limits, provider failures, and invalid responses produce a safe unavailable result and audit event; they never block a refund request or alter its deterministic outcome.

Customers see only customer-safe helpful guidance. Support staff can see the detailed AI classification, risk, summary, reasoning, and advisory status.

## API overview

All routes are under `/api/`.

| Method | Route | Access |
| --- | --- | --- |
| `GET` | `/auth/csrf/` | Public CSRF cookie bootstrap |
| `POST` | `/auth/login/` | Public customer login; CSRF protected |
| `GET` | `/auth/session/` | Authenticated linked customer |
| `POST` | `/auth/logout/` | Authenticated customer; CSRF protected |
| `POST` | `/auth/staff/login/` | Public staff login; CSRF protected and restricted to `is_staff=True` |
| `GET` | `/auth/staff/session/` | Authenticated staff session bootstrap after dashboard refresh |
| `GET` | `/customers/lookup/?email=<session-email>` | Authenticated owner or staff |
| `GET` | `/orders/<reference>/` | Authenticated owner or staff |
| `GET` | `/refund-requests/` | Request owner or staff |
| `POST` | `/refund-requests/` | Authenticated owner or staff |
| `GET` | `/support/refund-requests/` | Staff only |
| `GET` | `/support/refund-requests/<id>/` | Staff only |
| `POST` | `/support/refund-requests/<id>/review/` | Staff only |

Example request payload:

```json
{
  "order_reference": "SYN-001",
  "reason_code": "damaged",
  "reason": "The soles separated after delivery.",
  "items": [
    {"order_item_id": 1, "requested_quantity": 1}
  ]
}
```

`POST /api/refund-requests/` also requires an 8–64 character `Idempotency-Key` header. The server calculates requested amounts and decisions; neither is accepted from the client.

## Verification commands

```powershell
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py test
docker compose exec frontend npm test -- --run
docker compose exec frontend npm run build
docker compose config --quiet
```

The automated suite covers policy rules, ownership isolation, session authentication and CSRF, idempotency, customer history, AI normal/failure/truncation/prompt-injection cases, audit behavior, support review boundaries, and frontend customer/support behavior.

## Suggested video walkthrough

1. Run Compose and seed the data.
2. Sign in as Avery; look up `SYN-016`; submit a damaged-item request; show the approved customer result and helpful guidance.
3. Sign out, sign in as Diego; show `SYN-005` is available and `SYN-004` returns the generic unavailable response.
4. Submit Diego's $650 damaged-TV request; show the customer-facing “Needs a quick review” state.
5. Sign in as staff at Django admin; open `/support`; inspect the advisory AI details and audit trail; record a human review decision.
6. Return to Diego’s customer page; show polling updates the resolved result without resubmission.
7. Briefly show `.env.example` and explain that removing `OPENAI_API_KEY` leaves deterministic processing intact.

## Trade-offs

- The project deliberately uses a small direct OpenAI client integration instead of an agent framework. The workflow has one bounded advisory task, so additional orchestration would not improve policy safety.
- Customer order data is private. A login is required before lookup because an entered email cannot prove ownership.
- AI calls are synchronous and deliberately bounded for this assessment. A production system could move advisory generation to a durable background queue while retaining the same safe unavailable fallback.

## Demo Video

[Watch the Worknoon AI Refund System Demo] https://drive.google.com/file/d/1WSwDK4515ueEd7ZRUoSgONpNeCLWBjvS/view?usp=sharing