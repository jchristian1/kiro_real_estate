# Gmail Lead Sync & Response Engine

A lead management system for Real Estate agents that monitors Gmail accounts via IMAP, extracts lead information using configurable parsing rules, stores leads in a local database, and sends automated acknowledgment emails via SMTP.

## Features

- **Zero-Cost Operation**: Uses IMAP/SMTP protocols instead of paid Google APIs
- **Idempotent Processing**: Each email is processed exactly once using Gmail UID tracking
- **Configurable Parsing**: Database-driven regex patterns for different lead sources
- **Automated Responses**: Send customizable acknowledgment emails to new leads
- **Secure Credentials**: AES-256 encrypted storage of Gmail credentials
- **Comprehensive Audit Trail**: Complete processing logs for debugging and verification
- **Resilient Design**: Exponential backoff retry logic and graceful error handling

## Requirements

- Python 3.10 or higher
- Gmail account with App Password enabled (requires 2FA)
- SQLite (included with Python)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd gmail-lead-sync
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install the package in development mode:
```bash
pip install -e .
```

## Configuration

### Environment Variables

The system requires the following environment variables:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `ENCRYPTION_KEY` | Yes | 32-byte base64-encoded key for credential encryption | `gAAAAABh...` |
| `GMAIL_EMAIL` | Optional | Gmail account email (alternative to DB storage) | `agent@gmail.com` |
| `GMAIL_APP_PASSWORD` | Optional | Gmail app password (alternative to DB storage) | `abcd efgh ijkl mnop` |
| `DATABASE_URL` | Optional | SQLite database path | `sqlite:///gmail_lead_sync.db` |
| `LOG_LEVEL` | Optional | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

**Setting Environment Variables:**

On Linux/Mac:
```bash
export ENCRYPTION_KEY="your-generated-key-here"
export GMAIL_EMAIL="your-email@gmail.com"
export GMAIL_APP_PASSWORD="your-app-password"
```

On Windows:
```cmd
set ENCRYPTION_KEY=your-generated-key-here
set GMAIL_EMAIL=your-email@gmail.com
set GMAIL_APP_PASSWORD=your-app-password
```

For persistent configuration, add these to your shell profile (`~/.bashrc`, `~/.zshrc`) or create a `.env` file.

### Gmail App Password Setup

**Step-by-Step Instructions:**

1. **Enable 2-Factor Authentication:**
   - Go to https://myaccount.google.com/security
   - Under "Signing in to Google", select "2-Step Verification"
   - Follow the prompts to enable 2FA

2. **Generate App Password:**
   - Visit https://myaccount.google.com/apppasswords
   - Select "Mail" as the app and "Other" as the device
   - Enter "Gmail Lead Sync" as the custom name
   - Click "Generate"
   - Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)

3. **Store Securely:**
   - Save the app password in your environment variables or password manager
   - Never commit the app password to version control
   - The app password can only be viewed once during generation

**Important Notes:**
- App passwords bypass 2FA, so keep them secure
- You can revoke app passwords at any time from the same page
- If you change your Google account password, app passwords remain valid
- IMAP must be enabled in Gmail settings (Settings → Forwarding and POP/IMAP)

### Encryption Key Generation

Generate a secure encryption key for credential storage:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

This generates a 32-byte base64-encoded key suitable for AES-256 encryption.

**Example output:**
```
gAAAAABhkN8vQ7X2Z9J4K5L6M7N8O9P0Q1R2S3T4U5V6W7X8Y9Z0A1B2C3D4E5F6=
```

Set the encryption key as an environment variable:

```bash
export ENCRYPTION_KEY="gAAAAABhkN8vQ7X2Z9J4K5L6M7N8O9P0Q1R2S3T4U5V6W7X8Y9Z0A1B2C3D4E5F6="
```

**Security Best Practices:**
- Generate a unique key for each environment (dev, staging, production)
- Store the key securely (password manager, secrets management system)
- Never commit the key to version control
- Rotate keys periodically (requires re-encryption of stored credentials)
- Backup the key securely before rotating

### Database Initialization

Initialize the database with Alembic migrations:

```bash
alembic upgrade head
```

This creates the following tables:
- `leads`: Stores extracted lead information
- `lead_sources`: Configurable parsing rules for different email senders
- `templates`: Email response templates
- `processing_logs`: Audit trail of all email processing attempts
- `credentials`: Encrypted Gmail credentials (if using DB storage)

## Usage

