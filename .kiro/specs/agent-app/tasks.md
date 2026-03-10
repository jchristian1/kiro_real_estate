# Implementation Plan: agent-app

## Overview

Implement the agent-facing web application across 6 milestones: auth + onboarding backend, onboarding frontend, leads inbox + dashboard backend, leads inbox + lead detail frontend, settings + reports, and polish + testing. Backend is FastAPI + SQLAlchemy + Alembic (Python). Frontend is React 18 + TypeScript + Tailwind CSS.

## Tasks

- [x] 1. Database schema and Alembic migrations
  - [x] 1.1 Create SQLAlchemy models for `agent_users`, `agent_sessions`, `agent_preferences`, `buyer_automation_configs`, `agent_templates`, `lead_events`
    - Define all columns, constraints, indexes, and FK relationships per the data models in the design
    - Add new columns to existing `leads` table: `property_address`, `listing_url`, `score`, `score_bucket`, `score_breakdown`, `current_state`, `agent_user_id`, `company_id`, `lead_source_name`, `last_agent_action_at`
    - _Requirements: 1.1, 2.6, 7.1, 13.7, 20.1_
  - [x] 1.2 Write Alembic migration for all new tables and `leads` column additions
    - Single migration file covering all new tables and leads alterations
    - _Requirements: 1.1, 13.7_

- [x] 2. Credential encryption service
  - [x] 2.1 Implement `encrypt_app_password` and `decrypt_app_password` using AES-256 (cryptography library), key from environment variable
    - Use `SecretStr` for all app password fields in Pydantic models
    - Never log or return plaintext
    - _Requirements: 19.1, 19.2, 19.3, 19.4_
  - [x] 2.2 Write property test for encryption round-trip
    - **Property 3: Encryption Round-Trip** — for any non-empty string, encrypt then decrypt returns original value exactly
    - **Validates: Requirements 19.5**

- [x] 3. Agent auth backend
  - [x] 3.1 Implement `POST /api/v1/agent/auth/signup` — create agent account, auto-login, return session cookie
    - Hash password with bcrypt; return 409 on duplicate email; return 422 on short password
    - _Requirements: 1.1, 1.2, 1.3, 1.5_
  - [x] 3.2 Implement `POST /api/v1/agent/auth/login`, `POST /api/v1/agent/auth/logout`, `GET /api/v1/agent/auth/me`
    - Session cookie: `httponly=True, secure=True, samesite=lax`; 64-byte cryptographically secure token
    - Return 401 on invalid credentials; invalidate session on logout
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6_
  - [x] 3.3 Implement agent auth middleware — validate session cookie on all `/api/v1/agent/` routes, return 401 if missing/expired
    - _Requirements: 2.4_
  - [x] 3.4 Write property test for session token uniqueness
    - **Property 22: Session Token Uniqueness** — any two generated session tokens are different and are exactly 64 bytes
    - **Validates: Requirements 2.6**
  - [x] 3.5 Write property test for unauthenticated request rejection
    - **Property 21: Unauthenticated Requests Rejected** — any request to `/api/v1/agent/` without valid session returns 401
    - **Validates: Requirements 2.4**

- [ ] 4. IMAP connection service
  - [~] 4.1 Implement `test_imap_connection(gmail_address, app_password)` using `imaplib.IMAP4_SSL`
    - Implement `classify_imap_error()` returning fixed enum: `IMAP_DISABLED`, `TWO_FACTOR_REQUIRED`, `INVALID_PASSWORD`, `RATE_LIMITED`, `CONNECTION_FAILED`
    - Never include app_password in logs or error output
    - _Requirements: 5.1, 5.3, 5.4, 5.5, 5.6, 5.8, 19.4_
  - [~] 4.2 Implement IMAP rate limiting — max 5 attempts per agent per 15-minute window, return 429 with `retry_after_seconds` on breach
    - _Requirements: 5.7_
  - [~] 4.3 Write property test for IMAP error classification
    - **Property 14: IMAP Error Classification** — for any error message string, `classify_imap_error()` returns a value from the fixed safe enumeration and never returns the raw message
    - **Validates: Requirements 5.3, 5.4, 5.5, 5.6**
  - [~] 4.4 Write property test for IMAP rate limiting
    - **Property 13: IMAP Rate Limiting** — for any agent, the 6th attempt within a 15-minute window always returns 429 with `error: "RATE_LIMITED"`
    - **Validates: Requirements 5.7**

