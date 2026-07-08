"""
Configuration module for the MCP Server.

Loads settings from environment variables with .env fallback.
Supports both file-based credentials (local dev) and env var JSON
(cloud deployment on Railway/Render/etc).
"""

import os
import json
import logging
import tempfile
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# --- Transport ---
MCP_TRANSPORT: str = os.getenv("MCP_TRANSPORT", "stdio")
PORT: int = int(os.getenv("PORT", "8000"))
HOST: str = os.getenv("HOST", "0.0.0.0")

# --- Credential resolution ---
# Priority: env var JSON > file path
# This allows Railway (no filesystem) to inject credentials as env vars,
# while local dev continues using files.

_credentials_json_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
_token_json_env = os.getenv("GOOGLE_TOKEN_JSON")


def _write_env_json_to_tempfile(json_content: str, filename: str) -> str:
    """
    Write JSON content from an env var to a temp file and return the path.

    This bridges the gap between Railway (env vars only) and the Google
    client libraries (which expect file paths).
    """
    tmp_dir = tempfile.gettempdir()
    filepath = os.path.join(tmp_dir, filename)
    with open(filepath, "w") as f:
        f.write(json_content)
    return filepath


# Resolve credentials path
if _credentials_json_env:
    GOOGLE_CREDENTIALS_PATH: str = _write_env_json_to_tempfile(
        _credentials_json_env, "mcp_credentials.json"
    )
    CREDENTIALS_FROM_ENV = True
else:
    GOOGLE_CREDENTIALS_PATH: str = os.getenv(
        "GOOGLE_CREDENTIALS_PATH", "./credentials.json"
    )
    CREDENTIALS_FROM_ENV = False

# Resolve token path
if _token_json_env:
    GOOGLE_TOKEN_PATH: str = _write_env_json_to_tempfile(
        _token_json_env, "mcp_token.json"
    )
    TOKEN_FROM_ENV = True
else:
    GOOGLE_TOKEN_PATH: str = os.getenv(
        "GOOGLE_TOKEN_PATH", "./token.json"
    )
    TOKEN_FROM_ENV = False

# --- Cloud mode detection ---
# Cloud mode = credentials loaded from env vars (no browser available)
CLOUD_MODE: bool = CREDENTIALS_FROM_ENV or TOKEN_FROM_ENV

# --- OAuth Scopes ---
_DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/documents",
]

_scopes_env = os.getenv("GOOGLE_SCOPES")
GOOGLE_SCOPES: list[str] = (
    [s.strip() for s in _scopes_env.split(",") if s.strip()]
    if _scopes_env
    else _DEFAULT_SCOPES
)

# --- Logging ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


def configure_logging() -> None:
    """
    Configure logging to write to stderr only.

    This is critical for stdio transport -- stdout is reserved
    for MCP JSON-RPC communication.
    """
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],  # defaults to stderr
    )


def validate_config() -> None:
    """
    Validate that required configuration files exist.

    In cloud mode (env var JSON), the temp files are already written
    so this check will pass. In local mode, raises FileNotFoundError
    with a clear message if credentials.json is missing.
    """
    creds_path = Path(GOOGLE_CREDENTIALS_PATH)
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Google OAuth credentials file not found at '{creds_path.resolve()}'.\n"
            f"Download it from Google Cloud Console > APIs & Services > Credentials\n"
            f"and place it at: {creds_path.resolve()}\n"
            f"Or set GOOGLE_CREDENTIALS_JSON env var with the JSON content."
        )
