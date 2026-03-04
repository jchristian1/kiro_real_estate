# Requirements Document

## Introduction

This document defines the requirements for the **Buyer Lead Qualification** pipeline (`leads-preapproval`) within the existing multi-tenant Gmail Lead Sync SaaS. The feature automates the qualification of buyer leads by sending a dynamic form invite upon email receipt, collecting answers, scoring the lead, bucketing them (HOT/WARM/NURTURE), and dispatching a tailored acknowledgement email — all tracked through an immutable state machine. The admin panel exposes full configuration and monitoring capabilities. The system is scoped to `intent_type=BUY` for MVP but is architected to extend to SELL and RENT without schema or service refactoring.

---

## Glossary

- **Lead**: A prospective buyer whose email was ingested by the Gmail Lead Sync watcher.
- **Tenant**: A real estate company (row in `companies`) using the SaaS platform.
- **FormTemplate**: A named, tenant-scoped container for versioned buyer qualification forms.
- **FormVersion**: An immutable snapshot of a form's questions and logic rules, published from a FormTemplate.
- **FormQuestion**: A single question within a FormVersion, identified by a `question_key`.
- **FormLogicRule**: A conditional visibility rule within a FormVersion (e.g., hide question B if answer to A is X).
- **ScoringConfig**: A named, tenant-scoped container for versioned scoring rule sets.
- **ScoringVersion**: An immutable snapshot of scoring rules and bucket thresholds, published from a ScoringConfig.
- **Bucket**: One of three lead quality tiers: HOT, WARM, or NURTURE, determined by total score vs. thresholds.
- **FormInvitation**: A single-use, expiring, tokenized invitation sent to a lead to complete the qualification form.
- **FormSubmission**: A lead's completed response to a FormVersion, linked to a FormInvitation.
- **SubmissionScore**: The computed score record for a FormSubmission, including total, bucket, breakdown, and explanation.
- **MessageTemplate**: A named, tenant-scoped container for versioned email templates.
- **MessageTemplateVersion**: An immutable snapshot of an email template's subject, body, and optional bucket variants.
- **LeadState**: One of the defined states in the lead qualification state machine.
- **LeadStateTransition**: An immutable event-log row recording a state change for a lead.
- **LeadInteraction**: An immutable record of an inbound or outbound communication with a lead.
- **IntentType**: The lead's intent category: BUY (MVP), SELL (reserved), or RENT (reserved).
- **INITIAL_INVITE_EMAIL**: The email template key for the form invitation email.
- **POST_SUBMISSION_EMAIL**: The email template key for the post-submission acknowledgement email, with per-bucket variants.
- **LeadStateMachine**: The service that enforces valid state transitions and persists the immutable event log.
- **ScoringEngine**: The service that applies versioned scoring rules to a submission's answers and returns a ScoreResult.
- **TemplateRenderEngine**: The service that renders versioned message templates with variable substitution.
- **FormInvitationService**: The service that generates and validates single-use, expiring form tokens.
- **PublicSubmissionEndpoint**: The unauthenticated HTTP endpoint at `POST /public/buyer-qualification/{token}/submit`.
- **AdminAPI**: The authenticated HTTP API mounted under `/api/v1/buyer-leads/`.
- **SimulationTab**: The admin panel tab that allows testing scoring and email rendering with arbitrary answers.
- **AuditTab**: The admin panel tab displaying the filterable audit log for all buyer-lead automation actions.

---

## Requirements

### Requirement 1: Lead State Machine

**User Story:** As a system operator, I want leads to progress through a defined qualification pipeline, so that every lead's status is always known and transitions are auditable.

#### Acceptance Criteria

