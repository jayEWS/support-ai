#!/usr/bin/env python3
"""
GCS Migration Script — Phase 2
Uploads all existing knowledge files from data/knowledge/ to GCS bucket.

Usage:
  # Set env vars first:
  export GCS_ENABLED=True
  export GCS_BUCKET_NAME=support-edgeworks-knowledge
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
  
  # Run:
  python scripts/migrate_to_gcs.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


def main():
    print("=" * 60)
    print("  GCS Migration — Phase 2: Upload Knowledge to GCS")
    print("=" * 60)
    print()

    # Check config
    print(f"  GCS_ENABLED:    {settings.GCS_ENABLED}")
    print(f"  GCS_BUCKET:     {settings.GCS_BUCKET_NAME}")
    print(f"  GCP_PROJECT_ID: {settings.GCP_PROJECT_ID}")
    print(f"  KNOWLEDGE_DIR:  {settings.KNOWLEDGE_DIR}")
    print()

    if not settings.GCS_ENABLED:
        print("❌ GCS_ENABLED is False. Set GCS_ENABLED=True in .env")
        sys.exit(1)

    if not settings.GCS_BUCKET_NAME:
        print("❌ GCS_BUCKET_NAME not set in .env")
        sys.exit(1)

    # Check knowledge directory
    knowledge_dir = settings.KNOWLEDGE_DIR
    if not os.path.exists(knowledge_dir):
        print(f"❌ Knowledge directory not found: {knowledge_dir}")
        sys.exit(1)

    files = [
        f for f in os.listdir(knowledge_dir)
        if f != ".gitkeep" and os.path.isfile(os.path.join(knowledge_dir, f))
    ]
    print(f"  Found {len(files)} local knowledge files")
    print()

    if not files:
        print("⚠️  No files to migrate.")
        sys.exit(0)

    # Initialize GCS service
    print("Initializing GCS client...")
    from app.services.gcs_service import GCSService
    gcs = GCSService()

    if not gcs.enabled:
        print("❌ GCS service failed to initialize. Check credentials.")
        sys.exit(1)

    print(f"✅ Connected to gs://{settings.GCS_BUCKET_NAME}/")
    print()

    # Sync
    print("Starting upload...")
    print("-" * 60)

    results = gcs.sync_local_to_gcs(knowledge_dir)

    print("-" * 60)
    print()

    # Summary
    success = sum(1 for v in results.values() if v != "FAILED")
    failed = sum(1 for v in results.values() if v == "FAILED")

    print(f"  ✅ Uploaded: {success}")
    print(f"  ❌ Failed:   {failed}")
    print(f"  📁 Total:    {len(results)}")
    print()

    if failed > 0:
        print("Failed files:")
        for f, r in results.items():
            if r == "FAILED":
                print(f"  - {f}")
        print()

    # Verify
    print("Verifying GCS contents...")
    gcs_files = gcs.list_files()
    total_size = sum(f["size"] for f in gcs_files)
    print(f"  GCS has {len(gcs_files)} files ({total_size / 1024:.1f} KB)")
    print()

    for f in gcs_files:
        print(f"  📄 {f['filename']} ({f['size']} bytes) — {f['gcs_uri']}")

    print()
    print("=" * 60)
    print("  Migration complete!")
    print(f"  Bucket: gs://{settings.GCS_BUCKET_NAME}/knowledge/")
    print("=" * 60)


if __name__ == "__main__":
    main()
