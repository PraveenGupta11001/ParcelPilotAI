# Developer Testing and Troubleshooting Guide (`dev_tests_reads`)

This guide captures major errors, warnings, and architectural bottlenecks encountered during the modernization of the **ParcelPilot** application, long-term testing checks, and resolutions.

---

## 1. Frontend State Synchronization & SSE Race Conditions
### Symptom
On creating a new chat session, the initial user message is duplicated inside the chat history database schema. At the same time, the streaming assistant response panel temporarily loads but vanishes from the UI before completion.

### Root Cause
When the frontend posts the initial message of a chat session, the backend creates a session ID and returns a `session_created` SSE event. In the React `ChatPanel.tsx`:
1. Receiving `session_created` calls `setActiveSessionId(newSId)` to change the URL context and select the active item in the sidebar.
2. A `useEffect` hook listening to changes in `activeSessionId` instantly fires a background database fetch `/chat/sessions/{id}/messages`.
3. Since the database has already written the user query message but hasn't finalized the streaming answer generator task, the API returns only the user's message.
4. Setting message history to the fetched value overwrites the active React state, truncating the assistant's streaming message structure.
5. Users resubmit their query due to the interface disappearing, creating duplicate messages.

### Resolution
Introduce a React `useRef` blocker (`isCreatingSessionRef`) that flags the current session creation action:
```typescript
const isCreatingSessionRef = useRef(false);

const handleSendMessage = async (e: React.FormEvent) => {
    ...
    if (!activeSessionId) {
        isCreatingSessionRef.current = true;
    }
    ...
};

useEffect(() => {
    if (activeSessionId) {
        if (isCreatingSessionRef.current) {
            // Prevent fetching and running race condition on initial session generation
            isCreatingSessionRef.current = false;
        } else {
            loadSessionMessages();
        }
    } else {
        setMessages([]);
    }
}, [activeSessionId]);
```

---

## 2. Empty Vector Database (pgvector) after Seeding
### Symptom
The customer agent executes successfully and registers traces in the browser console, but outputs an empty list (`[]`) and fails to fetch reference policy matches or cancellation details.

### Root Cause
Calling `python -m app.db.seed` recreates all database tables (executing `Base.metadata.drop_all` followed by `Base.metadata.create_all`). While this seeds baseline Excel records (users, orders, tickets), it truncates the `document_chunks` table to zero. The policy PDFs are not re-embedded or written back during seeding.

### Resolution
You must re-run the parse/ingester Python script to rebuild the document database index after every database reset:
```bash
python -m app.ingestion.parse_pdfs
```

---

## 3. Strict API Validation for Assistant Tool Calls (OpenAI/Groq/Gemini Coexistence)
### Symptom
LLMs return empty response content (`""`) or complete with zero message tokens immediately after executing intermediate tool actions.

### Root Cause
When appending past assistant choices that initiated tool calls to the history context:
```python
# BROKEN
to_append = {"role": "assistant", "content": assistant_msg.content or ""}
```
Replacing a `None` content value with an empty string `""` causes API validation checks on strict OpenAI compatibility layers (like Groq) to fail or ignore generation. Assistant messages holding `tool_calls` require content to be exactly `None` / `null`.

### Resolution
Retain the exact object values:
```python
# CORRECTED
to_append = {"role": "assistant", "content": assistant_msg.content}
```

---

## 4. Playwright Browser Automation Driver Failures (404 Mirror Error)
### Symptom
Running automated browser scenarios via tools like `browser_subagent` yields environment crashes:
```
got non 200 status code: 404 (404 Not Found) from https://playwright.azureedge.net/builds/driver/playwright-1.50.1-linux.zip
```

### Root Cause
The default regional CDN mirror where Playwright retrieves binary drivers experiences down-times or returns 404 links, preventing automatic installation of sandbox contexts.

### Resolution
1. Verify routes and token operations manually using browser console.
2. Build the application (`tsc -b && vite build`) to confirm TypeScript code compiles without syntax errors before deployment.

---

## 5. TypeScript Unused Variable Warnings (`App.tsx`)
### Symptom
Build commands fail or issue warnings with:
```
App.tsx: 'refreshToken' is declared but its value is never read.
```