- [ ] 5. Lead scoring engine
  - [~] 5.1 Implement `score_lead(lead_id, buyer_config_id)` — evaluate 5 factors, compute score, assign bucket, persist to lead record, insert `LEAD_SCORED` event
    - When `enable_tour_question = FALSE`, tour interest factor contributes 0 points
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8_
  - [~] 5.2 Write property test for score computation correctness
    - **Property 4: Score Computation Correctness** — for any factor inputs, score equals sum of points for met factors and is between 0 and 100 inclusive
    - **Validates: Requirements 13.1, 13.6**
  - [~] 5.3 Write property test for bucket assignment determinism
    - **Property 5: Bucket Assignment Determinism** — for any score and `(hot_threshold, warm_threshold)` where `hot_t > warm_t > 0`, bucket is exactly one of HOT/WARM/NURTURE and the three cases are mutually exclusive and exhaustive
    - **Validates: Requirements 13.3, 13.4, 13.5**
  - [~] 5.4 Write property test for tour question disabled
    - **Property 6: Tour Question Disabled Zeroes Score** — when `enable_tour_question = FALSE`, tour factor always contributes 0 regardless of submission answer
    - **Validates: Requirements 13.8**

- [ ] 6. Onboarding backend endpoints
  - [~] 6.1 Implement `PUT /api/v1/agent/onboarding/profile` — persist full_name, phone, timezone, service_area, optional company join code; advance `onboarding_step` to 2
    - _Requirements: 4.1, 4.3_
  - [~] 6.2 Implement `POST /api/v1/agent/onboarding/gmail` — call IMAP service, encrypt and persist credentials on success, return structured error codes on failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  - [~] 6.3 Implement `PUT /api/v1/agent/onboarding/sources` — persist `enabled_lead_source_ids`, advance `onboarding_step` to 4
    - _Requirements: 6.2_
  - [~] 6.4 Implement `PUT /api/v1/agent/onboarding/automation` — create/update `BuyerAutomationConfig`, advance `onboarding_step` to 5
    - _Requirements: 7.1_
  - [~] 6.5 Implement `PUT /api/v1/agent/onboarding/templates` — persist agent template overrides with tone selection, validate placeholders, advance `onboarding_step` to 6
    - Return 422 with `error: "INVALID_PLACEHOLDER"` for unsupported placeholders
    - _Requirements: 8.4, 8.5_
  - [~] 6.6 Implement onboarding step-order enforcement middleware — return 400 with `error: "ONBOARDING_STEP_REQUIRED"` when step N+2 is accessed without completing step N
    - _Requirements: 3.2_
  - [~] 6.7 Implement `POST /api/v1/agent/onboarding/test` — pure simulation using `simulate_onboarding_test()`, no DB writes
    - _Requirements: 9.1, 9.2, 9.3_
  - [~] 6.8 Implement `POST /api/v1/agent/onboarding/complete` — validate all 4 Go Live preconditions (Gmail connected, ≥1 source, BuyerAutomationConfig exists, all 4 template types active), set `onboarding_completed = TRUE`
    - Return checklist of incomplete items if preconditions not met
    - _Requirements: 9.4, 9.5_
  - [~] 6.9 Write property test for onboarding completeness gate
    - **Property 9: Onboarding Completeness Gate** — `onboarding_completed` is set to TRUE if and only if all 4 preconditions hold simultaneously
    - **Validates: Requirements 9.4**
  - [~] 6.10 Write property test for onboarding test simulation leaves no records
    - **Property 20: Onboarding Test Simulation Leaves No Records** — record counts in `leads`, `lead_events`, `agent_templates` are identical before and after simulation
    - **Validates: Requirements 9.3**

