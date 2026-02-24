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

### Gmail App Password Setup

1. Enable 2-factor authentication on your Gmail account
2. Generate an app-specific password at https://myaccount.google.com/apppasswords
3. Store the 16-character app password securely

### Encryption Key Generation

Generate an encryption key for secure credential storage:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set the encryption key as an environment variable:

```bash
export ENCRYPTION_KEY="your-generated-key-here"
```

### Database Initialization

Initialize the database with Alembic migrations:

```bash
alembic upgrade head
```

## Usage

### Start the Watcher

```bash
gmail-lead-sync start
```

### Manage Lead Sources

Add a new lead source:
```bash
gmail-lead-sync add-source \
    --sender "leads@example.com" \
    --identifier "New Lead Notification" \
    --name-regex "Name:\s*(.+)" \
    --phone-regex "Phone:\s*([\d\-]+)" \
    --template-id 1
```

List all lead sources:
```bash
gmail-lead-sync list-sources
```

Update a lead source:
```bash
gmail-lead-sync update-source --id 1 --name-regex "Full Name:\s*(.+)"
```

Delete a lead source:
```bash
gmail-lead-sync delete-source --id 1
```

### Manage Templates

Add a new template:
```bash
gmail-lead-sync add-template \
    --name "Default Acknowledgment" \
    --subject "Thank you for your inquiry" \
    --body-file template.txt
```

List all templates:
```bash
gmail-lead-sync list-templates
```

### Test Regex Patterns

Test parsing patterns against sample emails:

```bash
gmail-lead-sync test-parser \
    --email-file sample.txt \
    --name-regex "Name:\s*(.+)" \
    --phone-regex "Phone:\s*([\d\-]+)"
```

## Architecture

The system consists of the following components:

- **Watcher**: Monitors Gmail inbox via IMAP for new emails
- **Parser**: Extracts lead information using configurable regex patterns
- **Auto Responder**: Sends automated acknowledgment emails via SMTP
- **Credentials Store**: Securely stores Gmail credentials with AES-256 encryption
- **Configuration Manager**: CLI interface for managing lead sources and templates
- **Parser Tester**: Utility for testing regex patterns before deployment

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

If IMAP connection fails:
1. Verify Gmail App Password is correct
2. Check that 2FA is enabled on Gmail account
3. Ensure IMAP is enabled in Gmail settings
4. Check firewall/network settings

### Parsing Issues

If leads are not being extracted:
1. Use the `test-parser` command to verify regex patterns
2. Check Processing_Log table for error details
3. Verify identifier_snippet exists in email body
4. Ensure regex patterns have capture groups: `(.+)`

### Database Issues

If database operations fail:
1. Check file permissions on database file
2. Ensure only one instance of the watcher is running
3. Check disk space availability
4. Review logs for lock timeout errors

## License

MIT License - See LICENSE file for details

## Support

For issues and questions, please open an issue on the project repository.
