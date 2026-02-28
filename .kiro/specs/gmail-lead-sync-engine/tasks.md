# Implementation Plan: Gmail Lead Sync & Response Engine

## Overview

This implementation plan breaks down the Gmail Lead Sync & Response Engine into discrete coding tasks. The system will be built in Python 3.10+ using SQLite, SQLAlchemy ORM, IMAP/SMTP protocols, and Pydantic validation. The implementation follows a bottom-up approach: database layer first, then core components, CLI utilities, and finally integration with comprehensive testing throughout.

## Tasks

- [x] 1. Project setup and dependencies
  - Create project directory structure (gmail_lead_sync/, tests/, migrations/)
  - Create requirements.txt with dependencies: SQLAlchemy, Alembic, Pydantic, cryptography, hypothesis, pytest, pytest-cov
  - Create requirements-dev.txt with development dependencies
  - Set up .gitignore for Python projects (exclude *.db, __pycache__, .env)
  - Create setup.py or pyproject.toml for package installation
  - Initialize git repository
  - _Requirements: 9.1, 9.2_

- [x] 2. Database models and schema
  - [x] 2.1 Create SQLAlchemy base and models
    - Create gmail_lead_sync/models.py with Base = declarative_base()
    - Implement Lead model with all fields (id, name, phone, source_email, lead_source_id, gmail_uid, created_at, updated_at, response_sent, response_status)
    - Implement LeadSource model with all fields (id, sender_email, identifier_snippet, name_regex, phone_regex, template_id, auto_respond_enabled, created_at, updated_at)
    - Implement ProcessingLog model with all fields (id, gmail_uid, timestamp, sender_email, status, error_details, lead_id, created_at)
    - Implement Template model with all fields (id, name, subject, body, created_at, updated_at)
    - Implement Credentials model with all fields (id, agent_id, email_encrypted, app_password_encrypted, created_at, updated_at)
    - Define all relationships (Lead.lead_source, Lead.processing_logs, LeadSource.leads, LeadSource.template, etc.)
    - Add indexes: gmail_uid (unique), source_email, sender_email, timestamp, status
    - Add composite index on ProcessingLog (timestamp, sender_email, status)
    - _Requirements: 9.3, 9.6_

  - [ ]* 2.2 Write property test for database models
    - **Property 8: Atomic Lead and UID Storage**
    - **Validates: Requirements 3.3, 3.4**
    - Test that Lead and gmail_uid are stored atomically (transaction rollback test)

  - [x] 2.3 Create Alembic migration configuration
    - Initialize Alembic with `alembic init migrations`
    - Configure alembic.ini with SQLite connection string
    - Create initial migration script for all tables
    - Test migration up and down
    - _Requirements: 9.5_

- [x] 3. Pydantic validation models
  - [x] 3.1 Create validation models
    - Create gmail_lead_sync/validation.py
    - Implement LeadData model with name, phone, source_email fields
    - Add validator for phone: regex pattern, minimum 7 digits
    - Add validator for name: strip whitespace
    - Implement LeadSourceConfig model with all fields and regex validation
    - Implement TemplateConfig model with placeholder validation
    - _Requirements: 5.6, 9.4_

  - [ ]* 3.2 Write property test for Pydantic validation
    - **Property 15: Pydantic Validation Gate**
    - **Validates: Requirements 5.6**
    - Test that invalid data is rejected before database insertion

- [x] 4. Credentials Store component
  - [x] 4.1 Implement credentials store interface and implementations
    - Create gmail_lead_sync/credentials.py
    - Define CredentialsStore abstract base class with get_credentials() and store_credentials() methods
    - Implement EnvironmentCredentialsStore that reads from environment variables
    - Implement EncryptedDBCredentialsStore with Fernet encryption
    - Add encrypt() and decrypt() methods using cryptography.fernet
    - Load encryption key from ENCRYPTION_KEY environment variable
    - Add error handling for missing encryption key
    - _Requirements: 7.1, 7.2, 7.4, 7.5_

  - [ ]* 4.2 Write unit tests for credentials store
    - Test environment variable retrieval
    - Test encryption/decryption round-trip
    - Test missing encryption key error
    - Test invalid agent_id lookup
    - _Requirements: 7.1, 7.2_

  - [ ]* 4.3 Write property test for credential encryption
    - **Property 22: Credential Encryption**
    - **Validates: Requirements 7.2**
    - Test that encrypt then decrypt produces original credentials

