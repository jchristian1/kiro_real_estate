"""
Seed script for buyer lead qualification defaults.

Usage:
    python -m gmail_lead_sync.preapproval.seed --tenant-id <id>

Inserts:
- Default company (NYSLegal) if not present
- Law firm landlord/tenant intake form template + version (5 questions)
- Scoring config + version tuned for legal urgency
- Default INITIAL_INVITE_EMAIL message template + version
- Default POST_SUBMISSION_EMAIL message template + version

All versions are set is_active=True. Safe to run multiple times — skips if
a record with the same tenant_id + key/name already exists.
"""

import json
import argparse
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from gmail_lead_sync.preapproval.models_preapproval import (
    FormTemplate,
    FormVersion,
    FormQuestion,
    ScoringConfig,
    ScoringVersion,
    MessageTemplate,
    MessageTemplateVersion,
    MessageTemplateKey,
)


# ---------------------------------------------------------------------------
# Law firm landlord/tenant intake form (5 questions)
# ---------------------------------------------------------------------------

LAW_FIRM_QUESTIONS = [
    {
        "question_key": "situation_type",
        "type": "single_choice",
        "label": "Which best describes your situation?",
        "required": True,
        "options": [
            {"value": "landlord_tenant_issue", "label": "I am a landlord with a tenant issue"},
            {"value": "tenant_landlord_issue",  "label": "I am a tenant with a landlord issue"},
            {"value": "residential_lease",      "label": "Residential lease matter"},
            {"value": "commercial_lease",       "label": "Commercial lease matter"},
            {"value": "not_sure",               "label": "I am not sure"},
        ],
        "order": 1,
    },
    {
        "question_key": "issue_type",
        "type": "single_choice",
        "label": "What issue are you dealing with right now?",
        "required": True,
        "options": [
            {"value": "eviction",           "label": "Eviction / removal of tenant"},
            {"value": "unpaid_rent",        "label": "Unpaid rent / rent collection"},
            {"value": "lease_violation",    "label": "Lease violation / breach of lease"},
            {"value": "notice_to_quit",     "label": "Notice to quit / termination notice"},
            {"value": "security_deposit",   "label": "Security deposit dispute"},
            {"value": "property_damage",    "label": "Property damage"},
            {"value": "habitability",       "label": "Habitability / repair dispute"},
            {"value": "commercial_dispute", "label": "Commercial lease dispute"},
            {"value": "other",              "label": "Other"},
        ],
        "order": 2,
    },
    {
        "question_key": "urgency",
        "type": "single_choice",
        "label": "How urgent is your matter?",
        "required": True,
        "options": [
            {"value": "emergency",   "label": "Emergency \u2014 court date, notice, or lockout happening now or within 7 days"},
            {"value": "urgent",      "label": "Urgent \u2014 needs legal help within 2 weeks"},
            {"value": "soon",        "label": "Soon \u2014 I want help within 30 days"},
            {"value": "researching", "label": "Just researching options for now"},
        ],
        "order": 3,
    },
    {
        "question_key": "hiring_stage",
        "type": "single_choice",
        "label": "Where are you in the hiring process?",
        "required": True,
        "options": [
            {"value": "ready_now",              "label": "I am ready to speak with an attorney immediately"},
            {"value": "consultation_this_week", "label": "I want a consultation this week"},
            {"value": "comparing",              "label": "I am comparing attorneys"},
            {"value": "info_only",              "label": "I only want information for now"},
        ],
        "order": 4,
    },
    {
        "question_key": "legal_action_taken",
        "type": "single_choice",
        "label": "Have you already taken any legal action or received legal papers?",
        "required": True,
        "options": [
            {"value": "filed_court",     "label": "Yes \u2014 I filed something in court"},
            {"value": "received_papers", "label": "Yes \u2014 I received a notice, summons, or court papers"},
            {"value": "sent_notices",    "label": "Yes \u2014 I sent formal notices but have not filed"},
            {"value": "no_action",       "label": "No \u2014 not yet"},
        ],
        "order": 5,
    },
]


# ---------------------------------------------------------------------------
# Scoring rules tuned for legal urgency
# ---------------------------------------------------------------------------

