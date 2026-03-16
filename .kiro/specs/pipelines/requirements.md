# Requirements Document

## Introduction

The Pipelines feature adds a configurable, multi-stage lead journey system to the existing multi-tenant SaaS platform. It acts as an orchestration layer over existing capabilities (email templates, qualification forms, scoring buckets, audit logs), giving platform admins a visual pipeline builder and agents a richer lead detail view. This document derives requirements from the approved design document.

## Glossary

- **Pipeline**: A named, ordered collection of stages representing a lead journey, scoped to a single company. Only one pipeline may be active per company at a time.
- **PipelineStage**: A single step within a pipeline, with a name, key, color, category, and ordering position.
- **LeadStageHistory**: An immutable record of every stage transition a lead has undergone, including source and reason.
- **LeadStageTransitionEngine**: The orchestration service that receives lifecycle events, resolves event mappings, evaluates automation rules, and delegates to platform services.
- **PipelineEventMapping**: A configuration record that maps a built-in platform lifecycle event to a target pipeline stage.
- **PipelineActionRule**: A When/Then automation rule with a trigger, optional condition, and one or more action steps.
- **PipelineActionRuleStep**: A single action within a rule (e.g., send email, move stage).
- **ChangeSource**: The origin of a stage transition — one of `system`, `event`, `automation`, or `manual`.
- **StageCategory**: The classification of a stage — one of `open`, `in_progress`, `waiting`, `won`, or `lost`.
- **BuiltInEventType**: A platform lifecycle event — one of `lead_created`, `response_email_sent`, `qualification_form_sent`, `qualification_form_submitted`, `qualification_bucket_hot`, `qualification_bucket_warm`, `qualification_bucket_nurture`.
- **Platform_Admin**: A user with the `platform_admin` role who manages pipeline configuration.
- **Agent**: A user with the `agent` role who views lead pipeline status on the lead detail page.
- **PipelineService**: The service responsible for pipeline CRUD and active pipeline enforcement.
- **PipelineStageService**: The service responsible for stage CRUD, ordering, and validation.
- **LeadStageService**: The service responsible for lead-to-stage assignment and history recording.
- **PipelineEventMappingService**: The service responsible for event-to-stage mapping configuration.
- **PipelineActionRuleService**: The service responsible for automation rule CRUD and evaluation.
- **Metrics_Endpoint**: The API endpoint that returns aggregated pipeline metrics for a given pipeline.

---

## Requirements

### Requirement 1: Pipeline Configuration Management

**User Story:** As a Platform_Admin, I want to create and manage pipelines for my company, so that I can define the lead journey stages appropriate for my business.

#### Acceptance Criteria

1. THE PipelineService SHALL provide create, read, update, and list operations for pipelines scoped to a company.
2. WHEN a pipeline is created, THE PipelineService SHALL require a non-empty name of at most 100 characters.
3. THE PipelineService SHALL enforce that pipeline names are unique within a company.
4. WHEN a pipeline is activated, THE PipelineService SHALL set `is_active = true` on the target pipeline and `is_active = false` on all other pipelines belonging to the same company.
5. THE PipelineService SHALL enforce that at most one pipeline per company has `is_active = true` at any point in time.
6. WHEN a Platform_Admin requests the list of pipelines, THE PipelineService SHALL return only pipelines belonging to the requesting company.

### Requirement 2: Pipeline Stage Management

**User Story:** As a Platform_Admin, I want to create, configure, and reorder stages within a pipeline, so that I can model the exact steps of my lead journey.

#### Acceptance Criteria

