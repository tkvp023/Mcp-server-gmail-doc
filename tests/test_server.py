"""
Unit tests for the MCP server tool definitions.

Tests input validation and tool wiring — all external
API calls are mocked.
"""

from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# We need to mock validate_config before importing server,
# since it runs on import and would fail without credentials.json
# ---------------------------------------------------------------------------

with patch("src.config.validate_config"):
    from src.server import (
        gmail_send_email,
        gmail_create_draft,
        gdoc_append_content,
        _validate_email_inputs,
    )


# ---------------------------------------------------------------------------
# Tests: Input validation
# ---------------------------------------------------------------------------

class TestValidateEmailInputs:
    """Tests for the _validate_email_inputs helper."""

    def test_valid_inputs(self):
        assert _validate_email_inputs("a@b.com", "Sub", "Body", "text") is None

    def test_valid_inputs_html(self):
        assert _validate_email_inputs("a@b.com", "Sub", "<p>Body</p>", "html") is None

    def test_empty_to(self):
        result = _validate_email_inputs("", "Sub", "Body", "text")
        assert result is not None
        assert "to" in result.lower()

    def test_empty_to_list(self):
        result = _validate_email_inputs([], "Sub", "Body", "text")
        assert result is not None

    def test_empty_subject(self):
        result = _validate_email_inputs("a@b.com", "", "Body", "text")
        assert result is not None
        assert "subject" in result.lower()

    def test_whitespace_subject(self):
        result = _validate_email_inputs("a@b.com", "   ", "Body", "text")
        assert result is not None

    def test_empty_body(self):
        result = _validate_email_inputs("a@b.com", "Sub", "", "text")
        assert result is not None
        assert "body" in result.lower()

    def test_invalid_body_type(self):
        result = _validate_email_inputs("a@b.com", "Sub", "Body", "markdown")
        assert result is not None
        assert "body_type" in result.lower()


# ---------------------------------------------------------------------------
# Tests: gmail_send_email tool
# ---------------------------------------------------------------------------

class TestGmailSendEmailTool:
    """Tests for the gmail_send_email MCP tool."""

    @patch("src.server.gmail_client")
    def test_send_success(self, mock_gmail):
        mock_gmail.send_email.return_value = {
            "status": "success", "message_id": "msg_001"
        }

        result = gmail_send_email("test@example.com", "Hello", "World")

        assert result["status"] == "success"
        assert result["message_id"] == "msg_001"
        mock_gmail.send_email.assert_called_once()

    def test_send_invalid_to(self):
        result = gmail_send_email("", "Subject", "Body")
        assert result["status"] == "error"
        assert "to" in result["error_message"].lower()

    def test_send_invalid_body_type(self):
        result = gmail_send_email("a@b.com", "Sub", "Body", body_type="xml")
        assert result["status"] == "error"
        assert "body_type" in result["error_message"].lower()

    @patch("src.server.gmail_client")
    def test_send_with_cc_bcc(self, mock_gmail):
        mock_gmail.send_email.return_value = {
            "status": "success", "message_id": "msg_002"
        }

        result = gmail_send_email(
            "to@test.com", "Sub", "Body",
            cc=["cc@test.com"], bcc=["bcc@test.com"]
        )

        assert result["status"] == "success"
        mock_gmail.send_email.assert_called_once_with(
            to="to@test.com", subject="Sub", body="Body",
            cc=["cc@test.com"], bcc=["bcc@test.com"], body_type="text"
        )


# ---------------------------------------------------------------------------
# Tests: gmail_create_draft tool
# ---------------------------------------------------------------------------

class TestGmailCreateDraftTool:
    """Tests for the gmail_create_draft MCP tool."""

    @patch("src.server.gmail_client")
    def test_draft_success(self, mock_gmail):
        mock_gmail.create_draft.return_value = {
            "status": "success", "draft_id": "draft_001"
        }

        result = gmail_create_draft("test@example.com", "Draft", "Content")

        assert result["status"] == "success"
        assert result["draft_id"] == "draft_001"

    def test_draft_empty_subject(self):
        result = gmail_create_draft("a@b.com", "", "Body")
        assert result["status"] == "error"

    def test_draft_empty_body(self):
        result = gmail_create_draft("a@b.com", "Sub", "")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests: gdoc_append_content tool
# ---------------------------------------------------------------------------

class TestGdocAppendContentTool:
    """Tests for the gdoc_append_content MCP tool."""

    @patch("src.server.gdoc_client")
    def test_append_success(self, mock_gdoc):
        mock_gdoc.append_content.return_value = {
            "status": "success",
            "document_id": "doc_001",
            "revision_id": "rev_001",
        }

        result = gdoc_append_content("doc_001", "New text")

        assert result["status"] == "success"
        assert result["document_id"] == "doc_001"

    def test_append_empty_document_id(self):
        result = gdoc_append_content("", "Content")
        assert result["status"] == "error"
        assert "document_id" in result["error_message"].lower()

    def test_append_whitespace_document_id(self):
        result = gdoc_append_content("   ", "Content")
        assert result["status"] == "error"

    def test_append_empty_content(self):
        result = gdoc_append_content("doc_001", "")
        assert result["status"] == "error"
        assert "content" in result["error_message"].lower()

    @patch("src.server.gdoc_client")
    def test_append_no_newline(self, mock_gdoc):
        mock_gdoc.append_content.return_value = {
            "status": "success",
            "document_id": "doc_001",
            "revision_id": "",
        }

        result = gdoc_append_content("doc_001", "Text", add_newline_before=False)

        assert result["status"] == "success"
        mock_gdoc.append_content.assert_called_once_with(
            document_id="doc_001",
            content="Text",
            add_newline_before=False,
        )
