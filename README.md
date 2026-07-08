# MCP Server for Gmail & Google Docs

A standalone **Model Context Protocol (MCP)** server that exposes tools for sending/drafting emails via Gmail and appending content to Google Docs. Built with the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) using `FastMCP`.

## Features

| Tool | Description |
|------|-------------|
| `gmail_send_email` | Send an email immediately via Gmail |
| `gmail_create_draft` | Create a draft email (no auto-send) |
| `gdoc_append_content` | Append text to an existing Google Doc |

- **Generic & reusable** — works with any MCP-compatible client
- **OAuth 2.0** — browser-based consent flow, auto-refresh tokens
- **Structured responses** — always returns `status` + IDs or `error_message`
- **Retry logic** — exponential backoff on rate limits and server errors
- **Secure** — credentials never logged, secrets gitignored

## Prerequisites

- **Python 3.10+**
- **Google Cloud project** with Gmail API and Google Docs API enabled
- **OAuth credentials** (`credentials.json`) downloaded from Google Cloud Console

## Setup

### 1. Google Cloud Configuration

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services > Library**
4. Enable **Gmail API** and **Google Docs API**
5. Go to **APIs & Services > OAuth consent screen**
   - Set up the consent screen
   - Add your email as a **test user**
6. Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Select **Desktop app**
   - Download the JSON file and save it as `credentials.json` in the project root

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment (Optional)

```bash
cp .env.example .env
# Edit .env if you need custom paths
```

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_CREDENTIALS_PATH` | `./credentials.json` | Path to OAuth client secrets |
| `GOOGLE_TOKEN_PATH` | `./token.json` | Path to cached token |
| `LOG_LEVEL` | `INFO` | Logging level |

### 4. First Run (OAuth Consent)

```bash
python -m src.server
```

On the first run, a browser window will open asking you to authorize the app. After granting access, a `token.json` file will be created and future runs will not require re-authorization.

## Usage

### Running the Server

```bash
python -m src.server
```

The server communicates over **stdio** using the MCP protocol.

### Connecting from an MCP Client

#### Antigravity / Claude Desktop

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/MCP-SERVER"
    }
  }
}
```

### Tool Schemas

#### `gmail_send_email`

```json
{
  "to": "recipient@example.com",
  "subject": "Hello from MCP",
  "body": "This is a test email.",
  "cc": ["cc@example.com"],
  "bcc": ["bcc@example.com"],
  "body_type": "text"
}
```

**Response (success):**
```json
{"status": "success", "message_id": "18a1b2c3d4e5f6"}
```

#### `gmail_create_draft`

Same input schema as `gmail_send_email`.

**Response (success):**
```json
{"status": "success", "draft_id": "r123456789"}
```

#### `gdoc_append_content`

```json
{
  "document_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
  "content": "Text to append at the end of the document.",
  "add_newline_before": true
}
```

**Response (success):**
```json
{"status": "success", "document_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz", "revision_id": "ALm37BWx..."}
```

#### Error Response (all tools)

```json
{"status": "error", "error_message": "Document not found: bad_id_123"}
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src
```

## Architecture

```
[Any MCP Client]
      |
      | MCP protocol (stdio)
      v
[MCP Server: google-workspace]
   ├── server.py      → Tool definitions + input validation
   ├── auth.py        → OAuth2 token management + refresh
   ├── gmail_client.py → Gmail API (send, draft)
   ├── gdoc_client.py  → Docs API (append)
   └── config.py      → Environment configuration
      |
      v
[Google Workspace APIs]
```

## Project Structure

```
MCP-SERVER/
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .gitignore              # Secrets & cache exclusions
├── README.md               # This file
├── credentials.json        # (user-provided, gitignored)
├── token.json              # (auto-generated, gitignored)
├── src/
│   ├── __init__.py
│   ├── server.py           # FastMCP server + tools
│   ├── auth.py             # OAuth2 authentication
│   ├── gmail_client.py     # Gmail API wrapper
│   ├── gdoc_client.py      # Google Docs API wrapper
│   └── config.py           # Configuration loading
└── tests/
    ├── __init__.py
    ├── test_server.py       # Tool + validation tests
    ├── test_gmail_client.py # Gmail client tests
    └── test_gdoc_client.py  # Docs client tests
```

## License

MIT
