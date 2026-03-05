# Implementation Plan: Buyer Lead Qualification (leads-preapproval)

## Overview

Implement the buyer lead qualification pipeline: DB migrations, backend services (state machine, scoring, templates, invitations), FastAPI routes (admin + public), seed data, and React admin panel tabs. Python (FastAPI/SQLAlchemy) for backend, TypeScript/React for frontend.

## Tasks

- [x] 1. Database migrations (Alembic)
  - [x] 1.1 Add `current_state` and `current_state_updated_at` columns to `leads` table
    - Generate Alembic migration; manually strip any DROP TABLE statements from the upgrade function
    - _Requirements: 1.5_
  - [x] 1.2 Create the 14 new tables
    - Generate Alembic migration for: `form_templates`, `form_versions`, `form_questions`, `form_logic_rules`, `scoring_configs`, `scoring_versions`, `form_invitations`, `form_submissions`, `submission_answers`, `submission_scores`, `message_templates`, `message_template_versions`, `lead_state_transitions`, `lead_interactions`
    - Include unique index on `form_invitations.token_hash`, unique constraint on `submission_scores.submission_id`, and index on `lead_state_transitions(lead_id, occurred_at)`
    - Manually strip any DROP TABLE statements from the upgrade function before running
    - _Requirements: 1.4, 3.2, 20.4_

- [x] 2. SQLAlchemy models and enums
  - [x] 2.1 Create `gmail_lead_sync/preapproval/models_preapproval.py` with all enums and models
    - Define enums: `IntentType`, `LeadState`, `Bucket`, `ActorType`, `Channel`, `MessageTemplateKey`
    - Define all 14 SQLAlchemy model classes matching the schema in the design doc
    - Add `current_state` and `current_state_updated_at` fields to the existing `Lead` model (or patch via mixin)
    - _Requirements: 1.4, 2.1, 3.1, 19.1_

- [ ] 3. LeadStateMachine service
  - [x] 3.1 Implement `gmail_lead_sync/preapproval/state_machine.py`
    - Implement `VALID_TRANSITIONS` dict and `InvalidTransitionError`
    - Implement `transition()`: validate transition, insert immutable `LeadStateTransition` row, update `leads.current_state` + `current_state_updated_at` atomically
    - Implement `current_state()`: query current state from lead record
    - Raise `NotFoundException` when lead does not exist
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_
  - [ ] 3.2 Write unit tests for LeadStateMachine
    - Test all valid transitions succeed and produce correct DB rows
    - Test all invalid transitions raise `InvalidTransitionError` and leave state unchanged
    - Test `NotFoundException` when lead not found
    - _Requirements: 1.2, 1.3, 1.8_
  - [ ] 3.3 Write property test for state transition validity (Property 4)
    - **Property 4: State Transition Validity**
    - **Validates: Requirements 1.2, 1.3**
  - [ ] 3.4 Write property test for state monotonicity (Property 5)
    - **Property 5: State Monotonicity**
    - **Validates: Requirements 1.4, 1.5, 1.6**

- [ ] 4. FormInvitationService
  - [x] 4.1 Implement `gmail_lead_sync/preapproval/invitation_service.py`
    - Implement `create_invitation()`: generate 32-byte `secrets.token_urlsafe`, store only SHA-256 hash, set `expires_at = now() + ttl_hours`
    - Implement `validate_token()`: hash lookup, raise `TokenNotFoundError` / `TokenUsedError` / `TokenExpiredError`
    - Implement `mark_used()`: set `used_at = now()`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  - [ ] 4.2 Write unit tests for FormInvitationService
    - Test token expiry logic, used-token rejection, not-found error
    - _Requirements: 3.3, 3.4, 3.5_
  - [ ] 4.3 Write property test for token uniqueness (Property 13)
    - **Property 13: Token Uniqueness** — generate N tokens, assert all N SHA-256 hashes are distinct
    - **Validates: Requirements 3.6**
  - [ ] 4.4 Write property test for token hash storage (Property 12)
    - **Property 12: Token Hash Storage** — assert stored hash equals `sha256(raw_token)` and raw token not in any DB column
    - **Validates: Requirements 3.2, 17.4**

