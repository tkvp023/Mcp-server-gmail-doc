"""
MCP Server for Gmail & Google Docs.

Exposes three tools via the Model Context Protocol:
- gmail_send_email: Send an email immediately
- gmail_create_draft: Create a draft email
- gdoc_append_content: Append text to an existing Google Doc

Uses FastMCP from the official MCP Python SDK with stdio transport.
"""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.config import configure_logging, validate_config, MCP_TRANSPORT, PORT, HOST
from src import gmail_client, gdoc_client

# Configure logging before anything else
configure_logging()
logger = logging.getLogger(__name__)

# Validate configuration on import
try:
    validate_config()
except FileNotFoundError as e:
    logger.error(str(e))
    raise

# Initialize MCP server
mcp = FastMCP("google-workspace")


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def _validate_email_inputs(
    to: str | list[str],
    subject: str,
    body: str,
    body_type: str,
) -> str | None:
    """
    Validate common email inputs. Returns an error message if invalid,
    or None if everything is OK.
    """
    if not to:
        return "Parameter 'to' is required and cannot be empty."

    if isinstance(to, list) and len(to) == 0:
        return "Parameter 'to' list cannot be empty."

    if not subject or not subject.strip():
        return "Parameter 'subject' is required and cannot be empty."

    if not body:
        return "Parameter 'body' is required and cannot be empty."

    if body_type not in ("text", "html"):
        return f"Parameter 'body_type' must be 'text' or 'html', got '{body_type}'."

    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def gmail_send_email(
    to: str | list[str],
    subject: str,
    body: str,
    cc: Optional[list[str]] = None,
    bcc: Optional[list[str]] = None,
    body_type: str = "text",
) -> dict:
    """
    Send an email immediately via the authenticated Gmail account.

    Args:
        to: Recipient email address or list of addresses.
        subject: Email subject line.
        body: Email body content (plain text or HTML).
        cc: CC recipients (optional).
        bcc: BCC recipients (optional).
        body_type: 'text' for plain text or 'html' for HTML (default: 'text').

    Returns:
        A dict with 'status' ('success' or 'error'), 'message_id' on success,
        or 'error_message' on error.
    """
    logger.info(
        "gmail_send_email called: to=%s, subject=%s, body_type=%s",
        to, subject, body_type
    )

    # Validate inputs
    error = _validate_email_inputs(to, subject, body, body_type)
    if error:
        logger.warning("Input validation failed: %s", error)
        return {"status": "error", "error_message": error}

    result = gmail_client.send_email(
        to=to, subject=subject, body=body,
        cc=cc, bcc=bcc, body_type=body_type,
    )

    logger.info("gmail_send_email result: status=%s", result.get("status"))
    return result


@mcp.tool()
def gmail_create_draft(
    to: str | list[str],
    subject: str,
    body: str,
    cc: Optional[list[str]] = None,
    bcc: Optional[list[str]] = None,
    body_type: str = "text",
) -> dict:
    """
    Create a draft email in Gmail without sending it.

    Args:
        to: Recipient email address or list of addresses.
        subject: Email subject line.
        body: Email body content (plain text or HTML).
        cc: CC recipients (optional).
        bcc: BCC recipients (optional).
        body_type: 'text' for plain text or 'html' for HTML (default: 'text').

    Returns:
        A dict with 'status' ('success' or 'error'), 'draft_id' on success,
        or 'error_message' on error.
    """
    logger.info(
        "gmail_create_draft called: to=%s, subject=%s, body_type=%s",
        to, subject, body_type
    )

    # Validate inputs
    error = _validate_email_inputs(to, subject, body, body_type)
    if error:
        logger.warning("Input validation failed: %s", error)
        return {"status": "error", "error_message": error}

    result = gmail_client.create_draft(
        to=to, subject=subject, body=body,
        cc=cc, bcc=bcc, body_type=body_type,
    )

    logger.info("gmail_create_draft result: status=%s", result.get("status"))
    return result


@mcp.tool()
def gdoc_append_content(
    document_id: str,
    content: str,
    add_newline_before: bool = True,
) -> dict:
    """
    Append text content to the end of an existing Google Doc.

    Args:
        document_id: The Google Doc ID (found in the document URL).
        content: Text content to append to the document.
        add_newline_before: If True, prepend a newline before the content
            to separate it from existing text (default: True).

    Returns:
        A dict with 'status' ('success' or 'error'), 'document_id',
        'revision_id' on success, or 'error_message' on error.
    """
    logger.info(
        "gdoc_append_content called: document_id=%s, add_newline_before=%s",
        document_id, add_newline_before
    )

    # Validate inputs
    if not document_id or not document_id.strip():
        error = "Parameter 'document_id' is required and cannot be empty."
        logger.warning("Input validation failed: %s", error)
        return {"status": "error", "error_message": error}

    if not content:
        error = "Parameter 'content' is required and cannot be empty."
        logger.warning("Input validation failed: %s", error)
        return {"status": "error", "error_message": error}

    result = gdoc_client.append_content(
        document_id=document_id,
        content=content,
        add_newline_before=add_newline_before,
    )

    logger.info("gdoc_append_content result: status=%s", result.get("status"))
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if MCP_TRANSPORT == "streamable-http":
        logger.info(
            "Starting MCP Google Workspace server (HTTP transport on %s:%d)...",
            HOST, PORT
        )
        mcp.run(transport="streamable-http", host=HOST, port=PORT)
    else:
        logger.info("Starting MCP Google Workspace server (stdio transport)...")
        mcp.run(transport="stdio")
