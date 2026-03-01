# Requirements Document

## Introduction

This document specifies requirements for the Gmail Lead Sync Web UI & API Layer, a full-stack web application that provides a management interface for the existing Gmail Lead Sync Engine CLI system. The system enables administrators to manage Gmail agents, lead sources, templates, and monitoring through a web-based dashboard with a REST API backend.

## Glossary

- **Web_UI**: The React-based frontend application providing the administrative dashboard
- **API_Layer**: The FastAPI-based REST API backend service
- **Agent**: A Gmail account configuration with encrypted credentials used for email monitoring
- **Lead_Source**: A configuration defining regex patterns to identify lead emails
- **Template**: An email response template with placeholders for dynamic content
- **Watcher**: A background process monitoring a specific Agent's Gmail inbox
- **Regex_Profile**: A versioned collection of regex patterns for lead identification
- **Audit_Log**: A timestamped record of system actions and changes
- **Health_Monitor**: A component tracking system health metrics and watcher status
- **Admin_User**: An authenticated user with administrative privileges
- **Lead**: An identified email matching Lead_Source criteria
- **Sync_Operation**: A manual or scheduled operation to check for new leads

## Requirements

### Requirement 1: Agent Management

**User Story:** As an administrator, I want to manage Gmail agent configurations, so that I can control which accounts monitor for leads

#### Acceptance Criteria

1. THE API_Layer SHALL provide endpoints for creating, reading, updating, and deleting Agent records
2. WHEN an Agent is created, THE API_Layer SHALL encrypt credentials before storage
3. WHEN an Agent is retrieved via API, THE API_Layer SHALL exclude decrypted credentials from the response
4. THE Web_UI SHALL display a list of all configured Agents with status indicators
5. WHEN an administrator creates an Agent, THE Web_UI SHALL validate email format and required fields
6. THE Web_UI SHALL provide a detail view showing Agent configuration and associated Watcher status
7. WHEN an Agent is deleted, THE API_Layer SHALL stop any running Watcher for that Agent
8. THE Audit_Log SHALL record all Agent creation, modification, and deletion operations

### Requirement 2: Lead Source Management

**User Story:** As an administrator, I want to manage lead source configurations, so that I can define which emails qualify as leads

#### Acceptance Criteria

1. THE API_Layer SHALL provide endpoints for creating, reading, updating, and deleting Lead_Source records
2. WHEN a Lead_Source is created, THE API_Layer SHALL validate regex pattern syntax
3. THE Web_UI SHALL provide a regex testing harness for validating patterns against sample emails
4. WHEN a regex pattern is tested, THE API_Layer SHALL enforce a timeout of 1000 milliseconds
5. THE Web_UI SHALL display validation errors for invalid regex patterns
6. THE API_Layer SHALL sanitize all user input in Lead_Source configurations
7. THE Audit_Log SHALL record all Lead_Source creation, modification, and deletion operations

### Requirement 3: Template Management

**User Story:** As an administrator, I want to manage email response templates, so that I can customize automated responses to leads

#### Acceptance Criteria

1. THE API_Layer SHALL provide endpoints for creating, reading, updating, and deleting Template records
2. WHEN a Template is created, THE API_Layer SHALL validate against email header injection patterns
3. THE Web_UI SHALL provide a template preview feature with sample placeholder data
4. THE API_Layer SHALL validate that all placeholders in templates are supported
5. THE Web_UI SHALL display available placeholders for template creation
6. THE API_Layer SHALL maintain version history for Template modifications
7. WHEN a Template version is requested, THE API_Layer SHALL support rollback to previous versions
8. THE Audit_Log SHALL record all Template creation, modification, deletion, and rollback operations

### Requirement 4: Watcher Control

**User Story:** As an administrator, I want to control watcher processes, so that I can start, stop, and manually sync agents

#### Acceptance Criteria

