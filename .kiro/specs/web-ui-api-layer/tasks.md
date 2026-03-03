# Implementation Plan: Gmail Lead Sync Web UI & API Layer

## Overview

This implementation plan covers the development of a full-stack web application providing a management interface for the Gmail Lead Sync Engine. The system consists of a FastAPI backend (Python) and a React + TypeScript frontend (Vite), integrating with the existing CLI system while adding web-based administration capabilities.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create backend directory structure (`api/`, `api/models/`, `api/routes/`, `api/services/`)
  - Create frontend directory structure (`frontend/src/`, `frontend/src/components/`, `frontend/src/contexts/`, `frontend/src/pages/`)
  - Set up Python virtual environment and install FastAPI, SQLAlchemy, Pydantic, cryptography, prometheus-client
  - Initialize Vite React TypeScript project with Tailwind CSS, React Router, Axios, React Hook Form, Zod
  - Create `.env.example` files for backend and frontend configuration
  - _Requirements: 12.1, 12.2, 12.5_

- [ ] 2. Database schema extensions and migrations
  - [x] 2.1 Create Alembic migration for new tables
    - Create migration script for `users`, `sessions`, `audit_logs`, `template_versions`, `regex_profile_versions`, `settings` tables
    - Add indexes for performance optimization
    - Ensure backward compatibility with existing CLI tables
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 2.2 Create SQLAlchemy models for new tables
    - Implement `User`, `Session`, `AuditLog`, `TemplateVersion`, `RegexProfileVersion`, `Setting` models
    - Define relationships and foreign keys
    - _Requirements: 11.1, 11.2_
  
  - [x] 2.3 Write unit tests for database models
    - Test model creation, relationships, and constraints
    - Test migration rollback functionality
    - _Requirements: 24.4_

- [ ] 3. Authentication and session management
  - [x] 3.1 Implement authentication module
    - Create `api/auth.py` with login, logout, and session validation functions
    - Implement bcrypt password hashing for user credentials
    - Generate cryptographically secure session tokens (64 bytes)
    - Create authentication dependency for protected routes
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 26.1, 26.2_
  
  - [x] 3.2 Implement session management
    - Create session storage and retrieval functions
    - Implement 24-hour session expiration with sliding window
    - Create session cleanup background task for expired sessions
    - _Requirements: 26.3, 26.4, 26.5, 26.6, 26.7_
  
  - [x] 3.3 Write unit tests for authentication
    - Test login with valid and invalid credentials
    - Test session token generation and validation
    - Test session expiration handling
    - Test logout functionality
    - _Requirements: 24.1, 24.2_

- [ ] 4. Core API application setup
  - [x] 4.1 Create FastAPI application with middleware
    - Initialize FastAPI app in `api/main.py`
    - Configure CORS middleware with environment-based origins
    - Set up session cookie middleware
    - Configure structured JSON logging
    - Mount API routes under `/api/v1` prefix
    - _Requirements: 12.1, 12.2, 27.1, 27.2, 27.3, 27.4, 27.5_
  
  - [x] 4.2 Implement configuration management
    - Create configuration parser reading from environment variables
    - Validate required configuration on startup
    - Implement configuration validation command
    - Log configuration values on startup (excluding sensitive data)
    - _Requirements: 12.1, 12.5, 25.1, 25.2, 25.3, 25.4, 25.5_
  
  - [x] 4.3 Implement error handling and logging
    - Create global exception handler returning structured errors
    - Implement structured JSON logging for all operations
    - Ensure no sensitive information in error responses
    - Create error response models with error codes
    - _Requirements: 22.1, 22.2, 22.3, 22.4, 8.8_

- [ ] 5. Audit logging system
  - [x] 5.1 Implement audit log recording
    - Create `record_audit_log()` helper function
    - Implement append-only audit log storage
    - Record timestamp, user, action type, resource type, resource ID, and details
    - _Requirements: 7.3, 7.6_
  
  - [x] 5.2 Create audit log API endpoints
    - Implement `GET /api/v1/audit-logs` with pagination
    - Add filtering by action type, user_id, and date range
    - _Requirements: 7.1, 7.2, 7.4_
  
  - [x] 5.3 Write unit tests for audit logging
    - Test audit log recording for various actions
    - Test pagination and filtering
    - Test append-only constraint
    - _Requirements: 24.2_

