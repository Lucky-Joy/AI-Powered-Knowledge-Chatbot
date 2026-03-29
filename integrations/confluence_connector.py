"""
Confluence Connector — KnowSure Enterprise Integration.

Connects to Atlassian Confluence to ingest SOPs, runbooks,
internal wikis, and operational guides stored as Confluence pages.

Current status: STUB IMPLEMENTATION
Full implementation requires:
  - Atlassian API token (per-user or service account)
  - Confluence base URL and space keys

Production implementation will use Confluence REST API v2:
  https://{domain}.atlassian.net/wiki/api/v2/pages

Environment variables required for production:
  CONFLUENCE_BASE_URL
  CONFLUENCE_EMAIL
  CONFLUENCE_API_TOKEN
  CONFLUENCE_SPACE_KEYS  (comma-separated)
"""

from __future__ import annotations
import os
from integrations.base_connector import BaseConnector


class ConfluenceConnector(BaseConnector):
    """
    Connector for Atlassian Confluence wiki pages.
    Stub implementation — demonstrates integration design.
    """

    SYSTEM_NAME = "Atlassian Confluence"

    def __init__(self):
        super().__init__(config={
            "base_url":    os.getenv("CONFLUENCE_BASE_URL", ""),
            "email":       os.getenv("CONFLUENCE_EMAIL", ""),
            "api_token":   os.getenv("CONFLUENCE_API_TOKEN", ""),
            "space_keys":  os.getenv("CONFLUENCE_SPACE_KEYS", "").split(","),
        })

    def connect(self) -> bool:
        """
        STUB: Authenticate with Confluence using Basic Auth (email + API token).
        Production: GET /wiki/rest/api/space to verify credentials.
        """
        print(f"[STUB] Confluence: connecting to {self.config.get('base_url', 'not configured')}")
        print("[STUB] Confluence: Basic Auth with API token — not yet implemented.")
        print("[STUB] Confluence: Set CONFLUENCE_BASE_URL, EMAIL, API_TOKEN to enable.")
        self.connected = True
        return True

    def list_documents(self, folder: str | None = None) -> list[dict]:
        """
        STUB: Returns mock Confluence page listing.
        Production: GET /wiki/api/v2/pages?spaceKey={key}
        """
        return [
            {
                "id":          "conf-page-001",
                "title":       "Account Opening SOP v2.1",
                "modified_at": "2024-09-20T14:00:00Z",
                "file_type":   "html",
                "source":      self.SYSTEM_NAME,
            },
            {
                "id":          "conf-page-002",
                "title":       "Exception Handling Runbook",
                "modified_at": "2024-08-10T11:00:00Z",
                "file_type":   "html",
                "source":      self.SYSTEM_NAME,
            },
        ]

    def download_document(self, document_id: str) -> bytes:
        """
        STUB: Returns empty bytes.
        Production: GET /wiki/rest/api/content/{id}?expand=body.storage
        Then convert HTML body to plain text for ingestion.
        """
        print(f"[STUB] Confluence: download_document({document_id}) — not yet implemented.")
        return b""

    def get_document_metadata(self, document_id: str) -> dict:
        return {
            "id":            document_id,
            "title":         f"Confluence Page {document_id}",
            "version":       "1.0",
            "modified_at":   "2024-01-01T00:00:00Z",
            "author":        "Unknown",
            "file_type":     "html",
            "source_system": self.SYSTEM_NAME,
        }