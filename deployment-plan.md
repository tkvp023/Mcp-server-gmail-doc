# Deployment Plan: MCP Server on Railway

Deploy the MCP Google Workspace server to [Railway](https://railway.com/) so that remote MCP clients can connect to it over the network.

---

## Key Challenge

The current server uses **stdio** transport (stdin/stdout), which only works when the client starts the server as a local subprocess. For Railway, we need to switch to **Streamable HTTP** transport so the server runs as a long-lived web service that clients connect to over HTTPS.

Additionally, the current auth module loads `credentials.json` and `token.json` from disk files. On Railway, there is no persistent filesystem, so we need to load these from **environment variables** instead.

---

## What Needs to Change

| Area | Current (Local) | Target (Railway) |
|------|-----------------|-------------------|
| **Transport** | `stdio` | `streamable-http` |
| **Port** | N/A | `$PORT` (Railway-assigned) |
| **Host** | N/A | `0.0.0.0` |
| **Credentials** | `credentials.json` file | `GOOGLE_CREDENTIALS_JSON` env var |
| **Token** | `token.json` file | `GOOGLE_TOKEN_JSON` env var |
| **Token persistence** | Write to disk | Write back to env var (not possible on Railway) -- use refresh token only |
| **OAuth consent flow** | Browser popup | Not possible on Railway -- token must be pre-generated locally |

---

## Pre-Deployment: Generate Token Locally

> [!IMPORTANT]
> Railway has no browser, so the OAuth consent flow **cannot** run in the cloud. You must generate `token.json` locally first (which you have already done), then paste its contents into a Railway environment variable.

You already have a valid `token.json` from the local setup. No action needed here.

---

## Step 1: Modify `src/config.py`

Add support for loading credentials and token from environment variables (as raw JSON strings), falling back to file paths for local development.

#### [MODIFY] [config.py](file:///c:/Users/THARUN/Videos/MCP-SERVER/src/config.py)

Add these new environment variables:

| Variable | Description |
|----------|-------------|
| `GOOGLE_CREDENTIALS_JSON` | Raw JSON content of `credentials.json` (alternative to file path) |
| `GOOGLE_TOKEN_JSON` | Raw JSON content of `token.json` (alternative to file path) |
| `MCP_TRANSPORT` | Transport mode: `stdio` or `streamable-http` (default: `stdio`) |
| `PORT` | Port for HTTP transport (default: `8000`, Railway provides this) |
| `HOST` | Host to bind to (default: `0.0.0.0`) |

**Logic:**
- If `GOOGLE_CREDENTIALS_JSON` env var is set, write it to a temp file and use that path
- If `GOOGLE_TOKEN_JSON` env var is set, write it to a temp file and use that path
- Otherwise, fall back to `GOOGLE_CREDENTIALS_PATH` / `GOOGLE_TOKEN_PATH` (existing behavior)
- Skip `validate_config()` file check if using env var JSON mode

---

## Step 2: Modify `src/auth.py`

Update `get_credentials()` to handle the cloud scenario:
- When running on Railway, there's no browser for the consent flow
- If the token is expired and refresh fails, return a structured error instead of trying `InstalledAppFlow`
- Token saving: if running from env vars, log a warning that the refreshed token cannot be persisted (it will be refreshed in-memory on each restart)

---

## Step 3: Modify `src/server.py`

Update the entry point to support both transports:

```python
if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        port = int(os.getenv("PORT", "8000"))
        host = os.getenv("HOST", "0.0.0.0")
        logger.info("Starting MCP server (HTTP transport on %s:%d)...", host, port)
        mcp.run(transport="streamable-http", host=host, port=port)
    else:
        logger.info("Starting MCP server (stdio transport)...")
        mcp.run(transport="stdio")
```

This keeps backward compatibility -- local development still uses `stdio` by default.

---

## Step 4: Create `Dockerfile`

#### [NEW] [Dockerfile](file:///c:/Users/THARUN/Videos/MCP-SERVER/Dockerfile)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Railway provides $PORT at runtime
ENV MCP_TRANSPORT=streamable-http
ENV HOST=0.0.0.0

# Start the MCP server
CMD ["python", "-m", "src.server"]
```

---

## Step 5: Create `Procfile` (optional backup)

#### [NEW] [Procfile](file:///c:/Users/THARUN/Videos/MCP-SERVER/Procfile)

```
web: python -m src.server
```

---

## Step 6: Deploy to Railway

### 6.1 Push to GitHub

```bash
cd C:\Users\THARUN\Videos\MCP-SERVER
git init
git add .
git commit -m "MCP Server for Gmail & Google Docs"
git remote add origin https://github.com/<your-username>/mcp-google-workspace.git
git push -u origin main
```

### 6.2 Create Railway Project

1. Go to [railway.com](https://railway.com/) and sign in
2. Click **"New Project"** > **"Deploy from GitHub repo"**
3. Select your `mcp-google-workspace` repository
4. Railway will auto-detect the Dockerfile and start building

### 6.3 Set Environment Variables

In the Railway dashboard, go to your service > **Variables** tab and add:

| Variable | Value | How to get it |
|----------|-------|---------------|
| `MCP_TRANSPORT` | `streamable-http` | Fixed value |
| `GOOGLE_CREDENTIALS_JSON` | *(paste full contents of credentials.json)* | `cat credentials.json` |
| `GOOGLE_TOKEN_JSON` | *(paste full contents of token.json)* | `cat token.json` |
| `LOG_LEVEL` | `INFO` | Fixed value |

> [!WARNING]
> **Do NOT set `PORT`** -- Railway auto-injects this variable. Your code should read `os.getenv("PORT", "8000")`.

> [!CAUTION]
> **Security:** The `GOOGLE_TOKEN_JSON` contains your refresh token. Railway encrypts environment variables at rest, but treat this as a secret. Never log it or expose it in API responses.

### 6.4 Verify Deployment

Once Railway deploys successfully, it will assign a public URL like:
```
https://mcp-google-workspace-production.up.railway.app
```

The MCP endpoint will be at:
```
https://mcp-google-workspace-production.up.railway.app/mcp
```

---

## Step 7: Connect MCP Clients

### From Claude Desktop / Antigravity

Update your MCP client configuration to point to the Railway URL:

```json
{
  "mcpServers": {
    "google-workspace": {
      "type": "streamable-http",
      "url": "https://mcp-google-workspace-production.up.railway.app/mcp"
    }
  }
}
```

### From Python (programmatic client)

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("https://your-app.up.railway.app/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        print(tools)
```

---

## Summary of File Changes

| File | Action | What Changes |
|------|--------|--------------|
| `src/config.py` | MODIFY | Add env var JSON loading, transport/port/host settings |
| `src/auth.py` | MODIFY | Handle cloud mode (no browser consent, in-memory refresh) |
| `src/server.py` | MODIFY | Dual transport support (stdio + streamable-http) |
| `Dockerfile` | NEW | Container image for Railway |
| `Procfile` | NEW | Start command for Railway |
| `.gitignore` | MODIFY | Ensure `credentials.json` and `token.json` are excluded |

---

## Execution Order

| Step | Task | Time Estimate |
|------|------|---------------|
| 1 | Update `config.py` with env var JSON support | 5 min |
| 2 | Update `auth.py` for cloud mode | 5 min |
| 3 | Update `server.py` with dual transport | 2 min |
| 4 | Create `Dockerfile` | 2 min |
| 5 | Create `Procfile` | 1 min |
| 6 | Test locally with `MCP_TRANSPORT=streamable-http` | 5 min |
| 7 | Push to GitHub | 2 min |
| 8 | Deploy on Railway + set env vars | 5 min |
| 9 | Verify remote connection | 5 min |

**Total: ~30 minutes**

---

## Token Refresh Strategy

> [!NOTE]
> Google OAuth refresh tokens are long-lived (they don't expire unless revoked or unused for 6 months). When the access token expires (~1 hour), the server will automatically use the refresh token to get a new access token in-memory. This works seamlessly on Railway without needing to update the env var.
>
> However, if the refresh token itself is revoked (e.g., you change your Google password or revoke access), you will need to:
> 1. Re-run `python auth_setup.py` locally to generate a new `token.json`
> 2. Update the `GOOGLE_TOKEN_JSON` env var in Railway with the new contents
