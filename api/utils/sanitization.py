"""
Input sanitization utilities for XSS prevention.

Strips HTML tags from user-supplied string inputs before storage
to prevent stored XSS attacks.

Requirements: 11.4
"""

import bleach


def sanitize_string(value: str) -> str:
    """
    Strip all HTML tags from a string using bleach.

    Args:
        value: Raw user-supplied string input.

    Returns:
        String with all HTML tags removed.

    Requirements: 11.4
    """
    return bleach.clean(value, tags=[], strip=True)
