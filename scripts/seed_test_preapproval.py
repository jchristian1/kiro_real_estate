"""
Seed test preapproval data for a lead.

Usage:
    python scripts/seed_test_preapproval.py --tenant-id 1 --lead-id 1

This simulates the full preapproval flow:
  1. NEW_EMAIL_RECEIVED → FORM_INVITE_CREATED → FORM_INVITE_SENT
  2. FORM_SUBMITTED → SCORING_COMPLETE
  3. Outbound email interaction (form invite)
  4. Inbound interaction (form submission)
"""

import sys
import json
import argparse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")

from api.main import SessionLocal
from gmail_lead_sync.preapproval.models_preapproval import (
    LeadStateTransition,
    FormSubmission,
    FormVersion,
    SubmissionAnswer,
    SubmissionScore,
    LeadInteraction,
    ScoringVersion,
    FormTemplate,
    ScoringConfig,
)
from gmail_lead_sync.preapproval.scoring_engine import ScoringEngine


def seed(tenant_id: int, lead_id: int):
    db = SessionLocal()
    try:
        # Check lead exists
        from gmail_lead_sync.models import Lead
        lead = db.get(Lead, lead_id)
        if not lead:
            print(f"Lead {lead_id} not found")
            return

        print(f"Seeding preapproval data for lead {lead_id} ({lead.name}), tenant {tenant_id}")

        # Clean up existing data for this lead
        db.query(LeadStateTransition).filter_by(lead_id=lead_id).delete()
        db.query(LeadInteraction).filter_by(lead_id=lead_id).delete()
        for sub in db.query(FormSubmission).filter_by(lead_id=lead_id).all():
            db.query(SubmissionAnswer).filter_by(submission_id=sub.id).delete()
            db.query(SubmissionScore).filter_by(submission_id=sub.id).delete()
        db.query(FormSubmission).filter_by(lead_id=lead_id).delete()
        db.commit()

        now = datetime.now(timezone.utc)

        # ── State transitions ──────────────────────────────────────────────
        transitions = [
            ("NEW_EMAIL_RECEIVED", None, now - timedelta(hours=3), "system"),
            ("FORM_INVITE_CREATED", "NEW_EMAIL_RECEIVED", now - timedelta(hours=3), "system"),
            ("FORM_INVITE_SENT", "FORM_INVITE_CREATED", now - timedelta(hours=2, minutes=58), "system"),
            ("FORM_SUBMITTED", "FORM_INVITE_SENT", now - timedelta(hours=1), "lead"),
            ("SCORING_COMPLETE", "FORM_SUBMITTED", now - timedelta(minutes=59), "system"),
        ]
        for to_state, from_state, ts, actor in transitions:
            db.add(LeadStateTransition(
                tenant_id=tenant_id,
                lead_id=lead_id,
                intent_type="BUY",
                from_state=from_state,
                to_state=to_state,
                occurred_at=ts,
                actor_type=actor,
                metadata_json=None,
            ))
        db.flush()
        print(f"  ✓ {len(transitions)} state transitions")

        # ── Form submission ────────────────────────────────────────────────
        # Find active form version for tenant
        form_version = (
            db.query(FormVersion)
            .join(FormTemplate)
            .filter(FormTemplate.tenant_id == tenant_id, FormVersion.is_active == True)
            .first()
        )
        if not form_version:
            print("  ⚠ No active form version found — skipping submission")
        else:
            submission = FormSubmission(
                tenant_id=tenant_id,
                lead_id=lead_id,
                form_version_id=form_version.id,
                submitted_at=now - timedelta(hours=1),
            )
            db.add(submission)
            db.flush()

            # Sample answers matching default seed questions
            sample_answers = {
                "timeline": "1_3_months",
                "budget": "500k_750k",
                "pre_approved": "yes",
                "property_type": "single_family",
                "bedrooms": "3",
                "location_flexibility": "somewhat_flexible",
                "agent_relationship": "no_agent",
            }
            for qkey, val in sample_answers.items():
                db.add(SubmissionAnswer(
                    submission_id=submission.id,
                    question_key=qkey,
                    answer_value_json=json.dumps(val),
                ))
            db.flush()
            print(f"  ✓ Form submission with {len(sample_answers)} answers")

            # ── Score ──────────────────────────────────────────────────────
            scoring_version = (
                db.query(ScoringVersion)
                .join(ScoringConfig)
                .filter(ScoringConfig.tenant_id == tenant_id, ScoringVersion.is_active == True)
                .first()
            )
            if scoring_version:
                engine = ScoringEngine()
                result = engine.compute(sample_answers, scoring_version, {})
                db.add(SubmissionScore(
                    submission_id=submission.id,
                    total_score=result.total,
                    bucket=result.bucket.value,
                    breakdown_json=json.dumps([b.__dict__ for b in result.breakdown]),
                    explanation_text=result.explanation,
                ))
                db.flush()
                print(f"  ✓ Score: {result.total} ({result.bucket})")
            else:
                print("  ⚠ No active scoring version — skipping score")

        # ── Interactions ───────────────────────────────────────────────────
        interactions = [
            {
                "channel": "email",
                "direction": "outbound",
                "occurred_at": now - timedelta(hours=2, minutes=58),
                "content_text": "Hi, we'd love to learn more about your home search. Please fill out our quick qualification form.",
            },
            {
                "channel": "email",
                "direction": "inbound",
                "occurred_at": now - timedelta(hours=1),
                "content_text": "[Form submitted via qualification link]",
            },
        ]
        for ix in interactions:
            db.add(LeadInteraction(
                tenant_id=tenant_id,
                lead_id=lead_id,
                intent_type="BUY",
                **ix,
            ))
        db.flush()
        print(f"  ✓ {len(interactions)} interactions")

        db.commit()
        print(f"\nDone. Open the Leads page, find lead {lead_id} ({lead.name}), and click View.")

    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--lead-id", type=int, default=1)
    args = parser.parse_args()
    seed(args.tenant_id, args.lead_id)