1. WHEN a new lead email is ingested, THE LeadStateMachine SHALL transition the lead to `NEW_EMAIL_RECEIVED` as the initial state.
2. WHEN the LeadStateMachine receives a transition request, THE LeadStateMachine SHALL validate that the requested `to_state` is in the `VALID_TRANSITIONS` map for the lead's current state before persisting any change.
3. IF the requested transition is not in `VALID_TRANSITIONS` for the current state, THEN THE LeadStateMachine SHALL raise an `InvalidTransitionError` and leave the lead's state unchanged.
4. WHEN a valid state transition occurs, THE LeadStateMachine SHALL insert an immutable row into `lead_state_transitions` recording `tenant_id`, `lead_id`, `intent_type`, `from_state`, `to_state`, `occurred_at`, `actor_type`, and `actor_id`.
5. WHEN a valid state transition occurs, THE LeadStateMachine SHALL update `leads.current_state` and `leads.current_state_updated_at` atomically with the `lead_state_transitions` insert.
6. THE LeadStateMachine SHALL enforce the following valid transition sequence: `NULL → NEW_EMAIL_RECEIVED → FORM_INVITE_CREATED → FORM_INVITE_SENT → FORM_SUBMITTED → SCORED → POST_SUBMISSION_EMAIL_SENT`.
7. THE LeadStateMachine SHALL never update or delete rows in `lead_state_transitions` after insertion.
8. WHEN a lead does not exist, THE LeadStateMachine SHALL raise a `NotFoundException` and perform no state change.

---

### Requirement 2: Form Template and Version Management

**User Story:** As a tenant admin, I want to create and manage versioned buyer qualification forms, so that I can update questions without disrupting in-flight invitations.

#### Acceptance Criteria

1. THE AdminAPI SHALL allow authenticated tenant admins to create, read, update, and delete `FormTemplate` records scoped to their tenant.
2. WHEN a tenant admin publishes a new `FormVersion`, THE AdminAPI SHALL snapshot the current question list and logic rules into `schema_json` and set `published_at` to the current timestamp.
3. WHEN a `FormVersion` is published, THE AdminAPI SHALL set `is_active=True` on the new version and `is_active=False` on all other versions for the same `template_id`.
4. THE AdminAPI SHALL support rolling back to a previous `FormVersion` by setting `is_active=True` on the target version and `is_active=False` on all others for the same `template_id`.
5. AT ALL TIMES, for any given `template_id`, THE System SHALL ensure at most one `FormVersion` has `is_active=True`.
6. THE AdminAPI SHALL support the following question types within a `FormVersion`: `single_choice`, `multi_select`, `free_text`, `phone`, and `email`.
7. WHEN a `FormVersion` is published, THE AdminAPI SHALL validate that all `question_key` values within the version are unique.
8. THE AdminAPI SHALL allow tenant admins to define `FormLogicRule` entries per `FormVersion` that conditionally show or hide questions based on prior answers.
9. WHEN a `FormVersion` is active, THE FormInvitationService SHALL use that version when creating new invitations for the tenant's BUY intent.

---

### Requirement 3: Form Invitation Service

**User Story:** As a system operator, I want each lead to receive a unique, expiring, single-use form link, so that form submissions are authenticated without requiring the lead to log in.

#### Acceptance Criteria

1. WHEN a buyer lead email is received and an active `FormVersion` exists for the tenant, THE FormInvitationService SHALL generate a cryptographically random 32-byte URL-safe token.
2. THE FormInvitationService SHALL store only the SHA-256 hash of the raw token in `form_invitations.token_hash`; the raw token SHALL NOT be persisted in the database.
3. WHEN creating a `FormInvitation`, THE FormInvitationService SHALL set `expires_at` to 72 hours from creation time by default, configurable per tenant.
4. WHEN validating a token, THE FormInvitationService SHALL raise `TokenNotFoundError` if no matching hash exists, `TokenUsedError` if `used_at` is not null, and `TokenExpiredError` if `expires_at` is in the past.
5. WHEN a form is successfully submitted, THE FormInvitationService SHALL set `form_invitations.used_at` to the current timestamp, rendering the token permanently invalid for further submissions.
6. THE FormInvitationService SHALL generate tokens such that any two independently generated tokens produce distinct SHA-256 hashes.

---

### Requirement 4: Public Tokenized Submission Endpoint

**User Story:** As a buyer lead, I want to submit my qualification answers via a link in my email, so that I can complete the form without creating an account.

#### Acceptance Criteria

