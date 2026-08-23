# Developer Testing, Troubleshooting, and Architecture Guide (`dev_tests_reads.md`)

This guide captures major troubleshooting flows, setup guidelines, system architecture reviews, security constraints, and resolution summaries for the modernized **ParcelPilot Customer Support AI** system.

---

## 1. Project Requirements & Video Demonstration

### Demo Video Specifications
Submit a video of approximately 5 minutes covering:
*   **The solution architecture** (FastAPI, React + TypeScript + Tailwind v4, PostgreSQL/pgvector).
*   **A demonstration of the working application** (role switching, live chat streaming, proposing and executing/rejecting actions, multi-tenant scoped library).
*   **Important product or technical decisions** you made, along with the rationale.

### Example Requests & Reasoning Scenarios
The system is built to dynamically load and reason over custom data rather than hard-coding IDs or responses. Key scenarios tested include:
1.  **Can Northstar cancel ORD-1001 without a cancellation fee? Explain why.**
    *   *System Answer*: Yes, because the Northstar Logistics Enterprise Contract (Level 1 authority) explicitly waives all cancellation fees for booked shipments.
2.  **A pickup is three hours late because of carrier fault. Should I get a service credit?**
    *   *System Answer*: Under the default policy, a 3-hour late pickup does not qualify for a credit (requires >=4 hours or specific tier thresholds). Dynamic checks calculate this based on the active client contract.

### Two Additional Client Problems Addressed
#### Problem 1: Proactive Issue Detection
Rather than relying purely on reactive chat requests, the internal manager/operations view computes active operational signals:
*   **SLA breaches and warnings** countdown trackers.
*   **Delayed pickups** detection (e.g. carrier missed pickups).
*   **Unassigned ticket** logs requiring urgent attention.
*   **Carrier performance scorecards** calculating fault rates dynamically.

#### Problem 2: Trust and Reliability (Authority Hierarchy & Conflict Resolution)
To deal with policy updates and conflicts, the AI Orchestration layer enforces **Strict Authority Level Precedence**:
*   *Level 1*: Signed Customer Contracts/Agreements (e.g. Northstar, LumenWorks) override standard company policies.
*   *Level 2*: Current Active SOPs (e.g. Support Policy v3, Cancellation Refund SOP v4).
*   *Level 3*: General manuals (e.g. Product Operations Playbook v1).
*   *Level 4*: Deprecated policies (e.g. Support Policy v2) – explicitly filtered out from vector searches.
*   *Level 5*: Historical resolution logs.
Also, the **Propose-Confirm Flow** provides a Human-in-the-Loop review checkpoint for sensitive state mutations (like credits and cancellations) before applying changes directly to production database rows.

---

## 2. Developer Setup Guidelines

### Method A: Orchestrated Container Launch (Docker Compose)
Launch the entire system (Database, Backend API, and Frontend) in an isolated container network:

1. **Build and start services**:
   ```bash
   docker-compose up --build
   ```
2. **Initialize Database Schema and Seed Data**:
   With the containers running, seed the PostgreSQL database (the `backend` container is configured to wait until the database is ready):
   ```bash
   # Enter the backend container shell
   docker exec -it parcelpilot_backend bash

   # Seed relational registers
   PYTHONPATH=. python app/db/seed.py

   # Ingest and index PDF policy documents
   PYTHONPATH=. python app/ingestion/parse_pdfs.py
   ```
3. **Verify running containers**:
   - Backend API: `http://localhost:8000/docs` (Swagger Interactive API Documentation)
   - Frontend Portal: `http://localhost:5173/`

### Method B: Manual Developer Execution (Local System)
If you prefer running services directly on your host machine:

#### 1. Database Service
Ensure docker volume container for postgres/pgvector is running:
```bash
docker-compose up -d db
```

#### 2. Backend Environment
1. Navigate to the backend directory and set up a virtual environment:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run database migration and seeding tasks:
   ```bash
   PYTHONPATH=. python app/db/seed.py
   PYTHONPATH=. python app/ingestion/parse_pdfs.py
   ```
3. Launch uvicorn developer webserver:
   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```

#### 3. Frontend Setup
1. Navigate to frontend directory and install modules:
   ```bash
   cd ../frontend
   npm install
   ```
2. Start the Vite React development server:
   ```bash
   npm run dev
   ```
3. Interact with the UI portal at `http://localhost:5173/`.

