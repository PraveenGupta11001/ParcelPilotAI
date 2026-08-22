# ParcelPilot AI Customer Support System

A secure, tenant-isolated AI Customer Support Portal and Operational Insights Dashboard for logistics operations. The frontend is styled in a premium CalQuity-inspired clean light theme featuring a ChatGPT-style sidebar navigation.

---

## Technical Stack & Portfolio Features

### Backend Service Stack
*   **Web Framework**: FastAPI core with asynchronous endpoints and SSE response streaming support.
*   **Database & Vector Store**: PostgreSQL with `pgvector` indexing for semantic policy routing, relational tracking, and UUID-based chat sessions.
*   **AI Agent Orchestrator**: Anthropic Claude messages loop implementing reactive tools and trust safety checks.
*   **Reliability Guardrails**: Propose-confirm workflow gating database mutations and enforcing role-based permissions at the tool level.
*   **Document Metadata Tools**: Distinct document tracking (`get_document_count` & `list_all_documents`) with built-in tenant filtering.

### Frontend Interface
*   **Development Framework**: Vite + React (TypeScript) + React Router.
*   **Styling Engine**: Tailwind CSS v4 featuring HSL color systems and custom dot-grid backplate overlays.
*   **Components**: Custom atomic library (`Button`, `Card`, `TextInput`, `Select`, etc.) with ref forwarding support.
*   **Branded Experience**: Authentic logo layouts for login screen and chat empty states combined with keyboard autofocus flow management.
*   **Dashboards**: Recharts analytics visualization of SLAs, delay statistics, and carrier reliability scorecards.

---

## Directory Organization

```
├── Data/                              # Document SLA contracts and excel sheets
├── backend/                           # FastAPI server
│   ├── app/
│   │   ├── agent/                     # Orchestration engine & loop
│   │   ├── auth/                      # MockJWT & Auth policies
│   │   ├── db/                        # Seed, models, and session schema
│   │   ├── ingestion/                 # Semantic PDF chunkers
│   │   └── tools/                     # Scoped agent tool registry
│   ├── tests/                         # Integration test modules
│   └── requirements.txt               # Dependencies list
├── frontend/                          # Vite React application
│   ├── src/
│   │   ├── components/ui/             # Reusable modular UI elements
│   │   └── App.tsx                    # Main portal view
│   └── package.json                   # UI packages config
├── dev_test_reads/                     # Developer walkthroughs (git-ignored)
└── docker-compose.yml                 # Database & pgvector container config
```

---

## Local Setup & Run Guidelines

### 1. Database & Seeding
Start structural database services and seed assessment registers (anchored at `2026-08-16 11:00:00+05:30` baseline):
```bash
# Start Docker compose
docker-compose up -d

# Seed Excel rows
source venv/bin/activate
cd backend
PYTHONPATH=. python app/db/seed.py

# Ingest and embed PDF policies
PYTHONPATH=. python app/ingestion/parse_pdfs.py
```

### 2. Run Backend Webhooks
```bash
python -m uvicorn app.main:app --reload --port 8000
```

### 3. Run Frontend Local Dev Server
```bash
cd ../frontend
npm install
npm run dev
```
Open `http://localhost:5173` to interact with the application scope.

---

## Test Executions
Run the integration pytest suite:
```bash
cd backend
PYTHONPATH=. pytest tests/
```
