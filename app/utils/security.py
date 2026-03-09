"""
Security Utilities — Centralized security functions for the Support Portal.

Covers:
  - Path traversal prevention
  - Filename sanitization
  - SSRF protection (URL validation)
  - Input sanitization helpers
"""

import os
import re
import ipaddress
import hashlib
from urllib.parse import urlparse
from typing import Union
from fastapi import HTTPException, Request, WebSocket
from app.core.logging import logger

# ============ SESSION & IDOR PROTECTION ============

_user_ip_map: dict[str, str] = {}  # user_id -> hashed IP

def bind_user_ip(user_id: str, connection: Union[Request, WebSocket]):
    """
    Bind a user_id to the first IP that uses it, preventing IDOR enumeration.
    Supports both standard FastAPI Request and WebSocket objects.
    """
    if not user_id:
        return

    # Extract client IP based on connection type
    client_ip = "unknown"
    if isinstance(connection, Request):
        client_ip = connection.client.host if connection.client else "unknown"
    elif isinstance(connection, WebSocket):
        client_ip = connection.client.host if connection.client else "unknown"

    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]

    if user_id not in _user_ip_map:
        _user_ip_map[user_id] = ip_hash
        logger.info(f"[SECURITY] Bound user_id {user_id} to IP hash {ip_hash}")
    elif _user_ip_map[user_id] != ip_hash:
        logger.warning(f"[SECURITY] IDOR attempt blocked: user_id={user_id} accessed from IP {client_ip} (expected hash {_user_ip_map[user_id]})")
        raise HTTPException(status_code=403, detail="Session mismatch. Please start a new chat.")


# ============ PATH TRAVERSAL PROTECTION ============

def safe_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.
    Strips directory components, null bytes, and dangerous characters.

    Args:
        filename: Raw user-supplied filename

    Returns:
        Sanitized filename safe for use in file operations

    Raises:
        HTTPException 400 if filename is invalid after sanitization
    """
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Remove any directory components (handles both / and \ separators)
    filename = os.path.basename(filename)

    # Remove null bytes
    filename = filename.replace('\x00', '')

    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)

    # Remove potentially dangerous leading characters
    filename = filename.lstrip('.')

    # Remove any remaining path separator characters
    filename = filename.replace('/', '').replace('\\', '')

    if not filename or filename.strip() == '':
        raise HTTPException(status_code=400, detail="Invalid filename")

    return filename


def safe_path(base_dir: str, filename: str) -> str:
    """
    Resolve a file path and ensure it stays within the base directory.
    Prevents path traversal via ../ sequences, symlinks, etc.

    Args:
        base_dir: The allowed base directory
        filename: User-supplied filename (will be sanitized)

    Returns:
        Absolute path guaranteed to be under base_dir

    Raises:
        HTTPException 400 if the resolved path escapes base_dir
    """
    sanitized = safe_filename(filename)
    full_path = os.path.realpath(os.path.join(base_dir, sanitized))
    base_real = os.path.realpath(base_dir)

    # Ensure the resolved path is under the base directory
    if not full_path.startswith(base_real + os.sep) and full_path != base_real:
        logger.warning(f"[SECURITY] Path traversal attempt blocked: {filename} → {full_path}")
        raise HTTPException(status_code=400, detail="Invalid file path")

    return full_path


# ============ SSRF PROTECTION ============

# Hosts that must never be accessed by server-side requests
BLOCKED_HOSTS = {
    "169.254.169.254",          # AWS/GCP metadata endpoint
    "metadata.google.internal", # GCP metadata
    "metadata",                 # Short form
    "100.100.100.200",          # Alibaba Cloud metadata
    "fd00:ec2::254",            # AWS IPv6 metadata
}

# Blocked schemes
ALLOWED_SCHEMES = {"http", "https"}


def is_safe_url(url: str) -> bool:
    """
    Validate a URL to prevent SSRF (Server-Side Request Forgery).
    Blocks access to internal networks, metadata endpoints, and private IPs.

    Args:
        url: URL to validate

    Returns:
        True if the URL is safe to fetch, False otherwise
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Scheme check
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Block known metadata endpoints
    if hostname.lower() in BLOCKED_HOSTS:
        return False

    # Try to parse as IP address and block private/reserved ranges
    try:
        ip = ipaddress.ip_address(hostname)
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast):
            return False
    except ValueError:
        # Not an IP address — it's a hostname, which is OK
        # But block common internal hostnames
        lower_host = hostname.lower()
        if any(internal in lower_host for internal in [
            'localhost', '127.0.0.1', '0.0.0.0',
            '.internal', '.local', '.corp', '.lan'
        ]):
            return False

    return True


def validate_url_or_raise(url: str) -> str:
    """
    Validate a URL and raise an HTTPException if it's not safe.

    Args:
        url: URL to validate

    Returns:
        The validated URL

    Raises:
        HTTPException 400 if the URL is not safe
    """
    if not is_safe_url(url):
        logger.warning(f"[SECURITY] SSRF attempt blocked: {url}")
        raise HTTPException(
            status_code=400,
            detail="URL is not allowed. Only public HTTP/HTTPS URLs are permitted."
        )
    return url


# ============ KNOWLEDGE FILE TYPE VALIDATION ============

ALLOWED_KNOWLEDGE_EXTENSIONS = {
    '.txt', '.md', '.pdf', '.doc', '.docx',
    '.xlsx', '.xls', '.csv', '.json', '.log', '.text'
}


def validate_knowledge_file(filename: str) -> str:
    """
    Validate that a knowledge base file has an allowed extension.

    Args:
        filename: Filename to check

    Returns:
        Sanitized filename

    Raises:
        HTTPException 400 if file type is not allowed
    """
    sanitized = safe_filename(filename)
    ext = os.path.splitext(sanitized)[1].lower()

    if ext not in ALLOWED_KNOWLEDGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not allowed for knowledge base. "
                   f"Allowed: {', '.join(sorted(ALLOWED_KNOWLEDGE_EXTENSIONS))}"
        )

    return sanitized