- [ ] 5. ScoringEngine
  - [x] 5.1 Implement `gmail_lead_sync/preapproval/scoring_engine.py`
    - Implement `ScoreBreakdownItem` and `ScoreResult` dataclasses
    - Implement `compute()`: iterate rules, match `answer_value` (including `__any_range__` and `__present__` sentinels), sum points, determine bucket from thresholds, build breakdown and explanation
    - Support negative point values
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10_
  - [ ] 5.2 Write unit tests for ScoringEngine
    - Parametrized tests for each default rule, boundary conditions at HOT/WARM thresholds, negative scores, sentinel matching
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.8, 5.9, 5.10_
  - [ ] 5.3 Write property test for score-bucket consistency (Property 1)
    - **Property 1: Score-Bucket Consistency** — for any valid scoring version and answers, bucket assignment matches threshold comparison
    - **Validates: Requirements 5.3, 5.4, 5.5**
  - [ ] 5.4 Write property test for score breakdown completeness (Property 8)
    - **Property 8: Score Breakdown Completeness** — `sum(item.points for item in breakdown) == total`
    - **Validates: Requirements 5.6, 5.7**
  - [ ] 5.5 Write property test for scoring sentinel matching (Property 18)
    - **Property 18: Scoring Sentinel Matching** — `__any_range__` matches all except `"not_sure"`, `__present__` matches non-null/non-empty only
    - **Validates: Requirements 5.8, 5.9**

- [ ] 6. TemplateRenderEngine
  - [x] 6.1 Implement `gmail_lead_sync/preapproval/template_engine.py`
    - Define `SUPPORTED_VARS` frozenset
    - Implement `render()`: select variant if `variant_key` provided, validate all `{{var}}` tokens against `SUPPORTED_VARS`, substitute context values (HTML-escape body values, not subject), raise `UnknownVariableError` / `VariantNotFoundError`; substitute empty string for missing context vars and log warning
    - Implement `preview()`: render arbitrary subject/body strings with optional sample context
    - _Requirements: 7.5, 7.6, 7.7, 7.8, 8.1, 8.2, 8.3, 8.4, 8.5_
  - [ ] 6.2 Write unit tests for TemplateRenderEngine
    - Test variable substitution, HTML escaping, variant selection, unknown variable detection, missing variable fallback
    - _Requirements: 7.7, 7.8, 8.1, 8.2, 8.3_
  - [ ] 6.3 Write property test for template rendering idempotence (Property 16)
    - **Property 16: Template Rendering Idempotence** — rendering same template + context twice produces identical output
    - **Validates: Requirements 8.4**
  - [ ] 6.4 Write property test for HTML escaping (Property 14)
    - **Property 14: HTML Escaping in Email Bodies** — any context value with `<`, `>`, `&`, `"`, `'` is escaped in rendered body
    - **Validates: Requirements 7.7, 17.7**
  - [ ] 6.5 Write property test for template variable safety (Property 9)
    - **Property 9: Template Variable Safety** — publishing a template with any unknown `{{variable}}` is rejected
    - **Validates: Requirements 7.5, 8.1**

- [x] 7. Checkpoint — Ensure all service unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Event handlers
  - [x] 8.1 Implement `gmail_lead_sync/preapproval/handlers.py` — `on_buyer_lead_email_received()`
    - Resolve active `FormVersion` for tenant + BUY; log warning and return if none
    - Transition lead to `FORM_INVITE_CREATED`, create `FormInvitation`, render `INITIAL_INVITE_EMAIL`, send email, transition to `FORM_INVITE_SENT`, record outbound `LeadInteraction`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  - [x] 8.2 Implement `on_buyer_form_submitted()` in `handlers.py`
    - Validate token, validate answers against form schema, persist `FormSubmission` + `SubmissionAnswer` rows, mark token used, transition to `FORM_SUBMITTED`, compute score, persist `SubmissionScore`, transition to `SCORED`, render and send `POST_SUBMISSION_EMAIL` for bucket, transition to `POST_SUBMISSION_EMAIL_SENT`, record outbound `LeadInteraction`
    - Handle missing active scoring version (log warning, leave in `FORM_SUBMITTED`)
    - Handle missing active template version (log error, record failed interaction)
    - _Requirements: 4.3, 5.1, 10.1, 10.2, 10.3, 10.4, 5.11_