1. THE API_Layer SHALL provide endpoints for starting, stopping, and triggering sync operations per Agent
2. WHEN a Watcher is started, THE API_Layer SHALL create a background task for that Agent
3. WHEN a Watcher is stopped, THE API_Layer SHALL gracefully terminate the background task
4. THE API_Layer SHALL prevent multiple concurrent Watchers for the same Agent
5. WHEN a manual sync is triggered, THE API_Layer SHALL execute a single sync operation for the Agent
6. THE Web_UI SHALL display real-time Watcher status for each Agent
7. THE Health_Monitor SHALL track Watcher heartbeats and last sync timestamps
8. THE Audit_Log SHALL record all Watcher start, stop, and sync operations

### Requirement 5: Lead Viewing and Filtering

**User Story:** As an administrator, I want to view and filter leads, so that I can review identified emails and their processing status

#### Acceptance Criteria

1. THE API_Layer SHALL provide endpoints for retrieving Lead records with pagination
2. THE API_Layer SHALL support filtering Leads by Agent, date range, and processing status
3. THE Web_UI SHALL display a table of Leads with sortable columns
4. THE Web_UI SHALL provide a detail view showing full Lead content and metadata
5. THE API_Layer SHALL provide an endpoint for exporting Leads to CSV format
6. WHEN Leads are exported, THE API_Layer SHALL include all requested fields in the CSV
7. THE Web_UI SHALL display processing status and response status for each Lead

### Requirement 6: Authentication and Authorization

**User Story:** As a system owner, I want secure authentication, so that only authorized users can access the management interface

#### Acceptance Criteria

1. THE API_Layer SHALL require authentication for all management endpoints
2. WHEN an Admin_User logs in with valid credentials, THE API_Layer SHALL issue a session token
3. WHEN an Admin_User logs in with invalid credentials, THE API_Layer SHALL return an authentication error
4. THE API_Layer SHALL validate session tokens on all protected endpoints
5. THE API_Layer SHALL use secure HTTP-only cookies for session management
6. THE Web_UI SHALL redirect unauthenticated users to the login page
7. THE API_Layer SHALL support role-based access control structure for future multi-tenant expansion
8. WHEN a session expires, THE API_Layer SHALL return an authentication error

### Requirement 7: Audit Logging

**User Story:** As an administrator, I want to view audit logs, so that I can track all system changes and operations

#### Acceptance Criteria

1. THE API_Layer SHALL provide endpoints for retrieving Audit_Log records with pagination
2. THE API_Layer SHALL support filtering Audit_Log by action type, user, and date range
3. THE Audit_Log SHALL record timestamp, user, action type, and affected resource for each entry
4. THE Web_UI SHALL display audit logs in a filterable table
5. THE API_Layer SHALL log all authentication attempts in the Audit_Log
6. THE Audit_Log SHALL be append-only with no deletion capability

### Requirement 8: Health Monitoring and Metrics

**User Story:** As an administrator, I want to monitor system health, so that I can identify issues and track performance

#### Acceptance Criteria

1. THE API_Layer SHALL provide a health check endpoint returning system status
2. THE API_Layer SHALL provide a metrics endpoint in Prometheus format
3. THE Health_Monitor SHALL track active Watcher count and last heartbeat per Watcher
4. THE Health_Monitor SHALL track database connection status
5. THE Web_UI SHALL display a dashboard with system health metrics
6. THE Web_UI SHALL display error logs from the last 24 hours
7. WHEN a Watcher fails, THE Health_Monitor SHALL record the failure in error logs
8. THE API_Layer SHALL emit structured JSON logs for all operations

### Requirement 9: Regex Profile Versioning

**User Story:** As an administrator, I want versioned regex profiles, so that I can safely update patterns and rollback if needed

#### Acceptance Criteria

1. THE API_Layer SHALL maintain version history for Regex_Profile modifications
2. WHEN a Regex_Profile is updated, THE API_Layer SHALL create a new version record
3. THE API_Layer SHALL provide an endpoint for retrieving Regex_Profile version history
4. WHEN a Regex_Profile rollback is requested, THE API_Layer SHALL restore the specified version
5. THE Web_UI SHALL display version history for each Regex_Profile
6. THE Web_UI SHALL provide a rollback action with confirmation dialog
7. THE Audit_Log SHALL record all Regex_Profile version changes and rollbacks

### Requirement 10: Input Sanitization and Validation

**User Story:** As a system owner, I want comprehensive input validation, so that the system is protected from malicious input