- [x] 5. Parser component
  - [x] 5.1 Implement lead parser
    - Create gmail_lead_sync/parser.py
    - Implement LeadParser class with __init__(db_session)
    - Implement get_lead_source(sender_email, email_body) to match sender and verify identifier_snippet
    - Implement extract_lead(email_body, lead_source) to apply name_regex and phone_regex
    - Implement validate_and_create_lead(lead_data, gmail_uid, lead_source_id) using Pydantic
    - Add error handling for regex match failures
    - Add logging for parsing failures with email content snippets (truncated to 500 chars)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ]* 5.2 Write unit tests for parser
    - Test successful lead extraction with valid email
    - Test identifier_snippet not found
    - Test name_regex no match
    - Test phone_regex no match
    - Test Pydantic validation failure
    - Test multiple Lead_Source matching (first with valid identifier wins)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 5.3 Write property tests for parser
    - **Property 9: Lead Source Matching**
    - **Validates: Requirements 4.3**
    - **Property 11: Identifier Snippet Verification**
    - **Validates: Requirements 5.1**
    - **Property 13: Dual Extraction Attempt**
    - **Validates: Requirements 5.3, 5.4**
    - **Property 16: Valid Lead Creation**
    - **Validates: Requirements 5.7**

- [x] 6. Checkpoint - Ensure parser tests pass
  - Run pytest tests/unit/test_parser.py and tests/property/test_parsing_properties.py
  - Ensure all tests pass, ask the user if questions arise

- [x] 7. Auto Responder component
  - [x] 7.1 Implement template renderer
    - Create gmail_lead_sync/responder.py
    - Implement TemplateRenderer class with render_template(template, lead, agent_info) method
    - Replace placeholders: {lead_name}, {agent_name}, {agent_phone}, {agent_email}
    - Add validation that all placeholders are replaced
    - _Requirements: 6.3, 6.4, 13.1_

  - [x] 7.2 Implement auto responder with SMTP
    - Implement AutoResponder class with __init__(credentials_store, db_session)
    - Implement send_acknowledgment(lead, lead_source) to check auto_respond_enabled and template
    - Implement send_email(to_address, subject, body) with SMTP connection to smtp.gmail.com:587
    - Add TLS/STARTTLS support
    - Add retry logic with exponential backoff (max 3 attempts)
    - Update Lead.response_sent and Lead.response_status fields
    - Add error handling for SMTP failures without blocking lead processing
    - _Requirements: 6.1, 6.2, 6.5, 6.6, 6.7_

  - [ ]* 7.3 Write unit tests for auto responder
    - Test template rendering with all placeholders
    - Test send_email success
    - Test send_email retry on failure
    - Test send_email final failure after 3 attempts
    - Test auto_respond_enabled=False skips sending
    - Test missing template skips sending
    - _Requirements: 6.1, 6.4, 6.5, 6.6_

  - [ ]* 7.4 Write property tests for auto responder
    - **Property 17: Conditional Auto-Response**
    - **Validates: Requirements 6.1**
    - **Property 18: Template Placeholder Replacement**
    - **Validates: Requirements 6.4, 13.1**
    - **Property 19: SMTP Retry Logic**
    - **Validates: Requirements 6.5**
    - **Property 20: SMTP Failure Isolation**
    - **Validates: Requirements 6.6**
    - **Property 34: Lead to Template Round-Trip**
    - **Validates: Requirements 14.2, 14.3**