- [ ] 7. Template renderer
  - [~] 7.1 Implement `render_template(template, lead, agent_user_id)` — substitute all supported placeholders (`{lead_name}`, `{agent_name}`, `{agent_phone}`, `{agent_email}`, `{form_link}`), strip newlines from subject
    - _Requirements: 14.5, 14.6, 14.7_
  - [~] 7.2 Write property test for template placeholder safety
    - **Property 10: Template Placeholder Safety** — for any rendered email, subject contains no newline characters and no unresolved `{...}` placeholders remain in subject or body
    - **Validates: Requirements 14.5, 14.6, 14.7**

- [~] 8. Checkpoint — backend core complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Dashboard and leads backend
  - [~] 9.1 Implement `GET /api/v1/agent/dashboard` — HOT lead summaries, aging leads, `response_time_today_minutes`, `watcher_status`; scope all queries by `agent_user_id`
    - Aging: HOT leads where `last_agent_action_at IS NULL` AND `(NOW() - created_at) > sla_minutes_hot`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  - [~] 9.2 Implement `GET /api/v1/agent/leads` — urgency sort (HOT → WARM → NURTURE), bucket/status/search filters, aging annotation, pagination at 25/page
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  - [~] 9.3 Implement `GET /api/v1/agent/leads/{id}` — enriched lead, scoring breakdown, timeline, rendered emails, notes; return 403 for cross-agent access
    - _Requirements: 12.1, 12.2, 12.3, 18.2_
  - [~] 9.4 Implement `PATCH /api/v1/agent/leads/{id}/status` — validate state transition, update `current_state`, set `last_agent_action_at` on CONTACTED, insert `STATUS_CHANGED` event
    - Reject invalid transitions with 422
    - _Requirements: 12.4, 12.6, 20.3_
  - [~] 9.5 Implement `POST /api/v1/agent/leads/{id}/notes` — persist note, insert `NOTE_ADDED` event
    - _Requirements: 12.5, 20.1_
  - [~] 9.6 Wire `lead_events` insertion into the watcher pipeline — insert `EMAIL_RECEIVED`, `INVITE_SENT`, `FORM_SUBMITTED`, `POST_EMAIL_SENT` events at each stage
    - _Requirements: 20.1_
  - [~] 9.7 Write property test for tenant isolation
    - **Property 1: Tenant Isolation** — for any agent API response, every resource in the response has `agent_user_id` matching the authenticated agent
    - **Validates: Requirements 10.2, 11.7, 17.3, 18.1, 18.2**
  - [~] 9.8 Write property test for urgency sort order
    - **Property 15: Urgency Sort Order** — for any leads inbox query result, all HOT leads appear before all WARM leads, and all WARM leads appear before all NURTURE leads
    - **Validates: Requirements 11.1**
  - [~] 9.9 Write property test for filter correctness
    - **Property 16: Filter Correctness** — for any query with active filters, every returned lead satisfies all active filter conditions simultaneously
    - **Validates: Requirements 11.2, 11.3**
  - [~] 9.10 Write property test for pagination bound
    - **Property 17: Pagination Bound** — for any paginated leads inbox response, the number of leads returned is at most 25
    - **Validates: Requirements 11.4**
  - [~] 9.11 Write property test for HOT lead aging accuracy
    - **Property 11: HOT Lead Aging Accuracy** — `is_aging = TRUE` iff `last_agent_action_at IS NULL` AND `(NOW() - created_at) > sla_minutes_hot`
    - **Validates: Requirements 10.3, 11.5**
  - [~] 9.12 Write property test for WARM lead aging accuracy
    - **Property 12: WARM Lead Aging Accuracy** — `is_aging = TRUE` iff `(NOW() - created_at) > 24 hours`
    - **Validates: Requirements 11.6**
  - [~] 9.13 Write property test for status transition validity
    - **Property 18: Status Transition Validity** — any transition not in the valid set is rejected with 422
    - **Validates: Requirements 12.6**