1. THE PublicSubmissionEndpoint SHALL accept `POST /public/buyer-qualification/{token}/submit` requests without requiring authentication.
2. WHEN a valid, unexpired, unused token is presented, THE PublicSubmissionEndpoint SHALL validate the submitted answers against the `FormVersion` schema referenced by the invitation.
3. WHEN answers pass validation, THE PublicSubmissionEndpoint SHALL persist a `FormSubmission`, all `SubmissionAnswer` rows, and a `SubmissionScore` within a single database transaction.
4. WHEN the submission is persisted, THE PublicSubmissionEndpoint SHALL return HTTP 200 with `{ submission_id, score: { total, bucket, explanation } }`.
5. IF the token is not found, THEN THE PublicSubmissionEndpoint SHALL return HTTP 404 with `{"error": "Invalid submission link"}`.
6. IF the token is expired or already used, THEN THE PublicSubmissionEndpoint SHALL return HTTP 410 with an appropriate error message.
7. IF the submitted answers fail schema validation, THEN THE PublicSubmissionEndpoint SHALL return HTTP 400 with field-level validation errors.
8. THE PublicSubmissionEndpoint SHALL enforce a rate limit of 5 requests per minute per IP address, returning HTTP 429 when the limit is exceeded.
9. WHEN a submission is accepted, THE PublicSubmissionEndpoint SHALL trigger the full scoring and post-submission email pipeline before returning the response.

---

### Requirement 5: Scoring Engine

**User Story:** As a tenant admin, I want submitted answers to be automatically scored against my configured rules, so that leads are ranked and bucketed without manual review.

#### Acceptance Criteria

1. WHEN a `FormSubmission` is received, THE ScoringEngine SHALL evaluate all rules in the active `ScoringVersion` against the submission's answers and metadata.
2. THE ScoringEngine SHALL compute `total_score` as the sum of `points` for all rules whose `answer_value` matches the corresponding answer or metadata value.
3. WHEN `total_score >= thresholds["HOT"]`, THE ScoringEngine SHALL assign `bucket = HOT`.
4. WHEN `thresholds["WARM"] <= total_score < thresholds["HOT"]`, THE ScoringEngine SHALL assign `bucket = WARM`.
5. WHEN `total_score < thresholds["WARM"]`, THE ScoringEngine SHALL assign `bucket = NURTURE`.
6. THE ScoringEngine SHALL produce a `breakdown` list containing one entry per matched rule, each with `question_key`, `answer`, `points`, and `reason`.
7. THE ScoringEngine SHALL ensure that the sum of all `points` values in `breakdown` equals `total_score`.
8. THE ScoringEngine SHALL support the sentinel `answer_value` of `"__any_range__"` to match any non-`"not_sure"` answer value.
9. THE ScoringEngine SHALL support the sentinel `answer_value` of `"__present__"` to match any non-null, non-empty metadata value.
10. THE ScoringEngine SHALL support negative point values in rules to allow disqualifying signals to reduce the total score.
11. IF no active `ScoringVersion` exists for the tenant's BUY intent, THEN THE System SHALL log a warning, leave the lead in `FORM_SUBMITTED` state, and not send a `POST_SUBMISSION_EMAIL`.

---

### Requirement 6: Scoring Version Management

**User Story:** As a tenant admin, I want to manage versioned scoring configurations, so that I can update scoring rules without affecting historical scores.

#### Acceptance Criteria

1. THE AdminAPI SHALL allow authenticated tenant admins to create, read, and publish `ScoringVersion` records scoped to their tenant and intent type.
2. WHEN a `ScoringVersion` is published, THE AdminAPI SHALL set `is_active=True` on the new version and `is_active=False` on all other versions for the same `scoring_config_id`.
3. AT ALL TIMES, for any given `scoring_config_id`, THE System SHALL ensure at most one `ScoringVersion` has `is_active=True`.
4. WHEN a `ScoringVersion` is published, THE AdminAPI SHALL validate that `thresholds_json` contains both `"HOT"` and `"WARM"` integer keys and that `thresholds["HOT"] > thresholds["WARM"] >= 0`.
5. THE AdminAPI SHALL expose a simulation endpoint that accepts a set of answers and returns the computed `ScoreResult` using the active `ScoringVersion`, without persisting any data.

---

### Requirement 7: Email Template Management

**User Story:** As a tenant admin, I want to manage versioned email templates for the invite and post-submission emails, so that I can customize messaging per lead bucket.

#### Acceptance Criteria

