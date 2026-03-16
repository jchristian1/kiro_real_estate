# Testing Gaps

This document lists modules and areas that are not fully covered by the automated test suite, along with the rationale for each gap. It is maintained as a living document — gaps should be closed over time or explicitly accepted with justification.

---

## Backend — `gmail_lead_sync/`

### `gmail_lead_sync/watcher.py` — ~13% covered

**Gap**: The `GmailWatcher` class contains ~350 statements; only ~45 are exercised by the current test suite. The untested paths include the live IMAP connection logic, `process_unseen_emails`, SMTP response sending, and reconnection handling.

**Rationale**: These paths require a live Gmail IMAP/SMTP connection. Mocking the full IMAP4_SSL protocol is high-effort and brittle. The watcher's resilience properties (backoff, heartbeat, exception survival) are covered by property-based tests in `tests/property/test_prop_watcher_*.py` using mock watcher objects. End-to-end watcher behaviour is validated manually during clean-clone validation.

**Risk**: Medium. A regression in IMAP parsing or SMTP sending would not be caught automatically.

---

### `gmail_lead_sync/responder.py` — ~15% covered

**Gap**: The `AutoResponder` class (~114 statements) is largely untested. Untested paths include SMTP connection setup, TLS negotiation, template rendering into emails, retry logic, and failure handling.

**Rationale**: Requires a live SMTP server or a complex mock. The template rendering logic is separately tested via `api/services/template_renderer.py`. SMTP retry logic mirrors the watcher's backoff, which is property-tested.

**Risk**: Medium. A broken SMTP send would not be caught until a real email is attempted.

---

### `gmail_lead_sync/parser.py` — ~16% covered

**Gap**: The email parser (~106 statements) has low coverage. Untested paths include multi-part MIME handling, HTML email stripping, and edge cases in regex extraction.

**Rationale**: Core parsing properties (regex correctness, capture group validation) are covered by `tests/property/test_parsing_properties.py`. The untested paths are mostly MIME-handling branches that require constructing realistic email objects.

**Risk**: Low-medium. Parsing failures surface quickly in manual testing and produce clear `processing_logs` entries.

---

### `gmail_lead_sync/error_handling.py` — ~16% covered

**Gap**: The error handling module (~128 statements) is largely untested. It contains retry decorators, IMAP error classifiers, and structured error formatters.

**Rationale**: IMAP error classification is covered by `tests/property/test_prop_imap_error_classification.py`. The retry decorator paths require simulating sequences of failures, which is complex to set up reliably.

**Risk**: Low. Error handling is defensive code; failures degrade gracefully rather than causing data loss.

---

### `gmail_lead_sync/logging_config.py` — 0% covered

**Gap**: The logging configuration module (36 statements) has no automated tests.

**Rationale**: This module configures Python's `logging` framework at startup. Its correctness is observable at runtime (log output format, level filtering). Writing tests for logging configuration setup provides low value relative to the effort.

**Risk**: Very low. A misconfiguration produces visible log output immediately.

---

### `gmail_lead_sync/health.py` — 0% covered

**Gap**: The legacy CLI health check module (80 statements) has no tests.

**Rationale**: This is the original CLI-era health check, superseded by the `GET /api/v1/health` endpoint which is fully tested in `tests/unit/test_public_health.py` and `tests/unit/test_health_api.py`. The CLI health module is retained for backward compatibility but is not on the critical path.

**Risk**: Very low. The API health endpoint is the authoritative health signal.

---

### `gmail_lead_sync/__main__.py` — 0% covered

**Gap**: The CLI entry point (~180 statements) has no automated tests.

**Rationale**: This is the original CLI interface (`gmail-lead-sync start`, `add-source`, etc.). The web API has replaced the CLI as the primary interface. Testing CLI entry points requires subprocess invocation and is low priority given the Docker-first deployment model.

**Risk**: Low. CLI commands are not used in the Docker deployment path.

---

### `gmail_lead_sync/cli/config_manager.py` — 0% covered
### `gmail_lead_sync/cli/parser_tester.py` — 0% covered

**Gap**: Both CLI utility modules (318 and 105 statements respectively) have no tests.

**Rationale**: Same as `__main__.py` — these are legacy CLI tools superseded by the web API. They are retained for developer convenience but are not on the production code path.

**Risk**: Low.

---

### `gmail_lead_sync/credentials.py` — ~40% covered

**Gap**: The legacy `EncryptedDBCredentialsStore` class has partial coverage. The untested paths are the IMAP/SMTP credential retrieval methods that decrypt and return credentials for live connections.

**Rationale**: Retrieval paths require a live IMAP connection. The encryption/decryption logic itself is fully covered by `tests/property/test_prop_credential_never_plaintext.py` and `tests/unit/test_credential_encryption.py`.

**Risk**: Low. The encryption correctness is well-tested; the retrieval wiring is simple.

---

### `gmail_lead_sync/lead_event_utils.py` — 0% covered

**Gap**: Utility functions for lead event formatting (16 statements) have no tests.

