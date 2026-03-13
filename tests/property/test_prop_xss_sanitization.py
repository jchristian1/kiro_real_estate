"""
Property-based tests for XSS sanitization of string inputs.

# Feature: production-hardening, Property 15: XSS sanitization strips HTML from string inputs

**Property 15: XSS sanitization strips HTML from string inputs** — for any
string input to ``lead.name``, ``lead.email``, or ``lead.notes`` that contains
HTML tags, the value stored in the database SHALL have all HTML tags stripped,
and the stored value SHALL be equal to
``bleach.clean(input, tags=[], strip=True)``.

**Validates: Requirements 11.4**
"""

import bleach
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from api.utils.sanitization import sanitize_string

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# HTML tag names to inject
_TAG_NAMES = st.sampled_from([
    "script", "img", "a", "div", "span", "p", "b", "i", "em", "strong",
    "iframe", "object", "embed", "form", "input", "button", "style", "link",
    "meta", "svg", "math", "table", "tr", "td",
])

# Random text content (no HTML)
_plain_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="<>",
    ),
    min_size=0,
    max_size=50,
)


def _html_string_strategy():
    """Generate strings that contain at least one HTML tag."""
    return st.builds(
        lambda tag, before, content, after: f"{before}<{tag}>{content}</{tag}>{after}",
        tag=_TAG_NAMES,
        before=_plain_text,
        content=_plain_text,
        after=_plain_text,
    )


def _html_with_attrs_strategy():
    """Generate strings with HTML tags that have attributes (e.g. XSS vectors)."""
    return st.builds(
        lambda tag, attr_val, content: (
            f'<{tag} onclick="{attr_val}" href="{attr_val}">{content}</{tag}>'
        ),
        tag=_TAG_NAMES,
        attr_val=st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz_()"),
        content=_plain_text,
    )


def _script_injection_strategy():
    """Generate classic XSS script injection strings."""
    payloads = [
        '<script>alert("xss")</script>',
        '<img src=x onerror=alert(1)>',
        '<a href="javascript:alert(1)">click</a>',
        '<svg onload=alert(1)>',
        '<iframe src="javascript:alert(1)"></iframe>',
        '"><script>alert(document.cookie)</script>',
        '<b onmouseover=alert(1)>hover</b>',
        '<input type="text" value="" onfocus="alert(1)">',
    ]
    return st.sampled_from(payloads)


# ---------------------------------------------------------------------------
# Property 15: XSS sanitization strips HTML from string inputs
# ---------------------------------------------------------------------------


class TestProperty15XSSSanitization:
    """
    Property 15: XSS sanitization strips HTML from string inputs.
    **Validates: Requirements 11.4**
    """

    @given(value=_html_string_strategy())
    @settings(max_examples=100, deadline=None)
    def test_sanitize_string_matches_bleach_clean(self, value: str):
        """
        # Feature: production-hardening, Property 15: XSS sanitization strips HTML from string inputs
        **Validates: Requirements 11.4**

        For any string containing HTML tags, sanitize_string(value) SHALL equal
        bleach.clean(value, tags=[], strip=True).
        """
        expected = bleach.clean(value, tags=[], strip=True)
        actual = sanitize_string(value)
        assert actual == expected, (
            f"sanitize_string({value!r}) = {actual!r}, "
            f"expected bleach.clean result = {expected!r}"
        )

    @given(value=_html_with_attrs_strategy())
    @settings(max_examples=100, deadline=None)
    def test_sanitize_strips_tags_with_attributes(self, value: str):
        """
        # Feature: production-hardening, Property 15: XSS sanitization strips HTML from string inputs
        **Validates: Requirements 11.4**

        For any string containing HTML tags with attributes (potential XSS vectors),
        sanitize_string SHALL strip all tags and attributes.
        """
        result = sanitize_string(value)
        assert "<" not in result, (
            f"HTML tag not stripped from: {value!r} → {result!r}"
        )
        assert ">" not in result, (
            f"HTML tag not stripped from: {value!r} → {result!r}"
        )

    @given(value=_script_injection_strategy())
    @settings(max_examples=50, deadline=None)
    def test_sanitize_strips_xss_payloads(self, value: str):
        """
        # Feature: production-hardening, Property 15: XSS sanitization strips HTML from string inputs
        **Validates: Requirements 11.4**

        Classic XSS injection payloads SHALL be fully sanitized by sanitize_string.
        """
        result = sanitize_string(value)
        expected = bleach.clean(value, tags=[], strip=True)
        assert result == expected, (
            f"XSS payload not fully sanitized: {value!r} → {result!r}"
        )
        assert "<script" not in result.lower(), (
            f"<script> tag survived sanitization: {value!r} → {result!r}"
        )

    @given(value=_plain_text)
    @settings(max_examples=100, deadline=None)
    def test_sanitize_preserves_plain_text(self, value: str):
        """
        # Feature: production-hardening, Property 15: XSS sanitization strips HTML from string inputs
        **Validates: Requirements 11.4**

        For any plain text string (no HTML tags), sanitize_string SHALL return
        the same value (no content is lost).
        """
        result = sanitize_string(value)
        expected = bleach.clean(value, tags=[], strip=True)
        assert result == expected, (
            f"Plain text was altered: {value!r} → {result!r}"
        )

    @given(value=_html_string_strategy())
    @settings(max_examples=100, deadline=None)
    def test_sanitize_result_contains_no_html_tags(self, value: str):
        """
        # Feature: production-hardening, Property 15: XSS sanitization strips HTML from string inputs
        **Validates: Requirements 11.4**

        The result of sanitize_string SHALL never contain '<' or '>' characters
        that form HTML tags.
        """
        result = sanitize_string(value)
        # bleach.clean with strip=True removes all tags; result should have no angle brackets
        # from tags (bleach may escape & but strips < >)
        assert "<" not in result, (
            f"'<' found in sanitized output: {value!r} → {result!r}"
        )
        assert ">" not in result, (
            f"'>' found in sanitized output: {value!r} → {result!r}"
        )

    def test_sanitize_known_xss_vectors(self):
        """
        # Feature: production-hardening, Property 15: XSS sanitization strips HTML from string inputs
        **Validates: Requirements 11.4**

        Verify specific known XSS vectors are sanitized correctly.
        """
        cases = [
            ('<script>alert(1)</script>', 'alert(1)'),
            ('<b>bold</b>', 'bold'),
            ('<img src=x onerror=alert(1)>', ''),
            ('Hello <b>World</b>!', 'Hello World!'),
            ('<a href="evil.com">click</a>', 'click'),
            ('Normal text', 'Normal text'),
            ('', ''),
        ]
        for input_val, expected in cases:
            result = sanitize_string(input_val)
            assert result == expected, (
                f"sanitize_string({input_val!r}) = {result!r}, expected {expected!r}"
            )

    def test_sanitize_idempotent(self):
        """
        # Feature: production-hardening, Property 15: XSS sanitization strips HTML from string inputs
        **Validates: Requirements 11.4**

        Applying sanitize_string twice SHALL produce the same result as once
        (idempotency).
        """
        inputs = [
            '<script>alert(1)</script>',
            '<b>Hello</b>',
            'Plain text',
            '<img src=x>',
        ]
        for value in inputs:
            once = sanitize_string(value)
            twice = sanitize_string(once)
            assert once == twice, (
                f"sanitize_string is not idempotent for {value!r}: "
                f"once={once!r}, twice={twice!r}"
            )
