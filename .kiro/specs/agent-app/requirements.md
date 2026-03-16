# Requirements Document

## Introduction

The agent-app is a mobile-first responsive web application that enables real estate agents to self-enroll, connect their Gmail account, manage leads with urgency-first bucketing, configure buyer automation, and monitor their pipeline. The system extends an existing FastAPI + SQLAlchemy backend with agent-scoped routes and a new React (TypeScript) frontend. Key goals: enroll a new agent in under 10 minutes, surface HOT leads instantly, and make every automation action transparent and auditable.

## Glossary

- **Agent**: A real estate agent who uses the agent-app to manage leads and automation.
- **Agent_App**: The mobile-first React SPA and its supporting FastAPI backend routes.
- **Auth_Service**: The backend component responsible for agent signup, login, logout, and session management.
- **Onboarding_Wizard**: The 7-step (steps 0–6) guided enrollment flow that takes an agent from account creation to going live.
- **IMAP_Service**: The backend component that tests and manages Gmail IMAP connections.
- **Watcher**: The Gmail IMAP polling service that ingests new lead emails for an agent.
- **Scoring_Engine**: The backend component that computes a lead's numeric score and bucket assignment.
- **Lead**: A prospective buyer record parsed from an inbound email.
- **Lead_Inbox**: The filterable, sortable list view of an agent's leads.
- **Lead_Detail**: The single-lead view showing scoring breakdown, timeline, and contact actions.
- **Dashboard**: The home screen showing HOT lead counts, aging alerts, and response time metrics.
- **Template_Editor**: The UI component for editing email template subject and body with live preview.
- **Template_Renderer**: The backend component that substitutes placeholders in email templates.
- **Automation_Settings**: The page and backend for configuring buyer qualification thresholds and weights.
- **Credential_Store**: The backend component that encrypts and stores Gmail app passwords.
- **Session_Store**: The backend component managing agent session tokens.
- **Reports_Dashboard**: The lightweight analytics page showing lead source distribution, bucket breakdown, and response time.
- **HOT**: A lead bucket assigned when `score >= hot_threshold`.
- **WARM**: A lead bucket assigned when `warm_threshold <= score < hot_threshold`.
- **NURTURE**: A lead bucket assigned when `score < warm_threshold`.
- **SLA**: Service Level Agreement — the maximum time (in minutes) before a HOT lead is considered aging.
- **App_Password**: A Gmail application-specific password used for IMAP/SMTP access without OAuth.

---

## Requirements

### Requirement 1: Agent Account Creation

**User Story:** As a new real estate agent, I want to create an account with my email and password, so that I can access the agent-app and begin onboarding.

#### Acceptance Criteria

1. WHEN an agent submits a valid email, password (minimum 8 characters), and matching confirm password, THE Auth_Service SHALL create a new agent account and return a 201 response with `agent_user_id` and `onboarding_step: 0`.
2. WHEN an agent submits a signup request with an email that already exists, THE Auth_Service SHALL return a 409 response with `error: "EMAIL_ALREADY_EXISTS"`.
3. WHEN an agent submits a password shorter than 8 characters, THE Auth_Service SHALL reject the request with a 422 validation error.
4. WHEN an agent submits a password that does not match the confirm password field, THE Agent_App SHALL prevent form submission and display a validation error.
5. WHEN account creation succeeds, THE Auth_Service SHALL automatically log the agent in and THE Agent_App SHALL redirect to `/onboarding/profile`.

---

### Requirement 2: Agent Authentication

**User Story:** As a registered agent, I want to log in and out securely, so that my account and lead data remain protected.

#### Acceptance Criteria

1. WHEN an agent submits valid credentials, THE Auth_Service SHALL set a session cookie (`httponly=True, secure=True, samesite=lax`) and return `agent_user_id`, `full_name`, and `onboarding_completed`.
2. WHEN an agent submits invalid credentials, THE Auth_Service SHALL return a 401 response with `error: "INVALID_CREDENTIALS"`.
3. WHEN an agent logs out, THE Auth_Service SHALL invalidate the session cookie and return 200.
4. WHEN an unauthenticated request is made to any `/api/v1/agent/` route, THE Auth_Service SHALL return 401.
5. WHEN an authenticated agent requests `GET /api/v1/agent/auth/me`, THE Auth_Service SHALL return `agent_user_id`, `email`, `full_name`, `onboarding_completed`, and `onboarding_step`.
6. THE Session_Store SHALL use 64-byte cryptographically secure random tokens for all agent sessions.

