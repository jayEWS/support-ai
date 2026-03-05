"""
Knowledge Repository
=====================
Knowledge base metadata operations, extracted from DatabaseManager.
"""

from typing import Optional, List
from app.repositories.base import BaseRepository
from app.models.models import KnowledgeMetadata
from app.core.logging import logger


class KnowledgeRepository(BaseRepository):
    """Manages knowledge base file metadata."""

    def save_knowledge_metadata(
        self,
        filename: str,
        file_path: str,
        uploaded_by: str = None,
        status: str = "Processing",
        source_url: str = None,
    ):
        """Save or update knowledge file metadata."""
        with self.session_scope() as session:
            existing = session.query(KnowledgeMetadata).filter_by(filename=filename).first()
            if existing:
                existing.file_path = file_path
                existing.status = status
                if uploaded_by:
                    existing.uploaded_by = uploaded_by
                if source_url:
                    existing.source_url = source_url
            else:
                meta = KnowledgeMetadata(
                    filename=filename,
                    file_path=file_path,
                    uploaded_by=uploaded_by,
                    status=status,
                    source_url=source_url,
                )
                session.add(meta)

    def get_all_knowledge(self) -> List[dict]:
        """Get all knowledge file metadata."""
        with self.session_scope() as session:
            items = session.query(KnowledgeMetadata).order_by(KnowledgeMetadata.upload_date.desc()).all()
            return [
                {
                    "id": k.id,
                    "filename": k.filename,
                    "file_path": k.file_path,
                    "upload_date": str(k.upload_date),
                    "uploaded_by": k.uploaded_by,
                    "status": k.status,
                    "source_url": k.source_url,
                }
                for k in items
            ]

    def update_knowledge_status(self, filename: str, status: str):
        """Update indexing status for a knowledge file."""
        with self.session_scope() as session:
            meta = session.query(KnowledgeMetadata).filter_by(filename=filename).first()
            if meta:
                meta.status = status

    def get_knowledge_metadata(self, filename: str) -> Optional[dict]:
        """Get metadata for a specific knowledge file."""
        with self.session_scope() as session:
            k = session.query(KnowledgeMetadata).filter_by(filename=filename).first()
            if not k:
                return None
            return {
                "id": k.id,
                "filename": k.filename,
                "file_path": k.file_path,
                "upload_date": str(k.upload_date),
                "uploaded_by": k.uploaded_by,
                "status": k.status,
            }

    def delete_knowledge_metadata(self, filename: str) -> bool:
        """Delete knowledge file metadata."""
        with self.session_scope() as session:
            meta = session.query(KnowledgeMetadata).filter_by(filename=filename).first()
            if meta:
                session.delete(meta)
                return True
            return False