LAW_FIRM_SCORING_RULES = [
    {"source": "answer", "key": "urgency",            "answer_value": "emergency",              "points": 40, "reason": "Emergency situation"},
    {"source": "answer", "key": "urgency",            "answer_value": "urgent",                 "points": 25, "reason": "Urgent timeline"},
    {"source": "answer", "key": "urgency",            "answer_value": "soon",                   "points": 10, "reason": "Near-term need"},
    {"source": "answer", "key": "hiring_stage",       "answer_value": "ready_now",              "points": 30, "reason": "Ready to hire"},
    {"source": "answer", "key": "hiring_stage",       "answer_value": "consultation_this_week", "points": 20, "reason": "Wants consult soon"},
    {"source": "answer", "key": "hiring_stage",       "answer_value": "comparing",              "points": 10, "reason": "Actively comparing"},
    {"source": "answer", "key": "legal_action_taken", "answer_value": "filed_court",            "points": 20, "reason": "Already in legal process"},
    {"source": "answer", "key": "legal_action_taken", "answer_value": "received_papers",        "points": 15, "reason": "Has legal papers"},
]

LAW_FIRM_THRESHOLDS = {"HOT": 80, "WARM": 50}


# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

INITIAL_INVITE_SUBJECT = "Complete your intake form \u2014 {{tenant.name}}"
INITIAL_INVITE_BODY = """\
Hi {{lead.first_name}},

Thank you for reaching out. To help us understand your situation and connect you with the right attorney, please take 2 minutes to complete our intake form:

{{form.link}}

This link expires in 48 hours.

Best regards,
{{tenant.name}}
"""

POST_SUBMISSION_SUBJECT = "We received your intake form, {{lead.first_name}}"
POST_SUBMISSION_BODY = """\
Hi {{lead.first_name}},

Thank you for completing our intake form. We will review your information and be in touch with you shortly.

Best regards,
{{tenant.name}}
"""

POST_SUBMISSION_VARIANTS = {
    "HOT": {
        "subject": "An attorney will contact you shortly, {{lead.first_name}}",
        "body": """\
Hi {{lead.first_name}},

Based on your intake form, your matter appears to be time-sensitive. One of our attorneys will be reaching out to you very shortly.

If you need immediate assistance, please call our office directly.

Best regards,
{{tenant.name}}
""",
    },
    "WARM": {
        "subject": "Next steps for your legal matter, {{lead.first_name}}",
        "body": """\
Hi {{lead.first_name}},

Thank you for completing our intake form. We have reviewed your information and will be in touch within 1-2 business days to discuss your options.

Best regards,
{{tenant.name}}
""",
    },
    "NURTURE": {
        "subject": "We\u2019re here when you\u2019re ready, {{lead.first_name}}",
        "body": """\
Hi {{lead.first_name}},

Thank you for your interest. We have noted your information and will keep you in mind as your situation develops.

Feel free to reach out whenever you are ready to move forward.

Best regards,
{{tenant.name}}
""",
    },
}


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_company(db: Session, name: str = "NYSLegal") -> "Company":
    """Create the default company if it doesn't exist. Returns the Company."""
    from gmail_lead_sync.models import Company
    existing = db.query(Company).filter(Company.name == name).first()
    if existing:
        return existing
    company = Company(name=name)
    db.add(company)
    db.flush()
    print(f"  ✓ Created company: {name} (id={company.id})")
    return company


def seed_form_template(db: Session, tenant_id: int) -> FormTemplate:
    """Insert law firm intake form template + version if not already present."""
    existing = (
        db.query(FormTemplate)
        .filter_by(tenant_id=tenant_id, intent_type="BUY", name="Law Firm")
        .first()
    )
    if existing:
        # Make sure its latest version is active
        from gmail_lead_sync.preapproval.models_preapproval import FormVersion as FV
        fv = (
            db.query(FV)
            .filter_by(template_id=existing.id, is_active=True)
            .first()
        )
        if fv:
            return existing

    now = datetime.now(timezone.utc)

    template = FormTemplate(
        tenant_id=tenant_id,
        intent_type="BUY",
        name="Law Firm",
        status="active",
        created_at=now,
    )
    db.add(template)
    db.flush()

    # Build schema_json with options_json as string (matches what the editor saves)
    questions_for_schema = []
    for q in LAW_FIRM_QUESTIONS:
        questions_for_schema.append({
            "question_key": q["question_key"],
            "type": q["type"],
            "label": q["label"],
            "required": q["required"],
            "options_json": json.dumps(q["options"]) if q.get("options") else None,
            "order": q["order"],
            "validation_json": None,
        })

    schema = {
        "questions": questions_for_schema,
        "logic_rules": [],
    }

    version = FormVersion(
        template_id=template.id,
        version_number=1,
        schema_json=json.dumps(schema),
        created_at=now,
        published_at=now,
        is_active=True,
    )
    db.add(version)
    db.flush()

    for q in LAW_FIRM_QUESTIONS:
        db.add(FormQuestion(
            form_version_id=version.id,
            question_key=q["question_key"],
            type=q["type"],
            label=q["label"],
            required=q["required"],
            options_json=json.dumps(q["options"]) if q.get("options") else None,
            order=q["order"],
        ))

    print(f"  ✓ Created form template 'Law Firm' (version 1, tenant_id={tenant_id})")
    return template


