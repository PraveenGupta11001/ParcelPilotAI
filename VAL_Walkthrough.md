# ParcelPilot Customer Support AI: System Walkthrough & Testing Guide

This comprehensive guide describes the architecture, security features, guardrails, and step-by-step walk-throughs for testing and showcasing the ParcelPilot Customer Support AI system.

---

## 1. System Architecture & Context

ParcelPilot Customer Support AI is a multi-tenant client-support orchestrator built with:
*   **Frontend**: React (Vite, TypeScript, Tailwind CSS) featuring Server-Sent Events (SSE) chat streaming, smart background polling fallback, dynamic loading/thinking indicators, and an interactive policy viewer with custom confirmation controls.
*   **Backend**: FastAPI webserver providing authentication endpoints, streaming agent loops, document management APIs, and database seeding utilities.
*   **Database**: PostgreSQL equipped with the `pgvector` extension for semantic vector similarity searches over ingested documents.
*   **AI Agent Loop**: An autonomous tool-calling workflow that fallback-loops across **Groq (Qwen)**, and **Gemini (Generative Language API)**.

---

## 2. Security, RBAC & Safety Guardrails

The application enforces strict enterprise-grade rules at both the API and query-level to prevent cross-tenant leaks and unauthorized system mutations.

### A. Role-Based Access Control (RBAC)

The system defines three roles, each mapping to exact permission boundaries:

| User Role | Workspace Scope | Allowed Action Drafts | Human-in-the-Loop Confirms |
| :--- | :--- | :--- | :--- |
| **`customer`** | Locked strictly to their `account_id` | `CANCEL_ORDER`, `ESCALATE_TICKET` | Own account's drafts only (Cannot confirm credits) |
| **`internal_support`** | Global (All accounts) | All actions (`CANCEL_ORDER`, `ESCALATE_TICKET`, `ISSUE_CREDIT`) | Approvals for credits $\le$ 1,000 INR |
| **`internal_lead`** | Global (All accounts) | All actions | Approvals for credits > 1,000 INR (Manager Override) |

### B. Action Eligibility Guardrails (Rules of Engagement)

When a state-changing action is drafted via `propose_action`, the backend verifies programmatic rules before generating a proposal:
*   **Cancellations**: Orders can only be cancelled it they have status `BOOKED`. Once an order is processed, cancellation is rejected.
*   **Service Credits (Refunds)**: 
    *   The corresponding order must show `status = "PICKED_UP"` or `"DELIVERED"`.
    *   The delay must be a **carrier fault** (`carrier_fault = True`) and must **not** be a customer fault (`customer_fault = False`).
    *   The credit amount is dynamically computed from SLA policies: standard tier gets 20% of the shipment fee (capped at 500 INR), premium tier gets 40% (capped at 1,500 INR).

---

## 3. Remote Cloud database Initialization

To make cloud database setup effortless, a unified API endpoint is provided:
*   **Endpoint**: `POST /db/initialize-and-seed`
*   **What it does**: Drops existing tables (refreshing the environment), builds new database schemas, reads and feeds baseline excel records directly, and executes vector similarity chunking for all registered PDFs.

To trigger initialization in your production deployment:
```bash
curl -X POST https://your-render-backend-url.onrender.com/db/initialize-and-seed
```

---

## 4. Manual QA Walkthrough (Demo Scenarios)

Use the following step-by-step procedures to showcase constraints, security barriers, and correct state mutations.

### Mock Credentials Baseline:
*   **Customer User (Northstar - ACCT-001)**: `northstar@parcelpilot.ai` / `password123`
*   **Customer User (LumenWorks - ACCT-002)**: `lumenworks@parcelpilot.ai` / `password123`
*   **Support Agent (Maya)**: `maya@parcelpilot.ai` / `password123`
*   **Support Lead/Manager (Rohit)**: `rohit@parcelpilot.ai` / `password123`

---