#### 4. Technical Verification & Pytests
To execute the backend service integration test suite:
```bash
cd backend
source venv/bin/activate
PYTHONPATH=. pytest tests/
```

---

## 3. System Architecture & System Walkthrough

### System Architecture & Context
ParcelPilot Customer Support AI is a multi-tenant client-support orchestrator built with:
*   **Frontend**: React (Vite, TypeScript, Tailwind CSS) featuring Server-Sent Events (SSE) chat streaming, smart background polling fallback, dynamic loading/thinking indicators, and an interactive policy viewer with custom confirmation controls.
*   **Backend**: FastAPI webserver providing authentication endpoints, streaming agent loops, document management APIs, and database seeding utilities.
*   **Database**: PostgreSQL equipped with the `pgvector` extension for semantic vector similarity searches over ingested documents.
*   **AI Agent Loop**: An autonomous tool-calling workflow that fallback-loops across **Groq (Qwen)**, and **Gemini (Generative Language API)**.

### Security, RBAC & Safety Guardrails
The application enforces strict enterprise-grade rules at both the API and query-level to prevent cross-tenant leaks and unauthorized system mutations.

#### A. Role-Based Access Control (RBAC)
The system defines three roles, each mapping to exact permission boundaries:

| User Role | Workspace Scope | Allowed Action Drafts | Human-in-the-Loop Confirms |
| :--- | :--- | :--- | :--- |
| **`customer`** | Locked strictly to their `account_id` | `CANCEL_ORDER`, `ESCALATE_TICKET` | Own account's drafts only (Cannot confirm credits) |
| **`internal_support`** | Global (All accounts) | All actions (`CANCEL_ORDER`, `ESCALATE_TICKET`, `ISSUE_CREDIT`) | Approvals for credits $\le$ 1,000 INR |
| **`internal_lead`** | Global (All accounts) | All actions | Approvals for credits > 1,000 INR (Manager Override) |

#### B. Action Eligibility Guardrails (Rules of Engagement)
When a state-changing action is drafted via `propose_action`, the backend verifies programmatic rules before generating a proposal:
*   **Cancellations**: Orders can only be cancelled it they have status `BOOKED`. Once an order is processed, cancellation is rejected.
*   **Service Credits (Refunds)**: 
    *   The corresponding order must show `status = "PICKED_UP"` or `"DELIVERED"`.
    *   The delay must be a **carrier fault** (`carrier_fault = True`) and must **not** be a customer fault (`customer_fault = False`).
    *   The credit amount is dynamically computed from SLA policies: standard tier gets 20% of the shipment fee (capped at 500 INR), premium tier gets 40% (capped at 1,500 INR).

### Remote Cloud database Initialization
To make cloud database setup effortless, a unified API endpoint is provided:
*   **Endpoint**: `POST /db/initialize-and-seed`
*   **What it does**: Drops existing tables (refreshing the environment), builds new database schemas, reads and feeds baseline excel records directly, and executes vector similarity chunking for all registered PDFs.

To trigger initialization in your production deployment:
```bash
curl -X POST https://your-render-backend-url.onrender.com/db/initialize-and-seed
```

### Manual QA Walkthrough (Demo Scenarios)
Use the following step-by-step procedures to showcase constraints, security barriers, and correct state mutations.

#### Mock Credentials Baseline:
*   **Customer User (Northstar - ACCT-001)**: `northstar@parcelpilot.ai` / `password123`
*   **Customer User (LumenWorks - ACCT-002)**: `lumenworks@parcelpilot.ai` / `password123`
*   **Support Agent (Maya)**: `maya@parcelpilot.ai` / `password123`
*   **Support Lead/Manager (Rohit)**: `rohit@parcelpilot.ai` / `password123`

#### Scenario A: Propose & Confirm Order Cancellation
1. Log in as **Northstar** (`northstar@parcelpilot.ai`).
2. Open a chat and type: *"Can you please cancel my order ORD-2001?"*
3. **Backend check**: The agent queries structured data, finds that `ORD-2001` belongs to `ACCT-001` and is in `BOOKED` status (eligible).
4. **Draft card**: The agent displays a UI proposal card: **Confirm Order Cancellation (ORD-2001)**.
5. Click **[Confirm Action]**.
6. **DB Mutation Verification**: The frontend displays a success toast. If you look at the DB, the status of `ORD-2001` is now `CANCELLED` and `cancellation_requested_at` is set.
7. Under the same chat session, write: *"Cancel my order ORD-2001 again please."*
8. **Guardrail check**: The agent responds that code-level guards block double cancellation since the order status in the database is already `CANCELLED`.

