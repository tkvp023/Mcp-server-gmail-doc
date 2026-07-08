"""
Unit tests for the Gmail client module.

All Google API calls are mocked — no real emails are sent.
"""

import base64
from unittest.mock import patch, MagicMock
from email import message_from_bytes

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from src.gmail_client import send_email, create_draft, _build_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_http_error(status: int, reason: str = "Error") -> HttpError:
    """Create a mock HttpError with the given status code."""
    resp = Response({"status": status})
    resp.reason = reason
    return HttpError(resp, b"error body", uri="https://gmail.googleapis.com/test")


def _decode_raw_message(raw: str) -> dict:
    """Decode a base64url-encoded email and return headers + body."""
    raw_bytes = base64.urlsafe_b64decode(raw.encode("utf-8"))
    msg = message_from_bytes(raw_bytes)
    return {
        "to": msg["To"],
        "subject": msg["Subject"],
        "cc": msg.get("Cc"),
        "bcc": msg.get("Bcc"),
        "body": msg.get_payload(decode=True).decode("utf-8") if msg.get_payload() else "",
    }


# ---------------------------------------------------------------------------
# Tests: Message construction
# ---------------------------------------------------------------------------

class TestBuildMessage:
    """Tests for _build_message helper."""

    def test_plain_text_message(self):
        raw = _build_message("test@example.com", "Hello", "World")
        decoded = _decode_raw_message(raw)
        assert decoded["to"] == "test@example.com"
        assert decoded["subject"] == "Hello"
        assert "World" in decoded["body"]

    def test_html_message(self):
        raw = _build_message(
            "test@example.com", "HTML Test", "<h1>Hello</h1>", body_type="html"
        )
        decoded = _decode_raw_message(raw)
        assert "<h1>Hello</h1>" in decoded["body"]

    def test_multiple_recipients(self):
        raw = _build_message(
            ["a@test.com", "b@test.com"], "Multi", "Body"
        )
        decoded = _decode_raw_message(raw)
        assert "a@test.com" in decoded["to"]
        assert "b@test.com" in decoded["to"]

    def test_cc_and_bcc(self):
        raw = _build_message(
            "to@test.com", "Sub", "Body",
            cc=["cc@test.com"],
            bcc=["bcc@test.com"],
        )
        decoded = _decode_raw_message(raw)
        assert decoded["cc"] == "cc@test.com"
        assert decoded["bcc"] == "bcc@test.com"

    def test_no_cc_bcc(self):
        raw = _build_message("to@test.com", "Sub", "Body")
        decoded = _decode_raw_message(raw)
        assert decoded["cc"] is None
        assert decoded["bcc"] is None


# ---------------------------------------------------------------------------
# Tests: send_email
# ---------------------------------------------------------------------------

class TestSendEmail:
    """Tests for the send_email function."""

    @patch("src.gmail_client._get_gmail_service")
    def test_send_success(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.return_value = {
            "id": "msg_123",
            "threadId": "thread_456",
        }
        mock_get_service.return_value = mock_service

        result = send_email("test@example.com", "Subject", "Body text")

        assert result["status"] == "success"
        assert result["message_id"] == "msg_123"

    @patch("src.gmail_client._get_gmail_service")
    def test_send_http_error_400(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.side_effect = (
            _make_http_error(400, "Bad Request")
        )
        mock_get_service.return_value = mock_service

        result = send_email("invalid", "Subject", "Body")

        assert result["status"] == "error"
        assert "400" in result["error_message"]

    @patch("src.gmail_client._get_gmail_service")
    def test_send_http_error_401(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.side_effect = (
            _make_http_error(401, "Unauthorized")
        )
        mock_get_service.return_value = mock_service

        result = send_email("test@example.com", "Subject", "Body")

        assert result["status"] == "error"
        assert "401" in result["error_message"]

    @patch("src.gmail_client._get_gmail_service")
    def test_send_unexpected_error(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.side_effect = (
            RuntimeError("connection lost")
        )
        mock_get_service.return_value = mock_service

        result = send_email("test@example.com", "Subject", "Body")

        assert result["status"] == "error"
        assert "connection lost" in result["error_message"]


# ---------------------------------------------------------------------------
# Tests: create_draft
# ---------------------------------------------------------------------------

class TestCreateDraft:
    """Tests for the create_draft function."""

    @patch("src.gmail_client._get_gmail_service")
    def test_draft_success(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.users().drafts().create().execute.return_value = {
            "id": "draft_789",
        }
        mock_get_service.return_value = mock_service

        result = create_draft("test@example.com", "Draft Subject", "Draft body")

        assert result["status"] == "success"
        assert result["draft_id"] == "draft_789"

    @patch("src.gmail_client._get_gmail_service")
    def test_draft_http_error(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.users().drafts().create().execute.side_effect = (
            _make_http_error(403, "Forbidden")
        )
        mock_get_service.return_value = mock_service

        result = create_draft("test@example.com", "Subject", "Body")

        assert result["status"] == "error"
        assert "403" in result["error_message"]

    @patch("src.gmail_client._get_gmail_service")
    def test_draft_html_body(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.users().drafts().create().execute.return_value = {
            "id": "draft_html",
        }
        mock_get_service.return_value = mock_service

        result = create_draft(
            "test@example.com", "HTML Draft", "<p>Hello</p>", body_type="html"
        )

        assert result["status"] == "success"
        assert result["draft_id"] == "draft_html"