---

### Requirement 3: Onboarding Wizard — Step Sequencing and Persistence

**User Story:** As an agent in the middle of onboarding, I want my progress saved and the wizard to enforce step order, so that I can resume where I left off and complete setup correctly.

#### Acceptance Criteria

1. THE Onboarding_Wizard SHALL persist completed step data in localStorage so that a page refresh resumes the wizard at the last completed step.
2. WHEN an agent attempts to access onboarding step N+2 without completing step N, THE Agent_App SHALL redirect to the required step and THE Auth_Service SHALL return 400 with `error: "ONBOARDING_STEP_REQUIRED"` and `required_step`.
3. THE Onboarding_Wizard SHALL display a progress indicator showing the current step number out of 6.
4. WHEN an agent navigates backward in the wizard, THE Onboarding_Wizard SHALL preserve previously entered data without loss.
5. WHEN all steps 1–6 are completed and the agent clicks "Go Live", THE Auth_Service SHALL set `onboarding_completed = TRUE` and redirect to `/dashboard`.

---

### Requirement 4: Agent Profile Setup (Onboarding Step 1)

**User Story:** As an agent completing onboarding, I want to enter my profile details, so that my name and contact information appear correctly in automated emails.

#### Acceptance Criteria

1. WHEN an agent submits a valid profile with `full_name` and `timezone`, THE Auth_Service SHALL persist the profile and advance `onboarding_step` to 2.
2. WHEN an agent submits a profile without `full_name`, THE Agent_App SHALL prevent submission and display a required field error.
3. WHERE a company join code is provided, THE Auth_Service SHALL associate the agent with the corresponding company.
4. WHEN no timezone is selected, THE Agent_App SHALL default the timezone selector to the browser's detected timezone.

---

### Requirement 5: Gmail Connection (Onboarding Step 2)

**User Story:** As an agent, I want to connect my Gmail account using an App Password, so that the system can monitor my inbox for new leads.

#### Acceptance Criteria

1. WHEN an agent submits a Gmail address and App Password, THE IMAP_Service SHALL attempt a live IMAP connection test against `imap.gmail.com:993`.
2. WHEN the IMAP connection test succeeds, THE Auth_Service SHALL encrypt the App Password using AES-256 and persist it, and THE Agent_App SHALL display a success state with the connected Gmail address.
3. WHEN the IMAP connection fails with "IMAP access is disabled", THE IMAP_Service SHALL return `error: "IMAP_DISABLED"` and THE Agent_App SHALL display actionable guidance to enable IMAP in Gmail settings.
4. WHEN the IMAP connection fails with "Application-specific password required", THE IMAP_Service SHALL return `error: "TWO_FACTOR_REQUIRED"`.
5. WHEN the IMAP connection fails with "Invalid credentials", THE IMAP_Service SHALL return `error: "INVALID_PASSWORD"`.
6. WHEN the IMAP connection fails with "Too many login attempts", THE IMAP_Service SHALL return `error: "RATE_LIMITED"`.
7. IF an agent makes more than 5 IMAP connection test attempts within a 15-minute window, THEN THE IMAP_Service SHALL return 429 with `error: "RATE_LIMITED"` and `retry_after_seconds`.
8. THE Credential_Store SHALL never store, log, or return the App Password in plaintext.
9. WHEN the watcher toggle is set and `watcher_admin_override = TRUE`, THE Agent_App SHALL display the toggle as read-only with an explanation.

---

### Requirement 6: Lead Source Preferences (Onboarding Step 3)

**User Story:** As an agent, I want to select which lead sources I accept, so that only relevant inbound emails are processed as leads.

#### Acceptance Criteria

1. WHEN an agent reaches step 3, THE Agent_App SHALL display all platform-managed lead sources with name, logo, and a sample parsed preview (name, phone, address, listing URL).
2. WHEN an agent submits their source selections, THE Auth_Service SHALL persist the `enabled_lead_source_ids` list and advance `onboarding_step` to 4.
3. WHEN no explicit selection is made, THE Agent_App SHALL default all common lead sources to enabled.

---

### Requirement 7: Buyer Automation Setup (Onboarding Step 4)

**User Story:** As an agent, I want to configure my lead qualification thresholds and working hours, so that the automation behaves according to my preferences.

