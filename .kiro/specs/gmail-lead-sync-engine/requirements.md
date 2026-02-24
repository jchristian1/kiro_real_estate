# Requirements Document

## Introduction

The Gmail Lead Sync & Response Engine is a lead management system for Real Estate agents that uses Gmail as the primary data source. The system monitors Gmail accounts via IMAP, extracts lead information using configurable parsing rules, stores leads in a local database, and optionally sends automated acknowledgment emails. The system operates at zero cost by avoiding Google API usage and implements idempotent sync logic to ensure reliable, duplicate-free lead processing.

## Glossary

- **Watcher**: The component that monitors Gmail accounts via IMAP for new emails
- **Parser**: The component that extracts lead information from email bodies using regex patterns
- **Auto_Responder**: The component that sends automated acknowledgment emails via SMTP
- **Lead**: A potential customer record extracted from an email, containing name and phone number
- **Lead_Source**: A configuration record defining how to identify and parse emails from a specific sender
- **Gmail_UID**: The unique identifier assigned by Gmail to each email message
- **Processing_Log**: A record of each email processing attempt including success or failure details
- **Agent**: A Real Estate agent user of the system
- **Configurable_Sender_List**: A list of email addresses from which the system should process leads
- **Template**: A customizable email message format with placeholders for lead information
- **Credentials_Store**: The secure storage mechanism for Agent Gmail credentials

## Requirements

### Requirement 1: Gmail IMAP Connection

**User Story:** As an Agent, I want the system to connect to my Gmail account via IMAP, so that I can monitor incoming leads without incurring Google API costs.

#### Acceptance Criteria

1. THE Watcher SHALL connect to Gmail using the imaplib protocol with App Password authentication
2. WHEN the IMAP connection fails, THE Watcher SHALL implement exponential backoff retry logic with a maximum of 5 attempts
3. WHEN the maximum retry attempts are exhausted, THE Watcher SHALL log the failure and wait 5 minutes before attempting reconnection
4. THE Watcher SHALL maintain the IMAP connection in IDLE mode to receive real-time notifications
5. WHEN the IMAP connection is lost, THE Watcher SHALL attempt to reconnect without crashing the application

### Requirement 2: Unseen Email Discovery

**User Story:** As an Agent, I want the system to search for unread emails from specific senders, so that I can process only relevant lead emails.

#### Acceptance Criteria

1. THE Watcher SHALL search for emails with the UNSEEN flag from senders in the Configurable_Sender_List
2. WHEN new UNSEEN emails are found, THE Watcher SHALL retrieve the Gmail_UID for each email
3. THE Watcher SHALL retrieve the email sender address and body content for processing
4. THE Watcher SHALL process emails in chronological order based on received date

### Requirement 3: Idempotent Email Processing

**User Story:** As an Agent, I want each email to be processed exactly once, so that I don't create duplicate lead records.

#### Acceptance Criteria

1. WHEN an email is discovered, THE Watcher SHALL check if the Gmail_UID exists in the database before processing
2. IF the Gmail_UID already exists in the database, THEN THE Watcher SHALL skip processing that email
3. WHEN an email is successfully processed, THE Watcher SHALL store the Gmail_UID in the database
4. THE Watcher SHALL store the Gmail_UID atomically with the Lead record to ensure consistency

### Requirement 4: Lead Source Configuration

**User Story:** As an Agent, I want to configure parsing rules for different lead sources, so that I can extract lead information from various email formats.

#### Acceptance Criteria

1. THE Parser SHALL retrieve Lead_Source configuration records from the database
2. THE Lead_Source record SHALL contain sender_email, identifier_snippet, name_regex, and phone_regex fields
3. WHEN processing an email, THE Parser SHALL match the sender address against Lead_Source records
4. WHEN multiple Lead_Source records match the sender, THE Parser SHALL use the first matching record with a valid identifier_snippet
5. WHERE no Lead_Source record matches the sender, THE Parser SHALL log a warning and skip the email

### Requirement 5: Lead Information Extraction

**User Story:** As an Agent, I want the system to extract lead names and phone numbers from emails, so that I can contact potential customers.

#### Acceptance Criteria

1. WHEN a matching Lead_Source is found, THE Parser SHALL verify the identifier_snippet exists in the email body
2. IF the identifier_snippet is not found in the email body, THEN THE Parser SHALL skip the email and log the mismatch
3. WHEN the identifier_snippet is found, THE Parser SHALL apply the name_regex to extract the lead name
4. WHEN the identifier_snippet is found, THE Parser SHALL apply the phone_regex to extract the lead phone number
5. WHEN either name_regex or phone_regex fails to match, THE Parser SHALL log the failure with the email content for debugging
6. WHEN both name and phone are successfully extracted, THE Parser SHALL validate the data using Pydantic models
7. WHEN validation succeeds, THE Parser SHALL create a Lead record in the database

### Requirement 6: Automated Email Response

**User Story:** As an Agent, I want to send automated acknowledgment emails to new leads, so that I can provide immediate engagement.

#### Acceptance Criteria

1. WHERE automated responses are enabled for a Lead_Source, THE Auto_Responder SHALL send an acknowledgment email when a Lead is created
2. THE Auto_Responder SHALL connect to Gmail SMTP using the Agent credentials
3. THE Auto_Responder SHALL retrieve the Template associated with the Lead_Source
4. THE Auto_Responder SHALL replace placeholders in the Template with Lead information
5. WHEN the SMTP send operation fails, THE Auto_Responder SHALL log the failure and retry up to 3 times
6. WHEN all retry attempts fail, THE Auto_Responder SHALL log the final failure without blocking lead processing
7. THE Auto_Responder SHALL record the response status in the Lead record