### Scenario A: Propose & Confirm Order Cancellation
1. Log in as **Northstar** (`northstar@parcelpilot.ai`).
2. Open a chat and type: *"Can you please cancel my order ORD-2001?"*
3. **Backend check**: The agent queries structured data, finds that `ORD-2001` belongs to `ACCT-001` and is in `BOOKED` status (eligible).
4. **Draft card**: The agent displays a UI proposal card: **Confirm Order Cancellation (ORD-2001)**.
5. Click **[Confirm Action]**.
6. **DB Mutation Verification**: The frontend displays a success toast. If you look at the DB, the status of `ORD-2001` is now `CANCELLED` and `cancellation_requested_at` is set.
7. Under the same chat session, write: *"Cancel my order ORD-2001 again please."*
8. **Guardrail check**: The agent responds that code-level guards block double cancellation since the order status in the database is already `CANCELLED`.

---

### Scenario B: Propose & Confirm Ticket Escalation
1. Log in as **Northstar** (`northstar@parcelpilot.ai`).
2. Open a chat and type: *"I need to escalate my billing tickets TKT-501 because shipping creation keeps failing."*
3. **Draft card**: The agent identifies `TKT-501` as belonging to `ACCT-001` and drafts an **ESCALATE_TICKET** card.
4. Click **[Confirm Action]**.
5. **DB Mutation Verification**: The ticket status changes to `ESCALATED` and a record is committed to the `escalations` audit table.

---

### Scenario C: Service Credit Proposal & Manager Protection
1. Log in as **Customer (Northstar)**.
2. Ask: *"Issue me a credit for order ORD-1002 on ticket TKT-504."*
3. **Guardrail Check**: The agent will draft a credit proposal (since `ORD-1002` is delayed and `carrier_fault` is true), but when you click **Confirm Action**, the system halts execution showing a `403 Forbidden` error: *“Access denied: Service credit issue proposals require internal support or manager authorization.”*
4. **Agent Escalation**: Log out, then log in as **Maya Support Agent** (`maya@parcelpilot.ai`).
5. Open a chat and ask to draft the credit again: *"Check credit eligibility for order ORD-1002 and issue credit on ticket TKT-504."*
6. Click **[Confirm Action]**. Since the credit amount is calculated as 300 INR (which is under Maya's support limit of 1000 INR), the action succeeds!
7. **Manager Override Limit**: Now try to issue a credit for a large shipment fee where the credit exceeds 1000 INR. Proposing this as Maya will show: **Requires Manager Approval** on the card. Trying to confirm it as Maya will block it.
8. Log in as **Rohit Lead** (`rohit@parcelpilot.ai`) to confirm the proposal. Since Rohit is an `internal_lead` role, he will be permitted to confirm the transaction.

---

### Scenario D: Tenant Isolation & Document Leak Protection (403 Test)
1. Log in as **Maya Agent**. Click the **Document Library** icon.
2. Choose **Scoping Target** as `ACCT-002 (LumenWorks)` and upload a policy file (e.g. `lumenworks_secret_policy.txt`).
3. Log out, then log in as **Customer Northstar (ACCT-001)**.
4. Open the **Document Library** viewer.
5. **Security Check**: Verify that `lumenworks_secret_policy.txt` is **not visible** in Northstar's sidebar (as their scope is restricted to `general` and `ACCT-001`).
6. Hack Check: Even if Northstar intercepts the network and directly requests `GET /uploaded-documents/lumenworks_secret_policy.txt` or `DELETE /uploaded-documents/lumenworks_secret_policy.txt`, the API intercepts the token payload, detects scope mismatch, and blocks the request with a **403 Forbidden** error.

---

## 5. Technical Test Suite Execution

A fully structured automatic Pytest harness verifies all security rules, math limits, and LLM arguments sanitization.

To execute the test suite:
```bash
# Enter the backend directory
cd backend

# Run the test suite via the virtual environment pytest
../venv/bin/pytest
```

All 28 tests must run and return `28 passed` successfully.
