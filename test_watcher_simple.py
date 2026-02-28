#!/usr/bin/env python
"""
Simple watcher test - processes just the most recent UNSEEN email.
"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gmail_lead_sync.models import Base
from gmail_lead_sync.credentials import EnvironmentCredentialsStore
from gmail_lead_sync.watcher import GmailWatcher

print("=" * 60)
print("Gmail Lead Sync - Simple Watcher Test")
print("=" * 60)

# Check environment variables
email = os.getenv('GMAIL_EMAIL')
password = os.getenv('GMAIL_APP_PASSWORD')

if not email or not password:
    print("❌ ERROR: Environment variables not set!")
    sys.exit(1)

print(f"\n📧 Email: {email}")
print(f"🔑 Password: Set ({len(password)} characters)")

# Set up database
print("\n💾 Setting up database...")
engine = create_engine('sqlite:///gmail_lead_sync.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
db_session = SessionLocal()
print("✅ Database ready")

# Set up credentials store
print("\n🔐 Setting up credentials...")
credentials_store = EnvironmentCredentialsStore()
print("✅ Credentials store ready")

# Create watcher
print("\n👀 Creating watcher...")
watcher = GmailWatcher(credentials_store, db_session, agent_id='default')
print("✅ Watcher created")

# Connect
print("\n🔌 Connecting to Gmail...")
if watcher.connect():
    print("✅ Connected successfully!")
    
    # Process emails from your address only
    sender_list = [email]
    print(f"\n📬 Processing UNSEEN emails from: {sender_list}")
    print("   (This will process ALL unread emails from you)")
    print("   Press Ctrl+C to stop\n")
    
    try:
        watcher.process_unseen_emails(sender_list)
        print("\n✅ Processing complete!")
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n👋 Disconnecting...")
        watcher.disconnect()
        print("✅ Disconnected")
        
        # Show results
        print("\n" + "=" * 60)
        print("📊 Results:")
        print("=" * 60)
        
        from gmail_lead_sync.models import Lead, ProcessingLog
        
        leads = db_session.query(Lead).all()
        print(f"\n✅ Total leads in database: {len(leads)}")
        
        if leads:
            print("\nLeads:")
            for lead in leads[-5:]:  # Show last 5
                print(f"  - {lead.name} | {lead.phone} | {lead.source_email}")
        
        logs = db_session.query(ProcessingLog).order_by(ProcessingLog.timestamp.desc()).limit(5).all()
        print(f"\n📝 Recent processing logs: {len(logs)}")
        for log in logs:
            print(f"  - {log.timestamp} | {log.status} | {log.sender_email}")
        
        db_session.close()
else:
    print("❌ Failed to connect")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ TEST COMPLETE!")
print("=" * 60)
