"""
Base connector interface for enterprise integrations — KnowSure.

All enterprise connectors (SharePoint, Confluence, CRM, ERP, DMS)
implement this interface. The ingestion pipeline can call any connector
through this unified interface without knowing the underlying system.

Current status: Stub implementations only.
Full OAuth/API integration is planned for the next development phase.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path


class BaseConnector(ABC):
    """
    Abstract base class for all enterprise system connectors.

    Each connector is responsible for:
    1. Authenticating with the external system
    2. Listing available documents
    3. Downloading document content as bytes
    4. Providing document metadata (title, version, modified date)
    """

    def __init__(self, config: dict):
        """
        Args:
            config: Connector-specific configuration dict.
                    Typically loaded from environment variables or settings.
        """
        self.config = config
        self.connected = False

    @abstractmethod
    def connect(self) -> bool:
        """
        Authenticate and establish connection to the external system.

        Returns:
            True if connection succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def list_documents(self, folder: str | None = None) -> list[dict]:
        """
        List available documents in the external system.

        Args:
            folder: Optional folder/library path to list.

        Returns:
            List of document metadata dicts, each containing at minimum:
            - id:           Unique document identifier in the source system
            - title:        Human-readable document title
            - modified_at:  Last modification timestamp (ISO format string)
            - file_type:    File extension (pdf, docx, xlsx, etc.)
        """
        pass

    @abstractmethod
    def download_document(self, document_id: str) -> bytes:
        """
        Download a document's content as raw bytes.

        Args:
            document_id: Unique identifier from list_documents().

        Returns:
            Raw file bytes ready for writing to disk or passing to extractors.
        """
        pass

    @abstractmethod
    def get_document_metadata(self, document_id: str) -> dict:
        """
        Get detailed metadata for a specific document.

        Returns:
            Dict containing: id, title, version, modified_at,
            author, file_type, source_system.
        """
        pass

    def fetch_to_directory(self, output_dir: str | Path) -> list[str]:
        """
        Download all documents from the source system to a local directory.

        This is a convenience method used by the ingestion pipeline.
        It calls list_documents(), then download_document() for each,
        and saves to the output directory.

        Args:
            output_dir: Local directory to save documents.

        Returns:
            List of local file paths of downloaded documents.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        documents = self.list_documents()
        saved_paths = []

        for doc in documents:
            try:
                content = self.download_document(doc["id"])
                filename = f"{doc['id']}.{doc.get('file_type', 'pdf')}"
                filepath = output_dir / filename
                filepath.write_bytes(content)
                saved_paths.append(str(filepath))
            except Exception as exc:
                print(f"Failed to download {doc.get('title', doc['id'])}: {exc}")

        return saved_paths