1. THE AdminAPI SHALL allow authenticated tenant admins to create, read, and publish `MessageTemplateVersion` records for `INITIAL_INVITE_EMAIL` and `POST_SUBMISSION_EMAIL` template keys.
2. WHEN a `MessageTemplateVersion` is published, THE AdminAPI SHALL set `is_active=True` on the new version and `is_active=False` on all other versions for the same `template_id`.
3. AT ALL TIMES, for any given `template_id`, THE System SHALL ensure at most one `MessageTemplateVersion` has `is_active=True`.
4. THE `POST_SUBMISSION_EMAIL` template SHALL support per-bucket variants with separate `subject` and `body` for each of `HOT`, `WARM`, and `NURTURE`.
5. WHEN a `MessageTemplateVersion` is published, THE TemplateRenderEngine SHALL validate that every `{{variable}}` in `subject_template` and `body_template` (and all variants) is a member of `SUPPORTED_VARS`; if any unknown variable is found, THE AdminAPI SHALL reject the publish with a descriptive error.
6. WHEN a `MessageTemplateVersion` is published, THE AdminAPI SHALL validate that `subject_template` contains no newline characters to prevent header injection.
7. THE TemplateRenderEngine SHALL HTML-escape all user-supplied context values when substituting into `body_template`.
8. WHEN a context variable referenced in a template is absent from the render context, THE TemplateRenderEngine SHALL substitute an empty string and log a warning.
9. IF no active `MessageTemplateVersion` exists for a required template key, THEN THE System SHALL log an error, skip the email send, and record a failed `LeadInteraction`.

---

### Requirement 8: Template Rendering

**User Story:** As a system operator, I want the template engine to produce consistent, safe email content, so that leads receive correctly formatted and injection-free emails.

#### Acceptance Criteria

1. WHEN rendering a template, THE TemplateRenderEngine SHALL substitute all `{{variable}}` placeholders using the provided context dictionary.
2. WHEN a `variant_key` is provided and the template has a matching variant in `variants_json`, THE TemplateRenderEngine SHALL use the variant's `subject` and `body` instead of the base template fields.
3. IF a `variant_key` is provided but not found in `variants_json`, THEN THE TemplateRenderEngine SHALL raise a `VariantNotFoundError`.
4. THE TemplateRenderEngine SHALL produce identical output when rendering the same template version and context more than once (idempotent rendering).
5. THE TemplateRenderEngine SHALL support a `preview` method that renders arbitrary subject and body strings with an optional sample context, without requiring a persisted `MessageTemplateVersion`.

---

### Requirement 9: Buyer Lead Email Received Handler

**User Story:** As a system operator, I want the system to automatically initiate the qualification pipeline when a buyer lead email arrives, so that no manual intervention is needed.

#### Acceptance Criteria

1. WHEN a `lead_created` event is received from the Gmail watcher for a BUY intent lead, THE System SHALL resolve the active `FormVersion` for the tenant's BUY intent.
2. IF no active `FormVersion` exists for the tenant's BUY intent, THEN THE System SHALL log a warning and take no further action for that lead.
3. WHEN an active `FormVersion` is found, THE System SHALL transition the lead to `FORM_INVITE_CREATED`, create a `FormInvitation`, render the `INITIAL_INVITE_EMAIL` template, send the email, and transition the lead to `FORM_INVITE_SENT` — all within the same request context.
4. WHEN the invitation email is sent, THE System SHALL record an outbound `LeadInteraction` with `channel=EMAIL` and the rendered email subject as `content_text`.
5. WHEN building the render context for `INITIAL_INVITE_EMAIL`, THE System SHALL populate `{{form.link}}` with the public submission URL containing the raw token.

---

### Requirement 10: Post-Submission Pipeline

**User Story:** As a system operator, I want the system to automatically score a lead and send a tailored acknowledgement email after form submission, so that leads receive timely, relevant follow-up.

#### Acceptance Criteria

1. WHEN a valid form submission is received, THE System SHALL transition the lead through `FORM_SUBMITTED → SCORED → POST_SUBMISSION_EMAIL_SENT` in sequence.
2. WHEN scoring is complete, THE System SHALL render the `POST_SUBMISSION_EMAIL` template using the `score.bucket` as the `variant_key`.
3. WHEN the post-submission email is sent, THE System SHALL record an outbound `LeadInteraction` with `channel=EMAIL` and the rendered email subject as `content_text`.
4. THE System SHALL NOT store the full rendered email body in `lead_interactions.content_text`; only the subject SHALL be stored.