1. THE PipelineStageService SHALL provide create, read, update, delete, and reorder operations for stages within a pipeline.
2. WHEN a stage is created or updated, THE PipelineStageService SHALL validate that the `key` field contains only lowercase alphanumeric characters and underscores.
3. THE PipelineStageService SHALL enforce that stage keys are unique within a pipeline.
4. WHEN stages are reordered, THE PipelineStageService SHALL assign positions as a contiguous 1-based integer sequence matching the provided order.
5. THE PipelineStageService SHALL enforce that exactly one stage per pipeline has `is_default = true` at any point in time.
6. WHEN a stage is set as the default, THE PipelineStageService SHALL unset the default flag on all other stages in the same pipeline.
7. WHEN a stage is created or updated, THE PipelineStageService SHALL validate that `category` is one of: `open`, `in_progress`, `waiting`, `won`, `lost`.
8. THE PipelineStageService SHALL enforce that `is_closed_won` and `is_closed_lost` are mutually exclusive on any single stage.
9. WHEN a stage is created or updated, THE PipelineStageService SHALL validate that `color` is a valid hex color string.
10. IF a Platform_Admin attempts to delete a stage that has leads currently assigned to it, THEN THE PipelineStageService SHALL reject the request with HTTP 409 and include the count of affected leads in the response.
11. WHERE a `reassign_to_stage_id` parameter is provided on stage deletion, THE PipelineStageService SHALL reassign all leads from the deleted stage to the specified stage before completing the deletion.


### Requirement 3: Lead Stage Tracking and History

**User Story:** As a Platform_Admin, I want every lead stage transition to be recorded with full context, so that I have a complete audit trail of how each lead progressed through the pipeline.

#### Acceptance Criteria

1. WHEN a lead is assigned to a stage for the first time, THE LeadStageService SHALL create a `LeadStageHistory` entry with `from_stage_id` set to null.
2. WHEN a lead is moved from one stage to another, THE LeadStageService SHALL create a `LeadStageHistory` entry recording `from_stage_id`, `to_stage_id`, `change_source`, `change_reason`, and `changed_by_user_id`.
3. THE LeadStageService SHALL update `lead.current_stage_id` and `lead.stage_entered_at` on every stage transition.
4. THE lead `current_stage_id` SHALL always equal the `to_stage_id` of the most recent `LeadStageHistory` entry for that lead.
5. THE `LeadStageHistory` `change_source` field SHALL contain one of: `system`, `event`, `automation`, `manual`.
6. THE LeadStageService SHALL never delete or modify existing `LeadStageHistory` entries.
7. WHEN a Platform_Admin requests the stage history for a lead, THE LeadStageService SHALL return all history entries for that lead ordered by `created_at` ascending.


### Requirement 4: Pipeline Event Mappings

**User Story:** As a Platform_Admin, I want to map platform lifecycle events to pipeline stages, so that leads automatically advance through the pipeline when key events occur.

#### Acceptance Criteria

1. THE PipelineEventMappingService SHALL support the following built-in event types: `lead_created`, `response_email_sent`, `qualification_form_sent`, `qualification_form_submitted`, `qualification_bucket_hot`, `qualification_bucket_warm`, `qualification_bucket_nurture`.
2. THE PipelineEventMappingService SHALL enforce at most one mapping per `(pipeline_id, event_type)` pair, using upsert semantics on write.
3. WHEN an event mapping is created or updated, THE PipelineEventMappingService SHALL validate that `target_stage_id` belongs to the same pipeline as the mapping.
4. WHEN a stage referenced by an event mapping is deleted, THE PipelineEventMappingService SHALL automatically set `is_enabled = false` on the affected mapping.
5. WHEN a Platform_Admin requests the list of event mappings for a pipeline, THE PipelineEventMappingService SHALL return one entry per supported event type, including disabled mappings.


### Requirement 5: Pipeline Automation Rules

**User Story:** As a Platform_Admin, I want to define When/Then automation rules on my pipeline, so that actions like sending emails or moving stages happen automatically when conditions are met.

#### Acceptance Criteria