- [ ] 10. Settings and reports backend
  - [~] 10.1 Implement templates CRUD: `GET /api/v1/agent/templates`, `PUT /api/v1/agent/templates/{type}`, `POST /api/v1/agent/templates/{type}/preview`, `DELETE /api/v1/agent/templates/{type}`
    - Increment version on each save; revert to platform default on DELETE
    - _Requirements: 14.1, 14.2, 14.3, 14.4_
  - [~] 10.2 Implement `GET /api/v1/agent/automation` and `PUT /api/v1/agent/automation`
    - _Requirements: 15.1, 15.2, 15.3_
  - [~] 10.3 Implement account/Gmail endpoints: `GET /api/v1/agent/account/gmail`, `POST /api/v1/agent/account/gmail/test`, `PUT /api/v1/agent/account/gmail`, `DELETE /api/v1/agent/account/gmail`, `PATCH /api/v1/agent/account/watcher`, `PUT /api/v1/agent/account/preferences`
    - Test new credentials before persisting on PUT; return 403 on watcher toggle when `watcher_admin_override = TRUE`
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_
  - [~] 10.4 Implement `GET /api/v1/agent/reports/summary` with `period` query param (7d/30d/90d, default 30d); scope by `agent_user_id`
    - _Requirements: 17.1, 17.2, 17.3_
  - [~] 10.5 Write property test for template version monotonicity
    - **Property 19: Template Version Monotonicity** — each save increments version by exactly 1
    - **Validates: Requirements 14.2**
  - [~] 10.6 Write property test for watcher admin lock
    - **Property 8: Watcher Admin Lock** — when `watcher_admin_override = TRUE`, any toggle request returns 403 with `error: "ADMIN_LOCKED"` regardless of `enabled` value
    - **Validates: Requirements 16.6**
  - [~] 10.7 Write property test for credential never plaintext
    - **Property 2: Credential Never Plaintext** — for any IMAP test or credential update, app_password never appears in log output, error responses, or API responses
    - **Validates: Requirements 5.8, 19.1, 19.4**

- [~] 11. Checkpoint — backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. React app scaffold and routing
  - [~] 12.1 Scaffold Vite + React 18 + TypeScript project; configure React Router v6, TanStack Query, React Hook Form, Zod, Tailwind CSS
    - Set up route structure: `/login`, `/signup`, `/onboarding/*`, `/dashboard`, `/leads`, `/leads/:id`, `/settings/*`, `/reports`
    - Add auth guard: redirect unauthenticated users to `/login`; redirect authenticated users with incomplete onboarding to `/onboarding`
    - _Requirements: 2.4, 3.5_
  - [~] 12.2 Implement API client layer with TanStack Query — typed hooks for all backend endpoints, session cookie handling, 401 redirect
    - _Requirements: 2.4_

- [ ] 13. Onboarding wizard frontend
  - [~] 13.1 Implement `OnboardingWizard` shell — progress bar (step N of 6), step routing, localStorage persistence, backward navigation without data loss
    - _Requirements: 3.1, 3.3, 3.4_
  - [~] 13.2 Implement Step 0 (Account Creation) — email, password, confirm password fields; Zod validation (min 8 chars, match); POST to signup; auto-redirect to `/onboarding/profile`
    - _Requirements: 1.1, 1.3, 1.4, 1.5_
  - [~] 13.3 Implement Step 1 (Agent Profile) — full_name (required), phone, timezone (default browser TZ), service_area, optional company join code
    - _Requirements: 4.1, 4.2, 4.4_
  - [~] 13.4 Implement Step 2 (Gmail Connection) — Gmail address + App Password fields, collapsible "How to create App Password" instructions, live IMAP test on submit, success/error states per error code, watcher toggle (read-only if admin locked)
    - _Requirements: 5.2, 5.3, 5.9, 9.5_
  - [~] 13.5 Implement Step 3 (Lead Sources) — checklist of platform lead sources with name, logo, sample parsed preview; default all enabled
    - _Requirements: 6.1, 6.3_
  - [~] 13.6 Implement Step 4 (Buyer Automation) — HOT threshold slider (60–95, default 80), SLA select (5/15/30/60 min), tour question toggle, working hours time range picker
    - _Requirements: 7.2, 7.3, 7.4, 7.5_
  - [~] 13.7 Implement Step 5 (Template Setup) — 4 template cards, tone selector, inline subject/body editor, live preview panel with sample lead data
    - _Requirements: 8.1, 8.2, 8.3_
  - [~] 13.8 Implement Step 6 (Go Live) — checklist with status icons, "Run Test" button with simulation result display (rendered emails, score, bucket), "Go Live" button with precondition checklist
    - _Requirements: 9.1, 9.2, 9.5_