def seed_scoring_config(db: Session, tenant_id: int) -> ScoringConfig:
    """Insert law firm scoring config + version if not already present."""
    existing = (
        db.query(ScoringConfig)
        .filter_by(tenant_id=tenant_id, intent_type="BUY", name="Law Firm Scoring")
        .first()
    )
    if existing:
        return existing

    now = datetime.now(timezone.utc)

    config = ScoringConfig(
        tenant_id=tenant_id,
        intent_type="BUY",
        name="Law Firm Scoring",
        created_at=now,
    )
    db.add(config)
    db.flush()

    db.add(ScoringVersion(
        scoring_config_id=config.id,
        version_number=1,
        rules_json=json.dumps(LAW_FIRM_SCORING_RULES),
        thresholds_json=json.dumps(LAW_FIRM_THRESHOLDS),
        created_at=now,
        published_at=now,
        is_active=True,
    ))

    print(f"  ✓ Created scoring config 'Law Firm Scoring' (tenant_id={tenant_id})")
    return config


def seed_message_templates(db: Session, tenant_id: int) -> None:
    """Insert default message templates + versions if not already present."""
    now = datetime.now(timezone.utc)

    invite_key = MessageTemplateKey.INITIAL_INVITE_EMAIL.value
    if not db.query(MessageTemplate).filter_by(tenant_id=tenant_id, intent_type="BUY", key=invite_key).first():
        invite_tmpl = MessageTemplate(tenant_id=tenant_id, intent_type="BUY", key=invite_key, created_at=now)
        db.add(invite_tmpl)
        db.flush()
        db.add(MessageTemplateVersion(
            template_id=invite_tmpl.id,
            version_number=1,
            subject_template=INITIAL_INVITE_SUBJECT,
            body_template=INITIAL_INVITE_BODY,
            variants_json=None,
            created_at=now,
            published_at=now,
            is_active=True,
        ))
        print(f"  ✓ Created INITIAL_INVITE_EMAIL template (tenant_id={tenant_id})")

    post_key = MessageTemplateKey.POST_SUBMISSION_EMAIL.value
    if not db.query(MessageTemplate).filter_by(tenant_id=tenant_id, intent_type="BUY", key=post_key).first():
        post_tmpl = MessageTemplate(tenant_id=tenant_id, intent_type="BUY", key=post_key, created_at=now)
        db.add(post_tmpl)
        db.flush()
        db.add(MessageTemplateVersion(
            template_id=post_tmpl.id,
            version_number=1,
            subject_template=POST_SUBMISSION_SUBJECT,
            body_template=POST_SUBMISSION_BODY,
            variants_json=json.dumps(POST_SUBMISSION_VARIANTS),
            created_at=now,
            published_at=now,
            is_active=True,
        ))
        print(f"  ✓ Created POST_SUBMISSION_EMAIL template (tenant_id={tenant_id})")


def seed_assign_form_to_company(db: Session, company_id: int, form_version_id: int) -> None:
    """Set active_form_version_id on the company."""
    from gmail_lead_sync.models import Company
    company = db.query(Company).filter(Company.id == company_id).first()
    if company and company.active_form_version_id != form_version_id:
        company.active_form_version_id = form_version_id
        print(f"  ✓ Assigned form version {form_version_id} to company {company_id}")


def seed_all(db: Session, tenant_id: int) -> None:
    """Run all seed functions and commit."""
    company = seed_company(db)
    tenant_id = company.id  # always use the real company id

    form_template = seed_form_template(db, tenant_id)
    seed_scoring_config(db, tenant_id)
    seed_message_templates(db, tenant_id)

    # Assign the active form version to the company
    from gmail_lead_sync.preapproval.models_preapproval import FormVersion as FV
    active_fv = (
        db.query(FV)
        .filter_by(template_id=form_template.id, is_active=True)
        .first()
    )
    if active_fv:
        seed_assign_form_to_company(db, tenant_id, active_fv.id)

    db.commit()
    print(f"[seed] Done — tenant_id={tenant_id}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed default buyer lead qualification data")
    parser.add_argument("--tenant-id", type=int, default=1, help="Company/tenant ID to seed (default: 1)")
    args = parser.parse_args()

    import os
    from dotenv import load_dotenv
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    load_dotenv()
    db_url = os.getenv("DATABASE_URL", "sqlite:///./gmail_lead_sync.db")
    engine = create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    try:
        seed_all(session, args.tenant_id)
    finally:
        session.close()
