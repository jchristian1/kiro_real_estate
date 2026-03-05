"""
Seed script for buyer lead qualification defaults.

Usage:
    python -m gmail_lead_sync.preapproval.seed --tenant-id <id>

Inserts:
- Default buyer qualification form template + version (7 questions)
- Default scoring config + version (15 rules, HOT>=80, WARM>=50)
- Default INITIAL_INVITE_EMAIL message template + version
- Default POST_SUBMISSION_EMAIL message template + version (HOT/WARM/NURTURE variants)

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
# Default form questions
# ---------------------------------------------------------------------------

DEFAULT_QUESTIONS = [
    {
        "question_key": "timeline",
        "type": "single_choice",
        "label": "When are you looking to buy?",
        "required": True,
        "options": [
            {"value": "asap", "label": "As soon as possible"},
            {"value": "1_3_months", "label": "1–3 months"},
            {"value": "3_6_months", "label": "3–6 months"},
            {"value": "6_plus_months", "label": "6+ months"},
            {"value": "not_sure", "label": "Not sure yet"},
        ],
        "order": 1,
    },
    {
        "question_key": "budget",
        "type": "single_choice",
        "label": "What is your approximate budget?",
        "required": True,
        "options": [
            {"value": "under_300k", "label": "Under $300,000"},
            {"value": "300k_500k", "label": "$300,000 – $500,000"},
            {"value": "500k_750k", "label": "$500,000 – $750,000"},
            {"value": "750k_1m", "label": "$750,000 – $1,000,000"},
            {"value": "over_1m", "label": "Over $1,000,000"},
            {"value": "not_sure", "label": "Not sure yet"},
        ],
        "order": 2,
    },
    {
        "question_key": "financing",
        "type": "single_choice",
        "label": "How do you plan to finance your purchase?",
        "required": True,
        "options": [
            {"value": "pre_approved", "label": "I'm already pre-approved"},
            {"value": "cash", "label": "Cash purchase"},
            {"value": "need_mortgage", "label": "I need to get a mortgage"},
            {"value": "not_sure", "label": "Not sure yet"},
        ],
        "order": 3,
    },
    {
        "question_key": "areas",
        "type": "multi_select",
        "label": "Which areas are you interested in?",
        "required": False,
        "options": [
            {"value": "downtown", "label": "Downtown"},
            {"value": "suburbs", "label": "Suburbs"},
            {"value": "rural", "label": "Rural"},
            {"value": "flexible", "label": "Flexible / Open to suggestions"},
        ],
        "order": 4,
    },
    {
        "question_key": "contact_preference",
        "type": "single_choice",
        "label": "How would you prefer we contact you?",
        "required": True,
        "options": [
            {"value": "email", "label": "Email"},
            {"value": "phone", "label": "Phone call"},
            {"value": "text", "label": "Text message"},
        ],
        "order": 5,
    },
    {
        "question_key": "has_agent",
        "type": "single_choice",
        "label": "Are you currently working with a real estate agent?",
        "required": True,
        "options": [
            {"value": "yes", "label": "Yes"},
            {"value": "no", "label": "No"},
        ],
        "order": 6,
    },
    {
        "question_key": "wants_tour",
        "type": "single_choice",
        "label": "Would you like to schedule a property tour?",
        "required": False,
        "options": [
            {"value": "yes", "label": "Yes, please"},
            {"value": "maybe", "label": "Maybe later"},
            {"value": "no", "label": "No thanks"},
        ],
        "order": 7,
    },
]


# ---------------------------------------------------------------------------
# Default scoring rules (15 rules)
# ---------------------------------------------------------------------------

DEFAULT_SCORING_RULES = [
    # Timeline
    {"question_key": "timeline", "answer_value": "asap",         "points": 30, "reason": "Immediate buyer"},
    {"question_key": "timeline", "answer_value": "1_3_months",   "points": 20, "reason": "Near-term buyer"},
    {"question_key": "timeline", "answer_value": "3_6_months",   "points": 10, "reason": "Mid-term buyer"},
    {"question_key": "timeline", "answer_value": "6_plus_months","points":  5, "reason": "Long-term buyer"},
    # Budget
    {"question_key": "budget",   "answer_value": "over_1m",      "points": 20, "reason": "High-value buyer"},
    {"question_key": "budget",   "answer_value": "750k_1m",      "points": 15, "reason": "Premium buyer"},
    {"question_key": "budget",   "answer_value": "500k_750k",    "points": 10, "reason": "Mid-range buyer"},
    {"question_key": "budget",   "answer_value": "300k_500k",    "points":  5, "reason": "Entry-level buyer"},
    # Financing
    {"question_key": "financing","answer_value": "pre_approved",  "points": 25, "reason": "Pre-approved — ready to buy"},
    {"question_key": "financing","answer_value": "cash",          "points": 25, "reason": "Cash buyer — no financing risk"},
    {"question_key": "financing","answer_value": "need_mortgage", "points":  5, "reason": "Needs mortgage — some risk"},
    # Agent
    {"question_key": "has_agent","answer_value": "no",            "points": 10, "reason": "No agent — open to representation"},
    {"question_key": "has_agent","answer_value": "yes",           "points": -5, "reason": "Already has agent"},
    # Tour
    {"question_key": "wants_tour","answer_value": "yes",          "points": 15, "reason": "Wants tour — high intent"},
    {"question_key": "wants_tour","answer_value": "maybe",        "points":  5, "reason": "Open to tour"},
]

DEFAULT_THRESHOLDS = {"HOT": 80, "WARM": 50}


# ---------------------------------------------------------------------------
# Default message templates
# ---------------------------------------------------------------------------

INITIAL_INVITE_SUBJECT = "You have a new property inquiry — complete your buyer profile"
INITIAL_INVITE_BODY = """\
Hi {{lead_name}},