- [x] 8. Watcher component
  - [x] 8.1 Implement IMAP connection manager
    - Create gmail_lead_sync/watcher.py
    - Implement IMAPConnection class with connect_with_retry(max_attempts=5)
    - Add exponential backoff retry logic (2^attempt seconds)
    - Add connection loss detection and reconnection
    - Add IDLE mode support for real-time notifications
    - Add error handling for authentication failures
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 8.2 Implement email discovery and processing
    - Implement GmailWatcher class with __init__(credentials_store, db_session)
    - Implement process_unseen_emails(sender_list) to search UNSEEN emails
    - Implement is_email_processed(gmail_uid) to check UID existence
    - Implement mark_as_processed(gmail_uid, lead_id) to store UID atomically
    - Add chronological ordering by received date
    - Retrieve Gmail_UID, sender, and body for each email
    - Integrate with Parser to extract leads
    - Integrate with AutoResponder to send acknowledgments
    - Create Processing_Log records for all attempts
    - Add error isolation: continue processing on individual email failures
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 8.1, 8.2, 8.3, 8.4, 11.2_

  - [ ]* 8.3 Write unit tests for watcher
    - Test IMAP connection with retry
    - Test UNSEEN email search
    - Test UID existence check
    - Test email skipping when UID exists
    - Test chronological processing order
    - Test Processing_Log creation on success
    - Test Processing_Log creation on failure
    - Test error isolation (one email fails, others continue)
    - _Requirements: 1.2, 2.1, 2.4, 3.1, 3.2, 8.1, 11.2_

  - [ ]* 8.4 Write property tests for watcher
    - **Property 1: Connection Retry Exponential Backoff**
    - **Validates: Requirements 1.2**
    - **Property 2: Connection Loss Resilience**
    - **Validates: Requirements 1.5**
    - **Property 3: UNSEEN Email Filtering**
    - **Validates: Requirements 2.1**
    - **Property 4: Complete Email Data Retrieval**
    - **Validates: Requirements 2.2, 2.3**
    - **Property 5: Chronological Processing Order**
    - **Validates: Requirements 2.4**
    - **Property 6: UID Existence Check Before Processing**
    - **Validates: Requirements 3.1**
    - **Property 7: Idempotent Email Processing**
    - **Validates: Requirements 3.2**
    - **Property 23: Processing Audit Trail**
    - **Validates: Requirements 8.1, 8.2**
    - **Property 29: Error Isolation**
    - **Validates: Requirements 11.2**

- [x] 9. Checkpoint - Ensure core components work together
  - Run all unit and property tests for parser, responder, and watcher
  - Ensure all tests pass, ask the user if questions arise

- [x] 10. Error handling and logging
  - [x] 10.1 Implement centralized error handling
    - Create gmail_lead_sync/error_handling.py
    - Implement execute_with_retry(operation, max_attempts=3) for database operations
    - Add database lock handling with exponential backoff
    - Add IntegrityError handling for duplicate UIDs
    - Implement top-level exception handler for main loop
    - _Requirements: 11.1, 11.3, 11.4_

  - [x] 10.2 Configure logging system
    - Create gmail_lead_sync/logging_config.py
    - Set up RotatingFileHandler with 10MB max size, 5 backups
    - Configure log format with timestamp, component, level, message
    - Implement redact_sensitive_data() to mask emails and passwords in logs
    - Add RedactingFormatter class
    - Set log level to INFO for production, DEBUG for development
    - _Requirements: 7.3, 11.1_

  - [ ]* 10.3 Write unit tests for error handling
    - Test database retry logic
    - Test database lock handling
    - Test duplicate UID handling (IntegrityError)
    - Test sensitive data redaction in logs
    - _Requirements: 11.3, 11.4, 7.3_

  - [ ]* 10.4 Write property tests for error handling
    - **Property 28: Exception Logging**
    - **Validates: Requirements 11.1**
    - **Property 30: Database Operation Retry**
    - **Validates: Requirements 11.3, 11.4**

