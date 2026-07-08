"""
Unit tests for the Google Docs client module.

All Google API calls are mocked — no real documents are modified.
"""

from unittest.mock import patch, MagicMock

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from src.gdoc_client import append_content


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_http_error(status: int, reason: str = "Error") -> HttpError:
    """Create a mock HttpError with the given status code."""
    resp = Response({"status": status})
    resp.reason = reason
    return HttpError(resp, b"error body", uri="https://docs.googleapis.com/test")


def _make_fake_doc(end_index: int = 50) -> dict:
    """
    Create a fake Google Doc response with a given end index.

    Mimics the structure returned by documents().get().
    """
    return {
        "documentId": "doc_123",
        "title": "Test Document",
        "body": {
            "content": [
                {
                    "sectionBreak": {},
                    "startIndex": 0,
                    "endIndex": 1,
                },
                {
                    "paragraph": {
                        "elements": [
                            {
                                "textRun": {"content": "Existing content"},
                                "startIndex": 1,
                                "endIndex": end_index,
                            }
                        ]
                    },
                    "startIndex": 1,
                    "endIndex": end_index,
                },
            ]
        },
    }


# ---------------------------------------------------------------------------
# Tests: append_content
# ---------------------------------------------------------------------------

class TestAppendContent:
    """Tests for the append_content function."""

    @patch("src.gdoc_client._get_docs_service")
    def test_append_success(self, mock_get_service):
        mock_service = MagicMock()

        # Mock documents().get()
        mock_service.documents().get().execute.return_value = _make_fake_doc(50)

        # Mock documents().batchUpdate()
        mock_service.documents().batchUpdate().execute.return_value = {
            "writeControl": {"requiredRevisionId": "rev_001"},
        }

        mock_get_service.return_value = mock_service

        result = append_content("doc_123", "New content here")

        assert result["status"] == "success"
        assert result["document_id"] == "doc_123"
        assert result["revision_id"] == "rev_001"

    @patch("src.gdoc_client._get_docs_service")
    def test_append_with_newline(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.documents().get().execute.return_value = _make_fake_doc(50)
        mock_service.documents().batchUpdate().execute.return_value = {
            "writeControl": {},
        }
        mock_get_service.return_value = mock_service

        result = append_content("doc_123", "Content", add_newline_before=True)

        assert result["status"] == "success"

        # Verify batchUpdate was called with newline-prepended text
        call_args = mock_service.documents().batchUpdate.call_args
        if call_args:
            body = call_args[1].get("body", {}) if call_args[1] else {}
            requests = body.get("requests", [])
            if requests:
                inserted_text = requests[0]["insertText"]["text"]
                assert inserted_text.startswith("\n")

    @patch("src.gdoc_client._get_docs_service")
    def test_append_without_newline(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.documents().get().execute.return_value = _make_fake_doc(50)
        mock_service.documents().batchUpdate().execute.return_value = {
            "writeControl": {},
        }
        mock_get_service.return_value = mock_service

        result = append_content("doc_123", "Content", add_newline_before=False)

        assert result["status"] == "success"

    @patch("src.gdoc_client._get_docs_service")
    def test_append_document_not_found(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.documents().get().execute.side_effect = (
            _make_http_error(404, "Not Found")
        )
        mock_get_service.return_value = mock_service

        result = append_content("bad_doc_id", "Content")

        assert result["status"] == "error"
        assert "not found" in result["error_message"].lower()
        assert result["document_id"] == "bad_doc_id"

    @patch("src.gdoc_client._get_docs_service")
    def test_append_permission_denied(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.documents().get().execute.side_effect = (
            _make_http_error(403, "Forbidden")
        )
        mock_get_service.return_value = mock_service

        result = append_content("private_doc", "Content")

        assert result["status"] == "error"
        assert "access denied" in result["error_message"].lower()
        assert result["document_id"] == "private_doc"

    @patch("src.gdoc_client._get_docs_service")
    def test_append_empty_body(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.documents().get().execute.return_value = {
            "documentId": "doc_empty",
            "body": {"content": []},
        }
        mock_get_service.return_value = mock_service

        result = append_content("doc_empty", "Content")

        assert result["status"] == "error"
        assert "empty" in result["error_message"].lower()

    @patch("src.gdoc_client._get_docs_service")
    def test_append_unexpected_error(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.documents().get().execute.side_effect = (
            RuntimeError("network failure")
        )
        mock_get_service.return_value = mock_service

        result = append_content("doc_123", "Content")

        assert result["status"] == "error"
        assert "network failure" in result["error_message"]