- [ ] 6. Agent management API
  - [x] 6.1 Implement agent CRUD endpoints
    - Create `POST /api/v1/agents` for agent creation with credential encryption
    - Create `GET /api/v1/agents` for listing agents (exclude credentials)
    - Create `GET /api/v1/agents/{agent_id}` for agent details
    - Create `PUT /api/v1/agents/{agent_id}` for agent updates
    - Create `DELETE /api/v1/agents/{agent_id}` for agent deletion
    - Integrate with `EncryptedDBCredentialsStore` from existing CLI system
    - _Requirements: 1.1, 1.2, 1.3, 21.1, 21.3_
  
  - [x] 6.2 Implement agent deletion with watcher coordination
    - Stop running watcher when agent is deleted
    - Record audit log for agent deletion
    - _Requirements: 1.7, 1.8_
  
  - [x] 6.3 Implement input validation for agents
    - Validate email format against RFC 5322
    - Sanitize all user input
    - Enforce maximum length limits
    - _Requirements: 1.5, 10.1, 10.4, 10.5_
  
  - [x] 6.4 Write unit tests for agent endpoints
    - Test agent creation with credential encryption
    - Test agent listing excludes credentials
    - Test agent update and deletion
    - Test validation errors
    - _Requirements: 24.2_

- [ ] 7. Lead source management API
  - [x] 7.1 Implement lead source CRUD endpoints
    - Create `POST /api/v1/lead-sources` with regex validation
    - Create `GET /api/v1/lead-sources` for listing
    - Create `GET /api/v1/lead-sources/{id}` for details
    - Create `PUT /api/v1/lead-sources/{id}` for updates
    - Create `DELETE /api/v1/lead-sources/{id}` for deletion
    - _Requirements: 2.1, 2.2, 2.6_
  
  - [x] 7.2 Implement regex testing harness endpoint
    - Create `POST /api/v1/lead-sources/test-regex` endpoint
    - Implement 1000ms timeout using `signal.alarm()` (Unix) or `threading.Timer()` (Windows)
    - Return match results and captured groups
    - Validate regex syntax before execution
    - _Requirements: 2.3, 2.4, 14.1, 14.2, 14.3, 14.4_
  
  - [x] 7.3 Implement regex profile versioning
    - Create version records on lead source updates
    - Implement `GET /api/v1/lead-sources/{id}/versions` endpoint
    - Implement `POST /api/v1/lead-sources/{id}/rollback` endpoint
    - Record audit logs for version changes
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.7_
  
  - [x] 7.4 Write unit tests for lead source endpoints
    - Test regex validation and syntax checking
    - Test regex timeout enforcement
    - Test version history and rollback
    - _Requirements: 24.2_

- [ ] 8. Template management API
  - [x] 8.1 Implement template CRUD endpoints
    - Create `POST /api/v1/templates` with validation
    - Create `GET /api/v1/templates` for listing
    - Create `GET /api/v1/templates/{id}` for details
    - Create `PUT /api/v1/templates/{id}` for updates (creates new version)
    - Create `DELETE /api/v1/templates/{id}` for deletion
    - _Requirements: 3.1, 3.2_
  
  - [x] 8.2 Implement template validation
    - Validate against email header injection patterns (newlines in subject)
    - Validate placeholders: `{lead_name}`, `{agent_name}`, `{agent_phone}`, `{agent_email}`
    - Return validation errors for unsupported placeholders
    - _Requirements: 3.2, 3.4, 3.5, 10.2, 13.4, 13.5_
  
  - [x] 8.3 Implement template preview endpoint
    - Create `POST /api/v1/templates/preview` endpoint
    - Substitute placeholders with sample data
    - Escape HTML in body for display
    - _Requirements: 3.3, 10.7, 13.1, 13.2, 13.3_
  
  - [x] 8.4 Implement template versioning
    - Create version records on template updates
    - Implement `GET /api/v1/templates/{id}/versions` endpoint
    - Implement `POST /api/v1/templates/{id}/rollback` endpoint
    - Record audit logs for all template operations
    - _Requirements: 3.6, 3.7, 3.8_
  
  - [x] 8.5 Write unit tests for template endpoints
    - Test template validation (header injection, placeholders)
    - Test preview rendering
    - Test version history and rollback
    - _Requirements: 24.2, 24.6_

