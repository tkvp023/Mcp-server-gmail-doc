"""
Google Docs API client module.

Provides functions for appending content to existing Google Docs.
All functions return structured dicts with status, IDs, and error
messages — never raise exceptions.
"""

import logging
import time
import functools

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
# Docs service (lazy singleton)
# ---------------------------------------------------------------------------

_docs_service = None


def _get_docs_service():
    """Get or create the Google Docs API service client."""
    global _docs_service
    if _docs_service is None:
        _docs_service = build_service("docs", "v1")
    return _docs_service


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@_retryable()
def append_content(
    document_id: str,
    content: str,
    add_newline_before: bool = True,
) -> dict:
    """
    Append text content to the end of an existing Google Doc.

    This works by:
    1. Fetching the document to determine the current end index
    2. Inserting text at that position via batchUpdate

    Args:
        document_id: The Google Doc ID (from the URL).
        content: Text content to append.
        add_newline_before: If True, prepend a newline before the content
            to separate it from existing text (default: True).

    Returns:
        dict with:
            - status: 'success' or 'error'
            - document_id: The document ID
            - revision_id: The new revision ID (if available)
            - error_message: Error description (on error)
    """
    try:
        service = _get_docs_service()

        # Step 1: Get current document to find end index
        doc = service.documents().get(documentId=document_id).execute()
        body_content = doc.get("body", {}).get("content", [])

        if not body_content:
            return {
                "status": "error",
                "document_id": document_id,
                "error_message": "Document body is empty or has unexpected structure.",
            }

        # The end index of the last element, minus 1 (to stay before the trailing newline)
        end_index = body_content[-1]["endIndex"] - 1

        # Step 2: Prepare the text to insert
        text_to_insert = content
        if add_newline_before and end_index > 1:
            text_to_insert = "\n" + content

        # Step 3: Insert text at the end
        requests = [
            {
                "insertText": {
                    "location": {"index": end_index},
                    "text": text_to_insert,
                }
            }
        ]

        result = (
            service.documents()
            .batchUpdate(documentId=document_id, body={"requests": requests})
            .execute()
        )

        revision_id = result.get("writeControl", {}).get("requiredRevisionId", "")

        logger.info(
            "Content appended to document %s (revision: %s)",
            document_id, revision_id
        )

        return {
            "status": "success",
            "document_id": document_id,
            "revision_id": revision_id,
        }

    except HttpError as e:
        status_code = e.resp.status
        if status_code == 404:
            error_msg = f"Document not found: {document_id}"
        elif status_code == 403:
            error_msg = f"Access denied to document: {document_id}"
        else:
            error_msg = f"Google Docs API error ({status_code}): {e.reason}"

        logger.error("Failed to append content: %s", error_msg)
        return {
            "status": "error",
            "document_id": document_id,
            "error_message": error_msg,
        }
    except Exception as e:
        error_msg = f"Unexpected error appending to document: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "document_id": document_id,
            "error_message": error_msg,
        }