1. THE PipelineActionRuleService SHALL provide create, read, update, delete, and reorder operations for automation rules within a pipeline.
2. WHEN a rule is created or updated, THE PipelineActionRuleService SHALL validate that `trigger_type` is one of: `on_event`, `on_stage_enter`.
3. WHEN a rule is created or updated, THE PipelineActionRuleService SHALL validate that `condition_type` is one of: `bucket_is`, `stage_is`, `always`.
4. WHEN a rule is created or updated, THE PipelineActionRuleService SHALL validate that each action step's `action_type` is one of: `send_email_template`, `send_qualification_form`, `send_bucket_followup_email`, `move_to_stage`.
5. WHEN rules are reordered, THE PipelineActionRuleService SHALL assign positions as a contiguous 1-based integer sequence matching the provided order.
6. WHEN rules are evaluated, THE PipelineActionRuleService SHALL evaluate rules in ascending `position` order.
7. WHEN a rule's condition is not met, THE PipelineActionRuleService SHALL skip that rule and continue evaluating subsequent rules.
8. WHEN a rule is disabled (`is_enabled = false`), THE PipelineActionRuleService SHALL skip that rule during evaluation.
9. WHEN a rule is created or updated, THE PipelineActionRuleService SHALL validate `action_config_json` against the expected schema for the given `action_type`.


### Requirement 6: Lead Stage Transition Engine

**User Story:** As a Platform_Admin, I want platform lifecycle events to automatically trigger stage transitions and automation rules, so that the pipeline advances without manual intervention.

#### Acceptance Criteria

1. WHEN a lifecycle event is fired, THE LeadStageTransitionEngine SHALL look up the active pipeline for the lead's company before taking any action.
2. IF a company has no active pipeline, THEN THE LeadStageTransitionEngine SHALL create the lead with `pipeline_id`, `current_stage_id`, and `stage_entered_at` set to null and SHALL NOT raise an error.
3. WHEN an event mapping exists for the fired event and `is_enabled = true`, THE LeadStageTransitionEngine SHALL move the lead to the mapped target stage with `change_source = "event"`.
4. WHEN an event mapping exists for the fired event and `is_enabled = false`, THE LeadStageTransitionEngine SHALL NOT move the lead to the mapped stage.
5. WHEN automation rules are evaluated, THE LeadStageTransitionEngine SHALL execute matching rules in ascending position order.
6. WHEN an automation rule action step fails, THE LeadStageTransitionEngine SHALL log the failure to the audit log and continue executing the remaining action steps without rolling back the stage transition.
7. WHEN a lead is created and an active pipeline exists, THE LeadStageTransitionEngine SHALL assign the lead to the pipeline's default stage with `change_source = "system"`.
8. THE LeadStageTransitionEngine SHALL write an audit log entry for every stage transition and every action executed.


### Requirement 7: Admin Pipeline API

**User Story:** As a Platform_Admin, I want a complete REST API for managing pipelines, stages, event mappings, and automation rules, so that the admin UI can provide full pipeline configuration capabilities.

#### Acceptance Criteria

1. THE admin pipeline API SHALL require `platform_admin` role authentication on all pipeline configuration endpoints.
2. THE admin pipeline API SHALL expose endpoints for pipeline CRUD at `/api/v1/pipelines` and `/api/v1/pipelines/{id}`.
3. THE admin pipeline API SHALL expose a `POST /api/v1/pipelines/{id}/activate` endpoint to set a pipeline as active.
4. THE admin pipeline API SHALL expose stage CRUD and reorder endpoints at `/api/v1/pipelines/{id}/stages` and `/api/v1/pipelines/{id}/stages/{stage_id}`.
5. THE admin pipeline API SHALL expose event mapping list and upsert endpoints at `/api/v1/pipelines/{id}/event-mappings` and `/api/v1/pipelines/{id}/event-mappings/{event_type}`.
6. THE admin pipeline API SHALL expose automation rule CRUD and reorder endpoints at `/api/v1/pipelines/{id}/rules` and `/api/v1/pipelines/{id}/rules/{rule_id}`.
7. THE admin pipeline API SHALL expose lead stage read and manual-move endpoints at `/api/v1/pipelines/leads/{lead_id}/stage`.
8. WHEN a Platform_Admin submits a `PATCH /api/v1/pipelines/leads/{lead_id}/stage` request, THE admin pipeline API SHALL move the lead to the specified stage with `change_source = "manual"` and record an audit log entry with the requesting user's ID.
9. THE admin pipeline API SHALL expose a metrics endpoint at `GET /api/v1/pipelines/{id}/metrics`.
10. THE admin pipeline API SHALL enforce company-level tenant isolation so that a Platform_Admin can only access pipelines belonging to their own company.


