"""
Google Cloud Storage Service for Knowledge Base Document Management.

Phase 2 of Google Cloud Migration:
- Syncs knowledge documents to GCS bucket
- Prepares documents for Vertex AI Search (Phase 3)
- Maintains local+cloud dual storage with graceful fallback

Bucket structure:
  gs://<bucket>/knowledge/<filename>
"""

import os
import asyncio
from typing import List, Optional, Dict
from app.core.config import settings
from app.core.logging import logger


class GCSService:
    """Google Cloud Storage client for knowledge document sync."""

    def __init__(self):
        self.enabled = False
        self.bucket = None
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize GCS client if configured."""
        if not settings.GCS_ENABLED:
            logger.info("[GCS] Disabled (GCS_ENABLED=False)")
            return

        if not settings.GCS_BUCKET_NAME:
            logger.warning("[GCS] GCS_ENABLED=True but GCS_BUCKET_NAME not set. Disabling.")
            return

        try:
            from google.cloud import storage

            # Authenticate via service account JSON or ADC (Application Default Credentials)
            creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
            if creds_path and os.path.exists(creds_path):
                self.client = storage.Client.from_service_account_json(creds_path)
                logger.info(f"[GCS] Authenticated via service account: {creds_path}")
            else:
                # Fall back to Application Default Credentials (works on GCP VM with attached SA)
                self.client = storage.Client(project=settings.GCP_PROJECT_ID or None)
                logger.info("[GCS] Authenticated via Application Default Credentials")

            self.bucket = self.client.bucket(settings.GCS_BUCKET_NAME)

            # Verify bucket exists
            if not self.bucket.exists():
                logger.warning(f"[GCS] Bucket '{settings.GCS_BUCKET_NAME}' does not exist. Creating...")
                self.bucket = self.client.create_bucket(
                    settings.GCS_BUCKET_NAME,
                    location="asia-southeast1"  # Singapore region
                )
                logger.info(f"[GCS] Created bucket: {settings.GCS_BUCKET_NAME}")

            self.enabled = True
            logger.info(f"[GCS] Ready — bucket: gs://{settings.GCS_BUCKET_NAME}/")

        except ImportError:
            logger.warning("[GCS] google-cloud-storage not installed. Run: pip install google-cloud-storage")
        except Exception as e:
            logger.error(f"[GCS] Init failed: {e}")
            self.enabled = False

    def _blob_path(self, filename: str) -> str:
        """Get the GCS blob path for a knowledge file."""
        return f"knowledge/{filename}"

    def upload_file(self, local_path: str, filename: str) -> Optional[str]:
        """
        Upload a file to GCS.

        Args:
            local_path: Local file path
            filename: Target filename in GCS

        Returns:
            GCS URI (gs://bucket/path) on success, None on failure
        """
        if not self.enabled:
            return None

        try:
            blob_path = self._blob_path(filename)
            blob = self.bucket.blob(blob_path)

            # Detect content type
            import mimetypes
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

            blob.upload_from_filename(local_path, content_type=content_type)

            gcs_uri = f"gs://{settings.GCS_BUCKET_NAME}/{blob_path}"
            logger.info(f"[GCS] Uploaded: {filename} → {gcs_uri}")
            return gcs_uri

        except Exception as e:
            logger.error(f"[GCS] Upload failed for {filename}: {e}")
            return None

    def upload_bytes(self, file_bytes: bytes, filename: str, content_type: str = "application/octet-stream") -> Optional[str]:
        """
        Upload bytes directly to GCS.

        Args:
            file_bytes: Raw file content
            filename: Target filename in GCS
            content_type: MIME type

        Returns:
            GCS URI on success, None on failure
        """
        if not self.enabled:
            return None

        try:
            blob_path = self._blob_path(filename)
            blob = self.bucket.blob(blob_path)
            blob.upload_from_string(file_bytes, content_type=content_type)

            gcs_uri = f"gs://{settings.GCS_BUCKET_NAME}/{blob_path}"
            logger.info(f"[GCS] Uploaded bytes: {filename} → {gcs_uri}")
            return gcs_uri

        except Exception as e:
            logger.error(f"[GCS] Upload bytes failed for {filename}: {e}")
            return None

    def delete_file(self, filename: str) -> bool:
        """
        Delete a file from GCS.

        Args:
            filename: Filename to delete

        Returns:
            True if deleted, False on failure/disabled
        """
        if not self.enabled:
            return False

        try:
            blob_path = self._blob_path(filename)
            blob = self.bucket.blob(blob_path)

            if blob.exists():
                blob.delete()
                logger.info(f"[GCS] Deleted: {filename}")
                return True
            else:
                logger.warning(f"[GCS] File not found for delete: {filename}")
                return True  # Not an error — file doesn't exist

        except Exception as e:
            logger.error(f"[GCS] Delete failed for {filename}: {e}")
            return False

    def delete_files(self, filenames: List[str]) -> Dict[str, bool]:
        """
        Delete multiple files from GCS.

        Returns:
            Dict of {filename: success_bool}
        """
        results = {}
        for filename in filenames:
            results[filename] = self.delete_file(filename)
        return results

    def list_files(self) -> List[Dict[str, any]]:
        """
        List all knowledge files in GCS bucket.

        Returns:
            List of dicts with name, size, updated, gcs_uri
        """
        if not self.enabled:
            return []

        try:
            blobs = self.client.list_blobs(self.bucket, prefix="knowledge/")
            files = []
            for blob in blobs:
                if blob.name == "knowledge/":  # Skip the folder itself
                    continue
                filename = blob.name.replace("knowledge/", "", 1)
                files.append({
                    "filename": filename,
                    "size": blob.size,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                    "gcs_uri": f"gs://{settings.GCS_BUCKET_NAME}/{blob.name}",
                    "content_type": blob.content_type,
                })
            return files

        except Exception as e:
            logger.error(f"[GCS] List files failed: {e}")
            return []

    def file_exists(self, filename: str) -> bool:
        """Check if a file exists in GCS."""
        if not self.enabled:
            return False

        try:
            blob = self.bucket.blob(self._blob_path(filename))
            return blob.exists()
        except Exception:
            return False

    def sync_local_to_gcs(self, knowledge_dir: str = None) -> Dict[str, str]:
        """
        Sync all local knowledge files to GCS.
        Used for initial migration and periodic sync.

        Args:
            knowledge_dir: Local knowledge directory path (default: settings.KNOWLEDGE_DIR)

        Returns:
            Dict of {filename: gcs_uri or error_message}
        """
        if not self.enabled:
            return {"_status": "GCS disabled"}

        knowledge_dir = knowledge_dir or settings.KNOWLEDGE_DIR
        if not os.path.exists(knowledge_dir):
            return {"_status": f"Directory not found: {knowledge_dir}"}

        results = {}
        files = [
            f for f in os.listdir(knowledge_dir)
            if f != ".gitkeep" and os.path.isfile(os.path.join(knowledge_dir, f))
        ]

        logger.info(f"[GCS] Syncing {len(files)} files to gs://{settings.GCS_BUCKET_NAME}/knowledge/")

        for filename in files:
            local_path = os.path.join(knowledge_dir, filename)
            gcs_uri = self.upload_file(local_path, filename)
            results[filename] = gcs_uri or "FAILED"

        uploaded = sum(1 for v in results.values() if v != "FAILED")
        logger.info(f"[GCS] Sync complete: {uploaded}/{len(files)} files uploaded")
        return results

    async def async_upload_file(self, local_path: str, filename: str) -> Optional[str]:
        """Async wrapper for upload_file (runs in thread pool)."""
        return await asyncio.to_thread(self.upload_file, local_path, filename)

    async def async_delete_file(self, filename: str) -> bool:
        """Async wrapper for delete_file."""
        return await asyncio.to_thread(self.delete_file, filename)

    async def async_sync_local_to_gcs(self, knowledge_dir: str = None) -> Dict[str, str]:
        """Async wrapper for sync_local_to_gcs."""
        return await asyncio.to_thread(self.sync_local_to_gcs, knowledge_dir)

    def get_status(self) -> Dict[str, any]:
        """Get GCS service status for health checks."""
        status = {
            "enabled": self.enabled,
            "bucket": settings.GCS_BUCKET_NAME if self.enabled else None,
        }

        if self.enabled:
            try:
                files = self.list_files()
                status["file_count"] = len(files)
                status["total_size_mb"] = round(sum(f["size"] for f in files) / (1024 * 1024), 2)
                status["status"] = "healthy"
            except Exception as e:
                status["status"] = f"error: {e}"

        return status


# Singleton instance
gcs_service: Optional[GCSService] = None


def init_gcs_service() -> GCSService:
    """Initialize the GCS service singleton."""
    global gcs_service
    gcs_service = GCSService()
    return gcs_service


def get_gcs_service() -> GCSService:
    """Get the GCS service singleton, initializing if needed."""
    global gcs_service
    if gcs_service is None:
        gcs_service = GCSService()
    return gcs_service
