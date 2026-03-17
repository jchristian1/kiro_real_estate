# Implementation Plan: Pipelines

## Overview

Implement the configurable Pipelines feature as an orchestration layer over existing platform capabilities. The work proceeds in layers: data models → services → API → frontend → integration → seed data → property tests.

## Tasks

- [x] 1. SQLAlchemy models and Alembic migration
  - [x] 1.1 Create pipeline SQLAlchemy models
    - Create `api/models/pipeline_models.py` with ORM classes: `Pipeline`, `PipelineStage`, `LeadStageHistory`, `PipelineEventMapping`, `PipelineActionRule`, `PipelineActionRuleStep`
    - Add `pipeline_id`, `current_stage_id`, `stage_entered_at` columns to the existing `Lead` model (in `gmail_lead_sync/models.py` or wherever `Lead` is defined)
    - Add composite index on `lead_stage_history(lead_id, created_at)`
    - Add unique constraint on `pipeline_event_mappings(pipeline_id, event_type)`
    - Add unique constraint on `pipeline_stages(pipeline_id, key)`
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 1.2 Generate Alembic migration
    - Create migration in `alembic/versions/` covering all new tables and the three new `leads` columns
    - Ensure migration is reversible (downgrade removes new tables and columns)
    - _Requirements: 13.1, 13.2_

- [x] 2. Pydantic schemas
  - [x] 2.1 Create pipeline Pydantic schemas
    - Create `api/models/pipeline_schemas.py` with request/response schemas for all six models: `PipelineCreate`, `PipelineResponse`, `PipelineStageCreate`, `PipelineStageResponse`, `LeadStageHistoryResponse`, `PipelineEventMappingResponse`, `PipelineActionRuleCreate`, `PipelineActionRuleResponse`, `PipelineActionRuleStepCreate`, `AgentLeadPipelineResponse`
    - Include `StageCategory`, `ChangeSource`, `BuiltInEventType`, `ActionType` enums
    - _Requirements: 7.1, 10.5_

- [x] 3. PipelineService and PipelineStageService
  - [x] 3.1 Implement PipelineService
    - Create `api/services/pipeline_service.py`
    - Implement `get_active_pipeline`, `create_pipeline`, `update_pipeline`, `set_active_pipeline`, `list_pipelines`
    - Enforce single active pipeline per company: on activation, set all other company pipelines to `is_active = false`
    - Enforce unique pipeline name per company
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 3.2 Write property test for single active pipeline invariant
    - **Property 1: Single Active Pipeline Invariant**
    - **Validates: Requirements 1.4, 1.5**

  - [x] 3.3 Implement PipelineStageService
    - Create `api/services/pipeline_stage_service.py`
    - Implement `list_stages`, `create_stage`, `update_stage`, `delete_stage`, `reorder_stages`, `set_default_stage`
    - Validate `key` format (lowercase alphanumeric + underscores), uniqueness per pipeline
    - Validate `category` enum, `color` hex format, `is_closed_won`/`is_closed_lost` mutual exclusivity
    - Enforce exactly one `is_default` stage per pipeline
    - On stage deletion with active leads and no `reassign_to_stage_id`: raise HTTP 409 with affected lead count
    - On stage deletion with `reassign_to_stage_id`: reassign leads then delete
    - Implement bulk UPDATE for reorder (single query, not N queries)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 12.2, 13.7_

  - [x] 3.4 Write property test for stage position contiguity
    - **Property 2: Stage Positions Are Contiguous 1-Based**
    - **Validates: Requirements 2.4**

  - [x] 3.5 Write property test for exactly one default stage
    - **Property 3: Exactly One Default Stage Per Pipeline**
    - **Validates: Requirements 2.5, 2.6**

  - [x] 3.6 Write property test for stage key format invariant
    - **Property 13: Stage Key Format Invariant**
    - **Validates: Requirements 2.2, 12.6**

  - [x] 3.7 Write property test for closed won/lost mutual exclusivity
    - **Property 14: Closed Won and Closed Lost Are Mutually Exclusive**
    - **Validates: Requirements 2.8**

- [x] 4. LeadStageService
  - [x] 4.1 Implement LeadStageService
    - Create `api/services/lead_stage_service.py`
    - Implement `assign_initial_stage`, `move_stage`, `get_current_stage`, `get_stage_history`, `get_leads_in_stage`
    - On every transition: write `LeadStageHistory` entry, update `lead.current_stage_id` and `lead.stage_entered_at`
    - `assign_initial_stage` sets `from_stage_id = null`
    - Never delete or modify existing history entries
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 4.2 Write property test for stage history length equals move count
    - **Property 4: Stage History Length Equals Move Count**
    - **Validates: Requirements 3.1, 3.2**

  - [x] 4.3 Write property test for current stage consistency
    - **Property 5: Current Stage Consistency**
    - **Validates: Requirements 3.3, 3.4**