- [ ] 9. Watcher controller and background task management
  - [x] 9.1 Implement watcher registry
    - Create `WatcherRegistry` class managing background tasks
    - Implement watcher task lifecycle (start, stop, status)
    - Prevent multiple concurrent watchers for same agent
    - Track heartbeat and last sync timestamps
    - _Requirements: 4.2, 4.3, 4.4, 4.7, 20.1, 20.2_
  
  - [x] 9.2 Implement watcher control endpoints
    - Create `POST /api/v1/watchers/{agent_id}/start` endpoint
    - Create `POST /api/v1/watchers/{agent_id}/stop` endpoint
    - Create `POST /api/v1/watchers/{agent_id}/sync` for manual sync
    - Create `GET /api/v1/watchers/status` for all watcher statuses
    - Integrate with existing `GmailWatcher` from CLI system
    - _Requirements: 4.1, 4.5, 4.6, 21.1, 21.2_
  
  - [x] 9.3 Implement watcher auto-restart and error handling
    - Auto-restart failed watchers (max 3 retries)
    - Log all background task lifecycle events
    - Gracefully terminate all tasks on shutdown
    - Record watcher failures in error logs
    - _Requirements: 20.3, 20.4, 20.5, 8.7_
  
  - [x] 9.4 Write unit tests for watcher controller
    - Test watcher start, stop, and sync operations
    - Test concurrent watcher prevention
    - Test auto-restart functionality
    - Test graceful shutdown
    - _Requirements: 24.3_

- [ ] 10. Lead viewing and export API
  - [x] 10.1 Implement lead listing endpoint
    - Create `GET /api/v1/leads` with pagination
    - Implement filtering by agent_id, date range, processing status
    - Support sortable columns
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [x] 10.2 Implement lead detail endpoint
    - Create `GET /api/v1/leads/{id}` for full lead content and metadata
    - Display processing status and response status
    - _Requirements: 5.4, 5.7_
  
  - [x] 10.3 Implement CSV export endpoint
    - Create `GET /api/v1/leads/export` endpoint
    - Apply same filters as list endpoint
    - Include all requested fields with proper CSV escaping
    - Set appropriate headers for file download
    - _Requirements: 5.5, 5.6, 19.1, 19.2, 19.3, 19.4_
  
  - [x] 10.4 Write unit tests for lead endpoints
    - Test pagination and filtering
    - Test CSV export with various filters
    - Test CSV special character escaping
    - _Requirements: 24.2_

- [ ] 11. Health monitoring and metrics
  - [x] 11.1 Implement health check endpoint
    - Create `GET /api/v1/health` endpoint
    - Track database connection status
    - Track active watcher count and heartbeats
    - Track errors from last 24 hours
    - _Requirements: 8.1, 8.3, 8.4, 8.6_
  
  - [x] 11.2 Implement Prometheus metrics endpoint
    - Create `GET /metrics` endpoint in Prometheus text format
    - Track request count per endpoint
    - Track request duration per endpoint
    - Track active watcher count
    - Track lead processing rate
    - Track error rate per endpoint
    - _Requirements: 8.2, 29.1, 29.2, 29.3, 29.4, 29.5, 29.6, 29.7_
  
  - [x] 11.3 Write unit tests for health and metrics
    - Test health check response format
    - Test Prometheus metrics format
    - Test metric counters and histograms
    - _Requirements: 24.2_