### Requirement 8: Pipeline Metrics

**User Story:** As a Platform_Admin, I want to see key pipeline metrics at a glance, so that I can identify bottlenecks and track overall pipeline health.

#### Acceptance Criteria

1. WHEN a Platform_Admin requests pipeline metrics, THE Metrics_Endpoint SHALL return the total count of leads currently assigned to the pipeline.
2. WHEN a Platform_Admin requests pipeline metrics, THE Metrics_Endpoint SHALL return the average time leads spend in each stage, computed from `LeadStageHistory`.
3. WHEN a Platform_Admin requests pipeline metrics, THE Metrics_Endpoint SHALL return the conversion rate to won stages (leads that have reached a `is_closed_won = true` stage divided by total leads in pipeline).
4. WHEN a Platform_Admin requests pipeline metrics, THE Metrics_Endpoint SHALL return the count of leads that have been in their current stage for more than 7 days.
5. THE Metrics_Endpoint SHALL compute all aggregations using database-level queries rather than loading all rows into application memory.


### Requirement 9: Admin Pipeline Builder UI

**User Story:** As a Platform_Admin, I want a visual pipeline builder at `/admin/pipelines`, so that I can configure stages, event mappings, and automation rules through an intuitive interface.

#### Acceptance Criteria

1. WHEN a Platform_Admin navigates to `/admin/pipelines`, THE Pipeline_Builder_UI SHALL display overview metric cards for: leads in pipeline, average time in stage, conversion to won, and stuck leads.
2. THE Pipeline_Builder_UI SHALL display a Builder tab with a horizontal stage flow showing colored stage pills in position order.
3. THE Pipeline_Builder_UI SHALL support drag-and-drop stage reordering using `@dnd-kit/core` and `@dnd-kit/sortable`.
4. WHEN a Platform_Admin clicks a stage pill, THE Pipeline_Builder_UI SHALL open a side drawer with editable fields for name, key, color, category, and default/won/lost toggles.
5. THE Pipeline_Builder_UI SHALL display a Built-in Rules tab with a table showing all supported event types, a target stage dropdown per row, and an enable/disable toggle per row.
6. THE Pipeline_Builder_UI SHALL display an Automations tab with card-based rule builders showing trigger, condition, and action step configuration.
7. THE Pipeline_Builder_UI SHALL display an Activity tab with a paginated table of `LeadStageHistory` entries showing lead name, from/to stage, source, reason, and timestamp.
8. WHEN no pipeline exists for the company, THE Pipeline_Builder_UI SHALL display a first-run template chooser modal offering: Real Estate Buyer Pipeline, Law Firm Pipeline, and Blank pipeline options.
9. WHERE multiple pipelines exist for a company, THE Pipeline_Builder_UI SHALL display a pipeline selector control.


### Requirement 10: Agent Lead Detail Pipeline Enrichment

**User Story:** As an Agent, I want to see the current pipeline stage and lifecycle history for each of my leads, so that I can understand where each lead is in the journey and take appropriate next actions.

#### Acceptance Criteria

