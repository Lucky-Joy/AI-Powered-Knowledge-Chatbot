"""
CRM Connector — KnowSure Enterprise Integration.

Connects to CRM systems (Salesforce / Microsoft Dynamics)
to ingest customer-facing policy documents, product rulebooks,
and service guidelines stored in the CRM knowledge base.

Current status: STUB IMPLEMENTATION
Full implementation requires CRM API credentials.

Environment variables required for production (Salesforce):
  CRM_PROVIDER          (salesforce | dynamics)
  SALESFORCE_INSTANCE_URL
  SALESFORCE_CLIENT_ID
  SALESFORCE_CLIENT_SECRET
"""

from __future__ import annotations
import os
from integrations.base_connector import BaseConnector


class CRMConnector(BaseConnector):
    """
    Connector for CRM knowledge base articles and product documents.
    Stub implementation — demonstrates integration design.
    """

    SYSTEM_NAME = "CRM Knowledge Base"

    def __init__(self):
        super().__init__(config={
            "provider":      os.getenv("CRM_PROVIDER", "salesforce"),
            "instance_url":  os.getenv("SALESFORCE_INSTANCE_URL", ""),
            "client_id":     os.getenv("SALESFORCE_CLIENT_ID", ""),
            "client_secret": os.getenv("SALESFORCE_CLIENT_SECRET", ""),
        })

    def connect(self) -> bool:
        """
        STUB: Authenticate with CRM using OAuth2.
        Production: POST to Salesforce OAuth token endpoint.
        """
        print(f"[STUB] CRM ({self.config.get('provider')}): connect() — not yet implemented.")
        print("[STUB] CRM: Set CRM_PROVIDER and credentials to enable.")
        self.connected = True
        return True

    def list_documents(self, folder: str | None = None) -> list[dict]:
        """
        STUB: Returns mock CRM knowledge article listing.
        Production (Salesforce): SOQL query on KnowledgeArticle object.
        """
        return [
            {
                "id":          "crm-art-001",
                "title":       "Product Rulebook — Savings Account",
                "modified_at": "2024-07-01T08:00:00Z",
                "file_type":   "pdf",
                "source":      self.SYSTEM_NAME,
            },
            {
                "id":          "crm-art-002",
                "title":       "Loan Product Guidelines 2024",
                "modified_at": "2024-06-15T12:00:00Z",
                "file_type":   "pdf",
                "source":      self.SYSTEM_NAME,
            },
        ]

    def download_document(self, document_id: str) -> bytes:
        """STUB: Returns empty bytes."""
        print(f"[STUB] CRM: download_document({document_id}) — not yet implemented.")
        return b""

    def get_document_metadata(self, document_id: str) -> dict:
        return {
            "id":            document_id,
            "title":         f"CRM Article {document_id}",
            "version":       "1.0",
            "modified_at":   "2024-01-01T00:00:00Z",
            "author":        "Unknown",
            "file_type":     "pdf",
            "source_system": self.SYSTEM_NAME,
        }