- [ ] 12. Settings management API
  - [x] 12.1 Implement settings endpoints
    - Create `GET /api/v1/settings` for retrieving all settings
    - Create `PUT /api/v1/settings` for updating settings
    - Support settings: `sync_interval_seconds`, `regex_timeout_ms`, `session_timeout_hours`, `max_leads_per_page`, `enable_auto_restart`
    - Validate setting values before storage
    - Record audit logs for settings modifications
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_
  
  - [x] 12.2 Write unit tests for settings endpoints
    - Test settings retrieval and updates
    - Test validation of setting values
    - _Requirements: 24.2_

- [ ] 13. Static file serving and production setup
  - [x] 13.1 Configure static file serving
    - Mount frontend static files from configurable directory
    - Serve `index.html` for all non-API routes (client-side routing)
    - Set appropriate cache headers for static assets
    - Ensure API routes under `/api/v1` prefix take precedence
    - _Requirements: 12.6, 28.1, 28.2, 28.3, 28.4_
  
  - [x] 13.2 Create seed data script
    - Create script to generate demo agents with encrypted credentials
    - Generate sample lead sources, templates, and leads
    - Make script idempotent and safe to run multiple times
    - Provide flag to clear existing data before seeding
    - _Requirements: 12.4, 30.1, 30.2, 30.3, 30.4, 30.5, 30.6, 30.7_

- [x] 14. Checkpoint - Backend API complete
  - Ensure all backend tests pass, verify API endpoints with manual testing or Postman, ask the user if questions arise.

- [x] 15. Frontend authentication and routing
  - [x] 15.1 Create authentication context
    - Implement `AuthProvider` in `src/contexts/AuthContext.tsx`
    - Manage authentication state (user, loading, error)
    - Provide login and logout functions
    - Handle session persistence and redirects on auth errors
    - _Requirements: 6.6, 23.3_
  
  - [x] 15.2 Create routing structure
    - Set up React Router with protected routes
    - Create `LoginPage` component
    - Create `DashboardLayout` with sidebar and header
    - Create route guards for authenticated routes
    - _Requirements: 6.6_
  
  - [x] 15.3 Write tests for authentication flow
    - Test login success and failure
    - Test logout functionality
    - Test protected route redirects
    - _Requirements: 23.3_

- [x] 16. Frontend dashboard and health monitoring
  - [x] 16.1 Create dashboard page
    - Implement `DashboardPage` component
    - Create `HealthMetrics` component displaying system health
    - Create `WatcherStatusGrid` component with real-time status
    - Create `RecentErrorsTable` component for last 24 hours
    - Poll health endpoint every 5 seconds
    - _Requirements: 8.5, 8.6, 16.1, 16.2, 16.3_
  
  - [x] 16.2 Write unit tests for dashboard components
    - Test health metrics display
    - Test watcher status updates
    - _Requirements: 23.4_

- [ ] 17. Frontend agent management
  - [x] 17.1 Create agent list page
    - Implement `AgentsPage` component
    - Create `AgentList` component displaying all agents with status
    - Display watcher status indicators
    - Add create, edit, delete actions
    - _Requirements: 1.4, 1.6_
  
  - [-] 17.2 Create agent form
    - Implement `AgentForm` component for create/edit
    - Validate email format and required fields
    - Show validation errors
    - _Requirements: 1.5_
  
  - [~] 17.3 Create agent detail view
    - Implement `AgentDetail` component
    - Display agent configuration and watcher status
    - Add watcher control buttons (start, stop, sync)
    - _Requirements: 1.6_
  
  - [~] 17.4 Implement dangerous action confirmations
    - Create `ConfirmDialog` component
    - Show confirmation for agent deletion
    - Display agent name in confirmation dialog
    - _Requirements: 15.1, 15.5, 15.6_
  
  - [~] 17.5 Write unit tests for agent components
    - Test agent list rendering
    - Test form validation
    - Test confirmation dialogs
    - _Requirements: 23.4, 23.5_