---

### Requirement 11: Admin Panel — Form Tab

**User Story:** As a tenant admin, I want a dedicated admin panel tab for managing buyer qualification forms, so that I can configure and publish forms without engineering support.

#### Acceptance Criteria

1. THE AdminPanel SHALL provide a `BuyerFormTab` that lists all `FormTemplate` records for the authenticated tenant.
2. THE `BuyerFormTab` SHALL allow admins to create new form templates, edit draft versions, and publish new versions.
3. THE `FormVersionEditor` SHALL support drag-and-drop question ordering and a conditional logic rule builder.
4. THE `FormVersionEditor` SHALL display a JSON schema preview of the current form version.
5. THE `BuyerFormTab` SHALL allow admins to roll back to a previous published version.

---

### Requirement 12: Admin Panel — Scoring Tab

**User Story:** As a tenant admin, I want a dedicated admin panel tab for managing scoring rules, so that I can tune lead qualification criteria without engineering support.

#### Acceptance Criteria

1. THE AdminPanel SHALL provide a `BuyerScoringTab` that lists all `ScoringConfig` records for the authenticated tenant.
2. THE `ScoringVersionEditor` SHALL allow admins to add, edit, and delete scoring rules via a table interface showing `question_key`, `answer_value`, `points`, and `reason`.
3. THE `ScoringVersionEditor` SHALL allow admins to set HOT and WARM bucket thresholds.
4. THE `ScoringVersionEditor` SHALL display version history for each scoring config.

---

### Requirement 13: Admin Panel — Templates Tab

**User Story:** As a tenant admin, I want a dedicated admin panel tab for managing email templates, so that I can customize messaging for each lead bucket.

#### Acceptance Criteria

1. THE AdminPanel SHALL provide an `EmailTemplatesTab` that lists `INITIAL_INVITE_EMAIL` and `POST_SUBMISSION_EMAIL` templates for the authenticated tenant.
2. THE `TemplateVersionEditor` SHALL provide a variable picker listing all `SUPPORTED_VARS`.
3. THE `TemplateVersionEditor` SHALL provide a live preview panel that renders the template with sample context data.
4. THE `TemplateVersionEditor` SHALL allow editing per-bucket variants (HOT, WARM, NURTURE) for `POST_SUBMISSION_EMAIL`.

---

### Requirement 14: Admin Panel — Lead States and Monitoring Tab

**User Story:** As a tenant admin, I want to monitor the current state of all leads in the qualification pipeline, so that I can identify stalled or problematic leads.

#### Acceptance Criteria

1. THE AdminPanel SHALL provide a `LeadStatesTab` that displays a paginated table of leads with their `current_state` and `current_state_updated_at`.
2. THE `LeadStatesTab` SHALL allow filtering leads by `current_state` and `bucket`.
3. THE AdminAPI SHALL expose a funnel conversion stats endpoint (`GET /tenants/{tid}/leads/funnel`) that returns the count of leads at each state.
4. THE `LeadStatesTab` SHALL display a funnel chart visualizing state-to-state conversion rates.

---

### Requirement 15: Admin Panel — Simulation Tab

**User Story:** As a tenant admin, I want to simulate the scoring and email output for a hypothetical set of answers, so that I can validate my scoring rules and templates before going live.

#### Acceptance Criteria

1. THE AdminPanel SHALL provide a `SimulationTab` that renders the active buyer qualification form for the tenant.
2. WHEN an admin submits answers in the `SimulationTab`, THE AdminAPI SHALL compute and return the `ScoreResult` (total, bucket, breakdown, explanation) using the active `ScoringVersion` without persisting any data.
3. THE `SimulationTab` SHALL display the rendered `POST_SUBMISSION_EMAIL` preview for the computed bucket alongside the score breakdown.

---

### Requirement 16: Admin Panel — Audit Tab

**User Story:** As a tenant admin, I want a filterable audit log of all buyer-lead automation actions, so that I can investigate issues and demonstrate compliance.

#### Acceptance Criteria