- [x] 11. Health check endpoint
  - [x] 11.1 Implement health check API
    - Create gmail_lead_sync/health.py
    - Implement Flask app with /health endpoint
    - Check database connectivity
    - Check last successful sync time (within 1 hour)
    - Check IMAP connection status
    - Return JSON with status, database, imap, last_successful_sync, timestamp
    - Return 200 for healthy, 503 for degraded
    - _Requirements: 11.5_

  - [ ]* 11.2 Write unit tests for health check
    - Test healthy status (all checks pass)
    - Test degraded status (database disconnected)
    - Test degraded status (no recent sync)
    - Test degraded status (IMAP disconnected)
    - _Requirements: 11.5_

- [x] 12. Parser Tester CLI utility
  - [x] 12.1 Implement parser tester
    - Create gmail_lead_sync/cli/parser_tester.py
    - Implement test_pattern(email_body, pattern, pattern_type) to find all matches
    - Implement highlight_matches(email_body, matches) to show matches in context
    - Implement validate_regex(pattern) to check syntax
    - Add CLI command: test-parser --email-file <path> --name-regex <pattern> --phone-regex <pattern>
    - Display all matches with line numbers
    - Display syntax errors for invalid patterns
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ]* 12.2 Write unit tests for parser tester
    - Test pattern matching with valid regex
    - Test pattern matching with no matches
    - Test regex syntax validation
    - Test invalid regex error message
    - Test match highlighting
    - _Requirements: 10.2, 10.3, 10.5, 10.6_

  - [ ]* 12.3 Write property tests for parser tester
    - **Property 26: Parser Tester Match Display**
    - **Validates: Requirements 10.2, 10.3**
    - **Property 27: Regex Syntax Validation**
    - **Validates: Requirements 10.5, 10.6, 12.5**

- [x] 13. Configuration Manager CLI utility
  - [x] 13.1 Implement Lead Source management commands
    - Create gmail_lead_sync/cli/config_manager.py
    - Implement add_source command with arguments: sender, identifier, name-regex, phone-regex, template-id
    - Implement list_sources command to display all Lead_Source records
    - Implement update_source command with --id and optional field updates
    - Implement delete_source command with --id
    - Add regex syntax validation before saving
    - Add email format validation for sender_email
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [x] 13.2 Implement Template management commands
    - Implement add_template command with arguments: name, subject, body-file
    - Implement list_templates command to display all Template records
    - Implement update_template command with --id and optional field updates
    - Implement delete_template command with --id
    - Add placeholder validation (only supported placeholders allowed)
    - _Requirements: 13.2, 13.3_

  - [ ]* 13.3 Write unit tests for configuration manager
    - Test add_source with valid data
    - Test add_source with invalid regex
    - Test add_source with invalid email
    - Test list_sources output
    - Test update_source
    - Test delete_source
    - Test add_template with valid placeholders
    - Test add_template with invalid placeholders
    - _Requirements: 12.1, 12.5, 12.6, 13.2, 13.3_

  - [ ]* 13.4 Write property tests for configuration manager
    - **Property 10: Unmatched Sender Handling**
    - **Validates: Requirements 4.5**
    - **Property 12: Missing Identifier Handling**
    - **Validates: Requirements 5.2**
    - **Property 14: Extraction Failure Logging**
    - **Validates: Requirements 5.5**
    - **Property 21: Response Status Recording**
    - **Validates: Requirements 6.7**
    - **Property 24: Parsing Failure Diagnostics**
    - **Validates: Requirements 8.3**
    - **Property 25: Successful Processing Link**
    - **Validates: Requirements 8.4**
    - **Property 31: Email Format Validation**
    - **Validates: Requirements 12.6**
    - **Property 32: Template Placeholder Validation**
    - **Validates: Requirements 13.3**
    - **Property 33: No Template No Response**
    - **Validates: Requirements 13.5**

