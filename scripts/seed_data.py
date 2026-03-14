#!/usr/bin/env python3
"""
Seed data script for Gmail Lead Sync Web UI & API Layer.

This script generates demo data for testing and development purposes:
- Demo users (admin, viewer roles)
- Demo agents with encrypted Gmail credentials
- Demo lead sources with various regex patterns
- Demo templates with different content
- Demo leads with various statuses

Usage:
    python scripts/seed_data.py              # Add seed data (idempotent)
    python scripts/seed_data.py --clear      # Clear existing data before seeding

Features:
- Idempotent: Safe to run multiple times
- --clear flag: Deletes existing data before seeding
- Progress messages: Shows what's being created
- Error handling: Graceful error messages
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from gmail_lead_sync.models import Lead, LeadSource, Template, Credentials
from api.models.web_ui_models import User, Setting
from api.auth import hash_password
from gmail_lead_sync.credentials import EncryptedDBCredentialsStore


# Load environment variables
load_dotenv()


def get_database_session():
    """
    Create database session from environment configuration.
    
    Returns:
        SQLAlchemy session
        
    Raises:
        ValueError: If DATABASE_URL not set
    """
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./gmail_lead_sync.db')
    
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
    )
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def clear_data(db):
    """
    Clear all seed data from database.
    
    Deletes data in correct order to respect foreign key constraints.
    
    Args:
        db: Database session
    """
    print("Clearing existing data...")
    
    # Delete in order to respect foreign key constraints
    db.query(Lead).delete()
    print("  ✓ Cleared leads")
    
    db.query(LeadSource).delete()
    print("  ✓ Cleared lead sources")
    
    db.query(Template).delete()
    print("  ✓ Cleared templates")
    
    db.query(Credentials).delete()
    print("  ✓ Cleared credentials")
    
    db.query(Setting).delete()
    print("  ✓ Cleared settings")
    
    db.query(User).delete()
    print("  ✓ Cleared users")
    
    db.commit()
    print("✓ All data cleared\n")


def seed_users(db):
    """
    Create demo users.
    
    Creates:
    - admin user (username: admin, password: admin123)
    - viewer user (username: viewer, password: viewer123)
    
    Args:
        db: Database session
        
    Returns:
        Dictionary mapping username to User object
    """
    print("Creating demo users...")
    
    users = {}
    
    # Check if admin user exists
    admin = db.query(User).filter(User.username == 'admin').first()
    if not admin:
        admin = User(
            username='admin',
            password_hash=hash_password('admin123'),
            role='admin'
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print("  ✓ Created admin user (username: admin, password: admin123)")
    else:
        print("  ⊙ Admin user already exists")
    
    users['admin'] = admin
    
    # Check if viewer user exists
    viewer = db.query(User).filter(User.username == 'viewer').first()
    if not viewer:
        viewer = User(
            username='viewer',
            password_hash=hash_password('viewer123'),
            role='viewer'
        )
        db.add(viewer)
        db.commit()
        db.refresh(viewer)
        print("  ✓ Created viewer user (username: viewer, password: viewer123)")
    else:
        print("  ⊙ Viewer user already exists")
    
    users['viewer'] = viewer
    
    print()
    return users


def seed_templates(db):
    """
    Create demo email templates.
    
    Creates templates with various content and placeholders.
    
    Args:
        db: Database session
        
    Returns:
        List of created Template objects
    """
    print("Creating demo templates...")
    
    templates = []
    
    template_data = [
        {
            'name': 'Welcome Template',
            'subject': 'Thank you for your inquiry, {lead_name}',
            'body': '''Hi {lead_name},

Thank you for reaching out to us! We received your inquiry and are excited to help you.

I'm {agent_name}, and I'll be your point of contact. You can reach me at:
- Phone: {agent_phone}
- Email: {agent_email}

I'll be in touch with you shortly to discuss your needs.

Best regards,
{agent_name}'''
        },
        {
            'name': 'Quick Response',
            'subject': 'We received your message',
            'body': '''Hello {lead_name},

Thanks for contacting us! We'll get back to you soon.

{agent_name}
{agent_phone}'''
        },
        {
            'name': 'Detailed Follow-up',
            'subject': 'Following up on your inquiry',
            'body': '''Dear {lead_name},

I hope this message finds you well. I wanted to follow up on your recent inquiry.

Our team is ready to assist you with your needs. Please feel free to contact me directly:

{agent_name}
Phone: {agent_phone}
Email: {agent_email}

I look forward to speaking with you soon.

Warm regards,
{agent_name}'''
        }
    ]
    
    for data in template_data:
        # Check if template exists
        existing = db.query(Template).filter(Template.name == data['name']).first()
        if not existing:
            template = Template(**data)
            db.add(template)
            db.commit()
            db.refresh(template)
            templates.append(template)
            print(f"  ✓ Created template: {data['name']}")
        else:
            templates.append(existing)
            print(f"  ⊙ Template already exists: {data['name']}")
    
    print()
    return templates


def seed_agents(db, credentials_store):
    """
    Create demo agents with encrypted credentials.
    
    Creates agents with demo Gmail credentials (encrypted).
    
    Args:
        db: Database session
        credentials_store: EncryptedDBCredentialsStore instance
        
    Returns:
        List of agent_id strings
    """
    print("Creating demo agents...")
    
    agents = []
    
    agent_data = [
        {
            'agent_id': 'demo_agent_1',
            'email': 'demo.agent1@example.com',
            'app_password': 'demo-app-password-1234'
        },
        {
            'agent_id': 'demo_agent_2',
            'email': 'demo.agent2@example.com',
            'app_password': 'demo-app-password-5678'
        },
        {
            'agent_id': 'demo_agent_3',
            'email': 'demo.agent3@example.com',
            'app_password': 'demo-app-password-9012'
        }
    ]
    
    for data in agent_data:
        # Check if agent exists
        existing = db.query(Credentials).filter(Credentials.agent_id == data['agent_id']).first()
        if not existing:
            credentials_store.store_credentials(
                agent_id=data['agent_id'],
                email=data['email'],
                app_password=data['app_password']
            )
            agents.append(data['agent_id'])
            print(f"  ✓ Created agent: {data['agent_id']} ({data['email']})")
        else:
            agents.append(data['agent_id'])
            print(f"  ⊙ Agent already exists: {data['agent_id']}")
    
    print()
    return agents


def seed_lead_sources(db, templates):
    """
    Create demo lead sources with various regex patterns.
    
    Args:
        db: Database session
        templates: List of Template objects to associate with lead sources
        
    Returns:
        List of created LeadSource objects
    """
    print("Creating demo lead sources...")
    
    lead_sources = []
    
    lead_source_data = [
        {
            'sender_email': 'leads@zillow.com',
            'identifier_snippet': 'New Lead Notification',
            'name_regex': r'Name:\s*(.+)',
            'phone_regex': r'Phone:\s*([\d\-\(\)\s]+)',
            'template_id': templates[0].id if templates else None,
            'auto_respond_enabled': True
        },
        {
            'sender_email': 'notifications@realtor.com',
            'identifier_snippet': 'You have a new inquiry',
            'name_regex': r'Client Name:\s*(.+)',
            'phone_regex': r'Contact:\s*([\d\-\(\)\s]+)',
            'template_id': templates[1].id if len(templates) > 1 else None,
            'auto_respond_enabled': True
        },
        {
            'sender_email': 'leads@redfin.com',
            'identifier_snippet': 'New buyer inquiry',
            'name_regex': r'Buyer:\s*(.+)',
            'phone_regex': r'Phone Number:\s*([\d\-\(\)\s]+)',
            'template_id': templates[2].id if len(templates) > 2 else None,
            'auto_respond_enabled': False
        },
        {
            'sender_email': 'system@trulia.com',
            'identifier_snippet': 'Lead Alert',
            'name_regex': r'Full Name:\s*(.+)',
            'phone_regex': r'Tel:\s*([\d\-\(\)\s]+)',
            'template_id': templates[0].id if templates else None,
            'auto_respond_enabled': True
        },
        {
            'sender_email': 'alerts@homes.com',
            'identifier_snippet': 'Property Inquiry',
            'name_regex': r'Inquirer:\s*(.+)',
            'phone_regex': r'Phone:\s*([\d\-\(\)\s]+)',
            'template_id': templates[1].id if len(templates) > 1 else None,
            'auto_respond_enabled': False
        }
    ]
    
    for data in lead_source_data:
        # Check if lead source exists
        existing = db.query(LeadSource).filter(LeadSource.sender_email == data['sender_email']).first()
        if not existing:
            lead_source = LeadSource(**data)
            db.add(lead_source)
            db.commit()
            db.refresh(lead_source)
            lead_sources.append(lead_source)
            print(f"  ✓ Created lead source: {data['sender_email']}")
        else:
            lead_sources.append(existing)
            print(f"  ⊙ Lead source already exists: {data['sender_email']}")
    
    print()
    return lead_sources


def seed_leads(db, lead_sources):
    """
    Create demo leads with various statuses.
    
    Args:
        db: Database session
        lead_sources: List of LeadSource objects to associate with leads
        
    Returns:
        List of created Lead objects
    """
    print("Creating demo leads...")
    
    if not lead_sources:
        print("  ⚠ No lead sources available, skipping lead creation")
        print()
        return []
    
    leads = []
    
    # Generate leads with various statuses
    lead_data = [
        {
            'name': 'John Smith',
            'phone': '555-0101',
            'source_email': lead_sources[0].sender_email,
            'lead_source_id': lead_sources[0].id,
            'gmail_uid': 'demo_uid_001',
            'response_sent': True,
            'response_status': 'success',
            'created_at': datetime.utcnow() - timedelta(days=5)
        },
        {
            'name': 'Jane Doe',
            'phone': '555-0102',
            'source_email': lead_sources[0].sender_email,
            'lead_source_id': lead_sources[0].id,
            'gmail_uid': 'demo_uid_002',
            'response_sent': True,
            'response_status': 'success',
            'created_at': datetime.utcnow() - timedelta(days=4)
        },
        {
            'name': 'Bob Johnson',
            'phone': '555-0103',
            'source_email': lead_sources[1].sender_email if len(lead_sources) > 1 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[1].id if len(lead_sources) > 1 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_003',
            'response_sent': False,
            'response_status': None,
            'created_at': datetime.utcnow() - timedelta(days=3)
        },
        {
            'name': 'Alice Williams',
            'phone': '555-0104',
            'source_email': lead_sources[1].sender_email if len(lead_sources) > 1 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[1].id if len(lead_sources) > 1 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_004',
            'response_sent': True,
            'response_status': 'failed',
            'created_at': datetime.utcnow() - timedelta(days=2)
        },
        {
            'name': 'Charlie Brown',
            'phone': '555-0105',
            'source_email': lead_sources[2].sender_email if len(lead_sources) > 2 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[2].id if len(lead_sources) > 2 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_005',
            'response_sent': True,
            'response_status': 'success',
            'created_at': datetime.utcnow() - timedelta(days=1)
        },
        {
            'name': 'Diana Prince',
            'phone': '555-0106',
            'source_email': lead_sources[0].sender_email,
            'lead_source_id': lead_sources[0].id,
            'gmail_uid': 'demo_uid_006',
            'response_sent': False,
            'response_status': None,
            'created_at': datetime.utcnow() - timedelta(hours=12)
        },
        {
            'name': 'Edward Norton',
            'phone': '555-0107',
            'source_email': lead_sources[1].sender_email if len(lead_sources) > 1 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[1].id if len(lead_sources) > 1 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_007',
            'response_sent': True,
            'response_status': 'success',
            'created_at': datetime.utcnow() - timedelta(hours=6)
        },
        {
            'name': 'Fiona Green',
            'phone': '555-0108',
            'source_email': lead_sources[2].sender_email if len(lead_sources) > 2 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[2].id if len(lead_sources) > 2 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_008',
            'response_sent': False,
            'response_status': None,
            'created_at': datetime.utcnow() - timedelta(hours=3)
        },
        {
            'name': 'George Harris',
            'phone': '555-0109',
            'source_email': lead_sources[3].sender_email if len(lead_sources) > 3 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[3].id if len(lead_sources) > 3 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_009',
            'response_sent': True,
            'response_status': 'success',
            'created_at': datetime.utcnow() - timedelta(hours=2)
        },
        {
            'name': 'Helen Clark',
            'phone': '555-0110',
            'source_email': lead_sources[4].sender_email if len(lead_sources) > 4 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[4].id if len(lead_sources) > 4 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_010',
            'response_sent': False,
            'response_status': None,
            'created_at': datetime.utcnow() - timedelta(hours=1)
        },
        {
            'name': 'Ivan Martinez',
            'phone': '555-0111',
            'source_email': lead_sources[0].sender_email,
            'lead_source_id': lead_sources[0].id,
            'gmail_uid': 'demo_uid_011',
            'response_sent': True,
            'response_status': 'success',
            'created_at': datetime.utcnow() - timedelta(minutes=45)
        },
        {
            'name': 'Julia Anderson',
            'phone': '555-0112',
            'source_email': lead_sources[1].sender_email if len(lead_sources) > 1 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[1].id if len(lead_sources) > 1 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_012',
            'response_sent': False,
            'response_status': None,
            'created_at': datetime.utcnow() - timedelta(minutes=30)
        },
        {
            'name': 'Kevin Lee',
            'phone': '555-0113',
            'source_email': lead_sources[2].sender_email if len(lead_sources) > 2 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[2].id if len(lead_sources) > 2 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_013',
            'response_sent': True,
            'response_status': 'failed',
            'created_at': datetime.utcnow() - timedelta(minutes=20)
        },
        {
            'name': 'Laura Wilson',
            'phone': '555-0114',
            'source_email': lead_sources[0].sender_email,
            'lead_source_id': lead_sources[0].id,
            'gmail_uid': 'demo_uid_014',
            'response_sent': True,
            'response_status': 'success',
            'created_at': datetime.utcnow() - timedelta(minutes=15)
        },
        {
            'name': 'Michael Taylor',
            'phone': '555-0115',
            'source_email': lead_sources[1].sender_email if len(lead_sources) > 1 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[1].id if len(lead_sources) > 1 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_015',
            'response_sent': False,
            'response_status': None,
            'created_at': datetime.utcnow() - timedelta(minutes=10)
        },
        {
            'name': 'Nancy Thomas',
            'phone': '555-0116',
            'source_email': lead_sources[2].sender_email if len(lead_sources) > 2 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[2].id if len(lead_sources) > 2 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_016',
            'response_sent': True,
            'response_status': 'success',
            'created_at': datetime.utcnow() - timedelta(minutes=5)
        },
        {
            'name': 'Oliver Jackson',
            'phone': '555-0117',
            'source_email': lead_sources[3].sender_email if len(lead_sources) > 3 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[3].id if len(lead_sources) > 3 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_017',
            'response_sent': False,
            'response_status': None,
            'created_at': datetime.utcnow() - timedelta(minutes=3)
        },
        {
            'name': 'Patricia White',
            'phone': '555-0118',
            'source_email': lead_sources[4].sender_email if len(lead_sources) > 4 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[4].id if len(lead_sources) > 4 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_018',
            'response_sent': True,
            'response_status': 'success',
            'created_at': datetime.utcnow() - timedelta(minutes=2)
        },
        {
            'name': 'Quincy Adams',
            'phone': '555-0119',
            'source_email': lead_sources[0].sender_email,
            'lead_source_id': lead_sources[0].id,
            'gmail_uid': 'demo_uid_019',
            'response_sent': False,
            'response_status': None,
            'created_at': datetime.utcnow() - timedelta(minutes=1)
        },
        {
            'name': 'Rachel Moore',
            'phone': '555-0120',
            'source_email': lead_sources[1].sender_email if len(lead_sources) > 1 else lead_sources[0].sender_email,
            'lead_source_id': lead_sources[1].id if len(lead_sources) > 1 else lead_sources[0].id,
            'gmail_uid': 'demo_uid_020',
            'response_sent': True,
            'response_status': 'success',
            'created_at': datetime.utcnow()
        }
    ]
    
    for data in lead_data:
        # Check if lead exists
        existing = db.query(Lead).filter(Lead.gmail_uid == data['gmail_uid']).first()
        if not existing:
            lead = Lead(**data)
            db.add(lead)
            db.commit()
            db.refresh(lead)
            leads.append(lead)
            print(f"  ✓ Created lead: {data['name']} ({data['phone']})")
        else:
            leads.append(existing)
            print(f"  ⊙ Lead already exists: {data['name']}")
    
    print()
    return leads


def seed_settings(db):
    """
    Create default system settings.
    
    Args:
        db: Database session
    """
    print("Creating default settings...")
    
    settings_data = [
        {'key': 'sync_interval_seconds', 'value': '300'},
        {'key': 'regex_timeout_ms', 'value': '1000'},
        {'key': 'session_timeout_hours', 'value': '24'},
        {'key': 'max_leads_per_page', 'value': '50'},
        {'key': 'enable_auto_restart', 'value': 'true'}
    ]
    
    for data in settings_data:
        # Check if setting exists
        existing = db.query(Setting).filter(Setting.key == data['key']).first()
        if not existing:
            setting = Setting(**data)
            db.add(setting)
            db.commit()
            print(f"  ✓ Created setting: {data['key']} = {data['value']}")
        else:
            print(f"  ⊙ Setting already exists: {data['key']}")
    
    print()


def main():
    """
    Main entry point for seed data script.
    
    Parses command line arguments and executes seeding operations.
    """
    parser = argparse.ArgumentParser(
        description='Seed demo data for Gmail Lead Sync Web UI & API Layer'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing data before seeding'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Gmail Lead Sync - Seed Data Script")
    print("=" * 60)
    print()
    
    try:
        # Get database session
        db = get_database_session()
        print("✓ Connected to database\n")
        
        # Get encryption key for credentials
        encryption_key = os.getenv('ENCRYPTION_KEY')
        if not encryption_key:
            print("✗ Error: ENCRYPTION_KEY environment variable not set")
            print("  Generate key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
            sys.exit(1)
        
        # Create credentials store
        credentials_store = EncryptedDBCredentialsStore(db, encryption_key=encryption_key)
        
        # Clear data if requested
        if args.clear:
            clear_data(db)
        
        # Seed data in order
        users = seed_users(db)
        templates = seed_templates(db)
        agents = seed_agents(db, credentials_store)
        lead_sources = seed_lead_sources(db, templates)
        leads = seed_leads(db, lead_sources)
        seed_settings(db)

        # Seed preapproval data (form, scoring, message templates) for tenant 1
        try:
            from gmail_lead_sync.preapproval.seed import seed_all as seed_preapproval
            seed_preapproval(db, tenant_id=1)
            print("✓ Preapproval seed data created (tenant_id=1)")
        except Exception as e:
            print(f"  (preapproval seed skipped: {e})")
        
        # Summary
        print("=" * 60)
        print("Seed data complete!")
        print("=" * 60)
        print()
        print("Summary:")
        print(f"  Users: {len(users)}")
        print(f"  Templates: {len(templates)}")
        print(f"  Agents: {len(agents)}")
        print(f"  Lead Sources: {len(lead_sources)}")
        print(f"  Leads: {len(leads)}")
        print()
        print("Login credentials:")
        print("  Admin: username=admin, password=admin123")
        print("  Viewer: username=viewer, password=viewer123")
        print()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        if 'db' in locals():
            db.close()


if __name__ == '__main__':
    main()
