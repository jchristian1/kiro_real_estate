"""
Pipeline seed templates for Real Estate and Law Firm verticals.

Provides ready-made pipeline configurations with stages and default event mappings.

Requirements: 11.1, 11.2, 11.3
"""

from sqlalchemy.orm import Session

from api.models.pipeline_models import (
    BuiltInEventType,
    ChangeSource,
    Pipeline,
    PipelineEventMapping,
    PipelineStage,
    StageCategory,
)


def _create_stages(db: Session, pipeline_id: int, stage_defs: list[dict]) -> dict[str, PipelineStage]:
    """Bulk-create stages and return a key→stage mapping."""
    stages: dict[str, PipelineStage] = {}
    for defn in stage_defs:
        stage = PipelineStage(
            pipeline_id=pipeline_id,
            name=defn["name"],
            key=defn["key"],
            color=defn["color"],
            category=defn["category"],
            position=defn["position"],
            is_default=defn.get("is_default", False),
            is_closed_won=defn.get("is_closed_won", False),
            is_closed_lost=defn.get("is_closed_lost", False),
        )
        db.add(stage)
        stages[defn["key"]] = stage
    db.flush()
    return stages


def _create_event_mappings(
    db: Session,
    pipeline_id: int,
    stages: dict[str, PipelineStage],
    mapping_defs: list[dict],
) -> None:
    """Create event mappings for the given pipeline."""
    for defn in mapping_defs:
        stage = stages.get(defn["stage_key"])
        if stage is None:
            continue
        db.add(
            PipelineEventMapping(
                pipeline_id=pipeline_id,
                event_type=defn["event_type"],
                target_stage_id=stage.id,
                is_enabled=True,
            )
        )
    db.flush()


def create_real_estate_pipeline(db: Session, company_id: int) -> Pipeline:
    """Create the Real Estate Buyer Pipeline template for *company_id*.

    Stages: New Lead → Contacted → Appointment Set → Under Contract → Won / Lost
    Default event mappings included.

    Requirements: 11.1, 11.3
    """
    pipeline = Pipeline(
        company_id=company_id,
        name="Real Estate Buyer Pipeline",
        description="Standard pipeline for real estate buyer leads.",
        is_active=False,
    )
    db.add(pipeline)
    db.flush()

    stage_defs = [
        {"name": "New Lead",         "key": "new_lead",        "color": "#6366F1", "category": StageCategory.active,      "position": 1, "is_default": True},
        {"name": "Contacted",        "key": "contacted",       "color": "#3B82F6", "category": StageCategory.active,      "position": 2},
        {"name": "Appointment Set",  "key": "appointment_set", "color": "#F59E0B", "category": StageCategory.active,      "position": 3},
        {"name": "Under Contract",   "key": "under_contract",  "color": "#10B981", "category": StageCategory.active,      "position": 4},
        {"name": "Won",              "key": "won",             "color": "#22C55E", "category": StageCategory.closed_won,  "position": 5, "is_closed_won": True},
        {"name": "Lost",             "key": "lost",            "color": "#EF4444", "category": StageCategory.closed_lost, "position": 6, "is_closed_lost": True},
    ]
    stages = _create_stages(db, pipeline.id, stage_defs)

    mapping_defs = [
        {"event_type": BuiltInEventType.lead_created,               "stage_key": "new_lead"},
        {"event_type": BuiltInEventType.response_email_sent,        "stage_key": "contacted"},
        {"event_type": BuiltInEventType.qualification_form_sent,    "stage_key": "contacted"},
        {"event_type": BuiltInEventType.qualification_form_submitted,"stage_key": "appointment_set"},
        {"event_type": BuiltInEventType.qualification_bucket_hot,   "stage_key": "appointment_set"},
        {"event_type": BuiltInEventType.qualification_bucket_warm,  "stage_key": "contacted"},
        {"event_type": BuiltInEventType.qualification_bucket_nurture,"stage_key": "contacted"},
    ]
    _create_event_mappings(db, pipeline.id, stages, mapping_defs)

    db.commit()
    db.refresh(pipeline)
    return pipeline


def create_law_firm_pipeline(db: Session, company_id: int) -> Pipeline:
    """Create the Law Firm Pipeline template for *company_id*.

    Stages: New Inquiry → Consultation Scheduled → Retained → Active Case → Closed Won / Closed Lost
    Default event mappings included.

    Requirements: 11.2, 11.3
    """
    pipeline = Pipeline(
        company_id=company_id,
        name="Law Firm Pipeline",
        description="Standard pipeline for law firm client leads.",
        is_active=False,
    )
    db.add(pipeline)
    db.flush()

    stage_defs = [
        {"name": "New Inquiry",             "key": "new_inquiry",            "color": "#6366F1", "category": StageCategory.active,      "position": 1, "is_default": True},
        {"name": "Consultation Scheduled",  "key": "consultation_scheduled", "color": "#3B82F6", "category": StageCategory.active,      "position": 2},
        {"name": "Retained",                "key": "retained",               "color": "#F59E0B", "category": StageCategory.active,      "position": 3},
        {"name": "Active Case",             "key": "active_case",            "color": "#10B981", "category": StageCategory.active,      "position": 4},
        {"name": "Closed Won",              "key": "closed_won",             "color": "#22C55E", "category": StageCategory.closed_won,  "position": 5, "is_closed_won": True},
        {"name": "Closed Lost",             "key": "closed_lost",            "color": "#EF4444", "category": StageCategory.closed_lost, "position": 6, "is_closed_lost": True},
    ]
    stages = _create_stages(db, pipeline.id, stage_defs)

    mapping_defs = [
        {"event_type": BuiltInEventType.lead_created,               "stage_key": "new_inquiry"},
        {"event_type": BuiltInEventType.response_email_sent,        "stage_key": "consultation_scheduled"},
        {"event_type": BuiltInEventType.qualification_form_sent,    "stage_key": "consultation_scheduled"},
        {"event_type": BuiltInEventType.qualification_form_submitted,"stage_key": "retained"},
        {"event_type": BuiltInEventType.qualification_bucket_hot,   "stage_key": "retained"},
        {"event_type": BuiltInEventType.qualification_bucket_warm,  "stage_key": "consultation_scheduled"},
        {"event_type": BuiltInEventType.qualification_bucket_nurture,"stage_key": "new_inquiry"},
    ]
    _create_event_mappings(db, pipeline.id, stages, mapping_defs)

    db.commit()
    db.refresh(pipeline)
    return pipeline