### Starting the Watcher

Start the background email monitoring service:

```bash
gmail-lead-sync start
```

The watcher will:
- Connect to Gmail via IMAP
- Monitor for new UNSEEN emails from configured senders
- Extract lead information using regex patterns
- Store leads in the database
- Send automated responses (if configured)
- Run continuously until stopped (Ctrl+C)

**Options:**
```bash
gmail-lead-sync start --log-level DEBUG  # Enable debug logging
```

### Managing Lead Sources

Lead sources define how to identify and parse emails from specific senders.

**Add a new lead source:**
```bash
gmail-lead-sync add-source \
    --sender "leads@example.com" \
    --identifier "New Lead Notification" \
    --name-regex "Name:\s*(.+)" \
    --phone-regex "Phone:\s*([\d\-]+)" \
    --template-id 1
```

**Parameters:**
- `--sender`: Email address to monitor (must be valid email format)
- `--identifier`: Text snippet that must appear in email body
- `--name-regex`: Regex pattern to extract lead name (must have capture group)
- `--phone-regex`: Regex pattern to extract phone number (must have capture group)
- `--template-id`: (Optional) Template ID for automated responses

**Example patterns:**
```bash
# Extract name after "Full Name:" label
--name-regex "Full Name:\s*(.+)"

# Extract phone with various formats
--phone-regex "Phone:\s*([\d\-\(\)\s]+)"

# Extract from HTML emails
--name-regex "<strong>Name:</strong>\s*(.+?)</p>"

# Extract international phone numbers
--phone-regex "Phone:\s*(\+?[\d\s\-\(\)]+)"
```

**List all lead sources:**
```bash
gmail-lead-sync list-sources
```

Output example:
```
ID  Sender                  Identifier              Auto-Respond  Template
--  ----------------------  ----------------------  ------------  --------
1   leads@zillow.com        New Lead Notification   Yes           1
2   contact@realtor.com     Contact Request         No            None
```

**Update a lead source:**
```bash
# Update regex patterns
gmail-lead-sync update-source --id 1 --name-regex "Full Name:\s*(.+)"

# Enable auto-response
gmail-lead-sync update-source --id 1 --auto-respond --template-id 2

# Disable auto-response
gmail-lead-sync update-source --id 1 --no-auto-respond
```

**Delete a lead source:**
```bash
gmail-lead-sync delete-source --id 1
```

**Warning:** Deleting a lead source does not delete existing leads, but new emails from that sender will no longer be processed.

### Managing Templates

Templates define automated response emails with customizable placeholders.

**Add a new template:**
```bash
gmail-lead-sync add-template \
    --name "Default Acknowledgment" \
    --subject "Thank you for your inquiry" \
    --body-file template.txt
```

**Example template file (template.txt):**
```
Hello {lead_name},

Thank you for your interest in our real estate services. I received your inquiry and will get back to you shortly.

Best regards,
{agent_name}
{agent_phone}
{agent_email}
```

**Supported placeholders:**
- `{lead_name}`: Name extracted from the lead email
- `{agent_name}`: Your name (from configuration)
- `{agent_phone}`: Your phone number (from configuration)
- `{agent_email}`: Your email address (from configuration)

**List all templates:**
```bash
gmail-lead-sync list-templates
```

**Update a template:**
```bash
# Update template body
gmail-lead-sync update-template --id 1 --body-file new_template.txt

# Update subject line
gmail-lead-sync update-template --id 1 --subject "Thanks for reaching out!"
```

**Delete a template:**
```bash
gmail-lead-sync delete-template --id 1
```

**Warning:** Deleting a template will disable auto-responses for any lead sources using that template.

### Testing Regex Patterns

Before deploying regex patterns, test them against sample emails:

```bash
gmail-lead-sync test-parser \
    --email-file sample.txt \
    --name-regex "Name:\s*(.+)" \
    --phone-regex "Phone:\s*([\d\-]+)"
```

**Example sample.txt:**
```
New Lead Notification

Name: John Smith
Phone: 555-123-4567
Email: john@example.com

Message: I'm interested in viewing properties in downtown.
```

**Output:**
```
Testing name pattern: Name:\s*(.+)
✓ Match found: "John Smith"

Testing phone pattern: Phone:\s*([\d\-]+)
✓ Match found: "555-123-4567"

Both patterns matched successfully!
```

