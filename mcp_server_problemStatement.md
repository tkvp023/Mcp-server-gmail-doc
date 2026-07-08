# Problem Statement: MCP Server for Gmail & Google Docs

## 1. Overview

Build a standalone **MCP (Model Context Protocol) server** that exposes tools for:

1. **Sending and drafting emails via Gmail**
2. **Appending content to a Google Doc**

This server is the integration layer that other agents/pipelines call into — it does not itself do any review ingestion, clustering, or summarization. The primary near-term consumer is a "weekly mobile-store review pulse" agent (which publishes a summary note to a Google Doc and drafts a Gmail email pointing to it), but the server itself must remain **generic and reusable** by any MCP-compatible client, not hardcoded to that use case.

## 2. Goals

- Expose a small, well-defined set of MCP tools covering Gmail send/draft and Google Docs append.
- Handle all Google OAuth 2.0 auth and token refresh internally — callers never touch credentials or REST calls directly.
- Keep tool schemas generic enough that any agent (not just the review-pulse agent) can use them for its own purposes.
- Return structured, predictable success/error responses so calling agents can reason about outcomes without parsing raw API errors.

## 3. Non-Goals

- No review ingestion, theme clustering, or note generation — that logic lives in the calling agent, not this server.
- No creation of brand-new Google Docs in v1 — only appending to an *existing* doc (create-new can be a fast-follow if needed).
- No inbox reading/search, labeling, or email management beyond send/draft.
- No attachments in v1.
- No multi-tenant credential UI — a single configured account/service credential is sufficient for v1.

## 4. Functional Requirements

### 4.1 Tool: `gmail_send_email`
Sends an email immediately via the authenticated Gmail account.

**Input:**
- `to` (string or array of strings, required)
- `cc` (array of strings, optional)
- `bcc` (array of strings, optional)
- `subject` (string, required)
- `body` (string, required) — plain text or HTML
- `body_type` (enum: `text` | `html`, optional, default `text`)

**Output:**
- `status` (`success` | `error`)
- `message_id` (string, if success)
- `error_message` (string, if error)

### 4.2 Tool: `gmail_create_draft`
Creates a draft email without sending it — this is the primary mode the review-pulse agent will use (draft to self/alias, never auto-sent).

**Input:** same schema as `gmail_send_email`.

**Output:**
- `status` (`success` | `error`)
- `draft_id` (string, if success)
- `error_message` (string, if error)

### 4.3 Tool: `gdoc_append_content`
Appends text content to the end of an existing Google Doc — used to publish/update the weekly pulse note.

**Input:**
- `document_id` (string, required)
- `content` (string, required)
- `add_newline_before` (boolean, optional, default `true`)

**Output:**
- `status` (`success` | `error`)
- `document_id` (string)
- `revision_id` (string, if available)
- `error_message` (string, if error)

### 4.4 Tool Discovery
All tools discoverable via standard MCP `list_tools`, with self-describing names/descriptions/JSON Schemas so any generic agent — including the review-pulse agent and others — can use them without special-casing.

## 5. Non-Functional Requirements

- **Genericity:** No review-pulse-specific (or any other caller-specific) logic in the server. Tool names/schemas/behavior stay agent-agnostic.
- **Authentication:**
  - Google OAuth 2.0 (installed-app or service-account flow, to be decided per deployment).
  - Scopes required:
    - `https://www.googleapis.com/auth/gmail.send`
    - `https://www.googleapis.com/auth/gmail.compose`
    - `https://www.googleapis.com/auth/documents`
  - Tokens stored/refreshed securely; no secrets in logs.
- **Error Handling:** Structured errors for auth failures, invalid doc IDs, malformed email fields, rate limits — never raw stack traces to the caller.
- **Logging:** Log tool invocations (params minus sensitive body content) and outcomes for debugging/audit.
- **Retries:** Backoff/retry on Google API quota/rate-limit errors.
- **Configurability:** Credentials, scopes, target account set via env vars/config — not hardcoded.
- **Transport:** Standard MCP transport (stdio and/or HTTP/SSE, per whatever Antigravity's default MCP server convention is).

## 6. Architecture (High-Level)

```
[Any MCP Client]
  e.g. review-pulse agent, or any other agent
        |
        | MCP protocol (tool calls)
        v
[MCP Server: Gmail + Docs]
   ├── Tool Layer (gmail_send_email, gmail_create_draft, gdoc_append_content)
   ├── Auth Layer (OAuth2 token management, refresh)
   ├── Google API Clients (Gmail API, Docs API)
   └── Error/Response Normalization Layer
        |
        v
[Google Workspace APIs: Gmail API, Docs API]
```

## 7. Authentication Flow (Proposed)

1. On startup, check for stored credentials (token file / secret store).
2. If absent, run OAuth 2.0 consent flow (or use a pre-configured service account with domain-wide delegation, if applicable).
3. Store refresh token securely; auto-refresh access token before each API call as needed.
4. On invalid/expired auth that can't be silently refreshed, return a clear structured error rather than crashing.

## 8. Success Criteria

- MCP `list_tools` returns all three tools with correct, self-describing schemas.
- `gmail_send_email` successfully delivers an email from the configured account.
- `gmail_create_draft` creates a visible Gmail draft (used by the review-pulse agent to draft its weekly email).
- `gdoc_append_content` appends text to a specified doc, verifiable by reopening it (used by the review-pulse agent to publish its weekly note).
- Errors (bad doc ID, invalid email, expired auth) return structured, human-readable messages, not crashes.
- The server works correctly when called by more than one type of MCP client — proving it isn't secretly coupled to the review-pulse agent.

## 9. Open Questions

- Per-user OAuth (each caller connects their own account) or a single shared service account for this server?
- Is `gdoc_append_content`-only sufficient, or will the review-pulse agent (or others) eventually need "create new doc" too?
- What transport does Antigravity expect by default (stdio vs HTTP/SSE)?
- Any need for a "send with scheduling" mode later, or is immediate send + draft sufficient indefinitely?

## 10. Suggested Milestones

1. **M1:** MCP server scaffolding + tool discovery (mocked responses, no real Google calls).
2. **M2:** Google OAuth integration + `gmail_send_email` working end-to-end.
3. **M3:** `gmail_create_draft` implemented.
4. **M4:** `gdoc_append_content` implemented.
5. **M5:** Error handling, logging, retry logic, docs.
6. **M6:** Verify genericity by testing with at least two different MCP clients (e.g., a simple test client + the review-pulse agent).