### Requirement 7: Credentials Security

**User Story:** As an Agent, I want my Gmail credentials stored securely, so that my account remains protected.

#### Acceptance Criteria

1. THE Credentials_Store SHALL support storage via environment variables or encrypted database fields
2. WHEN credentials are stored in the database, THE Credentials_Store SHALL encrypt them using AES-256 encryption
3. THE Credentials_Store SHALL never log or display credentials in plain text
4. THE Watcher SHALL retrieve credentials from the Credentials_Store at connection time
5. THE Auto_Responder SHALL retrieve credentials from the Credentials_Store at send time

### Requirement 8: Processing Audit Trail

**User Story:** As an Agent, I want detailed logs of all email processing attempts, so that I can debug issues and verify system behavior.

#### Acceptance Criteria

1. WHEN the Watcher processes an email, THE Watcher SHALL create a Processing_Log record
2. THE Processing_Log record SHALL contain the Gmail_UID, timestamp, sender, processing status, and error details
3. WHEN parsing fails, THE Processing_Log SHALL include the failure reason and the regex patterns used
4. WHEN lead extraction succeeds, THE Processing_Log SHALL reference the created Lead record
5. THE Processing_Log SHALL be queryable by date range, sender, and status

### Requirement 9: Database Schema and ORM

**User Story:** As a developer, I want a well-structured database with ORM support, so that I can maintain and extend the system easily.

#### Acceptance Criteria

1. THE system SHALL use SQLite as the database engine
2. THE system SHALL use SQLAlchemy ORM for all database operations
3. THE system SHALL define models for Lead, Lead_Source, Processing_Log, and Credentials tables
4. THE system SHALL use Pydantic models for data validation before database insertion
5. THE system SHALL implement database migrations using Alembic
6. THE system SHALL create indexes on Gmail_UID and sender_email fields for query performance

### Requirement 10: Parser Testing Utility

**User Story:** As an Agent, I want to test regex patterns against sample email content, so that I can verify parsing rules before deploying them.

#### Acceptance Criteria

1. THE Parser_Tester SHALL accept email body text and regex patterns as input
2. WHEN the user provides a name_regex, THE Parser_Tester SHALL display all matches found in the email body
3. WHEN the user provides a phone_regex, THE Parser_Tester SHALL display all matches found in the email body
4. THE Parser_Tester SHALL highlight the matched text in the email body for visual confirmation
5. THE Parser_Tester SHALL validate that regex patterns are syntactically correct before testing
6. WHEN a regex pattern is invalid, THE Parser_Tester SHALL display the syntax error message

### Requirement 11: Error Recovery and System Stability

**User Story:** As an Agent, I want the system to handle errors gracefully, so that temporary issues don't stop lead processing.

#### Acceptance Criteria

1. WHEN any component encounters an unhandled exception, THE system SHALL log the full stack trace
2. WHEN the Watcher encounters an error processing a specific email, THE Watcher SHALL continue processing remaining emails
3. WHEN database operations fail, THE system SHALL retry the operation up to 3 times with exponential backoff
4. WHEN the database is locked, THE system SHALL wait and retry the operation
5. THE system SHALL expose a health check endpoint that reports connection status and last successful sync time

### Requirement 12: Configuration Management

**User Story:** As an Agent, I want to manage Lead_Source configurations easily, so that I can add new lead sources without code changes.

#### Acceptance Criteria

1. THE system SHALL provide a command-line interface to add Lead_Source records
2. THE system SHALL provide a command-line interface to list all Lead_Source records
3. THE system SHALL provide a command-line interface to update Lead_Source records
4. THE system SHALL provide a command-line interface to delete Lead_Source records
5. WHEN adding a Lead_Source, THE system SHALL validate that the regex patterns are syntactically correct
6. WHEN adding a Lead_Source, THE system SHALL validate that the sender_email is a valid email format

### Requirement 13: Template Management

**User Story:** As an Agent, I want to customize automated response templates, so that I can personalize my communication with leads.

#### Acceptance Criteria

1. THE Template SHALL support placeholders for lead name, agent name, and agent contact information
2. THE system SHALL provide a command-line interface to create and edit Templates
3. THE system SHALL validate that Templates contain only supported placeholders
4. THE Lead_Source record SHALL reference an optional Template for automated responses
5. WHERE no Template is associated with a Lead_Source, THE Auto_Responder SHALL not send automated responses

### Requirement 14: Round-Trip Email Processing

**User Story:** As a developer, I want to ensure email parsing and template generation are inverse operations, so that data integrity is maintained.

#### Acceptance Criteria

1. THE Parser_Tester SHALL support testing the complete round-trip: parse email, generate response template, verify placeholders
2. WHEN a Lead is extracted from an email, THE system SHALL be able to regenerate a response using the Template
3. FOR ALL valid Lead records, generating a response template and extracting placeholders SHALL produce the original Lead data

## State Diagram Reference

The design document will include a state diagram showing email state transitions:
- Gmail Inbox (UNSEEN) → Discovered by Watcher → UID Check → Parsing → Lead Created → Response Sent → Marked as Processed

## Notes

- The system prioritizes reliability and idempotency over real-time performance
- All regex patterns should be tested using the Parser_Tester before production use
- The system is designed to run as a long-running background service
- Future enhancements may include a web UI for configuration management