**Testing tips:**
- Always use capture groups `()` in your regex patterns
- Test with multiple sample emails to ensure consistency
- Check for edge cases (missing fields, extra whitespace, special characters)
- Use the `--verbose` flag to see all matches and context

### Viewing Processing Logs

Query the database to view processing history:

```bash
sqlite3 gmail_lead_sync.db "SELECT * FROM processing_logs ORDER BY timestamp DESC LIMIT 10;"
```

Or use Python:
```python
from gmail_lead_sync.models import ProcessingLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///gmail_lead_sync.db')
Session = sessionmaker(bind=engine)
session = Session()

# View recent logs
logs = session.query(ProcessingLog).order_by(ProcessingLog.timestamp.desc()).limit(10).all()
for log in logs:
    print(f"{log.timestamp} - {log.sender_email} - {log.status}")
```

### Health Check

Check system health status:

```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "imap": "connected",
  "last_successful_sync": "2024-01-15T10:30:00",
  "timestamp": "2024-01-15T10:35:00"
}
```

## Architecture

The system consists of the following components:

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Gmail Account                          │
│  ┌──────────────────┐              ┌──────────────────┐    │
│  │  Gmail Inbox     │              │   Gmail SMTP     │    │
│  │  (UNSEEN Emails) │              │   (Port 587)     │    │
│  └────────┬─────────┘              └────────▲─────────┘    │
└───────────┼────────────────────────────────┼───────────────┘
            │                                │
            │ IMAP                           │ SMTP
            │                                │
┌───────────▼────────────────────────────────┼───────────────┐
│                Gmail Lead Sync Engine      │               │
│  ┌──────────────────┐                      │               │
│  │     Watcher      │──────────────────────┘               │
│  │  (IMAP Monitor)  │                                      │
│  └────────┬─────────┘                                      │
│           │                                                 │
│           ▼                                                 │
│  ┌──────────────────┐         ┌──────────────────┐        │
│  │      Parser      │────────▶│  Auto Responder  │        │
│  │ (Regex Extract)  │         │  (SMTP Client)   │        │
│  └────────┬─────────┘         └──────────────────┘        │
│           │                                                 │
│           ▼                                                 │
│  ┌──────────────────────────────────────────────┐         │
│  │            SQLAlchemy ORM                     │         │
│  │  ┌────────────────────────────────────────┐  │         │
│  │  │      Credentials Store (AES-256)       │  │         │
│  │  └────────────────────────────────────────┘  │         │
│  └────────┬─────────────────────────────────────┘         │
│           │                                                 │
│           ▼                                                 │
│  ┌──────────────────┐                                      │
│  │ SQLite Database  │                                      │
│  │  • leads         │                                      │
│  │  • lead_sources  │                                      │
│  │  • templates     │                                      │
│  │  • proc_logs     │                                      │
│  │  • credentials   │                                      │
│  └──────────────────┘                                      │
│                                                             │
│  CLI Utilities:                                            │
│  • Config Manager  • Parser Tester  • Health Check        │
└─────────────────────────────────────────────────────────────┘
```

### Component Descriptions

- **Watcher**: Monitors Gmail inbox via IMAP for new emails
  - Connects using IMAP IDLE mode for real-time notifications
  - Implements exponential backoff retry logic (max 5 attempts)
  - Maintains connection resilience with automatic reconnection
  - Processes emails in chronological order

- **Parser**: Extracts lead information using configurable regex patterns
  - Matches sender email to Lead_Source configurations
  - Verifies identifier snippet exists in email body
  - Applies name_regex and phone_regex patterns
  - Validates extracted data with Pydantic models
  - Creates audit trail in Processing_Log

- **Auto Responder**: Sends automated acknowledgment emails via SMTP
  - Connects to Gmail SMTP with TLS encryption
  - Renders templates with placeholder replacement
  - Implements retry logic with exponential backoff (max 3 attempts)
  - Updates lead records with response status
  - Isolates failures to prevent blocking lead processing

- **Credentials Store**: Securely stores Gmail credentials with AES-256 encryption
  - Supports environment variable or database storage
  - Encrypts email and app password before storage
  - Never logs credentials in plain text
  - Provides secure retrieval for IMAP/SMTP connections

- **Configuration Manager**: CLI interface for managing lead sources and templates
  - Add, list, update, delete lead sources
  - Add, list, update, delete templates
  - Validates regex syntax and email formats
  - Validates template placeholders

- **Parser Tester**: Utility for testing regex patterns before deployment
  - Tests patterns against sample email content
  - Displays all matches with context
  - Validates regex syntax
  - Highlights matched text for visual confirmation

### Email Processing Flow

```
1. Email arrives in Gmail inbox (UNSEEN)
2. Watcher discovers email via IMAP search
3. Watcher checks if Gmail UID exists in database
   ├─ If exists: Skip (idempotent processing)
   └─ If new: Continue to step 4