- [x] 5. PipelineEventMappingService
  - [x] 5.1 Implement PipelineEventMappingService
    - Create `api/services/pipeline_event_mapping_service.py`
    - Implement `list_mappings`, `upsert_mapping`, `get_mapping`
    - Enforce upsert semantics on `(pipeline_id, event_type)` — one mapping per pair
    - Validate `target_stage_id` belongs to the same pipeline
    - On stage deletion: auto-disable affected mappings (set `is_enabled = false`)
    - `list_mappings` returns one entry per supported event type including disabled ones
    - Implement in-memory cache per company; invalidate on any write
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 12.1, 13.6_

  - [x] 5.2 Write property test for event mapping uniqueness
    - **Property 6: Event Mapping Uniqueness**
    - **Validates: Requirements 4.2**

  - [x] 5.3 Write property test for event mapping cross-pipeline validation
    - **Property 7: Event Mapping Cross-Pipeline Validation**
    - **Validates: Requirements 4.3**

- [x] 6. PipelineActionRuleService
  - [x] 6.1 Implement PipelineActionRuleService
    - Create `api/services/pipeline_action_rule_service.py`
    - Implement `list_rules`, `create_rule`, `update_rule`, `delete_rule`, `reorder_rules`, `evaluate_rules`
    - Validate `trigger_type`, `condition_type`, `action_type` enums
    - Validate `action_config_json` schema per `action_type` on every write
    - `evaluate_rules`: return matching enabled rules in ascending `position` order; skip disabled rules and rules whose condition is not met
    - Implement in-memory cache per company; invalidate on any write
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 12.5, 13.6_

  - [x] 6.2 Write property test for rules evaluated in position order
    - **Property 9: Rules Evaluated in Position Order**
    - **Validates: Requirements 5.6, 6.5**

- [x] 7. LeadStageTransitionEngine
  - [x] 7.1 Implement LeadStageTransitionEngine
    - Create `api/services/lead_stage_transition_engine.py`
    - Implement `fire_event(lead_id, event_type, context)`
    - Look up active pipeline for lead's company; if none, return without error
    - Apply enabled event mapping → move lead with `change_source = "event"`
    - Evaluate and execute matching automation rules in position order
    - For each rule action step failure: write audit log entry (rule_id, step_id, error); continue remaining steps; do not roll back stage transition
    - Write audit log entry for every stage transition and every action executed
    - Delegate email/form/scoring actions to existing platform services (no duplication)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 12.3, 12.4_

  - [x] 7.2 Write property test for disabled mapping does not move lead
    - **Property 8: Disabled Mapping Does Not Move Lead**
    - **Validates: Requirements 6.4**

  - [x] 7.3 Write property test for failed action step does not halt remaining steps
    - **Property 10: Failed Action Step Does Not Halt Remaining Steps**
    - **Validates: Requirements 6.6, 12.3, 12.4**

- [x] 8. Checkpoint — backend services
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Admin pipeline router
  - [x] 9.1 Create admin_pipelines router
    - Create `api/routers/admin_pipelines.py` with `platform_admin` role guard on all routes
    - Implement pipeline CRUD: `GET/POST /api/v1/pipelines`, `GET/PUT /api/v1/pipelines/{id}`, `POST /api/v1/pipelines/{id}/activate`
    - Implement stage CRUD + reorder: `GET/POST /api/v1/pipelines/{id}/stages`, `PUT/DELETE /api/v1/pipelines/{id}/stages/{stage_id}`, `POST /api/v1/pipelines/{id}/stages/reorder`
    - Implement event mapping list + upsert: `GET /api/v1/pipelines/{id}/event-mappings`, `PUT /api/v1/pipelines/{id}/event-mappings/{event_type}`
    - Implement rule CRUD + reorder: `GET/POST /api/v1/pipelines/{id}/rules`, `PUT/DELETE /api/v1/pipelines/{id}/rules/{rule_id}`, `POST /api/v1/pipelines/{id}/rules/reorder`
    - Implement lead stage endpoints: `GET/PATCH /api/v1/pipelines/leads/{lead_id}/stage` (PATCH uses `change_source = "manual"`, records audit log with requesting user ID)
    - Implement metrics endpoint: `GET /api/v1/pipelines/{id}/metrics` (total leads, avg time per stage, conversion to won, stuck leads >7 days — all via DB aggregation queries)
    - Enforce company-level tenant isolation on all endpoints
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10, 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 9.2 Register admin_pipelines router in main.py
    - Import and mount `admin_pipelines_router` in `api/main.py` under `/api/v1` with tag `Pipelines`
    - _Requirements: 7.1_