#### Scenario B: Propose & Confirm Ticket Escalation
1. Log in as **Northstar** (`northstar@parcelpilot.ai`).
2. Open a chat and type: *"I need to escalate my billing tickets TKT-501 because shipping creation keeps failing."*
3. **Draft card**: The agent identifies `TKT-501` as belonging to `ACCT-001` and drafts an **ESCALATE_TICKET** card.
4. Click **[Confirm Action]**.
5. **DB Mutation Verification**: The ticket status changes to `ESCALATED` and a record is committed to the `escalations` audit table.

#### Scenario C: Service Credit Proposal & Manager Protection
1. Log in as **Customer (Northstar)**.
2. Ask: *"Issue me a credit for order ORD-1002 on ticket TKT-504."*
3. **Guardrail Check**: The agent will draft a credit proposal (since `ORD-1002` is delayed and `carrier_fault` is true), but when you click **Confirm Action**, the system halts execution showing a `403 Forbidden` error: *“Access denied: Service credit issue proposals require internal support or manager authorization.”*
4. **Agent Escalation**: Log out, then log in as **Maya Support Agent** (`maya@parcelpilot.ai`).
5. Open a chat and ask to draft the credit again: *"Check credit eligibility for order ORD-1002 and issue credit on ticket TKT-504."*
6. Click **[Confirm Action]**. Since the credit amount is calculated as 300 INR (which is under Maya's support limit of 1000 INR), the action succeeds!
7. **Manager Override Limit**: Now try to issue a credit for a large shipment fee where the credit exceeds 1000 INR. Proposing this as Maya will show: **Requires Manager Approval** on the card. Trying to confirm it as Maya will block it.
8. Log in as **Rohit Lead** (`rohit@parcelpilot.ai`) to confirm the proposal. Since Rohit is an `internal_lead` role, he will be permitted to confirm the transaction.

#### Scenario D: Tenant Isolation & Document Leak Protection (403 Test)
1. Log in as **Maya Agent**. Click the **Document Library** icon.
2. Choose **Scoping Target** as `ACCT-002 (LumenWorks)` and upload a policy file (e.g. `lumenworks_secret_policy.txt`).
3. Log out, then log in as **Customer Northstar (ACCT-001)**.
4. Open the **Document Library** viewer.
5. **Security Check**: Verify that `lumenworks_secret_policy.txt` is **not visible** in Northstar's sidebar (as their scope is restricted to `general` and `ACCT-001`).
6. Hack Check: Even if Northstar intercepts the network and directly requests `GET /uploaded-documents/lumenworks_secret_policy.txt` or `DELETE /uploaded-documents/lumenworks_secret_policy.txt`, the API intercepts the token payload, detects scope mismatch, and blocks the request with a **403 Forbidden** error.

---

## 4. Troubleshooting Case Studies (Errors, Root Causes, and Resolutions)

### Case 1: Frontend State Synchronization & SSE Race Conditions
*   **Symptom**: On creating a new chat session, the initial user message is duplicated inside the chat history database. At the same time, the streaming assistant response panel temporarily loads but vanishes from the UI before completion.
*   **Root Cause**: When the frontend posts the initial message of a chat session, the backend creates a session ID and returns a `session_created` SSE event. In the React `ChatPanel.tsx`, receiving `session_created` calls `setActiveSessionId(newSId)` to change the URL context and select the active item in the sidebar. A `useEffect` hook listening to changes in `activeSessionId` instantly fires a background database fetch `/chat/sessions/{id}/messages`. Since the database has already written the user query message but hasn't finalized the streaming answer generator task, the API returns only the user's message, overwriting the active React state, and truncating the streaming message.
*   **Resolution**: Introduce a React `useRef` blocker (`isCreatingSessionRef`) that flags the current session creation action so the background loader skips fetching on initial session redirection.

### Case 2: Empty Vector Database (pgvector) after Seeding
*   **Symptom**: The customer agent executes successfully and registers traces in the browser console, but outputs an empty list (`[]`) and fails to fetch reference policy matches or cancellation details.
*   **Root Cause**: Calling `python -m app.db.seed` recreates all database tables. While this seeds baseline Excel records (users, orders, tickets), it truncates the `document_chunks` table to zero. The policy PDFs are not re-embedded or written back during seeding.
*   **Resolution**: Run the parse/ingester Python script to rebuild the document database index after every database reset:
    `python -m app.ingestion.parse_pdfs`

### Case 3: Strict API Validation for Assistant Tool Calls (OpenAI/Groq/Gemini Coexistence)
*   **Symptom**: LLMs return empty response content (`""`) or complete with zero message tokens immediately after executing intermediate tool actions.
*   **Root Cause**: When appending past assistant choices that initiated tool calls to the history context, replacing a `None` content value with an empty string `""` causes API validation checks on strict OpenAI compatibility layers (like Groq) to fail or ignore generation. Assistant messages holding `tool_calls` require content to be exactly `None` / `null`.
*   **Resolution**: Retain the exact object values (`content: assistant_msg.content`) instead of falling back to default empty strings.

### Case 4: Playwright Browser Automation Driver Failures (404 Mirror Error)
*   **Symptom**: Running automated browser scenarios via tools like `browser_subagent` yields environment crashes matching `non 200 status code: 404 from playwright.azureedge.net/builds/driver/playwright-1.50.1-linux.zip`.
*   **Root Cause**: The default regional CDN mirror where Playwright retrieves binary drivers experiences down-times or returns 404 links, preventing automatic installation of sandbox contexts.
*   **Resolution**: Verify routes and token operations manually using browser console. Build the application (`tsc -b && vite build`) to confirm TypeScript code compiles without syntax errors before deployment.

### Case 5: TypeScript Unused Variable Warnings (`App.tsx`)
*   **Symptom**: Build commands fail or issue warnings with: `App.tsx: 'refreshToken' is declared but its value is never read.`
*   **Root Cause**: The state variable `refreshToken` is defined for future UI configurations but not read in the component.
*   **Resolution**: Destructure only the dispatcher method to avoid compiler errors:
    `const [, setRefreshToken] = useState<string | null>(localStorage.getItem('refresh_token'));`

### Case 6: Truncated Responses from Reasoning Models (`max_tokens` Cap)
*   **Symptom**: The AI agent makes diagnostic tool calls successfully but yields an empty string (`""`) for the final text response block without throwing exceptions.
*   **Root Cause**: Under modern reasoning models (like deep reasoning systems mapped on Groq/Qwen), a significant token budget is consumed inside the thinking phase. Capping `max_tokens` at `800` causes completion threads to trigger `finish_reason: length` before writing any actual user content.
*   **Resolution**: Enlarge the completion buffer size from `800` to `4096` in the orchestration loops.

### Case 7: Gemini API Legacy Model Catalog Error (404 v1main)
*   **Symptom**: Falling back to Gemini Backup raises a `404 - models/gemini-1.5-flash is not found for API version v1main` exception.
*   **Root Cause**: The legacy model `gemini-1.5-flash` has been deprecated or restricted for the API key in use, which causes Google's gateway to fail.
*   **Resolution**: Migrate the fallback configurations in `orchestration.py` to target the active model choice `gemini-2.5-flash` instead.

### Case 8: Aborted SSE Connections on First Chat Message (Session Creation Router Unmount)
*   **Symptom**: On creating a brand new chat session, sending the first message creates the session ID dynamically and redirects, but the UI goes completely blank for the assistant response. The user must re-submit the message.
*   **Root Cause**: Initially, the `/chat` route (for blank inputs) and `/chat/:chatId` route (for loaded sessions) rendered separate route definitions. When the backend yielded the `session_created` event, the UI updated the active session ID, causing React Router to unmount the initial `ChatPanel` instance and mount a fresh `ChatPanelWrapper` instance. This unmounting immediately aborted the active fetch stream and cut off the SSE reader before the assistant could render the response.
*   **Resolution**: Consolidate the split URL paths into a single optional parameter route in `App.tsx`:
    `<Route path="/chat/:chatId?" element={<ChatPanelWrapper />} />`

### Case 9: False Positives in Live Tool Execution Status (RAG Content Collisions)
*   **Symptom**: RAG documents searches (`search_documents`) execute successfully and return target policy content, but the UI component marks them as `FAILED` (colored in red).
*   **Root Cause**: The matching logic check `tc.output.toLowerCase().includes('fail')` was too greedy. Successful search outputs containing words like "failed-pickup", "failure", or "fail" (which frequently display within cancellation terms) triggered a false-positive failure state.
*   **Resolution**: Replace substring checking with robust JSON-structure verification in `ChatPanel.tsx` using `JSON.parse` to look for keys like `error`.

### Case 10: Adding Document Metadata Utilities (`get_document_count` & `list_all_documents`)
*   **Requirement**: Add tools to query the status and names of all active policies or agreements so the agent can accurately answer user queries such as: *How many docs do you have?* or *List all policies*.
*   **Implementation & Tenant Security**: Registered `get_document_count` and `list_all_documents` in `registry.py` and implemented in `document_info.py`. Both tools enforce the exact same isolation rules as RAG searches. If the user role is `customer`, they can only see general-scoped policies and those belonging to their `account_id`; other entries (like other customer agreements) are filtered out at the SQL compilation level. Internal operators maintain universal visibility.

### Case 11: Deprecation Warning Cleanup: Transitioning `utcnow` to Timezone-Aware UTC
*   **Symptom**: Running unit tests outputted multiple Python DeprecationWarnings warning of future removal of `datetime.datetime.utcnow()` from standard library versions.
*   **Root Cause**: SQLAlchemy schemas in `models.py` and token generator algorithms in `auth/jwt.py` relied on timezone-naive `datetime.utcnow()` calls.
*   **Resolution**: Migrate all application implementations to timezone-aware UTC format:
    `Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC))`

### Case 12: Input Focus, Ref forwarding, and Branded Empty State Layout
*   **Requirement**: Automatically focus on email input on login layout mount, focus message input box on chat panel mount or session switches, and return focus to message input immediately when message sending completes. Ensure input box is disabled during transaction proposals or message streaming. Display the logo in the EmptyState.
*   **Implementation**: Used `React.forwardRef<HTMLInputElement>` on the text input component. Added focus hooks using a `setTimeout` of 60ms to let reactive browser rendering update before the native focus action. Integrated the `parcelPilotLogo` brand image inside the chatEmptyState.

### Case 13: Migrating Chat Session IDs from Autoincrement Integers to UUID Strings
*   **Requirement**: Transition the chat session identifiers from incremental integers (e.g. `1`, `2`, `3`) to globally unique uuid strings.
*   **Implementation**: Modified `ChatSession.id` to a string of size 36, automatically initialized via `uuid.uuid4()`. Updated `ChatMessage.session_id` to refer to string size 36 foreign key. Updated Pydantic schemas, endpoints, tests (`test_chat_endpoint.py`), and client React models / React Router path configs.

---

## 5. Domain-Specific Component Walkthroughs

### A. Agentic AI & Reliability Engine
The system uses Anthropic's Claude messages model (or options fallback pool like Groq or Gemini) to perform agent orchestration.
*   **The Loop Control Pattern**:
    1.  **State Init**: Agent takes current user message + chat history context.
    2.  **Tool registry declaration**: Defines available tools (`search_documents`, `query_structured_data`, `propose_action`, etc.).
    3.  **LLM Call**: Claude is queried with tools enabled. If Claude decides to run a tool, the execution pauses.
    4.  **Security Gate Checking**: Intercepts tool calls before running to verify authenticated user role context scopes.
    5.  **Execution**: Runs tools and feeds outputs back to Claude.
    6.  **Resolution**: Loop completes when Claude returns a final text answer without further tool requests.
*   **The Propose-Confirm Workflow**:
    1.  **Proposed State**: Tool `propose_action` does not modify the production order databases directly. Instead, it serializes a target proposal transaction inside the `escalations` / proposal tables, returning a `proposal_id` (status `PENDING`).
    2.  **User Confirmation**: The UI receives the `ConfirmationCard` component. The user can accept or reject the proposal.
    3.  **State Commitment**: Confirming the proposal makes a POST call to `/chat/confirm`. The backend checks the user's role and execution permissions, and commits the state mutation to the db.

### B. Authentication & Scoping Control
This outlines the authentication and row-level authorization mechanics in the ParcelPilot AI backend.
*   **JWT-based Mock Authentication**: simulated authentication uses the standard OAuth2 password flow with JWT tokens. Users configured:
    1. `cust-northstar` (Customer, Account: `ACCT-001`)
    2. `cust-lumenworks` (Customer, Account: `ACCT-002`)
    3. `cust-beacon` (Customer, Account: `ACCT-003`)
    4. `agent-maya` (Support Agent, Scope: Global)
    5. `lead-rohit` (Team Lead, Scope: Global, Authorized Approval Limit: > 1000 INR)
*   **Row-Level Authorization & Access Scoping**: Authorization is strictly enforced in two backend places:
    1.  **Route Handlers**: Internal routes (e.g. `/insights`) inspect the decoded current user's role and block customer roles.
    2.  **Guardrails in Agent Tools**: `search_documents` restricts search chunks to general scope or user's `account_id`. `query_structured_data` restricts SQL filters for orders and tickets. `propose_action` restricts role execution rules.

### C. Relational & Vector Database Design
*   **Schema Definitions**:
    1.  **Account**: Tracks companies, support service level agreements (SLAs), and custom contract parameters.
    2.  **Order**: Tracks shipment packages (statuses: `BOOKED`, `PICKED_UP`, `DELIVERED`, `CANCELLED`).
    3.  **Ticket**: Tracks customer support queries.
    4.  **Document & DocumentChunk**: Handles document chunk indexes and vector arrays.
    5.  **AuditLog**: Tracks LLM actions.
    6.  **Escalation**: Stores supervisor review requests.
*   **Seeding Pipeline**: Seeding parses timestamps dynamically and anchors all time calculations relative to a fixed baseline timestamp: `2026-08-16 11:00:00+05:30` (Asia/Kolkata timezone).

### D. PDF Ingestion & Scope Mapping
*   **Semantic Section-based Ingestion**: processes 6 source PDF documents using PyPDF2. Extracts headings, metadata pages, and structural sections. Generates vector embeddings using the configured embedding engine (Voyage AI or fallback OpenAI `text-embedding-3-small` / OpenAI mock models). Chunks are loaded into the standard PostgreSQL `pg_document_chunks` table utilizing the `pgvector` index type.
*   **Authority Levels and Scope Mapping**:
    1.  **Client-specific Contracts**:
        *   *Northstar Contract* (`05_Northstar_SLA_Contract_v4_CURRENT.pdf`): Authority Level = 1 (Highest), Scope = `ACCT-001`.
        *   *LumenWorks Contract* (`06_LumenWorks_SLA_Contract_v4_CURRENT.pdf`): Authority Level = 1, Scope = `ACCT-002`.
    2.  **General Support Policies**:
        *   *Support Policy v3* (`01_Support_Policy_v3_CURRENT.pdf`): Authority Level = 2, Scope = `general`, Status = `CURRENT`.
        *   *Cancellation Policy SOP* (`03_Cancellation_Refund_SOP_v4.pdf`): Authority Level = 2, Scope = `general`, Status = `CURRENT`.
        *   *Product Operations Guide* (`04_Product_Operations_Playbook_v1.pdf`): Authority Level = 3 (Guidance), Scope = `general`, Status = `CURRENT`.
    3.  **Deprecated Versioning**:
        *   *Support Policy v2* (`02_Support_Policy_v2_DEPRECATED.pdf`): Authority Level = 2, Scope = `general`, Status = `DEPRECATED` (excluded from active query reasoning).

### E. Backend Automation Test Suite
*   **Test Files & Focus Areas**:
    1.  `test_auth.py`: Validates JWT login token exchanges and verifies that endpoints (like `/insights`) reject requests containing unauthorized customer role tokens.
    2.  `test_calculations.py`: Verifies refund and delivery delay fee calculations.
    3.  `test_reliability.py`: Confirms trust-layer guardrails prevent tool execution conflicts. Checks version status precedence.
    4.  `test_end_to_end.py`: Runs simulated FastAPI HTTP interactions (cancellation flow, isolation flow, etc.).
    5.  `test_orchestration.py`: Tests Claude tool-calling loops and supervisor approval restrictions.

### F. Frontend Architecture & Tech Stack
*   **Frontend Technology Stack**: React (TypeScript) + Vite + Tailwind CSS v4 compiler (via `@tailwindcss/vite` plugin) + `lucide-react` + `recharts`.
*   **Page & Layout Architecture**: side-by-side layout:
    1.  **Left Sidebar Pane**: Header Logo, Navigation Tabs (toggle AI Agent Console and Operations Dashboard), Privilege Simulator Select (role swaps), Recents Tracker, and user metadata panel.
    2.  **Right Viewport Pane**: Header Bar (tenant status) and Workspace Area.
