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

_user_ip_map: dict[str, str] = {}  # local fallback when Redis is unavailable


def _get_real_ip(connection: Union[Request, WebSocket]) -> str:
    """
    Extract the real client IP, respecting X-Forwarded-For set by a trusted
    reverse proxy (Caddy / nginx). Falls back to the direct connection IP.
    """
    # X-Real-IP (set by Caddy/nginx as the original client IP)
    real_ip = None
    if isinstance(connection, (Request, WebSocket)):
        headers = connection.headers
        real_ip = (
            headers.get("x-real-ip")
            or headers.get("x-forwarded-for", "").split(",")[0].strip()
            or None
        )
    if not real_ip:
        real_ip = connection.client.host if connection.client else "unknown"
    return real_ip


def bind_user_ip(user_id: str, connection: Union[Request, WebSocket]):
    """
    Bind a user_id to the first real IP that uses it, preventing IDOR enumeration.

    Uses Redis (shared across workers) when available; falls back to an in-process
    dict for single-worker / Redis-disabled deployments.

    The check is intentionally lenient: mismatches are *logged* as warnings but
    do NOT raise an exception, because behind a reverse proxy the observed IP can
    legitimately rotate (NAT, mobile networks, load-balancer health-probes, etc.).
    A hard block here causes more false positives than it prevents real attacks.
    """
    if not user_id:
        return

    client_ip = _get_real_ip(connection)
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]

    # --- Try Redis first (cross-worker safe) ---
    try:
        from app.core.redis import redis_service  # lazy import avoids circular deps
        if redis_service.enabled and redis_service.client:
            import asyncio
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            redis_key = f"user_ip:{user_id}"
            if loop and loop.is_running():
                # We're inside an async context — schedule as a fire-and-forget coroutine
                async def _redis_bind():
                    existing = await redis_service.client.get(redis_key)
                    if existing is None:
                        # Bind with 24-hour TTL (session lifetime)
                        await redis_service.client.setex(redis_key, 86400, ip_hash)
                        logger.info(f"[SECURITY] Bound user_id {user_id} to IP hash {ip_hash} (Redis)")
                    elif existing != ip_hash:
                        logger.warning(
                            f"[SECURITY] IP change detected: user_id={user_id} "
                            f"prev_hash={existing} new_hash={ip_hash} ip={client_ip}"
                        )
                        # Update to new IP (don't block — mobile users legitimately change IPs)
                        await redis_service.client.setex(redis_key, 86400, ip_hash)
                asyncio.ensure_future(_redis_bind())
                return
    except Exception:
        pass  # Redis unavailable — fall through to local dict

    # --- Local in-process fallback ---
    if user_id not in _user_ip_map:
        _user_ip_map[user_id] = ip_hash
        logger.info(f"[SECURITY] Bound user_id {user_id} to IP hash {ip_hash} (local)")
    elif _user_ip_map[user_id] != ip_hash:
        logger.warning(
            f"[SECURITY] IP change detected: user_id={user_id} "
            f"prev_hash={_user_ip_map[user_id]} new_hash={ip_hash} ip={client_ip}"
        )
        # Update to new binding — do not block the request
        _user_ip_map[user_id] = ip_hash


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
