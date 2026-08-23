# ParcelPilot Architecture Note

This document outlines the high-level architecture of the ParcelPilot AI customer support system, specifically focusing on the Agent Design and Tool Design.

## 1. Agent Design

The ParcelPilot Agent is engineered as a **stream-enabled, human-in-the-loop orchestrator** built in Python (via FastAPI). Its primary responsibility is to bridge the gap between unstructured natural language from customers/support staff and strict, structured business logic in our database.

### Key Architectural Choices:
- **Stateless Orchestration with Fallback Pool:** The agent layer is completely stateless, relying on the client/database for session context. It utilizes a robust multi-model fallback strategy. If the primary Large Language Model (e.g., GPT-4o-mini, Groq) hits a rate limit or fails to parse a tool-call reliably, the orchestrator instantly fails over to alternative providers (like Gemini). This ensures high reliability in production support environments.
- **Human-in-the-Loop State Mutation:** To solve the core problem of AI "Trust and Reliability," the agent is strictly isolated from directly mutating state. Instead of autonomously executing destructive operations, the agent is restricted to generating `PendingAction` proposals. These proposals are bubbled up to the UI, guaranteeing that a human operator (or the customer) explicitly confirms the action before any mutations occur.
- **Security & Tenant Isolation First:** The agent’s context is heavily governed by the authenticated user's token. During Retrieval-Augmented Generation (RAG) and tool usage, the agent is strictly prevented from fetching documents or proposing actions on data that does not belong to the user's `account_id` (unless the user has an internal operational role).

## 2. Tool Design

Tools are designed as strict, specialized endpoints that act as the interface between the LLM and the PostgreSQL database. Each tool abstracts complex business logic into safe, isolated functions.

### Key Tools Implemented:

1. **`search_documents` (Semantic RAG)**
   - **Mechanism:** Leverages `pgvector` in PostgreSQL to perform semantic cosine-similarity searches.
   - **Design Decision:** Rather than giving the LLM all policies, this tool dynamically filters based on `account_id` and actively excludes `DEPRECATED` policies by default. This ensures the LLM reasons over the most highly relevant, legally binding constraints (e.g., Signed Customer Contracts override General Policy).
   
2. **`query_structured_data` (Live Business Logic)**
   - **Mechanism:** Allows the LLM to query structured SQL records for `orders`, `tickets`, and `accounts`.
   - **Design Decision:** The tool doesn't just read data; it runs centralized Python business logic (e.g., calculating exact cancellation fees or SLA elapsed times) and returns these metrics directly. This prevents the LLM from hallucinating math or contract terms, ensuring 100% deterministic SLA and credit behavior.
   
3. **`propose_action` (Proposal Engine)**
   - **Mechanism:** The system's primary write-interface. Accepts commands to `CANCEL_ORDER`, `ISSUE_CREDIT`, or `ESCALATE_TICKET`.
   - **Design Decision:** Implements intelligent fallbacks. For instance, if an LLM proposes issuing a credit but forgets a required support ticket ID, the tool intelligently intercepts the request and auto-generates a linked ticket invisibly. It then saves the state as `PENDING` and returns a secure `proposal_id` to the LLM. It also features idempotency guards to prevent the LLM from spamming duplicate pending escalations for the same ticket.

---
*By decoupling the LLM's natural language understanding (Agent Design) from the rigid execution of business logic (Tool Design), ParcelPilot successfully balances automation efficiency with enterprise-grade reliability and security.*