### Root Cause
The state variable `refreshToken` is defined for future UI configurations but not read in the component.

### Resolution
Destructure only the dispatcher method to avoid compiler errors:
```typescript
const [, setRefreshToken] = useState<string | null>(localStorage.getItem('refresh_token'));
```

---

## 6. Truncated Responses from Reasoning Models (`max_tokens` Cap)
### Symptom
The AI agent makes diagnostic tool calls successfully but yields an empty string (`""`) for the final text response block without throwing exceptions.

### Root Cause
Under modern reasoning models (like deep reasoning systems mapped on Groq/Qwen), a significant token budget is consumed inside the thinking phase (yielding `reasoning_tokens` or `reasoning` keys). Capping `max_tokens` at `800` causes completion threads to trigger `finish_reason: length` before writing any actual user content.

### Resolution
Enlarge the completion buffer size from `800` to `4096` in the orchestration loops:
```python
response = client.chat.completions.create(
    model=model,
    messages=messages,
    tools=openai_tools,
    max_tokens=4096
)
```

---

## 7. Gemini API Legacy Model Catalog Error (404 v1main)
### Symptom
Falling back to Gemini Backup raises a `404 - models/gemini-1.5-flash is not found for API version v1main` exception.

### Root Cause
The legacy model `gemini-1.5-flash` has been deprecated or restricted for the API key in use, which causes Google's Generative AI gateway to map unauthorized queries to `v1main` and throw 404s.

### Resolution
Migrate the fallback configurations in `orchestration.py` to target the active model choice `gemini-2.5-flash` instead:
```python
options.append({
    "api_key": self.gemini_key,
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "model": "gemini-2.5-flash",
    "name": "Gemini Backup"
})
```

---

## 8. Aborted SSE Connections on First Chat Message (Session Creation Router Unmount)
### Symptom
On creating a brand new chat session, sending the first message creates the session ID dynamically and redirects, but the UI goes completely blank for the assistant response. The user must re-submit the message.

### Root Cause
Initially, the `/chat` route (for blank inputs) and `/chat/:chatId` route (for loaded sessions) rendered separate route definitions. When the backend yielded the `session_created` event, the UI updated the active session ID, causing React Router to unmount the initial `ChatPanel` instance and mount a fresh `ChatPanelWrapper` instance. This unmounting immediately aborted the active fetch stream and cut off the SSE reader before the assistant could render the response.

### Resolution
Consolidated the split URL paths into a single optional parameter route in `App.tsx`:
```typescript
<Route path="/chat/:chatId?" element={<ChatPanelWrapper />} />
```
This forces React Router to reuse the exact same component instance during URL updates (just mutating props), preserving the SSE network stream when the session ID gets assigned.

---

## 9. False Positives in Live Tool Execution Status (RAG Content Collisions)
### Symptom
RAG documents searches (`search_documents`) execute successfully and return target policy content, but the UI component marks them as `FAILED` (colored in red).

### Root Cause
The matching logic check `tc.output.toLowerCase().includes('fail')` was too greedy. Successful search outputs containing words like "failed-pickup", "failure", or "fail" (which frequently display within cancellation terms) triggered a false-positive failure state.

### Resolution
Replaced substring checking with robust JSON-structure verification in `ChatPanel.tsx`:
```typescript
const isFailed = (() => {
    if (!tc.output || typeof tc.output !== 'string') return false;
    const trimmed = tc.output.trim();
    if (trimmed.startsWith('{"error":')) return true;
    try {
        const parsed = JSON.parse(trimmed);
        return parsed && (parsed.error !== undefined || parsed.status === 'error' || parsed.status === 'FAILED');
    } catch (e) {
        return trimmed.toLowerCase().includes('error');
    }
})();
```

---

## 10. Adding Document Metadata Utilities (`get_document_count` & `list_all_documents`)
### Requirement
Add tools to query the status and names of all active policies or agreements so the agent can accurately answer user queries such as:
*   *How many docs do you have?*
*   *List all policies*

