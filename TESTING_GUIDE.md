# Gmail Lead Sync - Live Testing Guide

This guide will walk you through testing the Gmail Lead Sync Engine with your real Gmail account.

## Prerequisites

- Gmail account with 2FA enabled
- Python 3.10+ installed
- All dependencies installed (`pip install -r requirements.txt`)

## Step 1: Set Up Gmail App Password

1. **Enable 2-Factor Authentication** (if not already enabled):
   - Go to https://myaccount.google.com/security
   - Under "Signing in to Google", select "2-Step Verification"
   - Follow the prompts to enable 2FA

2. **Generate App Password**:
   - Visit https://myaccount.google.com/apppasswords
   - Select "Mail" as the app
   - Select "Other" as the device
   - Enter "Gmail Lead Sync" as the custom name
   - Click "Generate"
   - **Copy the 16-character password** (format: `xxxx xxxx xxxx xxxx`)
   - Remove spaces when using it: `xxxxxxxxxxxxxxxx`

3. **Enable IMAP** (if not already enabled):
   - Go to Gmail Settings → Forwarding and POP/IMAP
   - Enable IMAP access
   - Save changes

## Step 2: Set Environment Variables

Set your credentials as environment variables:

```bash
# Set the encryption key (already generated)
export ENCRYPTION_KEY="381SQe-HnEQJ1IOwI29L5U4NSJu6em_GyHuW5izVoz4="

# Set your Gmail email
export GMAIL_EMAIL="your-email@gmail.com"

# Set your Gmail App Password (remove spaces)
export GMAIL_APP_PASSWORD="xxxxxxxxxxxxxxxx"
```

**Verify they're set:**
```bash
echo $ENCRYPTION_KEY
echo $GMAIL_EMAIL
echo $GMAIL_APP_PASSWORD
```

## Step 3: Initialize the Database

Run the database migrations:

```bash
alembic upgrade head
```

This creates the SQLite database with all required tables.

## Step 4: Create a Test Email Template

Create a simple response template:

```bash
cat > test_template.txt << 'EOF'
Hello {lead_name},

Thank you for your inquiry! I received your contact information and will get back to you shortly.

Best regards,
Your Real Estate Agent
{agent_email}
EOF
```

Add the template to the database:

```bash
python -m gmail_lead_sync add-template \
    --name "Test Acknowledgment" \
    --subject "Thanks for reaching out!" \
    --body-file test_template.txt
```

## Step 5: Configure a Lead Source

Let's set up a test lead source. We'll use your own email as the sender for testing:

```bash
python -m gmail_lead_sync add-source \
    --sender "$GMAIL_EMAIL" \
    --identifier "Test Lead" \
    --name-regex "Name:\s*(.+)" \
    --phone-regex "Phone:\s*([\d\-\(\)\s]+)" \
    --template-id 1
```

**Verify it was added:**
```bash
python -m gmail_lead_sync list-sources
```

## Step 6: Send Yourself a Test Email

Send an email to yourself with this content:

**To:** your-email@gmail.com  
**Subject:** Test Lead Notification  
**Body:**
```
Test Lead

Name: John Smith
Phone: 555-123-4567
Email: john@example.com

This is a test lead for the Gmail Lead Sync system.
```

**Important:** Make sure the email is UNREAD in your inbox!

## Step 7: Test the Parser

Before running the watcher, let's test that the parser can extract the lead:

```bash
# Create a sample email file
cat > sample_test_email.txt << 'EOF'
Test Lead

Name: John Smith
Phone: 555-123-4567
Email: john@example.com

This is a test lead for the Gmail Lead Sync system.
EOF

# Test the regex patterns
python -m gmail_lead_sync test-parser \
    --email-file sample_test_email.txt \
    --name-regex "Name:\s*(.+)" \
    --phone-regex "Phone:\s*([\d\-\(\)\s]+)"
```

You should see:
```
✓ Name match found: "John Smith"
✓ Phone match found: "555-123-4567"
```

## Step 8: Run the Watcher (Dry Run)

Now let's run the watcher to process the email:

```bash
python -m gmail_lead_sync start --use-env --log-level DEBUG
```

**What should happen:**
1. The watcher connects to Gmail via IMAP
2. It searches for UNSEEN emails from your email address
3. It finds the test email you sent
4. It extracts the lead information (Name: John Smith, Phone: 555-123-4567)
5. It stores the lead in the database
6. It sends an acknowledgment email back to you (if auto-respond is enabled)