1. THE agent lead detail page SHALL display a Pipeline section showing the lead's current stage name and the time elapsed since entering that stage.
2. THE agent lead detail page SHALL display a visual stage progress indicator showing all pipeline stages with the current stage highlighted.
3. THE agent lead detail page SHALL display a Lifecycle Status section listing completed lifecycle events (response email sent, qualification form sent, form submitted, scoring bucket) with their timestamps.
4. THE agent lead detail page SHALL display quick action buttons for available actions (e.g., Call, Email).
5. WHEN an Agent requests pipeline data for a lead, THE agent pipeline API endpoint SHALL return: `pipeline_name`, `current_stage`, `stage_entered_at`, all pipeline stages, lifecycle statuses, and stage history.
6. THE agent pipeline API endpoint SHALL enforce that an Agent can only retrieve pipeline data for leads belonging to their own account.
7. THE agent pipeline API endpoint SHALL be accessible at `GET /api/v1/agent/leads/{lead_id}/pipeline`.


### Requirement 11: Seed Data and Pipeline Templates

**User Story:** As a Platform_Admin, I want pre-built pipeline templates for common use cases, so that I can get started quickly without building a pipeline from scratch.

#### Acceptance Criteria

1. THE seeding system SHALL provide a Real Estate Buyer Pipeline template with stages appropriate for a real estate buyer lead journey.
2. THE seeding system SHALL provide a Law Firm Pipeline template with stages appropriate for a landlord-tenant law firm lead journey.
3. WHEN a template pipeline is created from the first-run modal, THE PipelineService SHALL create the pipeline with all template stages, event mappings, and default configuration pre-populated.
4. THE seeding system SHALL integrate with the existing `scripts/seed_data.py` pattern.


### Requirement 12: Data Integrity and Error Handling

**User Story:** As a Platform_Admin, I want the system to handle error conditions gracefully and maintain data integrity, so that pipeline configuration mistakes do not corrupt lead data or disrupt operations.

#### Acceptance Criteria

1. IF a stage referenced by an event mapping is deleted, THEN THE PipelineEventMappingService SHALL disable the mapping and flag it in the admin UI rather than deleting it.
2. IF a Platform_Admin attempts to delete a stage with active leads and no `reassign_to_stage_id` is provided, THEN THE admin pipeline API SHALL return HTTP 409 with a message indicating the number of affected leads.
3. WHEN an automation rule action step fails during execution, THE LeadStageTransitionEngine SHALL write a failure record to the audit log including the rule ID, step ID, and error details.
4. WHEN an automation rule action step fails, THE LeadStageTransitionEngine SHALL continue executing the remaining steps in the rule without rolling back any completed stage transitions.
5. THE `action_config_json` field on PipelineActionRuleStep SHALL be validated against the expected schema for its `action_type` on every write operation.
6. THE stage `key` field SHALL be sanitized to contain only alphanumeric characters and underscores before storage.


### Requirement 13: Database Schema and Performance

**User Story:** As a developer, I want the pipeline data model to be performant and correctly indexed, so that the system scales as lead volume grows.

#### Acceptance Criteria

1. THE database schema SHALL include a `pipelines` table, `pipeline_stages` table, `lead_stage_history` table, `pipeline_event_mappings` table, `pipeline_action_rules` table, and `pipeline_action_rule_steps` table.
2. THE `leads` table SHALL be extended with `pipeline_id`, `current_stage_id`, and `stage_entered_at` columns.
3. THE `lead_stage_history` table SHALL have a composite index on `(lead_id, created_at)` to support fast history lookups.
4. THE `pipeline_event_mappings` table SHALL have a unique constraint on `(pipeline_id, event_type)`.
5. THE `pipeline_stages` table SHALL have a unique constraint on `(pipeline_id, key)`.
6. THE PipelineEventMappingService and PipelineActionRuleService SHALL cache pipeline configuration per company in memory after first load and invalidate the cache on any write operation.
7. THE PipelineStageService SHALL perform stage reordering using a single bulk UPDATE statement rather than N individual UPDATE statements.