- [x] 14. Main application entry point
  - [x] 14.1 Create main application script
    - Create gmail_lead_sync/__main__.py
    - Implement main() function with argument parsing
    - Add commands: start (run watcher), test-parser, add-source, list-sources, update-source, delete-source, add-template, list-templates, update-template, delete-template
    - Set up logging configuration
    - Initialize database session
    - Initialize credentials store
    - Implement graceful shutdown on SIGINT/SIGTERM
    - Add top-level exception handler with restart logic (wait 60 seconds)
    - _Requirements: 11.1_

  - [x] 14.2 Create systemd service file (optional)
    - Create gmail-lead-sync.service file for Linux systems
    - Configure auto-restart on failure
    - Set environment variables for ENCRYPTION_KEY
    - Add installation instructions in README

- [x] 15. Integration testing
  - [ ]* 15.1 Write end-to-end integration tests
    - Test complete flow: IMAP → Parser → Database → Auto Responder → SMTP
    - Test idempotency: process same email twice, verify single lead
    - Test error recovery: simulate IMAP disconnect, verify reconnection
    - Test multiple lead sources with different patterns
    - Test auto-response enabled vs disabled
    - Use mock IMAP and SMTP servers
    - _Requirements: 3.2, 1.5, 6.1_

  - [ ]* 15.2 Write health check integration tests
    - Test health endpoint with running watcher
    - Test health endpoint with database issues
    - Test health endpoint with stale sync
    - _Requirements: 11.5_

- [x] 16. Documentation
  - [x] 16.1 Create README.md
    - Add project overview and features
    - Add installation instructions (Python 3.10+, pip install -r requirements.txt)
    - Add configuration instructions (environment variables, encryption key generation)
    - Add usage examples for all CLI commands
    - Add Gmail App Password setup instructions
    - Add troubleshooting section
    - Add architecture diagram reference

  - [x] 16.2 Create DEPLOYMENT.md
    - Add deployment instructions for Linux servers
    - Add systemd service setup
    - Add database backup recommendations
    - Add monitoring and alerting recommendations
    - Add security best practices (file permissions, encryption key management)

  - [x] 16.3 Add inline code documentation
    - Add docstrings to all classes and public methods
    - Add type hints to all function signatures
    - Add comments for complex regex patterns and business logic

- [x] 17. Security hardening
  - [x] 17.1 Implement input sanitization
    - Add sanitize_email_body() to remove null bytes and limit size
    - Add validate_regex_safety() to detect catastrophic backtracking
    - Add timeout for regex execution (1 second max)
    - _Requirements: 7.3_

  - [x] 17.2 Implement rate limiting
    - Create RateLimiter class for IMAP requests (100 requests per minute)
    - Add rate limiting to fetch_email operations
    - Add logging for rate limit hits
    - _Requirements: 11.1_

  - [ ]* 17.3 Write security tests
    - Test email body size limit
    - Test null byte removal
    - Test regex timeout
    - Test rate limiting
    - Test credential encryption key validation
    - _Requirements: 7.2, 7.3_

- [x] 18. Final checkpoint and deployment preparation
  - Run full test suite: pytest tests/ -v --cov=gmail_lead_sync --cov-report=html
  - Verify coverage meets minimum 85% line coverage, 80% branch coverage
  - Run all 34 property-based tests with max_examples=100
  - Test database migrations (up and down)
  - Create sample Lead_Source and Template configurations
  - Test with real Gmail account (using test credentials)
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional testing tasks that can be skipped for faster MVP delivery
- Each task references specific requirements for traceability
- Property-based tests use Hypothesis library with max_examples=100
- All property tests must include docstring with format: "Feature: gmail-lead-sync-engine, Property N: [Title]"
- Database operations use SQLAlchemy ORM exclusively (no raw SQL)
- All credentials must be encrypted with AES-256 before storage
- IMAP and SMTP connections use exponential backoff retry logic
- Processing_Log provides complete audit trail for debugging
- System designed for long-running background service operation
- Health check endpoint enables monitoring and alerting integration

