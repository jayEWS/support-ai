"""
PII / Sensitive Data Scrubber
==============================
Regex-based utility to detect and mask Personally Identifiable Information (PII)
before it is persisted to the database (e.g., AIInteraction logs).

Covers:
  - Credit/Debit card numbers (Visa, MasterCard, Amex, Discover)
  - Singapore NRIC / FIN
  - Email addresses
  - Phone numbers (international, SG local)
  - Passwords / secrets shared in plain text
  - API keys (common patterns)

Usage:
    from app.utils.pii_scrubber import scrub_pii
    clean_text = scrub_pii(raw_user_input)
"""

import re
from typing import List, Tuple

# ── Pattern Definitions ───────────────────────────────────────────────

_PII_PATTERNS: List[Tuple[str, re.Pattern, str]] = [
    # Credit Card Numbers (13-19 digits, optionally separated by spaces or hyphens)
    (
        "CREDIT_CARD",
        re.compile(
            r"\b(?:4[0-9]{3}|5[1-5][0-9]{2}|3[47][0-9]{2}|6(?:011|5[0-9]{2}))"
            r"[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{1,7}\b"
        ),
        "[REDACTED_CARD]",
    ),
    # Generic long digit sequences (16+ digits) that might be card numbers
    (
        "LONG_DIGITS",
        re.compile(r"\b[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4,7}\b"),
        "[REDACTED_CARD]",
    ),
    # Singapore NRIC / FIN: S/T/F/G/M + 7 digits + letter
    (
        "SG_NRIC",
        re.compile(r"\b[STFGM][0-9]{7}[A-Z]\b", re.IGNORECASE),
        "[REDACTED_NRIC]",
    ),
    # Email addresses
    (
        "EMAIL",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
    # Phone numbers: international (+65XXXXXXXX) or local (9XXXXXXX, 8XXXXXXX, 6XXXXXXX)
    (
        "PHONE",
        re.compile(r"(?:\+?65[\s\-]?)?(?:[689][0-9]{7})\b"),
        "[REDACTED_PHONE]",
    ),
    # API keys / Bearer tokens (common patterns like sk-xxx, Bearer xxx)
    (
        "API_KEY",
        re.compile(
            r"\b(?:sk-[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9\-_.~+/]+=*)\b",
            re.IGNORECASE,
        ),
        "[REDACTED_KEY]",
    ),
    # Password-like strings: "password is xyz", "my password: xyz", "pw: xyz"
    (
        "PASSWORD_LEAK",
        re.compile(
            r"(?:password|passwd|pw|pwd|secret|token)\s*(?:is|:|=)\s*\S+",
            re.IGNORECASE,
        ),
        "[REDACTED_SECRET]",
    ),
]


def scrub_pii(text: str) -> str:
    """
    Scan input text and replace detected PII with safe placeholders.

    Args:
        text: Raw input string (e.g., user chat message).

    Returns:
        Sanitized string with PII replaced by [REDACTED_*] tokens.
    """
    if not text:
        return text

    result = text
    for _label, pattern, replacement in _PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def contains_pii(text: str) -> bool:
    """
    Quick check: does the text contain any detectable PII?

    Args:
        text: Raw input string.

    Returns:
        True if PII patterns are found.
    """
    if not text:
        return False

    for _label, pattern, _replacement in _PII_PATTERNS:
        if pattern.search(text):
            return True
    return False