- [x] 9. Public submission endpoint
  - [x] 9.1 Create `api/routes/public_submission.py`
    - Implement `POST /public/buyer-qualification/{token}/submit` (no auth)
    - Apply slowapi rate limit: 5 requests/minute per IP; return 429 on exceed
    - Return 404 for `TokenNotFoundError`, 410 for `TokenExpiredError` / `TokenUsedError`, 400 for validation errors, 200 with `{submission_id, score}` on success
    - Delegate to `on_buyer_form_submitted()`
    - _Requirements: 4.1, 4.2, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 17.3, 18.1, 18.2_
  - [x] 9.2 Register public router in `main.py`
    - Mount public router without auth middleware
    - _Requirements: 4.1_

- [x] 10. Admin API routes — buyer leads
  - [x] 10.1 Create `api/routes/buyer_leads.py` with form template CRUD and version management
    - `GET/POST /tenants/{tid}/forms` — list/create form templates
    - `GET/PUT/DELETE /tenants/{tid}/forms/{fid}` — manage form template
    - `POST /tenants/{tid}/forms/{fid}/versions` — publish new version (snapshot questions, set `is_active`, validate unique `question_key`s, validate logic rules)
    - `POST /tenants/{tid}/forms/{fid}/versions/{vid}/rollback` — rollback active version
    - Enforce tenant isolation: filter all queries by `tenant_id` from auth session; return 404 for cross-tenant access
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 17.1, 17.2_
  - [x] 10.2 Add scoring config and version routes to `buyer_leads.py`
    - `GET/POST /tenants/{tid}/scoring` — list/create scoring configs
    - `POST /tenants/{tid}/scoring/{sid}/versions` — publish scoring version (validate thresholds: HOT > WARM >= 0)
    - `POST /tenants/{tid}/simulate` — compute score without persisting; return `ScoreResult`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 15.2_
  - [x] 10.3 Add message template routes to `buyer_leads.py`
    - `GET/POST /tenants/{tid}/message-templates` — list/create message templates
    - `POST /tenants/{tid}/message-templates/{mid}/versions` — publish version (validate `SUPPORTED_VARS`, reject subject with newlines)
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6, 17.8_
  - [x] 10.4 Add lead state monitoring and audit routes to `buyer_leads.py`
    - `GET /tenants/{tid}/leads/states` — paginated leads table with `current_state`, filterable by state/bucket
    - `GET /tenants/{tid}/leads/funnel` — count of leads at each state
    - `GET /tenants/{tid}/audit` — filterable audit log (date range, event type, lead ID)
    - _Requirements: 14.1, 14.2, 14.3, 16.1, 16.2, 16.3_
  - [x] 10.5 Register admin router in `main.py` under `/api/v1/buyer-leads/`
    - _Requirements: 2.1, 6.1, 7.1_

- [x] 11. Seed data
  - [x] 11.1 Create seed script `gmail_lead_sync/preapproval/seed.py`
    - Insert default buyer form template + form version with 7 questions (timeline, budget, financing, areas, contact_preference, has_agent, wants_tour) as defined in design doc
    - Insert default scoring config + scoring version with all 15 rules and thresholds `{"HOT": 80, "WARM": 50}`
    - Insert default `INITIAL_INVITE_EMAIL` and `POST_SUBMISSION_EMAIL` message templates with HOT/WARM/NURTURE variants for the post-submission template
    - Set `is_active=True` on all default versions
    - _Requirements: 9.1, 5.1, 7.1_

