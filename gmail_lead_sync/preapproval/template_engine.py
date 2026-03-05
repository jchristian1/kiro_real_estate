"""
TemplateRenderEngine — renders versioned message templates with variable
substitution and HTML escaping.

Supported template variables ({{var}} syntax):
    lead.first_name, lead.email, lead.phone, lead.lead_source,
    lead.property_address, lead.listing_url,
    form.link,
    score.total, score.bucket, score.explanation,
    tenant.name
"""

from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from gmail_lead_sync.preapproval.models_preapproval import MessageTemplateVersion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported template variables
# ---------------------------------------------------------------------------

SUPPORTED_VARS: frozenset[str] = frozenset(
    {
        "lead.first_name",
        "lead.email",
        "lead.phone",
        "lead.lead_source",
        "lead.property_address",
        "lead.listing_url",
        "form.link",
        "score.total",
        "score.bucket",
        "score.explanation",
        "tenant.name",
    }
)

# Regex that matches every {{...}} token in a template string.
_VAR_RE = re.compile(r"\{\{([\w.]+)\}\}")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UnknownVariableError(ValueError):
    """Raised when a template contains a {{variable}} not in SUPPORTED_VARS."""

    def __init__(self, unknown: set[str]) -> None:
        self.unknown = unknown
        super().__init__(
            f"Template contains unknown variable(s): {', '.join(sorted(unknown))}"
        )


class VariantNotFoundError(KeyError):
    """Raised when a variant_key is provided but not found in variants_json."""

    def __init__(self, variant_key: str) -> None:
        self.variant_key = variant_key
        super().__init__(
            f"Variant '{variant_key}' not found in template variants_json"
        )


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class RenderedMessage:
    subject: str
    body: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class TemplateRenderEngine:
    """Render versioned message templates with variable substitution."""

    SUPPORTED_VARS: frozenset[str] = SUPPORTED_VARS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        template_version: MessageTemplateVersion,
        context: dict[str, Any],
        variant_key: str | None = None,
    ) -> RenderedMessage:
        """Render *template_version* with *context*.

        Args:
            template_version: The persisted ``MessageTemplateVersion`` to render.
            context: Mapping of variable names (without ``{{ }}``) to values.
            variant_key: Optional bucket key (e.g. ``"HOT"``, ``"WARM"``,
                ``"NURTURE"``).  When provided the matching variant's subject /
                body is used instead of the base template fields.

        Returns:
            A :class:`RenderedMessage` with ``subject`` and ``body`` strings.

        Raises:
            VariantNotFoundError: If *variant_key* is given but not present in
                ``variants_json``.
            UnknownVariableError: If any ``{{variable}}`` token in the selected
                subject / body is not a member of :attr:`SUPPORTED_VARS`.
        """
        subject_tpl, body_tpl = self._select_templates(
            template_version, variant_key
        )
        self._validate_vars(subject_tpl, body_tpl)

        rendered_subject = self._substitute(subject_tpl, context, escape=False)
        rendered_body = self._substitute(body_tpl, context, escape=True)

        return RenderedMessage(subject=rendered_subject, body=rendered_body)

    def preview(
        self,
        subject_template: str,
        body_template: str,
        sample_context: dict | None = None,
    ) -> RenderedMessage:
        """Render arbitrary subject / body strings without a persisted version.

        Variable validation is *not* performed here so that admins can preview
        drafts that may still contain unsupported variables.  Missing variables
        are substituted with an empty string (same as :meth:`render`).

        Args:
            subject_template: Raw subject string with ``{{variable}}`` tokens.
            body_template: Raw body string with ``{{variable}}`` tokens.
            sample_context: Optional context dict; defaults to ``{}``.

        Returns:
            A :class:`RenderedMessage` with substituted ``subject`` and ``body``.
        """
        ctx = sample_context or {}
        rendered_subject = self._substitute(subject_template, ctx, escape=False)
        rendered_body = self._substitute(body_template, ctx, escape=True)
        return RenderedMessage(subject=rendered_subject, body=rendered_body)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_templates(
        self,
        template_version: MessageTemplateVersion,
        variant_key: str | None,
    ) -> tuple[str, str]:
        """Return ``(subject_tpl, body_tpl)`` for the given variant (or base)."""
        if variant_key is not None and template_version.variants_json:
            variants: dict = json.loads(template_version.variants_json)
            if variant_key not in variants:
                raise VariantNotFoundError(variant_key)
            variant = variants[variant_key]
            # Variant subject is optional — fall back to base subject_template.
            subject_tpl = variant.get("subject") or template_version.subject_template
            body_tpl = variant["body"]
            return subject_tpl, body_tpl

        return template_version.subject_template, template_version.body_template

    @staticmethod
    def _extract_vars(text: str) -> set[str]:
        """Return the set of variable names found in *text*."""
        return set(_VAR_RE.findall(text))

    def _validate_vars(self, subject_tpl: str, body_tpl: str) -> None:
        """Raise :class:`UnknownVariableError` if any unknown vars are present."""
        used = self._extract_vars(subject_tpl + body_tpl)
        unknown = used - SUPPORTED_VARS
        if unknown:
            raise UnknownVariableError(unknown)

    @staticmethod
    def _substitute(
        template: str,
        context: dict[str, Any],
        *,
        escape: bool,
    ) -> str:
        """Replace every ``{{var}}`` token in *template* with its context value.

        Missing variables are replaced with an empty string and a warning is
        logged (Req 7.8).  When *escape* is ``True`` the substituted value is
        HTML-escaped (Req 7.7).
        """

        def replacer(match: re.Match) -> str:  # type: ignore[type-arg]
            var = match.group(1)
            if var not in context:
                logger.warning(
                    "Template variable '{{%s}}' not found in render context; "
                    "substituting empty string.",
                    var,
                )
                return ""
            value = str(context[var]) if context[var] is not None else ""
            return html.escape(value) if escape else value

        return _VAR_RE.sub(replacer, template)