**Watch the logs for:**
- `IMAP connection established`
- `Successfully connected to Gmail`
- `Matched Lead_Source ID 1`
- `Successfully extracted lead: name='John Smith', phone='555-123-4567'`
- `Created Lead ID 1`

**Stop the watcher:** Press `Ctrl+C` when done

## Step 9: Verify the Lead Was Created

Check the database to see if the lead was stored:

```bash
sqlite3 gmail_lead_sync.db "SELECT * FROM leads;"
```

You should see your test lead with:
- name: John Smith
- phone: 555-123-4567
- source_email: your-email@gmail.com

**Check processing logs:**
```bash
sqlite3 gmail_lead_sync.db "SELECT timestamp, sender_email, status FROM processing_logs ORDER BY timestamp DESC LIMIT 5;"
```

## Step 10: Check for Response Email

Check your Gmail inbox for the acknowledgment email. It should have:
- **Subject:** Thanks for reaching out!
- **Body:** Hello John Smith, Thank you for your inquiry...

## Step 11: Test Idempotency

Mark the test email as UNREAD again and run the watcher:

```bash
python -m gmail_lead_sync start --use-env --log-level DEBUG
```

**What should happen:**
- The watcher finds the email again
- It checks if the Gmail UID exists in the database
- It skips processing because it was already processed
- You should see: `Email already processed (duplicate UID), skipping`

This proves the system is idempotent!

## Step 12: Test with Multiple Emails

Send yourself 2-3 more test emails with different names and phone numbers:

**Email 2:**
```
Test Lead

Name: Jane Doe
Phone: 555-987-6543
```

**Email 3:**
```
Test Lead

Name: Bob Johnson
Phone: (555) 456-7890
```

Run the watcher and verify all leads are processed:

```bash
python -m gmail_lead_sync start --use-env --log-level DEBUG
```

Check the database:
```bash
sqlite3 gmail_lead_sync.db "SELECT id, name, phone FROM leads;"
```

## Troubleshooting

### Connection Issues

**Error: `IMAP4.error: [AUTHENTICATIONFAILED]`**
- Verify your Gmail App Password is correct (16 characters, no spaces)
- Check that 2FA is enabled
- Make sure you're using an App Password, not your main password

**Error: `Connection timeout`**
- Check your internet connection
- Verify firewall allows connections to imap.gmail.com:993
- Try from a different network

### Parsing Issues

**Error: `No Lead_Source configuration found`**
- Verify the sender email matches: `python -m gmail_lead_sync list-sources`
- Make sure you sent the email from the same address

**Error: `identifier_snippet not in email body`**
- Check that "Test Lead" appears in your email body
- The identifier is case-sensitive

**Error: `name_regex_no_match` or `phone_regex_no_match`**
- Use the test-parser command to debug your regex patterns
- Make sure the email format matches the patterns

### Database Issues

**Error: `Database is locked`**
- Make sure only one instance of the watcher is running
- Stop any other processes accessing the database

## Success Criteria

✅ Watcher connects to Gmail successfully  
✅ Test email is discovered and processed  
✅ Lead is extracted and stored in database  
✅ Acknowledgment email is sent (if enabled)  
✅ Duplicate emails are skipped (idempotency)  
✅ Multiple leads can be processed in sequence  

## Next Steps

Once testing is successful:

1. **Configure real lead sources** for your actual email senders (Zillow, Realtor.com, etc.)
2. **Customize templates** for different lead sources
3. **Deploy to production** using the DEPLOYMENT.md guide
4. **Set up monitoring** using the health check endpoint
5. **Configure systemd service** for automatic startup

## Clean Up Test Data

To clean up test data:

```bash
# Delete test leads
sqlite3 gmail_lead_sync.db "DELETE FROM leads WHERE source_email = '$GMAIL_EMAIL';"

# Delete test processing logs
sqlite3 gmail_lead_sync.db "DELETE FROM processing_logs WHERE sender_email = '$GMAIL_EMAIL';"

# Delete test lead source
python -m gmail_lead_sync delete-source --id 1

# Delete test template
python -m gmail_lead_sync delete-template --id 1
```

## Support

If you encounter issues:
1. Check the logs: `tail -f gmail_lead_sync.log`
2. Review the troubleshooting section in README.md
3. Check processing logs in the database
4. Run with DEBUG logging for more details