### Implementation & Tenant Security
1. **Tool Schema Registry**: Registered `get_document_count` and `list_all_documents` in `registry.py`.
2. **Logic Helpers (`document_info.py`)**: Counts and lists unique document names.
3. **Cross-Tenant Restrictions**: Both tools enforce the exact same isolation rules as RAG searches. If the user role is `customer`, they can only see general-scoped policies and those belonging to their `account_id`; other entries (like other customer agreements) are filtered out at the SQL compilation level. Internal operators maintain universal visibility.
4. **Execution Integration**: Added routes to `AgentService.run_tool` inside `orchestration.py`. Tested successfully via unit tests:
```bash
pytest tests/test_document_info.py
```

---

## 11. Deprecation Warning Cleanup: Transitioning `utcnow` to Timezone-Aware UTC
### Symptom
Running unit tests outputted multiple Python DeprecationWarnings warning of future removal of `datetime.datetime.utcnow()` from standard library versions.

### Root Cause
SQLAlchemy schemas in `models.py` and token generator algorithms in `auth/jwt.py` relied on timezone-naive `datetime.utcnow()` calls.

### Resolution
Migrated all application implementations to timezone-aware UTC format:
- Configured DB model default values to reference timezone-aware lambda expressions:
```python
Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC))
```
- Standardized JWT helpers to append `datetime.now(UTC)` targets from standard library packages. This reduced project warnings count by **over 50%**.

---

## 12. Input Focus, Ref forwarding, and Branded Empty State Layout
### Requirement
1. Automatically focus on the email input box on login layout mount.
2. In the chat dashboard, automatically focus the active chat session's message input box on panel mount or when switching active sessions.
3. Automatically return focus to the message input box immediately when message sending completes.
4. Ensure the input box is disabled while the transaction proposal or message streaming is running backend calculations.
5. Display the authentic `parcelPilotLogo` brand asset in the `EmptyState` component on new chat screens, and keep message layout styles completely original (no customer/agent message avatars).

### Implementation
1. **Ref forwarding**: Modified `TextInput` component (`text-input.tsx`) using `React.forwardRef<HTMLInputElement>` to expose the underlying raw HTML input element to callers.
2. **Autofocus Event Hooks**:
   - Added `autoFocus` prop directly to login email input.
   - Added a `useEffect` inside `ChatPanel.tsx` listening to `loadingChat` state transitions. Once message generation transitions from `true` to `false` (enabling the element), the ref automatically queries `.focus()`.
   - Used a `setTimeout` of 60ms to let reactive browser rendering update the elements before executing the native JavaScript element focus action.
3. **Branded Empty State**: Integrated the `parcelPilotLogo` brand image element callback inside `ChatPanel.tsx`'s `EmptyState` render block, centering it at the top of the initial welcome layout card without altering existing message bubbles.
4. Verified compilation and execution via frontend build scripts:
```bash
npm run build
```

---

## 13. Migrating Chat Session IDs from Autoincrement Integers to UUID Strings
### Requirement
Transition the chat session identifiers from incremental integers (e.g. `1`, `2`, `3`) to globally unique uuid strings (e.g. `e0e7a2bd-25b8-4d51-87e2-cfdf29983995`), propagating this change cleanly across database tables, API routing parameters, TypeScript models, validation asserts, and route path links.

### Implementation
1. **Database Schema (`models.py`)**:
   - Modified `ChatSession.id` to a string of size 36, automatically initialized via `uuid.uuid4()`.
   - Updated `ChatMessage.session_id` to refer to a string of size 36 instead of integer.
2. **API Routes & Schemas (`chat.py`)**:
   - Updated validation schema `ChatRequest` to expect `session_id` as an optional string.
   - Updated Python routes for message fetching (`/sessions/{session_id}/messages`) and session deletion (`/sessions/{session_id}`) to accept string path arguments.
3. **Tests (`test_chat_endpoint.py`)**:
   - Adjusted assertion to check that the returned session identifier is an authentication instance of `str`.
4. **React Client (`App.tsx`, `MainLayout.tsx`, `ChatPanel.tsx`)**:
   - Updated `SessionItem` model type definitions to specify `id: string`.
   - Replaced `parseInt(activeSessionId)` parsing checks inside raw POST payloads to directly pass string IDs.
   - Adjusted `sessionToDelete` state hooks to handle string/null types.
5. All backend test checks and production build suites compile cleanly:
```bash
pytest
npm run build
```