1. THE AdminPanel SHALL provide a `BuyerAuditTab` that displays a filterable, paginated audit log for the authenticated tenant.
2. THE `BuyerAuditTab` SHALL include events for: form version publishes, scoring version publishes, template version publishes, emails sent, and lead state transitions.
3. THE AdminAPI SHALL expose an audit log endpoint (`GET /tenants/{tid}/audit`) that returns audit entries filterable by date range, event type, and lead ID.

---

### Requirement 17: Tenant Isolation and Security

**User Story:** As a platform operator, I want all tenant data to be strictly isolated, so that one tenant cannot access or infer another tenant's leads, forms, or configurations.

#### Acceptance Criteria

1. THE AdminAPI SHALL filter all query results by the `tenant_id` derived from the authenticated session; cross-tenant records SHALL NOT be returned.
2. IF a request targets a resource belonging to a different tenant, THEN THE AdminAPI SHALL return HTTP 404 (not HTTP 403) to prevent tenant enumeration.
3. THE PublicSubmissionEndpoint SHALL not expose any tenant-identifying information in error responses.
4. THE System SHALL store only the SHA-256 hash of form invitation tokens in the database; the raw token SHALL be transmitted to the lead exactly once via email.
5. THE System SHALL NOT log `raw_payload_json` from form submissions; PII in submission answers SHALL NOT appear in application logs.
6. THE System SHALL NOT store the full rendered email body in `lead_interactions`; only the email subject SHALL be stored as `content_text`.
7. WHEN rendering email body templates, THE TemplateRenderEngine SHALL HTML-escape all user-supplied values before substitution.
8. WHEN a `MessageTemplateVersion` is published, THE AdminAPI SHALL reject any `subject_template` containing newline characters.

---

### Requirement 18: Rate Limiting

**User Story:** As a platform operator, I want the public submission endpoint to be rate-limited, so that brute-force token guessing is not feasible.

#### Acceptance Criteria

1. THE PublicSubmissionEndpoint SHALL enforce a maximum of 5 requests per minute per source IP address.
2. WHEN the rate limit is exceeded, THE PublicSubmissionEndpoint SHALL return HTTP 429 with `{"error": "Too many requests"}`.
3. THE rate limit threshold SHALL be configurable without code changes.

---

### Requirement 19: Scalability to Additional Intent Types

**User Story:** As a platform operator, I want the system to be extensible to SELL and RENT intent types, so that the same pipeline can serve additional lead categories without schema or service refactoring.

#### Acceptance Criteria

1. THE System SHALL store an `intent_type` discriminator on every versioned entity: `form_templates`, `scoring_configs`, `message_templates`, `form_invitations`, `form_submissions`, and `lead_state_transitions`.
2. WHEN resolving active versions, THE System SHALL filter by both `tenant_id` and `intent_type`, ensuring BUY, SELL, and RENT configurations are independent.
3. THE LeadStateMachine SHALL support independent `VALID_TRANSITIONS` maps per `intent_type`, allowing SELL and RENT to define different state graphs without modifying BUY transitions.
4. THE ScoringEngine SHALL apply the `ScoringVersion` matching the submission's `intent_type`, enabling distinct scoring rules per intent without code changes.
5. WHERE `intent_type=SELL` or `intent_type=RENT` configurations are added, THE System SHALL process those leads through the same pipeline services (FormInvitationService, ScoringEngine, TemplateRenderEngine, LeadStateMachine) without modification.

---

### Requirement 20: Data Integrity and Immutability

**User Story:** As a platform operator, I want all audit and scoring records to be immutable after creation, so that the historical record is trustworthy and tamper-evident.

#### Acceptance Criteria

1. THE System SHALL never update or delete rows in `lead_state_transitions` after insertion.
2. THE System SHALL never update or delete rows in `lead_interactions` after insertion.
3. WHEN a `FormSubmission` is persisted, THE System SHALL link it to the `FormInvitation` via `invitation_id` and ensure `form_invitations.used_at` is set within the same transaction.
4. THE System SHALL enforce at the database level that each `form_submission` has at most one associated `submission_score` (unique constraint on `submission_scores.submission_id`).
5. WHEN a `FormVersion`, `ScoringVersion`, or `MessageTemplateVersion` is published, THE System SHALL set `published_at` to the current timestamp and SHALL NOT allow modification of the version's content after publication.

