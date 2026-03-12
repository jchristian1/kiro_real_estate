"""
Buyer leads repository — all SQLAlchemy queries for FormTemplate, FormVersion,
FormQuestion, FormLogicRule, ScoringConfig, ScoringVersion, MessageTemplate,
MessageTemplateVersion, and FormInvitation domains.

Requirements: 7.1, 7.2
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from gmail_lead_sync.preapproval.models_preapproval import (
    FormLogicRule,
    FormQuestion,
    FormTemplate,
    FormVersion,
    ScoringConfig,
    ScoringVersion,
)


# ---------------------------------------------------------------------------
# Form Template Repository
# ---------------------------------------------------------------------------


class FormTemplateRepository:
    """Data-access layer for FormTemplate records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_tenant(self, tenant_id: int) -> list[FormTemplate]:
        """Return all FormTemplate records for *tenant_id* ordered by created_at desc."""
        return (
            self._db.query(FormTemplate)
            .filter(FormTemplate.tenant_id == tenant_id)
            .order_by(FormTemplate.created_at.desc())
            .all()
        )

    def get_by_id(self, template_id: int, tenant_id: int) -> Optional[FormTemplate]:
        """Return the FormTemplate filtered by id and tenant_id, or None."""
        return (
            self._db.query(FormTemplate)
            .filter(FormTemplate.id == template_id, FormTemplate.tenant_id == tenant_id)
            .first()
        )

    def create(self, tenant_id: int, intent_type: str, name: str) -> FormTemplate:
        """Create and persist a new FormTemplate."""
        template = FormTemplate(
            tenant_id=tenant_id,
            intent_type=intent_type,
            name=name,
            status="draft",
            created_at=datetime.utcnow(),
        )
        self._db.add(template)
        self._db.commit()
        self._db.refresh(template)
        return template

    def update(
        self,
        template_id: int,
        tenant_id: int,
        name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[FormTemplate]:
        """Update a FormTemplate. Returns the updated record, or None if not found."""
        template = self.get_by_id(template_id, tenant_id)
        if template is None:
            return None
        if name is not None:
            template.name = name
        if status is not None:
            template.status = status
        self._db.commit()
        self._db.refresh(template)
        return template

    def delete(self, template_id: int, tenant_id: int) -> Optional[FormTemplate]:
        """Delete a FormTemplate. Returns the deleted record, or None if not found."""
        template = self.get_by_id(template_id, tenant_id)
        if template is None:
            return None
        self._db.delete(template)
        self._db.commit()
        return template


# ---------------------------------------------------------------------------
# Form Version Repository
# ---------------------------------------------------------------------------


class FormVersionRepository:
    """Data-access layer for FormVersion records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_template(self, template_id: int) -> list[FormVersion]:
        """Return all FormVersion records for *template_id* ordered by version_number desc."""
        return (
            self._db.query(FormVersion)
            .filter(FormVersion.template_id == template_id)
            .order_by(FormVersion.version_number.desc())
            .all()
        )

    def get_by_id(self, version_id: int, template_id: int) -> Optional[FormVersion]:
        """Return the FormVersion filtered by id and template_id, or None."""
        return (
            self._db.query(FormVersion)
            .filter(FormVersion.id == version_id, FormVersion.template_id == template_id)
            .first()
        )

    def get_latest(self, template_id: int) -> Optional[FormVersion]:
        """Return the latest FormVersion for *template_id*, or None."""
        return (
            self._db.query(FormVersion)
            .filter(FormVersion.template_id == template_id)
            .order_by(FormVersion.version_number.desc())
            .first()
        )

    def deactivate_all(self, template_id: int) -> None:
        """Set is_active=False on all versions for *template_id*."""
        self._db.query(FormVersion).filter(FormVersion.template_id == template_id).update(
            {"is_active": False}, synchronize_session="fetch"
        )

    def create(
        self,
        template_id: int,
        version_number: int,
        schema_json: str,
        questions: list[Any],
        logic_rules: list[Any],
    ) -> FormVersion:
        """Create a new active FormVersion with its questions and logic rules."""
        now = datetime.utcnow()
        version = FormVersion(
            template_id=template_id,
            version_number=version_number,
            schema_json=schema_json,
            created_at=now,
            published_at=now,
            is_active=True,
        )
        self._db.add(version)
        self._db.flush()

        for q in questions:
            self._db.add(FormQuestion(
                form_version_id=version.id,
                question_key=q.question_key,
                type=q.type,
                label=q.label,
                required=q.required,
                options_json=q.options_json,
                order=q.order,
                validation_json=q
.validation_json,
            ))

        for rule in logic_rules:
            self._db.add(FormLogicRule(
                form_version_id=version.id,
                rule_json=rule.rule_json,
            ))

        self._db.commit()
        self._db.refresh(version)
        return version

    def activate(self, version_id: int, template_id: int) -> Optional[FormVersion]:
        """Set is_active=True on *version_id*, False on all others for *template_id*."""
        target = self.get_by_id(version_id, template_id)
        if target is None:
            return None
        self.deactivate_all(template_id)
        target.is_active = True
        self._db.commit()
        self._db.refresh(target)
        return target


# ---------------------------------------------------------------------------
# Scoring Config Repository
# ---------------------------------------------------------------------------


class ScoringConfigRepository:
    """Data-access layer for ScoringConfig records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_tenant(self, tenant_id: int) -> list[ScoringConfig]:
        """Return all ScoringConfig records for *tenant_id* ordered by created_at desc."""
        return (
            self._db.query(ScoringConfig)
            .filter(ScoringConfig.tenant_id == tenant_id)
            .order_by(ScoringConfig.created_at.desc())
            .all()
        )

    def get_by_id(self, config_id: int, tenant_id: int) -> Optional[ScoringConfig]:
        """Return the ScoringConfig filtered by id and tenant_id, or None."""
        return (
            self._db.query(ScoringConfig)
            .filter(ScoringConfig.id == config_id, ScoringConfig.tenant_id == tenant_id)
            .first()
        )

    def create(self, tenant_id: int, intent_type: str, name: str) -> ScoringConfig:
        """Create and persist a new ScoringConfig."""
        config = ScoringConfig(
            tenant_id=tenant_id,
            intent_type=intent_type,
            name=name,
            created_at=datetime.utcnow(),
        )
        self._db.add(config)
        self._db.commit()
        self._db.refresh(config)
        return config

    def update_name(self, config_id: int, tenant_id: int, name: str) -> Optional[ScoringConfig]:
        """Rename a ScoringConfig. Returns the updated record, or None if not found."""
        config = self.get_by_id(config_id, tenant_id)
        if config is None:
            return None
        config.name = name
        self._db.commit()
        self._db.refresh(config)
        return config

    def delete(self, config_id: int, tenant_id: int) -> Optional[ScoringConfig]:
        """Delete a ScoringConfig. Returns the deleted record, or None if not found."""
        config = self.get_by_id(config_id, tenant_id)
        if config is None:
            return None
        self._db.delete(config)
        self._db.commit()
        return config

    def get_active_version_for_intent(
        self, tenant_id: int, intent_type: str
    ) -> Optional[ScoringVersion]:
        """Return the active ScoringVersion for *tenant_id* and *intent_type*, or None."""
        return (
            self._db.query(ScoringVersion)
            .join(ScoringConfig)
            .filter(
                ScoringConfig.tenant_id == tenant_id,
                ScoringConfig.intent_type == intent_type,
                ScoringVersion.is_active == True,  # noqa: E712
            )
            .first()
        )


# ---------------------------------------------------------------------------
# Scoring Version Repository
# ---------------------------------------------------------------------------


class ScoringVersionRepository:
    """Data-access layer for ScoringVersion records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_config(self, config_id: int) -> list[ScoringVersion]:
        """Return all ScoringVersion records for *config_id* ordered by version_number desc."""
        return (
            self._db.query(ScoringVersion)
            .filter(ScoringVersion.scoring_config_id == config_id)
            .order_by(ScoringVersion.version_number.desc())
            .all()
        )

    def get_by_id(self, version_id: int, config_id: int) -> Optional[ScoringVersion]:
        """Return the ScoringVersion filtered by id and config_id, or None."""
        return (
            self._db.query(ScoringVersion)
            .filter(ScoringVersion.id == version_id, ScoringVersion.scoring_config_id == config_id)
            .first()
        )

    def get_latest(self, config_id: int) -> Optional[ScoringVersion]:
        """Return the latest ScoringVersion for *config_id*, or None."""
        return (
            self._db.query(ScoringVersion)
            .filter(ScoringVersion.scoring_config_id == config_id)
            .order_by(ScoringVersion.version_number.desc())
            .first()
        )

    def deactivate_all(self, config_id: int) -> None:
        """Set is_active=False on all versions for *config_id*."""
        self._db.query(ScoringVersion).filter(ScoringVersion.scoring_config_id == config_id).update(
            {"is_active": False}, synchronize_session="fetch"
        )

    def create(
        self,
        config_id: int,
        version_number: int,
        rules_json: str,
        thresholds_json: str,
    ) -> ScoringVersion:
        """Create a new active ScoringVersion."""
        now = datetime.utcnow()
        version = ScoringVersion(
            scoring_config_id=config_id,
            version_number=version_number,
            rules_json=rules_json,
            thresholds_json=thresholds_json,
            created_at=now,
            published_at=now,
            is_active=True,
        )
        self._db.add(version)
        self._db.commit()
        self._db.refresh(version)
        return version

    def activate(self, version_id: int, config_id: int) -> Optional[ScoringVersion]:
        """Set is_active=True on *version_id*, False on all others for *config_id*."""
        target = self.get_by_id(version_id, config_id)
        if target is None:
            return None
        self.deactivate_all(config_id)
        target.is_active = True
        self._db.commit()
        self._db.refresh(target)
        return target


# ---------------------------------------------------------------------------
# Message Template Repository
# ---------------------------------------------------------------------------


class MessageTemplateRepository:
    """Data-access layer for MessageTemplate and MessageTemplateVersion records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _model(self):
        from gmail_lead_sync.preapproval.models_preapproval import MessageTemplate
        return MessageTemplate

    def _version_model(self):
        from gmail_lead_sync.preapproval.models_preapproval import MessageTemplateVersion
        return MessageTemplateVersion

    def list_for_tenant(self, tenant_id: int) -> list:
        """Return all MessageTemplate records for *tenant_id* ordered by created_at desc."""
        M = self._model()
        return (
            self._db.query(M)
            .filter(M.tenant_id == tenant_id)
            .order_by(M.created_at.desc())
            .all()
        )

    def get_by_id(self, template_id: int, tenant_id: int):
        """Return the MessageTemplate filtered by id and tenant_id, or None."""
        M = self._model()
        return (
            self._db.query(M)
            .filter(M.id == template_id, M.tenant_id == tenant_id)
            .first()
        )

    def create(self, tenant_id: int, intent_type: str, key: str):
        """Create and persist a new MessageTemplate."""
        M = self._model()
        template = M(
            tenant_id=tenant_id,
            intent_type=intent_type,
            key=key,
            created_at=datetime.utcnow(),
        )
        self._db.add(template)
        self._db.commit()
        self._db.refresh(template)
        return template

    def update(self, template_id: int, tenant_id: int, key: str, intent_type: str):
        """Update a MessageTemplate. Returns the updated record, or None if not found."""
        template = self.get_by_id(template_id, tenant_id)
        if template is None:
            return None
        template.key = key
        template.intent_type = intent_type
        self._db.commit()
        self._db.refresh(template)
        return template

    def delete(self, template_id: int, tenant_id: int):
        """Delete a MessageTemplate. Returns the deleted record, or None if not found."""
        template = self.get_by_id(template_id, tenant_id)
        if template is None:
            return None
        self._db.delete(template)
        self._db.commit()
        return template

    def list_versions(self, template_id: int) -> list:
        """Return all MessageTemplateVersion records for *template_id* ordered by version_number desc."""
        V = self._version_model()
        return (
            self._db.query(V)
            .filter(V.template_id == template_id)
            .order_by(V.version_number.desc())
            .all()
        )

    def get_version_by_id(self, version_id: int, template_id: int):
        """Return the MessageTemplateVersion filtered by id and template_id, or None."""
        V = self._version_model()
        return (
            self._db.query(V)
            .filter(V.id == version_id, V.template_id == template_id)
            .first()
        )

    def get_latest_version(self, template_id: int):
        """Return the latest MessageTemplateVersion for *template_id*, or None."""
        V = self._version_model()
        return (
            self._db.query(V)
            .filter(V.template_id == template_id)
            .order_by(V.version_number.desc())
            .first()
        )

    def deactivate_all_versions(self, template_id: int) -> None:
        """Set is_active=False on all versions for *template_id*."""
        V = self._version_model()
        self._db.query(V).filter(V.template_id == template_id).update(
            {"is_active": False}, synchronize_session="fetch"
        )

    def create_version(
        self,
        template_id: int,
        version_number: int,
        subject_template: str,
        body_template: str,
        variants_json: Optional[str] = None,
    ):
        """Create a new active MessageTemplateVersion."""
        V = self._version_model()
        now = datetime.utcnow()
        version = V(
            template_id=template_id,
            version_number=version_number,
            subject_template=subject_template,
            body_template=body_template,
            variants_json=variants_json,
            created_at=now,
            published_at=now,
            is_active=True,
        )
        self._db.add(version)
        self._db.commit()
        self._db.refresh(version)
        return version

    def activate_version(self, version_id: int, template_id: int):
        """Set is_active=True on *version_id*, False on all others for *template_id*."""
        target = self.get_version_by_id(version_id, template_id)
        if target is None:
            return None
        self.deactivate_all_versions(template_id)
        target.is_active = True
        self._db.commit()
        self._db.refresh(target)
        return target


# ---------------------------------------------------------------------------
# Form Invitation Repository
# ---------------------------------------------------------------------------


class FormInvitationRepository:
    """Data-access layer for FormInvitation and FormVersion lookup."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_invitation_by_token_hash(self, token_hash: str):
        """Return the FormInvitation for *token_hash*, or None."""
        from gmail_lead_sync.preapproval.models_preapproval import FormInvitation
        return (
            self._db.query(FormInvitation)
            .filter(FormInvitation.token_hash == token_hash)
            .first()
        )

    def get_form_version_by_id(self, version_id: int):
        """Return the FormVersion with the given primary key, or None."""
        return self._db.get(FormVersion, version_id)


# ---------------------------------------------------------------------------
# Buyer Leads Query Repository (for admin monitoring endpoints)
# ---------------------------------------------------------------------------


class BuyerLeadsQueryRepository:
    """Data-access layer for admin lead state monitoring and audit queries."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_agent_ids_for_tenant(self, tenant_id: int) -> list[str]:
        """Return all agent_ids whose credentials belong to *tenant_id*."""
        from gmail_lead_sync.models import Credentials
        return [
            c.agent_id
            for c in self._db.query(Credentials).filter(Credentials.company_id == tenant_id).all()
        ]

    def list_leads_by_state(
        self,
        agent_ids: list[str],
        state: Optional[str] = None,
        bucket: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list, int]:
        """Return (leads, total) filtered by state and/or bucket for *agent_ids*."""
        from gmail_lead_sync.models import Lead
        from gmail_lead_sync.preapproval.models_preapproval import FormSubmission, SubmissionScore

        query = self._db.query(Lead).filter(Lead.agent_id.in_(agent_ids))
        if state is not None:
            query = query.filter(Lead.current_state == state)
        if bucket is not None:
            query = (
                query
                .join(FormSubmission, FormSubmission.lead_id == Lead.id)
                .join(SubmissionScore, SubmissionScore.submission_id == FormSubmission.id)
                .filter(SubmissionScore.bucket == bucket)
            )
        total = query.count()
        leads = (
            query
            .order_by(Lead.current_state_updated_at.desc().nullslast(), Lead.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return leads, total

    def get_leads_funnel(self, agent_ids: list[str]) -> dict[str, int]:
        """Return count of leads at each state for *agent_ids*."""
        from sqlalchemy import func
        from gmail_lead_sync.models import Lead

        rows = (
            self._db.query(Lead.current_state, func.count(Lead.id).label("count"))
            .filter(Lead.agent_id.in_(agent_ids), Lead.current_state.isnot(None))
            .group_by(Lead.current_state)
            .all()
        )
        return {row.current_state: row.count for row in rows}

    def get_lead_history(self, lead_id: int) -> dict:
        """Return full preapproval history for a single lead."""
        import json as _json
        from gmail_lead_sync.preapproval.models_preapproval import (
            FormSubmission,
            LeadInteraction,
        )
        from api.services.lead_state_machine import LeadState
        from gmail_lead_sync.preapproval.models_preapproval import LeadStateTransition

        transitions = (
            self._db.query(LeadStateTransition)
            .filter(LeadStateTransition.lead_id == lead_id)
            .order_by(LeadStateTransition.occurred_at.asc())
            .all()
        )

        submissions_raw = (
            self._db.query(FormSubmission)
            .filter(FormSubmission.lead_id == lead_id)
            .order_by(FormSubmission.submitted_at.desc())
            .all()
        )

        submissions = []
        for sub in submissions_raw:
            answers = [
                {"question_key": a.question_key, "answer": _json.loads(a.answer_value_json)}
                for a in sub.answers
            ]
            score = None
            if sub.score:
                score = {
                    "total": sub.score.total_score,
                    "bucket": sub.score.bucket,
                    "breakdown": _json.loads(sub.score.breakdown_json),
                    "explanation": sub.score.explanation_text,
                }
            submissions.append({
                "id": sub.id,
                "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
                "form_version_id": sub.form_version_id,
                "answers": answers,
                "score": score,
            })

        interactions = (
            self._db.query(LeadInteraction)
            .filter(LeadInteraction.lead_id == lead_id)
            .order_by(LeadInteraction.occurred_at.desc())
            .all()
        )

        return {
            "lead_id": lead_id,
            "state_transitions": [
                {
                    "id": t.id,
                    "from_state": t.from_state,
                    "to_state": t.to_state,
                    "occurred_at": t.occurred_at.isoformat() if t.occurred_at else None,
                    "actor_type": t.actor_type,
                    "metadata": _json.loads(t.metadata_json) if t.metadata_json else None,
                }
                for t in transitions
            ],
            "submissions": submissions,
            "interactions": [
                {
                    "id": i.id,
                    "channel": i.channel,
                    "direction": i.direction,
                    "occurred_at": i.occurred_at.isoformat() if i.occurred_at else None,
                    "content_text": i.content_text,
                    "metadata": _json.loads(i.metadata_json) if i.metadata_json else None,
                }
                for i in interactions
            ],
        }

    def get_audit_entries(
        self,
        tenant_id: int,
        lead_id: Optional[int] = None,
        event_type: Optional[str] = None,
        dt_from: Optional[datetime] = None,
        dt_to: Optional[datetime] = None,
    ) -> list[dict]:
        """Return merged audit entries (state transitions + interactions) for *tenant_id*."""
        from gmail_lead_sync.preapproval.models_preapproval import LeadInteraction, LeadStateTransition
        from api.services.lead_state_machine import LeadState

        entries: list[dict] = []

        include_transitions = event_type in (None, "state_transition")
        include_interactions = event_type in (None, "interaction")

        if include_transitions:
            q = self._db.query(LeadStateTransition).filter(LeadStateTransition.tenant_id == tenant_id)
            if lead_id is not None:
                q = q.filter(LeadStateTransition.lead_id == lead_id)
            if dt_from is not None:
                q = q.filter(LeadStateTransition.occurred_at >= dt_from)
            if dt_to is not None:
                q = q.filter(LeadStateTransition.occurred_at <= dt_to)
            for row in q.all():
                entries.append({
                    "event_type": "state_transition",
                    "id": row.id,
                    "lead_id": row.lead_id,
                    "tenant_id": row.tenant_id,
                    "from_state": row.from_state,
                    "to_state": row.to_state,
                    "actor_type": row.actor_type,
                    "actor_id": row.actor_id,
                    "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
                    "metadata_json": row.metadata_json,
                })

        if include_interactions:
            q = self._db.query(LeadInteraction).filter(LeadInteraction.tenant_id == tenant_id)
            if lead_id is not None:
                q = q.filter(LeadInteraction.lead_id == lead_id)
            if dt_from is not None:
                q = q.filter(LeadInteraction.occurred_at >= dt_from)
            if dt_to is not None:
                q = q.filter(LeadInteraction.occurred_at <= dt_to)
            for row in q.all():
                entries.append({
                    "event_type": "interaction",
                    "id": row.id,
                    "lead_id": row.lead_id,
                    "tenant_id": row.tenant_id,
                    "channel": row.channel,
                    "direction": row.direction,
                    "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
                    "metadata_json": row.metadata_json,
                    "content_text": row.content_text,
                })

        entries.sort(key=lambda e: e["occurred_at"] or "", reverse=True)
        return entries
