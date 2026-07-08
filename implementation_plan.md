# MCP Server for Gmail & Google Docs — Implementation Plan

Build a standalone MCP server exposing 3 tools (`gmail_send_email`, `gmail_create_draft`, `gdoc_append_content`) using the official MCP Python SDK (`FastMCP`) over **stdio** transport, with **OAuth installed-app** authentication and **pip/requirements.txt** for dependency management.

---

## 1. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **MCP SDK** | `mcp` v1.x (stable) with `FastMCP` | Production-ready; v2 is still in pre-release |
| **Transport** | `stdio` | Standard for local MCP tools (Claude Desktop, Antigravity) |
| **Auth model** | OAuth installed-app flow | Each deployment authenticates as a specific user via browser consent |
| **Dependency manager** | pip + `requirements.txt` | Simple, widely supported |
| **Python version** | 3.10+ | Required by `mcp` SDK |

---

## 2. Project Structure

```
MCP-SERVER/
├── mcp_server_problemStatement.md   # (existing) problem statement
├── implementation_plan.md           # (this file)
├── requirements.txt                 # [NEW] Python dependencies
├── .env.example                     # [NEW] env var template
├── .gitignore                       # [NEW] secrets & cache exclusions
├── README.md                        # [NEW] setup & usage guide
├── credentials.json                 # (user-provided, gitignored)
├── token.json                       # (auto-generated, gitignored)
├── src/
│   ├── __init__.py                  # [NEW]
│   ├── server.py                    # [NEW] FastMCP server + tool definitions
│   ├── auth.py                      # [NEW] OAuth2 token management
│   ├── gmail_client.py              # [NEW] Gmail API wrapper
│   ├── gdoc_client.py               # [NEW] Google Docs API wrapper
│   └── config.py                    # [NEW] env/config loading
└── tests/
    ├── __init__.py                   # [NEW]
    ├── test_server.py               # [NEW] tool schema + integration tests
    ├── test_gmail_client.py         # [NEW] Gmail send/draft unit tests
    └── test_gdoc_client.py          # [NEW] Docs append unit tests
```

---

## 3. Dependencies

```txt
mcp>=1.0,<2.0              # MCP Python SDK (stable v1.x with FastMCP)
google-api-python-client    # Google API client for Gmail & Docs
google-auth-oauthlib        # OAuth2 installed-app flow
google-auth-httplib2        # Transport adapter
python-dotenv               # .env file loading
pytest                      # Testing
```

---

## 4. Component Details

### 4.1 Configuration Layer — `src/config.py`

Loads configuration from environment variables with `.env` fallback via `python-dotenv`.

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_CREDENTIALS_PATH` | `./credentials.json` | Path to OAuth client secrets file |
| `GOOGLE_TOKEN_PATH` | `./token.json` | Path to cached token file |
| `GOOGLE_SCOPES` | *(see below)* | OAuth scopes (comma-separated) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

**Default scopes:**
- `https://www.googleapis.com/auth/gmail.send`
- `https://www.googleapis.com/auth/gmail.compose`
- `https://www.googleapis.com/auth/documents`

Validates required files exist at startup; raises clear errors if `credentials.json` is missing.

---

### 4.2 Auth Layer — `src/auth.py`

Handles all Google OAuth 2.0 lifecycle:

**`get_credentials() → Credentials`**
1. Check for existing `token.json` → load and verify
2. If token expired but has refresh token → auto-refresh via `credentials.refresh(Request())`
3. If no token exists → run `InstalledAppFlow.run_local_server(port=0)` for browser consent
4. Save refreshed/new token back to `token.json`
5. Return valid `google.oauth2.credentials.Credentials`

**`build_service(api_name: str, version: str) → Resource`**
- Builds an authenticated Google API service client
- e.g., `build('gmail', 'v1', credentials=creds)`

**Security:**
- Never logs tokens, secrets, or credential contents
- Catches `google.auth.exceptions.RefreshError` → returns structured error, never crashes

---

### 4.3 Gmail Client — `src/gmail_client.py`

Wraps the Gmail API. Consumed by the tool layer, never exposed directly.

#### `send_email(to, subject, body, cc=None, bcc=None, body_type="text") → dict`

1. Construct `email.message.EmailMessage` with `To`, `Cc`, `Bcc`, `Subject` headers
2. Set content as plain text or HTML based on `body_type`
3. Base64url-encode the message
4. Call `gmail.users().messages().send(userId="me", body={"raw": encoded})`
5. Return:
   - Success: `{"status": "success", "message_id": "<id>"}`
   - Error: `{"status": "error", "error_message": "<description>"}`

#### `create_draft(to, subject, body, cc=None, bcc=None, body_type="text") → dict`

1. Same message construction as `send_email`
2. Call `gmail.users().drafts().create(userId="me", body={"message": {"raw": encoded}})`
3. Return:
   - Success: `{"status": "success", "draft_id": "<id>"}`
   - Error: `{"status": "error", "error_message": "<description>"}`

#### Retry Logic (decorator-based)

- Exponential backoff: 3 retries, base delay 1 second
- Retryable: `HttpError` with status `429` (rate limit) or `5xx` (server error)
- Non-retryable: `400`, `401`, `403`, `404` → returned immediately as structured errors

---

### 4.4 Google Docs Client — `src/gdoc_client.py`

#### `append_content(document_id, content, add_newline_before=True) → dict`

1. **GET** the document to determine the end index:
   ```python
   doc = docs_service.documents().get(documentId=document_id).execute()
   end_index = doc["body"]["content"][-1]["endIndex"] - 1
   ```