- [ ] 18. Frontend lead source management
  - [~] 18.1 Create lead source list page
    - Implement `LeadSourcesPage` component
    - Create `LeadSourceList` component
    - Add create, edit, delete actions
    - _Requirements: 2.1_
  
  - [~] 18.2 Create lead source form
    - Implement `LeadSourceForm` component
    - Validate regex patterns
    - Display validation errors
    - _Requirements: 2.2, 2.5_
  
  - [~] 18.3 Create regex testing harness
    - Implement `RegexTestHarness` component
    - Add input fields for pattern and sample text
    - Display match results with highlighting
    - Display captured groups
    - Show timeout errors
    - _Requirements: 2.3, 2.4, 14.5, 14.6, 14.7_
  
  - [~] 18.4 Implement version history UI
    - Display version history for regex profiles
    - Add rollback action with confirmation
    - _Requirements: 9.5, 9.6_
  
  - [~] 18.5 Implement dangerous action confirmations
    - Show confirmation for lead source deletion
    - _Requirements: 15.2, 15.5, 15.6_
  
  - [~] 18.6 Write unit tests for lead source components
    - Test regex testing harness
    - Test form validation
    - Test version history display
    - _Requirements: 23.1, 23.2, 23.4, 23.5_

- [ ] 19. Frontend template management
  - [~] 19.1 Create template list page
    - Implement `TemplatesPage` component
    - Create `TemplateList` component
    - Add create, edit, delete actions
    - _Requirements: 3.1_
  
  - [~] 19.2 Create template editor
    - Implement `TemplateEditor` component
    - Add subject and body input fields
    - Add placeholder insertion buttons
    - Display available placeholders
    - Show validation errors
    - _Requirements: 3.3, 3.5_
  
  - [~] 19.3 Create template preview
    - Implement `TemplatePreview` component
    - Display rendered template with sample data
    - Update preview in real-time as user edits
    - _Requirements: 3.3, 13.3_
  
  - [~] 19.4 Implement version history UI
    - Create `VersionHistory` sidebar component
    - Display template version history
    - Add rollback action with confirmation
    - _Requirements: 3.6, 3.7_
  
  - [~] 19.5 Implement dangerous action confirmations
    - Show confirmation for template deletion
    - _Requirements: 15.3, 15.5, 15.6_
  
  - [~] 19.6 Write unit tests for template components
    - Test template editor
    - Test preview rendering
    - Test version history
    - _Requirements: 23.1, 23.4, 23.5_

- [ ] 20. Frontend watcher control
  - [~] 20.1 Create watcher status display
    - Implement real-time watcher status indicators
    - Display last sync timestamp
    - Poll watcher status every 5 seconds
    - Update display within 5 seconds of status change
    - _Requirements: 4.6, 4.7, 16.2, 16.3, 16.4, 16.5_
  
  - [~] 20.2 Implement watcher control actions
    - Add start, stop, sync buttons
    - Show confirmation for watcher stop
    - _Requirements: 4.1, 15.4, 15.5, 15.6_
  
  - [~] 20.3 Write unit tests for watcher components
    - Test status polling
    - Test control actions
    - _Requirements: 23.4_

- [ ] 21. Frontend lead viewing and export
  - [~] 21.1 Create leads page
    - Implement `LeadsPage` component
    - Create `LeadTable` component with sortable columns
    - Add pagination controls
    - Display processing status and response status
    - _Requirements: 5.3, 5.7_
  
  - [~] 21.2 Create lead filters
    - Implement `LeadFilters` component
    - Add filters for agent, date range, processing status
    - _Requirements: 5.2_
  
  - [~] 21.3 Create lead detail view
    - Implement `LeadDetail` component
    - Display full lead content and metadata
    - _Requirements: 5.4_
  
  - [~] 21.4 Implement CSV export
    - Add export button to leads page
    - Trigger browser download on export
    - Apply current filters to export
    - Show success toast on export
    - _Requirements: 5.5, 5.6, 19.5, 19.6_
  
  - [~] 21.5 Write unit tests for lead components
    - Test table rendering and sorting
    - Test filtering
    - Test CSV export trigger
    - _Requirements: 23.4_