#### Acceptance Criteria

1. THE API_Layer SHALL sanitize all user input before processing
2. WHEN a Template is submitted, THE API_Layer SHALL validate against email header injection patterns
3. WHEN a regex pattern is submitted, THE API_Layer SHALL validate syntax before storage
4. THE API_Layer SHALL enforce maximum length limits on all text fields
5. THE API_Layer SHALL validate email addresses against RFC 5322 format
6. WHEN invalid input is detected, THE API_Layer SHALL return descriptive validation errors
7. THE API_Layer SHALL escape HTML content in all user-generated text displayed in Web_UI

### Requirement 11: Database Schema Extensions

**User Story:** As a developer, I want database migrations for new tables, so that the web layer integrates with existing storage

#### Acceptance Criteria

1. THE API_Layer SHALL extend the existing SQLite schema with tables for sessions and audit logs
2. THE API_Layer SHALL use the existing Agent, Lead_Source, Template, and Lead tables
3. THE API_Layer SHALL provide migration scripts for schema updates
4. THE API_Layer SHALL maintain backward compatibility with existing CLI system
5. WHEN migrations are applied, THE API_Layer SHALL record migration version in the database

### Requirement 12: Deployment and Configuration

**User Story:** As a system administrator, I want simple deployment, so that I can run the system with minimal configuration

#### Acceptance Criteria

1. THE API_Layer SHALL read configuration from environment variables
2. THE system SHALL provide a docker-compose configuration for single-command deployment
3. THE docker-compose configuration SHALL include both API_Layer and Web_UI services
4. THE system SHALL provide a seed script for generating demo data
5. THE API_Layer SHALL expose configurable port via environment variable
6. THE Web_UI SHALL be served as static files from the API_Layer in production mode
7. THE system SHALL provide a systemd service file for production deployment

### Requirement 13: Template Preview and Validation

**User Story:** As an administrator, I want to preview templates with sample data, so that I can verify formatting before deployment

#### Acceptance Criteria

1. THE API_Layer SHALL provide an endpoint for rendering Template preview with sample data
2. WHEN a Template preview is requested, THE API_Layer SHALL substitute all placeholders with sample values
3. THE Web_UI SHALL display rendered Template preview in the template editor
4. THE API_Layer SHALL validate that Template placeholders match supported fields
5. WHEN unsupported placeholders are detected, THE API_Layer SHALL return validation errors listing invalid placeholders

### Requirement 14: Regex Testing Harness

**User Story:** As an administrator, I want to test regex patterns against sample emails, so that I can verify patterns before deployment

#### Acceptance Criteria

1. THE API_Layer SHALL provide an endpoint for testing regex patterns against sample text
2. WHEN a regex test is executed, THE API_Layer SHALL return match results and captured groups
3. THE API_Layer SHALL enforce a timeout of 1000 milliseconds for regex execution
4. IF a regex execution exceeds timeout, THEN THE API_Layer SHALL return a timeout error
5. THE Web_UI SHALL provide a testing interface with sample email input and pattern input
6. THE Web_UI SHALL display match results with highlighted matching text
7. THE Web_UI SHALL display captured groups from regex matches

### Requirement 15: Dangerous Action Confirmations

**User Story:** As an administrator, I want confirmation dialogs for dangerous actions, so that I can prevent accidental data loss

#### Acceptance Criteria

1. WHEN an Agent deletion is initiated, THE Web_UI SHALL display a confirmation dialog
2. WHEN a Lead_Source deletion is initiated, THE Web_UI SHALL display a confirmation dialog
3. WHEN a Template deletion is initiated, THE Web_UI SHALL display a confirmation dialog
4. WHEN a Watcher stop is initiated, THE Web_UI SHALL display a confirmation dialog
5. THE Web_UI SHALL require explicit confirmation before executing dangerous actions
6. THE confirmation dialog SHALL display the name of the resource being affected

### Requirement 16: Real-Time Status Updates

**User Story:** As an administrator, I want real-time watcher status, so that I can monitor operations without manual refresh

#### Acceptance Criteria