2. Prepend `\n` to content if `add_newline_before=True`
3. Call `documents().batchUpdate()` with:
   ```python
   {"insertText": {"location": {"index": end_index}, "text": text}}
   ```
4. Return:
   - Success: `{"status": "success", "document_id": "<id>", "revision_id": "<rev>"}`
   - Error: `{"status": "error", "error_message": "<description>"}`

**Error mapping:**
| Google API Error | Returned Error Message |
|-----------------|----------------------|
| `404 Not Found` | `"Document not found: <id>"` |
| `403 Forbidden` | `"Access denied to document: <id>"` |
| `429 / 5xx` | Auto-retry with backoff |

---

### 4.5 MCP Server — `src/server.py`

Main entry point. Uses `FastMCP` from the official MCP SDK.

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("google-workspace")

@mcp.tool()
def gmail_send_email(
    to: str | list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    body_type: str = "text"
) -> dict:
    """Send an email immediately via the authenticated Gmail account."""
    ...

@mcp.tool()
def gmail_create_draft(
    to: str | list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    body_type: str = "text"
) -> dict:
    """Create a draft email in Gmail without sending it."""
    ...

@mcp.tool()
def gdoc_append_content(
    document_id: str,
    content: str,
    add_newline_before: bool = True
) -> dict:
    """Append text content to the end of an existing Google Doc."""
    ...

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**Design decisions:**
- Each `@mcp.tool()` is a thin wrapper: validates inputs → delegates to client → returns structured dict
- Input validation at the tool layer (e.g., `to` must be non-empty, `body_type` must be `"text"` or `"html"`)
- All tools return dicts — **never raise exceptions** to the MCP layer
- Logging to **stderr** only (stdout is reserved for MCP JSON-RPC over stdio)

---

### 4.6 Logging Strategy

| Aspect | Approach |
|--------|----------|
| Library | Python `logging` module |
| Output | `stderr` only (required for stdio transport) |
| Format | `[%(asctime)s] %(levelname)s %(name)s: %(message)s` |
| Tool calls | Logged at `INFO` (parameters **minus** sensitive fields like `body`) |
| API errors | Logged at `WARNING` / `ERROR` with context |
| Stack traces | Logged at `DEBUG` only — never returned to caller |

---

### 4.7 Tests

#### `tests/test_server.py`
- Verify `list_tools` returns all 3 tools with correct names and descriptions
- Verify tool input schemas match the spec (required/optional fields, types, defaults)
- Verify tools return structured responses (not exceptions)

#### `tests/test_gmail_client.py`
- Mock `gmail.users().messages().send()` → verify MIME construction and base64 encoding
- Mock `gmail.users().drafts().create()` → verify draft creation
- Test HTML vs plain text body construction
- Test error handling: mock `HttpError(429)` → verify retry; mock `HttpError(400)` → verify immediate structured error

#### `tests/test_gdoc_client.py`
- Mock `documents().get()` → return fake doc structure → verify correct end-index calculation
- Mock `documents().batchUpdate()` → verify `insertText` request body
- Test `add_newline_before=True` vs `False`
- Test error handling: invalid doc ID → structured error; permission denied → structured error

---

## 5. Execution Phases

| Phase | Milestone | Files | Description |
|-------|-----------|-------|-------------|
| **1** | Scaffolding | `requirements.txt`, `.env.example`, `.gitignore`, `src/__init__.py`, `tests/__init__.py`, `src/config.py` | Project setup, dependencies, configuration |
| **2** | Auth | `src/auth.py` | OAuth2 token management, credential caching, auto-refresh |
| **3** | Gmail | `src/gmail_client.py`, `tests/test_gmail_client.py` | Send email + create draft with retry logic |
| **4** | Docs | `src/gdoc_client.py`, `tests/test_gdoc_client.py` | Append content with end-index detection |
| **5** | Server | `src/server.py`, `tests/test_server.py` | FastMCP tool definitions, input validation, wiring |
| **6** | Polish | `README.md`, all files | Logging, error handling review, documentation, manual verification |

---

## 6. Verification Plan

### Automated Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src
```

### Manual Verification

| # | Test | Expected Result |
|---|------|-----------------|
| 1 | Run `python -m src.server`, connect via MCP Inspector | All 3 tools listed with correct schemas |
| 2 | Call `gmail_send_email` with a test recipient | Email arrives in inbox |
| 3 | Call `gmail_create_draft` | Draft visible in Gmail web UI |
| 4 | Call `gdoc_append_content` with a test doc ID | Text appears at end of document |
| 5 | Call with invalid doc ID / bad email | Structured error response (no crash) |
| 6 | Connect a second MCP client | Tools work identically (genericity check) |

---

## 7. Prerequisites (User Action Required)

Before Phase 2 (Auth), you must:

1. **Create a Google Cloud project** at [console.cloud.google.com](https://console.cloud.google.com/)
2. **Enable APIs:** Gmail API + Google Docs API
3. **Configure OAuth consent screen:** Add your email as a test user
4. **Create OAuth credentials:** Desktop app → download `credentials.json`
5. **Place `credentials.json`** in the project root (`MCP-SERVER/credentials.json`)

---

## 8. Open Questions

| # | Question | Impact |
|---|----------|--------|
| 1 | Should we stub `gdoc_create_document` for a future v2? | Adds one tool skeleton now vs. later |
| 2 | Any email size limits to enforce beyond Gmail's own? | Affects input validation |
| 3 | Should `body_type` support `markdown` in addition to `text`/`html`? | Adds a rendering step |