4. Watcher retrieves email body and sender
5. Parser matches sender to Lead_Source configuration
   ├─ If no match: Log warning and skip
   └─ If match: Continue to step 6
6. Parser verifies identifier_snippet in email body
   ├─ If not found: Log mismatch and skip
   └─ If found: Continue to step 7
7. Parser applies name_regex and phone_regex
   ├─ If either fails: Log failure with patterns
   └─ If both succeed: Continue to step 8
8. Parser validates data with Pydantic
   ├─ If invalid: Log validation error
   └─ If valid: Continue to step 9
9. Parser creates Lead record and stores Gmail UID atomically
10. Processing_Log record created (success)
11. If auto_respond_enabled and template configured:
    ├─ Auto Responder renders template
    ├─ Auto Responder sends email via SMTP
    └─ Lead record updated with response status
12. Continue to next email
```

### State Transitions

```
Gmail Inbox (UNSEEN)
    ↓
Discovered by Watcher
    ↓
UID Check
    ├─ Already Processed → Skip
    └─ New Email → Continue
        ↓
    Parsing
        ├─ Failed → Log Error → Continue to Next
        └─ Success → Lead Created
            ↓
        Response Check
            ├─ No Template → Mark Processed
            └─ Template Configured → Send Response → Mark Processed
```

For detailed architecture diagrams, see the [Design Document](.kiro/specs/gmail-lead-sync-engine/design.md).

## Development

### Running Tests

Run all tests:
```bash
pytest
```

Run unit tests only:
```bash
pytest tests/unit
```

Run property-based tests:
```bash
pytest tests/property
```

Run with coverage:
```bash
pytest --cov=gmail_lead_sync --cov-report=html
```

### Code Quality

Format code with Black:
```bash
black gmail_lead_sync tests
```

Sort imports:
```bash
isort gmail_lead_sync tests
```

Type checking:
```bash
mypy gmail_lead_sync
```

## Security Considerations

- Never commit the `ENCRYPTION_KEY` to version control
- Store credentials in encrypted form only
- Use Gmail App Passwords, not main account passwords
- Restrict database file permissions: `chmod 600 gmail_lead_sync.db`
- Regularly rotate encryption keys and re-encrypt credentials

## Troubleshooting

### Connection Issues

**Problem: IMAP connection fails with authentication error**

Solutions:
1. Verify Gmail App Password is correct (16 characters, no spaces)
2. Check that 2FA is enabled on Gmail account
3. Ensure you're using an App Password, not your main account password
4. Verify the email address is correct
5. Check that IMAP is enabled in Gmail settings:
   - Go to Gmail Settings → Forwarding and POP/IMAP
   - Enable IMAP access

**Problem: Connection timeout or network errors**

Solutions:
1. Check firewall settings (allow outbound connections to imap.gmail.com:993)
2. Verify network connectivity: `ping imap.gmail.com`
3. Check if your ISP blocks IMAP ports
4. Try connecting from a different network
5. Review logs for specific error messages

**Problem: Connection drops frequently**

Solutions:
1. Check network stability
2. Increase IDLE timeout in watcher configuration
3. Review logs for patterns (time of day, specific operations)
4. The system will automatically reconnect with exponential backoff

**Problem: SMTP send fails**

Solutions:
1. Verify SMTP credentials match IMAP credentials
2. Check that TLS/STARTTLS is supported
3. Ensure outbound connections to smtp.gmail.com:587 are allowed
4. Check Gmail sending limits (500 emails per day for free accounts)
5. Review error logs for specific SMTP error codes

### Parsing Issues

**Problem: Leads are not being extracted from emails**

Diagnostic steps:
1. Check Processing_Log table for error details:
   ```bash
   sqlite3 gmail_lead_sync.db "SELECT * FROM processing_logs WHERE status != 'success' ORDER BY timestamp DESC LIMIT 10;"
   ```

2. Use the test-parser command to verify regex patterns:
   ```bash
   gmail-lead-sync test-parser --email-file sample.txt --name-regex "Name:\s*(.+)" --phone-regex "Phone:\s*([\d\-]+)"
   ```

3. Common issues:
   - **Identifier snippet not found**: The identifier text doesn't exist in the email body
     - Solution: Update identifier to match actual email content
   - **Regex pattern doesn't match**: The pattern doesn't match the email format
     - Solution: Test and adjust regex patterns using test-parser
   - **Missing capture groups**: Regex patterns must have `()` to capture data
     - Solution: Add capture groups: `Name:\s*(.+)` not `Name:\s*.+`
   - **Greedy matching**: Pattern captures too much text
     - Solution: Use non-greedy matching: `(.+?)` instead of `(.+)`

**Problem: Regex pattern matches wrong text**

Solutions:
1. Make patterns more specific:
   ```bash
   # Too broad
   --name-regex "Name:\s*(.+)"
   
   # More specific (stops at newline)
   --name-regex "Name:\s*([^\n]+)"
   
   # Even more specific (stops at specific delimiter)
   --name-regex "Name:\s*([^|]+)"
   ```

2. Use anchors and boundaries:
   ```bash
   # Match at start of line
   --name-regex "^Name:\s*(.+)"
   
   # Match word boundaries
   --phone-regex "\bPhone:\s*([\d\-]+)\b"
   ```

3. Test with multiple sample emails to ensure consistency

**Problem: Pydantic validation fails**

Common validation errors:
- **Phone too short**: Must have at least 7 digits
  - Solution: Ensure regex captures complete phone number
- **Invalid email format**: source_email must be valid email
  - Solution: Check Lead_Source sender_email configuration
- **Name contains only whitespace**: Name must have content
  - Solution: Adjust name_regex to exclude whitespace-only matches

Check validation errors in Processing_Log:
```bash
sqlite3 gmail_lead_sync.db "SELECT error_details FROM processing_logs WHERE status = 'validation_failed';"
```

**Problem: Multiple Lead_Source records match the same sender**

Behavior: The system uses the first matching Lead_Source with a valid identifier_snippet.

Solutions:
1. Make sender_email more specific (use exact address, not wildcards)
2. Use unique identifier_snippet for each Lead_Source
3. Delete or update duplicate Lead_Source records
4. Check Lead_Source priority by listing: `gmail-lead-sync list-sources`

### Database Issues

**Problem: Database locked errors**

Solutions:
1. Ensure only one instance of the watcher is running:
   ```bash
   ps aux | grep gmail-lead-sync
   ```
2. The system automatically retries with exponential backoff (up to 3 attempts)
3. If persistent, check for long-running queries or transactions
4. Consider increasing SQLite timeout in configuration

**Problem: Database file permissions error**

Solutions:
1. Check file permissions:
   ```bash
   ls -l gmail_lead_sync.db
   ```
2. Set correct permissions:
   ```bash
   chmod 600 gmail_lead_sync.db
   chown $USER:$USER gmail_lead_sync.db
   ```
3. Ensure the directory is writable:
   ```bash
   chmod 755 $(dirname gmail_lead_sync.db)
   ```

**Problem: Database corruption**

Solutions:
1. Check database integrity:
   ```bash
   sqlite3 gmail_lead_sync.db "PRAGMA integrity_check;"
   ```
2. If corrupted, restore from backup
3. If no backup, try to recover:
   ```bash
   sqlite3 gmail_lead_sync.db ".recover" | sqlite3 recovered.db
   ```
4. Prevent corruption:
   - Enable WAL mode (done automatically by migrations)
   - Ensure proper shutdown (Ctrl+C, not kill -9)
   - Regular backups

**Problem: Disk space full**

Solutions:
1. Check disk space:
   ```bash
   df -h
   ```
2. Clean up old processing logs:
   ```bash
   sqlite3 gmail_lead_sync.db "DELETE FROM processing_logs WHERE timestamp < datetime('now', '-30 days');"
   ```
3. Vacuum database to reclaim space:
   ```bash
   sqlite3 gmail_lead_sync.db "VACUUM;"
   ```

### Credential Issues

**Problem: Encryption key not found**

Error: `ENCRYPTION_KEY environment variable not set`

Solutions:
1. Set the environment variable:
   ```bash
   export ENCRYPTION_KEY="your-key-here"
   ```
2. Add to shell profile for persistence:
   ```bash
   echo 'export ENCRYPTION_KEY="your-key-here"' >> ~/.bashrc
   source ~/.bashrc
   ```
3. Verify it's set:
   ```bash
   echo $ENCRYPTION_KEY
   ```

**Problem: Decryption fails**

Error: `Invalid token` or `Decryption failed`

Causes:
- Encryption key changed after credentials were stored
- Database credentials corrupted
- Wrong encryption key being used

Solutions:
1. Verify you're using the correct encryption key
2. If key was rotated, re-encrypt credentials:
   ```python
   # Re-store credentials with new key
   from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
   store = EncryptedDBCredentialsStore(session)
   store.store_credentials("agent1", "email@gmail.com", "app-password")
   ```
3. As last resort, delete and re-create credentials

### Performance Issues

**Problem: Slow email processing**

Solutions:
1. Check database indexes:
   ```bash
   sqlite3 gmail_lead_sync.db ".schema" | grep INDEX
   ```
2. Ensure indexes exist on gmail_uid, sender_email, timestamp
3. Vacuum database to optimize:
   ```bash
   sqlite3 gmail_lead_sync.db "VACUUM; ANALYZE;"
   ```
4. Review regex patterns for catastrophic backtracking
5. Check system resources (CPU, memory, disk I/O)

**Problem: High memory usage**

Solutions:
1. Check for large email bodies being processed
2. Email bodies are limited to 1MB by default
3. Review logs for memory warnings
4. Restart the watcher periodically (e.g., daily via cron)

**Problem: Rate limiting**

Gmail limits:
- IMAP: ~100 requests per minute (handled automatically by rate limiter)
- SMTP: 500 emails per day for free accounts, 2000 for Google Workspace

Solutions:
1. The system implements automatic rate limiting
2. For SMTP limits, reduce auto-response frequency
3. Consider using multiple Gmail accounts for higher volume
4. Monitor rate limit warnings in logs

### Logging and Debugging

**Enable debug logging:**
```bash
export LOG_LEVEL=DEBUG
gmail-lead-sync start
```

**View logs:**
```bash
tail -f gmail_lead_sync.log
```

**Search logs for errors:**
```bash
grep ERROR gmail_lead_sync.log
grep -A 5 "Traceback" gmail_lead_sync.log  # Show stack traces
```

**Check health status:**
```bash
curl http://localhost:5000/health | python -m json.tool
```

**Query processing statistics:**
```sql
-- Success rate by sender
SELECT 
    sender_email,
    COUNT(*) as total,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM processing_logs