1. THE API_Layer SHALL provide an endpoint for retrieving current Watcher status for all Agents
2. THE Web_UI SHALL poll Watcher status at 5-second intervals
3. THE Web_UI SHALL display Watcher status indicators with visual state changes
4. THE Web_UI SHALL display last sync timestamp for each Watcher
5. WHEN a Watcher status changes, THE Web_UI SHALL update the display within 5 seconds

### Requirement 17: Toast Notifications

**User Story:** As an administrator, I want notification feedback, so that I know when operations succeed or fail

#### Acceptance Criteria

1. WHEN an API operation succeeds, THE Web_UI SHALL display a success toast notification
2. WHEN an API operation fails, THE Web_UI SHALL display an error toast notification with error message
3. THE Web_UI SHALL automatically dismiss success notifications after 3 seconds
4. THE Web_UI SHALL require manual dismissal for error notifications
5. THE Web_UI SHALL display toast notifications in a consistent location

### Requirement 18: Settings Management

**User Story:** As an administrator, I want to configure system settings, so that I can customize behavior and preferences

#### Acceptance Criteria

1. THE API_Layer SHALL provide endpoints for reading and updating system settings
2. THE Web_UI SHALL provide a settings page for configuration management
3. THE API_Layer SHALL validate setting values before storage
4. THE Audit_Log SHALL record all settings modifications
5. THE API_Layer SHALL support settings for sync interval, timeout values, and notification preferences

### Requirement 19: CSV Export Functionality

**User Story:** As an administrator, I want to export leads to CSV, so that I can analyze data in external tools

#### Acceptance Criteria

1. THE API_Layer SHALL provide an endpoint for exporting Lead records to CSV format
2. WHEN a CSV export is requested, THE API_Layer SHALL apply the same filters as the current Lead view
3. THE API_Layer SHALL include headers in the CSV export
4. THE API_Layer SHALL properly escape CSV special characters in exported data
5. THE Web_UI SHALL provide an export button on the Leads page
6. WHEN export is triggered, THE Web_UI SHALL download the CSV file to the user's browser

### Requirement 20: Background Task Management

**User Story:** As a system owner, I want reliable background task management, so that watchers run continuously without blocking API requests

#### Acceptance Criteria

1. THE API_Layer SHALL use asynchronous background tasks for Watcher processes
2. THE API_Layer SHALL maintain a registry of active background tasks
3. WHEN the API_Layer shuts down, THE API_Layer SHALL gracefully terminate all background tasks
4. THE API_Layer SHALL restart failed Watcher tasks automatically
5. THE API_Layer SHALL log all background task lifecycle events
6. THE Health_Monitor SHALL track background task health status

### Requirement 21: Integration with Existing System

**User Story:** As a developer, I want seamless integration with the existing CLI system, so that both interfaces can coexist

#### Acceptance Criteria

1. THE API_Layer SHALL use the existing gmail_lead_sync Python modules for core functionality
2. THE API_Layer SHALL maintain idempotent processing guarantees from the existing system
3. THE API_Layer SHALL preserve all existing security features for credential encryption
4. THE API_Layer SHALL use the same database schema as the CLI system for shared tables
5. THE API_Layer SHALL not interfere with CLI operations when both are running

### Requirement 22: Error Handling and Logging

**User Story:** As a developer, I want comprehensive error handling, so that I can diagnose and resolve issues quickly

#### Acceptance Criteria

1. THE API_Layer SHALL return structured error responses with error codes and messages
2. THE API_Layer SHALL log all errors with stack traces in structured JSON format
3. WHEN an unhandled exception occurs, THE API_Layer SHALL return a 500 error with generic message
4. THE API_Layer SHALL not expose sensitive information in error responses
5. THE Web_UI SHALL display user-friendly error messages for common error scenarios
6. THE Web_UI SHALL provide a link to view detailed error logs for administrators

### Requirement 23: Frontend Testing Requirements

**User Story:** As a developer, I want frontend tests, so that I can ensure UI components work correctly

#### Acceptance Criteria

1. THE Web_UI SHALL include unit tests for the template editor component
2. THE Web_UI SHALL include unit tests for the regex testing harness component
3. THE Web_UI SHALL include integration tests for authentication flow
4. THE Web_UI SHALL achieve minimum 70% code coverage for critical components
5. THE Web_UI SHALL include tests for form validation logic