#### Acceptance Criteria

1. WHEN an agent submits automation settings, THE Auth_Service SHALL persist a `BuyerAutomationConfig` record and advance `onboarding_step` to 5.
2. THE Agent_App SHALL allow the agent to set a HOT score threshold via a slider with range 60–95 and default value 80.
3. THE Agent_App SHALL allow the agent to select a response SLA for HOT leads from: 5 min, 15 min, 30 min, 1 hr, with default 5 min.
4. THE Agent_App SHALL allow the agent to toggle the "Tour soon?" qualification question on or off.
5. THE Agent_App SHALL allow the agent to set working hours via a time range picker with default 8am–8pm local time.

---

### Requirement 8: Email Template Setup (Onboarding Step 5)

**User Story:** As an agent, I want to review and customize my email templates during onboarding, so that automated emails reflect my personal tone and style.

#### Acceptance Criteria

1. WHEN an agent reaches step 5, THE Agent_App SHALL display all four template cards: INITIAL_INVITE, POST_HOT, POST_WARM, POST_NURTURE.
2. THE Agent_App SHALL provide a tone selector with options: Professional, Friendly, Short/Direct, which applies the corresponding platform default variant.
3. WHEN an agent edits a template subject or body, THE Template_Editor SHALL display a live preview panel rendered with sample lead data.
4. WHEN an agent submits template settings, THE Auth_Service SHALL persist agent template overrides and advance `onboarding_step` to 6.
5. WHEN an agent saves a template containing an unsupported placeholder (e.g., `{unknown_field}`), THE Auth_Service SHALL return 422 with `error: "INVALID_PLACEHOLDER"`, listing the invalid and supported placeholders.

---

### Requirement 9: Go Live and Test Simulation (Onboarding Step 6)

**User Story:** As an agent completing onboarding, I want to run a test simulation before going live, so that I can verify my configuration produces the expected emails and scoring.

#### Acceptance Criteria

1. WHEN an agent clicks "Run Test", THE Auth_Service SHALL execute a simulation that produces a rendered INITIAL_INVITE email and a scored POST_SUBMISSION email using the agent's actual configuration.
2. THE Agent_App SHALL display the simulated lead details, rendered invite email, form submission answers, computed score and bucket, and rendered post-submission email.
3. THE Auth_Service SHALL NOT persist any database records during the test simulation.
4. WHEN an agent clicks "Go Live", THE Auth_Service SHALL set `onboarding_completed = TRUE` only if Gmail is connected, at least one lead source is enabled, a `BuyerAutomationConfig` exists, and all 4 template types have an active template.
5. WHEN the "Go Live" preconditions are not met, THE Agent_App SHALL display a checklist indicating which items are incomplete.

---

### Requirement 10: Agent Dashboard

**User Story:** As an agent, I want a home dashboard that surfaces my most urgent leads and key metrics, so that I can act on HOT leads immediately.

#### Acceptance Criteria

1. WHEN an authenticated agent requests the dashboard, THE Dashboard SHALL return HOT lead count and summaries, aging lead count and summaries, today's average response time in minutes, and watcher status.
2. THE Dashboard SHALL include only leads where `agent_user_id` matches the authenticated agent.
3. WHEN a HOT lead has no agent action and `(NOW() - created_at) > sla_minutes_hot`, THE Dashboard SHALL include that lead in `aging_leads`.
4. THE Dashboard SHALL compute `response_time_today_minutes` as the mean of `(AGENT_CONTACTED.created_at - EMAIL_RECEIVED.created_at)` for all leads contacted today.
5. WHEN the watcher is running, THE Dashboard SHALL report `watcher_status: "running"`; WHEN stopped, `"stopped"`; WHEN in error, `"error"`.

---

### Requirement 11: Leads Inbox

**User Story:** As an agent, I want a filterable, urgency-first inbox of my leads, so that I can quickly find and act on the most important ones.

#### Acceptance Criteria

