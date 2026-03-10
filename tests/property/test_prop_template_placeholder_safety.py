"""
Property-based tests for Template Placeholder Safety.

Feature: agent-app

**Property 10: Template Placeholder Safety** — for any rendered email, subject
contains no newline characters and no unresolved `{...}` placeholders remain
in subject or body.

**Validates: Requirements 14.5, 14.6, 14.7**
"""

import re

from hypothesis import given, settings, strategies as st

from api.services.template_renderer import SUPPORTED_PLACEHOLDERS, render_template_str

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# A full context dict with all 5 supported placeholder keys mapped to
# arbitrary (non-empty) text values.
context_strategy = st.fixed_dictionaries(
    {key: st.text(min_size=0) for key in SUPPORTED_PLACEHOLDERS}
)

# Arbitrary text for subject / body (Hypothesis will generate strings that
# may contain newlines, braces, and other special characters).
text_strategy = st.text()


def _build_placeholder_string() -> str:
    """Return a string containing all 5 supported placeholders."""
    return " ".join("{" + key + "}" for key in sorted(SUPPORTED_PLACEHOLDERS))


# ---------------------------------------------------------------------------
# Property 10a: Subject No Newlines (Requirement 14.7)
# ---------------------------------------------------------------------------


class TestProperty10aSubjectNoNewlines:
    """
    Property 10a: Subject No Newlines
    **Validates: Requirements 14.7**

    For any subject string and any context dict, the rendered subject never
    contains \\n or \\r characters.
    """

    @given(subject=text_strategy, body=text_strategy, context=context_strategy)
    @settings(max_examples=100)
    def test_rendered_subject_contains_no_newlines(
        self, subject: str, body: str, context: dict
    ):
        """
        Property 10a: Subject No Newlines
        **Validates: Requirements 14.7**

        After rendering with any subject, body, and context, the returned
        subject must not contain \\n or \\r.
        """
        result = render_template_str(subject, body, context)
        assert "\n" not in result["subject"], (
            f"Rendered subject contains \\n. "
            f"subject={subject!r}, context={context!r}"
        )
        assert "\r" not in result["subject"], (
            f"Rendered subject contains \\r. "
            f"subject={subject!r}, context={context!r}"
        )

    @given(subject=text_strategy, context=context_strategy)
    @settings(max_examples=100)
    def test_subject_newline_stripping_is_unconditional(
        self, subject: str, context: dict
    ):
        """
        Property 10a: Subject No Newlines
        **Validates: Requirements 14.7**

        Even when the subject explicitly contains newline characters, the
        rendered result must have none.
        """
        subject_with_newlines = subject + "\n" + subject + "\r\n"
        result = render_template_str(subject_with_newlines, "", context)
        assert "\n" not in result["subject"]
        assert "\r" not in result["subject"]


# ---------------------------------------------------------------------------
# Property 10b: No Unresolved Supported Placeholders (Requirements 14.5, 14.6)
# ---------------------------------------------------------------------------


class TestProperty10bNoUnresolvedSupportedPlaceholders:
    """
    Property 10b: No Unresolved Supported Placeholders
    **Validates: Requirements 14.5, 14.6**

    For any subject/body containing any combination of the 5 supported
    placeholders, after rendering with a full context dict, none of the
    supported placeholder tokens remain in subject or body.
    """

    @given(context=context_strategy)
    @settings(max_examples=100)
    def test_all_supported_placeholders_resolved_in_subject(self, context: dict):
        """
        Property 10b: No Unresolved Supported Placeholders
        **Validates: Requirements 14.5, 14.6**

        A subject containing all 5 supported placeholders has none remaining
        after rendering with a full context.
        """
        subject = _build_placeholder_string()
        result = render_template_str(subject, "", context)

        for key in SUPPORTED_PLACEHOLDERS:
            token = "{" + key + "}"
            assert token not in result["subject"], (
                f"Unresolved placeholder {token!r} found in subject. "
                f"context={context!r}"
            )

    @given(context=context_strategy)
    @settings(max_examples=100)
    def test_all_supported_placeholders_resolved_in_body(self, context: dict):
        """
        Property 10b: No Unresolved Supported Placeholders
        **Validates: Requirements 14.5, 14.6**

        A body containing all 5 supported placeholders has none remaining
        after rendering with a full context.
        """
        body = _build_placeholder_string()
        result = render_template_str("", body, context)

        for key in SUPPORTED_PLACEHOLDERS:
            token = "{" + key + "}"
            assert token not in result["body"], (
                f"Unresolved placeholder {token!r} found in body. "
                f"context={context!r}"
            )

    @given(
        extra_text=text_strategy,
        context=context_strategy,
    )
    @settings(max_examples=100)
    def test_placeholders_resolved_when_mixed_with_arbitrary_text(
        self, extra_text: str, context: dict
    ):
        """
        Property 10b: No Unresolved Supported Placeholders
        **Validates: Requirements 14.5, 14.6**

        When supported placeholders are embedded in arbitrary surrounding text,
        they are still fully resolved after rendering.
        """
        placeholder_block = _build_placeholder_string()
        subject = extra_text + placeholder_block + extra_text
        body = extra_text + placeholder_block + extra_text

        result = render_template_str(subject, body, context)

        for key in SUPPORTED_PLACEHOLDERS:
            token = "{" + key + "}"
            assert token not in result["subject"], (
                f"Unresolved {token!r} in subject after rendering. "
                f"extra_text={extra_text!r}, context={context!r}"
            )
            assert token not in result["body"], (
                f"Unresolved {token!r} in body after rendering. "
                f"extra_text={extra_text!r}, context={context!r}"
            )

    # -----------------------------------------------------------------------
    # Bonus: arbitrary text without placeholders is a no-op on body
    # -----------------------------------------------------------------------

    @given(text=st.text(alphabet=st.characters(blacklist_characters="{}")))
    @settings(max_examples=100)
    def test_arbitrary_text_without_placeholders_body_unchanged(self, text: str):
        """
        Property 10b (corollary): No Unresolved Supported Placeholders
        **Validates: Requirements 14.5, 14.6**

        For any text that contains no `{` or `}` characters, rendering with
        an empty context leaves the body unchanged (no substitution occurs).
        """
        result = render_template_str("", text, {})
        assert result["body"] == text, (
            f"Body changed unexpectedly. input={text!r}, output={result['body']!r}"
        )

    @given(text=st.text(alphabet=st.characters(blacklist_characters="\n\r{}")))
    @settings(max_examples=100)
    def test_arbitrary_text_without_placeholders_subject_only_strips_newlines(
        self, text: str
    ):
        """
        Property 10b (corollary): No Unresolved Supported Placeholders
        **Validates: Requirements 14.7**

        For any text that contains no `{`, `}`, `\\n`, or `\\r` characters,
        rendering with an empty context leaves the subject unchanged (the
        newline-strip is a no-op when there are no newlines).
        """
        result = render_template_str(text, "", {})
        assert result["subject"] == text, (
            f"Subject changed unexpectedly. input={text!r}, output={result['subject']!r}"
        )