- [ ] 14. Dashboard and leads inbox frontend
  - [~] 14.1 Implement Dashboard page — HOT leads list, aging alerts with visual indicators, today/week response time stats, watcher status badge, watcher toggle
    - Poll or refetch on focus; scope display to authenticated agent
    - _Requirements: 10.1, 10.5_
  - [~] 14.2 Implement Leads Inbox page — filter bar (bucket, status), search input with 300ms debounce, lead cards with urgency bucket badge and aging indicator, pagination
    - HOT leads always rendered first regardless of filter
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_
  - [~] 14.3 Implement Lead Detail page — scoring breakdown panel (factor label, points, met/unmet), event timeline, rendered email previews, notes list, status update controls (CONTACTED / APPOINTMENT_SET / LOST / CLOSED), add note form
    - _Requirements: 12.1, 12.3, 12.4, 12.5_

- [ ] 15. Settings and reports frontend
  - [~] 15.1 Implement Templates settings page — 4 template cards with inline editor, live preview panel, save and revert-to-default actions
    - _Requirements: 14.1, 14.2, 14.3, 14.4_
  - [~] 15.2 Implement Automation settings page — threshold sliders, weight inputs, tour question toggle
    - _Requirements: 15.3_
  - [~] 15.3 Implement Account/Gmail settings page — connection status display, test connection button with result feedback, update credentials form, disconnect button, watcher toggle (disabled if admin locked)
    - _Requirements: 16.1, 16.2, 16.5, 16.6_
  - [~] 15.4 Implement Reports page — source distribution list, bucket distribution chart, average response time, appointments count, period selector (7d/30d/90d)
    - _Requirements: 17.1, 17.2_

- [~] 16. Checkpoint — frontend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Mobile-first CSS audit and polish
  - [~] 17.1 Audit and fix all pages at 375px, 390px, and 414px viewport widths — touch targets ≥ 44px, no horizontal overflow, readable font sizes
    - _Requirements: (design mobile-first goal)_
  - [~] 17.2 Verify watcher toggle, aging indicators, and status controls are usable on mobile

- [ ] 18. Integration and security tests
  - [~] 18.1 Write end-to-end integration test: full onboarding flow — signup → profile → gmail (mock IMAP) → sources → automation → templates → go-live → test simulation
    - _Requirements: 1.1, 3.5, 9.1, 9.4_
  - [~] 18.2 Write end-to-end integration test: lead lifecycle — ingest email → parse → score → invite → form submit → re-score → post-email → agent marks contacted
    - _Requirements: 13.7, 20.1_
  - [~] 18.3 Write security integration tests: verify app_password never in API responses or logs; verify IMAP rate limiting (6th attempt → 429); verify cross-agent 403 on leads/templates/preferences
    - _Requirements: 5.7, 5.8, 18.2, 19.4_
  - [~] 18.4 Write integration test: template header injection — subject with `\n` returns 422
    - _Requirements: 14.7_

- [~] 19. Final checkpoint — all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` (Python) for backend and can be added incrementally alongside implementation tasks
- All backend queries must scope by `agent_user_id` — tenant isolation is enforced at the query level, not just the route level
- The `app_password` field must use Pydantic `SecretStr` in all request/response models
