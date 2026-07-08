"""
Gmail API client module.

Provides functions for sending emails and creating drafts
via the Gmail API. All functions return structured dicts
with status, IDs, and error messages — never raise exceptions.
"""

import base64
import logging
import time
import functools
from email.message import EmailMessage

from googleapiclient.errors import HttpError

from src.auth import build_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def _retryable(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for exponential backoff on retryable Google API errors.

    Retries on:
        - 429 (Rate limit)
        - 5xx (Server errors)

    Non-retryable errors (400, 401, 403, 404) are returned immediately.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except HttpError as e:
                    status_code = e.resp.status
                    if status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            "Retryable error %d on attempt %d/%d for %s. "
                            "Retrying in %.1fs...",
                            status_code, attempt + 1, max_retries, func.__name__, delay
                        )
                        time.sleep(delay)
                    else:
                        raise
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Gmail service (lazy singleton)
# ---------------------------------------------------------------------------

_gmail_service = None


def _get_gmail_service():
    """Get or create the Gmail API service client."""
    global _gmail_service
    if _gmail_service is None:
        _gmail_service = build_service("gmail", "v1")
    return _gmail_service


# ---------------------------------------------------------------------------
# Message construction
# ---------------------------------------------------------------------------

def _build_message(
    to: str | list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    body_type: str = "text",
) -> str:
    """
    Build a base64url-encoded email message.

    Args:
        to: Recipient email address(es).
        subject: Email subject line.
        body: Email body content.
        cc: CC recipients.
        bcc: BCC recipients.
        body_type: 'text' for plain text, 'html' for HTML.

    Returns:
        Base64url-encoded message string.
    """
    message = EmailMessage()

    # Set body content
    if body_type == "html":
        message.set_content(body, subtype="html")
    else:
        message.set_content(body)

    # Set headers
    if isinstance(to, list):
        message["To"] = ", ".join(to)
    else:
        message["To"] = to

    message["Subject"] = subject

    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)

    # Base64url encode
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return raw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@_retryable()
def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    body_type: str = "text",
) -> dict:
    """
    Send an email immediately via the authenticated Gmail account.

    Args:
        to: Recipient email address(es).
        subject: Email subject line.
        body: Email body content (plain text or HTML).
        cc: CC recipients (optional).
        bcc: BCC recipients (optional).
        body_type: 'text' or 'html' (default: 'text').

    Returns:
        dict with:
            - status: 'success' or 'error'
            - message_id: Gmail message ID (on success)
            - error_message: Error description (on error)
    """
    try:
        raw = _build_message(to, subject, body, cc, bcc, body_type)
        service = _get_gmail_service()

        result = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )

        message_id = result.get("id", "")
        logger.info("Email sent successfully. Message ID: %s", message_id)
        return {"status": "success", "message_id": message_id}

    except HttpError as e:
        error_msg = f"Gmail API error ({e.resp.status}): {e.reason}"
        logger.error("Failed to send email: %s", error_msg)
        return {"status": "error", "error_message": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error sending email: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "error_message": error_msg}


@_retryable()
def create_draft(
    to: str | list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    body_type: str = "text",
) -> dict:
    """
    Create a draft email in Gmail without sending it.

    Args:
        to: Recipient email address(es).
        subject: Email subject line.
        body: Email body content (plain text or HTML).
        cc: CC recipients (optional).
        bcc: BCC recipients (optional).
        body_type: 'text' or 'html' (default: 'text').

    Returns:
        dict with:
            - status: 'success' or 'error'
            - draft_id: Gmail draft ID (on success)
            - error_message: Error description (on error)
    """
    try:
        raw = _build_message(to, subject, body, cc, bcc, body_type)
        service = _get_gmail_service()

        result = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )

        draft_id = result.get("id", "")
        logger.info("Draft created successfully. Draft ID: %s", draft_id)
        return {"status": "success", "draft_id": draft_id}

    except HttpError as e:
        error_msg = f"Gmail API error ({e.resp.status}): {e.reason}"
        logger.error("Failed to create draft: %s", error_msg)
        return {"status": "error", "error_message": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error creating draft: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "error_message": error_msg}