GROUP BY sender_email;

-- Recent failures
SELECT timestamp, sender_email, status, error_details
FROM processing_logs
WHERE status != 'success'
ORDER BY timestamp DESC
LIMIT 20;

-- Processing volume by day
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as emails_processed,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as leads_created
FROM processing_logs
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

### Common Error Messages

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `IMAP4.error: [AUTHENTICATIONFAILED]` | Invalid credentials | Verify app password and email |
| `Database is locked` | Concurrent access | Wait for retry, ensure single instance |
| `name_regex_no_match` | Regex doesn't match email | Test and adjust regex pattern |
| `identifier_snippet_not_found` | Identifier not in email | Update identifier to match email content |
| `validation_failed` | Data doesn't meet requirements | Check Pydantic validation rules |
| `SMTP authentication failed` | Invalid SMTP credentials | Verify credentials match IMAP |
| `Connection refused` | Network/firewall issue | Check network and firewall settings |
| `Invalid token` | Wrong encryption key | Verify ENCRYPTION_KEY is correct |

### Getting Help

If you're still experiencing issues:

1. **Check the logs** for detailed error messages and stack traces
2. **Review Processing_Log** table for parsing failures
3. **Test regex patterns** using the test-parser utility
4. **Verify configuration** (environment variables, database, credentials)
5. **Check system resources** (disk space, memory, network)
6. **Search existing issues** on the project repository
7. **Open a new issue** with:
   - Error messages and logs (redact sensitive information)
   - Steps to reproduce
   - System information (OS, Python version)
   - Configuration details (redact credentials)