- [ ] 22. Frontend audit logs and settings
  - [~] 22.1 Create audit logs page
    - Implement `AuditLogsPage` component
    - Create `AuditLogTable` component with filterable columns
    - Create `AuditLogFilters` for action type, user, date range
    - Add pagination controls
    - _Requirements: 7.1, 7.2, 7.4_
  
  - [~] 22.2 Create settings page
    - Implement `SettingsPage` component
    - Create `SettingsForm` component
    - Display all configurable settings
    - Validate setting values before submission
    - _Requirements: 18.1, 18.2, 18.3_
  
  - [~] 22.3 Write unit tests for audit and settings components
    - Test audit log filtering
    - Test settings form validation
    - _Requirements: 23.4, 23.5_

- [ ] 23. Frontend toast notifications and error handling
  - [x] 23.1 Create toast notification system
    - Implement `ToastContainer` component
    - Show success toasts for successful operations (auto-dismiss after 3 seconds)
    - Show error toasts for failed operations (manual dismissal)
    - Display error messages from API responses
    - Position toasts consistently
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_
  
  - [~] 23.2 Implement user-friendly error handling
    - Display user-friendly error messages for common scenarios
    - Provide link to detailed error logs for administrators
    - _Requirements: 22.5, 22.6_
  
  - [~] 23.3 Write unit tests for toast notifications
    - Test toast display and dismissal
    - Test error message formatting
    - _Requirements: 23.4_

- [ ] 24. Checkpoint - Frontend UI complete
  - Ensure all frontend tests pass, verify UI functionality in browser, ask the user if questions arise.

- [ ] 25. Docker deployment configuration
  - [~] 25.1 Create backend Dockerfile
    - Create multi-stage Dockerfile for FastAPI application
    - Install Python dependencies
    - Copy application code
    - Set up entry point for running migrations and starting server
    - _Requirements: 12.2, 12.3_
  
  - [~] 25.2 Create frontend build configuration
    - Configure Vite for production build
    - Set API base URL from environment variable
    - Build static assets for production
    - _Requirements: 28.5_
  
  - [~] 25.3 Create docker-compose configuration
    - Define service for FastAPI backend
    - Mount volume for SQLite database persistence
    - Mount volume for frontend static files
    - Configure environment variables
    - Expose port 8000
    - _Requirements: 12.2, 12.3, 12.5_
  
  - [~] 25.4 Create systemd service file
    - Create service file for production deployment
    - Configure auto-restart on failure
    - Set up logging
    - _Requirements: 12.7_

- [ ] 26. Integration testing and documentation
  - [~] 26.1 Write integration tests
    - Test authentication flow end-to-end
    - Test agent creation and watcher lifecycle
    - Test lead source regex testing
    - Test template preview and versioning
    - Test CSV export functionality
    - _Requirements: 23.3, 24.4_
  
  - [~] 26.2 Create deployment documentation
    - Document environment variable configuration
    - Document Docker deployment steps
    - Document systemd service setup
    - Document database migration process
    - Document seed data generation
    - _Requirements: 12.1, 12.2, 12.4_
  
  - [~] 26.3 Create API documentation
    - Generate OpenAPI/Swagger documentation from FastAPI
    - Document all endpoints with request/response examples
    - Document authentication requirements
    - _Requirements: 22.1_

- [ ] 27. Final checkpoint - Complete system integration
  - Run full integration tests, verify Docker deployment works, test with seed data, ensure backward compatibility with CLI system, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- The implementation reuses existing CLI modules (`gmail_lead_sync.watcher`, `gmail_lead_sync.parser`, `gmail_lead_sync.credentials`) for seamless integration
- Backend uses Python with FastAPI, frontend uses TypeScript with React and Vite
- All security features from the existing system are preserved (credential encryption, input sanitization)
- The system maintains backward compatibility with the existing CLI application