**Rationale**: These are thin formatting helpers. The lead state machine and event log endpoint are tested end-to-end in integration tests, which exercises the output of these utilities indirectly.

**Risk**: Very low.

---

### `gmail_lead_sync/preapproval/handlers.py` — ~14% covered

**Gap**: The preapproval email handlers (~200 statements) are largely untested. These handle the full email-to-lead pipeline for preapproval-type leads.

**Rationale**: Handlers require a realistic email fixture and a fully configured database. The state machine transitions they trigger are covered by property tests. Full handler testing is deferred pending a test fixture library for realistic email objects.

**Risk**: Medium. A regression in handler logic could cause leads to be silently dropped.

**Planned**: Add integration tests using synthetic email fixtures in a future sprint.

---

### `gmail_lead_sync/preapproval/scoring_engine.py` — ~36% covered

**Gap**: The scoring engine has partial coverage. Untested paths include edge cases in score calculation for unusual lead data combinations.

**Rationale**: Core scoring properties are covered by `tests/property/test_prop_scoring_engine.py`. The untested paths are boundary conditions in the scoring formula.

**Risk**: Low. Scoring errors produce incorrect scores, not crashes, and are visible in the UI.

---

### `gmail_lead_sync/preapproval/invitation_service.py` — ~41% covered

**Gap**: The invitation service has partial coverage. Untested paths include SMTP sending and error handling for failed invitations.

**Rationale**: SMTP paths require a live server. The service logic (invitation creation, state transitions) is covered. SMTP failure handling is defensive.

**Risk**: Low-medium.

---

### `gmail_lead_sync/preapproval/template_engine.py` — ~45% covered

**Gap**: The preapproval template engine has partial coverage. Untested paths include edge cases in placeholder substitution with missing values.

**Rationale**: Core template rendering is covered by `tests/unit/test_template_renderer.py`. The preapproval-specific template engine shares the same placeholder logic.

**Risk**: Low.

---

### `gmail_lead_sync/preapproval/seed.py` — 0% covered

**Gap**: The database seed script has no tests.

**Rationale**: Seed scripts are development/staging utilities, not production code. They are run manually and their output is immediately visible.

**Risk**: Very low.

---

## Frontend

### `frontend/src/apps/agent/` — no automated tests

**Gap**: The agent-facing React app has no component-level unit tests. The only frontend test is `frontend/src/test/authFlow.test.tsx` covering the auth flow.

**Rationale**: The frontend restructure (task 16) moved files into the new `apps/` structure. Component tests were not in scope for this hardening pass. The build (`make build`) and TypeScript typecheck (`make typecheck`) provide a baseline correctness signal.

**Risk**: Medium. UI regressions are not caught automatically.

**Planned**: Add Vitest component tests for critical agent pages (dashboard, leads list) in a follow-up sprint.

---

### `frontend/src/apps/platform-admin/` — no automated tests

**Gap**: Same as the agent app — no component tests exist for the platform-admin panel.

**Rationale**: Same as above.

**Risk**: Medium.

---

## API Layer

### `api/services/imap_service.py` — partially covered

**Gap**: The IMAP service's live connection paths are not tested. Rate limiting logic is covered by `tests/property/test_prop_imap_rate_limiting.py`.

**Rationale**: Live IMAP connections cannot be made in CI without real credentials.

**Risk**: Low. Connection failures are caught at runtime with clear error messages.

---

### `api/services/session_cleanup.py` — partially covered

**Gap**: The background session cleanup task is not tested end-to-end (the cleanup logic itself is unit-tested).

**Rationale**: Testing background task scheduling requires time-based mocking that adds test complexity without proportional value.

**Risk**: Very low. Expired sessions are harmless — they simply cannot be used.

---

## Summary

| Module | Coverage | Risk | Planned fix |
|--------|----------|------|-------------|
| `gmail_lead_sync/watcher.py` | ~13% | Medium | Email fixture library |
| `gmail_lead_sync/responder.py` | ~15% | Medium | SMTP mock |
| `gmail_lead_sync/parser.py` | ~16% | Low-medium | MIME fixtures |
| `gmail_lead_sync/error_handling.py` | ~16% | Low | — |
| `gmail_lead_sync/logging_config.py` | 0% | Very low | — |
| `gmail_lead_sync/health.py` | 0% | Very low | — (superseded) |
| `gmail_lead_sync/__main__.py` | 0% | Low | — (CLI, not prod path) |
| `gmail_lead_sync/cli/` | 0% | Low | — (CLI, not prod path) |
| `gmail_lead_sync/preapproval/handlers.py` | ~14% | Medium | Email fixture library |
| `gmail_lead_sync/preapproval/seed.py` | 0% | Very low | — |
| `gmail_lead_sync/lead_event_utils.py` | 0% | Very low | — |
| `frontend/src/apps/agent/` | 0% | Medium | Vitest component tests |
| `frontend/src/apps/platform-admin/` | 0% | Medium | Vitest component tests |
