"""
Google OAuth 2.0 authentication module.

Handles the full credential lifecycle:
- Load cached tokens from disk (or temp files from env vars)
- Auto-refresh expired tokens
- Run browser-based consent flow for first-time auth (local only)
- Build authenticated Google API service clients

In cloud mode (Railway), the browser consent flow is disabled.
The token must be pre-generated locally and injected via env var.
"""

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource

from src.config import (
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_PATH,
    GOOGLE_SCOPES,
    CLOUD_MODE,
)

logger = logging.getLogger(__name__)


def get_credentials() -> Credentials:
    """
    Obtain valid Google OAuth 2.0 credentials.

    Flow:
    1. Check for cached token.json -> load and verify
    2. If expired but has refresh token -> auto-refresh
    3. If no token exists AND local mode -> run browser consent flow
    4. If no token exists AND cloud mode -> raise error
    5. Save new/refreshed token to disk (local mode only)

    Returns:
        Valid Google OAuth2 Credentials object.

    Raises:
        FileNotFoundError: If credentials.json is missing.
        RuntimeError: If cloud mode and no valid token is available.
        google.auth.exceptions.RefreshError: If token refresh fails
            and re-authentication is needed.
    """
    creds = None
    token_path = Path(GOOGLE_TOKEN_PATH)
    creds_path = Path(GOOGLE_CREDENTIALS_PATH)

    # Step 1: Try to load cached token
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(token_path), GOOGLE_SCOPES
            )
            logger.info("Loaded cached credentials from %s", token_path)
        except Exception as e:
            logger.warning("Failed to load cached token: %s", e)
            creds = None

    # Step 2: Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Successfully refreshed expired credentials")
            # Save refreshed token (local mode only)
            if not CLOUD_MODE:
                _save_token(creds, token_path)
        except Exception as e:
            logger.warning("Token refresh failed: %s -- will re-authenticate", e)
            creds = None

    # Step 3: Re-authenticate if needed
    if not creds or not creds.valid:
        if CLOUD_MODE:
            # In cloud mode, we cannot open a browser for OAuth consent
            raise RuntimeError(
                "No valid Google credentials available in cloud mode. "
                "The token has expired and cannot be refreshed. "
                "Please re-generate token.json locally by running "
                "'python auth_setup.py' and update the GOOGLE_TOKEN_JSON "
                "environment variable with the new contents."
            )

        if not creds_path.exists():
            raise FileNotFoundError(
                f"Google OAuth credentials file not found at '{creds_path.resolve()}'.\n"
                f"Download it from Google Cloud Console > APIs & Services > Credentials."
            )

        logger.info("Starting browser-based OAuth consent flow...")
        flow = InstalledAppFlow.from_client_secrets_file(
            str(creds_path), GOOGLE_SCOPES
        )
        creds = flow.run_local_server(port=0)
        logger.info("OAuth consent flow completed successfully")

        # Save new token
        _save_token(creds, token_path)

    return creds


def _save_token(creds: Credentials, token_path: Path) -> None:
    """Save credentials to disk for caching."""
    try:
        token_path.write_text(creds.to_json())
        logger.info("Saved credentials to %s", token_path)
    except Exception as e:
        logger.error("Failed to save token to %s: %s", token_path, e)


def build_service(api_name: str, version: str) -> Resource:
    """
    Build an authenticated Google API service client.

    Args:
        api_name: Google API name (e.g., 'gmail', 'docs').
        version: API version (e.g., 'v1').

    Returns:
        Authenticated Google API Resource object.
    """
    creds = get_credentials()
    service = build(api_name, version, credentials=creds)
    logger.info("Built %s %s service client", api_name, version)
    return service
