#!/usr/bin/env python3
"""
GCS Integration Test Script — Phase 2

Tests:
1. GCS client initialization
2. Upload a test file
3. List files
4. Check file exists
5. Delete test file
6. Verify deletion
7. GCS service status

Usage:
  # With GCS enabled:
  export GCS_ENABLED=True
  export GCS_BUCKET_NAME=support-edgeworks-knowledge
  python scripts/test_gcs.py

  # Without GCS (tests graceful disable):
  python scripts/test_gcs.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⏭️  SKIP"


def test_1_init():
    """Test 1: GCS client initialization."""
    print("\n--- Test 1: GCS Client Initialization ---")
    from app.services.gcs_service import GCSService
    gcs = GCSService()

    if not settings.GCS_ENABLED:
        print(f"  GCS_ENABLED=False → service disabled (expected)")
        assert not gcs.enabled, "Should be disabled when GCS_ENABLED=False"
        print(f"  {PASS} — Gracefully disabled")
        return gcs, False  # gcs, is_enabled

    assert gcs.enabled, "GCS should be enabled"
    assert gcs.client is not None, "Client should be initialized"
    assert gcs.bucket is not None, "Bucket should be set"
    print(f"  Connected to gs://{settings.GCS_BUCKET_NAME}/")
    print(f"  {PASS}")
    return gcs, True


def test_2_upload(gcs, enabled):
    """Test 2: Upload a test file."""
    print("\n--- Test 2: Upload Test File ---")
    if not enabled:
        print(f"  {SKIP} (GCS disabled)")
        return None

    # Create a temp file
    test_content = "This is a GCS integration test file.\nPhase 2 migration test.\n"
    test_filename = "_gcs_test_file.txt"
    test_path = os.path.join(tempfile.gettempdir(), test_filename)

    with open(test_path, "w") as f:
        f.write(test_content)

    gcs_uri = gcs.upload_file(test_path, test_filename)
    assert gcs_uri is not None, "Upload should return a GCS URI"
    assert gcs_uri.startswith("gs://"), f"URI should start with gs://, got: {gcs_uri}"
    print(f"  Uploaded: {gcs_uri}")
    print(f"  {PASS}")

    # Cleanup local temp
    os.remove(test_path)
    return test_filename


def test_3_list(gcs, enabled):
    """Test 3: List files in GCS."""
    print("\n--- Test 3: List GCS Files ---")
    if not enabled:
        result = gcs.list_files()
        assert result == [], "Should return empty list when disabled"
        print(f"  {SKIP} (GCS disabled, returned empty list)")
        return

    files = gcs.list_files()
    assert isinstance(files, list), "Should return a list"
    print(f"  Found {len(files)} files in bucket")
    for f in files[:5]:  # Show first 5
        print(f"    📄 {f['filename']} ({f['size']} bytes)")
    if len(files) > 5:
        print(f"    ... and {len(files) - 5} more")
    print(f"  {PASS}")


def test_4_exists(gcs, enabled, test_filename):
    """Test 4: Check file exists."""
    print("\n--- Test 4: File Exists Check ---")
    if not enabled or not test_filename:
        print(f"  {SKIP} (GCS disabled or no test file)")
        return

    exists = gcs.file_exists(test_filename)
    assert exists, f"Test file {test_filename} should exist"
    print(f"  {test_filename} exists: {exists}")

    # Also check a non-existent file
    fake_exists = gcs.file_exists("_definitely_not_a_real_file_xyz.txt")
    assert not fake_exists, "Non-existent file should return False"
    print(f"  Non-existent file: {fake_exists}")
    print(f"  {PASS}")


def test_5_delete(gcs, enabled, test_filename):
    """Test 5: Delete test file."""
    print("\n--- Test 5: Delete Test File ---")
    if not enabled or not test_filename:
        print(f"  {SKIP} (GCS disabled or no test file)")
        return

    result = gcs.delete_file(test_filename)
    assert result, "Delete should return True"
    print(f"  Deleted: {test_filename}")
    print(f"  {PASS}")


def test_6_verify_delete(gcs, enabled, test_filename):
    """Test 6: Verify file was deleted."""
    print("\n--- Test 6: Verify Deletion ---")
    if not enabled or not test_filename:
        print(f"  {SKIP} (GCS disabled or no test file)")
        return

    exists = gcs.file_exists(test_filename)
    assert not exists, f"Test file should be deleted but still exists"
    print(f"  {test_filename} exists after delete: {exists}")
    print(f"  {PASS}")


def test_7_status(gcs, enabled):
    """Test 7: GCS service status."""
    print("\n--- Test 7: GCS Service Status ---")
    status = gcs.get_status()
    assert "enabled" in status, "Status should have 'enabled' key"
    print(f"  Status: {status}")

    if enabled:
        assert status["status"] == "healthy", f"Should be healthy, got: {status.get('status')}"
    
    print(f"  {PASS}")


def test_8_upload_bytes(gcs, enabled):
    """Test 8: Upload bytes directly."""
    print("\n--- Test 8: Upload Bytes ---")
    if not enabled:
        print(f"  {SKIP} (GCS disabled)")
        return

    test_bytes = b"Direct bytes upload test for Phase 2.\n"
    test_filename = "_gcs_bytes_test.txt"

    gcs_uri = gcs.upload_bytes(test_bytes, test_filename, "text/plain")
    assert gcs_uri is not None, "Upload bytes should return URI"
    print(f"  Uploaded bytes: {gcs_uri}")

    # Cleanup
    gcs.delete_file(test_filename)
    print(f"  Cleaned up test file")
    print(f"  {PASS}")


def main():
    print("=" * 60)
    print("  GCS Integration Test — Phase 2")
    print("=" * 60)
    print(f"  GCS_ENABLED:    {settings.GCS_ENABLED}")
    print(f"  GCS_BUCKET:     {settings.GCS_BUCKET_NAME or '(not set)'}")
    print(f"  GCP_PROJECT_ID: {settings.GCP_PROJECT_ID or '(not set)'}")

    passed = 0
    failed = 0
    total = 8

    try:
        gcs, enabled = test_1_init()
        passed += 1
    except AssertionError as e:
        print(f"  {FAIL} — {e}")
        failed += 1
        return

    for test_fn, args in [
        (test_2_upload, (gcs, enabled)),
    ]:
        try:
            test_filename = test_fn(*args)
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"  {FAIL} — {e}")
            failed += 1
            test_filename = None

    for test_fn, args in [
        (test_3_list, (gcs, enabled)),
        (test_4_exists, (gcs, enabled, test_filename)),
        (test_5_delete, (gcs, enabled, test_filename)),
        (test_6_verify_delete, (gcs, enabled, test_filename)),
        (test_7_status, (gcs, enabled)),
        (test_8_upload_bytes, (gcs, enabled)),
    ]:
        try:
            test_fn(*args)
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"  {FAIL} — {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if not enabled:
        print(f"  ⚠️  GCS disabled — only graceful-disable tests ran")
        print(f"  To run full tests, set GCS_ENABLED=True + bucket config")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