1. THE Lead_Inbox SHALL display leads sorted with HOT leads first, then WARM, then NURTURE, regardless of the selected sort option.
2. WHEN a bucket, status, or search filter is applied, THE Lead_Inbox SHALL return only leads matching all active filters.
3. WHEN a search term is entered, THE Lead_Inbox SHALL match against lead name, property address, and lead source name, with a 300ms debounce.
4. THE Lead_Inbox SHALL paginate results at 25 leads per page.
5. WHEN a HOT lead has no agent action and exceeds the SLA, THE Lead_Inbox SHALL display an aging indicator on that lead card.
6. WHEN a WARM lead was created more than 24 hours ago, THE Lead_Inbox SHALL display an aging indicator on that lead card.
7. THE Lead_Inbox SHALL return only leads belonging to the authenticated agent.

---

### Requirement 12: Lead Detail View

**User Story:** As an agent, I want to view the full detail of a lead including scoring breakdown and timeline, so that I can understand why a lead was scored and take informed action.

#### Acceptance Criteria

1. WHEN an agent requests a lead detail, THE Lead_Detail SHALL return the enriched lead, scoring breakdown with all factors, full event timeline, rendered emails, and notes.
2. WHEN an agent requests a lead that belongs to another agent, THE Auth_Service SHALL return 403 with `error: "LEAD_NOT_OWNED"`.
3. THE Lead_Detail SHALL display each scoring factor with its label, point value, and whether it was met.
4. WHEN an agent updates a lead status to CONTACTED, APPOINTMENT_SET, LOST, or CLOSED, THE Auth_Service SHALL update `current_state`, set `last_agent_action_at` to NOW() for CONTACTED transitions, and insert a `STATUS_CHANGED` lead event.
5. WHEN an agent adds a note to a lead, THE Auth_Service SHALL persist the note and insert a `NOTE_ADDED` lead event.
6. IF a lead status transition is invalid (e.g., CLOSED → CONTACTED), THEN THE Auth_Service SHALL reject the request with a 422 error.

---

### Requirement 13: Lead Scoring Engine

**User Story:** As an agent, I want leads automatically scored based on buyer qualification signals, so that I can prioritize the most likely buyers.

#### Acceptance Criteria

1. WHEN a lead is scored, THE Scoring_Engine SHALL compute a score as the sum of points for all met factors using the agent's `BuyerAutomationConfig` weights.
2. THE Scoring_Engine SHALL evaluate five factors: timeline urgency, pre-approval status, phone provided, tour interest, and budget match.
3. WHEN `score >= hot_threshold`, THE Scoring_Engine SHALL assign `bucket = "HOT"`.
4. WHEN `warm_threshold <= score < hot_threshold`, THE Scoring_Engine SHALL assign `bucket = "WARM"`.
5. WHEN `score < warm_threshold`, THE Scoring_Engine SHALL assign `bucket = "NURTURE"`.
6. THE Scoring_Engine SHALL produce a score between 0 and 100 inclusive.
7. WHEN scoring is complete, THE Scoring_Engine SHALL persist the score, bucket, and breakdown JSON to the lead record and insert a `LEAD_SCORED` event.
8. WHEN `enable_tour_question = FALSE`, THE Scoring_Engine SHALL assign 0 points for the tour interest factor regardless of the submission answer.

---

### Requirement 14: Email Template Management

**User Story:** As an agent, I want to create, preview, and revert email templates, so that I can customize automated outreach while always having a safe fallback.

#### Acceptance Criteria

1. WHEN an agent retrieves their templates, THE Auth_Service SHALL return all four template types (INITIAL_INVITE, POST_HOT, POST_WARM, POST_NURTURE) with subject, body, `is_custom` flag, version, and last updated timestamp.
2. WHEN an agent saves a template, THE Auth_Service SHALL increment the version number and persist the new subject and body.
3. WHEN an agent requests a template preview, THE Template_Renderer SHALL render the subject and body with sample lead data and return the rendered strings.
4. WHEN an agent deletes a custom template, THE Auth_Service SHALL remove the agent override and revert to the platform default for that template type.
5. THE Template_Renderer SHALL substitute all supported placeholders (`{lead_name}`, `{agent_name}`, `{agent_phone}`, `{agent_email}`, `{form_link}`) in both subject and body.
6. WHEN rendering is complete, THE Template_Renderer SHALL ensure no unresolved `{...}` placeholders remain in the output.
7. THE Template_Renderer SHALL ensure the rendered subject contains no newline characters.

---

### Requirement 15: Automation Settings Management

**User Story:** As an agent, I want to update my buyer automation configuration after onboarding, so that I can tune scoring thresholds and weights as I learn what works.

#### Acceptance Criteria