- [x] 10. Agent pipeline router
  - [x] 10.1 Create agent pipeline endpoint
    - Add `GET /api/v1/agent/leads/{lead_id}/pipeline` to `api/routers/agent_leads.py` (or a new `agent_pipeline.py`)
    - Return `AgentLeadPipelineResponse`: `pipeline_name`, `current_stage`, `stage_entered_at`, all stages, lifecycle statuses, stage history
    - Enforce tenant isolation: agent can only access their own leads
    - _Requirements: 10.5, 10.6, 10.7_

  - [x] 10.2 Write property test for agent endpoint tenant isolation
    - **Property 11: Agent Endpoint Tenant Isolation**
    - **Validates: Requirements 10.6**

- [x] 11. Integration hooks
  - [x] 11.1 Hook LeadStageTransitionEngine into lead creation flow
    - In the lead creation path (watcher / `LeadRepository.create` post-commit), call `LeadStageTransitionEngine.fire_event(lead_id, "lead_created", context)`
    - Ensure no error is raised when no active pipeline exists
    - _Requirements: 6.1, 6.2, 6.7_

  - [x] 11.2 Hook LeadStageTransitionEngine into qualification events
    - In the existing qualification/scoring flow, fire the appropriate `BuiltInEventType` events: `response_email_sent`, `qualification_form_sent`, `qualification_form_submitted`, `qualification_bucket_hot`, `qualification_bucket_warm`, `qualification_bucket_nurture`
    - _Requirements: 6.1, 6.3, 4.1_

- [x] 12. Checkpoint — backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Seed data and pipeline templates
  - [x] 13.1 Implement pipeline seed templates
    - Create `api/services/pipeline_templates.py` with `create_real_estate_pipeline(db, company_id)` and `create_law_firm_pipeline(db, company_id)` functions
    - Real Estate template: stages New Lead → Contacted → Appointment Set → Under Contract → Won / Lost; include default event mappings
    - Law Firm template: stages New Inquiry → Consultation Scheduled → Retained → Active Case → Closed Won / Closed Lost; include default event mappings
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 13.2 Integrate templates into seed_data.py
    - Add `seed_pipelines(db)` function to `scripts/seed_data.py` that calls the template functions for the demo company
    - Call `seed_pipelines` from the startup auto-seed block in `api/main.py`
    - _Requirements: 11.4_

- [ ] 14. Admin pipeline builder UI — foundation
  - [~] 14.1 Create pipeline API client
    - Create `frontend/src/apps/platform-admin/api/pipelinesApi.ts` with typed functions for all pipeline admin endpoints (pipelines CRUD, stages, event-mappings, rules, lead stage, metrics)
    - Follow the existing axios pattern used in the agent app
    - _Requirements: 9.1_

  - [~] 14.2 Create pipeline React Query hooks
    - Create `frontend/src/apps/platform-admin/hooks/usePipelineQueries.ts`
    - Hooks: `usePipelines`, `usePipeline`, `usePipelineStages`, `usePipelineEventMappings`, `usePipelineRules`, `usePipelineMetrics`, `useLeadStageHistory`
    - Mutation hooks: `useCreatePipeline`, `useUpdatePipeline`, `useActivatePipeline`, `useCreateStage`, `useUpdateStage`, `useDeleteStage`, `useReorderStages`, `useUpsertEventMapping`, `useCreateRule`, `useUpdateRule`, `useDeleteRule`, `useReorderRules`, `useMoveLeadStage`
    - _Requirements: 9.1_

  - [~] 14.3 Create PipelinesPage skeleton and register route
    - Create `frontend/src/apps/platform-admin/pages/PipelinesPage.tsx` with tab bar (Builder, Built-in Rules, Automations, Activity) and overview metric cards (Leads in Pipeline, Avg Time in Stage, Conversion to Won, Stuck Leads)
    - Add route `/pipelines` in `PlatformAdminApp.tsx`
    - Add "Pipelines" nav item (icon `⟶`) to `Sidebar.tsx` NAV_ITEMS
    - _Requirements: 9.1, 9.9_