## License

MIT License - See LICENSE file for details

## Systemd Service Installation (Linux)

For production deployments on Linux servers, you can run the Gmail Lead Sync Engine as a systemd service with automatic restart on failure.

### Prerequisites

1. Linux system with systemd (most modern distributions)
2. Python 3.10+ installed
3. Gmail Lead Sync Engine installed and configured

### Installation Steps

1. **Create a dedicated user for the service:**
```bash
sudo useradd -r -s /bin/false gmail-sync
```

2. **Create required directories:**
```bash
sudo mkdir -p /opt/gmail-lead-sync
sudo mkdir -p /var/lib/gmail-lead-sync
sudo mkdir -p /var/log/gmail-lead-sync
```

3. **Copy application files to /opt/gmail-lead-sync:**
```bash
sudo cp -r /path/to/gmail-lead-sync/* /opt/gmail-lead-sync/
```

4. **Create and activate virtual environment:**
```bash
cd /opt/gmail-lead-sync
sudo python3 -m venv venv
sudo /opt/gmail-lead-sync/venv/bin/pip install -r requirements.txt
sudo /opt/gmail-lead-sync/venv/bin/pip install -e .
```

5. **Set up the database:**
```bash
cd /opt/gmail-lead-sync
sudo -u gmail-sync /opt/gmail-lead-sync/venv/bin/alembic upgrade head
```