### Requirement 24: Backend Testing Requirements

**User Story:** As a developer, I want backend tests, so that I can ensure API endpoints work correctly

#### Acceptance Criteria

1. THE API_Layer SHALL include unit tests for authentication logic
2. THE API_Layer SHALL include unit tests for all API endpoints
3. THE API_Layer SHALL include unit tests for Watcher control logic
4. THE API_Layer SHALL include integration tests for database operations
5. THE API_Layer SHALL achieve minimum 80% code coverage for core modules
6. THE API_Layer SHALL include tests for input sanitization functions

### Requirement 25: Configuration Parser and Validator

**User Story:** As a system administrator, I want configuration validation, so that I can detect configuration errors before deployment

#### Acceptance Criteria

1. THE API_Layer SHALL parse configuration from environment variables on startup
2. WHEN required configuration is missing, THE API_Layer SHALL fail to start with descriptive error
3. THE API_Layer SHALL validate configuration value formats on startup
4. THE API_Layer SHALL provide a configuration validation command for pre-deployment checks
5. THE API_Layer SHALL log all configuration values on startup excluding sensitive values

### Requirement 26: Session Management

**User Story:** As an administrator, I want secure session management, so that my authentication persists across requests

#### Acceptance Criteria

1. THE API_Layer SHALL create sessions with cryptographically secure random identifiers
2. THE API_Layer SHALL store session data in the database
3. THE API_Layer SHALL set session expiration to 24 hours from creation
4. WHEN a session expires, THE API_Layer SHALL require re-authentication
5. THE API_Layer SHALL provide an endpoint for session logout
6. WHEN logout is requested, THE API_Layer SHALL invalidate the session
7. THE API_Layer SHALL use HTTP-only secure cookies for session tokens

### Requirement 27: CORS Configuration

**User Story:** As a developer, I want configurable CORS settings, so that the frontend can communicate with the API in development and production

#### Acceptance Criteria

1. THE API_Layer SHALL support CORS configuration via environment variables
2. THE API_Layer SHALL allow configurable allowed origins for CORS
3. THE API_Layer SHALL include credentials in CORS responses when configured
4. THE API_Layer SHALL restrict CORS origins in production mode
5. THE API_Layer SHALL allow all origins in development mode when configured

### Requirement 28: Static File Serving

**User Story:** As a system administrator, I want the API to serve frontend files, so that I can deploy a single service

#### Acceptance Criteria

1. THE API_Layer SHALL serve Web_UI static files from a configurable directory
2. THE API_Layer SHALL serve index.html for all non-API routes to support client-side routing
3. THE API_Layer SHALL set appropriate cache headers for static assets
4. THE API_Layer SHALL serve API routes under a dedicated path prefix
5. THE Web_UI SHALL be built as static files for production deployment

### Requirement 29: Metrics Collection

**User Story:** As a system administrator, I want Prometheus metrics, so that I can monitor system performance

#### Acceptance Criteria

1. THE API_Layer SHALL expose a metrics endpoint at /metrics
2. THE API_Layer SHALL track request count per endpoint
3. THE API_Layer SHALL track request duration per endpoint
4. THE API_Layer SHALL track active Watcher count
5. THE API_Layer SHALL track Lead processing rate
6. THE API_Layer SHALL track error rate per endpoint
7. THE metrics endpoint SHALL return data in Prometheus text format

### Requirement 30: Development Seed Data

**User Story:** As a developer, I want seed data generation, so that I can test the system with realistic data

#### Acceptance Criteria

1. THE system SHALL provide a seed script for generating demo data
2. WHEN the seed script is executed, THE system SHALL create sample Agents with encrypted credentials
3. WHEN the seed script is executed, THE system SHALL create sample Lead_Source configurations
4. WHEN the seed script is executed, THE system SHALL create sample Templates
5. WHEN the seed script is executed, THE system SHALL create sample Lead records
6. THE seed script SHALL be idempotent and safe to run multiple times
7. THE seed script SHALL provide a flag to clear existing data before seeding