1. WHEN an agent retrieves automation settings, THE Auth_Service SHALL return the current `BuyerAutomationConfig` with all thresholds, weights, and question toggles, plus an `is_platform_default` flag.
2. WHEN an agent updates automation settings, THE Auth_Service SHALL persist the changes to the agent's `BuyerAutomationConfig` and return the updated `config_id`.
3. THE Agent_App SHALL allow updating `hot_threshold`, `warm_threshold`, `enable_tour_question`, `weight_timeline`, `weight_preapproval`, and `weight_phone_provided`.

---

### Requirement 16: Gmail Connection Management

**User Story:** As an agent, I want to view, test, update, and disconnect my Gmail connection after onboarding, so that I can keep my email integration working correctly.

#### Acceptance Criteria

1. WHEN an agent retrieves Gmail account settings, THE Auth_Service SHALL return `connected`, `gmail_address`, `last_sync`, `watcher_enabled`, and `watcher_admin_locked`.
2. WHEN an agent tests the Gmail connection, THE IMAP_Service SHALL perform a live IMAP test and return success or a structured error code.
3. WHEN an agent updates Gmail credentials, THE IMAP_Service SHALL test the new credentials before persisting and THE Credential_Store SHALL encrypt the new App Password with AES-256.
4. WHEN an agent disconnects Gmail, THE Auth_Service SHALL stop the watcher and clear the stored credentials.
5. WHEN an agent toggles the watcher and `watcher_admin_override = FALSE`, THE Auth_Service SHALL update `watcher_enabled` and start or stop the watcher process accordingly.
6. IF an agent attempts to toggle the watcher and `watcher_admin_override = TRUE`, THEN THE Auth_Service SHALL return 403 with `error: "ADMIN_LOCKED"`.

---

### Requirement 17: Reports Dashboard

**User Story:** As an agent, I want a lightweight reports view of my pipeline metrics, so that I can understand my lead sources and response performance.

#### Acceptance Criteria

1. WHEN an agent requests the reports summary, THE Reports_Dashboard SHALL return leads by source, bucket distribution (HOT/WARM/NURTURE counts), average response time in minutes, appointments set count, and the period start and end dates.
2. THE Reports_Dashboard SHALL support a `period` query parameter with values `7d`, `30d`, and `90d`, defaulting to `30d`.
3. THE Reports_Dashboard SHALL include only data belonging to the authenticated agent.

---

### Requirement 18: Multi-Tenant Isolation

**User Story:** As a platform operator, I want every agent to see only their own data, so that lead and configuration data is never exposed across agent boundaries.

#### Acceptance Criteria

1. THE Auth_Service SHALL scope every database query for leads, templates, preferences, and automation configs by the authenticated `agent_user_id`.
2. WHEN an agent requests any resource belonging to another agent, THE Auth_Service SHALL return 403.
3. THE Auth_Service SHALL enforce tenant isolation at the database query level, not only at the route level.

---

### Requirement 19: Credential Security

**User Story:** As a platform operator, I want Gmail App Passwords stored and handled securely, so that agent credentials are never exposed in logs, responses, or storage.

#### Acceptance Criteria

1. THE Credential_Store SHALL encrypt all Gmail App Passwords using AES-256 before persisting to the database.
2. THE Credential_Store SHALL use an encryption key sourced exclusively from an environment variable (never hardcoded).
3. THE Auth_Service SHALL use `SecretStr` (or equivalent) for App Password fields in all request/response models to prevent accidental logging.
4. THE IMAP_Service SHALL never include the App Password in log output, error messages, or API responses.
5. WHEN the encryption key is used to encrypt then decrypt an App Password, THE Credential_Store SHALL recover the original plaintext exactly.

---

### Requirement 20: Lead Event Immutability

**User Story:** As an agent, I want a complete and trustworthy audit trail of every lead action, so that I can review exactly what happened and when.

#### Acceptance Criteria

1. THE Auth_Service SHALL insert a new `lead_events` record for every state transition, scoring event, email send, agent contact action, and note addition.
2. THE Auth_Service SHALL never update or delete existing `lead_events` records.
3. WHEN a lead status changes, THE Auth_Service SHALL insert a `STATUS_CHANGED` event with a payload containing `from`, `to`, and optional `note`.
4. WHEN a lead is scored, THE Scoring_Engine SHALL insert a `LEAD_SCORED` event with the score, bucket, and full breakdown in the payload.