6. **Generate encryption key:**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Save this key securely - you'll need it in the next step.

7. **Configure the service file:**
```bash
sudo cp gmail-lead-sync.service /etc/systemd/system/
sudo nano /etc/systemd/system/gmail-lead-sync.service
```

Edit the service file and replace `REPLACE_WITH_YOUR_ENCRYPTION_KEY` with your actual encryption key.

**Alternative: Use environment file (recommended for security):**
```bash
sudo mkdir -p /etc/gmail-lead-sync
sudo nano /etc/gmail-lead-sync/environment
```

Add your environment variables:
```
ENCRYPTION_KEY=your-encryption-key-here
DATABASE_URL=sqlite:////var/lib/gmail-lead-sync/gmail_lead_sync.db
LOG_LEVEL=INFO
```

Then update the service file to use the environment file:
```bash
sudo nano /etc/systemd/system/gmail-lead-sync.service
```

Comment out the inline Environment lines and uncomment:
```
EnvironmentFile=/etc/gmail-lead-sync/environment
```

8. **Set correct permissions:**
```bash
sudo chown -R gmail-sync:gmail-sync /opt/gmail-lead-sync
sudo chown -R gmail-sync:gmail-sync /var/lib/gmail-lead-sync
sudo chown -R gmail-sync:gmail-sync /var/log/gmail-lead-sync
sudo chmod 600 /etc/gmail-lead-sync/environment  # If using environment file
sudo chmod 600 /var/lib/gmail-lead-sync/gmail_lead_sync.db
```

9. **Configure Gmail credentials:**

Option A - Using environment variables (add to environment file):
```bash
sudo nano /etc/gmail-lead-sync/environment
```
Add:
```
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
```

Option B - Using encrypted database storage:
```bash
sudo -u gmail-sync /opt/gmail-lead-sync/venv/bin/python -c "
from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
from gmail_lead_sync.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

os.environ['ENCRYPTION_KEY'] = 'your-encryption-key-here'
engine = create_engine('sqlite:////var/lib/gmail-lead-sync/gmail_lead_sync.db')
Session = sessionmaker(bind=engine)
session = Session()

store = EncryptedDBCredentialsStore(session, os.environ['ENCRYPTION_KEY'].encode())
store.store_credentials('agent1', 'your-email@gmail.com', 'your-app-password')
print('Credentials stored successfully')
"
```

10. **Reload systemd and enable the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable gmail-lead-sync.service
```

11. **Start the service:**
```bash
sudo systemctl start gmail-lead-sync.service
```

12. **Check service status:**
```bash
sudo systemctl status gmail-lead-sync.service
```

### Service Management Commands

**Start the service:**
```bash
sudo systemctl start gmail-lead-sync
```

**Stop the service:**
```bash
sudo systemctl stop gmail-lead-sync
```

**Restart the service:**
```bash
sudo systemctl restart gmail-lead-sync
```

**Check service status:**
```bash
sudo systemctl status gmail-lead-sync
```

**View service logs:**
```bash
sudo journalctl -u gmail-lead-sync -f
```

**View recent logs:**
```bash
sudo journalctl -u gmail-lead-sync -n 100
```

**View logs since boot:**
```bash
sudo journalctl -u gmail-lead-sync -b
```

**Disable auto-start on boot:**
```bash
sudo systemctl disable gmail-lead-sync
```

**Enable auto-start on boot:**
```bash
sudo systemctl enable gmail-lead-sync
```

### Service Features

The systemd service provides:

- **Automatic restart on failure**: If the service crashes, systemd will automatically restart it after 10 seconds
- **Starts after network is available**: Ensures network connectivity before starting
- **Runs as dedicated user**: Improves security by running with limited privileges
- **Security hardening**: Multiple security restrictions applied (see service file)
- **Logging to systemd journal**: All logs are captured by journalctl
- **Automatic start on boot**: Service starts automatically when the system boots

### Troubleshooting Systemd Service

**Service fails to start:**
1. Check service status: `sudo systemctl status gmail-lead-sync`
2. View detailed logs: `sudo journalctl -u gmail-lead-sync -n 50`
3. Verify file permissions: `ls -la /opt/gmail-lead-sync /var/lib/gmail-lead-sync`
4. Check environment variables: `sudo systemctl show gmail-lead-sync --property=Environment`
5. Test manually: `sudo -u gmail-sync /opt/gmail-lead-sync/venv/bin/python -m gmail_lead_sync start`

**Permission denied errors:**
```bash
# Fix ownership
sudo chown -R gmail-sync:gmail-sync /opt/gmail-lead-sync
sudo chown -R gmail-sync:gmail-sync /var/lib/gmail-lead-sync