Thank you for your interest in {{property_address}}.

To help us match you with the right properties, please take 2 minutes to complete your buyer profile:

{{form_url}}

This link expires in 48 hours.

Best regards,
{{agent_name}}
"""

POST_SUBMISSION_SUBJECT = "Thanks for completing your buyer profile, {{lead_name}}"
POST_SUBMISSION_BODY = """\
Hi {{lead_name}},

Thank you for completing your buyer profile. We'll be in touch shortly.

Best regards,
{{agent_name}}
"""

POST_SUBMISSION_VARIANTS = {
    "HOT": {
        "subject": "Great news, {{lead_name}} — let's schedule your tour",
        "body": """\
Hi {{lead_name}},

Based on your profile, you look like a great fit for properties in our portfolio.

I'd love to schedule a tour at your earliest convenience. Reply to this email or call us directly.

Best regards,
{{agent_name}}
""",
    },
    "WARM": {
        "subject": "Your buyer profile is ready, {{lead_name}}",
        "body": """\
Hi {{lead_name}},

Thanks for completing your buyer profile. We have some great options that match your criteria.

When you're ready to take the next step, we're here to help.

Best regards,
{{agent_name}}
""",
    },
    "NURTURE": {
        "subject": "We're here when you're ready, {{lead_name}}",
        "body": """\
Hi {{lead_name}},

Thank you for your interest. We'll keep you updated on new listings that match your preferences.

Feel free to reach out whenever you're ready to move forward.

Best regards,
{{agent_name}}
""",
    },
}


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_form_template(db: Session, tenant_id: int) -> FormTemplate:
    """Insert default buyer form template + version if not already present."""
    existing = (
        db.query(FormTemplate)
        .filter_by(tenant_id=tenant_id, intent_type="BUY", name="Default Buyer Qualification Form")
        .first()
    )
    if existing:
        return existing

    now = datetime.now(timezone.utc)

    template = FormTemplate(
        tenant_id=tenant_id,
        intent_type="BUY",
        name="Default Buyer Qualification Form",
        status="active",
        created_at=now,
    )
    db.add(template)
    db.flush()  # get template.id

    schema = [
        {
            "question_key": q["question_key"],
            "type": q["type"],
            "label": q["label"],
            "required": q["required"],
            "options": q.get("options"),
            "order": q["order"],
        }
        for q in DEFAULT_QUESTIONS
    ]

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

    for q in DEFAULT_QUESTIONS:
        db.add(FormQuestion(
            form_version_id=version.id,
            question_key=q["question_key"],
            type=q["type"],
            label=q["label"],
            required=q["required"],
            options_json=json.dumps(q["options"]) if q.get("options") else None,
            order=q["order"],
        ))

    return template


def seed_scoring_config(db: Session, tenant_id: int) -> ScoringConfig:
    """Insert default scoring config + version if not already present."""
    existing = (
        db.query(ScoringConfig)
        .filter_by(tenant_id=tenant_id, intent_type="BUY", name="Default Buyer Scoring")
        .first()
    )
    if existing:
        return existing

    now = datetime.now(timezone.utc)

    config = ScoringConfig(
        tenant_id=tenant_id,
        intent_type="BUY",
        name="Default Buyer Scoring",
        created_at=now,
    )
    db.add(config)
    db.flush()

    version = ScoringVersion(
        scoring_config_id=config.id,
        version_number=1,
        rules_json=json.dumps(DEFAULT_SCORING_RULES),
        thresholds_json=json.dumps(DEFAULT_THRESHOLDS),
        created_at=now,
        published_at=now,
        is_active=True,
    )
    db.add(version)

    return config


def seed_message_templates(db: Session, tenant_id: int) -> None:
    """Insert default message templates + versions if not already present."""
    now = datetime.now(timezone.utc)

    # INITIAL_INVITE_EMAIL
    invite_key = MessageTemplateKey.INITIAL_INVITE_EMAIL.value
    existing_invite = (
        db.query(MessageTemplate)
        .filter_by(tenant_id=tenant_id, intent_type="BUY", key=invite_key)
        .first()
    )
    if not existing_invite:
        invite_tmpl = MessageTemplate(
            tenant_id=tenant_id,
            intent_type="BUY",
            key=invite_key,
            created_at=now,
        )
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

    # POST_SUBMISSION_EMAIL
    post_key = MessageTemplateKey.POST_SUBMISSION_EMAIL.value
    existing_post = (
        db.query(MessageTemplate)
        .filter_by(tenant_id=tenant_id, intent_type="BUY", key=post_key)
        .first()
    )
    if not existing_post:
        post_tmpl = MessageTemplate(
            tenant_id=tenant_id,
            intent_type="BUY",
            key=post_key,
            created_at=now,
        )
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


def seed_all(db: Session, tenant_id: int) -> None:
    """Run all seed functions and commit."""
    seed_form_template(db, tenant_id)
    seed_scoring_config(db, tenant_id)
    seed_message_templates(db, tenant_id)
    db.commit()
    print(f"[seed] Done — tenant_id={tenant_id}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed default buyer lead qualification data")
    parser.add_argument("--tenant-id", type=int, required=True, help="Company/tenant ID to seed")
    args = parser.parse_args()

    import os
    from dotenv import load_dotenv
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    load_dotenv()  # load .env so DATABASE_URL is available
    db_url = os.getenv("DATABASE_URL", "sqlite:///./gmail_lead_sync.db")
    engine = create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    try:
        seed_all(session, args.tenant_id)
    finally:
        session.close()