- [ ] 15. Admin pipeline builder UI — Builder tab
  - [~] 15.1 Implement horizontal stage flow with drag-and-drop
    - Install `@dnd-kit/core` and `@dnd-kit/sortable` (add to `frontend/package.json`)
    - Build `StageFlow` component: horizontal row of colored stage pills in position order, using `@dnd-kit/sortable` for drag-and-drop reordering
    - On drag end, call `useReorderStages` mutation
    - _Requirements: 9.2, 9.3_

  - [~] 15.2 Implement stage settings drawer
    - Build `StageDrawer` component: side drawer opened on stage pill click
    - Fields: name, key (auto-slugified), color picker (hex), category selector, is_default toggle, is_closed_won toggle, is_closed_lost toggle
    - Save calls `useUpdateStage`; delete calls `useDeleteStage` (with 409 handling showing affected lead count)
    - _Requirements: 9.4, 2.10_

  - [~] 15.3 Implement first-run template chooser modal
    - Build `TemplateChooserModal` component shown when no pipeline exists for the company
    - Options: Real Estate Buyer Pipeline, Law Firm Pipeline, Blank
    - On selection, call `useCreatePipeline` with the chosen template name then `useActivatePipeline`
    - _Requirements: 9.8, 11.3_

- [ ] 16. Admin pipeline builder UI — Built-in Rules tab
  - [~] 16.1 Implement Built-in Rules tab
    - Build `BuiltInRulesTab` component: table with one row per `BuiltInEventType`
    - Each row: event type label, target stage dropdown (pipeline stages), enable/disable toggle
    - Changes call `useUpsertEventMapping`
    - _Requirements: 9.5_

- [ ] 17. Admin pipeline builder UI — Automations tab
  - [~] 17.1 Implement Automations tab with When/Then card builder
    - Build `AutomationsTab` component: list of `RuleCard` components
    - Each `RuleCard`: WHEN trigger selector (trigger_type + trigger_event_type/trigger_stage_id), AND condition selector (condition_type + condition_value), THEN action steps (action_type + action_config), enable/disable toggle, delete button
    - "Add step" button appends a new action step row
    - "New Rule" button creates a blank rule via `useCreateRule`
    - Changes call `useUpdateRule`; delete calls `useDeleteRule`
    - _Requirements: 9.6_

- [ ] 18. Admin pipeline builder UI — Activity tab and pipeline selector
  - [~] 18.1 Implement Activity tab
    - Build `ActivityTab` component: paginated table of `LeadStageHistory` entries
    - Columns: lead name, from stage, to stage, source, reason, timestamp
    - _Requirements: 9.7_

  - [~] 18.2 Implement pipeline selector
    - When multiple pipelines exist, show a dropdown/selector above the tab bar to switch between pipelines
    - "New Pipeline" button opens a create modal
    - _Requirements: 9.9_

- [ ] 19. Agent lead detail pipeline enrichment
  - [~] 19.1 Add pipeline API hook to agent queries
    - Add `useLeadPipeline(leadId)` hook to `frontend/src/apps/agent/hooks/useAgentQueries.ts`
    - Calls `GET /api/v1/agent/leads/{lead_id}/pipeline`
    - _Requirements: 10.5, 10.7_

  - [~] 19.2 Add Pipeline section to AgentLeadDetailPage
    - Add a "Pipeline" tab to the existing tab bar in `AgentLeadDetailPage.tsx`
    - Pipeline tab content:
      - Pipeline Stage section: current stage name + "Entered N days ago"
      - Stage progress indicator: horizontal row of stage dots with current stage highlighted
      - Lifecycle Status section: checklist of completed events with timestamps
      - Quick Actions bar: Call button, Email button, Text button (marked "coming soon")
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ] 20. Checkpoint — metrics and stuck leads
  - [~] 20.1 Write property test for stuck leads threshold
    - **Property 12: Stuck Leads Threshold**
    - **Validates: Requirements 8.4**
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 21. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use `hypothesis` (already available in the Python backend)
- Each property test task references the exact property number from `design.md`
- The `LeadStageTransitionEngine` must never duplicate email/form/scoring logic — delegate to existing services
- Stage reorder must use a single bulk UPDATE (Requirement 13.7)
- Metrics endpoint must use DB-level aggregation, not Python-side row loading (Requirement 8.5)
- `@dnd-kit/core` and `@dnd-kit/sortable` are new frontend dependencies — add to `frontend/package.json` before implementing the Builder tab