- [x] 12. Checkpoint — Ensure all backend tests pass and routes are reachable
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Frontend — routing and navigation
  - [x] 13.1 Add React Router routes under `/tenants/:tenantId/buyer-leads/` in the router config
    - Routes: `forms`, `forms/:formId`, `scoring`, `scoring/:configId`, `templates`, `templates/:templateId`, `states`, `simulate`, `audit`
    - _Requirements: 11.1, 12.1, 13.1, 14.1, 15.1, 16.1_
  - [x] 13.2 Add "Buyer Lead Automation" navigation link in the sidebar/dashboard layout
    - Link to `/tenants/:tenantId/buyer-leads/forms`
    - _Requirements: 11.1_

- [x] 14. Frontend — BuyerFormTab and FormVersionEditor
  - [x] 14.1 Create `frontend/src/pages/buyer-leads/BuyerFormTab.tsx`
    - List form templates via `GET /api/v1/buyer-leads/tenants/{tid}/forms`
    - Create new template, publish version, rollback to previous version
    - Use existing table + pagination and modal patterns; Tailwind CSS; axios; useToast
    - _Requirements: 11.1, 11.2, 11.5_
  - [x] 14.2 Create `frontend/src/pages/buyer-leads/FormVersionEditor.tsx`
    - Drag-and-drop question ordering, conditional logic rule builder, JSON schema preview
    - _Requirements: 11.3, 11.4_

- [x] 15. Frontend — BuyerScoringTab
  - [x] 15.1 Create `frontend/src/pages/buyer-leads/BuyerScoringTab.tsx`
    - List scoring configs; inline rules table editor (question_key, answer_value, points, reason); HOT/WARM threshold inputs; version history display
    - Publish scoring version via `POST /api/v1/buyer-leads/tenants/{tid}/scoring/{sid}/versions`
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 16. Frontend — EmailTemplatesTab and TemplateVersionEditor
  - [x] 16.1 Create `frontend/src/pages/buyer-leads/EmailTemplatesTab.tsx`
    - List `INITIAL_INVITE_EMAIL` and `POST_SUBMISSION_EMAIL` templates
    - _Requirements: 13.1_
  - [x] 16.2 Create `frontend/src/pages/buyer-leads/TemplateVersionEditor.tsx`
    - Variable picker listing all `SUPPORTED_VARS`, live preview panel (calls preview API), per-bucket variant editor for `POST_SUBMISSION_EMAIL`
    - _Requirements: 13.2, 13.3, 13.4_

- [x] 17. Frontend — LeadStatesTab
  - [x] 17.1 Create `frontend/src/pages/buyer-leads/LeadStatesTab.tsx`
    - Paginated leads table with `current_state` and `current_state_updated_at`; filter by state and bucket
    - Funnel chart visualizing state-to-state conversion rates (data from `GET .../leads/funnel`)
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

- [x] 18. Frontend — SimulationTab
  - [x] 18.1 Create `frontend/src/pages/buyer-leads/SimulationTab.tsx`
    - Render active buyer qualification form questions dynamically
    - On submit, call `POST /api/v1/buyer-leads/tenants/{tid}/simulate` and display score breakdown + bucket + rendered `POST_SUBMISSION_EMAIL` preview
    - _Requirements: 15.1, 15.2, 15.3_

- [x] 19. Frontend — BuyerAuditTab
  - [x] 19.1 Create `frontend/src/pages/buyer-leads/BuyerAuditTab.tsx`
    - Filterable, paginated audit log (date range, event type, lead ID) via `GET .../audit`
    - _Requirements: 16.1, 16.2, 16.3_

- [x] 20. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use Hypothesis; unit tests use pytest with parametrize
- When running `alembic revision --autogenerate`, always manually strip DROP TABLE statements from the upgrade function before applying
- Tenant isolation: all admin API queries must filter by `tenant_id` from the authenticated session; cross-tenant access returns 404
- The `companies` table is the tenants table; FK is `companies.id`