# Fix database permissions
sudo chmod 600 /var/lib/gmail-lead-sync/gmail_lead_sync.db
```

**Service keeps restarting:**
1. Check logs for error messages: `sudo journalctl -u gmail-lead-sync -f`
2. Common causes:
   - Invalid encryption key
   - Missing or incorrect Gmail credentials
   - Database connection issues
   - Network connectivity problems
3. Test configuration manually before starting service

**Environment variables not loaded:**
1. Verify environment file exists: `ls -la /etc/gmail-lead-sync/environment`
2. Check file permissions: `sudo chmod 600 /etc/gmail-lead-sync/environment`
3. Verify EnvironmentFile line in service file is uncommented
4. Reload systemd: `sudo systemctl daemon-reload`

**Database locked errors:**
1. Ensure only one instance is running: `ps aux | grep gmail-lead-sync`
2. Stop any manual instances before starting service
3. Check for stale lock files

### Security Best Practices

1. **Use environment file instead of inline variables** to keep secrets out of service file
2. **Restrict environment file permissions**: `chmod 600 /etc/gmail-lead-sync/environment`
3. **Run as dedicated user** with minimal privileges
4. **Regularly rotate encryption keys** and re-encrypt credentials
5. **Monitor service logs** for suspicious activity
6. **Keep database backups** in secure location
7. **Use strong app passwords** and rotate them periodically
8. **Limit network access** using firewall rules if needed

### Backup and Recovery

**Backup database:**
```bash
sudo -u gmail-sync sqlite3 /var/lib/gmail-lead-sync/gmail_lead_sync.db ".backup /var/backups/gmail_lead_sync_$(date +%Y%m%d).db"
```

**Automated daily backups (cron):**
```bash
sudo crontab -e -u gmail-sync
```
Add:
```
0 2 * * * sqlite3 /var/lib/gmail-lead-sync/gmail_lead_sync.db ".backup /var/backups/gmail_lead_sync_$(date +\%Y\%m\%d).db"
```

**Restore from backup:**
```bash
sudo systemctl stop gmail-lead-sync
sudo -u gmail-sync cp /var/backups/gmail_lead_sync_20240115.db /var/lib/gmail-lead-sync/gmail_lead_sync.db
sudo systemctl start gmail-lead-sync
```

### Monitoring

**Set up monitoring alerts:**
1. Monitor service status with monitoring tools (Nagios, Zabbix, etc.)
2. Check health endpoint: `curl http://localhost:5000/health`
3. Monitor disk space: `/var/lib/gmail-lead-sync`
4. Monitor log file size: `/var/log/gmail-lead-sync`
5. Alert on service restarts: `journalctl -u gmail-lead-sync | grep "Started Gmail"`

**Example monitoring script:**
```bash
#!/bin/bash
# /usr/local/bin/check-gmail-sync.sh

if ! systemctl is-active --quiet gmail-lead-sync; then
    echo "CRITICAL: Gmail Lead Sync service is not running"
    exit 2
fi

HEALTH=$(curl -s http://localhost:5000/health | jq -r '.status')
if [ "$HEALTH" != "healthy" ]; then
    echo "WARNING: Gmail Lead Sync health check failed: $HEALTH"
    exit 1
fi

echo "OK: Gmail Lead Sync is running and healthy"
exit 0
```

## Support

For issues and questions, please open an issue on the project repository.
