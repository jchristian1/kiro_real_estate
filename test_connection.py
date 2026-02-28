#!/usr/bin/env python
"""
Simple test script to verify Gmail IMAP connection.
"""
import os
import imaplib
import sys

print("=" * 60)
print("Gmail IMAP Connection Test")
print("=" * 60)

# Get credentials from environment
email = os.getenv('GMAIL_EMAIL')
password = os.getenv('GMAIL_APP_PASSWORD')

if not email or not password:
    print("❌ ERROR: Environment variables not set!")
    print("Please set:")
    print("  export GMAIL_EMAIL='your-email@gmail.com'")
    print("  export GMAIL_APP_PASSWORD='your-app-password'")
    sys.exit(1)

print(f"\n📧 Email: {email}")
print(f"🔑 Password: {'*' * len(password)} ({len(password)} characters)")

print("\n🔌 Connecting to imap.gmail.com:993...")

try:
    # Connect to Gmail IMAP
    mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    print("✅ SSL connection established")
    
    # Login
    print(f"\n🔐 Logging in as {email}...")
    mail.login(email, password)
    print("✅ Login successful!")
    
    # Select inbox
    print("\n📬 Selecting INBOX...")
    status, messages = mail.select('INBOX')
    print(f"✅ INBOX selected: {messages[0].decode()} total messages")
    
    # Search for UNSEEN emails
    print(f"\n🔍 Searching for UNSEEN emails from {email}...")
    status, message_ids = mail.search(None, f'(UNSEEN FROM "{email}")')
    
    if message_ids[0]:
        ids = message_ids[0].split()
        print(f"✅ Found {len(ids)} UNSEEN email(s)!")
        print(f"   Email IDs: {ids}")
    else:
        print("⚠️  No UNSEEN emails found")
        print("   Make sure you sent the test email and it's still UNREAD")
    
    # Logout
    print("\n👋 Logging out...")
    mail.logout()
    print("✅ Disconnected successfully")
    
    print("\n" + "=" * 60)
    print("✅ CONNECTION TEST PASSED!")
    print("=" * 60)
    
except imaplib.IMAP4.error as e:
    print(f"\n❌ IMAP Error: {e}")
    print("\nPossible issues:")
    print("  1. App Password is incorrect")
    print("  2. IMAP is not enabled in Gmail settings")
    print("  3. 2FA is not enabled")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
